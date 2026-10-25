"""A current job's source-position snapshot; never a cache of market results."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
import fcntl
from .config import config
import uuid
from typing import Any

from sqlalchemy.orm import Session

from .models import Client, Job, now_utc

AWAITING_EXACT_SELECTION = "awaiting_exact_selection"
AWAITING_POSITION_SELECTION = "awaiting_position_selection"
SELECTION_STATUSES = {AWAITING_EXACT_SELECTION, AWAITING_POSITION_SELECTION}
MAX_SELECTED_POSITIONS = 5


def read_selection(job: Job) -> dict[str, Any]:
    try:
        value = json.loads(getattr(job, "position_selection_json", "") or "{}")
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def build_selection_snapshot(items: list[dict], *, price_kopeks: int, mode: str = "exact_product") -> str:
    rows = []
    for index, original in enumerate(items, 1):
        if not isinstance(original, dict):
            continue
        row = dict(original)
        row_id = uuid.uuid4().hex[:16]
        row.update(id=row_id, position_id=row_id, position_no=original.get("position_no") or index,
                   name=str(original.get("name") or original.get("name_in_tz") or f"Позиция {index}"))
        rows.append(row)
    groups = {}
    for row in rows:
        category = str(row.get("category") or "").strip()
        if not category:
            # A selection snapshot represents the source document; infering a
            # category from product-name keywords silently rewrites that source.
            category = "Позиции спецификации"
        row["category"] = category
        groups.setdefault(category, []).append(row["id"])
    maximum = len(rows) if mode in {"price_monitoring", "exact_product"} else MAX_SELECTED_POSITIONS
    return json.dumps({"revision": uuid.uuid4().hex, "mode": mode, "max_positions": maximum,
                       "pricing_mode": "per_found_position" if mode == "price_monitoring" else ("per_position" if mode == "exact_product" else "fixed_task"),
                       "price_kopeks": max(0, int(price_kopeks)), "items": rows,
                       "groups": [{"id": f"group-{index}", "name": name, "item_ids": ids} for index, (name, ids) in enumerate(groups.items(), 1)],
                       "selected_ids": [], "confirmed": False}, ensure_ascii=False)


def validate_selected_ids(selection: dict, revision: str, item_ids: list[str]) -> list[str]:
    if not revision or revision != selection.get("revision"):
        raise ValueError("Список позиций обновился. Откройте актуальный список и повторите выбор.")
    if not isinstance(item_ids, list) or not item_ids or any(not isinstance(i, str) for i in item_ids):
        raise ValueError("Выберите хотя бы одну позицию.")
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("Позиции в выборе не должны повторяться.")
    maximum = int(selection.get("max_positions") or 0) if selection.get("mode") in {"price_monitoring", "exact_product"} else MAX_SELECTED_POSITIONS
    if len(item_ids) > maximum:
        raise ValueError(f"За один запуск можно выбрать до {maximum} позиций.")
    allowed = [str(item["id"]) for item in selection.get("items", []) if isinstance(item, dict) and item.get("id")]
    if not set(item_ids).issubset(allowed):
        raise ValueError("В выборе есть позиции, которые не относятся к этому списку.")
    return [item_id for item_id in allowed if item_id in set(item_ids)]


def selected_positions(job: Job) -> list[dict]:
    selection = read_selection(job)
    ids = set(selection.get("selected_ids") or [])
    return [row for row in selection.get("items", []) if row.get("id") in ids]


def confirm_position_selection(db: Session, job: Job, revision: str, item_ids: list[str]) -> bool:
    """Compare-and-set the snapshot and state together; repeated same choice is harmless."""
    selection = read_selection(job)
    if job.mode not in {"exact_product", "price_monitoring"} or selection.get("mode", "exact_product") != job.mode:
        raise ValueError("Выбор позиций недоступен для этой задачи.")
    chosen = validate_selected_ids(selection, revision, item_ids)
    if selection.get("confirmed"):
        if chosen == selection.get("selected_ids") and job.status in {"pending", "running", "completed"}:
            return False
        raise ValueError("Выбор этой задачи уже подтверждён. Для другого состава создайте новый подбор.")
    if job.mode in {"price_monitoring", "exact_product"} and job.client_id and not getattr(job, "is_admin_rerun", False):
        if job.mode == "price_monitoring":
            client = db.get(Client, job.client_id)
            if client is not None:
                db.refresh(client, attribute_names=["money_balance_kopeks", "money_reserved_kopeks"])
                available = int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0)
                budget = len(chosen) * int(selection.get("price_kopeks") or 0)
                if available < budget:
                    raise ValueError(f"Недостаточно средств для выбранных позиций: нужно {budget / 100:.2f} ₽, доступно {available / 100:.2f} ₽. Уменьшите выбор или пополните баланс.")
        elif job.mode == "exact_product":
            from .billing import adjust_exact_product_reservation_for_selection
            unit_price = int(selection.get("price_kopeks") or 0)
            try:
                adjust_exact_product_reservation_for_selection(db, job, chosen_count=len(chosen), price_per_item_kopeks=unit_price)
            except Exception as e:
                raise ValueError(str(e)) from e
    expected_status = AWAITING_EXACT_SELECTION if job.mode == "exact_product" else AWAITING_POSITION_SELECTION
    if job.status != expected_status:
        raise ValueError("Эта задача сейчас не ожидает выбора товаров.")
    old_value = job.position_selection_json
    selection.update(selected_ids=chosen, confirmed=True)
    updated = db.query(Job).filter(Job.id == job.id, Job.status == expected_status,
                                   Job.position_selection_json == old_value).update(
        {Job.status: "pending", Job.position_selection_json: json.dumps(selection, ensure_ascii=False),
         Job.message: f"Подбор выбранных позиций: {len(chosen)}", Job.updated_at: now_utc()},
        synchronize_session=False)
    if updated != 1:
        db.rollback()
        raise ValueError("Состояние задачи изменилось. Обновите список задач.")
    db.commit()
    db.refresh(job)
    return True



def confirm_exact_product_selection(db: Session, job: Job, revision: str, item_ids: list[str]) -> bool:
    if job.mode != "exact_product":
        raise ValueError("Эта задача не относится к подбору товаров.")
    return confirm_position_selection(db, job, revision, item_ids)


def toggle_exact_draft_position(db: Session, job: Job, index: int) -> None:
    """Telegram callbacks resolve an index into this immutable snapshot, never a new parse."""
    selection = read_selection(job)
    items = selection.get("items") or []
    if job.mode not in {"exact_product", "price_monitoring"} or job.status not in SELECTION_STATUSES or selection.get("confirmed"):
        raise ValueError("Список уже подтверждён или задача больше не ожидает выбора.")
    if index < 0 or index >= len(items):
        raise ValueError("Позиция не найдена.")
    chosen = set(selection.get("selected_ids") or [])
    item_id = items[index]["id"]
    if item_id in chosen:
        chosen.remove(item_id)
    else:
        maximum = int(selection.get("max_positions") or MAX_SELECTED_POSITIONS)
        if len(chosen) >= maximum:
            raise ValueError(f"Можно выбрать до {maximum} позиций за один запуск.")
        chosen.add(item_id)
    old = job.position_selection_json
    selection["selected_ids"] = [row["id"] for row in items if row["id"] in chosen]
    updated = db.query(Job).filter(Job.id == job.id, Job.status == job.status,
                                   Job.position_selection_json == old).update(
        {Job.position_selection_json: json.dumps(selection, ensure_ascii=False)}, synchronize_session=False)
    if not updated:
        db.rollback()
        raise ValueError("Выбор обновился. Откройте список заново.")
    db.commit()
    db.refresh(job)


@contextmanager
def processing_retry_lock(parent_job_id: str):
    """Serialize creation of child retries across API processes, outside billing locks."""
    lock_dir = Path(config.storage_dir) / "locks" / "job-retries"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_name = uuid.uuid5(uuid.NAMESPACE_OID, str(parent_job_id)).hex
    with (lock_dir / f"{lock_name}.lock").open("a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
