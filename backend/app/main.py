from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import time

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .ai import call_llm
from .config import config
from .db import db_session, init_db
from .jobs import (
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_PROCUREMENT_REPORT,
    MODE_SUPPLIER_SEARCH,
    VALID_JOB_MODES,
    cleanup_expired_jobs,
    create_job,
    enqueue_job,
    package_job_outputs,
    recover_interrupted_jobs,
)
from .models import Client, ClientTelegramAccount, Job, JobFile, JobSource, SupplierResult, SystemSettings, parse_json_list
from .procurement_sources import source_label, source_payloads_from_text
from .repository import (
    client_access_error,
    commercial_jobs_query,
    current_function_usage,
    ensure_client_telegram_account,
    get_client_by_telegram_id,
    get_or_create_settings,
    is_internal_job_record,
    requested_function_units,
    seed_owner_client,
)
from .schemas import (
    AiTestRequest,
    ClientCreate,
    ClientPatch,
    ClientTelegramAccountCreate,
    ClientTelegramAccountPatch,
    LoginRequest,
    ManualJobCreate,
    SettingsPatch,
)
from .security import (
    ADMIN_COOKIE,
    admin_cookie_max_age,
    check_admin_credentials,
    create_admin_session,
    require_admin,
    verify_admin_session,
)
from .supplier_search import _google_credentials, _provider_order, _tavily_key_candidates, _yandex_credentials

app = FastAPI(title="AI Poisk Bot", version="0.1.0")
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    config.storage_path.mkdir(parents=True, exist_ok=True)
    init_db()
    db = next(db_session())
    recovered_job_ids: list[str] = []
    try:
        settings = get_or_create_settings(db)
        seed_owner_client(db)
        cleanup_expired_jobs(db, settings)
        recovered_job_ids = recover_interrupted_jobs(db)
    finally:
        db.close()
    for job_id in recovered_job_ids:
        enqueue_job(job_id)


