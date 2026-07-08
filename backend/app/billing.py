from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from sqlalchemy import and_, func, not_, or_
from sqlalchemy.orm import Session

from .models import BillingTransaction, Client, ClientTariffOverride, Job, TariffPackage, now_utc

KIND_SUPPLIER_SEARCH = "supplier_search"
KIND_PROCUREMENT_REPORT = "procurement_report"
KIND_SUPPLIER_SEARCH_EXTRA = "supplier_search_extra"
KIND_MONEY = "money"
VALID_BILLING_KINDS = {KIND_SUPPLIER_SEARCH, KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH_EXTRA}
SUPPLIER_SEARCH_EXTRA_DEFAULT_PERCENT = 50

OP_GRANT = "grant"
OP_RESERVE = "reserve"
OP_CHARGE = "charge"
OP_RELEASE = "release"
OP_MANUAL_DEBIT = "manual_debit"

STATUS_AWAITING_CUSTOMER_CONFIRMATION = "awaiting_customer_confirmation"
STATUS_CUSTOMER_DECLINED = "customer_declined"
STATUS_CONFIRMATION_EXPIRED = "confirmation_expired"

LOW_BALANCE_THRESHOLD = 1

MODE_SUPPLIER_SEARCH = "supplier_search"
MODE_PROCUREMENT_REPORT = "procurement_report"
MODE_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"

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


def billing_kind_label(kind: str) -> str:
    if kind == KIND_MONEY:
        return "Баланс"
    if kind == KIND_PROCUREMENT_REPORT:
        return "Анализ документации"
    if kind == KIND_SUPPLIER_SEARCH_EXTRA:
        return "Добор поставщиков"
    return "Поставщики"


def requested_billing_units(mode: str, *, supplier_search_count: int = 1) -> dict[str, int]:
    supplier_units = max(1, int(supplier_search_count or 1))
    if mode == MODE_SUPPLIER_SEARCH:
        return {KIND_SUPPLIER_SEARCH: supplier_units, KIND_PROCUREMENT_REPORT: 0, KIND_SUPPLIER_SEARCH_EXTRA: 0}
    if mode == MODE_PROCUREMENT_REPORT:
        return {KIND_SUPPLIER_SEARCH: 0, KIND_PROCUREMENT_REPORT: 1, KIND_SUPPLIER_SEARCH_EXTRA: 0}
    if mode == MODE_ANALYSIS_AND_SUPPLIERS:
        return {KIND_SUPPLIER_SEARCH: 1, KIND_PROCUREMENT_REPORT: 1, KIND_SUPPLIER_SEARCH_EXTRA: 0}
    return {KIND_SUPPLIER_SEARCH: 0, KIND_PROCUREMENT_REPORT: 0, KIND_SUPPLIER_SEARCH_EXTRA: 0}


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
        "money": money,
        "effective_prices": {
            kind: effective_price_to_dict(db, client, kind)
            for kind in (KIND_SUPPLIER_SEARCH, KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH_EXTRA)
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
    return 0


def _explicit_effective_price_kopeks(db: Session, client: Client | None, kind: str) -> int | None:
    if client:
        override = _client_tariff_override(db, client, kind)
        if override:
            if not override.is_enabled:
                return 0
            return max(0, int(override.price_kopeks or 0))
    package = (
        db.query(TariffPackage)
        .filter(TariffPackage.kind == kind)
        .filter(TariffPackage.is_active.is_(True))
        .order_by(TariffPackage.sort_order.asc(), TariffPackage.price_kopeks.asc())
        .first()
    )
    if not package:
        return None
    units = max(1, int(package.units or 1))
    return max(0, round(int(package.price_kopeks or 0) / units))


def _default_supplier_search_extra_price_kopeks(db: Session, client: Client | None) -> int:
    supplier_price = effective_price_kopeks(db, client, KIND_SUPPLIER_SEARCH)
    return max(0, round(supplier_price * SUPPLIER_SEARCH_EXTRA_DEFAULT_PERCENT / 100))


def _client_tariff_override(db: Session, client: Client, kind: str) -> ClientTariffOverride | None:
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
        for kind in (KIND_SUPPLIER_SEARCH, KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH_EXTRA)
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
    elif kind == KIND_SUPPLIER_SEARCH_EXTRA:
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
    return bool(client and client.is_trial and not client_has_paid_grants(db, client))


def access_error_for_units(db: Session, client: Client, units: dict[str, int]) -> str:
    for kind, count in units.items():
        if count <= 0:
            continue
        counter = _access_counter(db, client, kind)
        if counter["unlimited"]:
            continue
        if int(counter["available"] or 0) < count:
            return (
                f"Недостаточно генераций: {billing_kind_label(kind)}. "
                f"Доступно {counter['available']}, нужно {count}. "
                "Откройте «Тарифы и оплата», чтобы пополнить пакет."
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
    _initialize_legacy_balance_if_needed(db, client, exclude_job_id=job.id)
    units = resolve_requested_billing_kinds(
        db,
        client,
        job.mode,
        supplier_search_count=supplier_search_count,
        supplier_search_run_type=getattr(job, "supplier_search_run_type", "initial"),
    )
    error = access_error_for_units(db, client, units)
    if error:
        raise BillingError(error)
    for kind, count in units.items():
        if count <= 0 or _job_has_operation(db, job.id, kind, OP_RESERVE):
            continue
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
    if _kind_money_available_for_reservation(db, client, kind) < amount:
        return 0
    available_total = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))
    if available_total < amount:
        return 0
    return amount


