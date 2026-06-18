from __future__ import annotations

import base64
import hmac
import time
from hashlib import sha256

from fastapi import Header, HTTPException, Request, status

from .config import config

ADMIN_COOKIE = "aipoisk_admin_session"


def _admin_token() -> str:
    token = str(config.admin_token or "").strip()
    return token if token and token != "change-me" else "change-me"


def _session_secret() -> str:
    password = str(config.admin_password or "").strip()
    token = _admin_token()
    return token if token != "change-me" else password or token


def _session_ttl_seconds() -> int:
    return max(int(config.admin_session_hours or 24), 1) * 3600


def _sign(value: str) -> str:
    return hmac.new(_session_secret().encode(), value.encode(), sha256).hexdigest()


def check_admin_credentials(username: str, password: str) -> bool:
    expected_username = str(config.admin_username or "admin").strip()
    expected_password = str(config.admin_password or "").strip() or _admin_token()
    return hmac.compare_digest(username.strip(), expected_username) and hmac.compare_digest(password, expected_password)


def create_admin_session(username: str) -> str:
    expires_at = int(time.time()) + _session_ttl_seconds()
    payload = f"{username.strip()}:{expires_at}"
    signed = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(signed.encode()).decode()


def verify_admin_session(session: str) -> bool:
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
    if x_admin_token and hmac.compare_digest(x_admin_token, _admin_token()):
        return
    if verify_admin_session(request.cookies.get(ADMIN_COOKIE, "")):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authorization is invalid")


def mask_secret(value: str) -> str:
    value = str(value or "")
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
