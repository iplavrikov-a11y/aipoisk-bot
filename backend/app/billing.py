from __future__ import annotations

import fcntl
import time
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from sqlalchemy import func, not_, or_
from sqlalchemy.orm import Session

from .config import config
from .models import BillingTransaction, Client, ClientTariffOverride, Job, SystemSettings, TariffPackage, now_utc

KIND_SUPPLIER_SEARCH = "supplier_search"
KIND_PROCUREMENT_REPORT = "procurement_report"
KIND_SUPPLIER_SEARCH_EXTRA = "supplier_search_extra"
KIND_EXACT_PRODUCT = "exact_product"
KIND_MONEY = "money"
VALID_BILLING_KINDS = {
    KIND_SUPPLIER_SEARCH,
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH_EXTRA,
    KIND_EXACT_PRODUCT,
}
SUPPLIER_SEARCH_EXTRA_DEFAULT_PERCENT = 50
DEFAULT_EXACT_PRODUCT_PRICE_KOPEKS = 9900

OP_GRANT = "grant"
OP_RESERVE = "reserve"
OP_CHARGE = "charge"
OP_RELEASE = "release"
OP_MANUAL_DEBIT = "manual_debit"

STATUS_AWAITING_CUSTOMER_CONFIRMATION = "awaiting_customer_confirmation"
STATUS_CUSTOMER_DECLINED = "customer_declined"
STATUS_CONFIRMATION_EXPIRED = "confirmation_expired"
STATUS_DELIVERY_EXPIRED = "delivery_expired"

LOW_BALANCE_THRESHOLD = 1

MODE_SUPPLIER_SEARCH = "supplier_search"
MODE_PROCUREMENT_REPORT = "procurement_report"
MODE_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"
MODE_EXACT_PRODUCT = "exact_product"

INTERNAL_JOB_TOKENS = (
    "smoke",
    "retest",
    "patch",
    "remain",
    "pusher",
    "ai_required",
    "live_",
    "worker_smoke",
)


class BillingError(Exception):
    pass


@contextmanager
def _billing_client_lock(client_id: str) -> Iterator[None]:
    lock_dir = Path(config.storage_path) / ".billing-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(character for character in str(client_id or "") if character.isalnum() or character in {"-", "_"}) or "unknown"
    with (lock_dir / f"{safe_id}.lock").open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _normalized_idempotency_key(value: str) -> str | None:
    normalized = str(value or "").strip()
    return normalized[:80] or None


def _idempotent_transaction(
    db: Session,
    idempotency_key: str,
    *,
    client_id: str,
    kind: str,
    operation: str,
    amount_kopeks: int | None = None,
    units: int | None = None,
) -> BillingTransaction | None:
    normalized = _normalized_idempotency_key(idempotency_key)
    if not normalized:
        return None
    existing = db.query(BillingTransaction).filter(BillingTransaction.idempotency_key == normalized).first()
    if not existing:
        return None
    if existing.client_id != client_id or existing.kind != kind or existing.operation != operation:
        raise BillingError("Ключ операции уже использован для другого начисления или списания")
    if amount_kopeks is not None and int(existing.amount_kopeks or 0) != int(amount_kopeks):
        raise BillingError("Ключ операции повторно использован с другой суммой")
    if units is not None and int(existing.units or 0) != int(units):
        raise BillingError("Ключ операции повторно использован с другим количеством")
    return existing


def billing_kind_label(kind: str) -> str:
    if kind == KIND_MONEY:
        return "Баланс"
    if kind == KIND_PROCUREMENT_REPORT:
        return "Анализ документации"
    if kind == KIND_SUPPLIER_SEARCH_EXTRA:
        return "Добор поставщиков"
    if kind == KIND_EXACT_PRODUCT:
        return "Подбор товара и аналогов"
    return "Поставщики"


def requested_billing_units(mode: str, *, supplier_search_count: int = 1) -> dict[str, int]:
    supplier_units = max(1, int(supplier_search_count or 1))
    if mode == MODE_SUPPLIER_SEARCH:
        return {KIND_SUPPLIER_SEARCH: supplier_units, KIND_PROCUREMENT_REPORT: 0, KIND_SUPPLIER_SEARCH_EXTRA: 0, KIND_EXACT_PRODUCT: 0}
    if mode == MODE_PROCUREMENT_REPORT:
        return {KIND_SUPPLIER_SEARCH: 0, KIND_PROCUREMENT_REPORT: 1, KIND_SUPPLIER_SEARCH_EXTRA: 0, KIND_EXACT_PRODUCT: 0}
    if mode == MODE_ANALYSIS_AND_SUPPLIERS:
        return {KIND_SUPPLIER_SEARCH: 1, KIND_PROCUREMENT_REPORT: 1, KIND_SUPPLIER_SEARCH_EXTRA: 0, KIND_EXACT_PRODUCT: 0}
    if mode == MODE_EXACT_PRODUCT:
        return {KIND_SUPPLIER_SEARCH: 0, KIND_PROCUREMENT_REPORT: 0, KIND_SUPPLIER_SEARCH_EXTRA: 0, KIND_EXACT_PRODUCT: 1}
    return {KIND_SUPPLIER_SEARCH: 0, KIND_PROCUREMENT_REPORT: 0, KIND_SUPPLIER_SEARCH_EXTRA: 0, KIND_EXACT_PRODUCT: 0}


def requested_billing_kinds(mode: str, *, supplier_search_count: int = 1, supplier_search_run_type: str = "initial") -> dict[str, int]:
    units = requested_billing_units(mode, supplier_search_count=supplier_search_count)
    if mode == MODE_SUPPLIER_SEARCH and str(supplier_search_run_type or "") == "additional":
        units[KIND_SUPPLIER_SEARCH_EXTRA] = units.get(KIND_SUPPLIER_SEARCH, 0)
        units[KIND_SUPPLIER_SEARCH] = 0
    return units


