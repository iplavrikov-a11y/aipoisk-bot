from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from .billing import (
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    KIND_SUPPLIER_SEARCH_EXTRA,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    STATUS_CUSTOMER_DECLINED,
    STATUS_DELIVERY_EXPIRED,
    VALID_BILLING_KINDS,
    _billing_client_lock,
    _charge_job_kind_reservation_locked,
    _release_job_kind_reservation,
    job_reserved_amount_kopeks,
)
from .models import Job, UserJourneyEvent, now_utc, parse_json_dict

CONFIRMATION_KIND_PARTIAL_COUNT = "partial_count"
CONFIRMATION_KIND_REGISTRY_FALLBACK = "registry_fallback"

DECISION_PENDING = "pending"
DECISION_ACCEPTED = "accepted"
DECISION_DECLINED = "declined"
DECISION_EXPIRED = "expired"

DELIVERY_PENDING = "pending"
DELIVERY_DELIVERED = "delivered"
DELIVERY_EXPIRED = "expired"

MANIFEST_LOCKED = "locked_offer"
MANIFEST_FULL = "full"
MANIFEST_ANALYSIS_ONLY = "analysis_only"
MANIFEST_NONE = "none"

OFFER_DECISION_TTL = timedelta(hours=24)
OFFER_DELIVERY_TTL = timedelta(hours=24)
OFFER_DELIVERY_LEASE = timedelta(minutes=15)


class ResultOfferError(RuntimeError):
    code = "result_offer_error"


class ResultOfferConflict(ResultOfferError):
    code = "result_offer_conflict"


class ResultOfferGone(ResultOfferError):
    code = "result_offer_gone"


def publish_job_result_offer(
    db: Session,
    job: Job,
    *,
    kind: str,
    offered_at: datetime | None = None,
) -> None:
    """Publish a locked offer after every immutable output template is on disk."""
    if kind not in {CONFIRMATION_KIND_PARTIAL_COUNT, CONFIRMATION_KIND_REGISTRY_FALLBACK}:
        raise ValueError(f"Unsupported result offer kind: {kind}")
    now = _utc(offered_at or now_utc())
    job.confirmation_kind = kind
    job.confirmation_outcome = DECISION_PENDING
    job.confirmation_offered_at = now
    job.confirmation_expires_at = now + OFFER_DECISION_TTL
    job.confirmation_decided_at = None
    job.delivery_expires_at = None
    job.offer_delivery_outcome = ""
    job.offer_delivery_claim_token = ""
    job.offer_delivery_lease_expires_at = None
    job.offer_delivered_at = None
    job.offer_delivery_expired_at = None
    if kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
        job.active_output_manifest = MANIFEST_LOCKED
        job.active_output_manifest_version = int(job.active_output_manifest_version or 0) + 1
        job.active_entitlements_json = "[]"
        job.result_path = ""
    job.status = STATUS_AWAITING_CUSTOMER_CONFIRMATION
    job.updated_at = now
    if kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
        _add_offer_event(db, job, "registry_fallback_offered", channel=_job_channel(job), outcome="created")


def accept_job_result_offer(db: Session, job: Job, *, channel: str) -> Job:
    with _job_billing_lock(job):
        db.refresh(job)
        _bootstrap_legacy_offer(job)
        now = _utc(now_utc())
        if job.confirmation_outcome != DECISION_PENDING or job.status != STATUS_AWAITING_CUSTOMER_CONFIRMATION:
            raise ResultOfferConflict("Подтверждение уже не актуально.")
        if _deadline_passed(job.confirmation_expires_at, now):
            _expire_pending_decision_locked(db, job, now=now)
            db.commit()
            raise ResultOfferGone("Срок подтверждения результата истёк.")
        if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
            _activate_manifest(job, MANIFEST_FULL)
        job.confirmation_outcome = DECISION_ACCEPTED
        job.confirmation_decided_at = now
        job.delivery_expires_at = now + OFFER_DELIVERY_TTL
        job.offer_delivery_outcome = DELIVERY_PENDING
        job.offer_delivery_claim_token = ""
        job.offer_delivery_lease_expires_at = None
        job.status = "partial"
        job.message = (
            "Клиент принял результат без подтверждения реестра"
            if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK
            else "Клиент принял неполный отчёт"
        )
        job.error = ""
        job.updated_at = now
        if job.completed_at is None:
            job.completed_at = now
        if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
            _add_offer_event(db, job, "registry_fallback_accepted", channel=channel, outcome="accepted")
        db.commit()
        db.refresh(job)
        return job


