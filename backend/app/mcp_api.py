from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from .ai import get_model_selection
from .config import config
from .db import db_session
from .billing import (
    BillingError,
    BillingTransaction,
    OP_CHARGE,
    OP_RELEASE,
    OP_RESERVE,
    VALID_BILLING_KINDS,
    _billing_client_lock,
    _charge_job_reservation_locked,
    _release_job_kind_reservation,
    billing_kind_label,
    effective_price_kopeks,
    effective_job_unit_price_kopeks,
    reserve_job_units,
)
from .exact_product import (
    ExactProductReport,
    analyze_exact_product,
    write_exact_product_docx,
    is_exact_position_resolved,
)
from .models import ApiKey, ApiOperation, ApiRateLimitEvent, Client, Job, JobFile, SystemSettings, now_utc
from .procurement_report import generate_procurement_report
from .quote_request import build_quote_request_markdown_with_ai
from .repository import get_or_create_settings
from .security import require_admin
from .supplier_search import (
    discover_suppliers,
    extract_supplier_search_context,
    supplier_search_job_context,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])
admin_router = APIRouter(prefix="/api/admin/api-keys", tags=["admin_api_keys"])

# Kept solely as a backwards-compatible import for old in-process diagnostics.
# Production enforcement is the durable ``api_rate_limit_events`` table below.
_RATE_LIMIT_STORE: Dict[str, List[float]] = {}
_MAX_SPEC_LENGTH = 500000
_MAX_DOC_LENGTH = 800000


# ---------------------------------------------------------------------------
# Key Utilities & Security
# ---------------------------------------------------------------------------