def resolve_requested_billing_kinds(
    db: Session,
    client: Client,
    mode: str,
    *,
    supplier_search_count: int = 1,
    supplier_search_run_type: str = "initial",
) -> dict[str, int]:
    units = requested_billing_kinds(
        mode,
        supplier_search_count=supplier_search_count,
        supplier_search_run_type=supplier_search_run_type,
    )
    if (
        mode == MODE_SUPPLIER_SEARCH
        and str(supplier_search_run_type or "") == "additional"
        and units.get(KIND_SUPPLIER_SEARCH_EXTRA, 0) > 0
        and effective_price_kopeks(db, client, KIND_SUPPLIER_SEARCH_EXTRA) <= 0
        and not _has_billing_transactions(db, client.id, KIND_SUPPLIER_SEARCH_EXTRA)
    ):
        return requested_billing_units(mode, supplier_search_count=supplier_search_count)
    return units


def client_balance_summary(db: Session, client: Client) -> dict:
    money = money_balance_summary(db, client)
    return {
        KIND_SUPPLIER_SEARCH: balance_counter(db, client, KIND_SUPPLIER_SEARCH),
        KIND_PROCUREMENT_REPORT: balance_counter(db, client, KIND_PROCUREMENT_REPORT),
        KIND_SUPPLIER_SEARCH_EXTRA: balance_counter(db, client, KIND_SUPPLIER_SEARCH_EXTRA),
        KIND_EXACT_PRODUCT: balance_counter(db, client, KIND_EXACT_PRODUCT),
        "money": money,
        "effective_prices": {
            kind: effective_price_to_dict(db, client, kind)
            for kind in (KIND_SUPPLIER_SEARCH, KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH_EXTRA, KIND_EXACT_PRODUCT)
        },
    }


def client_service_balance_summary(db: Session, client: Client) -> dict:
    balances = deepcopy(client_balance_summary(db, client))
    if not _supplier_search_extra_uses_supplier_access(db, client):
        return balances

    supplier_counter = balances[KIND_SUPPLIER_SEARCH]
    extra_counter = balances[KIND_SUPPLIER_SEARCH_EXTRA]
    fallback_counter = _supplier_search_extra_fallback_counter(supplier_counter, extra_counter)
    extra_counter.update(fallback_counter)
    extra_counter["kind"] = KIND_SUPPLIER_SEARCH_EXTRA
    extra_counter["label"] = billing_kind_label(KIND_SUPPLIER_SEARCH_EXTRA)
    extra_counter["source"] = "supplier_search_access_fallback"
    extra_counter["fallback_kind"] = KIND_SUPPLIER_SEARCH

    return balances


def _supplier_search_extra_falls_back_to_supplier_search(db: Session, client: Client) -> bool:
    return (
        effective_price_kopeks(db, client, KIND_SUPPLIER_SEARCH_EXTRA) <= 0
        and not _has_billing_transactions(db, client.id, KIND_SUPPLIER_SEARCH_EXTRA)
    )


def _supplier_search_extra_uses_supplier_access(db: Session, client: Client) -> bool:
    return not _has_billing_grants(db, client.id, KIND_SUPPLIER_SEARCH_EXTRA)


def _supplier_search_extra_fallback_counter(supplier_counter: dict, extra_counter: dict) -> dict:
    unlimited = bool(supplier_counter.get("unlimited"))
    reserved = max(0, int(extra_counter.get("reserved") or 0))
    spent = max(0, int(extra_counter.get("spent") or 0))
    manual_debited = max(0, int(extra_counter.get("manual_debited") or 0))
    supplier_available = supplier_counter.get("available")
    if unlimited:
        available = None
    else:
        available = max(0, int(supplier_available or 0) - reserved - spent - manual_debited)
    price = int(extra_counter.get("price_kopeks") or 0)
    return {
        "granted": supplier_counter.get("granted"),
        "manual_debited": manual_debited,
        "available": available,
        "reserved": reserved,
        "spent": spent,
        "unlimited": unlimited,
        "price_kopeks": price,
        "price_rub": round(price / 100, 2),
        "low": False if unlimited else int(available or 0) <= LOW_BALANCE_THRESHOLD,
    }


def balance_counter(db: Session, client: Client, kind: str) -> dict:
    if _has_billing_transactions(db, client.id, kind):
        counter = _ledger_counter(db, client.id, kind)
    else:
        counter = _legacy_counter(db, client, kind)
    counter["kind"] = kind
    counter["label"] = billing_kind_label(kind)
    counter["low"] = not counter["unlimited"] and counter["available"] <= LOW_BALANCE_THRESHOLD
    price = effective_price_kopeks(db, client, kind)
    counter["price_kopeks"] = price
    counter["price_rub"] = round(price / 100, 2)
    return counter


def money_balance_summary(db: Session, client: Client) -> dict:
    balance = max(0, int(getattr(client, "money_balance_kopeks", 0) or 0))
    reserved = max(0, int(getattr(client, "money_reserved_kopeks", 0) or 0))
    available = max(0, balance - reserved)
    return {
        "balance_kopeks": balance,
        "reserved_kopeks": reserved,
        "available_kopeks": available,
        "balance_rub": round(balance / 100, 2),
        "reserved_rub": round(reserved / 100, 2),
        "available_rub": round(available / 100, 2),
        "source": "money_ledger",
        "low": available <= _lowest_active_function_price(db, client),
    }


def effective_price_kopeks(db: Session, client: Client | None, kind: str) -> int:
    if kind not in VALID_BILLING_KINDS:
        return 0
    explicit_price = _explicit_effective_price_kopeks(db, client, kind)
    if explicit_price is not None:
        return explicit_price
    if kind == KIND_SUPPLIER_SEARCH_EXTRA:
        return _default_supplier_search_extra_price_kopeks(db, client)
    if kind == KIND_EXACT_PRODUCT:
        return DEFAULT_EXACT_PRODUCT_PRICE_KOPEKS
    return 0


