"""Security, anti-spam, working-hours, and AI first-line triage for TenderLex."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from .admin_alerts import is_pytest
from .ai import AI_ROUTING_FALLBACK_LIGHT, call_llm
from .config import config
from .models import SecurityEvent, SupportBlockedActor, SystemSettings, TariffPackage, now_utc

logger = logging.getLogger(__name__)

PROTECTED_INFRASTRUCTURE_IPS: set[str] = {
    "79.133.182.215",
    "202.71.13.57",
    "127.0.0.1",
    "::1",
}

_RFC5737_TEST_NETS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)

_EPHEMERAL_CHALLENGE_SECRET: bytes | None = None


def get_protected_infrastructure_ips() -> set[str]:
    """Return canonical infrastructure/proxy IPs that are trusted hops and must never be blocked."""
    ips = set(PROTECTED_INFRASTRUCTURE_IPS)
    extra = os.getenv("AIPOISK_TRUSTED_PROXY_IPS", "")
    if extra:
        for part in extra.split(","):
            token = part.strip()
            if not token:
                continue
            try:
                ips.add(str(ipaddress.ip_address(token)))
            except ValueError:
                ips.add(token)
    return ips


def normalize_ip_token(raw_value: str | None) -> str:
    candidate = str(raw_value or "").strip()
    if not candidate or len(candidate) > 64 or candidate.lower() == "unknown":
        return ""
    try:
        return str(ipaddress.ip_address(candidate))[:64]
    except ValueError:
        return ""


def _is_pytest_doc_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        is_pytest()
        and isinstance(ip_obj, ipaddress.IPv4Address)
        and any(ip_obj in net for net in _RFC5737_TEST_NETS)
    )


def normalize_blockable_ip(raw_ip: str | None) -> str:
    """Normalize an untrusted public visitor IP; return '' for loopback, private, reserved, or infra IPs."""
    raw = str(raw_ip or "").strip().split(",")[0].strip()[:64]
    if not raw or raw.lower() == "unknown":
        return ""
    try:
        ip_obj = ipaddress.ip_address(raw)
    except ValueError:
        return ""
    if (
        ip_obj.is_loopback
        or ip_obj.is_reserved
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
        or (ip_obj.is_private and not _is_pytest_doc_ip(ip_obj))
    ):
        return ""
    normalized = str(ip_obj)
    if normalized in get_protected_infrastructure_ips():
        return ""
    return normalized


def _is_trusted_proxy_peer(peer_raw: str) -> bool:
    if not peer_raw or peer_raw == "testclient":
        return True
    peer = normalize_ip_token(peer_raw)
    if not peer:
        return False
    if peer in get_protected_infrastructure_ips():
        return True
    try:
        ip_obj = ipaddress.ip_address(peer)
        return bool(ip_obj.is_loopback or ip_obj.is_private)
    except ValueError:
        return False


def extract_real_request_ip(request: Any, *, default: str = "") -> str:
    """Resolve visitor IP walking X-Forwarded-For right-to-left ONLY when peer is a trusted proxy."""
    if request is None:
        return default
    client = getattr(request, "client", None)
    peer_raw = str(getattr(client, "host", "") or "").strip() if client else ""
    peer = normalize_ip_token(peer_raw) or peer_raw[:64]
    if peer_raw and not _is_trusted_proxy_peer(peer_raw):
        return peer or default
    headers = getattr(request, "headers", None)
    ips: list[str] = []
    real_ip = ""
    if headers:
        forwarded_raw = str(headers.get("x-forwarded-for", "") or "").strip()
        if forwarded_raw:
            ips = [ip for part in forwarded_raw.split(",") if (ip := normalize_ip_token(part))]
            for candidate in reversed(ips):
                if normalize_blockable_ip(candidate):
                    return candidate
        real_ip = normalize_ip_token(headers.get("x-real-ip", ""))
        if real_ip and normalize_blockable_ip(real_ip):
            return real_ip
        if real_ip and not ipaddress.ip_address(real_ip).is_loopback:
            return real_ip
        non_loopback = [ip for ip in reversed(ips) if not ipaddress.ip_address(ip).is_loopback]
        if non_loopback:
            return non_loopback[0]
        if ips:
            return ips[-1]
        if real_ip:
            return real_ip
    return peer or default

# Known disposable / temporary email domains and reserved test domains
DISPOSABLE_EMAIL_DOMAINS = {
    "nbasweeps.com",
    "fldubai.com",
    "mailinator.com",
    "10minutemail.com",
    "10minutemail.net",
    "tempmail.com",
    "temp-mail.org",
    "temp-mail.ru",
    "guerrillamail.com",
    "guerrillamail.org",
    "sharklasers.com",
    "yopmail.com",
    "throwawaymail.com",
    "trashmail.com",
    "getnada.com",
    "dispostable.com",
    "fakemailgenerator.com",
    "emailondeck.com",
    "mohmal.com",
    "dropmail.me",
    "maildrop.cc",
    "mintemail.com",
    "mytemp.email",
    "tempr.email",
    "burnermail.io",
    "spamgourmet.com",
    "example.com",
    "example.org",
    "example.net",
    "test.local",
    "invalid.local",
}

_GARBAGE_EMAIL_RE = re.compile(
    r"^(?:"
    r"\d{1,4}@(?:mail\.ru|yandex\.ru|ya\.ru|gmail\.com|bk\.ru|inbox\.ru|list\.ru|rambler\.ru)"
    r"|(?:admin|test\d{0,3}|probe|pentest|hacker|asdf|qwerty)@(?:mail\.ru|yandex\.ru|ya\.ru|gmail\.com|bk\.ru)"
    r"|(?:ctf|tl-pentest|tl-massign)[a-z0-9_-]*@"
    r")$",
    re.IGNORECASE,
)

_AUTOMATED_UA_RE = re.compile(
    r"(?:^|\b)(?:curl/|python-requests/|python-urllib|httpx/|aiohttp/|go-http-client|libwww-perl|sqlmap|nikto|nuclei|masscan|nmap|postmanruntime|scrapy|headlesschrome)(?:\b|/|$)",
    re.IGNORECASE,
)

_SQLI_XSS_CLI_PATTERNS = [
    re.compile(r"(?:^|\s)(?:-?\d+['\"]|['\"])\s*(?:or|and)\s+[\d\s+\-*/='\"]+=[\d\s+\-*/='\"]+", re.IGNORECASE),
    re.compile(
        r"\bunion\s+all\s+select\b|\bunion\s+select\s+(?:null|\d+|@@|version\s*\(|user\s*\()"
        r"|(?:;\s*(?:drop|delete|truncate|alter)\s+table\b)"
        r"|\b(?:waitfor\s+delay\b|pg_sleep\s*\(|benchmark\s*\()",
        re.IGNORECASE,
    ),
    re.compile(
        r"<\s*script\b|javascript\s*:\s*[a-zA-Z0-9_(]"
        r"|<\s*[a-z]+\b[^>]*\bon(?:error|load|toggle|mouseover|focus)\s*=",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:ls(?:\s+-[lahtrR]+)+\s*|whoami\s*|uname\s+-a\s*|id\s*)$"
        r"|(?:;|&&|\|\|)\s*(?:cat\s+/etc/(?:passwd|shadow)|rm\s+-rf\s+/|whoami\b|id\b)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:\.\./){2,}|(?:\.\.\\){2,}|/etc/(?:passwd|shadow)\b", re.IGNORECASE),
    re.compile(r"^[/\\'\"`;|&$]{2,6}$"),
]

_PLACEHOLDER_PHONE_DIGITS = {
    "123456789",
    "1234567890",
    "7123456789",
    "71234567890",
    "81234567890",
    "0123456789",
    "9876543210",
    "70000000000",
    "80000000000",
    "79999999999",
    "89999999999",
}

_GARBAGE_CONTACT_VALUES = {
    "admin",
    "administrator",
    "root",
    "test",
    "tester",
    "user",
    "guest",
    "x",
    "xx",
    "xxx",
    "none",
    "null",
    "qwerty",
    "asdf",
    "123",
    "1234",
    "12345",
    "123456",
}


def _challenge_secret() -> bytes:
    global _EPHEMERAL_CHALLENGE_SECRET
    explicit = os.getenv("AIPOISK_CHALLENGE_SECRET", "").strip()
    if explicit:
        return explicit.encode("utf-8")
    admin_tok = str(getattr(config, "admin_token", "") or "").strip()
    if admin_tok and admin_tok != "change-me":
        return hmac.new(
            admin_tok.encode("utf-8"),
            b"tenderlex-human-challenge-v1",
            hashlib.sha256,
        ).digest()
    if _EPHEMERAL_CHALLENGE_SECRET is None:
        _EPHEMERAL_CHALLENGE_SECRET = secrets.token_bytes(32)
        logger.warning(
            "AIPOISK_CHALLENGE_SECRET and non-default ADMIN_TOKEN are unset; using runtime ephemeral challenge secret."
        )
    return _EPHEMERAL_CHALLENGE_SECRET


def create_human_challenge() -> dict[str, Any]:
    """Issue a lightweight HMAC-signed timestamp token for invisible anti-bot verification."""
    ts = int(time.time())
    nonce = hashlib.sha256(f"{ts}:{os.urandom(8).hex()}".encode("utf-8")).hexdigest()[:12]
    payload = f"{ts}.{nonce}"
    sig = hmac.new(_challenge_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return {"token": f"{payload}.{sig}", "issued_at": ts}


_CONSUMED_CHALLENGE_NONCES: dict[str, float] = {}


def verify_human_challenge(token: str | None, *, min_elapsed_sec: float = 0.8, max_age_sec: int = 7200) -> tuple[bool, str]:
    raw = str(token or "").strip()
    if not raw:
        return False, "missing_challenge"
    parts = raw.split(".")
    if len(parts) != 3:
        return False, "invalid_challenge_format"
    ts_raw, nonce, sig = parts
    try:
        ts = int(ts_raw)
    except ValueError:
        return False, "invalid_challenge_ts"
    payload = f"{ts_raw}.{nonce}"
    expected_sig = hmac.new(_challenge_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    if not hmac.compare_digest(sig, expected_sig):
        return False, "invalid_challenge_sig"
    now_ts = time.time()
    age = now_ts - ts
    if age < min_elapsed_sec:
        return False, "submitted_too_fast"
    if age > max_age_sec:
        return False, "challenge_expired"
    expired_nonces = [k for k, exp in _CONSUMED_CHALLENGE_NONCES.items() if exp < now_ts]
    for k in expired_nonces:
        _CONSUMED_CHALLENGE_NONCES.pop(k, None)
    if payload in _CONSUMED_CHALLENGE_NONCES:
        return False, "challenge_replayed"
    if len(_CONSUMED_CHALLENGE_NONCES) >= 8192:
        oldest_key = min(_CONSUMED_CHALLENGE_NONCES, key=_CONSUMED_CHALLENGE_NONCES.get)
        _CONSUMED_CHALLENGE_NONCES.pop(oldest_key, None)
    _CONSUMED_CHALLENGE_NONCES[payload] = ts + max_age_sec
    return True, "ok"


def detect_attack_payload(text: str | None) -> str | None:
    """Return short reason string if text looks like SQLi, XSS, CLI probing, or fuzzing."""
    val = str(text or "").strip()
    if not val:
        return None
    for pat in _SQLI_XSS_CLI_PATTERNS:
        if pat.search(val):
            return f"suspicious_pattern:{pat.pattern[:40]}"
    return None


def is_automated_user_agent(user_agent: str | None) -> bool:
    ua = str(user_agent or "").strip()
    if not ua:
        return False
    return bool(_AUTOMATED_UA_RE.search(ua))


def is_disposable_or_garbage_email(email: str | None) -> str | None:
    """Return reason code if email is disposable or obvious garbage/test address."""
    clean = str(email or "").strip().lower()
    if "@" not in clean:
        return "invalid_email"
    domain = clean.rsplit("@", 1)[1].strip()
    if domain in {"example.com", "example.org", "example.net"} and is_pytest():
        return None
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return f"disposable_domain:{domain}"
    if _GARBAGE_EMAIL_RE.match(clean):
        return "garbage_test_email"
    return None


def validate_optional_phone(phone: str | None) -> str | None:
    """Return error message if non-empty phone is clearly fake/garbage, else None."""
    raw = str(phone or "").strip()
    if not raw:
        return None
    digits = re.sub(r"\D+", "", raw)
    if len(digits) < 7 or len(digits) > 15:
        return "Укажите корректный номер телефона (минимум 7 цифр) или оставьте поле пустым."
    if len(set(digits)) <= 2:
        return "Укажите реальный номер телефона или оставьте поле пустым."
    if digits in _PLACEHOLDER_PHONE_DIGITS:
        return "Укажите реальный номер телефона или оставьте поле пустым."
    return None


def validate_guest_contact(contact: str | None) -> str | None:
    """Validate visitor contact in chat widget. Returns Russian error message or None if valid."""
    raw = str(contact or "").strip()
    if not raw:
        return "Укажите телефон, email или @username в Telegram."
    if len(raw) < 4:
        return "Контакт слишком короткий. Укажите телефон, email или @telegram."
    if raw.lower() in _GARBAGE_CONTACT_VALUES:
        return "Укажите реальный телефон, email или @username в Telegram для связи."
    if detect_attack_payload(raw):
        return "Некорректный формат контакта."
    digits = re.sub(r"\D+", "", raw)
    if digits in _PLACEHOLDER_PHONE_DIGITS or (len(digits) >= 7 and len(set(digits)) <= 2):
        return "Укажите реальный номер телефона, email или @telegram."
    has_email = "@" in raw and "." in raw.split("@", 1)[-1]
    has_tg = raw.startswith("@") and len(raw) >= 4 or "t.me/" in raw.lower()
    has_phone = len(digits) >= 7
    if not (has_email or has_tg or has_phone):
        return "Укажите телефон (от 7 цифр), email или @username в Telegram."
    return None


def ipv4_subnet_prefix(ip_str: str | None) -> str:
    """Return /24 prefix for public untrusted IPv4 addresses or empty string."""
    clean = normalize_blockable_ip(ip_str)
    if not clean:
        return ""
    try:
        ip_obj = ipaddress.ip_address(clean)
    except ValueError:
        return ""
    if ip_obj.version != 4:
        return ""
    parts = clean.split(".")
    return ".".join(parts[:3]) + "."


def record_security_event(
    db: Session,
    *,
    event_type: str,
    severity: str = "medium",
    ip_address: str = "",
    actor_key: str = "",
    user_agent: str = "",
    payload_preview: str = "",
    reason: str = "",
    action_taken: str = "blocked",
    commit: bool = True,
) -> SecurityEvent:
    ev = SecurityEvent(
        event_type=str(event_type or "unknown")[:40],
        severity=str(severity or "medium")[:16],
        ip_address=str(ip_address or "")[:80],
        actor_key=str(actor_key or "")[:255],
        user_agent=str(user_agent or "")[:500],
        payload_preview=str(payload_preview or "")[:1000],
        reason=str(reason or "")[:255],
        action_taken=str(action_taken or "blocked")[:40],
        created_at=now_utc(),
    )
    db.add(ev)
    if commit:
        db.commit()
    else:
        db.flush()
    return ev


def maybe_auto_block_actor(
    db: Session,
    *,
    actor_type: str,
    actor_value: str,
    dialog_key: str = "",
    reason: str = "Автоблокировка за спам/атаки",
    threshold: int = 3,
    window_minutes: int = 30,
) -> bool:
    """Auto-block an actor in SupportBlockedActor if security events exceed threshold."""
    clean_val = str(actor_value or "").strip()
    if not clean_val or clean_val.lower() == "unknown":
        return False
    if actor_type == "ip":
        clean_val = normalize_blockable_ip(clean_val)
        if not clean_val:
            return False
    elif clean_val in get_protected_infrastructure_ips():
        return False

    cutoff = now_utc() - timedelta(minutes=window_minutes)
    if actor_type == "guest_session":
        actor_filter = SecurityEvent.actor_key.in_([clean_val, f"guest:{clean_val}"])
    elif actor_type == "client":
        actor_filter = SecurityEvent.actor_key.in_([clean_val, f"client:{clean_val}"])
    elif actor_type == "ip":
        actor_filter = (SecurityEvent.ip_address == clean_val) | (SecurityEvent.actor_key == clean_val)
    else:
        actor_filter = (SecurityEvent.ip_address == clean_val) | (SecurityEvent.actor_key == clean_val)

    recent_cnt = (
        db.query(SecurityEvent.id)
        .filter(
            SecurityEvent.created_at >= cutoff,
            actor_filter,
        )
        .count()
    )
    if recent_cnt < threshold:
        return False
    existing = (
        db.query(SupportBlockedActor.id)
        .filter(
            SupportBlockedActor.actor_type == actor_type,
            SupportBlockedActor.actor_value == clean_val,
        )
        .first()
    )
    if existing:
        return True
    db.add(
        SupportBlockedActor(
            actor_type=actor_type,
            actor_value=clean_val,
            dialog_key=dialog_key[:128],
            reason=reason[:500],
            blocked_by="auto_shield",
        )
    )
    record_security_event(
        db,
        event_type="auto_blocked",
        severity="high",
        ip_address=clean_val if actor_type == "ip" else "",
        actor_key=clean_val,
        reason=reason,
        action_taken="blocked",
        commit=False,
    )
    db.commit()
    return True


def _parse_hhmm(value: str | None, default_minutes: int) -> int:
    raw = str(value or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", raw)
    if not m:
        return default_minutes
    hh, mm = int(m.group(1)), int(m.group(2))
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return hh * 60 + mm
    return default_minutes


def get_support_work_hours_status(
    settings: SystemSettings | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    enabled = True if settings is None else bool(getattr(settings, "support_work_hours_enabled", True))
    start_str = (getattr(settings, "support_work_hours_start", None) if settings else None) or "09:00"
    end_str = (getattr(settings, "support_work_hours_end", None) if settings else None) or "20:00"
    tz_offset = int((getattr(settings, "support_timezone_offset", None) if settings else None) or 3)
    quiet_night = True if settings is None else bool(getattr(settings, "support_quiet_night_notifications", True))

    utc_now = now or datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=timezone.utc)
    local_dt = utc_now.astimezone(timezone(timedelta(hours=tz_offset)))
    local_minutes = local_dt.hour * 60 + local_dt.minute
    start_min = _parse_hhmm(start_str, 9 * 60)
    end_min = _parse_hhmm(end_str, 20 * 60)

    if not enabled:
        is_open = True
    elif start_min <= end_min:
        is_open = start_min <= local_minutes < end_min
    else:
        is_open = local_minutes >= start_min or local_minutes < end_min

    return {
        "enabled": enabled,
        "is_open": is_open,
        "start": start_str,
        "end": end_str,
        "tz_offset": tz_offset,
        "quiet_night": quiet_night,
        "local_time": local_dt.strftime("%H:%M"),
        "notice": (
            ""
            if is_open
            else f"Сейчас нерабочее время (поддержка работает с {start_str} до {end_str} МСК). AI-помощник ответит сразу, а менеджер подключится утром."
        ),
    }


def _build_tariffs_summary_for_ai(db: Session) -> str:
    try:
        rows = (
            db.query(TariffPackage)
            .filter(TariffPackage.is_active == True)  # noqa: E712
            .order_by(TariffPackage.sort_order.asc())
            .limit(8)
            .all()
        )
        if not rows:
            return "Тарифы и пополнение баланса доступны в личном кабинете на tenderlex.ru."
        lines = []
        for r in rows:
            rub = int((r.price_kopeks or 0) // 100)
            lines.append(f"- {r.name}: {rub} руб.")
        return "\n".join(lines)
    except Exception:
        return "Тарифы доступны в личном кабинете на tenderlex.ru."


async def classify_and_reply_support_message(
    db: Session,
    *,
    text: str,
    is_guest: bool = True,
    is_work_hours: bool = True,
    has_attachments: bool = False,
    force_in_test: bool = False,
) -> dict[str, Any]:
    """
    Use the light AI model to classify incoming support chat messages and optionally draft a first-line reply.
    Returns:
      {
        "category": "real_question" | "greeting" | "spam_or_probe",
        "need_human": bool,
        "reply": str,
        "used_ai": bool,
      }
    Gracefully falls back if AI is unavailable or in tests.
    """
    clean = str(text or "").strip()
    if not clean:
        return {"category": "real_question", "need_human": True, "reply": "", "used_ai": False}

    # Fast deterministic spam check first
    if detect_attack_payload(clean):
        return {"category": "spam_or_probe", "need_human": False, "reply": "", "used_ai": False}

    if has_attachments:
        return {"category": "real_question", "need_human": True, "reply": "", "used_ai": False}

    settings = db.query(SystemSettings).first()
    antispam_on = True if settings is None else bool(getattr(settings, "support_ai_antispam_enabled", True))
    autoreply_on = True if settings is None else bool(getattr(settings, "support_ai_auto_reply_enabled", True))
    if not antispam_on and not autoreply_on:
        return {"category": "real_question", "need_human": True, "reply": "", "used_ai": False}

    if is_pytest() and not force_in_test:
        return {"category": "real_question", "need_human": True, "reply": "", "used_ai": False}

    has_ai = bool(
        settings is not None
        and (
            getattr(settings, "has_active_ai_provider", False)
            or str(getattr(settings, "openrouter_api_key", "") or "").strip()
        )
    )
    if not has_ai:
        return {"category": "real_question", "need_human": True, "reply": "", "used_ai": False}

    tariffs_summary = _build_tariffs_summary_for_ai(db)
    system_prompt = (
        "Ты — AI-ассистент первой линии поддержки сервиса TenderLex (tenderlex.ru).\n"
        "Задачи:\n"
        "1) Классифицировать сообщение посетителя:\n"
        "   - 'spam_or_probe': бессмысленный набор символов, команды терминала, инъекции, реклама/ссылки, массовый тест.\n"
        "   - 'greeting': короткое приветствие ('привет', 'здравствуйте', 'hello') без конкретики.\n"
        "   - 'real_question': реальный вопрос по закупкам, тарифам, поиску поставщиков, подбору аналогов или оплате.\n"
        "2) Если это 'real_question' или 'greeting' и включён автоответ — дай короткий, вежливый, точный ответ на русском (2–4 предложения).\n"
        "СТРОГИЕ ПРАВИЛА ПРОДУКТА:\n"
        "- Основные модули TenderLex в порядке: 1. Поиск поставщиков, 2. Подбор товара и аналогов, 3. Анализ документации.\n"
        "- НИКОГДА не упоминай 'Форма 2' и не упоминай 'Tenderplan'.\n"
        "- Отчёт 'Подбор товара и аналогов' формируется ТОЛЬКО в формате Word (.docx), Excel/XLSX для него нет.\n"
        "- Не выдумывай цены. Актуальные тарифы:\n"
        f"{tariffs_summary}\n"
        f"- Сейчас {'рабочее время' if is_work_hours else 'нерабочее время (ночь/вечер, менеджер ответит в рабочие часы с 09:00 МСК)'}.\n"
        "Верни строго JSON без markdown-обёртки:\n"
        '{"category": "real_question|greeting|spam_or_probe", "need_human": true|false, "reply": "текст ответа или пустая строка"}'
    )
    try:
        raw = await call_llm(
            settings=settings,
            prompt=f"Сообщение посетителя ({'гость' if is_guest else 'клиент'}): {clean[:1000]}",
            system_prompt=system_prompt,
            routing_key=AI_ROUTING_FALLBACK_LIGHT,
            timeout_seconds=6.0,
            total_timeout_seconds=8.0,
            max_retries=1,
            temperature=0.2,
        )
        text_out = str(raw or "").strip()
        if text_out.startswith("```"):
            text_out = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_out, flags=re.IGNORECASE | re.DOTALL).strip()
        parsed = json.loads(text_out)
        cat = str(parsed.get("category") or "real_question").strip()
        if cat not in {"real_question", "greeting", "spam_or_probe"}:
            cat = "real_question"
        need_human = bool(parsed.get("need_human", True))
        reply = str(parsed.get("reply") or "").strip()[:1500]
        if not autoreply_on or cat == "spam_or_probe":
            reply = ""
        return {
            "category": cat,
            "need_human": need_human,
            "reply": reply,
            "used_ai": True,
        }
    except Exception as exc:
        logger.debug("AI support triage skipped/failed: %s", exc)
        return {"category": "real_question", "need_human": True, "reply": "", "used_ai": False}
