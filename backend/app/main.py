from __future__ import annotations

from pathlib import Path

import time

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .ai import call_llm
from .config import config
from .db import db_session, init_db
from .jobs import cleanup_expired_jobs, create_job, enqueue_job, package_job_outputs, recover_interrupted_jobs
from .models import Client, Job, JobFile, SupplierResult
from .repository import client_access_error, get_or_create_settings, seed_owner_client
from .schemas import AiTestRequest, ClientCreate, ClientPatch, LoginRequest, ManualJobCreate, SettingsPatch
from .security import (
    ADMIN_COOKIE,
    admin_cookie_max_age,
    check_admin_credentials,
    create_admin_session,
    require_admin,
    verify_admin_session,
)

app = FastAPI(title="AI Poisk Bot", version="0.1.0")
VALID_JOB_MODES = {"supplier_search", "procurement_report"}
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


@app.get("/api/settings", dependencies=[Depends(require_admin)])
def get_settings_api(db: Session = Depends(db_session)) -> dict:
    return get_or_create_settings(db).to_dict(include_secrets=False)


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
    return {"success": True, "settings": settings.to_dict(include_secrets=False)}


@app.get("/api/clients", dependencies=[Depends(require_admin)])
def list_clients(db: Session = Depends(db_session)) -> list[dict]:
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    return [client_to_dict(client) for client in clients]


@app.post("/api/clients", dependencies=[Depends(require_admin)])
def create_client(data: ClientCreate, db: Session = Depends(db_session)) -> dict:
    existing = db.query(Client).filter(Client.telegram_id == data.telegram_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Client with this Telegram ID already exists")
    client = Client(**data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client_to_dict(client)


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
    return client_to_dict(client)


@app.get("/api/jobs", dependencies=[Depends(require_admin)])
def list_jobs(db: Session = Depends(db_session)) -> list[dict]:
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(200).all()
    return [job_to_dict(job) for job in jobs]


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
    db: Session = Depends(db_session),
) -> dict:
    if mode not in VALID_JOB_MODES:
        raise HTTPException(status_code=400, detail="Unknown job mode")
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one document")
    client = db.query(Client).filter(Client.telegram_id == telegram_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    settings = get_or_create_settings(db)
    access_error = client_access_error(db, client, mode, incoming_file_count=len(files))
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
    title = Path(files[0].filename).stem if files else "manual job"
    job = create_job(
        db,
        client_id=client.id,
        mode=mode,
        title=title,
        target_suppliers=settings.default_supplier_target,
        files=payload,
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


def client_to_dict(client: Client) -> dict:
    return {
        "id": client.id,
        "telegram_id": client.telegram_id,
        "name": client.name,
        "username": client.username,
        "is_active": client.is_active,
        "access_until": client.access_until,
        "allowed_supplier_search": client.allowed_supplier_search,
        "allowed_procurement_report": client.allowed_procurement_report,
        "monthly_job_limit": client.monthly_job_limit,
        "monthly_file_limit": client.monthly_file_limit,
        "notes": client.notes,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


def job_to_dict(job: Job, include_files: bool = False) -> dict:
    data = {
        "id": job.id,
        "client_id": job.client_id,
        "client_name": job.client.name if job.client else "",
        "telegram_id": job.client.telegram_id if job.client else "",
        "mode": job.mode,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "title": job.title,
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
    }
