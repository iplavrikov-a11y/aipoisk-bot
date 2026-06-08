from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from .config import config
from .db import db_session
from .models import Client, WebSession, WebUser, new_id, now_utc

CUSTOMER_COOKIE = "tenderlex_customer_session"
CSRF_HEADER = "x-csrf-token"
PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
WEB_DEFAULT_FILE_LIMIT = 10


@dataclass
class WebAuthContext:
    user: WebUser
    session: WebSession | None


def normalize_email(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def validate_email(value: str) -> str:
    email = normalize_email(value)
    if not email or len(email) > 255 or not EMAIL_PATTERN.match(email):
        raise ValueError("Укажите корректный email.")
    return email


def hash_password(password: str) -> str:
    raw = str(password or "")
    if len(raw) < 8:
        raise ValueError("Пароль должен быть не короче 8 символов.")
    salt = secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${base64.urlsafe_b64encode(digest).decode()}"


def generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    safe_length = max(10, min(40, int(length or 14)))
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(safe_length))
        if any(ch.islower() for ch in value) and any(ch.isupper() for ch in value) and any(ch.isdigit() for ch in value):
            return value


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected = str(password_hash or "").split("$", 3)
        iterations = int(iterations_raw)
    except Exception:
        return False
    if algorithm != PASSWORD_ALGORITHM or iterations <= 0:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt.encode("utf-8"), iterations)
    actual = base64.urlsafe_b64encode(digest).decode()
    return hmac.compare_digest(actual, expected)


def create_web_user(
    db: Session,
    *,
    email: str,
    password: str,
    name: str = "",
    client: Client | None = None,
) -> WebUser:
    normalized_email = validate_email(email)
    if db.query(WebUser.id).filter(WebUser.email == normalized_email).first():
        raise ValueError("Пользователь с таким email уже зарегистрирован.")
    display_name = str(name or normalized_email).strip()[:255]
    if client is None:
        client = Client(
            telegram_id=f"web:{new_id()}",
            name=display_name,
            username="",
            is_active=True,
            is_trial=False,
            allowed_supplier_search=True,
            allowed_procurement_report=True,
            monthly_job_limit=0,
            monthly_supplier_search_limit=0,
            monthly_procurement_report_limit=0,
            monthly_file_limit=WEB_DEFAULT_FILE_LIMIT,
            notes=f"Website account: {normalized_email}. Manual grants required.",
        )
        db.add(client)
        db.flush()
    user = WebUser(
        client_id=client.id,
        email=normalized_email,
        password_hash=hash_password(password),
        name=display_name,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_web_user(db: Session, email: str, password: str) -> WebUser | None:
    normalized_email = normalize_email(email)
    if not normalized_email:
        return None
    user = db.query(WebUser).filter(WebUser.email == normalized_email).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_web_session(db: Session, user: WebUser, *, request: Request | object | None = None) -> tuple[str, str, WebSession]:
    token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    headers = getattr(request, "headers", {}) or {}
    client = getattr(request, "client", None)
    session = WebSession(
        user_id=user.id,
        token_hash=_token_hash(token),
        csrf_token=csrf_token,
        user_agent=str(headers.get("user-agent", ""))[:1000] if hasattr(headers, "get") else "",
        ip_address=str(getattr(client, "host", "") or "")[:80],
        expires_at=now_utc() + timedelta(hours=max(1, int(config.customer_session_hours or 168))),
        last_seen_at=now_utc(),
    )
    user.last_login_at = now_utc()
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, csrf_token, session


def set_customer_session_cookie(response: Response, token: str) -> None:
    secure = str(config.public_base_url or "").lower().startswith("https://")
    response.set_cookie(
        CUSTOMER_COOKIE,
        token,
        max_age=max(1, int(config.customer_session_hours or 168)) * 3600,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_customer_session_cookie(response: Response) -> None:
    response.delete_cookie(CUSTOMER_COOKIE, path="/")


def get_web_session_by_token(db: Session, token: str) -> WebSession | None:
    if not token:
        return None
    session = db.query(WebSession).filter(WebSession.token_hash == _token_hash(token)).first()
    if not session or session.revoked_at is not None:
        return None
    if _as_aware_utc(session.expires_at) < now_utc():
        return None
    if not session.user or not session.user.is_active:
        return None
    if not session.user.client or not session.user.client.is_active:
        return None
    return session


def require_web_context(request: Request, db: Session = Depends(db_session)) -> WebAuthContext:
    session = get_web_session_by_token(db, request.cookies.get(CUSTOMER_COOKIE, ""))
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Войдите в личный кабинет.")
    session.last_seen_at = now_utc()
    db.commit()
    return WebAuthContext(user=session.user, session=session)


def optional_web_context(request: Request, db: Session = Depends(db_session)) -> WebAuthContext | None:
    session = get_web_session_by_token(db, request.cookies.get(CUSTOMER_COOKIE, ""))
    if not session:
        return None
    session.last_seen_at = now_utc()
    db.commit()
    return WebAuthContext(user=session.user, session=session)


def require_customer_csrf(request: Request, context: WebAuthContext) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    expected = context.session.csrf_token if context.session else ""
    supplied = request.headers.get(CSRF_HEADER, "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Сессия устарела. Обновите страницу и повторите действие.")


def revoke_web_session(db: Session, session: WebSession | None) -> None:
    if not session:
        return
    session.revoked_at = now_utc()
    db.commit()