def decline_job_result_offer(db: Session, job: Job, *, channel: str) -> Job:
    with _job_billing_lock(job):
        db.refresh(job)
        _bootstrap_legacy_offer(job)
        now = _utc(now_utc())
        if job.confirmation_outcome != DECISION_PENDING or job.status != STATUS_AWAITING_CUSTOMER_CONFIRMATION:
            raise ResultOfferConflict("Подтверждение уже не актуально.")
        if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
            _settle_registry_fallback_without_supplier_locked(
                db,
                job,
                now=now,
                status_for_standalone=STATUS_CUSTOMER_DECLINED,
                combined_message="Анализ готов; вариант поставщиков без подтверждения реестра отклонён",
            )
        else:
            _release_all_locked(db, job, note="Резерв возвращён: клиент отказался от неполного отчёта")
            job.status = STATUS_CUSTOMER_DECLINED
            job.result_path = ""
        job.confirmation_outcome = DECISION_DECLINED
        job.confirmation_decided_at = now
        job.message = (
            "Клиент отказался от результата без подтверждения реестра; списания за поиск поставщиков нет"
            if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK and job.mode == "supplier_search"
            else job.message or "Клиент отказался от неполного отчёта"
        )
        job.error = ""
        job.completed_at = now
        job.updated_at = now
        if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
            _add_offer_event(db, job, "registry_fallback_declined", channel=channel, outcome="declined")
        db.commit()
        db.refresh(job)
        return job


def claim_job_result_offer_delivery(db: Session, job: Job, *, channel: str) -> str:
    """Claim the supplier/full delivery. An empty token means it was already delivered."""
    with _job_billing_lock(job):
        db.refresh(job)
        now = _utc(now_utc())
        if job.confirmation_outcome != DECISION_ACCEPTED:
            raise ResultOfferGone("Результат не принят клиентом.")
        if job.offer_delivery_outcome == DELIVERY_DELIVERED:
            return ""
        if job.offer_delivery_outcome != DELIVERY_PENDING:
            raise ResultOfferGone("Срок выдачи результата истёк.")
        if _deadline_passed(job.delivery_expires_at, now):
            live_lease = bool(job.offer_delivery_claim_token) and not _deadline_passed(job.offer_delivery_lease_expires_at, now)
            if not live_lease:
                _expire_accepted_delivery_locked(db, job, now=now)
                db.commit()
                raise ResultOfferGone("Срок выдачи результата истёк.")
        if job.offer_delivery_claim_token and not _deadline_passed(job.offer_delivery_lease_expires_at, now):
            raise ResultOfferConflict("Результат уже отправляется в другом канале.")
        token = secrets.token_hex(24)
        job.offer_delivery_claim_token = token
        job.offer_delivery_lease_expires_at = now + OFFER_DELIVERY_LEASE
        job.updated_at = now
        db.commit()
        return token


def complete_job_result_offer_delivery(
    db: Session,
    job: Job,
    token: str,
    *,
    billing_kinds: Iterable[str] | None = None,
    channel: str,
    note: str = "Результат отправлен клиенту",
) -> bool:
    with _job_billing_lock(job):
        db.refresh(job)
        if job.offer_delivery_outcome == DELIVERY_DELIVERED:
            return False
        if job.offer_delivery_outcome != DELIVERY_PENDING:
            raise ResultOfferGone("Выдача результата уже недоступна.")
        if not token or token != job.offer_delivery_claim_token:
            raise ResultOfferConflict("Право на выдачу результата устарело.")
        kinds = list(billing_kinds) if billing_kinds is not None else active_result_offer_entitlements(job)
        if not kinds:
            kinds = _default_job_entitlements(job)
        for kind in dict.fromkeys(kinds):
            if kind in VALID_BILLING_KINDS:
                _charge_job_kind_reservation_locked(db, job, kind, note=note)
        now = _utc(now_utc())
        job.offer_delivery_outcome = DELIVERY_DELIVERED
        job.offer_delivered_at = now
        job.offer_delivery_claim_token = ""
        job.offer_delivery_lease_expires_at = None
        job.updated_at = now
        if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
            _add_offer_event(db, job, "registry_fallback_delivered", channel=channel, outcome="delivered")
        db.commit()
        return True


def fail_job_result_offer_delivery(db: Session, job: Job, token: str) -> None:
    if not token:
        return
    with _job_billing_lock(job):
        db.refresh(job)
        if job.offer_delivery_outcome != DELIVERY_PENDING or job.offer_delivery_claim_token != token:
            return
        job.offer_delivery_claim_token = ""
        job.offer_delivery_lease_expires_at = None
        job.updated_at = now_utc()
        db.commit()


