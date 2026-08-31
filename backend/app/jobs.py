from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import socket
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, exists, func, or_, select, true
from sqlalchemy.orm import Session, aliased

from . import document_parser
from .ai import get_model_selection
from .billing import (
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    KIND_SUPPLIER_SEARCH_EXTRA,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    STATUS_CUSTOMER_DECLINED,
    STATUS_DELIVERY_EXPIRED,
    charge_job_reservation,
    release_job_kind_reservation,
    release_job_reservation,
    expire_stale_confirmations,
)
from .config import config
from .db import SessionLocal
from .models import BillingTransaction, Job, JobFile, JobSource, SupplierResult, now_utc
from .procurement_sources import (
    SOURCE_KIND_PROCUREMENT_URL,
    SOURCE_KIND_TENDERPLAN_NOTICE,
    classify_source_url,
    fetch_source_context_sync,
    source_label,
)
from .models import parse_json_dict
from .exact_product import (
    analyze_exact_product,
    write_exact_product_docx,
    write_exact_product_xlsx,
    ExactProductReport,
)
from .procurement_report import generate_procurement_report
from .quote_request import build_quote_request_markdown, build_quote_request_markdown_with_ai
from .repository import get_or_create_settings
from .report_builder import write_evidence, write_procurement_docx, write_quote_request_docx, write_supplier_xlsx, zip_paths
from .result_offers import (
    CONFIRMATION_KIND_PARTIAL_COUNT,
    CONFIRMATION_KIND_REGISTRY_FALLBACK,
    active_result_offer_output_items,
    expire_result_offers,
    publish_job_result_offer,
)
from .supplier_search import (
    discover_suppliers,
    extract_supplier_search_context,
    minprom_registry_preflight_error,
    supplier_search_job_context,
)
from .tenderplan import TenderplanDownloadedFile, fetch_tenderplan_source_sync

_RUNNING: set[str] = set()
_CANCELLED: set[str] = set()
TERMINAL_JOB_STATUSES = {
    "completed",
    "partial",
    "needs_review",
    "failed",
    "cancelled",
    "resolved",
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CUSTOMER_DECLINED,
    STATUS_CONFIRMATION_EXPIRED,
    STATUS_DELIVERY_EXPIRED,
}
STALE_RUNNING_AFTER = timedelta(minutes=8)
WORKER_POLL_INTERVAL_SECONDS = 2.0
JOB_CANCELLATION_POLL_INTERVAL_SECONDS = 0.5
MODE_SUPPLIER_SEARCH = "supplier_search"
MODE_PROCUREMENT_REPORT = "procurement_report"
MODE_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"
MODE_EXACT_PRODUCT = "exact_product"
KIND_EXACT_PRODUCT = "exact_product"
VALID_JOB_MODES = {
    MODE_SUPPLIER_SEARCH,
    MODE_PROCUREMENT_REPORT,
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_EXACT_PRODUCT,
}
SUPPLIER_POLICY_NORMAL = "normal"
SUPPLIER_POLICY_MINPROM_ONLY = "minprom_registry_only"
SUPPLIER_POLICY_MINPROM_PRIORITY = "minprom_registry_priority"
VALID_SUPPLIER_SEARCH_POLICIES = {
    SUPPLIER_POLICY_NORMAL,
    SUPPLIER_POLICY_MINPROM_ONLY,
    SUPPLIER_POLICY_MINPROM_PRIORITY,
}
SUPPLIER_RUN_INITIAL = "initial"
SUPPLIER_RUN_ADDITIONAL = "additional"
RESULT_STEM_MAX_BYTES = 150
RESULT_STEM_MAX_CHARS = 56
SUPPLIER_EXCLUSIONS_FILENAME = "excluded_suppliers.json"
DOBOR_CONTEXT_FILENAME = "dobor_context.json"
logger = logging.getLogger(__name__)


def _supplier_search_billing_kind(job: Job) -> str:
    if (
        str(job.mode or "") == MODE_SUPPLIER_SEARCH
        and str(job.supplier_search_run_type or "") == SUPPLIER_RUN_ADDITIONAL
    ):
        return KIND_SUPPLIER_SEARCH_EXTRA
    return KIND_SUPPLIER_SEARCH


class JobCancelledError(RuntimeError):
    """Raised when a running job was cancelled by a user or admin."""


def job_dir(job_id: str) -> Path:
    return config.storage_path / "jobs" / job_id


