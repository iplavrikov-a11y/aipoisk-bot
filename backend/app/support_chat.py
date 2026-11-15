"""
Unified synchronous customer support & omnichannel Telegram bridge for TenderLex.

Channels synchronized through a single DB ledger (`JobChatMessage` + `SupportDialogState`):
- Web cabinet & job-card chat (`/api/customer/chat`, `/api/customer/jobs/{id}/chat`)
- Public landing-page guest chat (`/api/public/guest-chat/*` -> Next.js `/api/chat/*`)
- Admin web panel «Диалоги» (`/api/admin/dialogs`, `/api/admin/clients/{id}/chat`, `/api/jobs/{id}/chat`)
- Option A: Admin personal DM with the Telegram bot (native Reply OR persistent "enter chat" session,
  text + documents + photos, `/dialogs`, `/exit_chat`)
- Option B: Private Telegram Admin Supergroup with Forum Topics (one auto-created Topic per
  client or guest visitor; messages/attachments in both directions stay mirrored & in sync)
- Client support directly inside the Telegram bot (`💬 Написать в поддержку` + Reply)
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .admin_alerts import is_pytest
from .config import config
from .jobs import job_dir
from .models import (
    Client,
    ClientTelegramAccount,
    Job,
    JobChatMessage,
    SupportDialogState,
    SupportGuestSession,
    SupportTelegramMessageMap,
    SupportTelegramSession,
    SystemSettings,
    new_id,
    now_utc,
)
from .repository import get_client_by_telegram_id, get_or_create_trial_client_by_telegram_id

logger = logging.getLogger(__name__)

GUEST_CLIENT_PREFIX = "guest:"
GUEST_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
TELEGRAM_ID_RE = re.compile(r"^-?\d{5,20}$")

DEFAULT_ADMIN_SESSION_TTL_HOURS = 4
DEFAULT_CLIENT_SESSION_TTL_HOURS = 4

GUEST_CHAT_SESSION_WINDOW_SEC = 60
GUEST_CHAT_SESSION_MAX_MESSAGES = 8
GUEST_CHAT_IP_WINDOW_SEC = 60
GUEST_CHAT_IP_MAX_MESSAGES = 12
GUEST_CHAT_IP_SESSION_WINDOW_SEC = 600
GUEST_CHAT_IP_MAX_NEW_SESSIONS = 5

CHAT_ALLOWED_EXTENSIONS = {
    ".docx", ".doc", ".pdf", ".xlsx", ".xls", ".rtf", ".odt",
    ".zip", ".rar", ".7z",
    ".txt", ".csv", ".tsv",
    ".png", ".jpg", ".jpeg", ".webp",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

LEGACY_CHAT_SESSIONS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "chat_sessions.json"

_LEGACY_SKIP_EXACT = {
    "test_sess_valid_1",
    "sess_interactive_test",
    "sess_live_test_001",
    "sess_live_final_test",
    "sqli-test-1",
    "cmdi-test-1",
    "contact-test-1",
    "session-alpha-111",
    "session-beta-222",
    "abc",
    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "sess_admin",
    "sess_mwgvflss_q6vw",
    "0970c55c-5192-4f7a-8c4b-c63a787238d3",
}

_MODE_LABELS = {
    "supplier_search": "Поиск поставщиков",
    "procurement_report": "Анализ закупки",
    "analysis_and_suppliers": "Анализ + поиск",
    "exact_product": "Подбор аналогов",
    "price_monitoring": "Мониторинг цен",
}

_CHANNEL_LABELS = {
    "web": "🌐 Сайт/кабинет",
    "guest_web": "🌐 Чат на сайте",
    "tg_bot": "✈️ Telegram-бот",
    "admin_web": "🖥 Админ-панель",
    "tg_dm": "💬 Админ (ЛС бота)",
    "tg_topic": "🗂 Админ (Группа/Тема)",
    "system": "⚙️ Система",
}

_LEGACY_BULK_IMPORTED = False


def reset_legacy_import_cache_for_tests() -> None:
    global _LEGACY_BULK_IMPORTED
    _LEGACY_BULK_IMPORTED = False


def get_bot_token() -> str:
    return (config.bot_token or os.getenv("AIPOISK_BOT_TOKEN") or "").strip()


def get_system_settings(db: Session) -> SystemSettings | None:
    return db.query(SystemSettings).first()


def parse_telegram_id_list(raw: str | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\s,;]+", str(raw or "").strip()):
        token = part.strip()
        if token and TELEGRAM_ID_RE.match(token) and token not in seen:
            seen.add(token)
            result.append(token)
    return result


def get_authorized_admin_telegram_ids(db: Session, settings: SystemSettings | None = None) -> list[str]:
    cfg_settings = settings or get_system_settings(db)
    raw_candidates = [
        config.owner_telegram_id,
        os.getenv("AIPOISK_OWNER_TELEGRAM_ID", ""),
        config.support_admin_ids,
        os.getenv("AIPOISK_SUPPORT_ADMIN_IDS", ""),
        getattr(cfg_settings, "support_admin_telegram_ids", "") if cfg_settings else "",
    ]
    result: list[str] = []
    seen: set[str] = set()
    for chunk in raw_candidates:
        for uid in parse_telegram_id_list(chunk):
            if uid not in seen and not uid.startswith("-"):
                seen.add(uid)
                result.append(uid)
    return result


def is_admin_telegram_user(db: Session, user_id: int | str | None, settings: SystemSettings | None = None) -> bool:
    uid = str(user_id or "").strip()
    if not uid or not TELEGRAM_ID_RE.match(uid):
        return False
    return uid in get_authorized_admin_telegram_ids(db, settings=settings)


def get_configured_support_group_id(db: Session, settings: SystemSettings | None = None) -> str:
    cfg_settings = settings or get_system_settings(db)
    candidates = [
        getattr(cfg_settings, "support_telegram_group_id", "") if cfg_settings else "",
        config.support_group_id,
        os.getenv("AIPOISK_SUPPORT_GROUP_ID", ""),
    ]
    for raw in candidates:
        val = str(raw or "").strip()
        if val and TELEGRAM_ID_RE.match(val):
            return val
    return ""


def is_support_group_chat(db: Session, chat_id: int | str | None, settings: SystemSettings | None = None) -> bool:
    cid = str(chat_id or "").strip()
    configured = get_configured_support_group_id(db, settings=settings)
    return bool(cid and configured and cid == configured)


def should_mirror_admin_replies_to_bot(db: Session, settings: SystemSettings | None = None) -> bool:
    cfg_settings = settings or get_system_settings(db)
    if cfg_settings is None:
        return True
    val = getattr(cfg_settings, "support_mirror_admin_replies_to_bot", None)
    return True if val is None else bool(val)


def validate_guest_session_id(session_id: str | None) -> str:
    sid = str(session_id or "").strip()
    if not sid or not GUEST_SESSION_RE.match(sid):
        raise ValueError("Некорректный идентификатор сессии чата.")
    return sid


def is_guest_client_id(client_id: str | None) -> bool:
    cid = str(client_id or "").strip()
    if not cid.startswith(GUEST_CLIENT_PREFIX):
        return False
    return bool(GUEST_SESSION_RE.match(cid[len(GUEST_CLIENT_PREFIX) :]))


def extract_guest_session_id(client_id: str | None) -> str:
    cid = str(client_id or "").strip()
    if cid.startswith(GUEST_CLIENT_PREFIX):
        sid = cid[len(GUEST_CLIENT_PREFIX) :]
        if GUEST_SESSION_RE.match(sid):
            return sid
    return ""


def check_guest_chat_rate_limits(
    db: Session,
    *,
    session_id: str,
    client_ip: str = "",
) -> str | None:
    """Enforce per-session and per-IP burst/session-creation limits before persisting a guest message."""
    clean_sid = validate_guest_session_id(session_id)
    now = now_utc()
    cutoff_msg = now - timedelta(seconds=GUEST_CHAT_SESSION_WINDOW_SEC)
    client_key = f"{GUEST_CLIENT_PREFIX}{clean_sid}"

    session_recent_cnt = (
        db.query(func.count(JobChatMessage.id))
        .filter(
            JobChatMessage.client_id == client_key,
            JobChatMessage.sender_role == "client",
            JobChatMessage.created_at >= cutoff_msg,
        )
        .scalar()
        or 0
    )
    if session_recent_cnt >= GUEST_CHAT_SESSION_MAX_MESSAGES:
        return "Слишком много сообщений подряд. Подождите минуту."

    clean_ip = str(client_ip or "").strip()[:64]
    if not clean_ip or clean_ip.lower() == "unknown":
        return None

    ip_cutoff_msg = now - timedelta(seconds=GUEST_CHAT_IP_WINDOW_SEC)
    ip_recent_cnt = (
        db.query(func.count(JobChatMessage.id))
        .join(
            SupportGuestSession,
            JobChatMessage.guest_session_id == SupportGuestSession.session_id,
        )
        .filter(
            SupportGuestSession.client_ip == clean_ip,
            JobChatMessage.sender_role == "client",
            JobChatMessage.created_at >= ip_cutoff_msg,
        )
        .scalar()
        or 0
    )
    if ip_recent_cnt >= GUEST_CHAT_IP_MAX_MESSAGES:
        return "Слишком много сообщений с одного адреса. Подождите минуту."

    existing_session = (
        db.query(SupportGuestSession.id)
        .filter(SupportGuestSession.session_id == clean_sid)
        .first()
    )
    if not existing_session:
        ip_cutoff_session = now - timedelta(seconds=GUEST_CHAT_IP_SESSION_WINDOW_SEC)
        ip_new_sessions = (
            db.query(func.count(SupportGuestSession.id))
            .filter(
                SupportGuestSession.client_ip == clean_ip,
                SupportGuestSession.created_at >= ip_cutoff_session,
            )
            .scalar()
            or 0
        )
        if ip_new_sessions >= GUEST_CHAT_IP_MAX_NEW_SESSIONS:
            return "Слишком много новых обращений с одного адреса. Подождите несколько минут."

    return None


def make_dialog_key(*, client_id: str = "", guest_session_id: str = "") -> str:
    sid = str(guest_session_id or "").strip() or extract_guest_session_id(client_id)
    if sid:
        return f"guest:{sid}"
    cid = str(client_id or "").strip()
    if cid:
        return f"client:{cid}"
    return ""


def _safe_storage_subpath(parts: tuple[str, ...]) -> Path:
    root = Path(config.storage_path).resolve()
    target = root.joinpath(*parts).resolve()
    target.relative_to(root)
    return target


def safe_chat_attachment_dir(*, client_id: str = "", guest_session_id: str = "", job_id: str = "") -> Path:
    clean_job_id = re.sub(r"[^A-Za-z0-9_-]", "", str(job_id or "").strip())
    if clean_job_id:
        base = Path(job_dir(clean_job_id)).resolve()
        target = (base / "chat").resolve()
        root = Path(config.storage_path).resolve()
        target.relative_to(root)
        target.mkdir(parents=True, exist_ok=True)
        return target
    sid = str(guest_session_id or "").strip() or extract_guest_session_id(client_id)
    if sid:
        safe_sid = validate_guest_session_id(sid)
        target = _safe_storage_subpath(("guest_chat", safe_sid))
        target.mkdir(parents=True, exist_ok=True)
        return target
    clean_cid = re.sub(r"[^A-Za-z0-9_-]", "", str(client_id or "").strip())
    if not clean_cid:
        clean_cid = "common"
    target = _safe_storage_subpath(("clients", clean_cid, "chat"))
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_attachment_bytes(
    *,
    filename: str,
    content: bytes,
    client_id: str = "",
    guest_session_id: str = "",
    job_id: str = "",
    prefix: str = "",
    enforce_allowlist: bool = True,
) -> dict[str, Any]:
    raw_name = Path(str(filename or "file")).name.strip() or "file"
    safe_name = re.sub(r"[^\w.\- ()А-Яа-яЁё]", "_", raw_name)[:140] or "file"
    ext = Path(safe_name).suffix.lower()
    if enforce_allowlist and ext not in CHAT_ALLOWED_EXTENSIONS:
        raise ValueError(f"Неподдерживаемый формат файла: {safe_name}")
    if len(content) > 15 * 1024 * 1024:
        raise ValueError(f"Файл {safe_name} превышает допустимый размер 15 МБ.")
    target_dir = safe_chat_attachment_dir(
        client_id=client_id,
        guest_session_id=guest_session_id,
        job_id=job_id,
    )
    prefix_clean = re.sub(r"[^A-Za-z0-9_-]", "", prefix)
    stamp = f"{prefix_clean}_" if prefix_clean else ""
    dest = (target_dir / f"{stamp}{int(time.time())}_{new_id()[:6]}_{safe_name}").resolve()
    dest.relative_to(target_dir.resolve())
    dest.write_bytes(content)
    return {
        "path": str(dest),
        "name": safe_name,
        "label": safe_name,
        "size": len(content),
    }


def _as_naive_utc(dt: datetime | None = None) -> datetime:
    val = dt if dt is not None else now_utc()
    if val.tzinfo is not None:
        return val.astimezone(timezone.utc).replace(tzinfo=None)
    return val


def _parse_iso_naive_utc(raw: str | None) -> datetime:
    text = str(raw or "").strip()
    if not text:
        return _as_naive_utc()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        return _as_naive_utc(dt)
    except Exception:
        return _as_naive_utc()


def _should_skip_legacy_session(session_id: str, payload: dict[str, Any]) -> bool:
    if session_id in _LEGACY_SKIP_EXACT:
        return True
    if session_id.startswith(("pt-", "test_", "session-alpha", "session-beta")):
        return True
    msgs = payload.get("messages") or []
    if not isinstance(msgs, list) or not msgs:
        return True
    if len(session_id) <= 4:
        return True
    return False


def _import_single_legacy_session(db: Session, session_id: str, payload: dict[str, Any]) -> SupportGuestSession | None:
    if not GUEST_SESSION_RE.match(session_id):
        return None
    existing = db.query(SupportGuestSession).filter(SupportGuestSession.session_id == session_id).first()
    if existing:
        return existing

    raw_msgs = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(raw_msgs, list):
        raw_msgs = []
    contact = str((payload or {}).get("contact") or "").strip()[:255]
    created_dt = _parse_iso_naive_utc((payload or {}).get("created"))
    updated_dt = _parse_iso_naive_utc((payload or {}).get("updated") or (payload or {}).get("created"))

    last_sender = str(raw_msgs[-1].get("sender") or "") if raw_msgs and isinstance(raw_msgs[-1], dict) else ""
    last_text = str(raw_msgs[-1].get("text") or "") if raw_msgs and isinstance(raw_msgs[-1], dict) else ""
    is_closed = "Диалог завершен" in last_text or "Диалог завершён" in last_text
    recent_cutoff = _as_naive_utc(now_utc() - timedelta(days=7))

    guest = SupportGuestSession(
        id=new_id(),
        session_id=session_id,
        visitor_name=contact or f"Гость сайта ({session_id[-6:]})",
        visitor_contact=contact,
        status="closed" if is_closed else "open",
        created_at=created_dt,
        updated_at=updated_dt,
    )
    db.add(guest)

    client_key = f"{GUEST_CLIENT_PREFIX}{session_id}"
    last_msg_dt = updated_dt
    for idx, item in enumerate(raw_msgs):
        if not isinstance(item, dict):
            continue
        raw_text = str(item.get("text") or item.get("preset") or "").strip()
        if not raw_text:
            continue
        sender_raw = str(item.get("sender") or "user").strip().lower()
        sender_role = "client" if sender_raw in ("user", "client", "visitor") else "admin"
        msg_dt = _parse_iso_naive_utc(item.get("timestamp"))
        last_msg_dt = msg_dt
        is_last = idx == len(raw_msgs) - 1
        mark_read = True
        if sender_role == "client" and is_last and not is_closed and _as_naive_utc(msg_dt) >= recent_cutoff:
            mark_read = False
        db.add(
            JobChatMessage(
                id=new_id(),
                client_id=client_key,
                guest_session_id=session_id,
                job_id="",
                sender_role=sender_role,
                channel="guest_web" if sender_role == "client" else "admin_web",
                message=raw_text,
                attachments_json="[]",
                is_read_by_client=True,
                is_read_by_admin=mark_read,
                created_at=msg_dt,
            )
        )

    dialog_key = f"guest:{session_id}"
    if not db.query(SupportDialogState).filter(SupportDialogState.dialog_key == dialog_key).first():
        db.add(
            SupportDialogState(
                id=new_id(),
                dialog_key=dialog_key,
                client_id=client_key,
                guest_session_id=session_id,
                topic_title=(f"Гость: {contact}" if contact else f"Гость {session_id[-8:]}")[:120],
                status="closed" if is_closed else "open",
                last_channel="guest_web" if last_sender == "user" else "admin_web",
                last_message_at=last_msg_dt,
            )
        )
    return guest


def ensure_legacy_guest_sessions_imported(
    db: Session,
    *,
    session_id: str | None = None,
    json_path: Path | None = None,
) -> None:
    """Import legacy guest chat sessions from data/chat_sessions.json idempotently."""
    global _LEGACY_BULK_IMPORTED
    if json_path is None and is_pytest():
        return
    target_file = json_path or LEGACY_CHAT_SESSIONS_FILE

    if session_id:
        clean_sid = str(session_id).strip()
        if not GUEST_SESSION_RE.match(clean_sid):
            return
        exists = db.query(SupportGuestSession.id).filter(SupportGuestSession.session_id == clean_sid).first()
        if exists:
            return
        if not target_file.is_file():
            return
        try:
            raw = json.loads(target_file.read_text(encoding="utf-8") or "{}")
            if isinstance(raw, dict) and isinstance(raw.get(clean_sid), dict):
                _import_single_legacy_session(db, clean_sid, raw[clean_sid])
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Failed single legacy guest chat import for %s: %s", clean_sid, exc)
        return

    if _LEGACY_BULK_IMPORTED and json_path is None:
        return
    if not target_file.is_file():
        if json_path is None:
            _LEGACY_BULK_IMPORTED = True
        return
    try:
        raw = json.loads(target_file.read_text(encoding="utf-8") or "{}")
        if not isinstance(raw, dict):
            return
        changed = False
        for sid, payload in raw.items():
            if not isinstance(sid, str) or not isinstance(payload, dict):
                continue
            if _should_skip_legacy_session(sid, payload):
                continue
            if not db.query(SupportGuestSession.id).filter(SupportGuestSession.session_id == sid).first():
                if _import_single_legacy_session(db, sid, payload):
                    changed = True
        if changed:
            db.commit()
        if json_path is None:
            _LEGACY_BULK_IMPORTED = True
    except Exception as exc:
        db.rollback()
        logger.warning("Failed bulk legacy guest chat import: %s", exc)


def get_or_create_guest_session(
    db: Session,
    session_id: str,
    *,
    contact: str = "",
    source_url: str = "",
    client_ip: str = "",
) -> SupportGuestSession:
    clean_sid = validate_guest_session_id(session_id)
    ensure_legacy_guest_sessions_imported(db, session_id=clean_sid)
    guest = db.query(SupportGuestSession).filter(SupportGuestSession.session_id == clean_sid).first()
    clean_contact = str(contact or "").strip()[:255]
    if not guest:
        guest = SupportGuestSession(
            id=new_id(),
            session_id=clean_sid,
            visitor_name=clean_contact or f"Гость сайта ({clean_sid[-6:]})",
            visitor_contact=clean_contact,
            source_url=str(source_url or "").strip()[:512],
            client_ip=str(client_ip or "").strip()[:64],
            status="open",
        )
        db.add(guest)
        db.flush()
    else:
        if clean_contact and clean_contact != guest.visitor_contact:
            guest.visitor_contact = clean_contact
            if guest.visitor_name.startswith("Гость сайта"):
                guest.visitor_name = clean_contact[:120]
        if source_url and not guest.source_url:
            guest.source_url = str(source_url).strip()[:512]
        clean_ip = str(client_ip or "").strip()[:64]
        if clean_ip and not guest.client_ip:
            guest.client_ip = clean_ip
        guest.status = "open"
        guest.updated_at = now_utc()
    return guest


def resolve_or_create_client_for_tg_user(
    db: Session,
    *,
    tg_user_id: str,
    username: str = "",
    full_name: str = "",
) -> tuple[Client | None, SupportGuestSession | None]:
    """Resolve existing client or provision trial client; fall back to tg_* guest session if trials off."""
    client, err = get_or_create_trial_client_by_telegram_id(
        db,
        tg_user_id,
        username=username,
        name=full_name,
    )
    if client and not err:
        return client, None
    client_existing, _ = get_client_by_telegram_id(db, tg_user_id)
    if client_existing:
        return client_existing, None

    guest_sid = f"tg_{tg_user_id}"
    contact_label = f"@{username.lstrip('@')}" if username else f"tg_id:{tg_user_id}"
    visitor_name = full_name or contact_label
    guest = get_or_create_guest_session(db, guest_sid, contact=contact_label)
    if visitor_name and guest.visitor_name != visitor_name:
        guest.visitor_name = visitor_name[:120]
    db.commit()
    return None, guest


def _short_job_label(job: Job | None) -> str:
    if not job:
        return ""
    num = f"#{job.job_number}" if getattr(job, "job_number", None) else f"#{job.id[:6]}"
    title = str(getattr(job, "title", "") or "").strip()
    if title and title not in ("Новая задача", "New task"):
        return f"{num} · {title[:70]}"
    m = _MODE_LABELS.get(str(getattr(job, "mode", "") or ""), str(getattr(job, "mode", "") or ""))
    return f"{num} · {m}" if m else num


def get_client_telegram_targets(db: Session, client: Client | None, job: Job | None = None) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()

    def _add(raw: object) -> None:
        val = str(raw or "").strip()
        if val and re.match(r"^\d{5,20}$", val) and val not in seen:
            seen.add(val)
            targets.append(val)

    if job is not None:
        _add(getattr(job, "created_by_telegram_id", ""))
    if client is not None:
        _add(getattr(client, "telegram_id", ""))
        accounts = (
            db.query(ClientTelegramAccount)
            .filter(
                ClientTelegramAccount.client_id == client.id,
                ClientTelegramAccount.is_active == True,
            )
            .all()
        )
        for acc in accounts:
            _add(acc.telegram_id)
    return targets


def get_or_create_dialog_state(
    db: Session,
    *,
    client_id: str = "",
    guest_session_id: str = "",
    topic_title: str = "",
) -> SupportDialogState:
    sid = str(guest_session_id or "").strip() or extract_guest_session_id(client_id)
    if sid:
        normalized_client_id = f"{GUEST_CLIENT_PREFIX}{sid}"
        dialog_key = f"guest:{sid}"
    else:
        normalized_client_id = str(client_id or "").strip()
        dialog_key = f"client:{normalized_client_id}"

    state = db.query(SupportDialogState).filter(SupportDialogState.dialog_key == dialog_key).first()
    if not state:
        state = SupportDialogState(
            id=new_id(),
            dialog_key=dialog_key,
            client_id=normalized_client_id,
            guest_session_id=sid,
            topic_title=(topic_title or dialog_key)[:120],
            status="open",
        )
        db.add(state)
        db.flush()
    elif topic_title and not state.topic_title:
        state.topic_title = topic_title[:120]
    return state


def get_dialog_profile(
    db: Session,
    *,
    client_id: str = "",
    guest_session_id: str = "",
    job_id: str = "",
) -> dict[str, Any]:
    sid = str(guest_session_id or "").strip() or extract_guest_session_id(client_id)
    target_job = db.get(Job, job_id) if job_id else None

    if sid:
        guest = db.query(SupportGuestSession).filter(SupportGuestSession.session_id == sid).first()
        contact = (guest.visitor_contact if guest else "") or ""
        name = (guest.visitor_name if guest and guest.visitor_name else "") or f"Гость {sid[-6:]}"
        tg_targets: list[str] = []
        if sid.startswith("tg_") and re.match(r"^\d{5,20}$", sid[3:]):
            tg_targets = [sid[3:]]
        topic_title = f"Гость: {contact or name}"[:120]
        if sid.startswith("tg_"):
            topic_title = f"TG {name}"[:120]
        state = get_or_create_dialog_state(
            db,
            client_id=f"{GUEST_CLIENT_PREFIX}{sid}",
            guest_session_id=sid,
            topic_title=topic_title,
        )
        return {
            "dialog_key": state.dialog_key,
            "state": state,
            "is_guest": True,
            "client_id": f"{GUEST_CLIENT_PREFIX}{sid}",
            "guest_session_id": sid,
            "client": None,
            "guest_session": guest,
            "job": None,
            "client_number": None,
            "display_name": name,
            "topic_title": topic_title,
            "email": contact if "@" in contact and not contact.startswith("@") else "",
            "phone": getattr(guest, "visitor_contact", "") if (guest and "@" not in (guest.visitor_contact or "")) else "",
            "contact": contact,
            "tg_username": contact if contact.startswith("@") else "",
            "telegram_targets": tg_targets,
            "job_label": "",
            "jobs_summary": [],
        }

    client = (
        db.query(Client)
        .options(selectinload(Client.web_users), selectinload(Client.jobs))
        .filter(Client.id == client_id)
        .first()
    )
    if not client and target_job and target_job.client_id:
        client = (
            db.query(Client)
            .options(selectinload(Client.web_users), selectinload(Client.jobs))
            .filter(Client.id == target_job.client_id)
            .first()
        )
        client_id = client.id if client else client_id

    name = (client.name if client and client.name else "") or "Клиент"
    num = getattr(client, "client_number", None) if client else None
    email = ""
    phone = getattr(client, "phone", "") if client else ""
    tg_username = getattr(client, "username", "") if client else ""
    if client and client.web_users:
        for wu in client.web_users:
            if wu.email and not email:
                email = wu.email
            if getattr(wu, "phone", "") and not phone:
                phone = wu.phone
            if getattr(wu, "telegram_username", "") and not tg_username:
                tg_username = wu.telegram_username
    tg_handle = f"@{tg_username.lstrip('@')}" if tg_username else ""
    prefix = f"#{num} " if num else ""
    display_name = f"{prefix}{name}".strip()
    topic_extra = tg_handle or email or phone
    topic_title = f"{display_name} ({topic_extra})"[:120] if topic_extra else display_name[:120]

    jobs_summary = []
    if client and client.jobs:
        for j in sorted(
            [item for item in client.jobs if not getattr(item, "is_admin_rerun", False)],
            key=lambda x: x.job_number or 0,
            reverse=True,
        )[:5]:
            jobs_summary.append(_short_job_label(j))

    state = get_or_create_dialog_state(
        db,
        client_id=client_id,
        topic_title=topic_title,
    )
    return {
        "dialog_key": state.dialog_key,
        "state": state,
        "is_guest": False,
        "client_id": client_id,
        "guest_session_id": "",
        "client": client,
        "guest_session": None,
        "job": target_job,
        "client_number": num,
        "display_name": display_name,
        "topic_title": topic_title,
        "email": email,
        "phone": phone or "",
        "contact": phone or email or tg_handle,
        "tg_username": tg_handle,
        "telegram_targets": get_client_telegram_targets(db, client, job=target_job),
        "job_label": _short_job_label(target_job),
        "jobs_summary": jobs_summary,
    }


async def _tg_api_post(
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    file_field: str | None = None,
    file_path: Path | None = None,
    file_name: str | None = None,
    bot_token: str = "",
    allow_in_test: bool = False,
) -> dict[str, Any]:
    if is_pytest() and not allow_in_test:
        return {"ok": False, "skipped_in_test": True}
    token = (bot_token or get_bot_token()).strip()
    if not token:
        return {"ok": False, "description": "Bot token not configured"}

    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            if file_field and file_path and file_path.is_file():
                data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in (payload or {}).items() if v is not None}
                file_bytes = file_path.read_bytes()
                files = {file_field: (file_name or file_path.name, file_bytes)}
                resp = await http_client.post(url, data=data, files=files)
            else:
                resp = await http_client.post(url, json=payload or {})
            try:
                parsed = resp.json()
            except Exception:
                parsed = {"ok": False, "error_code": resp.status_code, "description": resp.text[:300]}
            if not isinstance(parsed, dict):
                return {"ok": False, "description": "Invalid Telegram response"}
            return parsed
    except Exception as exc:
        logger.warning("Telegram API %s failed: %s", method, exc)
        return {"ok": False, "description": str(exc)}


async def _tg_send_attachment(
    *,
    chat_id: str,
    att: dict[str, Any],
    message_thread_id: int | None = None,
    caption_html: str = "",
    reply_markup: dict[str, Any] | None = None,
    allow_in_test: bool = False,
) -> dict[str, Any]:
    raw_path = str(att.get("path") or "").strip()
    if not raw_path:
        return {"ok": False, "description": "Empty attachment path"}
    file_path = Path(raw_path).resolve()
    if not file_path.is_file():
        return {"ok": False, "description": "Attachment file missing"}
    safe_label = str(att.get("name") or att.get("label") or file_path.name)
    is_photo = file_path.suffix.lower() in IMAGE_EXTENSIONS and file_path.stat().st_size <= 9 * 1024 * 1024
    method = "sendPhoto" if is_photo else "sendDocument"
    field = "photo" if is_photo else "document"
    payload: dict[str, Any] = {"chat_id": chat_id}
    if message_thread_id and message_thread_id > 0:
        payload["message_thread_id"] = int(message_thread_id)
    if caption_html:
        payload["caption"] = caption_html[:1000]
        payload["parse_mode"] = "HTML"
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _tg_api_post(
        method,
        payload,
        file_field=field,
        file_path=file_path,
        file_name=safe_label,
        allow_in_test=allow_in_test,
    )


def record_tg_message_map(
    db: Session,
    *,
    tg_chat_id: int | str,
    tg_message_id: int,
    tg_thread_id: int = 0,
    dialog_key: str,
    client_id: str = "",
    guest_session_id: str = "",
    job_id: str = "",
    chat_message_id: str = "",
    direction: str = "admin_dm_card",
) -> None:
    if not tg_message_id:
        return
    db.add(
        SupportTelegramMessageMap(
            id=new_id(),
            tg_chat_id=str(tg_chat_id),
            tg_message_id=int(tg_message_id),
            tg_thread_id=int(tg_thread_id or 0),
            dialog_key=dialog_key,
            client_id=client_id,
            guest_session_id=guest_session_id,
            job_id=job_id,
            chat_message_id=chat_message_id,
            direction=direction,
        )
    )


def lookup_tg_reply_target(db: Session, *, tg_chat_id: int | str, reply_to_message_id: int | None) -> SupportTelegramMessageMap | None:
    if not reply_to_message_id:
        return None
    return (
        db.query(SupportTelegramMessageMap)
        .filter(
            SupportTelegramMessageMap.tg_chat_id == str(tg_chat_id),
            SupportTelegramMessageMap.tg_message_id == int(reply_to_message_id),
        )
        .order_by(SupportTelegramMessageMap.created_at.desc())
        .first()
    )


def lookup_topic_dialog(db: Session, *, tg_chat_id: int | str, tg_thread_id: int | None) -> SupportDialogState | None:
    if not tg_thread_id or int(tg_thread_id) <= 0:
        return None
    return (
        db.query(SupportDialogState)
        .filter(
            SupportDialogState.telegram_group_id == str(tg_chat_id),
            SupportDialogState.telegram_thread_id == int(tg_thread_id),
        )
        .first()
    )


def get_active_tg_session(db: Session, *, tg_user_id: int | str, role_scope: str) -> SupportTelegramSession | None:
    uid = str(tg_user_id or "").strip()
    if not uid:
        return None
    now = _as_naive_utc()
    sessions = (
        db.query(SupportTelegramSession)
        .filter(
            SupportTelegramSession.tg_user_id == uid,
            SupportTelegramSession.role_scope == role_scope,
            SupportTelegramSession.is_active == True,
        )
        .order_by(SupportTelegramSession.updated_at.desc())
        .all()
    )
    active: SupportTelegramSession | None = None
    dirty = False
    for sess in sessions:
        if sess.expires_at and _as_naive_utc(sess.expires_at) < now:
            sess.is_active = False
            dirty = True
            continue
        if active is None:
            active = sess
        else:
            sess.is_active = False
            dirty = True
    if dirty:
        db.commit()
    return active


def set_active_tg_session(
    db: Session,
    *,
    tg_user_id: int | str,
    role_scope: str,
    dialog_key: str,
    client_id: str = "",
    guest_session_id: str = "",
    job_id: str = "",
    dialog_label: str = "",
    ttl_hours: int = DEFAULT_ADMIN_SESSION_TTL_HOURS,
) -> SupportTelegramSession:
    uid = str(tg_user_id or "").strip()
    db.query(SupportTelegramSession).filter(
        SupportTelegramSession.tg_user_id == uid,
        SupportTelegramSession.role_scope == role_scope,
        SupportTelegramSession.is_active == True,
    ).update({"is_active": False})
    now = now_utc()
    sess = SupportTelegramSession(
        id=new_id(),
        tg_user_id=uid,
        role_scope=role_scope,
        dialog_key=dialog_key,
        client_id=client_id,
        guest_session_id=guest_session_id,
        job_id=job_id,
        dialog_label=dialog_label[:160],
        is_active=True,
        expires_at=now + timedelta(hours=ttl_hours),
    )
    db.add(sess)
    db.commit()
    return sess


def clear_active_tg_session(db: Session, *, tg_user_id: int | str, role_scope: str | None = None) -> int:
    uid = str(tg_user_id or "").strip()
    query = db.query(SupportTelegramSession).filter(
        SupportTelegramSession.tg_user_id == uid,
        SupportTelegramSession.is_active == True,
    )
    if role_scope:
        query = query.filter(SupportTelegramSession.role_scope == role_scope)
    count = query.update({"is_active": False})
    db.commit()
    return int(count or 0)


def _build_topic_header_html(profile: dict[str, Any]) -> str:
    lines = [
        f"🗂 <b>Карточка диалога: {html.escape(profile['display_name'])}</b>",
    ]
    if profile["email"]:
        lines.append(f"📧 <b>Email:</b> {html.escape(profile['email'])}")
    if profile["phone"]:
        lines.append(f"📞 <b>Телефон:</b> {html.escape(profile['phone'])}")
    if profile["tg_username"]:
        lines.append(f"✈️ <b>Telegram:</b> {html.escape(profile['tg_username'])}")
    if profile["is_guest"] and profile["guest_session_id"]:
        lines.append(f"🌐 <b>Сессия сайта:</b> <code>{html.escape(profile['guest_session_id'])}</code>")
    if profile["jobs_summary"]:
        lines.append("📋 <b>Последние задачи:</b>")
        for item in profile["jobs_summary"][:3]:
            lines.append(f"  • {html.escape(item)}")
    lines.extend([
        "",
        "✍️ <b>Отвечайте прямо в этой теме</b> (текстом, документом или фото) — сообщение уйдёт клиенту и в «Диалоги».",
        "Команды в теме: <code>/info</code> (карточка), <code>/job ID</code> (сменить задачу), <code>/close</code> (закрыть тему).",
    ])
    return "\n".join(lines)


async def ensure_support_topic(
    db: Session,
    *,
    group_id: str,
    profile: dict[str, Any],
    allow_in_test: bool = False,
) -> SupportDialogState:
    state: SupportDialogState = profile["state"]
    if (
        state.telegram_group_id == str(group_id)
        and int(state.telegram_thread_id or 0) > 0
    ):
        return state

    topic_name = (profile.get("topic_title") or profile.get("display_name") or "Диалог")[:120]
    resp = await _tg_api_post(
        "createForumTopic",
        {"chat_id": str(group_id), "name": topic_name},
        allow_in_test=allow_in_test,
    )
    if not resp.get("ok"):
        logger.warning("createForumTopic failed for %s: %s", state.dialog_key, resp.get("description"))
        return state

    thread_id = int((resp.get("result") or {}).get("message_thread_id") or 0)
    if thread_id <= 0:
        return state

    state.telegram_group_id = str(group_id)
    state.telegram_thread_id = thread_id
    state.topic_title = topic_name
    state.status = "open"
    db.flush()

    header_resp = await _tg_api_post(
        "sendMessage",
        {
            "chat_id": str(group_id),
            "message_thread_id": thread_id,
            "text": _build_topic_header_html(profile),
            "parse_mode": "HTML",
        },
        allow_in_test=allow_in_test,
    )
    if header_resp.get("ok"):
        msg_id = int((header_resp.get("result") or {}).get("message_id") or 0)
        record_tg_message_map(
            db,
            tg_chat_id=group_id,
            tg_message_id=msg_id,
            tg_thread_id=thread_id,
            dialog_key=profile["dialog_key"],
            client_id=profile["client_id"],
            guest_session_id=profile["guest_session_id"],
            chat_message_id="",
            direction="topic_header",
        )
    return state


async def send_to_support_topic(
    db: Session,
    *,
    group_id: str,
    profile: dict[str, Any],
    text_html: str,
    attachments: list[dict[str, Any]] | None = None,
    chat_message_id: str = "",
    job_id: str = "",
    direction: str = "topic_post",
    allow_in_test: bool = False,
) -> int | None:
    state = await ensure_support_topic(db, group_id=group_id, profile=profile, allow_in_test=allow_in_test)
    thread_id = int(state.telegram_thread_id or 0)
    if thread_id <= 0:
        return None

    async def _attempt_send(target_thread: int) -> dict[str, Any]:
        return await _tg_api_post(
            "sendMessage",
            {
                "chat_id": str(group_id),
                "message_thread_id": target_thread,
                "text": text_html[:4000],
                "parse_mode": "HTML",
            },
            allow_in_test=allow_in_test,
        )

    resp = await _attempt_send(thread_id)
    if not resp.get("ok"):
        desc = str(resp.get("description") or "").upper()
        if "TOPIC_CLOSED" in desc:
            await _tg_api_post(
                "reopenForumTopic",
                {"chat_id": str(group_id), "message_thread_id": thread_id},
                allow_in_test=allow_in_test,
            )
            resp = await _attempt_send(thread_id)
        elif "THREAD NOT FOUND" in desc or "TOPIC_ID_INVALID" in desc or "MESSAGE THREAD NOT FOUND" in desc:
            state.telegram_thread_id = 0
            db.flush()
            state = await ensure_support_topic(db, group_id=group_id, profile=profile, allow_in_test=allow_in_test)
            thread_id = int(state.telegram_thread_id or 0)
            if thread_id > 0:
                resp = await _attempt_send(thread_id)

    sent_msg_id: int | None = None
    if resp.get("ok"):
        sent_msg_id = int((resp.get("result") or {}).get("message_id") or 0)
        if sent_msg_id > 0:
            record_tg_message_map(
                db,
                tg_chat_id=group_id,
                tg_message_id=sent_msg_id,
                tg_thread_id=thread_id,
                dialog_key=profile["dialog_key"],
                client_id=profile["client_id"],
                guest_session_id=profile["guest_session_id"],
                job_id=job_id,
                chat_message_id=chat_message_id,
                direction=direction,
            )

    for att in attachments or []:
        att_resp = await _tg_send_attachment(
            chat_id=str(group_id),
            att=att,
            message_thread_id=thread_id,
            caption_html=f"📎 {html.escape(str(att.get('name') or 'Файл'))}",
            allow_in_test=allow_in_test,
        )
        if att_resp.get("ok"):
            att_msg_id = int((att_resp.get("result") or {}).get("message_id") or 0)
            if att_msg_id > 0:
                record_tg_message_map(
                    db,
                    tg_chat_id=group_id,
                    tg_message_id=att_msg_id,
                    tg_thread_id=thread_id,
                    dialog_key=profile["dialog_key"],
                    client_id=profile["client_id"],
                    guest_session_id=profile["guest_session_id"],
                    job_id=job_id,
                    chat_message_id=chat_message_id,
                    direction=direction,
                )
    return sent_msg_id


def admin_dm_reply_markup(state_id: str, *, job_id: str = "", include_enter: bool = True) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    if include_enter:
        rows.append([{"text": "✍️ Ответить этому клиенту", "callback_data": f"tg_chat:enter:{state_id}"}])
    rows.append([
        {"text": "👤 О клиенте", "callback_data": f"tg_chat:info:{state_id}"},
        {"text": "💬 Все диалоги", "callback_data": "tg_chat:list"},
    ])
    return {"inline_keyboard": rows}


def _build_incoming_card_html(
    profile: dict[str, Any],
    *,
    text: str,
    attachments: list[dict[str, Any]] | None,
    channel: str,
    include_reply_hint: bool = True,
) -> str:
    ch_label = _CHANNEL_LABELS.get(channel, channel or "Сайт")
    lines = [
        f"📩 <b>Новое сообщение от {'гостя сайта' if profile['is_guest'] else 'клиента'}</b>",
        f"👤 <b>Отправитель:</b> {html.escape(profile['display_name'])}",
        f"📍 <b>Канал:</b> {html.escape(ch_label)}",
    ]
    if profile["email"]:
        lines.append(f"✉️ <b>Email:</b> {html.escape(profile['email'])}")
    if profile["phone"]:
        lines.append(f"📞 <b>Телефон:</b> {html.escape(profile['phone'])}")
    if profile["tg_username"]:
        lines.append(f"✈️ <b>Telegram:</b> {html.escape(profile['tg_username'])}")
    if profile["job_label"]:
        lines.append(f"📋 <b>Задача:</b> {html.escape(profile['job_label'])}")
    lines.append("")
    if text:
        safe_text = html.escape(text[:2800])
        lines.append(f"💬 <b>Сообщение:</b>\n{safe_text}")
    if attachments:
        att_names = ", ".join(html.escape(str(a.get("name") or "файл")) for a in attachments[:8])
        lines.append(f"📎 <b>Вложения:</b> {att_names}")
    if include_reply_hint:
        lines.extend([
            "",
            "💡 <i>Сделайте «Ответить» (Reply) на это сообщение для одного ответа или нажмите <b>«✍️ Ответить этому клиенту»</b>, чтобы писать подряд.</i>",
        ])
    return "\n".join(lines)


async def notify_admins_of_incoming_message(
    db: Session,
    *,
    client_id: str = "",
    guest_session_id: str = "",
    job_id: str = "",
    text: str = "",
    attachments: list[dict[str, Any]] | None = None,
    chat_message_id: str = "",
    channel: str = "web",
    allow_in_test: bool = False,
) -> dict[str, Any]:
    """Dispatch real-time notifications of an incoming client/guest message to Forum Topic + Admin Bot DMs."""
    profile = get_dialog_profile(
        db,
        client_id=client_id,
        guest_session_id=guest_session_id,
        job_id=job_id,
    )
    state: SupportDialogState = profile["state"]
    state.status = "open"
    state.last_channel = channel or "web"
    state.last_message_at = now_utc()
    db.flush()

    summary: dict[str, Any] = {"topic_msg_id": None, "dm_sent": 0}

    # Option B: Admin Forum Group Topic
    group_id = get_configured_support_group_id(db)
    if group_id:
        topic_html = _build_incoming_card_html(
            profile,
            text=text,
            attachments=attachments,
            channel=channel,
            include_reply_hint=False,
        )
        topic_msg_id = await send_to_support_topic(
            db,
            group_id=group_id,
            profile=profile,
            text_html=topic_html,
            attachments=attachments,
            chat_message_id=chat_message_id,
            job_id=job_id,
            direction="topic_post",
            allow_in_test=allow_in_test,
        )
        summary["topic_msg_id"] = topic_msg_id

    # Option A: Admin Personal DM with the Bot
    admin_ids = get_authorized_admin_telegram_ids(db)
    dm_html = _build_incoming_card_html(
        profile,
        text=text,
        attachments=attachments,
        channel=channel,
        include_reply_hint=True,
    )
    markup = admin_dm_reply_markup(state.id, job_id=job_id, include_enter=True)
    for admin_id in admin_ids:
        resp = await _tg_api_post(
            "sendMessage",
            {
                "chat_id": admin_id,
                "text": dm_html[:4000],
                "parse_mode": "HTML",
                "reply_markup": markup,
            },
            allow_in_test=allow_in_test,
        )
        if resp.get("ok"):
            summary["dm_sent"] += 1
            msg_id = int((resp.get("result") or {}).get("message_id") or 0)
            if msg_id > 0:
                record_tg_message_map(
                    db,
                    tg_chat_id=admin_id,
                    tg_message_id=msg_id,
                    dialog_key=profile["dialog_key"],
                    client_id=profile["client_id"],
                    guest_session_id=profile["guest_session_id"],
                    job_id=job_id,
                    chat_message_id=chat_message_id,
                    direction="admin_dm_card",
                )
        for att in attachments or []:
            att_resp = await _tg_send_attachment(
                chat_id=admin_id,
                att=att,
                caption_html=f"📎 От {html.escape(profile['display_name'])}: {html.escape(str(att.get('name') or 'Файл'))}",
                allow_in_test=allow_in_test,
            )
            if att_resp.get("ok"):
                att_msg_id = int((att_resp.get("result") or {}).get("message_id") or 0)
                if att_msg_id > 0:
                    record_tg_message_map(
                        db,
                        tg_chat_id=admin_id,
                        tg_message_id=att_msg_id,
                        dialog_key=profile["dialog_key"],
                        client_id=profile["client_id"],
                        guest_session_id=profile["guest_session_id"],
                        job_id=job_id,
                        chat_message_id=chat_message_id,
                        direction="admin_dm_card",
                    )

    db.commit()
    return summary


async def deliver_admin_reply(
    db: Session,
    *,
    client_id: str = "",
    guest_session_id: str = "",
    job_id: str = "",
    text: str = "",
    attachments: list[dict[str, Any]] | None = None,
    source_channel: str = "admin_web",
    actor_tg_user_id: str = "",
    actor_name: str = "Специалист TenderLex",
    notify_client_tg: bool = True,
    mirror_to_other_tg: bool = True,
    allow_in_test: bool = False,
) -> dict[str, Any]:
    """Save an admin reply into the DB ledger and synchronize it across client TG, Forum Topic, and Admin DMs."""
    clean_text = str(text or "").strip()
    atts = list(attachments or [])
    if not clean_text and not atts:
        raise ValueError("Пустое сообщение без текста и вложений.")

    profile = get_dialog_profile(
        db,
        client_id=client_id,
        guest_session_id=guest_session_id,
        job_id=job_id,
    )
    state: SupportDialogState = profile["state"]
    target_job: Job | None = profile["job"]
    resolved_job_id = ""
    if target_job:
        resolved_job_id = target_job.parent_job_id if (getattr(target_job, "is_admin_rerun", False) and getattr(target_job, "parent_job_id", "")) else target_job.id

    msg_obj = JobChatMessage(
        id=new_id(),
        client_id=profile["client_id"],
        guest_session_id=profile["guest_session_id"],
        job_id=resolved_job_id,
        sender_role="admin",
        channel=source_channel or "admin_web",
        message=clean_text,
        attachments_json=json.dumps(atts, ensure_ascii=False),
        is_read_by_admin=True,
        is_read_by_client=False,
        created_at=now_utc(),
    )
    db.add(msg_obj)

    # Mark client unread messages in this dialog as read by admin
    mark_query = db.query(JobChatMessage).filter(
        JobChatMessage.client_id == profile["client_id"],
        JobChatMessage.sender_role == "client",
        JobChatMessage.is_read_by_admin == False,
    )
    mark_query.update({"is_read_by_admin": True})

    if target_job:
        root_job = db.get(Job, resolved_job_id) or target_job
        if clean_text:
            root_job.admin_comment = clean_text
        root_job.admin_supplement_at = now_utc()
        root_job.updated_at = now_utc()

    if profile["guest_session"]:
        profile["guest_session"].status = "open"
        profile["guest_session"].updated_at = now_utc()

    state.status = "open"
    state.last_channel = source_channel or "admin_web"
    state.last_message_at = now_utc()
    db.commit()

    client_tg_sent = 0
    if notify_client_tg and profile["telegram_targets"]:
        header = "💬 <b>Специалист TenderLex ответил вам</b>"
        if profile["job_label"]:
            header += f"\n📋 <b>Задача:</b> {html.escape(profile['job_label'])}"
        body = f"\n\n{html.escape(clean_text[:3400])}" if clean_text else ""
        client_markup = {
            "inline_keyboard": [[{"text": "💬 Ответить специалисту", "callback_data": f"client_support:reply:{state.id}"}]]
        }
        client_html = f"{header}{body}"
        for target_tg in profile["telegram_targets"]:
            resp = await _tg_api_post(
                "sendMessage",
                {
                    "chat_id": target_tg,
                    "text": client_html,
                    "parse_mode": "HTML",
                    "reply_markup": client_markup,
                },
                allow_in_test=allow_in_test,
            )
            if resp.get("ok"):
                client_tg_sent += 1
                tg_msg_id = int((resp.get("result") or {}).get("message_id") or 0)
                if tg_msg_id > 0:
                    record_tg_message_map(
                        db,
                        tg_chat_id=target_tg,
                        tg_message_id=tg_msg_id,
                        dialog_key=profile["dialog_key"],
                        client_id=profile["client_id"],
                        guest_session_id=profile["guest_session_id"],
                        job_id=resolved_job_id,
                        chat_message_id=msg_obj.id,
                        direction="client_dm_reply",
                    )
            for att in atts:
                att_resp = await _tg_send_attachment(
                    chat_id=target_tg,
                    att=att,
                    caption_html=f"📎 От специалиста TenderLex: {html.escape(str(att.get('name') or 'Файл'))}",
                    reply_markup=client_markup,
                    allow_in_test=allow_in_test,
                )
                if att_resp.get("ok"):
                    att_msg_id = int((att_resp.get("result") or {}).get("message_id") or 0)
                    if att_msg_id > 0:
                        record_tg_message_map(
                            db,
                            tg_chat_id=target_tg,
                            tg_message_id=att_msg_id,
                            dialog_key=profile["dialog_key"],
                            client_id=profile["client_id"],
                            guest_session_id=profile["guest_session_id"],
                            job_id=resolved_job_id,
                            chat_message_id=msg_obj.id,
                            direction="client_dm_reply",
                        )

    if mirror_to_other_tg and should_mirror_admin_replies_to_bot(db):
        source_label = _CHANNEL_LABELS.get(source_channel, source_channel)
        # Mirror into Forum Topic if reply originated outside the Forum Topic
        group_id = get_configured_support_group_id(db)
        if group_id and source_channel != "tg_topic":
            topic_lines = [
                f"📤 <b>Ответ администратора</b> ({html.escape(source_label)})",
            ]
            if profile["job_label"]:
                topic_lines.append(f"📋 <b>Задача:</b> {html.escape(profile['job_label'])}")
            if clean_text:
                topic_lines.append("")
                topic_lines.append(html.escape(clean_text[:3400]))
            await send_to_support_topic(
                db,
                group_id=group_id,
                profile=profile,
                text_html="\n".join(topic_lines),
                attachments=atts,
                chat_message_id=msg_obj.id,
                job_id=resolved_job_id,
                direction="topic_post",
                allow_in_test=allow_in_test,
            )

        # Mirror into Admin Bot DMs (excluding the admin who just typed directly in DM)
        admin_ids = get_authorized_admin_telegram_ids(db)
        actor_clean = str(actor_tg_user_id or "").strip()
        mirror_targets = [aid for aid in admin_ids if not (source_channel == "tg_dm" and aid == actor_clean)]
        if mirror_targets:
            echo_lines = [
                f"📤 <b>Ответ отправлен → {html.escape(profile['display_name'])}</b>",
                f"📍 <b>Откуда:</b> {html.escape(source_label)}",
            ]
            if clean_text:
                echo_lines.append(f"💬 {html.escape(clean_text[:2000])}")
            if atts:
                echo_lines.append("📎 " + ", ".join(html.escape(str(a.get("name") or "файл")) for a in atts[:6]))
            markup = admin_dm_reply_markup(state.id, job_id=resolved_job_id, include_enter=True)
            for aid in mirror_targets:
                echo_resp = await _tg_api_post(
                    "sendMessage",
                    {
                        "chat_id": aid,
                        "text": "\n".join(echo_lines)[:4000],
                        "parse_mode": "HTML",
                        "reply_markup": markup,
                    },
                    allow_in_test=allow_in_test,
                )
                if echo_resp.get("ok"):
                    echo_id = int((echo_resp.get("result") or {}).get("message_id") or 0)
                    if echo_id > 0:
                        record_tg_message_map(
                            db,
                            tg_chat_id=aid,
                            tg_message_id=echo_id,
                            dialog_key=profile["dialog_key"],
                            client_id=profile["client_id"],
                            guest_session_id=profile["guest_session_id"],
                            job_id=resolved_job_id,
                            chat_message_id=msg_obj.id,
                            direction="admin_dm_echo",
                        )

    db.commit()
    return {
        "message": msg_obj,
        "state": state,
        "client_tg_sent": client_tg_sent,
        "profile": profile,
    }


async def deliver_client_telegram_message(
    db: Session,
    *,
    tg_user_id: str,
    username: str = "",
    full_name: str = "",
    text: str = "",
    attachments: list[dict[str, Any]] | None = None,
    job_id: str = "",
    allow_in_test: bool = False,
) -> dict[str, Any]:
    """Save an incoming client support message from Telegram Bot and sync to Admin Panel + Admin TG channels."""
    clean_text = str(text or "").strip()
    atts = list(attachments or [])
    if not clean_text and not atts:
        raise ValueError("Укажите сообщение или прикрепите файл.")

    client, guest = resolve_or_create_client_for_tg_user(
        db,
        tg_user_id=str(tg_user_id),
        username=username,
        full_name=full_name,
    )
    resolved_client_id = client.id if client else f"{GUEST_CLIENT_PREFIX}{guest.session_id}"
    resolved_guest_sid = guest.session_id if guest else ""

    resolved_job_id = ""
    if client and job_id:
        j = db.get(Job, job_id)
        if j and j.client_id == client.id:
            resolved_job_id = j.parent_job_id if (getattr(j, "is_admin_rerun", False) and getattr(j, "parent_job_id", "")) else j.id

    msg_obj = JobChatMessage(
        id=new_id(),
        client_id=resolved_client_id,
        guest_session_id=resolved_guest_sid,
        job_id=resolved_job_id,
        sender_role="client",
        channel="tg_bot",
        message=clean_text,
        attachments_json=json.dumps(atts, ensure_ascii=False),
        is_read_by_client=True,
        is_read_by_admin=False,
        created_at=now_utc(),
    )
    db.add(msg_obj)
    db.commit()

    notify_summary = await notify_admins_of_incoming_message(
        db,
        client_id=resolved_client_id,
        guest_session_id=resolved_guest_sid,
        job_id=resolved_job_id,
        text=clean_text,
        attachments=atts,
        chat_message_id=msg_obj.id,
        channel="tg_bot",
        allow_in_test=allow_in_test,
    )
    return {
        "message": msg_obj,
        "client": client,
        "guest": guest,
        "client_id": resolved_client_id,
        "guest_session_id": resolved_guest_sid,
        "notify": notify_summary,
    }


async def close_support_dialog(
    db: Session,
    *,
    state: SupportDialogState,
    actor_name: str = "Администратор",
    send_closing_note: bool = True,
    allow_in_test: bool = False,
) -> None:
    state.status = "closed"
    state.updated_at = now_utc()
    if state.guest_session_id:
        guest = db.query(SupportGuestSession).filter(SupportGuestSession.session_id == state.guest_session_id).first()
        if guest:
            guest.status = "closed"
            guest.updated_at = now_utc()
    db.query(JobChatMessage).filter(
        JobChatMessage.client_id == state.client_id,
        JobChatMessage.sender_role == "client",
        JobChatMessage.is_read_by_admin == False,
    ).update({"is_read_by_admin": True})

    if send_closing_note:
        db.add(
            JobChatMessage(
                id=new_id(),
                client_id=state.client_id,
                guest_session_id=state.guest_session_id,
                job_id="",
                sender_role="admin",
                channel="system",
                message="Диалог завершён администратором. Если появятся новые вопросы — напишите нам снова!",
                attachments_json="[]",
                is_read_by_admin=True,
                is_read_by_client=True,
                created_at=now_utc(),
            )
        )
    db.commit()

    group_id = get_configured_support_group_id(db)
    if group_id and state.telegram_group_id == group_id and int(state.telegram_thread_id or 0) > 0:
        await _tg_api_post(
            "closeForumTopic",
            {"chat_id": group_id, "message_thread_id": int(state.telegram_thread_id)},
            allow_in_test=allow_in_test,
        )


def list_recent_dialogs_for_bot(db: Session, *, limit: int = 8) -> list[dict[str, Any]]:
    """Return top recent client & guest dialogs for `/dialogs` in Telegram bot."""
    ensure_legacy_guest_sessions_imported(db)
    rows = (
        db.query(
            JobChatMessage.client_id,
            func.max(JobChatMessage.created_at).label("last_at"),
            func.count(JobChatMessage.id).label("total_cnt"),
        )
        .filter(JobChatMessage.client_id != "")
        .group_by(JobChatMessage.client_id)
        .order_by(func.max(JobChatMessage.created_at).desc())
        .limit(max(limit * 2, 16))
        .all()
    )
    items: list[dict[str, Any]] = []
    for cid, last_at, total_cnt in rows:
        profile = get_dialog_profile(db, client_id=cid)
        unread = (
            db.query(func.count(JobChatMessage.id))
            .filter(
                JobChatMessage.client_id == cid,
                JobChatMessage.sender_role == "client",
                JobChatMessage.is_read_by_admin == False,
            )
            .scalar()
            or 0
        )
        last_msg = (
            db.query(JobChatMessage)
            .filter(JobChatMessage.client_id == cid)
            .order_by(JobChatMessage.created_at.desc())
            .first()
        )
        items.append({
            "state": profile["state"],
            "state_id": profile["state"].id,
            "dialog_key": profile["dialog_key"],
            "client_id": cid,
            "display_name": profile["display_name"],
            "is_guest": profile["is_guest"],
            "unread_count": int(unread),
            "total_count": int(total_cnt or 0),
            "last_at": last_at,
            "last_preview": (last_msg.message[:65] if last_msg and last_msg.message else "📎 Вложение"),
        })
        if len(items) >= limit:
            break
    items.sort(key=lambda x: (x["unread_count"] > 0, str(x["last_at"] or "")), reverse=True)
    return items[:limit]


async def test_support_group_connection(
    db: Session,
    *,
    group_id_override: str | None = None,
    send_test_ping: bool = True,
    allow_in_test: bool = False,
) -> dict[str, Any]:
    """Validate Telegram Forum Supergroup configuration & bot admin rights."""
    group_id = str(group_id_override if group_id_override is not None else get_configured_support_group_id(db)).strip()
    if not group_id or not TELEGRAM_ID_RE.match(group_id):
        return {
            "ok": False,
            "error": "Укажите корректный числовой ID супергруппы Telegram (обычно начинается с -100...).",
        }
    token = get_bot_token()
    if not token:
        return {"ok": False, "error": "Не настроен AIPOISK_BOT_TOKEN."}

    me_resp = await _tg_api_post("getMe", bot_token=token, allow_in_test=allow_in_test)
    if not me_resp.get("ok"):
        return {
            "ok": False,
            "error": f"Не удалось получить данные бота через Telegram API: {me_resp.get('description') or 'unknown error'}",
        }
    bot_info = me_resp.get("result") or {}
    bot_id = bot_info.get("id")
    bot_username = bot_info.get("username") or ""

    chat_resp = await _tg_api_post("getChat", {"chat_id": group_id}, bot_token=token, allow_in_test=allow_in_test)
    if not chat_resp.get("ok"):
        return {
            "ok": False,
            "error": (
                f"Бот @{bot_username or 'bot'} не видит группу {group_id}: "
                f"{chat_resp.get('description') or 'убедитесь, что бот добавлен в группу и ID указан с -100...'}"
            ),
        }
    chat_info = chat_resp.get("result") or {}
    chat_type = str(chat_info.get("type") or "")
    chat_title = str(chat_info.get("title") or group_id)
    is_forum = bool(chat_info.get("is_forum"))

    if chat_type != "supergroup":
        return {
            "ok": False,
            "chat_title": chat_title,
            "is_forum": is_forum,
            "error": (
                f"Группа «{chat_title}» имеет тип «{chat_type}», а нужна супергруппа с темами. "
                "Откройте Настройки группы -> включите «Темы» (Topics) — Telegram автоматически переведёт группу в супергруппу."
            ),
        }
    if not is_forum:
        return {
            "ok": False,
            "chat_title": chat_title,
            "is_forum": False,
            "error": (
                f"В супергруппе «{chat_title}» отключены «Темы» (Topics). "
                "Включите Настройки группы -> «Темы» (Topics), чтобы для каждого клиента создавалась отдельная ветка."
            ),
        }

    member_resp = await _tg_api_post(
        "getChatMember",
        {"chat_id": group_id, "user_id": bot_id},
        bot_token=token,
        allow_in_test=allow_in_test,
    )
    if not member_resp.get("ok"):
        return {
            "ok": False,
            "chat_title": chat_title,
            "is_forum": True,
            "error": f"Не удалось проверить права бота в группе «{chat_title}»: {member_resp.get('description')}",
        }
    member = member_resp.get("result") or {}
    status = str(member.get("status") or "")
    can_manage_topics = bool(member.get("can_manage_topics"))
    if status != "administrator":
        return {
            "ok": False,
            "chat_title": chat_title,
            "is_forum": True,
            "error": f"Бот @{bot_username} должен быть администратором группы «{chat_title}» (сейчас статус: {status}).",
        }
    if not can_manage_topics:
        return {
            "ok": False,
            "chat_title": chat_title,
            "is_forum": True,
            "error": (
                f"У бота @{bot_username} в группе «{chat_title}» нет права «Управление темами» (Manage Topics). "
                "Включите его в Администраторах группы."
            ),
        }

    if send_test_ping:
        ping_resp = await _tg_api_post(
            "sendMessage",
            {
                "chat_id": group_id,
                "text": (
                    "✅ <b>TenderLex: группа поддержки подключена!</b>\n"
                    "Новые сообщения клиентов и гостей сайта будут автоматически создавать здесь отдельные темы."
                ),
                "parse_mode": "HTML",
            },
            bot_token=token,
            allow_in_test=allow_in_test,
        )
        if not ping_resp.get("ok"):
            return {
                "ok": False,
                "chat_title": chat_title,
                "is_forum": True,
                "error": f"Права подтверждены, но тестовое сообщение не отправлено: {ping_resp.get('description')}",
            }

    return {
        "ok": True,
        "chat_id": group_id,
        "chat_title": chat_title,
        "is_forum": True,
        "bot_username": bot_username,
        "message": f"Группа «{chat_title}» с темами подключена; права бота @{bot_username} подтверждены.",
    }


def unread_dialogs_count_for_admin(db: Session) -> int:
    ensure_legacy_guest_sessions_imported(db)
    return int(
        db.query(func.count(func.distinct(JobChatMessage.client_id)))
        .filter(
            JobChatMessage.sender_role == "client",
            JobChatMessage.is_read_by_admin == False,
            JobChatMessage.client_id != "",
        )
        .scalar()
        or 0
    )


def build_guest_chat_frontend_message(msg: JobChatMessage) -> dict[str, Any]:
    """Serialize a JobChatMessage into the exact shape expected by site/src/components/chat-widget.tsx."""
    sender = "user" if msg.sender_role == "client" else "admin"
    return {
        "id": msg.id,
        "sender": sender,
        "text": msg.message or "",
        "preset": None,
        "timestamp": (msg.created_at.isoformat() + "Z") if msg.created_at and msg.created_at.tzinfo is None else (msg.created_at.isoformat() if msg.created_at else now_utc().isoformat()),
    }
