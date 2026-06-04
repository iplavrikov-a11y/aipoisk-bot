from __future__ import annotations

import asyncio
import os
import re
import shutil
import socket
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from . import document_parser
from .billing import (
    KIND_SUPPLIER_SEARCH,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    STATUS_CUSTOMER_DECLINED,
    release_job_kind_reservation,
    release_job_reservation,
    expire_stale_confirmations,
)
from .config import config
from .db import SessionLocal
from .models import Job, JobFile, JobSource, SupplierResult, now_utc
from .procurement_sources import (
    SOURCE_KIND_PROCUREMENT_URL,
    classify_source_url,
    fetch_source_context_sync,
    source_label,
)
from .models import parse_json_dict
from .procurement_report import generate_procurement_report
from .repository import get_or_create_settings
from .report_builder import write_evidence, write_procurement_docx, write_supplier_xlsx, zip_paths
from .supplier_search import discover_suppliers, extract_supplier_search_context

_RUNNING: set[str] = set()
TERMINAL_JOB_STATUSES = {
    "completed",
    "partial",
    "needs_review",
    "failed",
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CUSTOMER_DECLINED,
    STATUS_CONFIRMATION_EXPIRED,
}
STALE_RUNNING_AFTER = timedelta(minutes=30)
WORKER_POLL_INTERVAL_SECONDS = 2.0
MODE_SUPPLIER_SEARCH = "supplier_search"
MODE_PROCUREMENT_REPORT = "procurement_report"
MODE_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"
VALID_JOB_MODES = {MODE_SUPPLIER_SEARCH, MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS}
RESULT_STEM_MAX_BYTES = 220


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
) -> Job:
    work_dir = job_dir("pending")
    work_dir.mkdir(parents=True, exist_ok=True)
    job = Job(
        client_id=client_id,
        created_by_telegram_id=str(created_by_telegram_id or ""),
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
    for source in _normalized_job_sources(sources or []):
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


def claim_next_job(db: Session, *, worker_id: str, stale_after: timedelta = STALE_RUNNING_AFTER) -> str | None:
    now = now_utc()
    stale_cutoff = now - stale_after
    jobs = (
        db.query(Job)
        .filter(
            or_(
                Job.status == "pending",
                and_(Job.status == "running", Job.updated_at < stale_cutoff),
            )
        )
        .order_by(Job.created_at.asc())
        .limit(20)
        .all()
    )
    for job in jobs:
        if job.status == "pending" or should_requeue_stale_job(job.status, job.updated_at, now, stale_after):
            rows = (
                db.query(Job)
                .filter(Job.id == job.id)
                .filter(
                    or_(
                        Job.status == "pending",
                        and_(Job.status == "running", Job.updated_at < stale_cutoff),
                    )
                )
                .update(
                    {
                        Job.status: "running",
                        Job.progress: 0,
                        Job.message: "Задача взята в обработку",
                        Job.error: "",
                        Job.updated_at: now,
                    },
                    synchronize_session=False,
                )
            )
            if rows:
                db.commit()
                return job.id
            db.rollback()
    return None


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


async def worker_loop(*, poll_interval: float = WORKER_POLL_INTERVAL_SECONDS) -> None:
    init_worker_database()
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    while True:
        db = SessionLocal()
        try:
            expire_stale_confirmations(db)
            job_id = claim_next_job(db, worker_id=worker_id)
        finally:
            db.close()
        if job_id:
            await process_job(job_id)
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
    stage = "load_job"
    try:
        job = db.get(Job, job_id)
        if not job:
            return
        settings = get_or_create_settings(db)
        stage = "extract_documents"
        _set_job(db, job, status="running", progress=3, message="Начинаю обработку документов")
        parsed: list[tuple[str, str]] = []
        source_blocks: list[str] = []
        source_count = len(job.sources)
        for index, source in enumerate(job.sources, start=1):
            stage = "extract_sources"
            _set_job(db, job, status="running", progress=3 + int(5 * (index - 1) / max(1, source_count)), message=f"Читаю ссылку закупки: {index}/{source_count}")
            result = fetch_source_context_sync(source.kind, source.value)
            source.parse_status = result.status
            source.extracted_chars = result.extracted_chars
            source.error = result.error
            if result.context:
                source_dir = job_dir(job.id) / "input" / "sources"
                source_dir.mkdir(parents=True, exist_ok=True)
                context_path = source_dir / f"{index:02d}_{source.kind}.txt"
                context_path.write_text(result.context, encoding="utf-8")
                source.context_path = str(context_path)
                source_blocks.append(result.context)
            db.commit()

        document_options = parse_json_dict(settings.document_settings_json)
        total_files = max(1, len(job.files))
        for index, file in enumerate(job.files, start=1):
            _set_job(db, job, status="running", progress=5 + int(10 * (index - 1) / total_files), message=f"Читаю документы: файл {index}/{total_files}")
            text, status = document_parser.extract_text(file.stored_path, document_options)
            file.parse_status = status
            file.extracted_chars = len(text)
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
        else:
            stage = "supplier_search"
            _process_supplier_search(db, job, settings, context)
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
    if title:
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
    if source and item:
        return f"Анализ документации: {source} - {item}"
    return f"Анализ документации: {source}" if source else "Анализ документации"


def _result_stem(job: Job, subject: str) -> str:
    source = _source_title(job)
    item = _short_label(subject)
    base = f"{source} - {item}" if item else source
    base = re.sub(r"[()\[\]{}]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return _truncate_filename_component(document_parser.sanitize_filename(base), RESULT_STEM_MAX_BYTES, fallback="result")


def _truncate_filename_component(value: str, max_bytes: int, *, fallback: str) -> str:
    value = str(value or "").strip()
    if len(value.encode("utf-8")) <= max_bytes:
        return value or fallback
    truncated = value.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").rstrip(" ._-")
    return truncated or fallback


def _short_label(value: object, *, limit: int = 80) -> str:
    cleaned = _clean_label(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].strip(" .,:;-")


def _clean_label(value: object) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;\"'")
    return cleaned.replace("/", "-").replace("\\", "-")


def _process_supplier_search(db: Session, job: Job, settings, context: str) -> None:
    _set_job(db, job, progress=25, message="Запускаю AI-поиск поставщиков")

    async def progress_callback(progress: int, message: str) -> None:
        _set_job(db, job, status="running", progress=progress, message=message)

    accepted, evidence = asyncio.run(discover_suppliers(settings, context, job.target_suppliers, progress_callback=progress_callback))
    _set_job(db, job, status="running", progress=95, message="Сохраняю проверенных поставщиков")
    _persist_supplier_rows(db, job, accepted)
    job.verified_count = len(accepted)
    _set_job(db, job, status="running", progress=97, message="Формирую XLSX и evidence")
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_supplier_evidence(evidence)
    evidence["subject"] = subject
    evidence["source_title"] = _source_title(job)
    evidence["sources"] = _job_sources_evidence(job)
    evidence_path = write_evidence(out_dir / "evidence.json", evidence)
    job.evidence_path = str(evidence_path)
    if not accepted:
        job.result_path = ""
        release_job_reservation(db, job, note="Резерв возвращён: поставщики не найдены")
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
        out_dir / f"{_result_stem(job, subject)}_{job.id[:8]}.xlsx",
        accepted,
        title=job.title,
        subject=subject,
        target=job.target_suppliers,
    )
    job.result_path = str(xlsx_path)
    if len(accepted) >= job.target_suppliers:
        status = "completed"
        message = _supplier_count_message("Готово", len(accepted), job.target_suppliers)
    elif settings.allow_partial_supplier_reports:
        status = STATUS_AWAITING_CUSTOMER_CONFIRMATION
        message = _supplier_count_message("Найдено меньше поставщиков", len(accepted), job.target_suppliers)
    else:
        status = "needs_review"
        message = _supplier_count_message("Нужна ручная проверка", len(accepted), job.target_suppliers)
    _set_job(db, job, status=status, progress=100, message=message, error="")
    job.completed_at = now_utc()
    db.commit()


