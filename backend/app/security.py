from __future__ import annotations

import base64
import hmac
import logging
import secrets
import time
from hashlib import sha256

from fastapi import Header, HTTPException, Request, status

from .config import config

ADMIN_COOKIE = "aipoisk_admin_session"
_EPHEMERAL_SESSION_SECRET = secrets.token_hex(32)
_REVOKED_ADMIN_SESSIONS: dict[str, int] = {}
_ALLOWED_ADMIN_ORIGINS = frozenset(
    {
        "https://tenderlex.ru",
        "https://www.tenderlex.ru",
        "https://admin.tenderlex.ru",
        "http://localhost:5173",
        "http://localhost:3093",
        "http://127.0.0.1:3093",
    }
)
logger = logging.getLogger(__name__)


def _admin_token() -> str:
    token = str(config.admin_token or "").strip()
    if not token or token == "change-me":
        return ""
    return token


def _session_secret() -> str:
    password = str(config.admin_password or "").strip()
    token = _admin_token()
    if token:
        return token
    if password and password != "change-me":
        return password
    logger.warning("Admin session secret not configured; using instance-isolated ephemeral secret")
    return _EPHEMERAL_SESSION_SECRET


def _session_ttl_seconds() -> int:
    return max(int(config.admin_session_hours or 24), 1) * 3600


def _sign(value: str) -> str:
    return hmac.new(_session_secret().encode(), value.encode(), sha256).hexdigest()


def check_admin_credentials(username: str, password: str) -> bool:
    expected_username = str(config.admin_username or "admin").strip()
    expected_password = str(config.admin_password or "").strip() or _admin_token()
    if not expected_password or expected_password == "change-me":
        return False
    return hmac.compare_digest(username.strip(), expected_username) and hmac.compare_digest(password, expected_password)


def create_admin_session(username: str) -> str:
    expires_at = int(time.time()) + _session_ttl_seconds()
    payload = f"{username.strip()}:{expires_at}"
    signed = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(signed.encode()).decode()


def revoke_admin_session(session: str | None) -> None:
    raw_tok = str(session or "").strip()
    if not raw_tok:
        return
    now = int(time.time())
    expired_keys = [k for k, exp in _REVOKED_ADMIN_SESSIONS.items() if exp < now]
    for k in expired_keys:
        _REVOKED_ADMIN_SESSIONS.pop(k, None)
    try:
        decoded = base64.urlsafe_b64decode(raw_tok.encode()).decode()
        _u, expires_raw, _sig = decoded.rsplit(":", 2)
        exp_ts = int(expires_raw)
    except Exception:
        exp_ts = now + _session_ttl_seconds()
    if len(_REVOKED_ADMIN_SESSIONS) >= 4096:
        oldest = min(_REVOKED_ADMIN_SESSIONS, key=_REVOKED_ADMIN_SESSIONS.get)
        _REVOKED_ADMIN_SESSIONS.pop(oldest, None)
    _REVOKED_ADMIN_SESSIONS[raw_tok] = exp_ts


def verify_admin_session(session: str) -> bool:
    if not session or session in _REVOKED_ADMIN_SESSIONS:
        return False
    try:
        raw = base64.urlsafe_b64decode(session.encode()).decode()
        username, expires_raw, signature = raw.rsplit(":", 2)
        payload = f"{username}:{expires_raw}"
        expires_at = int(expires_raw)
    except Exception:
        return False
    if expires_at < int(time.time()):
        return False
    if not hmac.compare_digest(signature, _sign(payload)):
        return False
    return hmac.compare_digest(username, str(config.admin_username or "admin").strip())


def admin_cookie_max_age() -> int:
    return _session_ttl_seconds()


def require_admin(request: Request, x_admin_token: str = Header(default="")) -> None:
    configured_token = _admin_token()
    if configured_token and x_admin_token and hmac.compare_digest(x_admin_token, configured_token):
        return
    if verify_admin_session(request.cookies.get(ADMIN_COOKIE, "")):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = str(request.headers.get("origin") or "").strip().rstrip("/")
            if origin and origin not in _ALLOWED_ADMIN_ORIGINS:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-origin admin request blocked")
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authorization is invalid")


def mask_secret(value: str) -> str:
    value = str(value or "")
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