def hash_api_key(raw_key: str) -> str:
    """Computes SHA-256 hex digest for secure API key storage and constant-time lookup."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def generate_api_key(is_admin: bool = False) -> tuple[str, str, str]:
    """
    Generates a cryptographically strong API key.
    Returns: (raw_key, key_hash, key_prefix)
    """
    prefix = "tl_admin_" if is_admin else "tl_live_"
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}{random_part}"
    key_hash = hash_api_key(raw_key)
    key_prefix = f"{raw_key[:12]}...{raw_key[-4:]}"
    return raw_key, key_hash, key_prefix


def build_report_download_signature(filename: str, key_secret: str, expires_at: int) -> str:
    """Create a short-lived report signature bound to one authenticated key."""
    payload = f"{Path(filename).name}:{int(expires_at)}".encode("utf-8")
    return hmac.new(str(key_secret).encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_report_download_signature(
    filename: str, key_secret: str, expires_at: int, signature: str, *, now: int | None = None
) -> bool:
    current = int(time.time()) if now is None else int(now)
    if int(expires_at) < current:
        return False
    expected = build_report_download_signature(filename, key_secret, int(expires_at))
    return bool(signature) and hmac.compare_digest(expected, signature)


def claim_api_operation(db: Session, api_key: ApiKey, service: str, idempotency_key: str | None, payload: Any) -> ApiOperation | None:
    """Claim a retry identity without retaining a completed market response."""
    # Direct handler unit tests do not pass FastAPI's injected header value.
    if not isinstance(idempotency_key, str):
        return None
    key = str(idempotency_key or "").strip()
    if not key:
        return None
    if len(key) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", key):
        raise HTTPException(status_code=422, detail="Invalid Idempotency-Key")
    digest = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
    with _billing_client_lock(f"api-operation-{api_key.id}"):
        existing = db.query(ApiOperation).filter(ApiOperation.api_key_id == api_key.id, ApiOperation.idempotency_key == key).first()
        if existing:
            if existing.service != service or existing.request_hash != digest:
                raise HTTPException(status_code=409, detail={"message": "Idempotency-Key already used for another request", "operation_id": existing.id})
            raise HTTPException(status_code=409, detail={"message": "Operation already accepted; inspect its job instead of repeating market work", "operation_id": existing.id, "status": existing.status, "job_id": existing.job_id, "job_ids": json.loads(existing.job_ids_json or "[]")})
        operation = ApiOperation(api_key_id=api_key.id, idempotency_key=key, service=service, request_hash=digest)
        db.add(operation)
        db.commit()
        return operation


def complete_api_operation(
    db: Session,
    operation: ApiOperation | None,
    *,
    status_value: str,
    job: Job | None = None,
    jobs: list[Job] | None = None,
) -> None:
    if operation is None:
        return
    lock_id = str(job.client_id) if job and job.client_id else f"api-key-{operation.api_key_id}"
    with _billing_client_lock(lock_id):
        db.refresh(operation)
        if job is not None:
            db.refresh(job)
            if job.status in {"cancelled", "failed"}:
                status_value = job.status
        operation.status = status_value
        job_ids: list[str] = []
        try:
            stored = json.loads(operation.job_ids_json or "[]")
            if isinstance(stored, list):
                job_ids.extend(str(value) for value in stored if value)
        except (TypeError, ValueError):
            pass
        for candidate in ([job] if job else []) + list(jobs or []):
            if candidate and candidate.id and candidate.id not in job_ids:
                job_ids.append(candidate.id)
        if job_ids:
            operation.job_id = job_ids[0]
        operation.job_ids_json = json.dumps(job_ids)
        db.commit()


def abandon_api_operation(db: Session, operation: ApiOperation | None) -> None:
    """Remove a preflight claim when no market task was ever started."""
    if operation is None:
        return
    with _billing_client_lock(f"api-operation-{operation.api_key_id}"):
        fresh = db.get(ApiOperation, operation.id)
        if fresh and not fresh.job_id and fresh.status == "processing":
            db.delete(fresh)
            db.commit()


def _check_rate_limit(db: Session, api_key: ApiKey, response: Response | None = None) -> None:
    """Enforce a process-safe, persisted per-key sliding one-minute window."""
    key_id = str(api_key.id)
    limit = max(1, int(api_key.rate_limit_per_minute or 30))
    now = now_utc()
    cutoff = now - timedelta(seconds=60)
    with _billing_client_lock(f"api-rate-{key_id}"):
        db.query(ApiRateLimitEvent).filter(
            ApiRateLimitEvent.api_key_id == key_id,
            ApiRateLimitEvent.created_at <= cutoff,
        ).delete(synchronize_session=False)
        events = (
            db.query(ApiRateLimitEvent)
            .filter(ApiRateLimitEvent.api_key_id == key_id, ApiRateLimitEvent.created_at > cutoff)
            .order_by(ApiRateLimitEvent.created_at.asc())
            .all()
        )
        used = len(events)
        oldest = events[0].created_at if events else now
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        reset_at = oldest + timedelta(seconds=60)
        remaining = max(0, limit - used)
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_at.timestamp())),
        }
        if used >= limit:
            retry_after = max(1, int((reset_at - now).total_seconds()) + 1)
            headers["Retry-After"] = str(retry_after)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {limit} requests per minute.",
                headers=headers,
            )
        db.add(ApiRateLimitEvent(api_key_id=key_id, created_at=now))
        db.commit()
        headers["X-RateLimit-Remaining"] = str(max(0, remaining - 1))
        if response is not None:
            response.headers.update(headers)


def get_api_key_auth(
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(db_session),
) -> ApiKey:
    """
    Dependency that authenticates requests using Bearer token or X-API-Key header.
    Validates key existence, active status, expiration, and rate limits.
    """
    raw_token = ""
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:].strip()
    elif x_api_key:
        raw_token = x_api_key.strip()
    elif authorization:
        raw_token = authorization.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Pass 'Authorization: Bearer tl_live_...' or 'X-API-Key: tl_live_...'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    computed_hash = hash_api_key(raw_token)
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == computed_hash).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is disabled or revoked",
        )

    if api_key.expires_at:
        now = datetime.now(timezone.utc)
        exp = api_key.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
            )

    # Check rate limit
    _check_rate_limit(db, api_key, response)

    # Update last used timestamp
    try:
        api_key.last_used_at = now_utc()
        db.commit()
    except Exception:
        db.rollback()

    return api_key


def consume_quota(db: Session, api_key: ApiKey, service: str, count: int = 1) -> int:
    """
    Verifies service permission and consumes quota or client money balance.
    - For admin master keys, quotas are bypassed.
    - When linked to a Client: deducts from the client's unified money balance based on
      their effective tariff (taking into account individual client price overrides),
      logs BillingTransaction, and tracks usage on the key.
    - For standalone keys without a client: checks legacy key request quotas.
    Returns remaining requests (-1 for unlimited).
    """
    if api_key.is_admin:
        return -1

    # 1. Check module permission
    if service == "supplier_search":
        if not api_key.allowed_supplier_search:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supplier search service ('supplier_search') is not permitted for this API key",
            )
    elif service == "exact_product":
        if not api_key.allowed_exact_product:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Exact product & Form 2 service ('exact_product') is not permitted for this API key",
            )
    elif service == "procurement_report":
        if not api_key.allowed_procurement_report:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Procurement documentation analysis service ('procurement_report') is not permitted for this API key",
            )
    elif service == "price_monitoring":
        if not api_key.allowed_price_monitoring:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Price monitoring service ('price_monitoring') is not permitted for this API key",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown service '{service}'",
        )

    # 2. Linked Client -> UNIFIED MONEY BALANCE
    if api_key.client_id:
        client = db.get(Client, api_key.client_id)
        if not client or not client.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт клиента заблокирован или не найден",
            )

        price_kopeks = effective_price_kopeks(db, client, service)
        if price_kopeks is None or price_kopeks < 0:
            price_kopeks = 0
        total_cost_kopeks = price_kopeks * count

        with _billing_client_lock(client.id):
            db.refresh(client)
            available_money_kopeks = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))

            if total_cost_kopeks > 0 and available_money_kopeks < total_cost_kopeks:
                needed_rub = total_cost_kopeks / 100
                avail_rub = available_money_kopeks / 100
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"Недостаточно средств на едином балансе. Требуется: {needed_rub:.2f} ₽, доступно: {avail_rub:.2f} ₽. Пополните баланс.",
                )

            if total_cost_kopeks > 0:
                client.money_balance_kopeks = max(0, int(client.money_balance_kopeks or 0) - total_cost_kopeks)
                service_label = billing_kind_label(service)
                tx = BillingTransaction(
                    client_id=client.id,
                    kind=service,
                    operation=OP_CHARGE,
                    units=count,
                    amount_kopeks=total_cost_kopeks,
                    balance_after_kopeks=client.money_balance_kopeks,
                    reserved_after_kopeks=max(0, int(client.money_reserved_kopeks or 0)),
                    note=f"Запрос по API ({api_key.name or api_key.key_prefix}): {service_label}",
                    created_by="api",
                )
                db.add(tx)

            # Update usage metrics on API key
            if service == "supplier_search":
                api_key.spent_supplier_search += count
            elif service == "exact_product":
                api_key.spent_exact_product += count
            elif service == "procurement_report":
                api_key.spent_procurement_report += count
            elif service == "price_monitoring":
                api_key.spent_price_monitoring += count
            api_key.last_used_at = now_utc()
            db.commit()

        if price_kopeks > 0:
            return int(client.money_balance_kopeks // price_kopeks)
        return 999999

    # 3. Standalone key without client -> Legacy fixed quota check
    if service == "supplier_search":
        if (api_key.spent_supplier_search + count) > api_key.quota_supplier_search:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Supplier search quota exceeded (spent: {api_key.spent_supplier_search}, limit: {api_key.quota_supplier_search})",
            )
        api_key.spent_supplier_search += count
        api_key.last_used_at = now_utc()
        db.commit()
        return max(0, api_key.quota_supplier_search - api_key.spent_supplier_search)

    elif service == "exact_product":
        if (api_key.spent_exact_product + count) > api_key.quota_exact_product:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Exact product quota exceeded (spent: {api_key.spent_exact_product}, limit: {api_key.quota_exact_product})",
            )
        api_key.spent_exact_product += count
        api_key.last_used_at = now_utc()
        db.commit()
        return max(0, api_key.quota_exact_product - api_key.spent_exact_product)

    elif service == "procurement_report":
        if (api_key.spent_procurement_report + count) > api_key.quota_procurement_report:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Procurement analysis quota exceeded (spent: {api_key.spent_procurement_report}, limit: {api_key.quota_procurement_report})",
            )
        api_key.spent_procurement_report += count
        api_key.last_used_at = now_utc()
        db.commit()
        return max(0, api_key.quota_procurement_report - api_key.spent_procurement_report)

    elif service == "price_monitoring":
        if (api_key.spent_price_monitoring + count) > api_key.quota_price_monitoring:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Price monitoring quota exceeded (spent: {api_key.spent_price_monitoring}, limit: {api_key.quota_price_monitoring})",
            )
        api_key.spent_price_monitoring += count
        api_key.last_used_at = now_utc()
        db.commit()
        return max(0, api_key.quota_price_monitoring - api_key.spent_price_monitoring)

    return -1


def check_api_service_permission(api_key: ApiKey, service: str) -> None:
    """Validates that the API key has permission for the specified service."""
    if api_key.is_admin:
        return
    if service == "supplier_search":
        if not api_key.allowed_supplier_search:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supplier search service ('supplier_search') is not permitted for this API key",
            )
    elif service == "exact_product":
        if not api_key.allowed_exact_product:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Exact product service ('exact_product') is not permitted for this API key",
            )
    elif service == "procurement_report":
        if not api_key.allowed_procurement_report:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Procurement documentation analysis service ('procurement_report') is not permitted for this API key",
            )
    elif service == "price_monitoring":
        if not api_key.allowed_price_monitoring:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Price monitoring service ('price_monitoring') is not permitted for this API key",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown service '{service}'",
        )


def _sanitize_filename(val: str, fallback: str = "закупка") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", str(val or "")).strip(" ._-")
    return cleaned[:80] or fallback


def _attach_api_input_file(db: Session, job: Job, text: str, filename: str = "Запрос_API.txt") -> None:
    if not job or not text:
        return
    try:
        from .jobs import job_dir
        in_dir = job_dir(job.id) / "input"
        in_dir.mkdir(parents=True, exist_ok=True)
        stored_path = in_dir / filename
        stored_path.write_text(text, encoding="utf-8")
        job_file = JobFile(
            job_id=job.id,
            original_filename=filename,
            stored_path=str(stored_path),
            parse_status="parsed",
            extracted_chars=len(text),
        )
        db.add(job_file)
        db.commit()
    except Exception as exc:
        logger.warning("failed_to_save_api_input_file for job %s: %s", getattr(job, "id", ""), exc)


def start_api_job_with_reservation(
    db: Session,
    api_key: ApiKey,
    service: str,
    title: str,
    *,
    target_count: int = 0,
    input_text: str = "",
    input_filename: str = "Запрос_API.txt",
    delivery_city: str = "",
    geo_radius_km: int | None = None,
) -> tuple[Optional[Job], int]:
    """
    Begins an API request with two-phase reservation:
    1. Validates permissions and account status.
    2. For linked clients: creates a Job in 'running' status and reserves required funds (OP_RESERVE).
       If balance is insufficient, raises 402 HTTP.
    3. For standalone keys: validates remaining quota.
    Returns: (job, remaining_runs)
    """
    check_api_service_permission(api_key, service)

    from .jobs import next_job_number

    if api_key.is_admin:
        job = Job(
            job_number=next_job_number(db),
            client_id=api_key.client_id,
            created_by_telegram_id=f"api:{api_key.key_prefix}",
            mode=service,
            status="running",
            progress=0,
            title=title[:250],
            target_suppliers=target_count,
            delivery_city=delivery_city,
            geo_radius_km=geo_radius_km,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        if input_text:
            _attach_api_input_file(db, job, input_text, input_filename)
        return job, -1

    if api_key.client_id:
        client = db.get(Client, api_key.client_id)
        if not client or not client.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт клиента заблокирован или не найден",
            )

        job = Job(
            job_number=next_job_number(db),
            client_id=client.id,
            created_by_telegram_id=f"api:{api_key.key_prefix}",
            mode=service,
            status="running",
            progress=0,
            title=title[:250],
            target_suppliers=target_count,
            delivery_city=delivery_city,
            geo_radius_km=geo_radius_km,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        if input_text:
            _attach_api_input_file(db, job, input_text, input_filename)

        try:
            reserve_job_units(db, client, job, supplier_search_count=1)
        except BillingError as be:
            job.status = "failed"
            job.error = str(be)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=str(be),
            )
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка резервирования средств: {exc}",
            )

        # Calculate remaining runs from available balance
        price_kopeks = effective_job_unit_price_kopeks(db, client, service, job=job) or 0
        avail_kopeks = max(0, int(client.money_balance_kopeks or 0) - int(client.money_reserved_kopeks or 0))
        remaining = int(avail_kopeks // price_kopeks) if price_kopeks > 0 else 999999
        return job, remaining

    # Standalone key (legacy fixed quota).  Reserve one quota unit under a
    # process-safe lock before starting external work, otherwise two concurrent
    # requests can both observe the same remaining unit.
    with _billing_client_lock(f"api-key-{api_key.id}"):
        db.refresh(api_key)
        spent = int(getattr(api_key, f"spent_{service}", 0) or 0)
        reserved_attr = f"reserved_{service}"
        reserved = int(getattr(api_key, reserved_attr, 0) or 0)
        quota = int(getattr(api_key, f"quota_{service}", 0) or 0)
        if (spent + reserved + 1) > quota:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"{service} quota exceeded (spent: {spent}, reserved: {reserved}, limit: {quota})",
            )
        # Each reserved slot has its own durable settlement identity. A repeated
        # completion must never consume a different concurrent call's slot.
        job = Job(
            job_number=next_job_number(db),
            created_by_telegram_id=f"api:{api_key.id}",
            mode=service,
            status="running",
            progress=0,
            title=title[:250],
            target_suppliers=target_count,
            delivery_city=delivery_city,
            geo_radius_km=geo_radius_km,
        )
        db.add(job)
        setattr(api_key, reserved_attr, reserved + 1)
        db.commit()
        db.refresh(job)
        return job, max(0, quota - spent - reserved - 1)


def _claim_api_job_settlement(db: Session, job_id: str) -> Job | None:
    """Claim exactly one running API job before any balance mutation occurs."""
    claimed = (
        db.query(Job)
        .filter(Job.id == job_id, Job.status == "running")
        .update(
            {Job.status: "settling", Job.updated_at: now_utc()},
            synchronize_session=False,
        )
    )
    if not claimed:
        db.expire_all()
        return None
    db.flush()
    db.expire_all()
    return db.get(Job, job_id)


def _finish_api_job_fields(
    job: Job,
    *,
    status_value: str,
    result_path: str = "",
    evidence_path: str = "",
    error: str = "",
    verified_count: int = 0,
) -> None:
    job.status = status_value
    job.error = error[:500] if error else ""
    job.verified_count = verified_count
    if result_path:
        job.result_path = result_path
    if evidence_path:
        job.evidence_path = evidence_path
    if status_value == "completed":
        job.progress = 100
        job.completed_at = now_utc()


def _release_api_job_reservation_locked(db: Session, job: Job, *, note: str) -> None:
    """Release every reserved billing kind while the caller owns the client lock."""
    for kind in VALID_BILLING_KINDS:
        _release_job_kind_reservation(db, job, kind, note=note)


def finalize_api_job_success(
    db: Session,
    api_key: ApiKey,
    job: Optional[Job],
    service: str,
    *,
    result_path: str = "",
    evidence_path: str = "",
    verified_count: int = 0,
) -> bool:
    """
    Settles reserved funds upon successful execution (OP_CHARGE),
    updates usage counters and marks job completed.
    """
    lock_id = (
        str(job.client_id)
        if job and job.client_id
        else f"api-key-{api_key.id}"
    )
    with _billing_client_lock(lock_id):
        db.expire_all()
        fresh_key = db.get(ApiKey, api_key.id)
        if fresh_key is None:
            return False
        fresh_job = _claim_api_job_settlement(db, job.id) if job else None
        if job and fresh_job is None:
            return False
        if fresh_job and fresh_job.client_id:
            _charge_job_reservation_locked(
                db,
                fresh_job,
                note=f"Запрос по API ({fresh_key.name or fresh_key.key_prefix}): {billing_kind_label(service)}",
            )
        if fresh_job:
            _finish_api_job_fields(
                fresh_job,
                status_value="completed",
                result_path=result_path,
                evidence_path=evidence_path,
                verified_count=verified_count,
            )

        # The job claim above binds settlement to this call; the key lock
        # protects quota counters shared with other concurrent calls.
        if not fresh_key.is_admin and not fresh_key.client_id:
            reserved_attr = f"reserved_{service}"
            reserved = int(getattr(fresh_key, reserved_attr, 0) or 0)
            if reserved <= 0:
                logger.warning("api_quota_finalize_without_reservation key=%s service=%s", fresh_key.id, service)
                db.rollback()
                return False
            setattr(fresh_key, reserved_attr, reserved - 1)

        spent_attr = f"spent_{service}"
        if hasattr(fresh_key, spent_attr):
            setattr(fresh_key, spent_attr, int(getattr(fresh_key, spent_attr, 0) or 0) + 1)
        fresh_key.last_used_at = now_utc()
        db.commit()
    if job:
        db.expire(job)
    return True


def release_api_job_reservation(
    db: Session,
    api_key: ApiKey,
    job: Optional[Job],
    service: str,
    *,
    error: str = "",
    note: str = "",
    status_val: str = "failed",
    verified_count: int = 0,
    result_path: str = "",
    evidence_path: str = "",
    message: str = "",
) -> bool:
    """
    Safely releases reserved funds when request fails or yields 0 items (OP_RELEASE).
    Client is NOT charged.
    """
    lock_id = (
        str(job.client_id)
        if job and job.client_id
        else f"api-key-{api_key.id}"
    )
    with _billing_client_lock(lock_id):
        db.expire_all()
        fresh_key = db.get(ApiKey, api_key.id)
        if fresh_key is None:
            return False
        fresh_job = _claim_api_job_settlement(db, job.id) if job else None
        if job and fresh_job is None:
            return False
        if fresh_job and fresh_job.client_id:
            _release_api_job_reservation_locked(
                db,
                fresh_job,
                note=note or f"Резерв возвращён: сбой запроса API ({error[:80]})",
            )
        if fresh_job:
            _finish_api_job_fields(
                fresh_job,
                status_value=status_val,
                error=error,
                verified_count=verified_count,
                result_path=result_path,
                evidence_path=evidence_path,
            )
            if message:
                fresh_job.message = message
        if not fresh_key.is_admin and not fresh_key.client_id:
            reserved_attr = f"reserved_{service}"
            reserved = int(getattr(fresh_key, reserved_attr, 0) or 0)
            if reserved > 0:
                setattr(fresh_key, reserved_attr, reserved - 1)
        fresh_key.last_used_at = now_utc()
        db.commit()
    if job:
        db.expire(job)
    return True


def _direct_api_job_key(db: Session, job: Job) -> ApiKey | None:
    owner = str(job.created_by_telegram_id or "")
    if not owner.startswith("api:"):
        return None
    identity = owner.removeprefix("api:")
    return db.get(ApiKey, identity) or db.query(ApiKey).filter(ApiKey.key_prefix == identity).first()


def _terminate_direct_api_job(
    db: Session, job: Job, *, status_value: str, stale_before: datetime | None = None
) -> bool:
    """Claim termination and return this call's reservation in one transaction."""
    owner_key = _direct_api_job_key(db, job)
    lock_id = (str(job.client_id) if job.client_id else
               f"api-key-{owner_key.id}" if owner_key else f"api-job-{job.id}")
    job_id = job.id
    with _billing_client_lock(lock_id):
        db.expire_all()
        query = db.query(Job).filter(Job.id == job_id, Job.status.in_(("pending", "running")))
        if stale_before is not None:
            query = query.filter(Job.updated_at < stale_before)
        cancelled = status_value == "cancelled"
        message = "Задача отменена клиентом" if cancelled else "Запрос API прерван; резерв возвращён. Создайте новый запрос."
        claimed = query.update(
            {Job.status: status_value, Job.progress: 100, Job.error: "" if cancelled else message,
             Job.message: message, Job.completed_at: now_utc(), Job.updated_at: now_utc()},
            synchronize_session=False,
        )
        if not claimed:
            return False
        db.flush()
        db.expire_all()
        terminated = db.get(Job, job_id)
        if terminated.client_id:
            _release_api_job_reservation_locked(db, terminated, note="Резерв возвращён: " + message)
        else:
            fresh_key = _direct_api_job_key(db, terminated)
            if fresh_key is not None and not fresh_key.is_admin and not fresh_key.client_id:
                reserved_attr = f"reserved_{terminated.mode}"
                if hasattr(fresh_key, reserved_attr):
                    setattr(fresh_key, reserved_attr, max(0, int(getattr(fresh_key, reserved_attr) or 0) - 1))
        db.query(ApiOperation).filter(ApiOperation.job_id == job_id).update(
            {ApiOperation.status: status_value}, synchronize_session=False,
        )
        db.commit()
    db.expire(job)
    return True