def trial_grant_summary_text(db: Session, client: Client | None) -> str:
    """Человеческое описание стартового триал-баланса, например '5 задач'.

    Считается из баланса настроек или лимитов и цен тарифов, чтобы тексты не протухали
    при смене лимитов/цен. Если данных нет — нейтральная формулировка.
    """
    settings = db.query(SystemSettings).first()
    if settings is None:
        return "бесплатные задачи"

    price_search = effective_price_kopeks(db, client, KIND_SUPPLIER_SEARCH) or 9900
    price_report = effective_price_kopeks(db, client, KIND_PROCUREMENT_REPORT) or 9900
    price_product = effective_price_kopeks(db, client, KIND_EXACT_PRODUCT) or 9900
    min_task_price = min(price for price in (price_search, price_report, price_product) if price > 0) or 9900

    trial_rub = getattr(settings, "trial_balance_rub", None)
    if trial_rub is not None and int(trial_rub or 0) > 0:
        total_kopeks = int(trial_rub) * 100
        total_units = max(1, total_kopeks // min_task_price)
    else:
        units_search = max(int(settings.trial_supplier_search_limit or 0), 0)
        units_report = max(int(settings.trial_procurement_report_limit or 0), 0)
        total_units = units_search + units_report
        total_kopeks = units_search * price_search + units_report * price_report

    if total_units <= 0 and total_kopeks <= 0:
        return "бесплатные задачи"

    if total_units % 100 in (11, 12, 13, 14):
        tasks_word = "задач"
    elif total_units % 10 == 1:
        tasks_word = "задача"
    elif total_units % 10 in (2, 3, 4):
        tasks_word = "задачи"
    else:
        tasks_word = "задач"

    return f"{total_units} {tasks_word}"


def invalidate_tariff_packages_cache(db: Session | None = None) -> None:
    if db is not None and hasattr(db, "info"):
        db.info.pop("active_tariff_packages", None)


def _active_tariff_packages(db: Session) -> dict[str, TariffPackage]:
    if hasattr(db, "info"):
        cached = db.info.get("active_tariff_packages")
        if cached is not None:
            return cached
    packages = (
        db.query(TariffPackage)
        .filter(TariffPackage.is_active.is_(True))
        .order_by(TariffPackage.sort_order.asc(), TariffPackage.price_kopeks.asc())
        .all()
    )
    result: dict[str, TariffPackage] = {}
    for pkg in packages:
        if pkg.kind not in result:
            result[pkg.kind] = pkg
    if hasattr(db, "info"):
        db.info["active_tariff_packages"] = result
    return result


def _explicit_effective_price_kopeks(db: Session | None, client: Client | None, kind: str) -> int | None:
    if db is None:
        return None
    if client:
        override = _client_tariff_override(db, client, kind)
        if override:
            if not override.is_enabled:
                return 0
            return max(0, int(override.price_kopeks or 0))
    package = _active_tariff_packages(db).get(kind)
    if not package:
        return None
    units = max(1, int(package.units or 1))
    return max(0, round(int(package.price_kopeks or 0) / units))


def _default_supplier_search_extra_price_kopeks(db: Session, client: Client | None) -> int:
    package = _active_tariff_packages(db).get(KIND_SUPPLIER_SEARCH_EXTRA)
    if package:
        units = max(1, int(package.units or 1))
        return max(0, round(int(package.price_kopeks or 0) / units))
    supplier_price = effective_price_kopeks(db, client, KIND_SUPPLIER_SEARCH)
    if supplier_price <= 0:
        return 0
    if supplier_price == 9900:
        return 4900
    return max(0, (supplier_price // 200) * 100 if supplier_price % 200 != 0 else round(supplier_price * SUPPLIER_SEARCH_EXTRA_DEFAULT_PERCENT / 100))


def _client_tariff_override(db: Session, client: Client, kind: str) -> ClientTariffOverride | None:
    overrides = getattr(client, "tariff_overrides", None)
    if overrides is not None and isinstance(overrides, list):
        matching = [ov for ov in overrides if ov.kind == kind]
        if matching:
            return max(matching, key=lambda ov: ov.updated_at or ov.created_at or datetime.min)
        return None
    return (
        db.query(ClientTariffOverride)
        .filter(ClientTariffOverride.client_id == client.id)
        .filter(ClientTariffOverride.kind == kind)
        .order_by(ClientTariffOverride.updated_at.desc())
        .first()
    )


def effective_price_to_dict(db: Session, client: Client | None, kind: str) -> dict:
    override = None
    if client:
        override = _client_tariff_override(db, client, kind)
    price = effective_price_kopeks(db, client, kind)
    explicit_price = _explicit_effective_price_kopeks(db, client, kind)
    return {
        "kind": kind,
        "label": billing_kind_label(kind),
        "price_kopeks": price,
        "price_rub": round(price / 100, 2),
        "source": _effective_price_source(kind, override=override, explicit_price=explicit_price),
        "enabled": price > 0,
    }


def _effective_price_source(kind: str, *, override: ClientTariffOverride | None, explicit_price: int | None) -> str:
    if override:
        return "client_override"
    if explicit_price is not None:
        return "global"
    if kind == KIND_SUPPLIER_SEARCH_EXTRA:
        return "supplier_search_default_50_percent"
    return "global"


def _lowest_active_function_price(db: Session, client: Client) -> int:
    prices = [
        effective_price_kopeks(db, client, kind)
        for kind in (KIND_SUPPLIER_SEARCH, KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH_EXTRA, KIND_EXACT_PRODUCT)
    ]
    active = [price for price in prices if price > 0]
    return min(active) if active else 1


def _ledger_counter(db: Session, client_id: str, kind: str) -> dict:
    rows = (
        db.query(BillingTransaction.operation, func.coalesce(func.sum(BillingTransaction.units), 0))
        .filter(BillingTransaction.client_id == client_id)
        .filter(BillingTransaction.kind == kind)
        .group_by(BillingTransaction.operation)
        .all()
    )
    totals = {operation: int(total or 0) for operation, total in rows}
    granted = totals.get(OP_GRANT, 0)
    manual_debited = totals.get(OP_MANUAL_DEBIT, 0)
    reserved_total = totals.get(OP_RESERVE, 0)
    released = totals.get(OP_RELEASE, 0)
    charged = totals.get(OP_CHARGE, 0)
    reserved = max(0, reserved_total - released - charged)
    available = max(0, granted + released - reserved_total - manual_debited)
    return {
        "granted": granted,
        "manual_debited": manual_debited,
        "available": available,
        "reserved": reserved,
        "spent": charged,
        "unlimited": False,
        "source": "ledger",
    }


def _legacy_counter(db: Session, client: Client, kind: str, *, exclude_job_id: str = "") -> dict:
    supplier_used, report_used = _legacy_current_month_usage(db, client.id, exclude_job_id=exclude_job_id)
    if kind == KIND_PROCUREMENT_REPORT:
        limit = int(client.monthly_procurement_report_limit or 0)
        used = report_used
    elif kind in {KIND_SUPPLIER_SEARCH_EXTRA, KIND_EXACT_PRODUCT}:
        limit = 0
        used = 0
    else:
        limit = int(client.monthly_supplier_search_limit or 0)
        used = supplier_used
    unlimited = limit < 0
    available = None if unlimited else max(0, limit - used)
    return {
        "granted": limit,
        "manual_debited": 0,
        "available": available,
        "reserved": 0,
        "spent": used,
        "unlimited": unlimited,
        "source": "legacy_monthly_limit",
    }


def _legacy_current_month_usage(db: Session, client_id: str, *, exclude_job_id: str = "") -> tuple[int, int]:
    now = now_utc()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    base = (
        db.query(Job)
        .filter(Job.client_id == client_id)
        .filter(Job.created_at >= month_start)
        .filter(not_(or_(*_internal_job_filters())))
    )
    if exclude_job_id:
        base = base.filter(Job.id != exclude_job_id)
    supplier_used = (
        base.filter(Job.mode.in_([MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS]))
        .with_entities(func.count(Job.id))
        .scalar()
    )
    report_used = (
        base.filter(Job.mode.in_([MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS]))
        .with_entities(func.count(Job.id))
        .scalar()
    )
    return int(supplier_used or 0), int(report_used or 0)


def _internal_job_filters() -> list:
    filters = []
    for token in INTERNAL_JOB_TOKENS:
        pattern = f"%{token}%"
        filters.extend(
            [
                func.coalesce(Job.title, "").ilike(pattern),
                func.coalesce(Job.message, "").ilike(pattern),
                func.coalesce(Job.error, "").ilike(pattern),
            ]
        )
    return filters


def _has_billing_transactions(db: Session, client_id: str, kind: str) -> bool:
    return bool(
        db.query(BillingTransaction.id)
        .filter(BillingTransaction.client_id == client_id)
        .filter(BillingTransaction.kind == kind)
        .first()
    )


def _has_billing_grants(db: Session, client_id: str, kind: str) -> bool:
    return bool(
        db.query(BillingTransaction.id)
        .filter(BillingTransaction.client_id == client_id)
        .filter(BillingTransaction.kind == kind)
        .filter(BillingTransaction.operation == OP_GRANT)
        .first()
    )


def client_has_paid_grants(db: Session, client: Client | None) -> bool:
    if not client:
        return False
    return bool(
        db.query(BillingTransaction.id)
        .filter(BillingTransaction.client_id == client.id)
        .filter(BillingTransaction.operation == OP_GRANT)
        .filter(func.lower(func.coalesce(BillingTransaction.created_by, "")).notin_(["", "system"]))
        .first()
    )


def client_uses_trial_access(db: Session, client: Client | None) -> bool:
    return bool(client and getattr(client, "is_trial", False) and not client_has_paid_grants(db, client))


def access_error_for_units(db: Session, client: Client, units: dict[str, int]) -> str:
    available_money = money_balance_summary(db, client)["available_kopeks"]
    for kind, count in units.items():
        if count <= 0:
            continue
        override = _client_tariff_override(db, client, kind)
        if override and not override.is_enabled:
            return f"Услуга «{billing_kind_label(kind)}» отключена для этого клиента."
        price = effective_price_kopeks(db, client, kind)
        if price > 0:
            required_money = max(0, int(count or 0)) * price
            if available_money < required_money:
                return (
                    f"Недостаточно средств для услуги «{billing_kind_label(kind)}». "
                    f"Доступно {round(available_money / 100, 2)} ₽, "
                    f"нужно {round(required_money / 100, 2)} ₽. "
                    "Откройте «Тарифы и оплата», чтобы пополнить баланс."
                )
            available_money -= required_money
            continue
        counter = _access_counter(db, client, kind)
        if counter["unlimited"]:
            continue
        if int(counter["available"] or 0) < count:
            return (
                f"Недостаточно генераций: {billing_kind_label(kind)}. "
                f"Доступно {counter['available']}, нужно {count}. "
                "Откройте «Тарифы и оплата», чтобы пополнить баланс."
            )
    return ""


def _access_counter(db: Session, client: Client, kind: str) -> dict:
    if kind == KIND_SUPPLIER_SEARCH_EXTRA and _supplier_search_extra_uses_supplier_access(db, client):
        supplier_counter = balance_counter(db, client, KIND_SUPPLIER_SEARCH)
        extra_counter = balance_counter(db, client, KIND_SUPPLIER_SEARCH_EXTRA)
        counter = _supplier_search_extra_fallback_counter(supplier_counter, extra_counter)
        counter["kind"] = KIND_SUPPLIER_SEARCH_EXTRA
        counter["label"] = billing_kind_label(KIND_SUPPLIER_SEARCH_EXTRA)
        return counter
    return balance_counter(db, client, kind)


def reserve_job_units(db: Session, client: Client, job: Job, *, supplier_search_count: int = 1) -> None:
    with _billing_client_lock(client.id):
        db.refresh(client)
        _reserve_job_units_locked(db, client, job, supplier_search_count=supplier_search_count)


def _reserve_job_units_locked(db: Session, client: Client, job: Job, *, supplier_search_count: int = 1) -> None:
    _initialize_legacy_balance_if_needed(db, client, exclude_job_id=job.id)
    units = resolve_requested_billing_kinds(
        db,
        client,
        job.mode,
        supplier_search_count=supplier_search_count,
        supplier_search_run_type=getattr(job, "supplier_search_run_type", "initial"),
    )
    units_to_reserve = {
        kind: count
        for kind, count in units.items()
        if count > 0 and not _job_has_operation(db, job.id, kind, OP_RESERVE)
    }
    error = access_error_for_units(db, client, units_to_reserve)
    if error:
        raise BillingError(error)
    for kind, count in units_to_reserve.items():
        amount = _reservable_amount_for_kind(db, client, kind, count)
        if amount > 0:
            client.money_reserved_kopeks = max(0, int(client.money_reserved_kopeks or 0)) + amount
        db.add(
            BillingTransaction(
                client_id=client.id,
                job_id=job.id,
                kind=kind,
                operation=OP_RESERVE,
                units=count,
                amount_kopeks=amount,
                balance_after_kopeks=max(0, int(client.money_balance_kopeks or 0)),
                reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
                note="Резерв средств перед запуском задачи" if amount > 0 else "Резерв перед запуском задачи",
                created_by="system",
            )
        )
    db.commit()


def _reservable_amount_for_kind(db: Session, client: Client, kind: str, count: int) -> int:
    price = effective_price_kopeks(db, client, kind)
    amount = price * max(0, int(count or 0))
    if amount <= 0:
        return 0
    available_total = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))
    if available_total < amount:
        raise BillingError(
            f"Недостаточно средств для услуги «{billing_kind_label(kind)}»: "
            f"доступно {available_total / 100:.2f} ₽, нужно {amount / 100:.2f} ₽"
        )
    return amount


def charge_job_reservation(db: Session, job: Job, *, note: str = "Результат отправлен клиенту") -> None:
    if not job.client_id:
        return
    with _billing_client_lock(job.client_id):
        _charge_job_reservation_locked(db, job, note=note)
        db.commit()


def _charge_job_reservation_locked(db: Session, job: Job, *, note: str) -> None:
    for kind in VALID_BILLING_KINDS:
        _charge_job_kind_reservation_locked(db, job, kind, note=note)


def charge_job_kind_reservation(
    db: Session,
    job: Job,
    kind: str,
    *,
    note: str = "Результат отправлен клиенту",
) -> None:
    """Settle only one reserved product kind, idempotently across delivery channels."""
    if not job.client_id or kind not in VALID_BILLING_KINDS:
        return
    with _billing_client_lock(job.client_id):
        _charge_job_kind_reservation_locked(db, job, kind, note=note)
        db.commit()


def _charge_job_kind_reservation_locked(db: Session, job: Job, kind: str, *, note: str) -> bool:
    if kind not in VALID_BILLING_KINDS:
        return False
    remaining = _job_reserved_remaining(db, job.id, kind)
    remaining_amount = _job_reserved_amount_remaining(db, job.id, kind)
    if (remaining <= 0 and remaining_amount <= 0) or _job_has_operation(db, job.id, kind, OP_CHARGE):
        return False
    client = db.get(Client, job.client_id) if job.client_id else None
    if client:
        db.refresh(client)
    if client and remaining_amount > 0:
        client.money_reserved_kopeks = max(0, int(client.money_reserved_kopeks or 0) - remaining_amount)
        client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0) - remaining_amount)
    db.add(
        BillingTransaction(
            client_id=job.client_id,
            job_id=job.id,
            kind=kind,
            operation=OP_CHARGE,
            units=remaining,
            amount_kopeks=remaining_amount,
            balance_after_kopeks=max(0, int(getattr(client, "money_balance_kopeks", 0) or 0)) if client else 0,
            reserved_after_kopeks=max(0, int(getattr(client, "money_reserved_kopeks", 0) or 0)) if client else 0,
            note=note,
            created_by="system",
        )
    )
    return True