@app.get("/api/health")
def health(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    return {
        "ok": True,
        "domain": settings.public_base_url,
        "logistics_enabled": settings.logistics_enabled,
    }


@app.post("/api/auth/login")
def login(data: LoginRequest, request: Request, response: Response) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts = [item for item in LOGIN_ATTEMPTS.get(client_ip, []) if now - item < 600]
    if len(attempts) >= 8:
        raise HTTPException(status_code=429, detail="Too many login attempts")
    if not check_admin_credentials(data.username, data.password):
        attempts.append(now)
        LOGIN_ATTEMPTS[client_ip] = attempts
        raise HTTPException(status_code=401, detail="Invalid login or password")
    LOGIN_ATTEMPTS.pop(client_ip, None)
    response.set_cookie(
        ADMIN_COOKIE,
        create_admin_session(data.username),
        max_age=admin_cookie_max_age(),
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {"ok": True, "username": data.username.strip()}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/session")
def auth_session(request: Request) -> dict:
    return {"ok": verify_admin_session(request.cookies.get(ADMIN_COOKIE, ""))}


@app.get("/api/auth/me", dependencies=[Depends(require_admin)])
def auth_me() -> dict:
    return {"ok": True}


@app.get("/api/dashboard", dependencies=[Depends(require_admin)])
def dashboard(db: Session = Depends(db_session)) -> dict:
    return {
        "clients": db.query(Client).count(),
        "active_clients": db.query(Client).filter(Client.is_active.is_(True)).count(),
        "jobs": db.query(Job).count(),
        "running_jobs": db.query(Job).filter(Job.status.in_(["pending", "running"])).count(),
        "completed_jobs": db.query(Job).filter(Job.status.in_(["completed", "partial"])).count(),
        "failed_jobs": db.query(Job).filter(Job.status == "failed").count(),
        "suppliers": db.query(SupplierResult).count(),
    }


@app.get("/api/ops/system-status", dependencies=[Depends(require_admin)])
def system_status_ops(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    return build_system_status(settings, db)


@app.get("/api/ops/supplier-quality", dependencies=[Depends(require_admin)])
def supplier_quality_ops(db: Session = Depends(db_session)) -> dict:
    jobs = (
        db.query(Job)
        .filter(Job.mode == "supplier_search")
        .order_by(Job.created_at.desc())
        .limit(100)
        .all()
    )
    return build_supplier_quality_snapshot(jobs)


@app.get("/api/settings", dependencies=[Depends(require_admin)])
def get_settings_api(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    return settings_to_public_dict(settings)


@app.get("/api/settings/keys", dependencies=[Depends(require_admin)])
def get_settings_keys(db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    # Mirrors EmailAgent behavior for editing custom provider JSON from the UI.
    return {
        "custom_ai_providers_json": settings.custom_ai_providers_json,
        "supplier_search_adapter_api_key": settings.supplier_search_adapter_api_key,
        "yandex_search_api_key": settings.yandex_search_api_key,
        "google_search_api_key": settings.google_search_api_key,
    }


@app.patch("/api/settings", dependencies=[Depends(require_admin)])
def patch_settings(data: SettingsPatch, db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
    # Product rule: ATI/logistics is disabled for AI Poisk.
    settings.logistics_enabled = False
    db.commit()
    db.refresh(settings)
    return {"success": True, "settings": settings_to_public_dict(settings)}


@app.get("/api/clients", dependencies=[Depends(require_admin)])
def list_clients(db: Session = Depends(db_session)) -> list[dict]:
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    return [client_to_dict(client, db=db) for client in clients]


@app.post("/api/clients", dependencies=[Depends(require_admin)])
def create_client(data: ClientCreate, db: Session = Depends(db_session)) -> dict:
    telegram_id = data.telegram_id.strip()
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Telegram ID is required")
    existing = db.query(Client).filter(Client.telegram_id == telegram_id).first()
    existing_account = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == telegram_id).first()
    if existing_account:
        existing = existing_account.client
    if existing:
        raise HTTPException(status_code=409, detail="Client with this Telegram ID already exists")
    payload = data.model_dump()
    payload["telegram_id"] = telegram_id
    client = Client(**payload)
    db.add(client)
    db.flush()
    ensure_client_telegram_account(
        db,
        client,
        telegram_id,
        username=client.username,
        name=client.name,
        notes="Primary Telegram account",
    )
    db.commit()
    db.refresh(client)
    return client_to_dict(client, db=db)


@app.patch("/api/clients/{client_id}", dependencies=[Depends(require_admin)])
def update_client(client_id: str, data: ClientPatch, db: Session = Depends(db_session)) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client_to_dict(client, db=db)


@app.post("/api/clients/{client_id}/telegram-accounts", dependencies=[Depends(require_admin)])
def create_client_telegram_account(client_id: str, data: ClientTelegramAccountCreate, db: Session = Depends(db_session)) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    telegram_id = data.telegram_id.strip()
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Telegram ID is required")
    existing_account = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == telegram_id).first()
    existing_client = db.query(Client).filter(Client.telegram_id == telegram_id).first()
    if existing_account or (existing_client and existing_client.id != client.id):
        raise HTTPException(status_code=409, detail="Telegram ID is already linked to a client")
    account = ClientTelegramAccount(
        client_id=client.id,
        telegram_id=telegram_id,
        username=data.username,
        name=data.name,
        is_active=data.is_active,
        notes=data.notes,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return telegram_account_to_dict(account)


@app.patch("/api/clients/{client_id}/telegram-accounts/{account_id}", dependencies=[Depends(require_admin)])
def update_client_telegram_account(
    client_id: str,
    account_id: str,
    data: ClientTelegramAccountPatch,
    db: Session = Depends(db_session),
) -> dict:
    account = (
        db.query(ClientTelegramAccount)
        .filter(ClientTelegramAccount.id == account_id)
        .filter(ClientTelegramAccount.client_id == client_id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Telegram account not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return telegram_account_to_dict(account)


@app.get("/api/jobs", dependencies=[Depends(require_admin)])
def list_jobs(
    include_internal: bool = False,
    limit: int = 200,
    db: Session = Depends(db_session),
) -> list[dict]:
    safe_limit = max(1, min(500, int(limit or 200)))
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(safe_limit * 3).all()
    visible_jobs = jobs if include_internal else [job for job in jobs if not is_internal_job(job)]
    return [job_to_dict(job) for job in visible_jobs[:safe_limit]]


@app.get("/api/jobs/{job_id}", dependencies=[Depends(require_admin)])
def get_job(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_dict(job, include_files=True)


@app.get("/api/jobs/{job_id}/download", dependencies=[Depends(require_admin)])
def download_job(job_id: str, db: Session = Depends(db_session)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    output = package_job_outputs(job)
    if not output or not output.exists():
        raise HTTPException(status_code=404, detail="Output not found")
    return FileResponse(output, filename=output.name)


@app.get("/api/jobs/{job_id}/evidence", dependencies=[Depends(require_admin)])
def get_job_evidence(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return read_job_evidence_payload(job)


@app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(require_admin)])
def retry_job(job_id: str, db: Session = Depends(db_session)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "pending"
    job.progress = 0
    job.error = ""
    job.message = "Повторный запуск"
    db.commit()
    enqueue_job(job.id)
    return {"success": True, "job": job_to_dict(job)}


def read_job_evidence_payload(job: Job, *, storage_root: Path | None = None) -> dict:
    evidence_path = str(getattr(job, "evidence_path", "") or "")
    if not evidence_path:
        raise HTTPException(status_code=404, detail="Evidence not found")
    root = (storage_root or config.storage_path).resolve()
    path = Path(evidence_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Evidence not found") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence not found")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Evidence is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Evidence JSON root must be an object")
    return payload


def build_supplier_quality_snapshot(jobs: list[Job], *, storage_root: Path | None = None) -> dict:
    status_counts: dict[str, int] = {}
    provider_status_counts: dict[str, dict[str, int]] = {}
    total_verified = 0
    supplier_jobs = 0
    underfilled = 0
    ai_required_failures = 0
    durations: list[float] = []
    recent_failures: list[dict] = []

    for job in jobs:
        if str(getattr(job, "mode", "") or "") not in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS}:
            continue
        if is_internal_job(job):
            continue
        supplier_jobs += 1
        status = str(getattr(job, "status", "") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        verified = int(getattr(job, "verified_count", 0) or 0)
        target = int(getattr(job, "target_suppliers", 0) or 0)
        total_verified += verified
        if status in {"completed", "partial", "needs_review"} and target and verified < target:
            underfilled += 1
        created_at = getattr(job, "created_at", None)
        completed_at = getattr(job, "completed_at", None)
        if created_at and completed_at:
            durations.append(max(0.0, (completed_at - created_at).total_seconds()))
        evidence = _safe_read_job_evidence(job, storage_root=storage_root)
        if evidence.get("ai_required") and status == "failed":
            ai_required_failures += 1
        search_reports = evidence.get("search", {}).get("reports", [])
        if isinstance(search_reports, list):
            for report in search_reports:
                if not isinstance(report, dict):
                    continue
                provider = str(report.get("provider") or "unknown")
                provider_status = str(report.get("status") or "unknown")
                provider_status_counts.setdefault(provider, {})
                provider_status_counts[provider][provider_status] = provider_status_counts[provider].get(provider_status, 0) + 1
        if status == "failed" and len(recent_failures) < 10:
            recent_failures.append(
                {
                    "id": str(getattr(job, "id", "") or ""),
                    "title": human_job_title(job),
                    "error": str(getattr(job, "error", "") or "")[:500],
                    "ai_required": bool(evidence.get("ai_required")),
                    "stage": str(evidence.get("stage") or ""),
                    "created_at": created_at.isoformat() if created_at else None,
                }
            )

    return {
        "window_size": supplier_jobs,
        "status_counts": dict(sorted(status_counts.items())),
        "average_verified_count": round(total_verified / supplier_jobs, 2) if supplier_jobs else 0,
        "average_duration_seconds": round(sum(durations) / len(durations), 2) if durations else 0,
        "underfilled_terminal_jobs": underfilled,
        "ai_required_failures": ai_required_failures,
        "provider_status_counts": {
            provider: dict(sorted(counts.items()))
            for provider, counts in sorted(provider_status_counts.items())
        },
        "recent_failures": recent_failures,
        "alerts": build_supplier_quality_alerts(
            supplier_jobs=supplier_jobs,
            status_counts=status_counts,
            provider_status_counts=provider_status_counts,
            ai_required_failures=ai_required_failures,
            underfilled_terminal_jobs=underfilled,
            average_duration_seconds=round(sum(durations) / len(durations), 2) if durations else 0,
        ),
    }


def build_supplier_quality_alerts(
    *,
    supplier_jobs: int,
    status_counts: dict[str, int],
    provider_status_counts: dict[str, dict[str, int]],
    ai_required_failures: int,
    underfilled_terminal_jobs: int,
    average_duration_seconds: float,
) -> list[dict]:
    alerts: list[dict] = []
    failed = status_counts.get("failed", 0)
    if supplier_jobs and failed / supplier_jobs >= 0.2:
        alerts.append({"severity": "critical", "code": "supplier_failure_rate", "message": f"Supplier failure rate is {failed}/{supplier_jobs}."})
    if ai_required_failures:
        alerts.append({"severity": "critical", "code": "ai_required_failures", "message": f"AI-required supplier failures: {ai_required_failures}."})
    if underfilled_terminal_jobs:
        alerts.append({"severity": "warning", "code": "underfilled_reports", "message": f"Underfilled terminal supplier reports: {underfilled_terminal_jobs}."})
    if average_duration_seconds >= 1800:
        alerts.append({"severity": "warning", "code": "slow_supplier_jobs", "message": f"Average supplier job duration is {average_duration_seconds}s."})
    primary_search_has_ok = any(provider_status_counts.get(provider, {}).get("ok", 0) > 0 for provider in ("yandex", "google"))
    for provider, counts in sorted(provider_status_counts.items()):
        total = sum(counts.values())
        if provider in {"tavily", "ddgs"} and primary_search_has_ok:
            continue
        if total and counts.get("ok", 0) == 0:
            alerts.append({"severity": "warning", "code": "search_provider_no_ok", "message": f"{provider} has no ok searches in the current window."})
    return alerts


def _safe_read_job_evidence(job: Job, *, storage_root: Path | None = None) -> dict:
    try:
        return read_job_evidence_payload(job, storage_root=storage_root)
    except HTTPException:
        return {}


@app.post("/api/jobs/manual", dependencies=[Depends(require_admin)])
def create_manual_job(data: ManualJobCreate, db: Session = Depends(db_session)) -> dict:
    if data.mode not in VALID_JOB_MODES:
        raise HTTPException(status_code=400, detail="Unknown job mode")
    raise HTTPException(status_code=400, detail="Upload a document through /api/upload or Telegram before creating a job.")


@app.post("/api/upload", dependencies=[Depends(require_admin)])
async def upload_job(
    telegram_id: str,
    mode: str = "supplier_search",
    files: list[UploadFile] = File(default=[]),
    source_urls: str = Form(default=""),
    db: Session = Depends(db_session),
) -> dict:
    if mode not in VALID_JOB_MODES:
        raise HTTPException(status_code=400, detail="Unknown job mode")
    sources = source_payloads_from_text(source_urls)
    if sources and mode not in {MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS}:
        raise HTTPException(
            status_code=400,
            detail="Supplier search requires a technical assignment file; procurement links are accepted for documentation analysis.",
        )
    if not files and not sources:
        raise HTTPException(status_code=400, detail="Upload at least one document or provide a procurement source URL")
    client, account_error = get_client_by_telegram_id(db, telegram_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    settings = get_or_create_settings(db)
    supplier_search_count = len(files) if mode == MODE_SUPPLIER_SEARCH and len(files) > 1 else 1
    access_error = account_error or client_access_error(
        db,
        client,
        mode,
        incoming_file_count=len(files),
        supplier_search_count=supplier_search_count,
    )
    if access_error:
        raise HTTPException(status_code=403, detail=access_error)
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(status_code=400, detail="Too many files")
    payload = []
    for file in files:
        content = await file.read()
        if len(content) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"{file.filename} is too large")
        payload.append((file.filename or "upload", content))
    if mode == MODE_SUPPLIER_SEARCH and len(payload) > 1:
        jobs = []
        for filename, content in payload:
            job = create_job(
                db,
                client_id=client.id,
                created_by_telegram_id=telegram_id,
                mode=mode,
                title=Path(filename).stem,
                target_suppliers=settings.default_supplier_target,
                files=[(filename, content)],
                sources=[],
            )
            enqueue_job(job.id)
            jobs.append(job_to_dict(job))
        return {"batch": True, "count": len(jobs), "jobs": jobs}

    title = Path(files[0].filename).stem if files else source_label(sources[0]["value"])
    job = create_job(
        db,
        client_id=client.id,
        created_by_telegram_id=telegram_id,
        mode=mode,
        title=title,
        target_suppliers=settings.default_supplier_target,
        files=payload,
        sources=sources,
    )
    enqueue_job(job.id)
    return job_to_dict(job)


@app.post("/api/ai/test", dependencies=[Depends(require_admin)])
async def test_ai(data: AiTestRequest, db: Session = Depends(db_session)) -> dict:
    settings = get_or_create_settings(db)
    override = f"{data.provider}:{data.model}" if data.provider and data.model else None
    text = await call_llm(
        settings,
        data.prompt,
        tier="light",
        routing_key=data.routing_key,
        override=override,
        timeout_seconds=45,
    )
    return {"success": True, "response": text[:1000]}


def settings_to_public_dict(settings: SystemSettings) -> dict:
    data = settings.to_dict(include_secrets=False)
    data["supplier_search_ui"] = supplier_search_ui(settings)
    return data


def is_internal_job(job: Job | object) -> bool:
    return is_internal_job_record(job)


def human_job_title(job: Job | object) -> str:
    if is_internal_job(job):
        return "Служебная проверка"
    mode = str(getattr(job, "mode", "") or "")
    raw = str(getattr(job, "title", "") or "").strip()
    if not raw:
        return mode_label(mode)
    cleaned = " ".join(raw.replace("_", " ").split())
    if not cleaned or _looks_like_hash(cleaned):
        return mode_label(mode)
    return f"{cleaned[:87]}..." if len(cleaned) > 90 else cleaned


def _looks_like_hash(value: str) -> bool:
    return len(value) >= 12 and all(char in "0123456789abcdefABCDEF" for char in value)


def mode_label(mode: str) -> str:
    labels = {
        MODE_SUPPLIER_SEARCH: "Поиск поставщиков",
        MODE_PROCUREMENT_REPORT: "Анализ документации",
        MODE_ANALYSIS_AND_SUPPLIERS: "Анализ + поставщики",
    }
    return labels.get(mode, "Задача")


def client_usage_summary(db: Session, client: Client) -> dict:
    supplier_used, report_used, _file_count = current_function_usage(db, client)
    return {
        "supplier_search": usage_counter(
            label="Отчёты по поставщикам",
            used=supplier_used,
            limit=client.monthly_supplier_search_limit,
        ),
        "procurement_report": usage_counter(
            label="Анализы документации",
            used=report_used,
            limit=client.monthly_procurement_report_limit,
        ),
    }


def usage_counter(*, label: str, used: int, limit: int) -> dict:
    unlimited = limit < 0
    remaining = None if unlimited else max(0, limit - used)
    percent = 0 if unlimited or limit <= 0 else min(100, round(used * 100 / limit))
    return {
        "label": label,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "unlimited": unlimited,
        "percent": percent,
    }


def client_recent_usage(db: Session, client: Client, *, limit: int = 5) -> list[dict]:
    jobs = (
        commercial_jobs_query(db, client)
        .order_by(Job.created_at.desc())
        .limit(max(1, limit * 3))
        .all()
    )
    items: list[dict] = []
    for job in jobs:
        supplier_units, report_units = requested_function_units(str(job.mode or ""))
        if supplier_units <= 0 and report_units <= 0:
            continue
        items.append(
            {
                "id": job.id,
                "mode": job.mode,
                "mode_label": mode_label(job.mode),
                "human_title": human_job_title(job),
                "created_by_telegram_id": job.created_by_telegram_id or (job.client.telegram_id if job.client else ""),
                "supplier_units": supplier_units,
                "procurement_report_units": report_units,
                "status": job.status,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
        )
        if len(items) >= limit:
            break
    return items


def supplier_search_ui(settings: SystemSettings) -> dict:
    provider_order = _provider_order(settings)
    tavily_ready = bool(_tavily_key_candidates(settings))
    google_key, google_cse = _google_credentials(settings)
    yandex_folder, yandex_key = _yandex_credentials(settings)
    configured = {
        "tavily": tavily_ready,
        "google": bool(google_key and google_cse),
        "yandex": bool(yandex_folder and yandex_key),
        "ddgs": "ddgs" in provider_order,
    }
    active_provider = next((provider for provider in provider_order if configured.get(provider)), "")
    if not active_provider:
        active_provider = provider_order[0] if provider_order else "tavily"
    active_ready = bool(configured.get(active_provider))
    return {
        "active_provider": active_provider,
        "active_label": supplier_search_source_label(active_provider),
        "active_note": supplier_search_active_note(active_provider, active_ready),
        "has_active_source": active_ready,
        "provider_order": provider_order,
        "technical_sources": [
            source_ui_item(provider, supplier_search_source_label(provider), configured[provider], active_provider)
            for provider in provider_order
            if provider in configured
        ],
    }


def supplier_search_source_label(provider: str) -> str:
    labels = {
        "yandex": "Яндекс Поиск",
        "google": "Google Поиск",
        "tavily": "Дополнительный поиск Tavily",
        "ddgs": "Резерв DuckDuckGo",
    }
    return labels.get(provider, "Источник поиска")


def supplier_search_active_note(provider: str, ready: bool) -> str:
    if not ready:
        return "Первый источник в порядке поиска не настроен. Добавьте ключи Яндекса или Google в расширенных параметрах."
    if provider == "yandex":
        return "Основной поиск через Яндекс подключён."
    if provider == "google":
        return "Основной поиск через Google подключён."
    if provider == "tavily":
        return "Работает дополнительный источник Tavily."
    if provider == "ddgs":
        return "Работает резервный поиск без ключа."
    return "Источник поиска подключён."


def source_ui_item(provider: str, label: str, configured: bool, active_provider: str) -> dict:
    return {
        "id": provider,
        "label": label,
        "configured": configured,
        "active": provider == active_provider,
        "status_label": "используется" if provider == active_provider and configured else "подключён" if configured else "не настроен",
    }


def build_system_status(settings: SystemSettings, db: Session) -> dict:
    root_disk = disk_usage_payload(Path("/"))
    storage_disk = disk_usage_payload(config.storage_path if config.storage_path.exists() else config.storage_path.parent)
    memory = memory_payload()
    server = {
        **root_disk,
        "cpu_percent": cpu_percent(),
        "ram_total_gb": memory["ram_total_gb"],
        "ram_used_gb": memory["ram_used_gb"],
        "ram_percent": memory["ram_percent"],
        "storage_free_gb": storage_disk["disk_free_gb"],
        "storage_used_gb": storage_disk["disk_used_gb"],
        "storage_percent": storage_disk["disk_percent"],
    }
    queue = {
        "pending": db.query(Job).filter(Job.status == "pending").count(),
        "running": db.query(Job).filter(Job.status == "running").count(),
        "failed": db.query(Job).filter(Job.status == "failed").count(),
        "completed": db.query(Job).filter(Job.status.in_(["completed", "partial"])).count(),
    }
    services = api_service_statuses(settings)
    warnings = []
    if server["disk_free_gb"] < 10:
        warnings.append("На сервере осталось меньше 10 ГБ свободного места.")
    if server["ram_percent"] >= 85:
        warnings.append("Оперативная память загружена выше 85%.")
    if server["cpu_percent"] >= 85:
        warnings.append("CPU загружен выше 85%.")
    if queue["pending"] >= 50:
        warnings.append("В очереди больше 50 задач. Проверьте worker и скорость обработки.")
    return {
        "server": server,
        "queue": queue,
        "services": services,
        "warnings": warnings,
        "status": "warning" if warnings else "ok",
        "updated_at": now_iso(),
    }


def disk_usage_payload(path: Path) -> dict:
    usage = shutil.disk_usage(path)
    return {
        "disk_total_gb": bytes_to_gb(usage.total),
        "disk_used_gb": bytes_to_gb(usage.used),
        "disk_free_gb": bytes_to_gb(usage.free),
        "disk_percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0.0,
    }


def memory_payload() -> dict:
    meminfo = read_meminfo()
    total = meminfo.get("MemTotal", 0) * 1024
    available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) * 1024
    used = max(0, total - available)
    return {
        "ram_total_gb": bytes_to_gb(total),
        "ram_used_gb": bytes_to_gb(used),
        "ram_percent": round((used / total) * 100, 1) if total else 0.0,
    }


def read_meminfo(path: Path = Path("/proc/meminfo")) -> dict[str, int]:
    result: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            parts = value.strip().split()
            if parts and parts[0].isdigit():
                result[key] = int(parts[0])
    except Exception:
        return {}
    return result


def cpu_percent() -> float:
    first = read_cpu_totals()
    time.sleep(0.05)
    second = read_cpu_totals()
    if first and second:
        total_delta = second[0] - first[0]
        idle_delta = second[1] - first[1]
        if total_delta > 0:
            return round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1)
    try:
        load_1m = os.getloadavg()[0]
        cpu_count = max(1, os.cpu_count() or 1)
        return round(max(0.0, min(100.0, load_1m / cpu_count * 100)), 1)
    except Exception:
        return 0.0


def read_cpu_totals(path: Path = Path("/proc/stat")) -> tuple[int, int] | None:
    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        parts = [int(part) for part in first_line.split()[1:]]
    except Exception:
        return None
    if len(parts) < 4:
        return None
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
    return sum(parts), idle


def api_service_statuses(settings: SystemSettings) -> list[dict]:
    yandex_folder, yandex_key = _yandex_credentials(settings)
    google_key, google_cse = _google_credentials(settings)
    configured_ai = [
        item
        for item in parse_json_list(settings.custom_ai_providers_json)
        if str(item.get("apiKey") or "").strip() and str(item.get("baseUrl") or "").strip()
    ]
    services = [
        api_service_item("yandex", "Яндекс Поиск", "yandex.cloud", bool(yandex_folder and yandex_key), "Основной источник поиска поставщиков."),
        api_service_item("google", "Google Поиск", "customsearch.googleapis.com", bool(google_key and google_cse), "Основной источник поиска поставщиков."),
        api_service_item("ai", "Нейросети", f"подключений: {len(configured_ai)}", bool(configured_ai), "Используются для анализа документации и проверки поставщиков."),
        api_service_item("tavily", "Tavily", "дополнительный поиск", bool(_tavily_key_candidates(settings)), "Вспомогательный источник после Яндекса и Google."),
    ]
    return services


def api_service_item(service_id: str, label: str, detail: str, configured: bool, note: str) -> dict:
    return {
        "id": service_id,
        "label": label,
        "detail": detail,
        "configured": configured,
        "status": "ok" if configured else "missing",
        "status_label": "подключено" if configured else "не настроено",
        "balance_label": "баланс не проверяется",
        "note": note,
    }


def bytes_to_gb(value: int | float) -> float:
    return round(float(value) / (1024**3), 2)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def client_to_dict(client: Client, *, db: Session | None = None) -> dict:
    return {
        "id": client.id,
        "telegram_id": client.telegram_id,
        "name": client.name,
        "username": client.username,
        "is_active": client.is_active,
        "is_trial": client.is_trial,
        "access_until": client.access_until,
        "allowed_supplier_search": client.allowed_supplier_search,
        "allowed_procurement_report": client.allowed_procurement_report,
        "monthly_job_limit": client.monthly_job_limit,
        "monthly_supplier_search_limit": client.monthly_supplier_search_limit,
        "monthly_procurement_report_limit": client.monthly_procurement_report_limit,
        "monthly_file_limit": client.monthly_file_limit,
        "notes": client.notes,
        "telegram_accounts": [telegram_account_to_dict(account) for account in sorted(client.telegram_accounts, key=lambda item: item.created_at, reverse=True)],
        "usage": client_usage_summary(db, client) if db else None,
        "recent_usage": client_recent_usage(db, client) if db else [],
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


def telegram_account_to_dict(account: ClientTelegramAccount) -> dict:
    return {
        "id": account.id,
        "client_id": account.client_id,
        "telegram_id": account.telegram_id,
        "username": account.username,
        "name": account.name,
        "is_active": account.is_active,
        "notes": account.notes,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


def job_to_dict(job: Job, include_files: bool = False) -> dict:
    supplier_units, report_units = requested_function_units(job.mode)
    data = {
        "id": job.id,
        "client_id": job.client_id,
        "client_name": job.client.name if job.client else "",
        "telegram_id": job.client.telegram_id if job.client else "",
        "created_by_telegram_id": job.created_by_telegram_id,
        "mode": job.mode,
        "mode_label": mode_label(job.mode),
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "title": job.title,
        "human_title": human_job_title(job),
        "is_internal": is_internal_job(job),
        "supplier_units": supplier_units,
        "procurement_report_units": report_units,
        "target_suppliers": job.target_suppliers,
        "verified_count": job.verified_count,
        "file_count": job.file_count,
        "has_result": bool(job.result_path),
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    if include_files:
        data["files"] = [file_to_dict(item) for item in job.files]
        data["sources"] = [source_to_dict(item) for item in job.sources]
        data["suppliers"] = [supplier_to_dict(item) for item in job.suppliers]
    return data


def file_to_dict(file: JobFile) -> dict:
    return {
        "id": file.id,
        "original_filename": file.original_filename,
        "parse_status": file.parse_status,
        "extracted_chars": file.extracted_chars,
        "error": file.error,
    }


def source_to_dict(source: JobSource) -> dict:
    return {
        "id": source.id,
        "kind": source.kind,
        "label": source.label,
        "value": source.value,
        "parse_status": source.parse_status,
        "extracted_chars": source.extracted_chars,
        "error": source.error,
    }


def supplier_to_dict(item: SupplierResult) -> dict:
    return {
        "company_name": item.company_name,
        "region": item.region,
        "status": item.status,
        "product": item.product,
        "phone": item.phone,
        "email": item.email,
        "site": item.site,
        "evidence_url": item.evidence_url,
        "contact_url": item.contact_url,
        "comments": item.comments,
        "evidence_status": item.evidence_status,
        "match_level": getattr(item, "match_level", ""),
        "source": getattr(item, "source", ""),
        "search_query": getattr(item, "search_query", ""),
        "quality_score": getattr(item, "quality_score", 0),
        "quality_tier": getattr(item, "quality_tier", ""),
        "procurement_item_id": getattr(item, "procurement_item_id", ""),
        "procurement_item": getattr(item, "procurement_item", ""),
        "ai_confidence": getattr(item, "ai_confidence", 0),
        "site_type": getattr(item, "site_type", ""),
        "product_fit": getattr(item, "product_fit", ""),
        "evidence_snippet": getattr(item, "evidence_snippet", ""),
        "contact_evidence_snippet": getattr(item, "contact_evidence_snippet", ""),
        "ai_rank_confidence": getattr(item, "ai_rank_confidence", 0),
        "ai_rank_reason": getattr(item, "ai_rank_reason", ""),
    }