def cancel_api_job(db: Session, job: Job) -> bool:
    """Atomically let cancellation win over a late API worker completion."""
    return _terminate_direct_api_job(db, job, status_value="cancelled")


def recover_stale_direct_api_jobs(db: Session, *, limit: int = 20) -> list[str]:
    """Release interrupted synchronous calls; never replay external market work.

    Direct requests may legitimately outlast the worker's eight-minute stale
    window, so only recover them after a conservative hour without an update.
    """
    cutoff = now_utc() - timedelta(minutes=60)
    jobs = (db.query(Job).filter(
        Job.created_by_telegram_id.startswith("api:"),
        Job.status.in_(("pending", "running")), Job.updated_at < cutoff,
    ).order_by(Job.updated_at.asc()).limit(max(1, limit)).all())
    recovered = []
    for candidate in jobs:
        if _terminate_direct_api_job(db, candidate, status_value="failed", stale_before=cutoff):
            recovered.append(candidate.id)
    return recovered




# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Public MCP Request / Response Schemas
# ---------------------------------------------------------------------------

def _extract_str(data: dict[str, Any], keys: list[str], default: str = "") -> str:
    for k in keys:
        val = data.get(k)
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def _extract_int(data: dict[str, Any], keys: list[str], default: int) -> int:
    for k in keys:
        val = data.get(k)
        if val is not None:
            try:
                iv = int(val)
                if iv > 0:
                    return iv
            except (ValueError, TypeError):
                pass
    return default


