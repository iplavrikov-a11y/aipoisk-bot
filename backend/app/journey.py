from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .billing import client_uses_trial_access
from .models import Client, Job, OnboardingReminder, SystemSettings, UserJourneyEvent, now_utc

logger = logging.getLogger(__name__)

ALLOWED_EVENTS = {
    "account_created",
    "bot_started",
    "create_opened",
    "mode_selected",
    "input_added",
    "launch_attempted",
    "launch_blocked",
    "job_created",
    "link_requested",
    "link_succeeded",
    "link_conflict",
    "onboarding_reminder_sent",
    "registry_fallback_offered",
    "registry_fallback_accepted",
    "registry_fallback_declined",
    "registry_fallback_expired",
    "registry_fallback_delivered",
    "registry_fallback_delivery_expired",
}
ALLOWED_CHANNELS = {"telegram", "web"}


def record_journey_event(
    db: Session,
    client_id: str | None,
    *,
    channel: str,
    event_name: str,
    actor_ref: str = "",
    mode: str = "",
    outcome: str = "",
    reason_code: str = "",
) -> bool:
    if event_name not in ALLOWED_EVENTS or channel not in ALLOWED_CHANNELS:
        return False
    if not all(hasattr(db, attribute) for attribute in ("query", "add", "commit")):
        return False
    try:
        cutoff = now_utc() - timedelta(seconds=5)
        duplicate = (
            db.query(UserJourneyEvent.id)
            .filter(
                UserJourneyEvent.client_id == client_id,
                UserJourneyEvent.channel == channel,
                UserJourneyEvent.event_name == event_name,
                UserJourneyEvent.mode == str(mode or "")[:40],
                UserJourneyEvent.outcome == str(outcome or "")[:40],
                UserJourneyEvent.reason_code == str(reason_code or "")[:80],
                UserJourneyEvent.created_at >= cutoff,
            )
            .first()
        )
        if duplicate:
            return False
        db.add(
            UserJourneyEvent(
                client_id=client_id,
                channel=channel,
                actor_ref=str(actor_ref or "")[:64],
                event_name=event_name,
                mode=str(mode or "")[:40],
                outcome=str(outcome or "")[:40],
                reason_code=str(reason_code or "")[:80],
            )
        )
        db.commit()
        return True
    except Exception as exc:
        rollback = getattr(db, "rollback", None)
        if callable(rollback):
            rollback()
        logger.warning("Journey event was skipped: %s", exc)
        return False


def client_journey_summary(db: Session, client_id: str) -> dict:
    last = (
        db.query(UserJourneyEvent)
        .filter(UserJourneyEvent.client_id == client_id)
        .order_by(UserJourneyEvent.created_at.desc())
        .first()
    )
    return {
        "last_event": last.event_name if last else "",
        "last_channel": last.channel if last else "",
        "last_mode": last.mode if last else "",
        "last_outcome": last.outcome if last else "",
        "last_reason_code": last.reason_code if last else "",
        "last_event_at": last.created_at.isoformat() if last and last.created_at else None,
    }


def _parse_rollout_at(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def reminder_candidates(
    db: Session,
    settings: SystemSettings,
    *,
    hours: int = 24,
    max_hours: int = 72,
    current_time: datetime | None = None,
) -> list[tuple[Client, str]]:
    if not bool(settings.onboarding_reminders_enabled):
        return []
    rollout_at = _parse_rollout_at(settings.onboarding_reminders_rollout_at)
    if rollout_at is None:
        return []
    now = current_time or now_utc()
    moscow_hour = now.astimezone(ZoneInfo("Europe/Moscow")).hour
    if moscow_hour < 9 or moscow_hour >= 20:
        return []
    cutoff = now - timedelta(hours=max(1, hours))
    oldest = now - timedelta(hours=max(hours + 1, max_hours))
    started_client_ids = {
        row[0]
        for row in db.query(UserJourneyEvent.client_id)
        .filter(
            UserJourneyEvent.event_name == "bot_started",
            UserJourneyEvent.channel == "telegram",
            UserJourneyEvent.created_at <= cutoff,
            UserJourneyEvent.created_at >= max(rollout_at, oldest),
            UserJourneyEvent.client_id.is_not(None),
        )
        .distinct()
        .all()
    }
    if not started_client_ids:
        return []
    reminded_client_ids = {row[0] for row in db.query(OnboardingReminder.client_id).filter(OnboardingReminder.client_id.in_(started_client_ids)).all()}
    clients = (
        db.query(Client)
        .filter(Client.id.in_(started_client_ids - reminded_client_ids), Client.is_active.is_(True))
        .all()
    )
    result: list[tuple[Client, str]] = []
    for client in clients:
        if not client_uses_trial_access(db, client):
            continue
        if db.query(Job.id).filter(Job.client_id == client.id).first():
            continue
        account = next(
            (
                item
                for item in sorted(client.telegram_accounts, key=lambda value: value.created_at)
                if item.is_active and str(item.telegram_id or "").isdigit()
            ),
            None,
        )
        if account:
            result.append((client, account.telegram_id))
    return result


def claim_reminder(db: Session, client_id: str) -> OnboardingReminder | None:
    reminder = OnboardingReminder(client_id=client_id, channel="telegram", status="claimed")
    db.add(reminder)
    try:
        db.commit()
        db.refresh(reminder)
        return reminder
    except IntegrityError:
        db.rollback()
        return None
