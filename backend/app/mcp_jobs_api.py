"""Queued MCP API for the same durable workflow used by the customer cabinet.

The synchronous MCP tools deliberately remain available for small direct calls.
This router is for files, long-running work, delivery geography and the explicit
customer choices that follow document parsing.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import db_session
from .jobs import (
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_EXACT_PRODUCT,
    MODE_PRICE_MONITORING,
    MODE_PROCUREMENT_REPORT,
    MODE_SUPPLIER_SEARCH,
    VALID_JOB_MODES,
)
from .mcp_api import abandon_api_operation, claim_api_operation, complete_api_operation, get_api_key_auth
from .models import ApiKey, Client, Job
from .repository import get_or_create_settings
from .web_auth import WebAuthContext


router = APIRouter(prefix="/api/v1/mcp/jobs", tags=["mcp_jobs"])

_MODE_ALIASES = {
    "suppliers": MODE_SUPPLIER_SEARCH,
    "supplier_search": MODE_SUPPLIER_SEARCH,
    "analysis": MODE_PROCUREMENT_REPORT,
    "procurement_analysis": MODE_PROCUREMENT_REPORT,
    "procurement_report": MODE_PROCUREMENT_REPORT,
    "analysis_and_suppliers": MODE_ANALYSIS_AND_SUPPLIERS,
    "exact": MODE_EXACT_PRODUCT,
    "exact_product": MODE_EXACT_PRODUCT,
    "product_selection": MODE_EXACT_PRODUCT,
    "price_monitoring": MODE_PRICE_MONITORING,
    "monitoring": MODE_PRICE_MONITORING,
}


class PositionSelectionRequest(BaseModel):
    revision: str = Field(min_length=1, max_length=128)
    selected_item_ids: list[str] = Field(default_factory=list, max_length=1000)


class StrategyRequest(BaseModel):
    revision: str | None = Field(default=None, min_length=1, max_length=128)
    multi_item_mode: str = Field(pattern="^(balanced|per_item)$")
    selected_item_ids: list[str] | None = Field(default=None, max_length=1000)


def _canonical_mode(value: str) -> str:
    mode = _MODE_ALIASES.get(str(value or "").strip().lower())
    if not mode or mode not in VALID_JOB_MODES:
        raise HTTPException(status_code=400, detail="Неизвестный режим обработки.")
    return mode


def _linked_client_or_403(api_key: ApiKey, db: Session) -> Client:
    """Queued work is never allowed for unlinked quota-only API keys.

    A queued request may reserve funds, receive files and later release/charge a
    result.  It must therefore have a concrete account owner.
    """
    if not api_key.client_id:
        raise HTTPException(status_code=403, detail="Queued jobs require an active API key linked to a client account.")
    client = db.get(Client, api_key.client_id)
    if not client or not client.is_active:
        raise HTTPException(status_code=403, detail="Клиентский аккаунт для API-ключа не найден или отключён.")
    return client


def _mode_is_permitted(api_key: ApiKey, client: Client, mode: str) -> bool:
    if mode == MODE_SUPPLIER_SEARCH:
        permitted = bool(getattr(api_key, "allowed_supplier_search", False))
    elif mode == MODE_PROCUREMENT_REPORT:
        permitted = bool(getattr(api_key, "allowed_procurement_report", False))
    elif mode == MODE_ANALYSIS_AND_SUPPLIERS:
        permitted = (
            bool(getattr(api_key, "allowed_procurement_report", False))
            and bool(getattr(api_key, "allowed_supplier_search", False))
        )
    elif mode == MODE_EXACT_PRODUCT:
        permitted = bool(getattr(api_key, "allowed_exact_product", False))
    elif mode == MODE_PRICE_MONITORING:
        permitted = bool(getattr(api_key, "allowed_price_monitoring", False) and getattr(client, "allowed_price_monitoring", False))
    else:  # guarded by _canonical_mode; retained for safe future mode additions
        permitted = False
    return permitted


def _require_mode_permission(api_key: ApiKey, client: Client, mode: str) -> None:
    if not _mode_is_permitted(api_key, client, mode):
        raise HTTPException(status_code=403, detail=f"Режим '{mode}' не разрешён этому API-ключу или клиентскому аккаунту.")


def _context_for_key(api_key: ApiKey, client: Client) -> WebAuthContext:
    # API-key authentication is an independent credential.  The customer helper
    # only needs the durable client owner and a verified-workflow marker; it does
    # not require a browser session or issue one here.
    user = SimpleNamespace(
        id=f"api:{api_key.id}",
        client_id=client.id,
        client=client,
        is_email_verified=True,
    )
    return WebAuthContext(user=user, session=None)


def _owned_job_or_404(db: Session, api_key: ApiKey, job_id: str) -> Job:
    client = _linked_client_or_403(api_key, db)
    job = db.get(Job, job_id)
    if not job or job.client_id != client.id:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    _require_mode_permission(api_key, client, job.mode)
    return job


def _job_payload(job: Job, db: Session) -> dict[str, Any]:
    from .main import customer_job_to_dict
    return customer_job_to_dict(job, include_files=True, db=db)


async def _file_fingerprints(files: list[UploadFile], *, max_files: int, max_bytes: int) -> list[dict[str, str]]:
    if len(files) > max_files:
        raise HTTPException(status_code=400, detail="Слишком много файлов в одной задаче.")
    result: list[dict[str, str]] = []
    for uploaded in files:
        digest = hashlib.sha256()
        total = 0
        while chunk := await uploaded.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                await uploaded.seek(0)
                raise HTTPException(status_code=413, detail=f"{uploaded.filename or 'Файл'} слишком большой.")
            digest.update(chunk)
        await uploaded.seek(0)
        result.append({
            "name": str(uploaded.filename or "upload"),
            "sha256": digest.hexdigest(),
        })
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_queued_job(
    mode: str = Form(...),
    text: str = Form(default=""),
    source_urls: str = Form(default=""),
    delivery_city: str = Form(default=""),
    geo_radius_km: int | None = Form(default=None),
    supplier_search_policy: str = Form(default="normal"),
    multi_item_mode: str = Form(default="balanced"),
    target_suppliers: int = Form(default=0, ge=0, le=100),
    files: list[UploadFile] = File(default=[]),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    canonical_mode = _canonical_mode(mode)
    client = _linked_client_or_403(api_key, db)
    _require_mode_permission(api_key, client, canonical_mode)
    settings = get_or_create_settings(db)
    fingerprint = await _file_fingerprints(
        files,
        max_files=int(getattr(settings, "max_files_per_batch", 20) or 20),
        max_bytes=int(getattr(settings, "max_upload_mb", 50) or 50) * 1024 * 1024,
    )
    operation = claim_api_operation(
        db,
        api_key,
        "queued_job",
        idempotency_key,
        {
            "mode": canonical_mode,
            "text": str(text or ""),
            "source_urls": str(source_urls or ""),
            "delivery_city": str(delivery_city or ""),
            "geo_radius_km": geo_radius_km,
            "supplier_search_policy": str(supplier_search_policy or ""),
            "multi_item_mode": str(multi_item_mode or ""),
            "target_suppliers": target_suppliers,
            "files": fingerprint,
        },
    )
    try:
        from .main import create_customer_job_api
        result = await create_customer_job_api(
            mode=canonical_mode,
            supplier_search_policy=supplier_search_policy,
            multi_item_mode=multi_item_mode,
            delivery_city=delivery_city,
            geo_radius_km=geo_radius_km,
            text=text,
            source_urls=source_urls,
            target_suppliers=target_suppliers,
            files=files,
            context=_context_for_key(api_key, client),
            db=db,
        )
    except Exception:
        # Validation/creation failures must be retryable with the same key.
        abandon_api_operation(db, operation)
        raise

    job_data = result.get("job") if isinstance(result, dict) else None
    batch_jobs = result.get("jobs") if isinstance(result, dict) else None
    if job_data is None and isinstance(batch_jobs, list) and batch_jobs:
        job_data = batch_jobs[0]
    if operation is not None and isinstance(job_data, dict) and job_data.get("id"):
        job = db.get(Job, str(job_data["id"]))
        operation_jobs = [
            found for row in (batch_jobs or []) if isinstance(row, dict)
            for found in [db.get(Job, str(row.get("id") or ""))] if found is not None
        ]
        complete_api_operation(db, operation, status_value="accepted", job=job, jobs=operation_jobs)
    return {
        "ok": True,
        "job": job_data,
        "jobs": batch_jobs if isinstance(batch_jobs, list) else None,
        "batch": bool(result.get("batch", False)),
        "count": result.get("count", 1),
    }


@router.get("")
def list_queued_jobs(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    api_key: ApiKey = Depends(get_api_key_auth),
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    client = _linked_client_or_403(api_key, db)
    modes = [mode for mode in VALID_JOB_MODES if _mode_is_permitted(api_key, client, mode)]
    query = db.query(Job).filter(Job.client_id == client.id, Job.mode.in_(modes)).order_by(Job.created_at.desc())
    total = query.count()
    jobs = query.offset(offset).limit(limit).all()
    return {"ok": True, "jobs": [_job_payload(job, db) for job in jobs], "meta": {"total": total, "limit": limit, "offset": offset}}


@router.get("/{job_id}")
def get_queued_job(job_id: str, api_key: ApiKey = Depends(get_api_key_auth), db: Session = Depends(db_session)) -> dict[str, Any]:
    return {"ok": True, "job": _job_payload(_owned_job_or_404(db, api_key, job_id), db)}


@router.post("/{job_id}/position-selection")
def choose_positions(job_id: str, payload: PositionSelectionRequest, api_key: ApiKey = Depends(get_api_key_auth), db: Session = Depends(db_session)) -> dict[str, Any]:
    client = _linked_client_or_403(api_key, db)
    job = _owned_job_or_404(db, api_key, job_id)
    if job.mode not in {MODE_EXACT_PRODUCT, MODE_PRICE_MONITORING}:
        raise HTTPException(status_code=409, detail="Для этой задачи выбор позиций недоступен.")
    _require_mode_permission(api_key, client, job.mode)
    from .main import choose_product_positions_api
    result = choose_product_positions_api(job_id, revision=payload.revision, selected_item_ids=payload.selected_item_ids, context=_context_for_key(api_key, client), db=db)
    return {"ok": True, "job": result["job"]}


@router.post("/{job_id}/strategy")
@router.post("/{job_id}/choose-strategy")
def choose_strategy(job_id: str, payload: StrategyRequest, api_key: ApiKey = Depends(get_api_key_auth), db: Session = Depends(db_session)) -> dict[str, Any]:
    client = _linked_client_or_403(api_key, db)
    job = _owned_job_or_404(db, api_key, job_id)
    if job.mode not in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS}:
        raise HTTPException(status_code=409, detail="Выбор стратегии доступен только для поиска поставщиков.")
    _require_mode_permission(api_key, client, job.mode)
    from .main import choose_customer_multi_item_strategy_api
    result = choose_customer_multi_item_strategy_api(job_id, multi_item_mode=payload.multi_item_mode, selected_item_ids=payload.selected_item_ids, revision=payload.revision, context=_context_for_key(api_key, client), db=db)
    return {"ok": True, "job": result["job"]}


@router.post("/{job_id}/cancel")
def cancel_queued_job(job_id: str, api_key: ApiKey = Depends(get_api_key_auth), db: Session = Depends(db_session)) -> dict[str, Any]:
    client = _linked_client_or_403(api_key, db)
    job = _owned_job_or_404(db, api_key, job_id)
    _require_mode_permission(api_key, client, job.mode)
    from .main import cancel_customer_job_api
    return cancel_customer_job_api(job_id, context=_context_for_key(api_key, client), db=db)


@router.post("/{job_id}/accept")
@router.post("/{job_id}/accept-partial")
def accept_partial_result(job_id: str, api_key: ApiKey = Depends(get_api_key_auth), db: Session = Depends(db_session)) -> dict[str, Any]:
    client = _linked_client_or_403(api_key, db)
    job = _owned_job_or_404(db, api_key, job_id)
    _require_mode_permission(api_key, client, job.mode)
    from .main import accept_customer_partial_job_api
    return accept_customer_partial_job_api(job_id, context=_context_for_key(api_key, client), db=db)


@router.post("/{job_id}/decline")
@router.post("/{job_id}/decline-partial")
def decline_partial_result(job_id: str, api_key: ApiKey = Depends(get_api_key_auth), db: Session = Depends(db_session)) -> dict[str, Any]:
    client = _linked_client_or_403(api_key, db)
    job = _owned_job_or_404(db, api_key, job_id)
    _require_mode_permission(api_key, client, job.mode)
    from .main import decline_customer_partial_job_api
    return decline_customer_partial_job_api(job_id, context=_context_for_key(api_key, client), db=db)


@router.get("/{job_id}/download")
def download_job(job_id: str, api_key: ApiKey = Depends(get_api_key_auth), db: Session = Depends(db_session)):
    client = _linked_client_or_403(api_key, db)
    job = _owned_job_or_404(db, api_key, job_id)
    _require_mode_permission(api_key, client, job.mode)
    from .main import download_customer_job_api
    return download_customer_job_api(job_id, context=_context_for_key(api_key, client), db=db)


@router.get("/{job_id}/files/{file_kind}")
def download_job_file(job_id: str, file_kind: str, api_key: ApiKey = Depends(get_api_key_auth), db: Session = Depends(db_session)):
    client = _linked_client_or_403(api_key, db)
    job = _owned_job_or_404(db, api_key, job_id)
    _require_mode_permission(api_key, client, job.mode)
    from .main import download_customer_job_file_api
    return download_customer_job_file_api(job_id, file_kind, context=_context_for_key(api_key, client), db=db)