def _format_characteristics(chars: Any) -> str:
    """Formats characteristics passed as list of dicts, dict, or list of strings into clean text."""
    if not chars:
        return ""
    lines = []
    if isinstance(chars, list):
        for item in chars:
            if isinstance(item, dict):
                name = item.get("name") or item.get("param") or item.get("parameter") or item.get("title") or item.get("key") or ""
                value = item.get("value") or item.get("val") or item.get("description") or ""
                if name and value:
                    lines.append(f"• {name}: {value}")
                elif name or value:
                    lines.append(f"• {name or value}")
            elif isinstance(item, str) and item.strip():
                lines.append(f"• {item.strip()}")
    elif isinstance(chars, dict):
        for k, v in chars.items():
            if str(k).strip() and str(v).strip():
                lines.append(f"• {str(k).strip()}: {str(v).strip()}")
    elif isinstance(chars, str) and chars.strip():
        lines.append(chars.strip())
    return "\n".join(lines)


class McpBalanceResponse(BaseModel):
    ok: bool = True
    key_name: str
    key_prefix: str
    is_admin: bool
    is_active: bool
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    client_balance_rub: Optional[float] = None
    billing_mode: str = "money_balance"  # "money_balance" | "fixed_quota"
    supplier_search: Dict[str, Any]
    exact_product: Dict[str, Any]
    procurement_report: Dict[str, Any]
    price_monitoring: Dict[str, Any]
    rate_limit_per_minute: int
    expires_at: Optional[str] = None