def _kind_money_available_for_reservation(db: Session, client: Client, kind: str) -> int:
    if kind == KIND_SUPPLIER_SEARCH_EXTRA and _supplier_search_extra_uses_supplier_access(db, client):
        return max(
            _kind_money_available_kopeks(db, client.id, KIND_SUPPLIER_SEARCH_EXTRA),
            _kind_money_available_kopeks(db, client.id, KIND_SUPPLIER_SEARCH),
        )
    return _kind_money_available_kopeks(db, client.id, kind)


def _kind_money_available_kopeks(db: Session, client_id: str, kind: str) -> int:
    rows = (
        db.query(BillingTransaction.operation, func.coalesce(func.sum(BillingTransaction.amount_kopeks), 0))
        .filter(BillingTransaction.client_id == client_id)
        .filter(BillingTransaction.kind == kind)
        .filter(BillingTransaction.amount_kopeks > 0)
        .group_by(BillingTransaction.operation)
        .all()
    )
    totals = {operation: int(total or 0) for operation, total in rows}
    granted = totals.get(OP_GRANT, 0)
    manual_debited = totals.get(OP_MANUAL_DEBIT, 0)
    reserved_total = totals.get(OP_RESERVE, 0)
    released = totals.get(OP_RELEASE, 0)
    return max(0, granted + released - reserved_total - manual_debited)


def charge_job_reservation(db: Session, job: Job, *, note: str = "Результат отправлен клиенту") -> None:
    if not job.client_id:
        return
    client = db.get(Client, job.client_id)
    for kind in VALID_BILLING_KINDS:
        remaining = _job_reserved_remaining(db, job.id, kind)
        remaining_amount = _job_reserved_amount_remaining(db, job.id, kind)
        if (remaining <= 0 and remaining_amount <= 0) or _job_has_operation(db, job.id, kind, OP_CHARGE):
            continue
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
    db.commit()


def job_has_unsettled_reservation(db: Session, job: Job) -> bool:
    if not job.client_id:
        return False
    return any(
        _job_reserved_remaining(db, job.id, kind) > 0 or _job_reserved_amount_remaining(db, job.id, kind) > 0
        for kind in VALID_BILLING_KINDS
    )


def release_job_reservation(db: Session, job: Job, *, note: str = "Резерв возвращён") -> None:
    if not job.client_id:
        return
    for kind in VALID_BILLING_KINDS:
        _release_job_kind_reservation(db, job, kind, note=note)
    db.commit()


def release_job_kind_reservation(db: Session, job: Job, kind: str, *, note: str = "Резерв возвращён") -> None:
    if not job.client_id:
        return
    _release_job_kind_reservation(db, job, kind, note=note)
    db.commit()