def expire_result_offers(db: Session, *, current_time: datetime | None = None) -> int:
    now = _utc(current_time or now_utc())
    jobs = (
        db.query(Job)
        .filter(Job.confirmation_kind.in_([CONFIRMATION_KIND_PARTIAL_COUNT, CONFIRMATION_KIND_REGISTRY_FALLBACK]))
        .filter(
            (Job.confirmation_outcome == DECISION_PENDING)
            | ((Job.confirmation_outcome == DECISION_ACCEPTED) & (Job.offer_delivery_outcome == DELIVERY_PENDING))
        )
        .all()
    )
    expired = 0
    for candidate in jobs:
        with _job_billing_lock(candidate):
            job = db.get(Job, candidate.id)
            if not job:
                continue
            db.refresh(job)
            if job.confirmation_outcome == DECISION_PENDING and _deadline_passed(job.confirmation_expires_at, now):
                _expire_pending_decision_locked(db, job, now=now)
                db.commit()
                expired += 1
                continue
            if (
                job.confirmation_outcome == DECISION_ACCEPTED
                and job.offer_delivery_outcome == DELIVERY_PENDING
                and _deadline_passed(job.delivery_expires_at, now)
            ):
                live_lease = bool(job.offer_delivery_claim_token) and not _deadline_passed(job.offer_delivery_lease_expires_at, now)
                if live_lease:
                    continue
                _expire_accepted_delivery_locked(db, job, now=now)
                db.commit()
                expired += 1
    return expired