class McpSupplierSearchRequest(BaseModel):
    specification: str = Field(..., min_length=2, max_length=_MAX_SPEC_LENGTH, description="Текст ТЗ, спецификации или наименование закупаемой продукции")
    target_count: int = Field(default=5, ge=1, le=50, description="Желаемое количество поставщиков для поиска")
    city: str = Field(default="", max_length=120, description="Город или регион поставки (опционально)")
    geo_radius_km: int | None = Field(default=None, ge=10, le=5000, description="Радиус приоритета поставщиков от города доставки, км")
    include_quote_request: bool = Field(default=True, description="Сформировать готовый шаблон запроса КП")
    search_policy: str = Field(
        default="normal",
        description="Режим поиска: 'normal' (обычный рынок РФ), 'minprom_registry_priority' (приоритет реестра Минпромторга / ГИСП), 'minprom_registry_only' (только производители из реестра Минпромторга РФ)"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # 1. Target count / limit / max_results
        target = _extract_int(d, ["target_count", "max_results", "limit", "count", "suppliers_count", "target"], default=5)
        d["target_count"] = min(50, max(1, target))

        # 2. City / Delivery region
        city = _extract_str(d, ["city", "delivery_region", "region", "location", "delivery_city", "address"], default="")
        d["city"] = city
        if d.get("geo_radius_km") is None:
            raw_radius = d.get("radius_km", d.get("delivery_radius_km"))
            if raw_radius not in (None, ""):
                d["geo_radius_km"] = raw_radius

        # 3. Search policy
        policy = _extract_str(d, ["search_policy", "policy", "mode"], default="normal").lower().strip()
        if policy in {"minprom_registry_only", "only_registry", "gisp_only"}:
            d["search_policy"] = "minprom_registry_only"
        elif policy in {"minprom_registry_priority", "registry_priority", "priority_registry", "gisp_priority"}:
            d["search_policy"] = "minprom_registry_priority"
        else:
            d["search_policy"] = "normal"

        # 4. Include quote request
        if "include_quote_request" not in d:
            for k in ["quote_request", "commercial_offer", "kp", "with_quote"]:
                if k in d:
                    d["include_quote_request"] = bool(d[k])
                    break

        # 5. Specification assembly from any AI agent format
        spec_text = _extract_str(d, ["specification", "spec", "text", "tz", "description", "content", "query"], default="")
        prod_name = _extract_str(d, ["product_name", "procurement_title", "title", "name", "item_name", "subject", "item"], default="")
        okpd2 = _extract_str(d, ["okpd2", "okpd", "code"], default="")
        qty = d.get("quantity") or d.get("amount") or d.get("count_items")
        chars_text = _format_characteristics(d.get("characteristics") or d.get("params") or d.get("parameters") or d.get("specs") or d.get("attributes"))

        parts = []
        if prod_name and prod_name.lower() not in spec_text.lower():
            parts.append(f"Предмет закупки / товар: {prod_name}")
        if okpd2 and okpd2 not in spec_text:
            parts.append(f"Код ОКПД2: {okpd2}")
        if qty and str(qty) not in spec_text:
            parts.append(f"Количество: {qty}")
        if spec_text:
            parts.append(spec_text)
        if chars_text and chars_text not in spec_text:
            parts.append(f"Характеристики:\n{chars_text}")

        final_spec = "\n\n".join([p for p in parts if p.strip()]).strip()
        if not final_spec:
            final_spec = prod_name or spec_text or "Товар по спецификации"

        d["specification"] = final_spec
        return d


class McpSupplierItem(BaseModel):
    company_name: str
    inn: str = ""
    region: str = ""
    status: str = "поставщик"  # завод | дилер | дистрибьютор | поставщик
    product: str = ""
    site: str = ""
    email: str = ""
    phone: str = ""
    match_level: str = "exact"  # exact | adjacent | profile
    quality_score: int = 0
    comments: str = ""
    evidence_url: str = ""


class McpSupplierSearchResponse(BaseModel):
    ok: bool = True
    total_found: int
    target_requested: int
    suppliers: List[McpSupplierItem]
    quote_request_markdown: Optional[str] = None
    quota_remaining: int
    source_title: str = ""


class McpExactProductRequest(BaseModel):
    specification: str = Field(..., min_length=2, max_length=_MAX_SPEC_LENGTH, description="Текст технического задания, параметров или требований к оборудованию")
    procurement_title: str = Field(default="", max_length=300, description="Наименование предмета закупки (опционально)")

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # 1. Procurement title
        title = _extract_str(d, ["procurement_title", "product_name", "title", "name", "item_name", "subject", "item"], default="")
        d["procurement_title"] = title

        # 2. Specification assembly from any AI agent format
        spec_text = _extract_str(d, ["specification", "spec", "text", "tz", "description", "content", "query"], default="")
        okpd2 = _extract_str(d, ["okpd2", "okpd", "code"], default="")
        qty = d.get("quantity") or d.get("amount") or d.get("count_items")
        chars_text = _format_characteristics(d.get("characteristics") or d.get("params") or d.get("parameters") or d.get("specs") or d.get("attributes"))

        parts = []
        if title and title.lower() not in spec_text.lower():
            parts.append(f"Предмет закупки / товар: {title}")
        if okpd2 and okpd2 not in spec_text:
            parts.append(f"Код ОКПД2: {okpd2}")
        if qty and str(qty) not in spec_text:
            parts.append(f"Количество: {qty}")
        if spec_text:
            parts.append(spec_text)
        if chars_text and chars_text not in spec_text:
            parts.append(f"Характеристики:\n{chars_text}")

        final_spec = "\n\n".join([p for p in parts if p.strip()]).strip()
        if not final_spec:
            final_spec = title or spec_text or "Товар по спецификации"

        d["specification"] = final_spec
        return d


class McpSpecMatchItem(BaseModel):
    param_name: str
    tz_requirement: str
    product_fact: str
    status: str  # match | mismatch | clarify
    comment: str = ""


class McpAlternativeItem(BaseModel):
    brand: str
    model: str
    manufacturer: str
    confidence: float
    notes: str = ""
    inn: str = ""
    region: str = ""
    specs_breakdown: List[McpSpecMatchItem] = []


class McpExactPositionItem(BaseModel):
    position_no: int
    name_in_tz: str
    identified_brand: str
    identified_model: str
    manufacturer: str
    confidence: float
    reasoning: str
    specs_breakdown: List[McpSpecMatchItem]
    alternatives: List[McpAlternativeItem]
    position_id: str = ""
    status: str = "found"
    error: str = ""


class McpExactProductResponse(BaseModel):
    ok: bool = True
    summary: str
    total_positions: int
    positions: List[McpExactPositionItem]
    docx_download_url: Optional[str] = None
    quota_remaining: int
    confirmed_positions: int = 0


class McpProcurementAnalyzeRequest(BaseModel):
    document_text: str = Field(..., min_length=2, max_length=_MAX_DOC_LENGTH, description="Текст проекта контракта, извещения или закупочной документации")

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        doc_text = _extract_str(d, [
            "document_text", "text", "document", "doc", "contract_text",
            "tz", "specification", "content", "file_content", "description", "data"
        ], default="")
        d["document_text"] = doc_text or "Документация закупки"
        return d


class McpProcurementAnalyzeResponse(BaseModel):
    ok: bool = True
    report_markdown: str
    ai_model: str = ""
    quota_remaining: int


# ---------------------------------------------------------------------------
# Public MCP Endpoints
# ---------------------------------------------------------------------------

@router.get("/balance", response_model=McpBalanceResponse)
def get_mcp_balance(
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
):
    """Check remaining quotas, active services, and limits for the authenticated API key."""
    client = db.get(Client, api_key.client_id) if api_key.client_id else None
    client_name = client.name if client else None
    client_balance_rub = round((client.money_balance_kopeks or 0) / 100, 2) if client else None
    billing_mode = "money_balance" if client else "fixed_quota"

    def _service_stat(kind: str, allowed: bool, spent: int, fallback_quota: int) -> dict[str, Any]:
        if api_key.is_admin:
            return {"allowed": True, "quota": "unlimited", "spent": spent, "remaining": "unlimited", "price_rub": 0.0}
        if client:
            price_kopeks = effective_price_kopeks(db, client, kind) or 0
            price_rub = round(price_kopeks / 100, 2)
            rem = int((client.money_balance_kopeks or 0) // price_kopeks) if price_kopeks > 0 else 999999
            return {
                "allowed": allowed,
                "billing_type": "client_money_balance",
                "price_rub": price_rub,
                "spent": spent,
                "remaining": rem,
                "client_balance_rub": client_balance_rub,
            }
        return {
            "allowed": allowed,
            "billing_type": "fixed_quota",
            "quota": fallback_quota,
            "spent": spent,
            "remaining": max(0, fallback_quota - spent),
        }

    return McpBalanceResponse(
        ok=True,
        key_name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_admin=api_key.is_admin,
        is_active=api_key.is_active,
        client_id=api_key.client_id,
        client_name=client_name,
        client_balance_rub=client_balance_rub,
        billing_mode=billing_mode,
        supplier_search=_service_stat("supplier_search", api_key.allowed_supplier_search, api_key.spent_supplier_search, api_key.quota_supplier_search),
        exact_product=_service_stat("exact_product", api_key.allowed_exact_product, api_key.spent_exact_product, api_key.quota_exact_product),
        procurement_report=_service_stat("procurement_report", api_key.allowed_procurement_report, api_key.spent_procurement_report, api_key.quota_procurement_report),
        price_monitoring=_service_stat("price_monitoring", api_key.allowed_price_monitoring, api_key.spent_price_monitoring, api_key.quota_price_monitoring),
        rate_limit_per_minute=api_key.rate_limit_per_minute or 30,
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
    )


def record_api_job(
    db: Session,
    api_key: ApiKey,
    mode: str,
    title: str,
    status: str = "completed",
    error: str = "",
    target_count: int = 0,
    verified_count: int = 0,
    result_path: str = "",
    evidence_path: str = "",
) -> Optional[Job]:
    """Records an executed or failed API request into the central jobs table for audit and admin visibility."""
    if not api_key or not api_key.client_id:
        return None
    try:
        from .jobs import next_job_number
        job = Job(
            job_number=next_job_number(db),
            client_id=api_key.client_id,
            created_by_telegram_id=f"api:{api_key.key_prefix}",
            mode=mode,
            status=status,
            progress=100 if status == "completed" else 0,
            title=title[:250],
            target_suppliers=target_count,
            verified_count=verified_count,
            result_path=result_path,
            evidence_path=evidence_path,
            error=error,
            completed_at=now_utc() if status == "completed" else None,
        )
        db.add(job)
        db.commit()
        return job
    except Exception as exc:
        logger.warning("failed_to_record_api_job: %s", exc)
        return None


@router.post("/suppliers/search", response_model=McpSupplierSearchResponse)
async def mcp_supplier_search(
    req: McpSupplierSearchRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
):
    """
    Search direct suppliers, manufacturers, and distributors matching technical specification in real time.
    Returns contact details, verified websites, phone numbers, and optional commercial offer markdown.
    Uses two-phase reservation billing: funds are reserved first and settled only upon verified results.
    If 0 suppliers found or error occurs, the reservation is released and money is not charged.
    """
    settings = get_or_create_settings(db)
    check_api_service_permission(api_key, "supplier_search")
    delivery_city = req.city.strip()
    geo_radius_km = req.geo_radius_km
    if geo_radius_km is not None:
        if api_key.client_id:
            client = db.get(Client, api_key.client_id)
            if not client or not bool(getattr(client, "allowed_geo_radius", False)):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Режим поиска в радиусе доставки недоступен для этого API-ключа")
        elif not api_key.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Для поиска в радиусе доставки нужен ключ клиента с подключенной услугой")
        from .geo_policy import validate_geo_request
        try:
            delivery_city, geo_radius_km = validate_geo_request(delivery_city, geo_radius_km, mode="supplier_search")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    spec_text = req.specification.strip()
    if delivery_city:
        spec_text = f"Регион поставки: {delivery_city}\n\n{spec_text}"

    job_title = f"API: Поиск поставщиков — {spec_text[:80].strip()}"
    operation = claim_api_operation(db, api_key, "supplier_search", idempotency_key, req.model_dump())
    try:
        job, remaining_quota = start_api_job_with_reservation(
            db,
            api_key,
            "supplier_search",
            job_title,
            target_count=req.target_count,
            input_text=spec_text,
            input_filename="ТЗ_поиск_поставщиков.txt",
            delivery_city=delivery_city,
            geo_radius_km=geo_radius_km,
        )
    except Exception:
        abandon_api_operation(db, operation)
        raise
    if operation and job:
        complete_api_operation(db, operation, status_value="processing", job=job)

    policy = req.search_policy.strip() if req.search_policy else "normal"
    if policy not in {"normal", "minprom_registry_priority", "minprom_registry_only"}:
        policy = "normal"

    try:
        clean_context = (await extract_supplier_search_context(settings, spec_text)) or spec_text[:20000]
        with supplier_search_job_context(f"mcp_{api_key.id[:8]}"):
            accepted_rows, evidence = await discover_suppliers(
                settings=settings,
                context=clean_context,
                target=req.target_count,
                supplier_search_policy=policy,
                delivery_city=delivery_city,
                geo_radius_km=geo_radius_km,
            )
    except (Exception, asyncio.CancelledError, BaseException) as exc:
        logger.error("mcp_supplier_search_failed: %s", exc, exc_info=True)
        release_api_job_reservation(
            db, api_key, job, "supplier_search", error=str(exc)
        )
        complete_api_operation(db, operation, status_value="failed", job=job)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supplier search processing error: {str(exc)}",
        )

    supplier_items: List[McpSupplierItem] = []
    for row in accepted_rows:
        supplier_items.append(
            McpSupplierItem(
                company_name=str(row.get("company_name") or "").strip(),
                inn=str(row.get("inn") or "").strip(),
                region=str(row.get("region") or "").strip(),
                status=str(row.get("status") or "поставщик").strip(),
                product=str(row.get("product") or "").strip(),
                site=str(row.get("site") or "").strip(),
                email=str(row.get("email") or "").strip(),
                phone=str(row.get("phone") or "").strip(),
                match_level=str(row.get("match_level") or "exact").strip(),
                quality_score=int(row.get("quality_score") or 0),
                comments=str(row.get("comments") or "").strip(),
                evidence_url=str(row.get("evidence_url") or "").strip(),
            )
        )

    quote_markdown = None
    if req.include_quote_request and supplier_items:
        try:
            subject = str(evidence.get("subject") or "Поставка продукции по ТЗ").strip()
            quote_markdown = await build_quote_request_markdown_with_ai(
                settings,
                clean_context,
                subject=subject,
                procurement_profile=evidence.get("procurement_profile") if isinstance(evidence, dict) else {},
            )
        except Exception as exc:
            logger.warning("mcp_quote_request_gen_failed: %s", exc)

    source_title = str(evidence.get("subject") or "").strip()
    if source_title and job:
        job.title = f"API: Поиск поставщиков — {source_title[:80].strip()}"

    res_path = ""
    evid_path = ""
    if job and accepted_rows:
        try:
            from .jobs import _persist_supplier_rows, job_dir
            from .report_builder import write_supplier_xlsx, write_quote_request_docx, write_evidence
            _persist_supplier_rows(db, job, accepted_rows)

            out_dir = job_dir(job.id) / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = _sanitize_filename(source_title or "поставщики", "поставщики")
            xlsx_filename = f"Поставщики - {stem}.xlsx"
            xlsx_path = write_supplier_xlsx(
                out_dir / xlsx_filename,
                accepted_rows,
                title=job.title,
                target=req.target_count,
                subject=source_title or "Поиск поставщиков",
                policy=policy,
                delivery_city=delivery_city,
            )
            output_files = [
                {"kind": "suppliers", "label": "Поставщики (Excel)", "path": str(xlsx_path)}
            ]
            if quote_markdown:
                quote_md_path = out_dir / f"Запрос КП - {stem}.md"
                quote_md_path.write_text(quote_markdown, encoding="utf-8")
                quote_docx_path = write_quote_request_docx(
                    out_dir / f"Запрос КП - {stem}.docx",
                    quote_markdown,
                    title="Запрос КП",
                )
                output_files.append({
                    "kind": "quote_request",
                    "label": "Запрос КП",
                    "path": str(quote_docx_path),
                    "content_path": str(quote_md_path),
                })
            evidence_payload = {
                "mode": "supplier_search",
                "subject": source_title or "Поиск поставщиков",
                "output_files": output_files,
                "verified_count": len(supplier_items),
            }
            evidence_path = write_evidence(out_dir / "evidence.json", evidence_payload)
            res_path = str(xlsx_path)
            evid_path = str(evidence_path)
        except Exception as exc:
            logger.warning("failed_to_save_api_supplier_artifacts: %s", exc)

    # Billing settlement based on results:
    if len(supplier_items) == 0:
        # 0 suppliers found: release reservation! Do NOT charge the client.
        settled = release_api_job_reservation(
            db,
            api_key,
            job,
            "supplier_search",
            note="Резерв возвращён: поставщики не найдены",
            status_val="completed",
            verified_count=0,
        )
    else:
        # Success: charge reserved funds
        settled = finalize_api_job_success(
            db,
            api_key,
            job,
            "supplier_search",
            result_path=res_path,
            evidence_path=evid_path,
            verified_count=len(supplier_items),
        )

    if settled is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Задача отменена или прервана; результат не выдан.")

    complete_api_operation(db, operation, status_value="completed", job=job)

    return McpSupplierSearchResponse(
        ok=True,
        total_found=len(supplier_items),
        target_requested=req.target_count,
        suppliers=supplier_items,
        quote_request_markdown=quote_markdown,
        quota_remaining=remaining_quota,
        source_title=source_title,
    )


@router.post("/products/exact-analogs", response_model=McpExactProductResponse)
async def mcp_exact_product(
    req: McpExactProductRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
):
    """
    Deep technical specification analysis to uncover hidden original model, Form 2 parameters,
    and 2-4 verified equivalent analogues with compliance verification and DOCX report.
    Uses two-phase reservation billing: funds settled on success, released on error.
    """
    settings = get_or_create_settings(db)
    check_api_service_permission(api_key, "exact_product")
    spec_text = req.specification.strip()
    proc_title = req.procurement_title.strip()

    job_title = f"API: Подбор товара и аналогов — {(proc_title or spec_text)[:80].strip()}"
    operation = claim_api_operation(db, api_key, "exact_product", idempotency_key, req.model_dump())
    try:
        job, remaining_quota = start_api_job_with_reservation(
            db,
            api_key,
            "exact_product",
            job_title,
            input_text=spec_text,
            input_filename="Спецификация_товаров.txt",
        )
    except Exception:
        abandon_api_operation(db, operation)
        raise
    if operation and job:
        complete_api_operation(db, operation, status_value="processing", job=job)

    try:
        report: ExactProductReport = await analyze_exact_product(
            settings=settings,
            context=spec_text,
            procurement_title=proc_title,
        )
    except (Exception, asyncio.CancelledError, BaseException) as exc:
        logger.error("mcp_exact_product_failed: %s", exc, exc_info=True)
        release_api_job_reservation(
            db, api_key, job, "exact_product", error=str(exc)
        )
        complete_api_operation(db, operation, status_value="failed", job=job)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Exact product analysis error: {str(exc)}",
        )

    verified_positions = sum(1 for pos in report.positions if is_exact_position_resolved(pos))

    # A result is deliverable only after both the Word report and its manifest are saved.
    docx_rel_url = None
    res_path = ""
    evid_path = ""
    try:
        from .jobs import job_dir
        from .report_builder import write_evidence
        storage_dir = Path(config.storage_dir or "/root/projects/tenderlex/storage") / "mcp_reports"
        storage_dir.mkdir(parents=True, exist_ok=True)
        doc_filename = f"exact_product_{secrets.token_hex(8)}.docx"
        doc_path = storage_dir / doc_filename
        write_exact_product_docx(doc_path, report, title=req.procurement_title or "Подбор товара и аналогов")
        public_url = getattr(settings, "public_base_url", "https://tenderlex.ru").rstrip("/")
        expires_at = int(time.time()) + 15 * 60
        # API dependency always provides a hash.  The fallback keeps isolated
        # handler tests decoupled from authentication plumbing.
        signature = build_report_download_signature(doc_filename, getattr(api_key, "key_hash", "test-only-key"), expires_at)
        owner_key_id = getattr(api_key, "id", "test-only-key")
        docx_rel_url = f"{public_url}/api/v1/mcp/downloads/{doc_filename}?expires={expires_at}&key_id={owner_key_id}&signature={signature}"

        if job:
            out_dir = job_dir(job.id) / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = _sanitize_filename(proc_title or spec_text[:60], "товар")
            job_doc_path = out_dir / f"Подбор товара - {stem}.docx"
            write_exact_product_docx(job_doc_path, report, title=req.procurement_title or "Подбор товара и аналогов")
            evidence_payload = {
                "mode": "exact_product",
                "subject": proc_title or "Подбор товара и аналогов",
                "output_files": [
                    {"kind": "exact_product", "label": "Подбор товара и аналоги (Word)", "path": str(job_doc_path)}
                ],
                "verified_count": verified_positions,
                **({"exact_product_report": report.to_dict()} if callable(getattr(report, "to_dict", None)) else {}),
            }
            evid_path = str(write_evidence(out_dir / "evidence.json", evidence_payload))
            res_path = str(job_doc_path)
    except Exception as exc:
        logger.warning("mcp_docx_save_failed: %s", exc)
        release_api_job_reservation(db, api_key, job, "exact_product", error="Не удалось сохранить отчёт подбора товара")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось сохранить отчёт подбора товара. Средства не списаны.") from exc

    positions_output: List[McpExactPositionItem] = []
    for pos in report.positions:
        specs_list = [
            McpSpecMatchItem(
                param_name=s.param_name,
                tz_requirement=s.tz_requirement,
                product_fact=s.product_fact,
                status=s.status,
                comment=s.comment,
            )
            for s in pos.specs_breakdown
        ]
        alts_list = [
            McpAlternativeItem(
                brand=alt.brand,
                model=alt.model,
                manufacturer=alt.manufacturer,
                confidence=alt.confidence,
                notes=alt.notes,
                inn=alt.inn,
                region=alt.region,
                specs_breakdown=[
                    McpSpecMatchItem(
                        param_name=alt_s.param_name,
                        tz_requirement=alt_s.tz_requirement,
                        product_fact=alt_s.product_fact,
                        status=alt_s.status,
                        comment=alt_s.comment,
                    )
                    for alt_s in alt.specs_breakdown
                ],
            )
            for alt in (getattr(pos, "alternativeBrands", None) or getattr(pos, "alternative_brands", []))
        ]
        positions_output.append(
            McpExactPositionItem(
                position_no=pos.position_no,
                name_in_tz=pos.name_in_tz,
                identified_brand=pos.identified_brand,
                identified_model=pos.identified_model,
                manufacturer=pos.manufacturer,
                confidence=pos.confidence,
                reasoning=pos.reasoning,
                specs_breakdown=specs_list,
                alternatives=alts_list,
                position_id=str(getattr(pos, "position_id", "") or ""),
                status=str(getattr(pos, "status", "found") or "needs_clarification"),
                error=str(getattr(pos, "error", "") or ""),
            )
        )

    if verified_positions:
        settled = finalize_api_job_success(
            db, api_key, job, "exact_product", result_path=res_path or str(doc_path),
            evidence_path=evid_path, verified_count=verified_positions,
        )
    else:
        settled = release_api_job_reservation(
            db, api_key, job, "exact_product", status_val="completed", verified_count=0,
            result_path=res_path, evidence_path=evid_path,
            message="Отчёт готов: подтверждённые товары не найдены; средства не списаны",
            note="Резерв возвращён: подтверждённые товары не найдены",
        )
    if settled is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Задача отменена или прервана; результат не выдан.")

    complete_api_operation(db, operation, status_value="completed", job=job)
    return McpExactProductResponse(
        ok=True,
        summary=report.summary,
        total_positions=report.total_positions,
        positions=positions_output,
        docx_download_url=docx_rel_url,
        quota_remaining=remaining_quota,
        confirmed_positions=verified_positions,
    )


