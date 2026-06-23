from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import socket
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session, aliased

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
    SOURCE_KIND_TENDERPLAN_NOTICE,
    classify_source_url,
    fetch_source_context_sync,
    source_label,
)
from .models import parse_json_dict
from .procurement_report import generate_procurement_report
from .quote_request import build_quote_request_markdown_with_ai
from .repository import get_or_create_settings
from .report_builder import write_evidence, write_procurement_docx, write_quote_request_docx, write_supplier_xlsx, zip_paths
from .supplier_search import discover_suppliers, extract_supplier_search_context
from .tenderplan import TenderplanDownloadedFile, fetch_tenderplan_source_sync

_RUNNING: set[str] = set()
_CANCELLED: set[str] = set()
TERMINAL_JOB_STATUSES = {
    "completed",
    "partial",
    "needs_review",
    "failed",
    "cancelled",
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
RESULT_STEM_MAX_BYTES = 150
RESULT_STEM_MAX_CHARS = 56
SUPPLIER_EXCLUSIONS_FILENAME = "excluded_suppliers.json"
logger = logging.getLogger(__name__)


class JobCancelledError(RuntimeError):
    """Raised when a running job was cancelled by a user or admin."""


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
    normalized_sources = _normalized_job_sources(sources or [])
    if mode == MODE_SUPPLIER_SEARCH and normalized_sources:
        raise ValueError(
            "Режим поиска поставщиков принимает только файл или текст ТЗ. "
            "Номер извещения или ссылку закупки отправьте в режим анализа закупки или анализа + поставщики."
        )
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
    for source in normalized_sources:
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


def write_supplier_exclusions(job: Job, *, previous_job_id: str, suppliers: list[dict]) -> Path:
    input_dir = job_dir(job.id) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    path = input_dir / SUPPLIER_EXCLUSIONS_FILENAME
    payload = {
        "previous_job_id": previous_job_id,
        "suppliers": [item for item in suppliers if isinstance(item, dict)],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _load_supplier_exclusions(job: Job) -> list[dict]:
    path = job_dir(job.id) / "input" / SUPPLIER_EXCLUSIONS_FILENAME
    if not path.exists():
        return []
    payload = parse_json_dict(path.read_text(encoding="utf-8"))
    suppliers = payload.get("suppliers")
    if not isinstance(suppliers, list):
        return []
    return [item for item in suppliers if isinstance(item, dict)]


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
    eligible_status_filter = or_(
        Job.status == "pending",
        and_(Job.status == "running", Job.updated_at < stale_cutoff),
    )
    fair_client_filter = _client_has_no_active_running_job_filter(stale_cutoff)
    jobs = (
        db.query(Job)
        .filter(eligible_status_filter)
        .filter(fair_client_filter)
        .order_by(Job.created_at.asc())
        .limit(100)
        .all()
    )
    for job in jobs:
        if job.status == "pending" or should_requeue_stale_job(job.status, job.updated_at, now, stale_after):
            claim_query = db.query(Job).filter(Job.id == job.id).filter(
                eligible_status_filter,
                fair_client_filter,
            )
            rows = claim_query.update(
                {
                    Job.status: "running",
                    Job.progress: 0,
                    Job.message: "Задача взята в обработку",
                    Job.error: "",
                    Job.updated_at: now,
                },
                synchronize_session=False,
            )
            if rows:
                db.commit()
                return job.id
            db.rollback()
    return None


def _active_client_job_exists(stale_cutoff: datetime):
    active_job = aliased(Job)
    return exists().where(
        and_(
            active_job.client_id == Job.client_id,
            active_job.id != Job.id,
            active_job.status == "running",
            or_(active_job.updated_at.is_(None), active_job.updated_at >= stale_cutoff),
        )
    )


def _client_has_no_active_running_job_filter(stale_cutoff: datetime):
    return or_(Job.client_id.is_(None), ~_active_client_job_exists(stale_cutoff))


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


def _normalized_worker_concurrency(value: int | str | None) -> int:
    try:
        parsed = int(value or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, parsed)


def _claim_job_for_worker(worker_id: str) -> str | None:
    db = SessionLocal()
    try:
        expire_stale_confirmations(db)
        return claim_next_job(db, worker_id=worker_id)
    finally:
        db.close()


def _fill_worker_slots(running_tasks: set[asyncio.Task[None]], *, worker_id: str, concurrency: int) -> int:
    claimed = 0
    while len(running_tasks) < concurrency:
        job_id = _claim_job_for_worker(worker_id)
        if not job_id:
            break
        running_tasks.add(asyncio.create_task(process_job(job_id)))
        claimed += 1
    return claimed


def _consume_finished_worker_tasks(tasks: set[asyncio.Task[None]]) -> None:
    for task in tasks:
        try:
            task.result()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker task failed")


async def worker_loop(*, poll_interval: float = WORKER_POLL_INTERVAL_SECONDS, concurrency: int | None = None) -> None:
    init_worker_database()
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    worker_concurrency = _normalized_worker_concurrency(concurrency if concurrency is not None else config.worker_concurrency)
    running_tasks: set[asyncio.Task[None]] = set()
    while True:
        finished = {task for task in running_tasks if task.done()}
        if finished:
            running_tasks.difference_update(finished)
            _consume_finished_worker_tasks(finished)

        claimed = _fill_worker_slots(running_tasks, worker_id=worker_id, concurrency=worker_concurrency)
        if running_tasks:
            timeout = 0 if claimed else poll_interval
            done, _pending = await asyncio.wait(running_tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            if done:
                running_tasks.difference_update(done)
                _consume_finished_worker_tasks(done)
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
        _CANCELLED.discard(job_id)


def cancel_running_job(job_id: str) -> None:
    """Mark a job as cancelled so the worker aborts processing."""
    _CANCELLED.add(job_id)
    _RUNNING.discard(job_id)


def _check_cancelled(job_id: str, db: Session | None = None, job: Job | None = None) -> None:
    """Raise if the job has been cancelled — call from worker threads."""
    if job_id in _CANCELLED:
        _CANCELLED.discard(job_id)
        raise JobCancelledError("Задача отменена")
    if db is not None:
        current = job or db.get(Job, job_id)
        if current is not None:
            try:
                db.refresh(current, attribute_names=["status"])
            except TypeError:
                db.refresh(current)
            if current.status == "cancelled":
                raise JobCancelledError("Задача отменена")


def _set_job(db: Session, job: Job, *, status: str | None = None, progress: int | None = None, message: str | None = None, error: str | None = None) -> None:
    _check_cancelled(str(job.id), db=db, job=job)
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
        _check_cancelled(job_id)
        job = db.get(Job, job_id)
        if not job:
            return
        _check_cancelled(job_id, db=db, job=job)
        settings = get_or_create_settings(db)
        stage = "extract_documents"
        _set_job(db, job, status="running", progress=3, message="Начинаю обработку документов")
        parsed: list[tuple[str, str]] = []
        source_blocks: list[str] = []
        source_count = len(job.sources)
        for index, source in enumerate(job.sources, start=1):
            _check_cancelled(job_id)
            stage = "extract_sources"
            label = "номер извещения" if source.kind == SOURCE_KIND_TENDERPLAN_NOTICE else "ссылку закупки"
            _set_job(db, job, status="running", progress=3 + int(5 * (index - 1) / max(1, source_count)), message=f"Читаю {label}: {index}/{source_count}")
            if source.kind == SOURCE_KIND_TENDERPLAN_NOTICE:
                result = fetch_tenderplan_source_sync(source.value)
                source.parse_status = result.status
                source.extracted_chars = len(result.context)
                source.error = result.error
                if result.context:
                    _update_job_title_from_source_context(job, result.context)
                    context_path = _persist_source_context(job, index, source.kind, result.context)
                    source.context_path = str(context_path)
                    source_blocks.append(result.context)
                if result.downloaded_files:
                    _store_tenderplan_downloaded_files(db, job, result.downloaded_files)
                    db.expire(job, ["files"])
            else:
                result = fetch_source_context_sync(source.kind, source.value)
                source.parse_status = result.status
                source.extracted_chars = result.extracted_chars
                source.error = result.error
                if result.context:
                    _update_job_title_from_source_context(job, result.context)
                    context_path = _persist_source_context(job, index, source.kind, result.context)
                    source.context_path = str(context_path)
                    source_blocks.append(result.context)
                if result.downloaded_files:
                    _store_tenderplan_downloaded_files(db, job, result.downloaded_files)
                    db.expire(job, ["files"])
            db.commit()

        document_options = parse_json_dict(settings.document_settings_json)
        total_files = max(1, len(job.files))
        for index, file in enumerate(job.files, start=1):
            _check_cancelled(job_id)
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
    except JobCancelledError as exc:
        job = db.get(Job, job_id)
        if job:
            release_job_reservation(db, job, note="Резерв возвращён: задача отменена")
            job.status = "cancelled"
            job.progress = 100
            job.message = str(exc)
            job.error = ""
            job.completed_at = now_utc()
            job.updated_at = now_utc()
            db.commit()
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
        "files": _job_files_evidence(job),
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


def _job_files_evidence(job: Job) -> list[dict]:
    files = getattr(job, "files", []) or []
    result: list[dict] = []
    for file in files:
        result.append(
            {
                "filename": getattr(file, "original_filename", ""),
                "parse_status": getattr(file, "parse_status", ""),
                "extracted_chars": getattr(file, "extracted_chars", 0),
                "error": getattr(file, "error", ""),
            }
        )
    return result


GENERIC_SOURCE_TITLE_RE = re.compile(
    r"^(?:закупка\s+\d{11,19}|номер извещения|документация|source-only|"
    r"(?:tenderplan|тендер\s*план|тендерплан)\s*(?:[-:]\s*)?(?:номер извещения)?)$",
    re.I,
)


def _is_generic_source_title(value: object) -> bool:
    text = _clean_label(value).lower()
    if not text or GENERIC_SOURCE_TITLE_RE.fullmatch(text):
        return True
    has_notice_phrase = "номер извещения" in text
    has_internal_brand = "tender" in text or "тендер" in text or "tande" in text
    return has_notice_phrase and has_internal_brand


def _extract_title_from_source_context(context: str) -> str:
    text = str(context or "")
    patterns = (
        r"(?m)^\s*-\s*Наименование\s*:\s*(.+)$",
        r"(?mi)^\s*(?:предмет|объект)\s+закупк[ии]\s*[:\-]\s*(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = _short_label(match.group(1), limit=120)
        if value and not _is_generic_source_title(value):
            return value
    return ""


def _update_job_title_from_source_context(job: Job, context: str) -> None:
    title = _extract_title_from_source_context(context)
    has_uploaded_files = bool(getattr(job, "files", []) or [])
    if title and (_is_generic_source_title(job.title) or not has_uploaded_files):
        job.title = title


def _persist_source_context(job: Job, index: int, kind: str, context: str) -> Path:
    source_dir = job_dir(job.id) / "input" / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    context_path = source_dir / f"{index:02d}_{kind}.txt"
    context_path.write_text(context, encoding="utf-8")
    return context_path


def _store_tenderplan_downloaded_files(db: Session, job: Job, files: list[TenderplanDownloadedFile]) -> None:
    input_dir = job_dir(job.id) / "input" / "tenderplan"
    input_dir.mkdir(parents=True, exist_ok=True)
    existing_names = {Path(str(item.stored_path)).name for item in getattr(job, "files", []) or []}
    for index, downloaded in enumerate(files, start=1):
        safe_name = document_parser.sanitize_filename(downloaded.filename)
        stored_name = f"{index:02d}_{safe_name}"
        while stored_name in existing_names:
            stored_name = f"{index:02d}_{len(existing_names) + 1}_{safe_name}"
        existing_names.add(stored_name)
        stored_path = input_dir / stored_name
        stored_path.write_bytes(downloaded.content)
        db.add(JobFile(job_id=job.id, original_filename=downloaded.filename, stored_path=str(stored_path)))
    job.file_count = int(job.file_count or 0) + len(files)


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
    if title and not _is_generic_source_title(title):
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
    if item:
        return f"Анализ документации: {item}"
    return f"Анализ документации: {source}" if source else "Анализ документации"


def _set_customer_job_title_from_subject(job: Job, subject: str) -> None:
    item = _short_label(subject)
    if not item:
        return
    if job.mode == MODE_PROCUREMENT_REPORT:
        job.title = f"Анализ закупки: {item}"
    elif job.mode == MODE_ANALYSIS_AND_SUPPLIERS:
        job.title = f"Анализ + поиск: {item}"
    elif job.mode == MODE_SUPPLIER_SEARCH:
        job.title = f"ТЗ: {item}"


def _result_stem(job: Job, subject: str) -> str:
    source = _source_title(job)
    item = _short_label(subject)
    base = item or source
    base = _strip_generated_output_suffixes(base)
    base = re.sub(r"\b([Дд])\s+(\d{1,3})\s+(\d{1,2})(?=\s+(?:ГОСТ|ТУ|и|$))", r"\1 \2,\3", base)
    base = re.sub(r"\bГОСТ\s+(\d{3,5})\s+(\d{2,4})\b", r"ГОСТ \1-\2", base, flags=re.I)
    base = re.sub(r"\bи\s+ещ[её]\s+(\d+)\s+позици[ияй]+\b", r"и ещё \1 поз.", base, flags=re.I)
    base = re.sub(r"[()\[\]{}]+", " ", base)
    base = _sanitize_result_filename_component(base)
    base = _truncate_result_stem(base, RESULT_STEM_MAX_CHARS)
    return _truncate_filename_component(base, RESULT_STEM_MAX_BYTES, fallback="закупка")


def _result_filename(kind: str, stem: str, suffix: str) -> str:
    prefix = {
        "analysis": "Анализ",
        "quote_request": "Запрос КП",
        "suppliers": "Поставщики",
        "archive": "Результаты",
    }.get(kind, "Результат")
    safe_stem = _sanitize_result_filename_component(stem).rstrip(" ._-") or "закупка"
    return f"{prefix} - {safe_stem}{suffix}"


def _strip_generated_output_suffixes(value: str) -> str:
    cleaned = re.sub(r"[_]+", " ", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;\"'")
    suffixes = (
        r"запрос\s*кп",
        r"техническое\s*задание",
        r"анализ",
        r"поставщики",
        r"suppliers?",
        r"quote\s*request",
    )
    changed = True
    while changed and cleaned:
        changed = False
        for suffix in suffixes:
            next_value = re.sub(rf"(?:\s*[-–—]\s*|\s+){suffix}\s*$", "", cleaned, flags=re.I).strip(" .,:;\"'-–—")
            if next_value != cleaned:
                cleaned = next_value
                changed = True
    return cleaned


def _sanitize_result_filename_component(value: str) -> str:
    cleaned = re.sub(r"[_]+", " ", str(value or ""))
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._-")
    return cleaned


def _truncate_filename_component(value: str, max_bytes: int, *, fallback: str) -> str:
    value = str(value or "").strip()
    if len(value.encode("utf-8")) <= max_bytes:
        return value or fallback
    truncated = value.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").rstrip(" ._-")
    return truncated or fallback


def _truncate_result_stem(value: str, max_chars: int) -> str:
    value = str(value or "").strip()
    if len(value) <= max_chars:
        return value
    truncated = value[:max_chars].rsplit(" ", 1)[0].strip(" .,:;_-")
    return truncated or value[:max_chars].strip(" .,:;_-")


def _short_label(value: object, *, limit: int = 80) -> str:
    cleaned = _clean_label(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].strip(" .,:;-")


def _clean_label(value: object) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").replace("_", " ")).strip(" .,:;\"'")
    return cleaned.replace("/", "-").replace("\\", "-")


def _process_supplier_search(db: Session, job: Job, settings, context: str) -> None:
    _check_cancelled(job.id)
    _set_job(db, job, progress=25, message="Запускаю ИИ-поиск поставщиков")

    async def progress_callback(progress: int, message: str) -> None:
        _check_cancelled(job.id)
        _set_job(db, job, status="running", progress=progress, message=message)

    excluded_suppliers = _load_supplier_exclusions(job)
    accepted, evidence = asyncio.run(
        discover_suppliers(
            settings,
            context,
            job.target_suppliers,
            progress_callback=progress_callback,
            excluded_suppliers=excluded_suppliers,
        )
    )
    _check_cancelled(job.id)
    _set_job(db, job, status="running", progress=95, message="Сохраняю проверенных поставщиков")
    _persist_supplier_rows(db, job, accepted)
    job.verified_count = len(accepted)
    _set_job(db, job, status="running", progress=97, message="Формирую Excel и проверочные данные")
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_supplier_evidence(evidence)
    source_title = _source_title(job)
    evidence["subject"] = subject
    evidence["source_title"] = source_title
    evidence["sources"] = _job_sources_evidence(job)
    _set_customer_job_title_from_subject(job, subject)
    if not accepted:
        evidence["output_files"] = []
        evidence_path = write_evidence(out_dir / "evidence.json", evidence)
        job.evidence_path = str(evidence_path)
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

    stem = _result_stem(job, subject)
    xlsx_path = write_supplier_xlsx(
        out_dir / _result_filename("suppliers", stem, ".xlsx"),
        accepted,
        title=job.title,
        subject=subject,
        target=job.target_suppliers,
    )
    quote_markdown = asyncio.run(
        build_quote_request_markdown_with_ai(
            settings,
            context,
            subject=subject,
            procurement_profile=evidence.get("procurement_profile") if isinstance(evidence, dict) else {},
        )
    )
    quote_md_path = out_dir / _result_filename("quote_request", stem, ".md")
    quote_md_path.write_text(quote_markdown, encoding="utf-8")
    quote_docx_path = write_quote_request_docx(
        out_dir / _result_filename("quote_request", stem, ".docx"),
        quote_markdown,
        title="Запрос КП",
    )
    evidence["output_files"] = [
        {"kind": "suppliers", "label": "Поставщики", "path": str(xlsx_path)},
        {
            "kind": "quote_request",
            "label": "Запрос КП",
            "path": str(quote_docx_path),
            "content_path": str(quote_md_path),
        },
    ]
    evidence_path = write_evidence(out_dir / "evidence.json", evidence)
    job.evidence_path = str(evidence_path)
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
    _check_cancelled(job.id)
    _set_job(db, job, progress=45, message="ИИ готовит анализ документации")
    result = asyncio.run(generate_procurement_report(settings, context))
    _check_cancelled(job.id)
    _set_job(db, job, progress=90, message="Формирую отчёт и проверочные данные")
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_report_text(result.report)
    report_title = _analysis_report_title(job, subject)
    source_title = _source_title(job)
    stem = _result_stem(job, subject)
    docx_path = write_procurement_docx(
        out_dir / _result_filename("analysis", stem, ".docx"),
        result.report,
        title=report_title,
    )
    quote_source = f"{result.report}\n\n{context}"
    quote_markdown = asyncio.run(
        build_quote_request_markdown_with_ai(
            settings,
            quote_source,
            subject=subject,
        )
    )
    quote_md_path = out_dir / _result_filename("quote_request", stem, ".md")
    quote_md_path.write_text(quote_markdown, encoding="utf-8")
    quote_docx_path = write_quote_request_docx(
        out_dir / _result_filename("quote_request", stem, ".docx"),
        quote_markdown,
        title="Запрос КП",
    )
    evidence_path = write_evidence(
        out_dir / "evidence.json",
        {
            "mode": job.mode,
            "subject": subject,
            "source_title": source_title,
            "sources": _job_sources_evidence(job),
            "files": _job_files_evidence(job),
            "output_files": [
                {"kind": "analysis", "path": str(docx_path)},
                {
                    "kind": "quote_request",
                    "label": "Запрос КП",
                    "path": str(quote_docx_path),
                    "content_path": str(quote_md_path),
                },
            ],
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
    _set_customer_job_title_from_subject(job, subject)
    if result.warning:
        _set_job(
            db,
            job,
            status="needs_review",
            progress=100,
            message="Анализ готов, нужна проверка ИИ-настроек",
            error=result.warning,
        )
    else:
        _set_job(db, job, status="completed", progress=100, message="Анализ документации готов")
    job.completed_at = now_utc()
    db.commit()


def _process_analysis_and_suppliers(db: Session, job: Job, settings, context: str) -> None:
    _check_cancelled(job.id)
    _set_job(db, job, progress=25, message="ИИ готовит анализ документации")
    report = asyncio.run(generate_procurement_report(settings, context))
    _check_cancelled(job.id)
    _set_job(db, job, progress=43, message="Выделяю ТЗ для поиска поставщиков")
    supplier_context = asyncio.run(extract_supplier_search_context(settings, context))
    _check_cancelled(job.id)
    _set_job(db, job, progress=45, message="Ищу поставщиков по ТЗ из документации")

    async def progress_callback(progress: int, message: str) -> None:
        _check_cancelled(job.id)
        mapped_progress = 45 + int(max(0, min(100, progress)) * 0.5)
        _set_job(db, job, status="running", progress=mapped_progress, message=message)

    accepted, supplier_evidence = asyncio.run(
        discover_suppliers(settings, supplier_context, job.target_suppliers, progress_callback=progress_callback)
    )
    _check_cancelled(job.id)
    _set_job(db, job, status="running", progress=96, message="Сохраняю анализ и поставщиков")
    _persist_supplier_rows(db, job, accepted)
    job.verified_count = len(accepted)
    out_dir = job_dir(job.id) / "output"
    subject = _subject_from_supplier_evidence(supplier_evidence) or _subject_from_report_text(report.report)
    stem = _result_stem(job, subject)
    report_title = _analysis_report_title(job, subject)
    docx_path = write_procurement_docx(out_dir / _result_filename("analysis", stem, ".docx"), report.report, title=report_title)
    quote_source = f"{report.report}\n\n{supplier_context}"
    quote_markdown = asyncio.run(
        build_quote_request_markdown_with_ai(
            settings,
            quote_source,
            subject=subject,
            procurement_profile=supplier_evidence.get("procurement_profile") if isinstance(supplier_evidence, dict) else {},
        )
    )
    quote_md_path = out_dir / _result_filename("quote_request", stem, ".md")
    quote_md_path.write_text(quote_markdown, encoding="utf-8")
    quote_docx_path = write_quote_request_docx(out_dir / _result_filename("quote_request", stem, ".docx"), quote_markdown, title="Запрос КП")
    source_title = _source_title(job)
    evidence_payload = {
        "mode": job.mode,
        "subject": subject,
        "source_title": source_title,
        "sources": _job_sources_evidence(job),
        "files": _job_files_evidence(job),
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
            out_dir / _result_filename("suppliers", stem, ".xlsx"),
            accepted,
            title=job.title,
            subject=subject,
            target=job.target_suppliers,
        )
    output_files = [{"kind": "analysis", "path": str(docx_path)}]
    if xlsx_path:
        output_files.append({"kind": "suppliers", "path": str(xlsx_path)})
    output_files.append(
        {
            "kind": "quote_request",
            "label": "Запрос КП",
            "path": str(quote_docx_path),
            "content_path": str(quote_md_path),
        }
    )
    evidence_payload["output_files"] = output_files
    evidence_path = write_evidence(out_dir / "evidence.json", evidence_payload)
    zip_path = zip_paths(out_dir / _result_filename("archive", stem, ".zip"), [Path(item["path"]) for item in output_files])
    job.result_path = str(zip_path)
    job.evidence_path = str(evidence_path)
    _set_customer_job_title_from_subject(job, subject)
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
        _set_job(db, job, status="needs_review", progress=100, message="Анализ и поставщики готовы, нужна проверка ИИ-настроек", error=report.warning)
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
    return [Path(item["path"]) for item in package_job_output_items(job)]


def package_job_output_items(job: Job) -> list[dict]:
    items = _output_file_items_from_evidence(job)
    if items:
        return items
    output = package_job_outputs(job)
    if not output or not output.exists():
        return []
    kind = "analysis" if job.mode == MODE_PROCUREMENT_REPORT else "suppliers"
    label = "Анализ" if kind == "analysis" else "Поставщики"
    return [{"kind": kind, "label": label, "path": str(output)}]


def _output_file_items_from_evidence(job: Job) -> list[dict]:
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
    items: list[dict] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path") or "")).resolve()
        try:
            path.relative_to(out_dir)
        except ValueError:
            continue
        if path.exists():
            kind = str(item.get("kind") or "").strip() or path.stem
            label = str(item.get("label") or "").strip() or {
                "analysis": "Анализ",
                "suppliers": "Поставщики",
                "quote_request": "Запрос КП",
            }.get(kind, kind)
            result = {"kind": kind, "label": label, "path": str(path)}
            content_path = str(item.get("content_path") or "").strip()
            if content_path:
                resolved_content_path = Path(content_path).resolve()
                content_allowed = True
                try:
                    resolved_content_path.relative_to(out_dir)
                except ValueError:
                    content_allowed = False
                if content_allowed and resolved_content_path.exists():
                    result["content_path"] = str(resolved_content_path)
            items.append(result)
    return items


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
