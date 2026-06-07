from __future__ import annotations

from datetime import timedelta

from sqlalchemy import and_, func, not_, or_
from sqlalchemy.orm import Session

from .models import BillingTransaction, Client, Job, TariffPackage, now_utc

KIND_SUPPLIER_SEARCH = "supplier_search"
KIND_PROCUREMENT_REPORT = "procurement_report"
VALID_BILLING_KINDS = {KIND_SUPPLIER_SEARCH, KIND_PROCUREMENT_REPORT}

OP_GRANT = "grant"
OP_RESERVE = "reserve"
OP_CHARGE = "charge"
OP_RELEASE = "release"

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
    if kind == KIND_PROCUREMENT_REPORT:
        return "Анализ документации"
    return "Поставщики"


def requested_billing_units(mode: str, *, supplier_search_count: int = 1) -> dict[str, int]:
    supplier_units = max(1, int(supplier_search_count or 1))
    if mode == MODE_SUPPLIER_SEARCH:
        return {KIND_SUPPLIER_SEARCH: supplier_units, KIND_PROCUREMENT_REPORT: 0}
    if mode == MODE_PROCUREMENT_REPORT:
        return {KIND_SUPPLIER_SEARCH: 0, KIND_PROCUREMENT_REPORT: 1}
    if mode == MODE_ANALYSIS_AND_SUPPLIERS:
        return {KIND_SUPPLIER_SEARCH: 1, KIND_PROCUREMENT_REPORT: 1}
    return {KIND_SUPPLIER_SEARCH: 0, KIND_PROCUREMENT_REPORT: 0}


def client_balance_summary(db: Session, client: Client) -> dict:
    return {
        KIND_SUPPLIER_SEARCH: balance_counter(db, client, KIND_SUPPLIER_SEARCH),
        KIND_PROCUREMENT_REPORT: balance_counter(db, client, KIND_PROCUREMENT_REPORT),
    }


def balance_counter(db: Session, client: Client, kind: str) -> dict:
    if _has_billing_transactions(db, client.id, kind):
        counter = _ledger_counter(db, client.id, kind)
    else:
        counter = _legacy_counter(db, client, kind)
    counter["kind"] = kind
    counter["label"] = billing_kind_label(kind)
    counter["low"] = not counter["unlimited"] and counter["available"] <= LOW_BALANCE_THRESHOLD
    return counter


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
    reserved_total = totals.get(OP_RESERVE, 0)
    released = totals.get(OP_RELEASE, 0)
    charged = totals.get(OP_CHARGE, 0)
    reserved = max(0, reserved_total - released - charged)
    available = max(0, granted + released - reserved_total)
    return {
        "granted": granted,
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
    else:
        limit = int(client.monthly_supplier_search_limit or 0)
        used = supplier_used
    unlimited = limit < 0
    available = None if unlimited else max(0, limit - used)
    return {
        "granted": limit,
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


def access_error_for_units(db: Session, client: Client, units: dict[str, int]) -> str:
    for kind, count in units.items():
        if count <= 0:
            continue
        counter = balance_counter(db, client, kind)
        if counter["unlimited"]:
            continue
        if int(counter["available"] or 0) < count:
            return (
                f"Недостаточно генераций: {billing_kind_label(kind)}. "
                f"Доступно {counter['available']}, нужно {count}. "
                "Откройте «Тарифы и оплата», чтобы пополнить пакет."
            )
    return ""


def reserve_job_units(db: Session, client: Client, job: Job, *, supplier_search_count: int = 1) -> None:
    _initialize_legacy_balance_if_needed(db, client, exclude_job_id=job.id)
    units = requested_billing_units(job.mode, supplier_search_count=supplier_search_count)
    error = access_error_for_units(db, client, units)
    if error:
        raise BillingError(error)
    for kind, count in units.items():
        if count <= 0 or _job_has_operation(db, job.id, kind, OP_RESERVE):
            continue
        db.add(
            BillingTransaction(
                client_id=client.id,
                job_id=job.id,
                kind=kind,
                operation=OP_RESERVE,
                units=count,
                note="Резерв перед запуском задачи",
                created_by="system",
            )
        )
    db.commit()


def charge_job_reservation(db: Session, job: Job, *, note: str = "Результат отправлен клиенту") -> None:
    if not job.client_id:
        return
    for kind in VALID_BILLING_KINDS:
        remaining = _job_reserved_remaining(db, job.id, kind)
        if remaining <= 0 or _job_has_operation(db, job.id, kind, OP_CHARGE):
            continue
        db.add(
            BillingTransaction(
                client_id=job.client_id,
                job_id=job.id,
                kind=kind,
                operation=OP_CHARGE,
                units=remaining,
                note=note,
                created_by="system",
            )
        )
    db.commit()


def job_has_unsettled_reservation(db: Session, job: Job) -> bool:
    if not job.client_id:
        return False
    return any(_job_reserved_remaining(db, job.id, kind) > 0 for kind in VALID_BILLING_KINDS)


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
    if remaining <= 0:
        return
    db.add(
        BillingTransaction(
            client_id=job.client_id,
            job_id=job.id,
            kind=kind,
            operation=OP_RELEASE,
            units=remaining,
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
    package_id: str = "",
    note: str = "",
    created_by: str = "admin",
) -> BillingTransaction:
    if kind not in VALID_BILLING_KINDS:
        raise BillingError("Unknown billing kind")
    safe_units = int(units or 0)
    if safe_units <= 0:
        raise BillingError("Units must be positive")
    transaction = BillingTransaction(
        client_id=client.id,
        package_id=package_id,
        kind=kind,
        operation=OP_GRANT,
        units=safe_units,
        note=note or "Ручное пополнение пакета",
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