def job_has_unsettled_reservation(db: Session, job: Job) -> bool:
    if not job.client_id:
        return False
    return any(
        _job_reserved_remaining(db, job.id, kind) > 0 or _job_reserved_amount_remaining(db, job.id, kind) > 0
        for kind in VALID_BILLING_KINDS
    )


def job_reserved_amount_kopeks(db: Session | None, job: Job, kind: str | None = None) -> int:
    """Return the still-reserved monetary amount shown before an offer is accepted."""
    if db is None or not getattr(job, "id", None):
        return 0
    if kind:
        return _job_reserved_amount_remaining(db, job.id, kind)
    return sum(_job_reserved_amount_remaining(db, job.id, item) for item in VALID_BILLING_KINDS)


def release_job_reservation(db: Session, job: Job, *, note: str = "Резерв возвращён") -> None:
    if not job.client_id:
        return
    with _billing_client_lock(job.client_id):
        for kind in VALID_BILLING_KINDS:
            _release_job_kind_reservation(db, job, kind, note=note)
        db.commit()


def release_job_kind_reservation(db: Session, job: Job, kind: str, *, note: str = "Резерв возвращён") -> None:
    if not job.client_id:
        return
    with _billing_client_lock(job.client_id):
        _release_job_kind_reservation(db, job, kind, note=note)
        db.commit()