def active_result_offer_entitlements(job: Job) -> list[str]:
    try:
        payload = json.loads(str(job.active_entitlements_json or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return list(
        dict.fromkeys(
            _normalize_job_billing_kind(job, str(item))
            for item in payload
            if str(item) in VALID_BILLING_KINDS
        )
    )


def active_result_offer_output_items(job: Job, _evidence: dict | None = None) -> list[dict] | None:
    """Return None for legacy jobs, and the DB-selected immutable template for offers."""
    if str(job.confirmation_kind or "") != CONFIRMATION_KIND_REGISTRY_FALLBACK:
        return None
    manifest_name = str(job.active_output_manifest or "")
    if manifest_name in {"", MANIFEST_LOCKED, MANIFEST_NONE}:
        return []
    manifest = _manifest_template(job, manifest_name, _evidence=_evidence)
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, list):
        return []
    items = [dict(item) for item in files if isinstance(item, dict)]
    for item in items:
        kind = str(item.get("billing_kind") or "")
        if kind in VALID_BILLING_KINDS:
            item["billing_kind"] = _normalize_job_billing_kind(job, kind)
    return items


def billing_kinds_for_result_delivery(job: Job, file_kind: str | None = None) -> list[str] | None:
    """Return None for legacy all-kind charging; otherwise the selected artifact entitlements."""
    if not str(job.confirmation_kind or ""):
        return None
    if not file_kind:
        return active_result_offer_entitlements(job)
    items = active_result_offer_output_items(job) or []
    return list(
        dict.fromkeys(
            str(item.get("billing_kind") or "")
            for item in items
            if str(item.get("kind") or "") == str(file_kind) and str(item.get("billing_kind") or "") in VALID_BILLING_KINDS
        )
    )


def result_offer_to_dict(db: Session | None, job: Job, _evidence: dict | None = None) -> dict | None:
    kind = str(job.confirmation_kind or "")
    if not kind:
        return None
    full_manifest = _manifest_template(job, MANIFEST_FULL, _evidence=_evidence)
    offered_entitlements = [
        _normalize_job_billing_kind(job, item)
        for item in _manifest_entitlements(full_manifest)
    ]
    if not offered_entitlements:
        offered_entitlements = _default_job_entitlements(job)
    primary_kind = offered_entitlements[0] if offered_entitlements else KIND_SUPPLIER_SEARCH
    items = [
        {
            "billing_kind": item,
            "units": 1,
            "amount_kopeks": job_reserved_amount_kopeks(db, job, item),
        }
        for item in dict.fromkeys(offered_entitlements)
    ]
    amount = sum(item["amount_kopeks"] for item in items)
    charge = {
        "billing_kind": primary_kind,
        "units": 1,
        "amount_kopeks": amount,
        "currency": "RUB",
        "items": items,
    }
    now = _utc(now_utc())
    pending = job.confirmation_outcome == DECISION_PENDING and not _deadline_passed(job.confirmation_expires_at, now)
    return {
        "kind": kind,
        "registry_verified_count": 0 if kind == CONFIRMATION_KIND_REGISTRY_FALLBACK else int(job.verified_count or 0),
        "alternative_verified_count": int(job.verified_count or 0),
        "decision_outcome": str(job.confirmation_outcome or ""),
        "decision_offered_at": _iso(job.confirmation_offered_at),
        "decision_expires_at": _iso(job.confirmation_expires_at),
        "decision_decided_at": _iso(job.confirmation_decided_at),
        "delivery_outcome": str(job.offer_delivery_outcome or ""),
        "delivery_expires_at": _iso(job.delivery_expires_at),
        "delivered_at": _iso(job.offer_delivered_at),
        "delivery_expired_at": _iso(job.offer_delivery_expired_at),
        "active_manifest": str(job.active_output_manifest or ""),
        "active_manifest_version": int(job.active_output_manifest_version or 0),
        "charge": charge,
        "charge_amount_kopeks": amount,
        "charge_amount_rub": round(amount / 100, 2),
        "can_accept": bool(pending),
        "can_decline": bool(pending),
    }


def _expire_pending_decision_locked(db: Session, job: Job, *, now: datetime) -> None:
    if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
        _settle_registry_fallback_without_supplier_locked(
            db,
            job,
            now=now,
            status_for_standalone=STATUS_CONFIRMATION_EXPIRED,
            combined_message="Анализ готов; срок решения по поставщикам без подтверждения реестра истёк",
        )
        _add_offer_event(db, job, "registry_fallback_expired", channel=_job_channel(job), outcome="expired")
    else:
        _release_all_locked(db, job, note="Резерв возвращён: клиент не подтвердил неполный отчёт за 24 часа")
        job.status = STATUS_CONFIRMATION_EXPIRED
        job.result_path = ""
        job.message = "Неполный отчёт не был подтверждён за 24 часа, списания нет"
    job.confirmation_outcome = DECISION_EXPIRED
    job.confirmation_decided_at = now
    job.error = ""
    job.completed_at = now
    job.updated_at = now


def _expire_accepted_delivery_locked(db: Session, job: Job, *, now: datetime) -> None:
    if job.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK:
        _settle_registry_fallback_without_supplier_locked(
            db,
            job,
            now=now,
            status_for_standalone=STATUS_DELIVERY_EXPIRED,
            combined_message="Анализ готов; срок выдачи варианта поставщиков без подтверждения реестра истёк",
        )
        _add_offer_event(db, job, "registry_fallback_delivery_expired", channel=_job_channel(job), outcome="expired")
    else:
        _release_all_locked(db, job, note="Резерв возвращён: принятый неполный отчёт не выдан за 24 часа")
        job.status = STATUS_DELIVERY_EXPIRED
        job.result_path = ""
        job.message = "Срок выдачи принятого отчёта истёк; списания нет"
    job.offer_delivery_outcome = DELIVERY_EXPIRED
    job.offer_delivery_expired_at = now
    job.offer_delivery_claim_token = ""
    job.offer_delivery_lease_expires_at = None
    job.error = ""
    job.completed_at = now
    job.updated_at = now


def _settle_registry_fallback_without_supplier_locked(
    db: Session,
    job: Job,
    *,
    now: datetime,
    status_for_standalone: str,
    combined_message: str,
) -> None:
    _release_job_kind_reservation(
        db,
        job,
        _supplier_search_billing_kind(job),
        note="Резерв поставщиков возвращён: вариант без подтверждения реестра не выдан",
    )
    if job.mode == "analysis_and_suppliers":
        _activate_manifest(job, MANIFEST_ANALYSIS_ONLY)
        job.status = "needs_review" if _analysis_has_warning(job) else "completed"
        job.message = combined_message
    else:
        _activate_manifest(job, MANIFEST_NONE)
        job.status = status_for_standalone
        job.message = "Результат без подтверждения реестра не выдан; списания нет"
    job.updated_at = now


def _release_all_locked(db: Session, job: Job, *, note: str) -> None:
    for kind in VALID_BILLING_KINDS:
        _release_job_kind_reservation(db, job, kind, note=note)


def _activate_manifest(job: Job, name: str) -> None:
    if name == MANIFEST_NONE:
        job.active_output_manifest = MANIFEST_NONE
        job.active_output_manifest_version = int(job.active_output_manifest_version or 0) + 1
        job.active_entitlements_json = "[]"
        job.result_path = ""
        return
    manifest = _manifest_template(job, name)
    if not manifest:
        raise ResultOfferConflict(f"Шаблон выдачи {name} не сформирован.")
    result_path = str(manifest.get("archive_path") or "").strip()
    if not result_path:
        files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
        result_path = str(files[0].get("path") or "").strip() if files and isinstance(files[0], dict) else ""
    if not result_path or not Path(result_path).exists():
        raise ResultOfferConflict("Файл результата не сформирован.")
    job.active_output_manifest = name
    job.active_output_manifest_version = int(job.active_output_manifest_version or 0) + 1
    job.active_entitlements_json = json.dumps(
        [_normalize_job_billing_kind(job, item) for item in _manifest_entitlements(manifest)],
        ensure_ascii=False,
    )
    job.result_path = result_path


def _manifest_template(job: Job, name: str, _evidence: dict | None = None) -> dict:
    payload = _read_evidence(job, _evidence=_evidence)
    manifests = payload.get("output_manifests") if isinstance(payload, dict) else None
    manifest = manifests.get(name) if isinstance(manifests, dict) else None
    return dict(manifest) if isinstance(manifest, dict) else {}


def _manifest_entitlements(manifest: dict) -> list[str]:
    raw = manifest.get("entitlements")
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item) in VALID_BILLING_KINDS]
    files = manifest.get("files")
    if not isinstance(files, list):
        return []
    return list(
        dict.fromkeys(
            str(item.get("billing_kind") or "")
            for item in files
            if isinstance(item, dict) and str(item.get("billing_kind") or "") in VALID_BILLING_KINDS
        )
    )


