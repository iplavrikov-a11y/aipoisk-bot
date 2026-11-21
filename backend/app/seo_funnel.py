from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.orm import Session

from .models import Invoice, Job, SeoEntry, WebUser, YooKassaPayment

ENTRY_COOKIE = "tenderlex_seo_entry"
RETENTION_DAYS = 90
ENTRY_SOURCES = {"google", "yandex", "bing"}
PUBLIC_LANDINGS = {
    "/", "/about", "/analiz-rynka-44-fz", "/analiz-zakupochnoi-dokumentacii", "/api-integracii",
    "/baza-znaniy", "/legal", "/monitoring-cen-postavshchikov-po-tz", "/ocenka-riskov-zakupki",
    "/otrasli", "/personal-data", "/podbor-tovara-i-analogov-po-tz", "/poisk-postavshchikov-dlya-tendera",
    "/poisk-postavshchikov-po-tz", "/poisk-proizvoditeley-po-tz", "/postavshchiki-dlya-zaprosa-kp",
    "/privacy", "/regiony", "/reestr-minpromtorga-v-zakupkah", "/terms", "/zapros-kp-po-tz",
}
PUBLIC_DETAIL_PATH = re.compile(r"/(?:baza-znaniy|otrasli|regiony)/[a-z0-9]+(?:-[a-z0-9]+)*")
ENTRY_TOKEN = re.compile(r"[A-Za-z0-9_-]{32}")
RESULT_STATUSES = {"completed", "partial", "needs_review", "resolved"}
MOSCOW = ZoneInfo("Europe/Moscow")


def _token_hash(token: str) -> str | None:
    if ENTRY_TOKEN.fullmatch(token):
        return hashlib.sha256(token.encode("ascii")).hexdigest()
    return None


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def create_entry(db: Session, source: str, landing: str, now: datetime) -> str | None:
    if source not in ENTRY_SOURCES or len(landing) > 200:
        return None
    if landing not in PUBLIC_LANDINGS and not PUBLIC_DETAIL_PATH.fullmatch(landing):
        return None
    token = secrets.token_urlsafe(24)
    db.add(SeoEntry(token_hash=_token_hash(token), source=source, landing=landing, entered_at=now))
    db.flush()
    return token


def entry_exists(db: Session, token: str, now: datetime) -> bool:
    digest = _token_hash(token)
    return bool(digest and db.scalar(select(SeoEntry.token_hash).where(
        SeoEntry.token_hash == digest, SeoEntry.entered_at > now - timedelta(days=RETENTION_DAYS),
    )))


def attach_registration(db: Session, token: str, user: WebUser) -> bool:
    digest = _token_hash(token)
    if not digest:
        return False
    registered_at = _utc(user.created_at)
    result = db.execute(update(SeoEntry).where(
        SeoEntry.token_hash == digest,
        SeoEntry.user_id.is_(None),
        SeoEntry.entered_at <= registered_at,
        SeoEntry.entered_at > registered_at - timedelta(days=RETENTION_DAYS),
        ~select(SeoEntry.token_hash).where(SeoEntry.user_id == user.id).exists(),
    ).values(user_id=user.id, registered_at=registered_at))
    return result.rowcount == 1


def delete_entry(db: Session, token: str, user_id: str | None) -> int:
    conditions = []
    if digest := _token_hash(token):
        conditions.append(SeoEntry.token_hash == digest)
    if user_id:
        conditions.append(SeoEntry.user_id == user_id)
    return db.query(SeoEntry).filter(or_(*conditions)).delete(synchronize_session=False) if conditions else 0


def prune_entries(db: Session, now: datetime) -> int:
    return db.query(SeoEntry).filter(SeoEntry.entered_at <= now - timedelta(days=RETENTION_DAYS)).delete(synchronize_session=False)


def preserve_expired_job(db: Session, job: Job) -> None:
    if not job.client_id or job.is_admin_rerun:
        return
    entry = db.scalar(select(SeoEntry).join(WebUser).where(
        WebUser.client_id == job.client_id, SeoEntry.registered_at <= job.created_at,
    ).with_for_update(of=SeoEntry))
    if not entry:
        return
    started_at = _utc(job.created_at)
    if entry.archived_task_at is None or started_at < _utc(entry.archived_task_at):
        entry.archived_task_at = started_at
    if job.status in RESULT_STATUSES and job.result_path and job.completed_at:
        result_at = _utc(job.completed_at)
        if entry.archived_result_at is None or result_at < _utc(entry.archived_result_at):
            entry.archived_result_at = result_at


def funnel_report(db: Session, now: datetime, days: int = 28) -> dict:
    today = _utc(now).astimezone(MOSCOW).date()
    start = today - timedelta(days=days)
    start_utc = datetime.combine(start, time.min, MOSCOW).astimezone(timezone.utc)
    end_utc = datetime.combine(today, time.min, MOSCOW).astimezone(timezone.utc)

    jobs = select(Job.id).where(Job.client_id == WebUser.client_id, Job.is_admin_rerun.is_(False),
                               Job.created_at >= SeoEntry.registered_at, Job.created_at <= now)
    result_ready = jobs.where(Job.status.in_(RESULT_STATUSES), Job.result_path != "", Job.completed_at <= now).exists()
    paid_online = select(YooKassaPayment.id).where(
        YooKassaPayment.client_id == WebUser.client_id, YooKassaPayment.status == "succeeded",
        YooKassaPayment.amount_rub > 0, YooKassaPayment.paid_at >= SeoEntry.registered_at, YooKassaPayment.paid_at <= now,
    ).exists()
    paid_invoice = select(Invoice.id).where(
        Invoice.client_id == WebUser.client_id, Invoice.status == "paid", Invoice.amount_rub > 0,
        Invoice.paid_at >= SeoEntry.registered_at, Invoice.paid_at <= now,
    ).exists()
    registered = SeoEntry.registered_at <= now
    milestones = {
        "entries": func.count(SeoEntry.token_hash),
        "registrations": func.sum(case((registered, 1), else_=0)),
        "task_started": func.sum(case((and_(registered, or_(SeoEntry.archived_task_at <= now, jobs.exists())), 1), else_=0)),
        "result_ready": func.sum(case((and_(registered, or_(SeoEntry.archived_result_at <= now, result_ready)), 1), else_=0)),
        "first_payment": func.sum(case((and_(registered, or_(paid_online, paid_invoice)), 1), else_=0)),
    }
    rows = db.execute(select(
        SeoEntry.source, SeoEntry.landing, *(expr.label(key) for key, expr in milestones.items()),
    ).outerjoin(WebUser).where(SeoEntry.entered_at >= start_utc, SeoEntry.entered_at < end_utc)
        .group_by(SeoEntry.source, SeoEntry.landing)
        .order_by(milestones["entries"].desc(), SeoEntry.source, SeoEntry.landing)).mappings().all()
    return {
        "period": {"start_date": start.isoformat(), "end_date": (today - timedelta(days=1)).isoformat(), "timezone": "Europe/Moscow"},
        "observed_at": _utc(now).isoformat(),
        "totals": {key: sum(row[key] for row in rows) for key in milestones},
        "rows": [dict(row) for row in rows],
    }