@router.post("/procurements/analyze", response_model=McpProcurementAnalyzeResponse)
async def mcp_procurement_analyze(
    req: McpProcurementAnalyzeRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
):
    """
    Expert audit of procurement contracts, notice terms, national regime, guarantees, and legal pitfalls under 44-FZ and 223-FZ.
    Uses two-phase reservation billing: funds settled on success, released on error.
    """
    settings = get_or_create_settings(db)
    check_api_service_permission(api_key, "procurement_report")
    doc_text = req.document_text.strip()
    job_title = f"API: Анализ документации — {doc_text[:80].strip()}"
    operation = claim_api_operation(db, api_key, "procurement_report", idempotency_key, req.model_dump())
    try:
        job, remaining_quota = start_api_job_with_reservation(
            db,
            api_key,
            "procurement_report",
            job_title,
            input_text=doc_text,
            input_filename="Документация_закупки.txt",
        )
    except Exception:
        abandon_api_operation(db, operation)
        raise
    if operation and job:
        complete_api_operation(db, operation, status_value="processing", job=job)

    try:
        gen_result = await generate_procurement_report(settings, doc_text)
    except (Exception, asyncio.CancelledError, BaseException) as exc:
        logger.error("mcp_procurement_analyze_failed: %s", exc, exc_info=True)
        release_api_job_reservation(
            db, api_key, job, "procurement_report", error=str(exc)
        )
        complete_api_operation(db, operation, status_value="failed", job=job)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Procurement report analysis error: {str(exc)}",
        )

    res_path = ""
    evid_path = ""
    if job and gen_result and gen_result.report:
        try:
            from .jobs import job_dir
            from .report_builder import write_procurement_docx, write_evidence
            out_dir = job_dir(job.id) / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = _sanitize_filename(doc_text[:60] or "документация", "документация")
            docx_filename = f"Анализ - {stem}.docx"
            docx_path = write_procurement_docx(
                out_dir / docx_filename,
                gen_result.report,
                title=job.title,
            )
            md_path = out_dir / f"Анализ - {stem}.md"
            md_path.write_text(gen_result.report, encoding="utf-8")
            evidence_payload = {
                "mode": "procurement_report",
                "subject": job.title,
                "output_files": [
                    {"kind": "analysis", "label": "Анализ документации (Word)", "path": str(docx_path)}
                ],
                "ai_model": gen_result.ai_model,
            }
            evidence_path = write_evidence(out_dir / "evidence.json", evidence_payload)
            res_path = str(docx_path)
            evid_path = str(evidence_path)
        except Exception as exc:
            logger.warning("failed_to_save_api_analysis_artifacts: %s", exc)

    settled = finalize_api_job_success(
        db,
        api_key,
        job,
        "procurement_report",
        result_path=res_path,
        evidence_path=evid_path,
        verified_count=1,
    )
    if settled is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Задача отменена или прервана; результат не выдан.")
    complete_api_operation(db, operation, status_value="completed", job=job)

    return McpProcurementAnalyzeResponse(
        ok=True,
        report_markdown=gen_result.report,
        ai_model=gen_result.ai_model,
        quota_remaining=remaining_quota,
    )


