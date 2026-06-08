from __future__ import annotations

import base64
import hashlib
import html as html_lib
import hmac
import logging
import re
import secrets
import smtplib
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr

import httpx
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from .config import config
from .db import db_session
from .models import Client, WebEmailVerificationToken, WebSession, WebUser, new_id, now_utc
from .repository import get_or_create_settings

CUSTOMER_COOKIE = "tenderlex_customer_session"
CSRF_HEADER = "x-csrf-token"
PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
WEB_DEFAULT_FILE_LIMIT = 10
logger = logging.getLogger(__name__)


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
    email_verified: bool = False,
) -> WebUser:
    normalized_email = validate_email(email)
    if db.query(WebUser.id).filter(WebUser.email == normalized_email).first():
        raise ValueError("Пользователь с таким email уже зарегистрирован.")
    display_name = str(name or normalized_email).strip()[:255]
    if client is None:
        settings = get_or_create_settings(db)
        trial_enabled = bool(settings.trial_enabled)
        supplier_limit = max(0, int(settings.trial_supplier_search_limit or 0)) if trial_enabled else 0
        report_limit = max(0, int(settings.trial_procurement_report_limit or 0)) if trial_enabled else 0
        file_limit = max(0, int(settings.trial_file_limit or WEB_DEFAULT_FILE_LIMIT)) if trial_enabled else WEB_DEFAULT_FILE_LIMIT
        client = Client(
            telegram_id=f"web:{new_id()}",
            name=display_name,
            username="",
            is_active=True,
            is_trial=trial_enabled,
            allowed_supplier_search=True,
            allowed_procurement_report=True,
            monthly_job_limit=supplier_limit + report_limit,
            monthly_supplier_search_limit=supplier_limit,
            monthly_procurement_report_limit=report_limit,
            monthly_file_limit=file_limit,
            notes=(
                f"Website trial account: {normalized_email}. Email verification required."
                if trial_enabled
                else f"Website account: {normalized_email}. Manual grants required."
            ),
        )
        db.add(client)
        db.flush()
    user = WebUser(
        client_id=client.id,
        email=normalized_email,
        password_hash=hash_password(password),
        name=display_name,
        is_active=True,
        is_email_verified=bool(email_verified),
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


def create_email_verification_token(
    db: Session,
    user: WebUser,
    *,
    request: Request | object | None = None,
) -> tuple[str, WebEmailVerificationToken]:
    token = secrets.token_urlsafe(48)
    headers = getattr(request, "headers", {}) or {}
    client = getattr(request, "client", None)
    record = WebEmailVerificationToken(
        user_id=user.id,
        email=user.email,
        token_hash=_token_hash(token),
        requested_ip=str(getattr(client, "host", "") or "")[:80],
        user_agent=str(headers.get("user-agent", ""))[:1000] if hasattr(headers, "get") else "",
        expires_at=now_utc() + timedelta(hours=max(1, int(config.customer_email_verification_hours or 24))),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return token, record


def verify_email_token(db: Session, token: str) -> WebUser:
    record = db.query(WebEmailVerificationToken).filter(WebEmailVerificationToken.token_hash == _token_hash(token)).first()
    if not record or record.used_at is not None:
        raise ValueError("Ссылка подтверждения недействительна.")
    if _as_aware_utc(record.expires_at) < now_utc():
        raise ValueError("Срок действия ссылки истёк. Отправьте письмо ещё раз.")
    user = record.user
    if not user or not user.is_active:
        raise ValueError("Пользователь не найден или отключён.")
    if normalize_email(record.email) != normalize_email(user.email):
        raise ValueError("Ссылка подтверждения недействительна.")
    user.is_email_verified = True
    verified_at = now_utc()
    db.query(WebEmailVerificationToken).filter(
        WebEmailVerificationToken.user_id == user.id,
        WebEmailVerificationToken.email == record.email,
        WebEmailVerificationToken.used_at.is_(None),
    ).update({WebEmailVerificationToken.used_at: verified_at}, synchronize_session=False)
    db.commit()
    db.refresh(user)
    return user


def email_verification_url(token: str, *, public_base_url: str = "") -> str:
    base_url = str(public_base_url or config.public_base_url or "https://tenderlex.ru").strip().rstrip("/")
    return f"{base_url}/api/customer/auth/verify-email/confirm?token={token}"


def _verification_sender_name() -> str:
    return str(config.email_from_name or "TenderLex").strip() or "TenderLex"


def _verification_sender_email() -> str:
    return str(config.email_from_email or config.smtp_from or config.smtp_username or "").strip()


def _verification_email_text(link: str) -> str:
    return "\n".join(
        [
            "Здравствуйте.",
            "",
            "Подтвердите email для личного кабинета TenderLex:",
            link,
            "",
            "После подтверждения можно запускать задачи на сайте.",
            "Если вы не создавали кабинет, просто не открывайте эту ссылку.",
        ]
    )


def _verification_email_html(link: str) -> str:
    safe_link = html_lib.escape(link, quote=True)
    return f"""<!doctype html>
<html>
  <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.5; color: #172321; background: #f6f8f7;">
    <div style="max-width: 560px; margin: 0 auto; padding: 28px 20px;">
      <div style="background: #ffffff; border: 1px solid #dce7e5; border-radius: 10px; padding: 24px;">
        <div style="font-size: 18px; font-weight: 700; color: #075f68; margin-bottom: 18px;">TenderLex</div>
    <p>Здравствуйте.</p>
    <p>Подтвердите email для личного кабинета TenderLex.</p>
        <p style="margin: 22px 0;">
      <a href="{safe_link}" style="display: inline-block; padding: 12px 18px; background: #075f68; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700;">
        Подтвердить email
      </a>
    </p>
        <p style="font-size: 14px; color: #4f625f;">Если кнопка не открылась, скопируйте ссылку в браузер:<br><a href="{safe_link}" style="color: #075f68;">{safe_link}</a></p>
        <p style="font-size: 14px; color: #4f625f;">Если вы не создавали кабинет, просто не открывайте эту ссылку.</p>
      </div>
    </div>
  </body>
</html>"""


def _send_email_verification_via_relay(user: WebUser, subject: str, html_body: str) -> bool:
    relay_url = str(config.email_relay_url or "").strip()
    relay_api_key = str(config.email_relay_api_key or "").strip()
    sender_email = _verification_sender_email()
    if not relay_url or not relay_api_key or not sender_email:
        return False

    payload = {
        "to": user.email,
        "subject": subject,
        "html": html_body,
        "from_name": _verification_sender_name(),
        "from_email": sender_email,
        "attachments": [],
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                f"{relay_url.rstrip('/')}/send",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {relay_api_key}",
                },
                json=payload,
            )
        if response.status_code != 200:
            logger.warning("email_verification_relay_http_error", extra={"status_code": response.status_code})
            return False
        result = response.json()
    except Exception as exc:
        logger.warning("email_verification_relay_failed", extra={"error": str(exc)})
        return False
    if not isinstance(result, dict):
        return False
    return bool(result.get("success"))


def _send_email_verification_via_smtp(user: WebUser, subject: str, text_body: str, html_body: str) -> bool:
    host = str(config.smtp_host or "").strip()
    sender_email = str(config.smtp_from or config.smtp_username or config.email_from_email or "").strip()
    if not host or not sender_email:
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((_verification_sender_name(), sender_email))
    message["To"] = user.email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    port = int(config.smtp_port or (465 if config.smtp_use_ssl else 587))
    timeout = max(1, int(config.smtp_timeout_seconds or 15))
    if config.smtp_use_ssl:
        smtp_factory = smtplib.SMTP_SSL
    else:
        smtp_factory = smtplib.SMTP
    try:
        with smtp_factory(host, port, timeout=timeout) as smtp:
            if not config.smtp_use_ssl and config.smtp_use_tls:
                smtp.starttls()
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password)
            smtp.send_message(message)
    except Exception as exc:
        logger.warning("email_verification_smtp_failed", extra={"error": str(exc)})
        return False
    return True


def send_email_verification(user: WebUser, token: str, *, public_base_url: str = "") -> bool:
    link = email_verification_url(token, public_base_url=public_base_url)
    subject = "Подтверждение email TenderLex"
    text_body = _verification_email_text(link)
    html_body = _verification_email_html(link)
    if _send_email_verification_via_relay(user, subject, html_body):
        return True
    return _send_email_verification_via_smtp(user, subject, text_body, html_body)


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