def _process_procurement_report(db: Session, job: Job, settings, context: str) -> None:
    _set_job(db, job, progress=45, message="AI готовит анализ документации")
    result = asyncio.run(generate_procurement_report(settings, context))
    _set_job(db, job, progress=90, message="Формирую отчёт и evidence")
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_report_text(result.report)
    report_title = _analysis_report_title(job, subject)
    docx_path = write_procurement_docx(
        out_dir / f"{_result_stem(job, subject)}_анализ_{job.id[:8]}.docx",
        result.report,
        title=report_title,
    )
    evidence_path = write_evidence(
        out_dir / "evidence.json",
        {
            "mode": job.mode,
            "subject": subject,
            "source_title": _source_title(job),
            "sources": _job_sources_evidence(job),
            "output_files": [{"kind": "analysis", "path": str(docx_path)}],
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
            message="Анализ готов, нужна проверка AI-настроек",
            error=result.warning,
        )
    else:
        _set_job(db, job, status="completed", progress=100, message="Анализ документации готов")
    job.completed_at = now_utc()
    db.commit()


def _process_analysis_and_suppliers(db: Session, job: Job, settings, context: str) -> None:
    _set_job(db, job, progress=25, message="AI готовит анализ документации")
    report = asyncio.run(generate_procurement_report(settings, context))
    _set_job(db, job, progress=43, message="Выделяю ТЗ для поиска поставщиков")
    supplier_context = asyncio.run(extract_supplier_search_context(settings, context))
    _set_job(db, job, progress=45, message="Ищу поставщиков по ТЗ из документации")

    async def progress_callback(progress: int, message: str) -> None:
        mapped_progress = 45 + int(max(0, min(100, progress)) * 0.5)
        _set_job(db, job, status="running", progress=mapped_progress, message=message)

    accepted, supplier_evidence = asyncio.run(
        discover_suppliers(settings, supplier_context, job.target_suppliers, progress_callback=progress_callback)
    )
    _set_job(db, job, status="running", progress=96, message="Сохраняю анализ и поставщиков")
    _persist_supplier_rows(db, job, accepted)
    job.verified_count = len(accepted)
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_supplier_evidence(supplier_evidence) or _subject_from_report_text(report.report)
    stem = _result_stem(job, subject)
    report_title = _analysis_report_title(job, subject)
    docx_path = write_procurement_docx(out_dir / f"{stem}_анализ_{job.id[:8]}.docx", report.report, title=report_title)
    evidence_payload = {
        "mode": job.mode,
        "subject": subject,
        "source_title": _source_title(job),
        "sources": _job_sources_evidence(job),
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
    xlsx_path = None
    if accepted:
        xlsx_path = write_supplier_xlsx(
            out_dir / f"{stem}_поставщики_{job.id[:8]}.xlsx",
            accepted,
            title=job.title,
            subject=subject,
            target=job.target_suppliers,
        )
    output_files = [{"kind": "analysis", "path": str(docx_path)}]
    if xlsx_path:
        output_files.append({"kind": "suppliers", "path": str(xlsx_path)})
    evidence_payload["output_files"] = output_files
    evidence_path = write_evidence(out_dir / "evidence.json", evidence_payload)
    zip_path = zip_paths(out_dir / f"{stem}_{job.id[:8]}.zip", [Path(item["path"]) for item in output_files])
    job.result_path = str(zip_path)
    job.evidence_path = str(evidence_path)
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
            message="Анализ готов, поставщики не подтверждены",
            error="Поиск не сформировал XLSX, потому что нет ни одного подтверждённого поставщика.",
        )
    elif report.warning:
        _set_job(db, job, status="needs_review", progress=100, message="Анализ и поставщики готовы, нужна проверка AI-настроек", error=report.warning)
    elif len(accepted) >= job.target_suppliers:
        _set_job(db, job, status="completed", progress=100, message=_supplier_count_message("Анализ готов", len(accepted), job.target_suppliers), error="")
    else:
        _set_job(
            db,
            job,
            status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
            progress=100,
            message=_supplier_count_message("Анализ готов, найдено меньше поставщиков", len(accepted), job.target_suppliers),
            error="",
        )
    job.completed_at = now_utc()
    db.commit()


def _supplier_count_message(prefix: str, count: int, target: int) -> str:
    return f"{prefix}: найдено и проверено {count}"


def package_job_outputs(job: Job) -> Path | None:
    if job.result_path:
        result_path = Path(job.result_path)
        if result_path.exists():
            return result_path
    return None


def package_job_output_files(job: Job) -> list[Path]:
    if job.mode == MODE_ANALYSIS_AND_SUPPLIERS:
        paths = _output_files_from_evidence(job)
        if paths:
            return paths
    output = package_job_outputs(job)
    return [output] if output and output.exists() else []


def _output_files_from_evidence(job: Job) -> list[Path]:
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
    out_dir = job_dir(job.id).resolve() / "output"
    paths: list[Path] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path") or "")).resolve()
        try:
            path.relative_to(out_dir)
        except ValueError:
            continue
        if path.exists():
            paths.append(path)
    return paths


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
                    Job.status.in_(["completed", "partial", "needs_review", STATUS_CUSTOMER_DECLINED, STATUS_CONFIRMATION_EXPIRED]),
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