def _release_job_kind_reservation(db: Session, job: Job, kind: str, *, note: str) -> None:
    remaining = _job_reserved_remaining(db, job.id, kind)
    remaining_amount = _job_reserved_amount_remaining(db, job.id, kind)
    if remaining <= 0 and remaining_amount <= 0:
        return
    client = db.get(Client, job.client_id) if job.client_id else None
    if client:
        db.refresh(client)
    if client and remaining_amount > 0:
        client.money_reserved_kopeks = max(0, int(client.money_reserved_kopeks or 0) - remaining_amount)
    db.add(
        BillingTransaction(
            client_id=job.client_id,
            job_id=job.id,
            kind=kind,
            operation=OP_RELEASE,
            units=remaining,
            amount_kopeks=remaining_amount,
            balance_after_kopeks=max(0, int(getattr(client, "money_balance_kopeks", 0) or 0)) if client else 0,
            reserved_after_kopeks=max(0, int(getattr(client, "money_reserved_kopeks", 0) or 0)) if client else 0,
            note=note,
            created_by="system",
        )
    )


def _job_reserved_remaining(db: Session, job_id: str, kind: str) -> int:
    rows = (
        db.query(BillingTransaction.operation, func.coalesce(func.sum(BillingTransaction.units), 0))
        .filter(BillingTransaction.job_id == job_id)
        .filter(BillingTransaction.kind == kind)
        .filter(BillingTransaction.operation.in_([OP_RESERVE, OP_CHARGE, OP_RELEASE]))
        .group_by(BillingTransaction.operation)
        .all()
    )
    totals = {operation: int(total or 0) for operation, total in rows}
    return max(0, totals.get(OP_RESERVE, 0) - totals.get(OP_CHARGE, 0) - totals.get(OP_RELEASE, 0))