class McpApiOperationResponse(BaseModel):
    operation_id: str
    service: str
    status: str
    job_id: Optional[str] = None
    job_ids: List[str] = []
    job_status: Optional[str] = None


@router.get("/operations/{operation_id}", response_model=McpApiOperationResponse)
def get_mcp_operation(
    operation_id: str,
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
):
    """Return retry state without retaining or returning market results."""
    operation = (
        db.query(ApiOperation)
        .filter(ApiOperation.id == operation_id, ApiOperation.api_key_id == api_key.id)
        .first()
    )
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API operation not found")
    job = db.get(Job, operation.job_id) if operation.job_id else None
    try:
        job_ids = json.loads(operation.job_ids_json or "[]")
        if not isinstance(job_ids, list):
            job_ids = []
    except (TypeError, ValueError):
        job_ids = []
    if operation.job_id and operation.job_id not in job_ids:
        job_ids.insert(0, operation.job_id)
    return McpApiOperationResponse(
        operation_id=operation.id,
        service=operation.service,
        status=operation.status,
        job_id=operation.job_id,
        job_ids=[str(value) for value in job_ids if value],
        job_status=job.status if job else None,
    )


@router.get("/downloads/{filename}")
def mcp_download_report(
    filename: str,
    expires: int,
    key_id: str,
    signature: str,
):
    """Serve a short-lived report link, invalidated when its owner key is revoked."""
    safe_name = Path(filename).name
    # A signed browser URL is usable by a human/MCP client without leaking its
    # API key; ownership is checked through the active key used to sign it.
    from .db import SessionLocal
    check_db = SessionLocal()
    try:
        api_key = check_db.get(ApiKey, key_id)
        key_expiry = api_key.expires_at if api_key else None
        if key_expiry is not None and key_expiry.tzinfo is None:
            key_expiry = key_expiry.replace(tzinfo=timezone.utc)
        valid = bool(
            api_key and api_key.is_active
            and (key_expiry is None or key_expiry > now_utc())
            and verify_report_download_signature(safe_name, api_key.key_hash, expires, signature)
        )
    finally:
        check_db.close()
    if not valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Download link is invalid or expired")
    if not safe_name.endswith((".docx", ".xlsx", ".pdf", ".zip")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file format")

    storage_dir = Path(config.storage_dir or "/root/projects/tenderlex/storage") / "mcp_reports"
    file_path = (storage_dir / safe_name).resolve()

    if not str(file_path).startswith(str(storage_dir.resolve())) or not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found or expired")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ---------------------------------------------------------------------------
# Admin API Keys Management Schemas & Endpoints
# ---------------------------------------------------------------------------

class AdminApiKeyItem(BaseModel):
    id: str
    key_prefix: str
    name: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    client_balance_rub: Optional[float] = None
    is_admin: bool
    is_active: bool
    allowed_supplier_search: bool
    allowed_exact_product: bool
    allowed_procurement_report: bool
    allowed_price_monitoring: bool
    quota_supplier_search: int
    quota_exact_product: int
    quota_procurement_report: int
    quota_price_monitoring: int
    spent_supplier_search: int
    spent_exact_product: int
    spent_procurement_report: int
    spent_price_monitoring: int
    rate_limit_per_minute: int
    notes: str
    created_at: str
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None


class AdminCreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    client_id: Optional[str] = None
    is_admin: bool = False
    allowed_supplier_search: bool = True
    allowed_exact_product: bool = True
    allowed_procurement_report: bool = True
    allowed_price_monitoring: bool = False
    quota_supplier_search: int = Field(default=20, ge=0, le=1000)
    quota_exact_product: int = Field(default=10, ge=0, le=1000)
    quota_procurement_report: int = Field(default=10, ge=0, le=1000)
    quota_price_monitoring: int = Field(default=0, ge=0, le=1000)
    rate_limit_per_minute: int = Field(default=30, ge=1, le=300)
    notes: str = ""
    expires_days: Optional[int] = Field(default=None, ge=1, le=3650)


class AdminCreateApiKeyResponse(BaseModel):
    ok: bool = True
    raw_api_key: str  # Returned only once upon creation
    item: AdminApiKeyItem


class AdminUpdateApiKeyRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    allowed_supplier_search: Optional[bool] = None
    allowed_exact_product: Optional[bool] = None
    allowed_procurement_report: Optional[bool] = None
    allowed_price_monitoring: Optional[bool] = None
    quota_supplier_search: Optional[int] = Field(default=None, ge=0, le=1000)
    quota_exact_product: Optional[int] = Field(default=None, ge=0, le=1000)
    quota_procurement_report: Optional[int] = Field(default=None, ge=0, le=1000)
    quota_price_monitoring: Optional[int] = Field(default=None, ge=0, le=1000)
    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1, le=300)
    notes: Optional[str] = None


class AdminTestApiKeyRequest(BaseModel):
    tool: str = Field(..., description="supplier_search | exact_product | procurement_report")
    query: str = Field(..., min_length=3, max_length=50000)
    search_policy: str = Field(default="normal", description="normal | minprom_registry_priority | minprom_registry_only")