def _default_job_entitlements(job: Job) -> list[str]:
    if job.mode == "supplier_search":
        return [_supplier_search_billing_kind(job)]
    if job.mode == "procurement_report":
        return [KIND_PROCUREMENT_REPORT]
    if job.mode == "analysis_and_suppliers":
        return [KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH]
    return []


def _supplier_search_billing_kind(job: Job) -> str:
    if (
        str(job.mode or "") == "supplier_search"
        and str(job.supplier_search_run_type or "") == "additional"
    ):
        return KIND_SUPPLIER_SEARCH_EXTRA
    return KIND_SUPPLIER_SEARCH


def _normalize_job_billing_kind(job: Job, kind: str) -> str:
    if kind == KIND_SUPPLIER_SEARCH:
        return _supplier_search_billing_kind(job)
    return kind


def _read_evidence(job: Job, _evidence: dict | None = None) -> dict:
    if _evidence is not None:
        return _evidence
    path = Path(str(job.evidence_path or ""))
    if not path.exists():
        return {}
    try:
        return parse_json_dict(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _analysis_has_warning(job: Job) -> bool:
    payload = _read_evidence(job)
    report = payload.get("report") if isinstance(payload, dict) else None
    return bool(report.get("warning")) if isinstance(report, dict) else False


def _bootstrap_legacy_offer(job: Job) -> None:
    if job.confirmation_outcome:
        return
    now = _utc(now_utc())
    job.confirmation_kind = job.confirmation_kind or CONFIRMATION_KIND_PARTIAL_COUNT
    job.confirmation_outcome = DECISION_PENDING
    job.confirmation_offered_at = _utc(job.updated_at or now)
    job.confirmation_expires_at = _utc(job.updated_at or now) + OFFER_DECISION_TTL


def _add_offer_event(db: Session, job: Job, event_name: str, *, channel: str, outcome: str) -> None:
    existing = (
        db.query(UserJourneyEvent.id)
        .filter(
            UserJourneyEvent.client_id == job.client_id,
            UserJourneyEvent.actor_ref == job.id,
            UserJourneyEvent.event_name == event_name,
        )
        .first()
    )
    if existing:
        return
    db.add(
        UserJourneyEvent(
            client_id=job.client_id,
            channel=channel if channel in {"web", "telegram"} else _job_channel(job),
            actor_ref=job.id,
            event_name=event_name,
            mode=job.mode,
            outcome=outcome,
            reason_code="registry_fallback",
        )
    )


def _job_channel(job: Job) -> str:
    creator = str(job.created_by_telegram_id or "")
    return "web" if creator.startswith("web:") else "telegram"


class _NullLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def _job_billing_lock(job: Job):
    return _billing_client_lock(job.client_id) if job.client_id else _NullLock()


def _deadline_passed(value: datetime | None, now: datetime) -> bool:
    return value is not None and _utc(value) <= now


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return _utc(value).isoformat() if value else None