def _job_reserved_amount_remaining(db: Session, job_id: str, kind: str) -> int:
    rows = (
        db.query(BillingTransaction.operation, func.coalesce(func.sum(BillingTransaction.amount_kopeks), 0))
        .filter(BillingTransaction.job_id == job_id)
        .filter(BillingTransaction.kind == kind)
        .filter(BillingTransaction.operation.in_([OP_RESERVE, OP_CHARGE, OP_RELEASE]))
        .group_by(BillingTransaction.operation)
        .all()
    )
    totals = {operation: int(total or 0) for operation, total in rows}
    return max(0, totals.get(OP_RESERVE, 0) - totals.get(OP_CHARGE, 0) - totals.get(OP_RELEASE, 0))


def _job_has_operation(db: Session, job_id: str, kind: str, operation: str) -> bool:
    return bool(
        db.query(BillingTransaction.id)
        .filter(BillingTransaction.job_id == job_id)
        .filter(BillingTransaction.kind == kind)
        .filter(BillingTransaction.operation == operation)
        .first()
    )


def _initialize_legacy_balance_if_needed(db: Session, client: Client, *, exclude_job_id: str = "") -> None:
    changed = False
    for kind in (KIND_SUPPLIER_SEARCH, KIND_PROCUREMENT_REPORT):
        if _has_billing_transactions(db, client.id, kind):
            continue
        counter = _legacy_counter(db, client, kind, exclude_job_id=exclude_job_id)
        if counter["unlimited"]:
            continue
        available = max(0, int(counter["available"] or 0))
        if available <= 0:
            continue
        db.add(
            BillingTransaction(
                client_id=client.id,
                kind=kind,
                operation=OP_GRANT,
                units=available,
                note="Перенос остатка из прежнего лимита",
                created_by="system",
            )
        )
        changed = True
    if changed:
        db.commit()


def grant_package_units(
    db: Session,
    client: Client,
    *,
    kind: str,
    units: int,
    amount_kopeks: int = 0,
    package_id: str = "",
    note: str = "",
    created_by: str = "admin",
    idempotency_key: str = "",
) -> BillingTransaction:
    if kind not in VALID_BILLING_KINDS:
        raise BillingError("Unknown billing kind")
    safe_units = int(units or 0)
    if safe_units <= 0:
        raise BillingError("Units must be positive")
    with _billing_client_lock(client.id):
        db.refresh(client)
        expected_amount = max(0, int(amount_kopeks or 0)) or _grant_amount_kopeks(db, client, kind, safe_units, package_id=package_id)
        existing = _idempotent_transaction(
            db,
            idempotency_key,
            client_id=client.id,
            kind=kind,
            operation=OP_GRANT,
            amount_kopeks=expected_amount,
            units=safe_units,
        )
        if existing:
            return existing
        return _grant_package_units_locked(
            db,
            client,
            kind=kind,
            units=safe_units,
            amount_kopeks=amount_kopeks,
            package_id=package_id,
            note=note,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )


def _grant_package_units_locked(
    db: Session,
    client: Client,
    *,
    kind: str,
    units: int,
    amount_kopeks: int,
    package_id: str,
    note: str,
    created_by: str,
    idempotency_key: str,
) -> BillingTransaction:
    safe_units = max(1, int(units or 1))
    amount = max(0, int(amount_kopeks or 0)) or _grant_amount_kopeks(db, client, kind, safe_units, package_id=package_id)
    if amount > 0:
        client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0)) + amount
    transaction = BillingTransaction(
        client_id=client.id,
        package_id=package_id,
        kind=kind,
        operation=OP_GRANT,
        idempotency_key=_normalized_idempotency_key(idempotency_key),
        units=safe_units,
        amount_kopeks=amount,
        balance_after_kopeks=max(0, int(client.money_balance_kopeks or 0)),
        reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
        note=note or "Ручное пополнение пакета",
        created_by=created_by,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def grant_money_balance(
    db: Session,
    client: Client,
    *,
    amount_kopeks: int,
    note: str = "",
    created_by: str = "admin",
    idempotency_key: str = "",
) -> BillingTransaction:
    amount = max(0, int(amount_kopeks or 0))
    if amount <= 0:
        raise BillingError("Amount must be positive")
    with _billing_client_lock(client.id):
        db.refresh(client)
        existing = _idempotent_transaction(db, idempotency_key, client_id=client.id, kind=KIND_MONEY, operation=OP_GRANT, amount_kopeks=amount, units=0)
        if existing:
            return existing
        return _grant_money_balance_locked(db, client, amount=amount, note=note, created_by=created_by, idempotency_key=idempotency_key)


def _grant_money_balance_locked(
    db: Session,
    client: Client,
    *,
    amount: int,
    note: str,
    created_by: str,
    idempotency_key: str,
) -> BillingTransaction:
    client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0)) + amount
    transaction = BillingTransaction(
        client_id=client.id,
        kind=KIND_MONEY,
        operation=OP_GRANT,
        idempotency_key=_normalized_idempotency_key(idempotency_key),
        units=0,
        amount_kopeks=amount,
        balance_after_kopeks=max(0, int(client.money_balance_kopeks or 0)),
        reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
        note=note or "Ручное пополнение баланса",
        created_by=created_by,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def debit_money_balance(
    db: Session,
    client: Client,
    *,
    amount_kopeks: int,
    note: str = "",
    created_by: str = "admin",
    idempotency_key: str = "",
) -> BillingTransaction:
    amount = max(0, int(amount_kopeks or 0))
    if amount <= 0:
        raise BillingError("Amount must be positive")
    with _billing_client_lock(client.id):
        db.refresh(client)
        existing = _idempotent_transaction(db, idempotency_key, client_id=client.id, kind=KIND_MONEY, operation=OP_MANUAL_DEBIT, amount_kopeks=amount, units=0)
        if existing:
            return existing
        return _debit_money_balance_locked(db, client, amount=amount, note=note, created_by=created_by, idempotency_key=idempotency_key)


def _debit_money_balance_locked(
    db: Session,
    client: Client,
    *,
    amount: int,
    note: str,
    created_by: str,
    idempotency_key: str,
) -> BillingTransaction:
    available_money = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))
    if available_money < amount:
        raise BillingError(f"Недостаточно денег для списания: доступно {available_money / 100:.2f} ₽, нужно {amount / 100:.2f} ₽")
    client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0) - amount)
    transaction = BillingTransaction(
        client_id=client.id,
        kind=KIND_MONEY,
        operation=OP_MANUAL_DEBIT,
        idempotency_key=_normalized_idempotency_key(idempotency_key),
        units=0,
        amount_kopeks=amount,
        balance_after_kopeks=max(0, int(client.money_balance_kopeks or 0)),
        reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
        note=note or "Ручное списание с баланса",
        created_by=created_by,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def grant_trial_balance(
    db: Session,
    client: Client,
    *,
    amount_kopeks: int | None = None,
    supplier_search_units: int = 0,
    procurement_report_units: int = 0,
    note: str = "Стартовый баланс триала",
) -> None:
    db.flush()
    with _billing_client_lock(client.id):
        db.refresh(client)
        _grant_trial_balance_locked(
            db,
            client,
            amount_kopeks=amount_kopeks,
            supplier_search_units=supplier_search_units,
            procurement_report_units=procurement_report_units,
            note=note,
        )


def _grant_trial_balance_locked(
    db: Session,
    client: Client,
    *,
    amount_kopeks: int | None = None,
    supplier_search_units: int = 0,
    procurement_report_units: int = 0,
    note: str,
) -> None:
    if amount_kopeks is not None:
        amount = max(0, int(amount_kopeks))
        if amount <= 0:
            return
        money_note = note
        existing_grant = (
            db.query(BillingTransaction.id)
            .filter(BillingTransaction.client_id == client.id)
            .filter(BillingTransaction.operation == OP_GRANT)
            .filter(func.lower(func.coalesce(BillingTransaction.created_by, "")) == "system")
            .filter(
                or_(
                    (BillingTransaction.kind == KIND_MONEY) & (BillingTransaction.note == money_note),
                    BillingTransaction.note.like(f"{note}%"),
                )
            )
            .first()
        )
        if existing_grant:
            return
        client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0)) + amount
        db.add(
            BillingTransaction(
                client_id=client.id,
                kind=KIND_MONEY,
                operation=OP_GRANT,
                units=0,
                amount_kopeks=amount,
                balance_after_kopeks=max(0, int(client.money_balance_kopeks or 0)),
                reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
                note=money_note,
                created_by="system",
            )
        )
        db.flush()
        return

    for kind, units in (
        (KIND_SUPPLIER_SEARCH, supplier_search_units),
        (KIND_PROCUREMENT_REPORT, procurement_report_units),
    ):
        safe_units = max(0, int(units or 0))
        amount = effective_price_kopeks(db, client, kind) * safe_units
        if amount <= 0:
            continue
        money_note = f"{note}: {billing_kind_label(kind)}"
        existing_grant = (
            db.query(BillingTransaction.id)
            .filter(BillingTransaction.client_id == client.id)
            .filter(BillingTransaction.operation == OP_GRANT)
            .filter(func.lower(func.coalesce(BillingTransaction.created_by, "")) == "system")
            .filter(
                or_(
                    (BillingTransaction.kind == kind) & (BillingTransaction.amount_kopeks > 0),
                    (BillingTransaction.kind == KIND_MONEY) & (BillingTransaction.note == money_note),
                )
            )
            .first()
        )
        if existing_grant:
            continue
        client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0)) + amount
        db.add(
            BillingTransaction(
                client_id=client.id,
                kind=KIND_MONEY,
                operation=OP_GRANT,
                units=0,
                amount_kopeks=amount,
                balance_after_kopeks=max(0, int(client.money_balance_kopeks or 0)),
                reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
                note=money_note,
                created_by="system",
            )
        )
    db.flush()


def _grant_amount_kopeks(db: Session, client: Client, kind: str, units: int, *, package_id: str = "") -> int:
    package = db.get(TariffPackage, package_id) if package_id else None
    if package:
        return max(0, int(package.price_kopeks or 0))
    return effective_price_kopeks(db, client, kind) * max(1, int(units or 1))