def create_job(
    db: Session,
    *,
    client_id: str | None,
    created_by_telegram_id: str = "",
    mode: str,
    title: str,
    target_suppliers: int,
    files: list[tuple[str, bytes]],
    sources: list[dict] | None = None,
    supplier_search_policy: str = SUPPLIER_POLICY_NORMAL,
    supplier_search_run_type: str = SUPPLIER_RUN_INITIAL,
    initial_status: str = "pending",
) -> Job:
    normalized_sources = _normalized_job_sources(sources or [])
    if mode == MODE_SUPPLIER_SEARCH and normalized_sources:
        raise ValueError(
            "Режим поиска поставщиков принимает только файл или текст ТЗ. "
            "Номер извещения или ссылку закупки отправьте в режим анализа закупки или анализа + поставщики."
        )
    normalized_policy = normalize_supplier_search_policy(supplier_search_policy)
    if mode in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS}:
        registry_error = minprom_registry_preflight_error(normalized_policy)
        if registry_error:
            raise ValueError(registry_error)
    normalized_run_type = SUPPLIER_RUN_ADDITIONAL if str(supplier_search_run_type or "") == SUPPLIER_RUN_ADDITIONAL else SUPPLIER_RUN_INITIAL
    work_dir = job_dir("pending")
    work_dir.mkdir(parents=True, exist_ok=True)
    job = Job(
        client_id=client_id,
        created_by_telegram_id=str(created_by_telegram_id or ""),
        mode=mode,
        supplier_search_policy=normalized_policy,
        supplier_search_run_type=normalized_run_type,
        title=title,
        target_suppliers=target_suppliers,
        status="draft" if initial_status == "draft" else "pending",
        message="Комплект подготавливается" if initial_status == "draft" else "Задача создана",
        file_count=len(files),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    actual_dir = job_dir(job.id)
    actual_dir.mkdir(parents=True, exist_ok=True)
    used_stored_names: set[str] = set()
    for filename, content in files:
        safe_name = document_parser.sanitize_filename(filename)
        candidate = safe_name
        suffix_index = 1
        while candidate.casefold() in used_stored_names:
            path = Path(safe_name)
            candidate = f"{path.stem}_{suffix_index}{path.suffix}"
            suffix_index += 1
        used_stored_names.add(candidate.casefold())
        stored_path = actual_dir / "input" / candidate
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(content)
        db.add(JobFile(job_id=job.id, original_filename=filename, stored_path=str(stored_path)))
    for source in normalized_sources:
        db.add(
            JobSource(
                job_id=job.id,
                kind=source["kind"],
                label=source["label"],
                value=source["value"],
            )
        )
    db.commit()
    db.refresh(job)
    return job


def normalize_supplier_search_policy(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_SUPPLIER_SEARCH_POLICIES:
        return normalized
    return SUPPLIER_POLICY_NORMAL


def _is_registry_only_supplier_search(job: Job) -> bool:
    return normalize_supplier_search_policy(getattr(job, "supplier_search_policy", "")) == SUPPLIER_POLICY_MINPROM_ONLY


def _normalized_job_sources(sources: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()
    for source in sources:
        value = str(source.get("value") or source.get("url") or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        kind = str(source.get("kind") or "").strip() or classify_source_url(value)
        label = str(source.get("label") or "").strip() or source_label(value)
        normalized.append({"kind": kind or SOURCE_KIND_PROCUREMENT_URL, "label": label, "value": value})
    return normalized


def enqueue_job(job_id: str) -> None:
    # Jobs are durable queue items: API and bot only persist pending jobs.
    # app.worker is responsible for claiming and processing them.
    return None


def write_supplier_exclusions(
    job: Job,
    *,
    previous_job_id: str,
    suppliers: list[dict],
    prior_verified_count: int = 0,
) -> Path:
    input_dir = job_dir(job.id) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    path = input_dir / SUPPLIER_EXCLUSIONS_FILENAME
    payload = {
        "previous_job_id": previous_job_id,
        "suppliers": [item for item in suppliers if isinstance(item, dict)],
        "prior_verified_count": int(prior_verified_count or 0),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_supplier_exclusions_payload(job: Job) -> dict:
    path = job_dir(job.id) / "input" / SUPPLIER_EXCLUSIONS_FILENAME
    if not path.exists():
        return {}
    return parse_json_dict(path.read_text(encoding="utf-8"))


def read_supplier_exclusions(job: Job) -> list[dict]:
    payload = read_supplier_exclusions_payload(job)
    suppliers = payload.get("suppliers")
    if not isinstance(suppliers, list):
        return []
    return [item for item in suppliers if isinstance(item, dict)]


def _load_supplier_exclusions(job: Job) -> list[dict]:
    return read_supplier_exclusions(job)


def write_dobor_context(
    job: Job,
    *,
    previous_job_id: str,
    unreviewed_candidates: list[dict] | None = None,
    cached_procurement_profile: dict | None = None,
    executed_queries: list[str] | None = None,
    additional_prompt: str = "",
    wave_index: int = 1,
) -> Path:
    input_dir = job_dir(job.id) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    path = input_dir / DOBOR_CONTEXT_FILENAME
    payload = {
        "previous_job_id": previous_job_id,
        "unreviewed_candidates": [item for item in (unreviewed_candidates or []) if isinstance(item, dict)],
        "procurement_profile": cached_procurement_profile or {},
        "executed_queries": [str(q).strip() for q in (executed_queries or []) if str(q).strip()],
        "additional_prompt": str(additional_prompt or "").strip(),
        "wave_index": wave_index,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_dobor_context(job: Job) -> dict:
    path = job_dir(job.id) / "input" / DOBOR_CONTEXT_FILENAME
    if not path.exists():
        return {}
    return parse_json_dict(path.read_text(encoding="utf-8"))


def should_requeue_stale_job(status: str, updated_at: datetime | None, now: datetime, stale_after: timedelta) -> bool:
    if status != "running" or updated_at is None:
        return False
    if updated_at.tzinfo is None and now.tzinfo is not None:
        updated_at = updated_at.replace(tzinfo=now.tzinfo)
    return updated_at < now - stale_after


def recover_interrupted_jobs(db: Session, *, stale_after: timedelta = STALE_RUNNING_AFTER, limit: int = 20) -> list[str]:
    now = now_utc()
    jobs = (
        db.query(Job)
        .filter(Job.status.in_(["pending", "running"]))
        .order_by(Job.created_at.asc())
        .limit(max(1, limit * 4))
        .all()
    )
    job_ids: list[str] = []
    changed = False
    for job in jobs:
        if job.status == "pending":
            job_ids.append(job.id)
        elif should_requeue_stale_job(job.status, job.updated_at, now, stale_after):
            job.status = "pending"
            job.progress = 0
            job.message = "Задача восстановлена после прерывания"
            job.error = ""
            job.updated_at = now
            job_ids.append(job.id)
            changed = True
        if len(job_ids) >= limit:
            break
    if changed:
        db.commit()
    return job_ids


def claim_next_job(
    db: Session,
    *,
    worker_id: str,
    stale_after: timedelta = STALE_RUNNING_AFTER,
    max_running_jobs_per_client: int | None = None,
) -> str | None:
    now = now_utc()
    stale_cutoff = now - stale_after
    if max_running_jobs_per_client is None:
        max_running_jobs_per_client = getattr(config, "max_running_jobs_per_client", 2)
    max_per_client = _normalized_max_running_jobs_per_client(max_running_jobs_per_client)
    eligible_status_filter = or_(
        Job.status == "pending",
        and_(Job.status == "running", Job.updated_at < stale_cutoff),
    )
    fair_client_filter = _client_under_concurrency_limit_filter(stale_cutoff, max_per_client=max_per_client)
    jobs = (
        db.query(Job)
        .filter(eligible_status_filter)
        .filter(fair_client_filter)
        .order_by(Job.created_at.asc())
        .limit(100)
        .all()
    )
    for job in jobs:
        if job.status == "pending" or should_requeue_stale_job(job.status, job.updated_at, now, stale_after):
            claim_query = db.query(Job).filter(Job.id == job.id).filter(
                eligible_status_filter,
                fair_client_filter,
            )
            rows = claim_query.update(
                {
                    Job.status: "running",
                    Job.progress: 0,
                    Job.message: "Задача взята в обработку",
                    Job.error: "",
                    Job.updated_at: now,
                },
                synchronize_session=False,
            )
            if rows:
                db.commit()
                return job.id
            db.rollback()
    return None


def _normalized_max_running_jobs_per_client(value: int | str | None) -> int:
    try:
        parsed = int(value or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, parsed)


def _active_client_job_exists(stale_cutoff: datetime):
    active_job = aliased(Job)
    return exists().where(
        and_(
            active_job.client_id == Job.client_id,
            active_job.id != Job.id,
            active_job.status == "running",
            or_(active_job.updated_at.is_(None), active_job.updated_at >= stale_cutoff),
        )
    )


def _client_running_jobs_count_subquery(stale_cutoff: datetime):
    active_job = aliased(Job)
    return (
        select(func.count(active_job.id))
        .where(
            and_(
                active_job.client_id == Job.client_id,
                active_job.id != Job.id,
                active_job.status == "running",
                or_(active_job.updated_at.is_(None), active_job.updated_at >= stale_cutoff),
            )
        )
        .scalar_subquery()
    )


def _client_under_concurrency_limit_filter(stale_cutoff: datetime, max_per_client: int = 2):
    if max_per_client <= 0:
        return true()
    if max_per_client == 1:
        return or_(Job.client_id.is_(None), ~_active_client_job_exists(stale_cutoff))
    running_count = _client_running_jobs_count_subquery(stale_cutoff)
    return or_(Job.client_id.is_(None), running_count < max_per_client)


def _client_has_no_active_running_job_filter(stale_cutoff: datetime):
    return _client_under_concurrency_limit_filter(stale_cutoff, max_per_client=1)


async def wait_for_job_completion(job_id: str, *, timeout_seconds: int = 3600, poll_interval: float = 3.0) -> Job | None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return None
            if job.status in TERMINAL_JOB_STATUSES:
                db.expunge(job)
                return job
        finally:
            db.close()
        if asyncio.get_running_loop().time() >= deadline:
            return None
        await asyncio.sleep(poll_interval)


def _normalized_worker_concurrency(value: int | str | None) -> int:
    try:
        parsed = int(value or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, parsed)


def _claim_job_for_worker(worker_id: str) -> str | None:
    db = SessionLocal()
    try:
        expire_result_offers(db)
        expire_stale_confirmations(db)
        return claim_next_job(db, worker_id=worker_id)
    finally:
        db.close()


def _fill_worker_slots(running_tasks: set[asyncio.Task[None]], *, worker_id: str, concurrency: int) -> int:
    claimed = 0
    while len(running_tasks) < concurrency:
        job_id = _claim_job_for_worker(worker_id)
        if not job_id:
            break
        running_tasks.add(asyncio.create_task(process_job(job_id)))
        claimed += 1
    return claimed


def _consume_finished_worker_tasks(tasks: set[asyncio.Task[None]]) -> None:
    for task in tasks:
        try:
            task.result()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker task failed")


async def worker_loop(*, poll_interval: float = WORKER_POLL_INTERVAL_SECONDS, concurrency: int | None = None) -> None:
    init_worker_database()
    db_startup = SessionLocal()
    try:
        stuck_jobs = db_startup.query(Job).filter(Job.status == "running").all()
        for j in stuck_jobs:
            j.status = "pending"
            j.progress = 5
            j.message = "Авто-возобновление после перезапуска сервера"
            j.error = ""
            j.updated_at = now_utc()
        if stuck_jobs:
            db_startup.commit()
    except Exception:
        pass
    finally:
        db_startup.close()
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    worker_concurrency = _normalized_worker_concurrency(concurrency if concurrency is not None else config.worker_concurrency)
    running_tasks: set[asyncio.Task[None]] = set()
    while True:
        finished = {task for task in running_tasks if task.done()}
        if finished:
            running_tasks.difference_update(finished)
            _consume_finished_worker_tasks(finished)

        claimed = _fill_worker_slots(running_tasks, worker_id=worker_id, concurrency=worker_concurrency)
        if running_tasks:
            timeout = 0 if claimed else poll_interval
            done, _pending = await asyncio.wait(running_tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            if done:
                running_tasks.difference_update(done)
                _consume_finished_worker_tasks(done)
            continue
        await asyncio.sleep(poll_interval)


def init_worker_database() -> None:
    from .db import init_db

    init_db()


async def process_job(job_id: str) -> None:
    if job_id in _RUNNING:
        return
    _RUNNING.add(job_id)
    try:
        await asyncio.to_thread(_process_job_sync, job_id)
    finally:
        _RUNNING.discard(job_id)
        _CANCELLED.discard(job_id)


def cancel_running_job(job_id: str) -> None:
    """Mark a job as cancelled so the worker aborts processing."""
    _CANCELLED.add(job_id)
    _RUNNING.discard(job_id)


def _is_job_cancelled_in_database(job_id: str) -> bool:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        return bool(job and job.status == "cancelled")
    finally:
        db.close()


async def _wait_for_database_cancellation(job_id: str) -> None:
    while True:
        await asyncio.sleep(JOB_CANCELLATION_POLL_INTERVAL_SECONDS)
        if _is_job_cancelled_in_database(job_id):
            return


async def _run_supplier_discovery_with_cancellation(job_id: str, discovery) -> tuple[list[dict], dict]:
    """Stop an in-flight supplier search promptly when another service cancels its job."""
    discovery_task = asyncio.create_task(discovery)
    cancellation_task = asyncio.create_task(_wait_for_database_cancellation(job_id))
    try:
        done, _ = await asyncio.wait(
            {discovery_task, cancellation_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if cancellation_task in done:
            await cancellation_task
            if not discovery_task.done():
                discovery_task.cancel()
            try:
                await discovery_task
            except asyncio.CancelledError:
                pass
            raise JobCancelledError("Задача отменена")
        return await discovery_task
    finally:
        if not cancellation_task.done():
            cancellation_task.cancel()
        if not discovery_task.done():
            discovery_task.cancel()
        await asyncio.gather(discovery_task, cancellation_task, return_exceptions=True)


def _check_cancelled(job_id: str, db: Session | None = None, job: Job | None = None) -> None:
    """Raise if the job has been cancelled — call from worker threads."""
    if job_id in _CANCELLED:
        _CANCELLED.discard(job_id)
        raise JobCancelledError("Задача отменена")
    if db is not None:
        current = job or db.get(Job, job_id)
        if current is not None:
            try:
                db.refresh(current, attribute_names=["status"])
            except TypeError:
                db.refresh(current)
            if current.status == "cancelled":
                raise JobCancelledError("Задача отменена")


def _set_job(db: Session, job: Job, *, status: str | None = None, progress: int | None = None, message: str | None = None, error: str | None = None) -> None:
    _check_cancelled(str(job.id), db=db, job=job)
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = max(0, min(100, progress))
    if message is not None:
        job.message = message
    if error is not None:
        job.error = error
    job.updated_at = now_utc()
    db.commit()
    try:
        from .event_bus import job_event_bus
        job_event_bus.publish({
            "type": "job_update",
            "job_id": str(job.id),
            "status": job.status,
            "progress": job.progress,
            "message": job.message or "",
            "verified_count": getattr(job, "verified_count", 0),
            "error": job.error or ""
        })
    except Exception:
        pass


def _process_job_sync(job_id: str) -> None:
    db = SessionLocal()
    stage = "load_job"
    try:
        _check_cancelled(job_id)
        job = db.get(Job, job_id)
        if not job:
            return
        _check_cancelled(job_id, db=db, job=job)
        settings = get_or_create_settings(db)
        stage = "extract_documents"
        _set_job(db, job, status="running", progress=3, message="Начинаю обработку документов")
        parsed: list[tuple[str, str]] = []
        source_blocks: list[str] = []
        source_count = len(job.sources)
        for index, source in enumerate(job.sources, start=1):
            _check_cancelled(job_id)
            stage = "extract_sources"
            label = "номер извещения" if source.kind == SOURCE_KIND_TENDERPLAN_NOTICE else "ссылку закупки"
            _set_job(db, job, status="running", progress=3 + int(5 * (index - 1) / max(1, source_count)), message=f"Читаю {label}: {index}/{source_count}")
            if source.kind == SOURCE_KIND_TENDERPLAN_NOTICE:
                result = fetch_tenderplan_source_sync(source.value)
                source.parse_status = result.status
                source.extracted_chars = len(result.context)
                source.error = result.error
                if result.context:
                    _update_job_title_from_source_context(job, result.context)
                    context_path = _persist_source_context(job, index, source.kind, result.context)
                    source.context_path = str(context_path)
                    source_blocks.append(result.context)
                if result.downloaded_files:
                    _store_tenderplan_downloaded_files(db, job, result.downloaded_files)
                    db.expire(job, ["files"])
            else:
                result = fetch_source_context_sync(source.kind, source.value)
                source.parse_status = result.status
                source.extracted_chars = result.extracted_chars
                source.error = result.error
                if result.context:
                    _update_job_title_from_source_context(job, result.context)
                    context_path = _persist_source_context(job, index, source.kind, result.context)
                    source.context_path = str(context_path)
                    source_blocks.append(result.context)
                if result.downloaded_files:
                    _store_tenderplan_downloaded_files(db, job, result.downloaded_files)
                    db.expire(job, ["files"])
            db.commit()

        document_options = parse_json_dict(settings.document_settings_json)
        total_files = max(1, len(job.files))
        for index, file in enumerate(job.files, start=1):
            _check_cancelled(job_id)
            _set_job(db, job, status="running", progress=5 + int(10 * (index - 1) / total_files), message=f"Читаю документы: файл {index}/{total_files}")
            text, status = document_parser.extract_text(file.stored_path, document_options)
            file.parse_status = status
            file.extracted_chars = len(text)
            file.error = ""
            if not text.strip() and status != "ok":
                file.error = status
            parsed.append((file.original_filename, text))
        db.commit()

        file_context = document_parser.combined_document_context(parsed)
        context = "\n\n".join([*source_blocks, file_context]).strip()
        if len(context.strip()) < 50:
            release_job_reservation(db, job, note="Резерв возвращён: документы или ссылки не прочитались")
            _set_job(
                db,
                job,
                status="failed",
                progress=100,
                message="Текст закупки не извлечён",
                error="Документы или ссылки не прочитались.",
            )
            job.completed_at = now_utc()
            db.commit()
            return
        _set_job(db, job, status="running", progress=18, message="Текст ТЗ извлечён, запускаю анализ")

        if job.mode == MODE_PROCUREMENT_REPORT:
            stage = "procurement_report"
            _process_procurement_report(db, job, settings, context)
        elif job.mode == MODE_ANALYSIS_AND_SUPPLIERS:
            stage = "analysis_and_suppliers"
            _process_analysis_and_suppliers(db, job, settings, context)
        elif job.mode == MODE_EXACT_PRODUCT:
            stage = "exact_product"
            _process_exact_product(db, job, settings, context)
        else:
            stage = "supplier_search"
            _process_supplier_search(db, job, settings, context)
    except JobCancelledError as exc:
        job = db.get(Job, job_id)
        if job:
            release_job_reservation(db, job, note="Резерв возвращён: задача отменена")
            job.status = "cancelled"
            job.progress = 100
            job.message = str(exc)
            job.error = ""
            job.completed_at = now_utc()
            job.updated_at = now_utc()
            db.commit()
    except Exception as exc:
        job = db.get(Job, job_id)
        if job:
            release_job_reservation(db, job, note="Резерв возвращён: задача завершилась ошибкой")
            _persist_failure_evidence(db, job, exc, stage=stage)
            _set_job(db, job, status="failed", progress=100, message="Ошибка обработки", error=str(exc))
            job.completed_at = now_utc()
            db.commit()
    finally:
        db.close()


def build_failure_evidence(job: Job, exc: Exception, *, stage: str) -> dict:
    mode = str(getattr(job, "mode", "") or "")
    supplier_search = mode in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS}
    return {
        "mode": mode,
        "stage": stage,
        "status": "failed",
        "ai_required": supplier_search,
        "report_generated": False,
        "xlsx_generated": False,
        "error": {
            "type": type(exc).__name__,
            "message": str(exc)[:2000],
        },
        "sources": _job_sources_evidence(job),
        "files": _job_files_evidence(job),
        "contract": (
            "Supplier report was not generated because AI-required supplier search failed before verified results were produced."
            if supplier_search
            else "Report generation failed before an output artifact was produced."
        ),
    }


def _job_sources_evidence(job: Job) -> list[dict]:
    sources = getattr(job, "sources", []) or []
    result: list[dict] = []
    for source in sources:
        result.append(
            {
                "kind": getattr(source, "kind", ""),
                "label": getattr(source, "label", ""),
                "value": getattr(source, "value", ""),
                "parse_status": getattr(source, "parse_status", ""),
                "extracted_chars": getattr(source, "extracted_chars", 0),
                "error": getattr(source, "error", ""),
            }
        )
    return result


def _job_files_evidence(job: Job) -> list[dict]:
    files = getattr(job, "files", []) or []
    result: list[dict] = []
    for file in files:
        result.append(
            {
                "filename": getattr(file, "original_filename", ""),
                "parse_status": getattr(file, "parse_status", ""),
                "extracted_chars": getattr(file, "extracted_chars", 0),
                "error": getattr(file, "error", ""),
            }
        )
    return result


GENERIC_SOURCE_TITLE_RE = re.compile(
    r"^(?:закупка\s+\d{11,19}|номер извещения|документация|source-only|"
    r"(?:tenderplan|тендер\s*план|тендерплан)\s*(?:[-:]\s*)?(?:номер извещения)?)$",
    re.I,
)


def _is_generic_source_title(value: object) -> bool:
    text = _clean_label(value).lower()
    if not text or GENERIC_SOURCE_TITLE_RE.fullmatch(text):
        return True
    has_notice_phrase = "номер извещения" in text
    has_internal_brand = "tender" in text or "тендер" in text or "tande" in text
    return has_notice_phrase and has_internal_brand


def _extract_title_from_source_context(context: str) -> str:
    text = str(context or "")
    patterns = (
        r"(?m)^\s*-\s*Наименование\s*:\s*(.+)$",
        r"(?mi)^\s*(?:предмет|объект)\s+закупк[ии]\s*[:\-]\s*(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = _short_label(match.group(1), limit=120)
        if value and not _is_generic_source_title(value):
            return value
    return ""


def _update_job_title_from_source_context(job: Job, context: str) -> None:
    title = _extract_title_from_source_context(context)
    has_uploaded_files = bool(getattr(job, "files", []) or [])
    if title and (_is_generic_source_title(job.title) or not has_uploaded_files):
        job.title = title


def _persist_source_context(job: Job, index: int, kind: str, context: str) -> Path:
    source_dir = job_dir(job.id) / "input" / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    context_path = source_dir / f"{index:02d}_{kind}.txt"
    context_path.write_text(context, encoding="utf-8")
    return context_path


def _store_tenderplan_downloaded_files(db: Session, job: Job, files: list[TenderplanDownloadedFile]) -> None:
    input_dir = job_dir(job.id) / "input" / "tenderplan"
    input_dir.mkdir(parents=True, exist_ok=True)
    existing_names = {Path(str(item.stored_path)).name for item in getattr(job, "files", []) or []}
    for index, downloaded in enumerate(files, start=1):
        safe_name = document_parser.sanitize_filename(downloaded.filename)
        stored_name = f"{index:02d}_{safe_name}"
        while stored_name in existing_names:
            stored_name = f"{index:02d}_{len(existing_names) + 1}_{safe_name}"
        existing_names.add(stored_name)
        stored_path = input_dir / stored_name
        stored_path.write_bytes(downloaded.content)
        db.add(JobFile(job_id=job.id, original_filename=downloaded.filename, stored_path=str(stored_path)))
    job.file_count = int(job.file_count or 0) + len(files)


def _persist_failure_evidence(db: Session, job: Job, exc: Exception, *, stage: str) -> None:
    try:
        out_dir = job_dir(job.id) / "output"
        evidence_path = write_evidence(out_dir / "evidence.json", build_failure_evidence(job, exc, stage=stage))
        job.evidence_path = str(evidence_path)
        job.result_path = ""
        job.verified_count = 0
        db.commit()
    except Exception:
        db.rollback()


def _persist_supplier_rows(db: Session, job: Job, accepted: list[dict]) -> None:
    db.query(SupplierResult).filter(SupplierResult.job_id == job.id).delete()
    for row in accepted:
        db.add(
            SupplierResult(
                job_id=job.id,
                company_name=row.get("company_name", ""),
                region=row.get("region", ""),
                status=row.get("status", ""),
                product=row.get("product", ""),
                contact_person=row.get("contact_person", ""),
                phone=row.get("phone", ""),
                email=row.get("email", ""),
                site=row.get("site", ""),
                evidence_url=row.get("evidence_url", ""),
                contact_url=row.get("contact_url", ""),
                comments=row.get("comments", ""),
                evidence_status=row.get("evidence_status", "verified"),
                match_level=row.get("match_level", ""),
                source=row.get("source", ""),
                search_query=row.get("search_query", ""),
                quality_score=int(row.get("quality_score") or 0),
                quality_tier=row.get("quality_tier", ""),
                procurement_item_id=row.get("procurement_item_id", ""),
                procurement_item=row.get("procurement_item", ""),
                ai_confidence=int(row.get("ai_confidence") or 0),
                site_type=row.get("site_type", ""),
                product_fit=row.get("product_fit", ""),
                evidence_snippet=row.get("evidence_snippet", ""),
                contact_evidence_snippet=row.get("contact_evidence_snippet", ""),
                ai_rank_confidence=int(row.get("ai_rank_confidence") or 0),
                ai_rank_reason=row.get("ai_rank_reason", ""),
            )
        )
    db.commit()


def _source_title(job: Job) -> str:
    title = _clean_label(job.title)
    if title and not _is_generic_source_title(title):
        return title
    files = getattr(job, "files", []) or []
    if files:
        return _clean_label(Path(files[0].original_filename).stem)
    return "документация"


def _subject_from_supplier_evidence(evidence: dict) -> str:
    profile = evidence.get("procurement_profile") if isinstance(evidence, dict) else {}
    if not isinstance(profile, dict):
        return ""
    items = profile.get("items")
    if not isinstance(items, list):
        return _short_label(profile.get("summary") or "")
    names = [_clean_label(item.get("name") if isinstance(item, dict) else "") for item in items]
    names = [name for name in names if name]
    if not names:
        return _short_label(profile.get("summary") or "")
    if len(names) == 1:
        return _short_label(names[0])
    if len(names) == 2:
        return _short_label(f"{names[0]} и {names[1]}")
    return _short_label(f"{names[0]} и ещё {len(names) - 1} позиции")


def _subject_from_report_text(markdown: str) -> str:
    text = str(markdown or "")
    for pattern in (
        r"(?:предмет|объект)\s+закупк[ии]\s*[:\-]\s*(.+)",
        r"(?:наименование\s+товара|номенклатура)\s*[:\-]\s*(.+)",
    ):
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _short_label(match.group(1))
    return ""


def _analysis_report_title(job: Job, subject: str) -> str:
    source = _source_title(job)
    item = _short_label(subject)
    if item:
        return f"Анализ документации: {item}"
    return f"Анализ документации: {source}" if source else "Анализ документации"


def _set_customer_job_title_from_subject(job: Job, subject: str) -> None:
    item = _short_label(subject)
    if not item:
        return
    if job.mode == MODE_PROCUREMENT_REPORT:
        job.title = f"Анализ закупки: {item}"
    elif job.mode == MODE_ANALYSIS_AND_SUPPLIERS:
        job.title = f"Анализ + поиск: {item}"
    elif job.mode == MODE_SUPPLIER_SEARCH:
        job.title = f"ТЗ: {item}"


def _result_stem(job: Job, subject: str) -> str:
    source = _source_title(job)
    item = _short_label(subject)
    base = item or source
    base = _strip_generated_output_suffixes(base)
    base = re.sub(r"\b([Дд])\s+(\d{1,3})\s+(\d{1,2})(?=\s+(?:ГОСТ|ТУ|и|$))", r"\1 \2,\3", base)
    base = re.sub(r"\bГОСТ\s+(\d{3,5})\s+(\d{2,4})\b", r"ГОСТ \1-\2", base, flags=re.I)
    base = re.sub(r"\bи\s+ещ[её]\s+(\d+)\s+позици[ияй]+\b", r"и ещё \1 поз.", base, flags=re.I)
    base = re.sub(r"[()\[\]{}]+", " ", base)
    base = _sanitize_result_filename_component(base)
    base = _truncate_result_stem(base, RESULT_STEM_MAX_CHARS)
    return _truncate_filename_component(base, RESULT_STEM_MAX_BYTES, fallback="закупка")


def _result_filename(kind: str, stem: str, suffix: str) -> str:
    prefix = {
        "analysis": "Анализ",
        "quote_request": "Запрос КП",
        "suppliers": "Поставщики",
        "archive": "Результаты",
    }.get(kind, "Результат")
    safe_stem = _sanitize_result_filename_component(stem).rstrip(" ._-") or "закупка"
    return f"{prefix} - {safe_stem}{suffix}"


def _strip_generated_output_suffixes(value: str) -> str:
    cleaned = re.sub(r"[_]+", " ", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;\"'")
    suffixes = (
        r"запрос\s*кп",
        r"техническое\s*задание",
        r"анализ",
        r"поставщики",
        r"suppliers?",
        r"quote\s*request",
    )
    changed = True
    while changed and cleaned:
        changed = False
        for suffix in suffixes:
            next_value = re.sub(rf"(?:\s*[-–—]\s*|\s+){suffix}\s*$", "", cleaned, flags=re.I).strip(" .,:;\"'-–—")
            if next_value != cleaned:
                cleaned = next_value
                changed = True
    return cleaned


def _sanitize_result_filename_component(value: str) -> str:
    cleaned = re.sub(r"[_]+", " ", str(value or ""))
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._-")
    return cleaned


def _truncate_filename_component(value: str, max_bytes: int, *, fallback: str) -> str:
    value = str(value or "").strip()
    if len(value.encode("utf-8")) <= max_bytes:
        return value or fallback
    truncated = value.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").rstrip(" ._-")
    return truncated or fallback


def _truncate_result_stem(value: str, max_chars: int) -> str:
    value = str(value or "").strip()
    if len(value) <= max_chars:
        return value
    truncated = value[:max_chars].rsplit(" ", 1)[0].strip(" .,:;_-")
    return truncated or value[:max_chars].strip(" .,:;_-")


def _short_label(value: object, *, limit: int = 80) -> str:
    cleaned = _clean_label(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].strip(" .,:;-")


def _clean_label(value: object) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").replace("_", " ")).strip(" .,:;\"'")
    return cleaned.replace("/", "-").replace("\\", "-")


REGISTRY_FALLBACK_QUOTE_WARNING = (
    "Подтверждение соответствия найденных поставщиков реестру российской промышленной продукции не получено. "
    "Просим указать в коммерческом предложении номер актуальной реестровой записи либо прямо сообщить об её отсутствии."
)


def _registry_fallback_rows(evidence: object) -> list[dict]:
    if not isinstance(evidence, dict):
        return []
    alternative = evidence.get("non_registry_alternative")
    if not isinstance(alternative, dict) or not bool(alternative.get("available")):
        return []
    rows = alternative.get("verified_rows")
    if not isinstance(rows, list):
        return []
    return [dict(item) for item in rows if isinstance(item, dict)]


def _output_artifact(
    kind: str,
    label: str,
    path: Path,
    billing_kind: str,
    *,
    content_path: Path | None = None,
) -> dict:
    item = {
        "kind": kind,
        "label": label,
        "path": str(path),
        "billing_kind": billing_kind,
    }
    if content_path is not None:
        item["content_path"] = str(content_path)
    return item


def _output_manifest(files: list[dict], archive_path: Path, entitlements: list[str]) -> dict:
    return {
        "files": [dict(item) for item in files],
        "archive_path": str(archive_path),
        "entitlements": list(dict.fromkeys(entitlements)),
    }


def _build_registry_fallback_supplier_outputs(
    job: Job,
    *,
    context: str,
    evidence: dict,
    rows: list[dict],
    out_dir: Path,
    subject: str,
    stem: str,
    supplier_billing_kind: str,
    quote_billing_kind: str,
) -> tuple[Path, list[dict]]:
    quote_markdown = build_quote_request_markdown(
        context,
        subject=subject,
        procurement_profile=evidence.get("procurement_profile") if isinstance(evidence, dict) else {},
    )
    quote_markdown = f"{quote_markdown.rstrip()}\n\n## Важно: реестр Минпромторга\n\n{REGISTRY_FALLBACK_QUOTE_WARNING}\n"
    xlsx_path = write_supplier_xlsx(
        out_dir / _result_filename("suppliers", stem, ".xlsx"),
        rows,
        title=job.title,
        subject=subject,
        target=job.target_suppliers,
        policy=getattr(job, "supplier_search_policy", "") or "",
        quote_markdown=quote_markdown,
    )
    quote_md_path = out_dir / _result_filename("quote_request", stem, ".md")
    quote_md_path.write_text(quote_markdown, encoding="utf-8")
    quote_docx_path = write_quote_request_docx(
        out_dir / _result_filename("quote_request", stem, ".docx"),
        quote_markdown,
        title="Запрос КП",
    )
    files = [
        _output_artifact("suppliers", "Поставщики", xlsx_path, supplier_billing_kind),
        _output_artifact(
            "quote_request",
            "Запрос КП",
            quote_docx_path,
            quote_billing_kind,
            content_path=quote_md_path,
        ),
    ]
    return xlsx_path, files


def _populate_job_ai_metadata(job: Job, settings, mode: str) -> None:
    try:
        tier = "primary" if mode == MODE_PROCUREMENT_REPORT else "supplier_search"
        routing_key = "procurement_document_analysis" if mode == MODE_PROCUREMENT_REPORT else "supplier_query_generation"
        selection = get_model_selection(settings, tier=tier, routing_key=routing_key)
        job.ai_provider = selection.provider_id
        job.ai_model = selection.model
    except Exception:
        if mode == MODE_PROCUREMENT_REPORT:
            job.ai_provider = str(getattr(settings, "primary_provider", "") or "")
            job.ai_model = str(getattr(settings, "primary_model", "") or "")
        else:
            job.ai_provider = str(getattr(settings, "supplier_ai_provider", "") or getattr(settings, "light_provider", "") or "")
            job.ai_model = str(getattr(settings, "supplier_ai_model", "") or getattr(settings, "light_model", "") or "")


def _process_supplier_search(db: Session, job: Job, settings, context: str) -> None:
    _check_cancelled(job.id)
    _populate_job_ai_metadata(job, settings, job.mode)
    _set_job(db, job, progress=25, message="Запускаю ИИ-поиск поставщиков")

    async def progress_callback(progress: int, message: str) -> None:
        _check_cancelled(job.id)
        _set_job(db, job, status="running", progress=progress, message=message)

    excluded_suppliers = _load_supplier_exclusions(job)
    dobor_ctx = read_dobor_context(job)
    is_extend = str(getattr(job, "supplier_search_run_type", "") or "") == SUPPLIER_RUN_ADDITIONAL
    wave_idx = int(dobor_ctx.get("wave_index") or (2 if is_extend else 1))
    try:
        discovery_coro = discover_suppliers(
            settings,
            context,
            job.target_suppliers,
            progress_callback=progress_callback,
            excluded_suppliers=excluded_suppliers,
            supplier_search_policy=getattr(job, "supplier_search_policy", SUPPLIER_POLICY_NORMAL),
            preloaded_candidates=dobor_ctx.get("unreviewed_candidates"),
            cached_procurement_profile=dobor_ctx.get("procurement_profile"),
            executed_queries=dobor_ctx.get("executed_queries"),
            additional_prompt=dobor_ctx.get("additional_prompt", ""),
            is_extend=is_extend,
            wave_index=wave_idx,
        )
    except TypeError:
        discovery_coro = discover_suppliers(
            settings,
            context,
            job.target_suppliers,
            progress_callback=progress_callback,
            excluded_suppliers=excluded_suppliers,
            supplier_search_policy=getattr(job, "supplier_search_policy", SUPPLIER_POLICY_NORMAL),
        )
    with supplier_search_job_context(job.id):
        accepted, evidence = asyncio.run(
            _run_supplier_discovery_with_cancellation(
                job.id,
                discovery_coro,
            )
        )
    _check_cancelled(job.id)
    _set_job(db, job, status="running", progress=95, message="Сохраняю проверенных поставщиков")
    fallback_rows = _registry_fallback_rows(evidence) if not accepted else []
    persisted_rows = accepted or fallback_rows
    _persist_supplier_rows(db, job, persisted_rows)
    job.verified_count = len(persisted_rows)
    y_reqs, y_cost = extract_yandex_job_metrics(evidence, getattr(settings, "yandex_search_price_per_request", 0.04))
    job.yandex_requests_count = y_reqs
    job.yandex_cost_rub = y_cost
    _set_job(db, job, status="running", progress=97, message="Формирую Excel и проверочные данные")
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_supplier_evidence(evidence)
    source_title = _source_title(job)
    evidence["subject"] = subject
    evidence["source_title"] = source_title
    evidence["sources"] = _job_sources_evidence(job)
    _set_customer_job_title_from_subject(job, subject)
    browser_failure_note = _supplier_browser_failure_note(evidence)
    browser_failure_error = _supplier_browser_failure_error(evidence)
    supplier_billing_kind = _supplier_search_billing_kind(job)
    if not accepted and fallback_rows:
        stem = _result_stem(job, subject)
        _xlsx_path, output_files = _build_registry_fallback_supplier_outputs(
            job,
            context=context,
            evidence=evidence,
            rows=fallback_rows,
            out_dir=out_dir,
            subject=subject,
            stem=stem,
            supplier_billing_kind=supplier_billing_kind,
            quote_billing_kind=supplier_billing_kind,
        )
        full_archive_path = zip_paths(
            out_dir / _result_filename("archive_no_registry_confirmation", stem, ".zip"),
            [Path(item["path"]) for item in output_files],
        )
        evidence["output_files"] = output_files
        evidence["generated_outputs"] = [dict(item) for item in output_files]
        evidence["output_manifests"] = {
            "full": _output_manifest(output_files, full_archive_path, [supplier_billing_kind]),
        }
        evidence_path = write_evidence(out_dir / "evidence.json", evidence)
        job.evidence_path = str(evidence_path)
        publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
        _set_job(
            db,
            job,
            status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
            progress=100,
            message=(
                "По реестру подходящие поставщики не подтверждены. "
                f"Вне реестра найдено и проверено: {len(fallback_rows)}. Можно получить этот результат отдельно."
                + browser_failure_note
            ),
            error=browser_failure_error,
        )
        job.completed_at = now_utc()
        db.commit()
        return
    if not accepted:
        evidence["output_files"] = []
        evidence_path = write_evidence(out_dir / "evidence.json", evidence)
        job.evidence_path = str(evidence_path)
        job.result_path = ""
        release_job_reservation(db, job, note="Резерв возвращён: поставщики не найдены")
        is_registry_only = normalize_supplier_search_policy(getattr(job, "supplier_search_policy", "")) == SUPPLIER_POLICY_MINPROM_ONLY
        msg = (
            "В реестре Минпромторга подходящие производители не найдены"
            if is_registry_only
            else "Поставщики не найдены: подтверждённых официальных сайтов с контактами 0" + browser_failure_note
        )
        err = (
            ""
            if is_registry_only
            else browser_failure_error or "Поиск не сформировал XLSX, потому что нет ни одного подтверждённого поставщика."
        )
        _set_job(
            db,
            job,
            status="failed",
            progress=100,
            message=msg,
            error=err,
        )
        job.completed_at = now_utc()
        db.commit()
        return

    stem = _result_stem(job, subject)
    quote_markdown = asyncio.run(
        build_quote_request_markdown_with_ai(
            settings,
            context,
            subject=subject,
            procurement_profile=evidence.get("procurement_profile") if isinstance(evidence, dict) else {},
        )
    )
    xlsx_path = write_supplier_xlsx(
        out_dir / _result_filename("suppliers", stem, ".xlsx"),
        accepted,
        title=job.title,
        subject=subject,
        target=job.target_suppliers,
        policy=getattr(job, "supplier_search_policy", "") or "",
        quote_markdown=quote_markdown,
    )
    quote_md_path = out_dir / _result_filename("quote_request", stem, ".md")
    quote_md_path.write_text(quote_markdown, encoding="utf-8")
    quote_docx_path = write_quote_request_docx(
        out_dir / _result_filename("quote_request", stem, ".docx"),
        quote_markdown,
        title="Запрос КП",
    )
    evidence["output_files"] = [
        {
            "kind": "suppliers",
            "label": "Поставщики",
            "path": str(xlsx_path),
            "billing_kind": supplier_billing_kind,
        },
        {
            "kind": "quote_request",
            "label": "Запрос КП",
            "path": str(quote_docx_path),
            "content_path": str(quote_md_path),
            "billing_kind": supplier_billing_kind,
        },
    ]
    evidence_path = write_evidence(out_dir / "evidence.json", evidence)
    job.evidence_path = str(evidence_path)
    job.result_path = str(xlsx_path)
    if len(accepted) >= job.target_suppliers or len(accepted) >= 20 or _is_registry_only_supplier_search(job):
        status = "completed"
        message = _supplier_count_message("Готово", len(accepted), job.target_suppliers)
        error = ""
    elif settings.allow_partial_supplier_reports:
        status = STATUS_AWAITING_CUSTOMER_CONFIRMATION
        message = _supplier_count_message("Найдено меньше поставщиков", len(accepted), job.target_suppliers) + browser_failure_note
        error = browser_failure_error
    else:
        status = "needs_review"
        message = _supplier_count_message("Нужна ручная проверка", len(accepted), job.target_suppliers) + browser_failure_note
        error = browser_failure_error
    if status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_PARTIAL_COUNT)
    _set_job(db, job, status=status, progress=100, message=message, error=error)
    job.completed_at = now_utc()
    if status == "completed":
        charge_job_reservation(db, job, note="Результат готов")
    db.commit()


def _process_procurement_report(db: Session, job: Job, settings, context: str) -> None:
    _check_cancelled(job.id)
    _populate_job_ai_metadata(job, settings, job.mode)
    _set_job(db, job, progress=45, message="ИИ готовит анализ документации")
    result = asyncio.run(generate_procurement_report(settings, context))
    _check_cancelled(job.id)
    _set_job(db, job, progress=90, message="Формирую отчёт и проверочные данные")
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_report_text(result.report)
    report_title = _analysis_report_title(job, subject)
    source_title = _source_title(job)
    stem = _result_stem(job, subject)
    docx_path = write_procurement_docx(
        out_dir / _result_filename("analysis", stem, ".docx"),
        result.report,
        title=report_title,
    )
    quote_source = f"{result.report}\n\n{context}"
    quote_markdown = asyncio.run(
        build_quote_request_markdown_with_ai(
            settings,
            quote_source,
            subject=subject,
        )
    )
    quote_md_path = out_dir / _result_filename("quote_request", stem, ".md")
    quote_md_path.write_text(quote_markdown, encoding="utf-8")
    quote_docx_path = write_quote_request_docx(
        out_dir / _result_filename("quote_request", stem, ".docx"),
        quote_markdown,
        title="Запрос КП",
    )
    evidence_path = write_evidence(
        out_dir / "evidence.json",
        {
            "mode": job.mode,
            "subject": subject,
            "source_title": source_title,
            "sources": _job_sources_evidence(job),
            "files": _job_files_evidence(job),
            "output_files": [
                {"kind": "analysis", "path": str(docx_path)},
                {
                    "kind": "quote_request",
                    "label": "Запрос КП",
                    "path": str(quote_docx_path),
                    "content_path": str(quote_md_path),
                },
            ],
            "ai_used": result.ai_used,
            "ai_model": result.ai_model,
            "warning": result.warning,
            "verification": result.verification,
            "logistics_enabled": False,
            "ati_enabled": False,
        },
    )
    job.result_path = str(docx_path)
    job.evidence_path = str(evidence_path)
    _set_customer_job_title_from_subject(job, subject)
    if result.warning:
        _set_job(
            db,
            job,
            status="needs_review",
            progress=100,
            message="Анализ готов, нужна проверка ИИ-настроек",
            error=result.warning,
        )
    else:
        _set_job(db, job, status="completed", progress=100, message="Анализ документации готов")
        charge_job_reservation(db, job, note="Результат готов")
    job.completed_at = now_utc()
    db.commit()


def _process_exact_product(db: Session, job: Job, settings: SystemSettings, context: str) -> None:
    _check_cancelled(job.id)
    _populate_job_ai_metadata(job, settings, job.mode)
    _set_job(db, job, progress=15, message="Интеллектуальный анализ ТЗ и планирование поиска (ИИ)")
    subject = job.title or "Спецификация ТЗ"

    async def _progress_callback(progress: int, message: str) -> None:
        _check_cancelled(job.id, db=db, job=job)
        _set_job(db, job, progress=progress, message=message)

    report = asyncio.run(
        analyze_exact_product(
            settings,
            context,
            procurement_title=job.title,
            progress_callback=_progress_callback,
        )
    )
    _check_cancelled(job.id)
    _set_job(db, job, progress=85, message="Формирую официальный отчёт в формате Word (Форма 2 и аналоги)")
    out_dir = job_dir(job.id) / "output"
    stem = _result_stem(job, subject)
    docx_path = write_exact_product_docx(
        out_dir / _result_filename("exact_product", stem, ".docx"),
        report,
        title=job.title or "Подбор товара, характеристики и аналоги",
    )
    output_files = [
        _output_artifact("exact_product", "Подбор товара и аналоги", docx_path, KIND_EXACT_PRODUCT),
    ]
    evidence_payload = {
        "mode": job.mode,
        "subject": subject,
        "source_title": _source_title(job),
        "sources": _job_sources_evidence(job),
        "files": _job_files_evidence(job),
        "exact_product_report": report.to_dict(),
        "yandex_requests_count": report.yandex_requests_count,
        "yandex_cost_rub": report.yandex_cost_rub,
        "output_files": output_files,
        "ai_required": True,
        "ai_used": True,
    }
    evidence_path = write_evidence(out_dir / "evidence.json", evidence_payload)
    job.evidence_path = str(evidence_path)
    job.result_path = str(docx_path)
    job.verified_count = report.total_positions
    job.yandex_requests_count = report.yandex_requests_count
    job.yandex_cost_rub = report.yandex_cost_rub
    _set_customer_job_title_from_subject(job, subject)
    charge_job_reservation(db, job, note="Подбор товара и аналогов завершен")
    _set_job(db, job, status="completed", progress=100, message=f"Готово: выявлено {report.total_positions} поз. с аналогами")
    job.completed_at = now_utc()
    db.commit()


def _process_analysis_and_suppliers(db: Session, job: Job, settings, context: str) -> None:
    _check_cancelled(job.id)
    _populate_job_ai_metadata(job, settings, job.mode)
    _set_job(db, job, progress=25, message="ИИ готовит анализ документации")
    report = asyncio.run(generate_procurement_report(settings, context))
    _check_cancelled(job.id)
    _set_job(db, job, progress=43, message="Выделяю ТЗ для поиска поставщиков")
    supplier_context = asyncio.run(extract_supplier_search_context(settings, context))
    _check_cancelled(job.id)
    _set_job(db, job, progress=45, message="Ищу поставщиков по ТЗ из документации")

    async def progress_callback(progress: int, message: str) -> None:
        _check_cancelled(job.id)
        mapped_progress = 45 + int(max(0, min(100, progress)) * 0.5)
        _set_job(db, job, status="running", progress=mapped_progress, message=message)

    with supplier_search_job_context(job.id):
        accepted, supplier_evidence = asyncio.run(
            _run_supplier_discovery_with_cancellation(
                job.id,
                discover_suppliers(
                    settings,
                    supplier_context,
                    job.target_suppliers,
                    progress_callback=progress_callback,
                    supplier_search_policy=getattr(job, "supplier_search_policy", SUPPLIER_POLICY_NORMAL),
                ),
            )
    )
    _check_cancelled(job.id)
    _set_job(db, job, status="running", progress=96, message="Сохраняю анализ и поставщиков")
    fallback_rows = _registry_fallback_rows(supplier_evidence) if not accepted else []
    persisted_rows = accepted or fallback_rows
    _persist_supplier_rows(db, job, persisted_rows)
    job.verified_count = len(persisted_rows)
    y_reqs, y_cost = extract_yandex_job_metrics(supplier_evidence, getattr(settings, "yandex_search_price_per_request", 0.04))
    job.yandex_requests_count = y_reqs
    job.yandex_cost_rub = y_cost
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_supplier_evidence(supplier_evidence) or _subject_from_report_text(report.report)
    stem = _result_stem(job, subject)
    report_title = _analysis_report_title(job, subject)
    docx_path = write_procurement_docx(out_dir / _result_filename("analysis", stem, ".docx"), report.report, title=report_title)
    if fallback_rows:
        xlsx_path, fallback_supplier_files = _build_registry_fallback_supplier_outputs(
            job,
            context=f"{report.report}\n\n{supplier_context}",
            evidence=supplier_evidence,
            rows=fallback_rows,
            out_dir=out_dir,
            subject=subject,
            stem=stem,
            supplier_billing_kind=KIND_SUPPLIER_SEARCH,
            quote_billing_kind=KIND_PROCUREMENT_REPORT,
        )
        quote_item = next(item for item in fallback_supplier_files if item["kind"] == "quote_request")
        quote_md_path = Path(quote_item["content_path"])
        quote_docx_path = Path(quote_item["path"])
    else:
        quote_source = f"{report.report}\n\n{supplier_context}"
        quote_markdown = asyncio.run(
            build_quote_request_markdown_with_ai(
                settings,
                quote_source,
                subject=subject,
                procurement_profile=supplier_evidence.get("procurement_profile") if isinstance(supplier_evidence, dict) else {},
            )
        )
        quote_md_path = out_dir / _result_filename("quote_request", stem, ".md")
        quote_md_path.write_text(quote_markdown, encoding="utf-8")
        quote_docx_path = write_quote_request_docx(
            out_dir / _result_filename("quote_request", stem, ".docx"),
            quote_markdown,
            title="Запрос КП",
        )
        xlsx_path = None
    source_title = _source_title(job)
    evidence_payload = {
        "mode": job.mode,
        "subject": subject,
        "source_title": source_title,
        "sources": _job_sources_evidence(job),
        "files": _job_files_evidence(job),
        "report": {
            "ai_used": report.ai_used,
            "ai_model": report.ai_model,
            "warning": report.warning,
            "verification": report.verification,
            "logistics_enabled": False,
            "ati_enabled": False,
        },
        "supplier_search": supplier_evidence,
        "supplier_context": {
            "input_chars": len(context),
            "extracted_chars": len(supplier_context),
        },
        "ai_required": True,
        "ai_used": bool(report.ai_used and supplier_evidence.get("ai_used")),
    }
    if accepted:
        xlsx_path = write_supplier_xlsx(
            out_dir / _result_filename("suppliers", stem, ".xlsx"),
            accepted,
            title=job.title,
            subject=subject,
            target=job.target_suppliers,
            policy=getattr(job, "supplier_search_policy", "") or "",
            quote_markdown=quote_markdown,
        )
    output_files = [_output_artifact("analysis", "Анализ", docx_path, KIND_PROCUREMENT_REPORT)]
    if xlsx_path:
        output_files.append(_output_artifact("suppliers", "Поставщики", xlsx_path, KIND_SUPPLIER_SEARCH))
    output_files.append(
        _output_artifact(
            "quote_request",
            "Запрос КП",
            quote_docx_path,
            KIND_PROCUREMENT_REPORT,
            content_path=quote_md_path,
        )
    )
    evidence_payload["output_files"] = output_files
    zip_path = zip_paths(out_dir / _result_filename("archive", stem, ".zip"), [Path(item["path"]) for item in output_files])
    if fallback_rows:
        analysis_only_files = [item for item in output_files if item["kind"] in {"analysis", "quote_request"}]
        analysis_only_zip_path = zip_paths(
            out_dir / _result_filename("archive_analysis_only", stem, ".zip"),
            [Path(item["path"]) for item in analysis_only_files],
        )
        evidence_payload["generated_outputs"] = [dict(item) for item in output_files]
        evidence_payload["output_manifests"] = {
            "full": _output_manifest(
                output_files,
                zip_path,
                [KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH],
            ),
            "analysis_only": _output_manifest(
                analysis_only_files,
                analysis_only_zip_path,
                [KIND_PROCUREMENT_REPORT],
            ),
        }
    evidence_path = write_evidence(out_dir / "evidence.json", evidence_payload)
    job.evidence_path = str(evidence_path)
    _set_customer_job_title_from_subject(job, subject)
    browser_failure_note = _supplier_browser_failure_note(supplier_evidence)
    browser_failure_error = _supplier_browser_failure_error(supplier_evidence)
    if fallback_rows:
        publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_REGISTRY_FALLBACK)
        _set_job(
            db,
            job,
            status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
            progress=100,
            message=(
                "Анализ готов. По реестру подходящие поставщики не подтверждены; "
                f"вне реестра найдено и проверено: {len(fallback_rows)}. Можно получить этот вариант отдельно."
                + browser_failure_note
            ),
            error=" ".join(item for item in (str(report.warning or "").strip(), browser_failure_error) if item),
        )
        job.completed_at = now_utc()
        db.commit()
        return
    job.result_path = str(zip_path)
    if not accepted:
        release_job_kind_reservation(
            db,
            job,
            KIND_SUPPLIER_SEARCH,
            note="Резерв поставщиков возвращён: подтверждённых поставщиков нет",
        )
        _set_job(
            db,
            job,
            status="needs_review",
            progress=100,
            message="Анализ готов, поставщики не подтверждены" + browser_failure_note,
            error=browser_failure_error or "Поиск не сформировал XLSX, потому что нет ни одного подтверждённого поставщика.",
        )
    elif report.warning:
        _set_job(
            db,
            job,
            status="needs_review",
            progress=100,
            message="Анализ и поставщики готовы, нужна проверка ИИ-настроек" + browser_failure_note,
            error=" ".join(item for item in (str(report.warning or "").strip(), browser_failure_error) if item),
        )
    elif len(accepted) >= job.target_suppliers or len(accepted) >= 20 or _is_registry_only_supplier_search(job):
        _set_job(db, job, status="completed", progress=100, message=_supplier_count_message("Анализ готов", len(accepted), job.target_suppliers), error="")
        charge_job_reservation(db, job, note="Результат готов")
    else:
        publish_job_result_offer(db, job, kind=CONFIRMATION_KIND_PARTIAL_COUNT)
        _set_job(
            db,
            job,
            status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
            progress=100,
            message=_supplier_count_message("Анализ готов, найдено меньше поставщиков", len(accepted), job.target_suppliers) + browser_failure_note,
            error=browser_failure_error,
        )
    job.completed_at = now_utc()
    db.commit()


def _supplier_count_message(prefix: str, count: int, target: int) -> str:
    return f"{prefix}: отобрано кандидатов {count}. Уровень технического совпадения указан в отчёте"


def _supplier_browser_failure_count(evidence: object) -> int:
    if not isinstance(evidence, dict):
        return 0
    failures = evidence.get("browser_failures")
    if not isinstance(failures, dict):
        return 0
    try:
        return max(0, int(failures.get("count") or 0))
    except (TypeError, ValueError):
        return 0


def _supplier_browser_failure_note(evidence: object) -> str:
    if _supplier_browser_failure_count(evidence) <= 0:
        return ""
    return " Часть сайтов временно не удалось проверить."


def _supplier_browser_failure_error(evidence: object) -> str:
    if _supplier_browser_failure_count(evidence) <= 0:
        return ""
    return "Часть сайтов не удалось проверить из-за временной технической ошибки. Повторите поиск, чтобы получить больше результатов."


def package_job_outputs(job: Job) -> Path | None:
    if job.result_path:
        result_path = Path(job.result_path)
        if result_path.exists():
            return result_path
    return None


def package_job_output_files(job: Job) -> list[Path]:
    return [Path(item["path"]) for item in package_job_output_items(job)]


def package_job_output_items(job: Job, _evidence: dict | None = None) -> list[dict]:
    selected_offer_items = active_result_offer_output_items(job, _evidence=_evidence)
    if selected_offer_items is not None:
        return _validated_output_items(job, selected_offer_items)
    items = _output_file_items_from_evidence(job, _evidence=_evidence)
    if items:
        return items
    output = package_job_outputs(job)
    if not output or not output.exists():
        return []
    kind = "analysis" if job.mode == MODE_PROCUREMENT_REPORT else "suppliers"
    label = "Анализ" if kind == "analysis" else "Поставщики"
    return [{"kind": kind, "label": label, "path": str(output)}]


def _output_file_items_from_evidence(job: Job, _evidence: dict | None = None) -> list[dict]:
    if _evidence is not None:
        payload = _evidence
    else:
        evidence_path = Path(str(getattr(job, "evidence_path", "") or ""))
        if not evidence_path.exists():
            return []
        try:
            payload = parse_json_dict(evidence_path.read_text(encoding="utf-8"))
        except Exception:
            return []
    files = payload.get("output_files")
    if not isinstance(files, list):
        return []
    return _validated_output_items(job, files)


def _validated_output_items(job: Job, files: list[dict]) -> list[dict]:
    out_dir = job_dir(job.id).resolve() / "output"
    items: list[dict] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path") or "")).resolve()
        try:
            path.relative_to(out_dir)
        except ValueError:
            continue
        if path.exists():
            kind = str(item.get("kind") or "").strip() or path.stem
            label = str(item.get("label") or "").strip() or {
                "analysis": "Анализ",
                "suppliers": "Поставщики",
                "quote_request": "Запрос КП",
            }.get(kind, kind)
            result = {"kind": kind, "label": label, "path": str(path)}
            content_path = str(item.get("content_path") or "").strip()
            if content_path:
                resolved_content_path = Path(content_path).resolve()
                content_allowed = True
                try:
                    resolved_content_path.relative_to(out_dir)
                except ValueError:
                    content_allowed = False
                if content_allowed and resolved_content_path.exists():
                    result["content_path"] = str(resolved_content_path)
            items.append(result)
    return items


def cleanup_expired_jobs(db: Session, settings=None) -> int:
    settings = settings or get_or_create_settings(db)
    now = now_utc()
    completed_cutoff = now - timedelta(days=max(1, int(settings.completed_job_retention_days or 1)))
    failed_cutoff = now - timedelta(days=max(1, int(settings.failed_job_retention_days or 1)))
    storage_cutoff = now - timedelta(days=max(1, int(settings.storage_retention_days or 1)))

    expired = (
        db.query(Job)
        .filter(
            or_(
                Job.confirmation_kind.is_(None),
                Job.confirmation_kind == "",
                Job.confirmation_outcome.in_(["declined", "expired"]),
                Job.offer_delivery_outcome.in_(["delivered", "expired"]),
            )
        )
        .filter(
            or_(
                and_(
                    Job.status.in_([
                        "completed",
                        "partial",
                        "needs_review",
                        STATUS_CUSTOMER_DECLINED,
                        STATUS_CONFIRMATION_EXPIRED,
                        STATUS_DELIVERY_EXPIRED,
                    ]),
                    Job.completed_at.is_not(None),
                    Job.completed_at < completed_cutoff,
                ),
                and_(
                    Job.status == "failed",
                    Job.completed_at.is_not(None),
                    Job.completed_at < failed_cutoff,
                ),
                and_(
                    Job.status.in_(TERMINAL_JOB_STATUSES),
                    Job.created_at < storage_cutoff,
                ),
            )
        )
        .all()
    )
    for job in expired:
        release_job_reservation(db, job, note="Резерв возвращён: истёк срок хранения задачи")
        db.query(BillingTransaction).filter(BillingTransaction.job_id == job.id).update(
            {BillingTransaction.job_id: None},
            synchronize_session=False,
        )
        shutil.rmtree(job_dir(job.id), ignore_errors=True)
        db.delete(job)
    if expired:
        db.commit()
    return len(expired)


def clear_storage() -> None:
    shutil.rmtree(config.storage_path, ignore_errors=True)
    config.storage_path.mkdir(parents=True, exist_ok=True)

def extract_yandex_job_metrics(evidence: dict | None, price_per_request: float = 0.04) -> tuple[int, float]:
    if not isinstance(evidence, dict):
        return 0, 0.0
    if not evidence.get("search") and isinstance(evidence.get("supplier_search"), dict):
        return extract_yandex_job_metrics(evidence["supplier_search"], price_per_request=price_per_request)
    req_count = 0
    search_info = evidence.get("search")
    if isinstance(search_info, dict):
        if "yandex_requests_count" in search_info:
            req_count += int(search_info["yandex_requests_count"])
    recovery_rounds = evidence.get("recovery_rounds", [])
    if isinstance(recovery_rounds, list):
        for r in recovery_rounds:
            if isinstance(r, dict):
                r_search = r.get("search")
                if isinstance(r_search, dict) and "yandex_requests_count" in r_search:
                    req_count += int(r_search["yandex_requests_count"])
                elif "yandex_requests_count" in r:
                    req_count += int(r["yandex_requests_count"])
    if req_count == 0:
        queries = evidence.get("queries", [])
        reports = search_info.get("reports", []) if isinstance(search_info, dict) else []
        yandex_report = next((r for r in reports if isinstance(r, dict) and r.get("provider") == "yandex"), None)
        if yandex_report and yandex_report.get("status") in ("ok", "error"):
            added = yandex_report.get("added", 0)
            q_len = len(queries) if isinstance(queries, list) else 0
            pages_per_q = 2.0 if added > 50 else 1.5
            req_count = int(q_len * pages_per_q)
    unit_price = float(price_per_request) if price_per_request else 0.04
    cost_rub = round(req_count * unit_price, 2)
    return req_count, cost_rub
