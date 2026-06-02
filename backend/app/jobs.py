from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from . import document_parser
from .config import config
from .db import SessionLocal
from .models import Job, JobFile, SupplierResult, now_utc
from .models import parse_json_dict
from .procurement_report import generate_procurement_report
from .repository import get_or_create_settings
from .report_builder import write_evidence, write_procurement_docx, write_supplier_xlsx
from .supplier_search import discover_suppliers

_RUNNING: set[str] = set()
TERMINAL_JOB_STATUSES = {"completed", "partial", "needs_review", "failed"}
STALE_RUNNING_AFTER = timedelta(minutes=30)


def job_dir(job_id: str) -> Path:
    return config.storage_path / "jobs" / job_id


def create_job(
    db: Session,
    *,
    client_id: str | None,
    mode: str,
    title: str,
    target_suppliers: int,
    files: list[tuple[str, bytes]],
) -> Job:
    work_dir = job_dir("pending")
    work_dir.mkdir(parents=True, exist_ok=True)
    job = Job(
        client_id=client_id,
        mode=mode,
        title=title,
        target_suppliers=target_suppliers,
        status="pending",
        message="Задача создана",
        file_count=len(files),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    actual_dir = job_dir(job.id)
    actual_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files:
        safe_name = document_parser.sanitize_filename(filename)
        stored_path = actual_dir / "input" / safe_name
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(content)
        db.add(JobFile(job_id=job.id, original_filename=filename, stored_path=str(stored_path)))
    db.commit()
    db.refresh(job)
    return job


def enqueue_job(job_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(process_job(job_id))
    except RuntimeError:
        asyncio.run(process_job(job_id))


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


async def process_job(job_id: str) -> None:
    if job_id in _RUNNING:
        return
    _RUNNING.add(job_id)
    try:
        await asyncio.to_thread(_process_job_sync, job_id)
    finally:
        _RUNNING.discard(job_id)


def _set_job(db: Session, job: Job, *, status: str | None = None, progress: int | None = None, message: str | None = None, error: str | None = None) -> None:
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


def _process_job_sync(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return
        settings = get_or_create_settings(db)
        _set_job(db, job, status="running", progress=5, message="Извлекаю текст из документов")
        parsed: list[tuple[str, str]] = []
        document_options = parse_json_dict(settings.document_settings_json)
        for file in job.files:
            text, status = document_parser.extract_text(file.stored_path, document_options)
            file.parse_status = status
            file.extracted_chars = len(text)
            if not text.strip() and status != "ok":
                file.error = status
            parsed.append((file.original_filename, text))
        db.commit()

        context = document_parser.combined_document_context(parsed)
        if len(context.strip()) < 50:
            _set_job(
                db,
                job,
                status="failed",
                progress=100,
                message="Текст документов не извлечён",
                error="Документы не прочитались или формат пока не подключён.",
            )
            job.completed_at = now_utc()
            db.commit()
            return

        if job.mode == "procurement_report":
            _process_procurement_report(db, job, settings, context)
        else:
            _process_supplier_search(db, job, settings, context)
    except Exception as exc:
        job = db.get(Job, job_id)
        if job:
            _set_job(db, job, status="failed", progress=100, message="Ошибка обработки", error=str(exc))
            job.completed_at = now_utc()
            db.commit()
    finally:
        db.close()


def _process_supplier_search(db: Session, job: Job, settings, context: str) -> None:
    _set_job(db, job, progress=25, message="Ищу поставщиков через web-поиск и проверяю официальные сайты")
    accepted, evidence = asyncio.run(discover_suppliers(settings, context, job.target_suppliers))
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
            )
        )
    db.commit()
    job.verified_count = len(accepted)
    out_dir = job_dir(job.id) / "output"
    evidence_path = write_evidence(out_dir / "evidence.json", evidence)
    job.evidence_path = str(evidence_path)
    if not accepted:
        job.result_path = ""
        _set_job(
            db,
            job,
            status="failed",
            progress=100,
            message="Поставщики не найдены: подтверждённых официальных сайтов с контактами 0",
            error="Поиск не сформировал XLSX, потому что нет ни одного подтверждённого поставщика.",
        )
        job.completed_at = now_utc()
        db.commit()
        return

    xlsx_path = write_supplier_xlsx(
        out_dir / f"{job.title or 'supplier_report'}_{job.id[:8]}.xlsx",
        accepted,
        title=job.title,
        target=job.target_suppliers,
    )
    job.result_path = str(xlsx_path)
    if len(accepted) >= job.target_suppliers:
        status = "completed"
        message = f"Готово: найдено и проверено {len(accepted)}/{job.target_suppliers}"
    elif settings.allow_partial_supplier_reports:
        status = "partial"
        message = f"Частично готово: найдено и проверено {len(accepted)}/{job.target_suppliers}"
    else:
        status = "needs_review"
        message = f"Нужна ручная проверка: найдено и проверено {len(accepted)}/{job.target_suppliers}"
    _set_job(db, job, status=status, progress=100, message=message, error="")
    job.completed_at = now_utc()
    db.commit()


def _process_procurement_report(db: Session, job: Job, settings, context: str) -> None:
    _set_job(db, job, progress=45, message="Готовлю Word-отчёт без ATI")
    result = asyncio.run(generate_procurement_report(settings, context))
    out_dir = job_dir(job.id) / "output"
    docx_path = write_procurement_docx(out_dir / f"{job.title or 'procurement_report'}_{job.id[:8]}.docx", result.report, title=job.title)
    evidence_path = write_evidence(
        out_dir / "evidence.json",
        {
            "mode": job.mode,
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
    if result.warning:
        _set_job(
            db,
            job,
            status="needs_review",
            progress=100,
            message="Word-черновик готов, нужна проверка AI-настроек",
            error=result.warning,
        )
    else:
        _set_job(db, job, status="completed", progress=100, message="Word-отчёт готов")
    job.completed_at = now_utc()
    db.commit()


def package_job_outputs(job: Job) -> Path | None:
    if job.result_path:
        result_path = Path(job.result_path)
        if result_path.exists():
            return result_path
    return None


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
                and_(
                    Job.status.in_(["completed", "partial", "needs_review"]),
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
        shutil.rmtree(job_dir(job.id), ignore_errors=True)
        db.delete(job)
    if expired:
        db.commit()
    return len(expired)


def clear_storage() -> None:
    shutil.rmtree(config.storage_path, ignore_errors=True)
    config.storage_path.mkdir(parents=True, exist_ok=True)