def debit_package_units(
    db: Session,
    client: Client,
    *,
    kind: str,
    units: int,
    amount_kopeks: int = 0,
    note: str = "",
    created_by: str = "admin",
    idempotency_key: str = "",
) -> BillingTransaction:
    if kind not in VALID_BILLING_KINDS:
        raise BillingError("Unknown billing kind")
    safe_units = int(units or 0)
    if safe_units <= 0:
        raise BillingError("Units must be positive")
    with _billing_client_lock(client.id):
        db.refresh(client)
        existing = _idempotent_transaction(db, idempotency_key, client_id=client.id, kind=kind, operation=OP_MANUAL_DEBIT, units=safe_units)
        if existing:
            return existing
        return _debit_package_units_locked(
            db,
            client,
            kind=kind,
            units=safe_units,
            amount_kopeks=amount_kopeks,
            note=note,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )


def _debit_package_units_locked(
    db: Session,
    client: Client,
    *,
    kind: str,
    units: int,
    amount_kopeks: int,
    note: str,
    created_by: str,
    idempotency_key: str,
) -> BillingTransaction:
    safe_units = max(1, int(units or 1))
    _initialize_legacy_balance_if_needed(db, client)
    explicit_amount = max(0, int(amount_kopeks or 0))
    amount = 0
    price_amount = effective_price_kopeks(db, client, kind) * safe_units
    if explicit_amount > 0 or price_amount > 0:
        debit_amount = explicit_amount or price_amount
        available_money = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))
        if available_money < debit_amount:
            raise BillingError(f"Недостаточно денег для списания: доступно {available_money / 100:.2f} ₽, нужно {debit_amount / 100:.2f} ₽")
        amount = debit_amount
        client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0) - amount)
    else:
        counter = balance_counter(db, client, kind)
        available = int(counter.get("available") or 0)
        if counter.get("unlimited"):
            raise BillingError("Manual debit is not supported for unlimited legacy balances")
        if available < safe_units:
            raise BillingError(f"Недостаточно доступных генераций для списания: доступно {available}, нужно {safe_units}")
    transaction = BillingTransaction(
        client_id=client.id,
        kind=kind,
        operation=OP_MANUAL_DEBIT,
        idempotency_key=_normalized_idempotency_key(idempotency_key),
        units=safe_units,
        amount_kopeks=amount,
        balance_after_kopeks=max(0, int(client.money_balance_kopeks or 0)),
        reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
        note=note or "Ручное списание с баланса",
        created_by=created_by,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def list_tariffs(db: Session, *, active_only: bool = False) -> list[TariffPackage]:
    query = db.query(TariffPackage)
    if active_only:
        query = query.filter(TariffPackage.is_active.is_(True))
    return query.order_by(TariffPackage.kind.asc(), TariffPackage.sort_order.asc(), TariffPackage.units.asc()).all()


def tariff_to_dict(package: TariffPackage) -> dict:
    return {
        "id": package.id,
        "kind": package.kind,
        "name": package.name,
        "units": package.units,
        "price_kopeks": package.price_kopeks,
        "price_rub": round(package.price_kopeks / 100, 2),
        "description": package.description,
        "is_active": package.is_active,
        "sort_order": package.sort_order,
        "created_at": package.created_at.isoformat() if package.created_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None,
    }


def transaction_to_dict(transaction: BillingTransaction) -> dict:
    return {
        "id": transaction.id,
        "client_id": transaction.client_id,
        "job_id": transaction.job_id,
        "package_id": transaction.package_id,
        "kind": transaction.kind,
        "kind_label": billing_kind_label(transaction.kind),
        "operation": transaction.operation,
        "idempotency_key": transaction.idempotency_key or "",
        "operation_label": operation_label(transaction.operation),
        "units": transaction.units,
        "amount_kopeks": transaction.amount_kopeks,
        "amount_rub": round(int(transaction.amount_kopeks or 0) / 100, 2),
        "balance_after_kopeks": transaction.balance_after_kopeks,
        "reserved_after_kopeks": transaction.reserved_after_kopeks,
        "note": transaction.note,
        "created_by": transaction.created_by,
        "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
    }


def operation_label(operation: str) -> str:
    labels = {
        OP_GRANT: "пополнение",
        OP_RESERVE: "резерв",
        OP_CHARGE: "списание",
        OP_RELEASE: "возврат резерва",
        OP_MANUAL_DEBIT: "ручное списание",
    }
    return labels.get(operation, operation)


def recent_billing_transactions(db: Session, client: Client, *, limit: int = 8) -> list[dict]:
    rows = (
        db.query(BillingTransaction)
        .filter(BillingTransaction.client_id == client.id)
        .order_by(BillingTransaction.created_at.desc())
        .limit(max(1, limit))
        .all()
    )
    return [transaction_to_dict(row) for row in rows]


def expire_stale_confirmations(db: Session, *, older_than: timedelta = timedelta(hours=24)) -> int:
    cutoff = now_utc() - older_than
    jobs = (
        db.query(Job)
        .filter(Job.status.in_([STATUS_AWAITING_CUSTOMER_CONFIRMATION, "partial"]))
        .filter(or_(Job.confirmation_kind.is_(None), Job.confirmation_kind == ""))
        .filter(Job.updated_at < cutoff)
        .all()
    )
    expired_jobs: list[Job] = []
    for job in jobs:
        if not job_has_unsettled_reservation(db, job):
            continue
        release_job_reservation(db, job, note="Резерв возвращён: клиент не подтвердил неполный отчёт за 24 часа")
        job.status = STATUS_CONFIRMATION_EXPIRED
        job.message = "Неполный отчёт не был скачан за 24 часа, списания нет"
        job.error = ""
        job.completed_at = now_utc()
        job.updated_at = now_utc()
        expired_jobs.append(job)
    if expired_jobs:
        db.commit()
    return len(expired_jobs)