def _serialize_api_key_item(k: ApiKey, client_name: Optional[str] = None) -> AdminApiKeyItem:
    client_balance_rub = round((k.client.money_balance_kopeks or 0) / 100, 2) if k.client else None
    return AdminApiKeyItem(
        id=k.id,
        key_prefix=k.key_prefix,
        name=k.name,
        client_id=k.client_id,
        client_name=client_name or (k.client.name if k.client else None),
        client_balance_rub=client_balance_rub,
        is_admin=k.is_admin,
        is_active=k.is_active,
        allowed_supplier_search=k.allowed_supplier_search,
        allowed_exact_product=k.allowed_exact_product,
        allowed_procurement_report=k.allowed_procurement_report,
        allowed_price_monitoring=k.allowed_price_monitoring,
        quota_supplier_search=k.quota_supplier_search,
        quota_exact_product=k.quota_exact_product,
        quota_procurement_report=k.quota_procurement_report,
        quota_price_monitoring=k.quota_price_monitoring,
        spent_supplier_search=k.spent_supplier_search,
        spent_exact_product=k.spent_exact_product,
        spent_procurement_report=k.spent_procurement_report,
        spent_price_monitoring=k.spent_price_monitoring,
        rate_limit_per_minute=k.rate_limit_per_minute or 30,
        notes=k.notes or "",
        created_at=k.created_at.isoformat() if k.created_at else "",
        expires_at=k.expires_at.isoformat() if k.expires_at else None,
        last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
    )


@admin_router.get("", response_model=List[AdminApiKeyItem])
def list_api_keys(
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """List all client and master API keys with usage statistics."""
    keys = db.query(ApiKey).order_by(ApiKey.is_admin.desc(), ApiKey.created_at.desc()).all()
    return [_serialize_api_key_item(k) for k in keys]


@admin_router.get("/master")
def get_master_key(
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """
    Returns Master Admin API key metadata only.  A secret cannot be recovered
    from storage; use the explicit POST action to create or rotate it.
    """
    master = db.query(ApiKey).filter(ApiKey.is_admin == True, ApiKey.is_active == True).first()
    return {
        "ok": True,
        "configured": bool(master),
        "raw_api_key": None,
        "item": _serialize_api_key_item(master) if master else None,
    }


@admin_router.post("/master")
def create_or_rotate_master_key(
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Explicitly create or rotate the master token and reveal it once."""
    raw_key, key_hash, key_prefix = generate_api_key(is_admin=True)
    master = db.query(ApiKey).filter(ApiKey.is_admin == True, ApiKey.is_active == True).first()
    if master:
        master.key_hash = key_hash
        master.key_prefix = key_prefix
        master.secret_token = None
    else:
        master = ApiKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            secret_token=None,
            name="Главный Master-ключ Администратора",
            is_admin=True,
            is_active=True,
            allowed_supplier_search=True,
            allowed_exact_product=True,
            allowed_procurement_report=True,
            allowed_price_monitoring=True,
            quota_supplier_search=999999,
            quota_exact_product=999999,
            quota_procurement_report=999999,
            quota_price_monitoring=999999,
            rate_limit_per_minute=120,
            notes="Мастер-ключ с полным безлимитным доступом ко всем модулям TenderLex",
        )
        db.add(master)
    db.commit()
    db.refresh(master)
    return {"ok": True, "raw_api_key": raw_key, "item": _serialize_api_key_item(master)}


@admin_router.post("", response_model=AdminCreateApiKeyResponse)
def create_api_key(
    req: AdminCreateApiKeyRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Creates a new API key and returns the raw secret key once."""
    raw_key, key_hash, key_prefix = generate_api_key(is_admin=req.is_admin)

    expires_at = None
    expiry_days = req.expires_days or (30 if not req.client_id and not req.is_admin else None)
    if expiry_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)

    client_name = None
    if req.client_id:
        client = db.query(Client).filter(Client.id == req.client_id).first()
        if not client or not client.is_active:
            raise HTTPException(status_code=400, detail="Активный клиент для ключа не найден")
        client_name = client.name

    new_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        secret_token=None,
        name=req.name.strip(),
        client_id=req.client_id or None,
        is_admin=req.is_admin,
        is_active=True,
        allowed_supplier_search=req.allowed_supplier_search,
        allowed_exact_product=req.allowed_exact_product,
        allowed_procurement_report=req.allowed_procurement_report,
        allowed_price_monitoring=req.allowed_price_monitoring,
        quota_supplier_search=req.quota_supplier_search,
        quota_exact_product=req.quota_exact_product,
        quota_procurement_report=req.quota_procurement_report,
        quota_price_monitoring=req.quota_price_monitoring,
        rate_limit_per_minute=req.rate_limit_per_minute,
        notes=req.notes.strip(),
        expires_at=expires_at,
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)

    return AdminCreateApiKeyResponse(
        ok=True,
        raw_api_key=raw_key,
        item=_serialize_api_key_item(new_key, client_name),
    )


@admin_router.post("/{key_id}/regenerate")
def regenerate_api_key(
    key_id: str,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Regenerates the token for an existing API key and returns the new raw token."""
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    raw_key, key_hash, key_prefix = generate_api_key(is_admin=key.is_admin)
    key.key_hash = key_hash
    key.key_prefix = key_prefix
    key.secret_token = None
    db.commit()
    db.refresh(key)

    return {
        "ok": True,
        "raw_api_key": raw_key,
        "item": _serialize_api_key_item(key),
    }


@admin_router.patch("/{key_id}", response_model=AdminApiKeyItem)
def update_api_key(
    key_id: str,
    req: AdminUpdateApiKeyRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Updates API key settings, quotas, allowed services, or status."""
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if req.name is not None:
        key.name = req.name.strip()
    if req.is_active is not None:
        key.is_active = req.is_active
    if req.allowed_supplier_search is not None:
        key.allowed_supplier_search = req.allowed_supplier_search
    if req.allowed_exact_product is not None:
        key.allowed_exact_product = req.allowed_exact_product
    if req.allowed_procurement_report is not None:
        key.allowed_procurement_report = req.allowed_procurement_report
    if req.allowed_price_monitoring is not None:
        key.allowed_price_monitoring = req.allowed_price_monitoring
    if req.quota_supplier_search is not None:
        key.quota_supplier_search = req.quota_supplier_search
    if req.quota_exact_product is not None:
        key.quota_exact_product = req.quota_exact_product
    if req.quota_procurement_report is not None:
        key.quota_procurement_report = req.quota_procurement_report
    if req.quota_price_monitoring is not None:
        key.quota_price_monitoring = req.quota_price_monitoring
    if req.rate_limit_per_minute is not None:
        key.rate_limit_per_minute = req.rate_limit_per_minute
    if req.notes is not None:
        key.notes = req.notes.strip()

    db.commit()
    db.refresh(key)
    return _serialize_api_key_item(key)


@admin_router.delete("/{key_id}")
def delete_api_key(
    key_id: str,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Deletes an API key."""
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    db.delete(key)
    db.commit()
    return {"ok": True, "deleted_id": key_id}


@admin_router.post("/test")
async def test_api_tool(
    req: AdminTestApiKeyRequest,
    _admin=Depends(require_admin),
    db: Session = Depends(db_session),
):
    """Executes a live test of an MCP tool directly from the admin panel."""
    settings = get_or_create_settings(db)
    start_time = time.time()

    if req.tool == "supplier_search":
        clean_ctx = (await extract_supplier_search_context(settings, req.query)) or req.query[:10000]
        policy = req.search_policy.strip() if req.search_policy else "normal"
        if policy not in {"normal", "minprom_registry_priority", "minprom_registry_only"}:
            policy = "normal"
        with supplier_search_job_context("admin_live_test"):
            accepted_rows, evidence = await discover_suppliers(
                settings=settings,
                context=clean_ctx,
                target=3,
                supplier_search_policy=policy,
            )
        duration = round(time.time() - start_time, 2)
        return {
            "ok": True,
            "tool": "supplier_search",
            "search_policy": policy,
            "duration_seconds": duration,
            "total_found": len(accepted_rows),
            "suppliers": accepted_rows[:5],
        }

    elif req.tool == "exact_product":
        report = await analyze_exact_product(
            settings=settings,
            context=req.query,
            procurement_title="Тестовый запрос из админ-панели",
        )
        duration = round(time.time() - start_time, 2)
        return {
            "ok": True,
            "tool": "exact_product",
            "duration_seconds": duration,
            "summary": report.summary,
            "total_positions": report.total_positions,
            "positions": [
                {
                    "identified_brand": p.identified_brand,
                    "identified_model": p.identified_model,
                    "confidence": p.confidence,
                    "specs_count": len(p.specs_breakdown),
                    "alternatives_count": len(p.alternative_brands),
                }
                for p in report.positions
            ],
        }

    elif req.tool == "procurement_report":
        gen_result = await generate_procurement_report(settings, req.query)
        duration = round(time.time() - start_time, 2)
        return {
            "ok": True,
            "tool": "procurement_report",
            "duration_seconds": duration,
            "ai_model": gen_result.ai_model,
            "report_snippet": gen_result.report[:1000],
        }

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown tool '{req.tool}'")