def _release_job_kind_reservation(db: Session, job: Job, kind: str, *, note: str) -> None:
    remaining = _job_reserved_remaining(db, job.id, kind)
    remaining_amount = _job_reserved_amount_remaining(db, job.id, kind)
    if remaining <= 0 and remaining_amount <= 0:
        return
    client = db.get(Client, job.client_id) if job.client_id else None
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
) -> BillingTransaction:
    if kind not in VALID_BILLING_KINDS:
        raise BillingError("Unknown billing kind")
    safe_units = int(units or 0)
    if safe_units <= 0:
        raise BillingError("Units must be positive")
    amount = max(0, int(amount_kopeks or 0)) or _grant_amount_kopeks(db, client, kind, safe_units, package_id=package_id)
    if amount > 0:
        client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0)) + amount
    transaction = BillingTransaction(
        client_id=client.id,
        package_id=package_id,
        kind=kind,
        operation=OP_GRANT,
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
) -> BillingTransaction:
    amount = max(0, int(amount_kopeks or 0))
    if amount <= 0:
        raise BillingError("Amount must be positive")
    client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0)) + amount
    transaction = BillingTransaction(
        client_id=client.id,
        kind=KIND_MONEY,
        operation=OP_GRANT,
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
) -> BillingTransaction:
    amount = max(0, int(amount_kopeks or 0))
    if amount <= 0:
        raise BillingError("Amount must be positive")
    available_money = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))
    if available_money < amount:
        raise BillingError(f"Недостаточно денег для списания: доступно {available_money / 100:.2f} ₽, нужно {amount / 100:.2f} ₽")
    client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0) - amount)
    transaction = BillingTransaction(
        client_id=client.id,
        kind=KIND_MONEY,
        operation=OP_MANUAL_DEBIT,
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
    supplier_search_units: int,
    procurement_report_units: int,
    note: str = "Стартовый баланс триала",
) -> None:
    db.flush()
    for kind, units in (
        (KIND_SUPPLIER_SEARCH, supplier_search_units),
        (KIND_PROCUREMENT_REPORT, procurement_report_units),
    ):
        safe_units = max(0, int(units or 0))
        if safe_units <= 0 or _has_billing_transactions(db, client.id, kind):
            continue
        amount = effective_price_kopeks(db, client, kind) * safe_units
        if amount > 0:
            client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0)) + amount
        db.add(
            BillingTransaction(
                client_id=client.id,
                kind=kind,
                operation=OP_GRANT,
                units=safe_units,
                amount_kopeks=amount,
                balance_after_kopeks=max(0, int(client.money_balance_kopeks or 0)),
                reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
                note=note,
                created_by="system",
            )
        )


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
) -> BillingTransaction:
    if kind not in VALID_BILLING_KINDS:
        raise BillingError("Unknown billing kind")
    safe_units = int(units or 0)
    if safe_units <= 0:
        raise BillingError("Units must be positive")
    _initialize_legacy_balance_if_needed(db, client)
    explicit_amount = max(0, int(amount_kopeks or 0))
    amount = 0
    if explicit_amount > 0:
        available_money = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))
        if available_money < explicit_amount:
            raise BillingError(f"Недостаточно денег для списания: доступно {available_money / 100:.2f} ₽, нужно {explicit_amount / 100:.2f} ₽")
        amount = explicit_amount
        client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0) - amount)
    else:
        counter = balance_counter(db, client, kind)
        available = int(counter.get("available") or 0)
        if counter.get("unlimited"):
            raise BillingError("Manual debit is not supported for unlimited legacy balances")
        if available < safe_units:
            raise BillingError(f"Недостаточно доступных генераций для списания: доступно {available}, нужно {safe_units}")
        requested_amount = effective_price_kopeks(db, client, kind) * safe_units
        if requested_amount > 0 and _kind_money_available_kopeks(db, client.id, kind) >= requested_amount:
            available_money = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))
            if available_money >= requested_amount:
                amount = requested_amount
                client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0) - amount)
    transaction = BillingTransaction(
        client_id=client.id,
        kind=kind,
        operation=OP_MANUAL_DEBIT,
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
        .filter(Job.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION)
        .filter(Job.updated_at < cutoff)
        .all()
    )
    for job in jobs:
        release_job_reservation(db, job, note="Резерв возвращён: клиент не подтвердил неполный отчёт за 24 часа")
        job.status = STATUS_CONFIRMATION_EXPIRED
        job.message = "Отчёт не был подтверждён за 24 часа, списания нет"
        job.error = ""
        job.completed_at = now_utc()
        job.updated_at = now_utc()
    if jobs:
        db.commit()
    return len(jobs)
