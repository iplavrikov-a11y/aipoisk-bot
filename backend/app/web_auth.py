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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .billing import grant_trial_balance
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
    password: str = "",
    name: str = "",
    client: Client | None = None,
    email_verified: bool = False,
    yandex_id: str | None = None,
    commit: bool = True,
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
                f"Website trial account: {normalized_email}. Verified via Yandex ID."
                if trial_enabled and yandex_id
                else (
                    f"Website trial account: {normalized_email}. Email verification required."
                    if trial_enabled
                    else f"Website account: {normalized_email}. Manual grants required."
                )
            ),
        )
        db.add(client)
        db.flush()
        if trial_enabled:
            grant_trial_balance(
                db,
                client,
                supplier_search_units=supplier_limit,
                procurement_report_units=report_limit,
            )
    password_val = password or generate_temporary_password(16)
    user = WebUser(
        client_id=client.id,
        email=normalized_email,
        yandex_id=str(yandex_id).strip() if yandex_id else None,
        password_hash=hash_password(password_val),
        name=display_name,
        is_active=True,
        is_email_verified=bool(email_verified),
    )
    db.add(user)
    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
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
            "Здравствуйте!",
            "",
            "Вы создали личный кабинет в сервисе TenderLex.",
            "Подтвердите email для активации тестового доступа на 4 задачи (396 ₽):",
            link,
            "",
            "Ссылка действительна в течение 24 часов.",
            "Если вы не регистрировались на сайте tenderlex.ru, просто проигнорируйте это письмо.",
            "",
            "— Команда TenderLex (https://tenderlex.ru)",
        ]
    )


def _verification_email_html(link: str) -> str:
    safe_link = html_lib.escape(link, quote=True)
    return (
        '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<title>Подтверждение email TenderLex</title></head>'
        '<body style="margin:0;padding:0;background:#ffffff;font-family:Arial,Helvetica,sans-serif;color:#1e293b;">'
        '<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;">'
        '<tr><td align="center" style="padding:16px 8px;">'
        '<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:580px;border-collapse:collapse;text-align:left;">'
        '<tr><td style="padding-bottom:12px;border-bottom:2px solid #0f766e;">'
        '<div style="font-size:22px;font-weight:bold;color:#0f766e;line-height:1.2;">TenderLex</div>'
        '<div style="font-size:12px;color:#64748b;margin-top:2px;">Сервис подбора поставщиков и анализа ТЗ</div>'
        '</td></tr>'
        '<tr><td style="padding-top:16px;padding-bottom:8px;">'
        '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Подтверждение адреса электронной почты</div>'
        '</td></tr>'
        '<tr><td style="padding-bottom:8px;">'
        '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
        '</td></tr>'
        '<tr><td style="padding-bottom:18px;">'
        '<div style="font-size:14px;line-height:1.5;color:#334155;">Вы создали личный кабинет в сервисе <b>TenderLex</b>. '
        'Подтвердите email для активации тестового доступа на 4 задачи (396 ₽):</div>'
        '</td></tr>'
        '<tr><td align="center" style="padding-bottom:18px;">'
        '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 auto;">'
        '<tr><td align="center" bgcolor="#0f766e" style="border-radius:8px;">'
        f'<a href="{safe_link}" target="_blank" style="display:inline-block;padding:12px 32px;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;line-height:1.2;text-align:center;">Подтвердить email</a>'
        '</td></tr></table>'
        '</td></tr>'
        '<tr><td style="padding-bottom:14px;">'
        '<div style="background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px;">'
        '<div style="font-size:11px;color:#64748b;margin-bottom:4px;font-weight:bold;">Прямая ссылка для перехода:</div>'
        f'<a href="{safe_link}" target="_blank" style="color:#0f766e;font-size:11px;line-height:1.4;word-break:break-all;font-family:monospace;text-decoration:underline;">{safe_link}</a>'
        '</div></td></tr>'
        '<tr><td style="padding-bottom:4px;">'
        '<div style="font-size:11px;color:#64748b;line-height:1.4;">• Ссылка действительна в течение 24 часов.</div>'
        '</td></tr>'
        '<tr><td style="padding-bottom:16px;">'
        '<div style="font-size:11px;color:#94a3b8;line-height:1.4;">• Если вы не регистрировались на сайте <a href="https://tenderlex.ru" target="_blank" style="color:#64748b;text-decoration:none;">tenderlex.ru</a>, просто проигнорируйте это письмо — аккаунт не будет активирован.</div>'
        '</td></tr>'
        '<tr><td style="border-top:1px solid #e2e8f0;padding-top:12px;">'
        '<div style="font-size:11px;color:#94a3b8;line-height:1.4;">© TenderLex • Сервис снабжения и аудита 44-ФЗ / 223-ФЗ • <a href="https://tenderlex.ru" target="_blank" style="color:#0f766e;text-decoration:none;font-weight:bold;">tenderlex.ru</a></div>'
        '</td></tr></table>'
        '</td></tr></table></body></html>'
    )


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
    touch_web_session_if_stale(db, session)
    return WebAuthContext(user=session.user, session=session)


def optional_web_context(request: Request, db: Session = Depends(db_session)) -> WebAuthContext | None:
    session = get_web_session_by_token(db, request.cookies.get(CUSTOMER_COOKIE, ""))
    if not session:
        return None
    touch_web_session_if_stale(db, session)
    return WebAuthContext(user=session.user, session=session)


def touch_web_session_if_stale(db: Session, session: WebSession, *, interval: timedelta = timedelta(minutes=5)) -> bool:
    current = now_utc()
    if _as_aware_utc(session.last_seen_at) > current - interval:
        return False
    try:
        session.last_seen_at = current
        db.commit()
        return True
    except OperationalError as exc:
        db.rollback()
        logger.warning("Skipping non-critical web session touch after database error: %s", exc)
        return False


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


YANDEX_OAUTH_COOKIE = "tenderlex_yandex_oauth_state"


def yandex_oauth_redirect_uri(public_base_url: str = "") -> str:
    if config.yandex_oauth_redirect_url:
        return config.yandex_oauth_redirect_url
    base = str(public_base_url or config.public_base_url or "https://tenderlex.ru").strip().rstrip("/")
    return f"{base}/api/customer/auth/yandex/callback"


def build_yandex_oauth_url(*, redirect_uri: str, state: str) -> str:
    from urllib.parse import urlencode

    client_id = str(config.yandex_oauth_client_id or "").strip()
    if not client_id:
        raise ValueError("Yandex OAuth Client ID не настроен.")
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "force_confirm": "no",
    }
    return f"https://oauth.yandex.ru/authorize?{urlencode(params)}"


def set_yandex_oauth_state_cookie(response: Response, state: str) -> None:
    secure = str(config.public_base_url or "").lower().startswith("https://")
    response.set_cookie(
        YANDEX_OAUTH_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/customer/auth/yandex",
    )


def clear_yandex_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(YANDEX_OAUTH_COOKIE, path="/api/customer/auth/yandex")


def fetch_yandex_oauth_profile(code: str, redirect_uri: str) -> dict:
    client_id = str(config.yandex_oauth_client_id or "").strip()
    client_secret = str(config.yandex_oauth_client_secret or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Yandex OAuth ключи не настроены.")

    token_url = "https://oauth.yandex.ru/token"
    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if redirect_uri:
        token_payload["redirect_uri"] = redirect_uri

    with httpx.Client(timeout=15.0) as client:
        token_res = client.post(token_url, data=token_payload)
        if token_res.status_code != 200:
            logger.warning("yandex_oauth_token_exchange_failed", extra={"status_code": token_res.status_code, "body": token_res.text})
            raise ValueError(f"Ошибка получения токена Яндекса: {token_res.status_code}")
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Не получен access_token от Яндекса.")

        info_res = client.get(
            "https://login.yandex.ru/info?format=json",
            headers={"Authorization": f"OAuth {access_token}"},
        )
        if info_res.status_code != 200:
            logger.warning("yandex_oauth_profile_fetch_failed", extra={"status_code": info_res.status_code, "body": info_res.text})
            raise ValueError(f"Ошибка получения профиля Яндекса: {info_res.status_code}")
        profile = info_res.json()

    yandex_id = str(profile.get("id") or "").strip()
    if not yandex_id:
        raise ValueError("В ответе Яндекса отсутствует id пользователя.")

    email = str(profile.get("default_email") or "").strip()
    if not email:
        emails = profile.get("emails") or []
        if emails and isinstance(emails, list):
            email = str(emails[0] or "").strip()

    if not email:
        raise ValueError("Яндекс не предоставил доступ к email пользователя.")

    real_name = str(profile.get("real_name") or "").strip()
    first_name = str(profile.get("first_name") or "").strip()
    last_name = str(profile.get("last_name") or "").strip()
    display_name = str(profile.get("display_name") or "").strip()
    combined_name = f"{first_name} {last_name}".strip()
    name = real_name or combined_name or display_name or email.split("@")[0]

    return {
        "yandex_id": yandex_id,
        "email": email,
        "name": name,
        "avatar_id": str(profile.get("default_avatar_id") or ""),
    }


def get_or_create_yandex_web_user(
    db: Session,
    *,
    yandex_user_id: str,
    email: str,
    name: str = "",
) -> tuple[WebUser, bool]:
    clean_yandex_id = str(yandex_user_id or "").strip()
    if not clean_yandex_id:
        raise ValueError("Не передан идентификатор пользователя Яндекс ID.")
    normalized_email = validate_email(email)
    display_name = str(name or "").strip()[:255]

    # 1. Match by yandex_id
    user = db.query(WebUser).filter(WebUser.yandex_id == clean_yandex_id).first()
    if user:
        modified = False
        if not user.is_email_verified:
            user.is_email_verified = True
            modified = True
        if display_name and not user.name:
            user.name = display_name
            modified = True
        if modified:
            db.commit()
            db.refresh(user)
        return user, False

    # 2. Match by email
    user = db.query(WebUser).filter(WebUser.email == normalized_email).first()
    if user:
        user.yandex_id = clean_yandex_id
        user.is_email_verified = True
        if display_name and not user.name:
            user.name = display_name
        db.commit()
        db.refresh(user)
        return user, False

    # 3. Create new user
    user = create_web_user(
        db,
        email=normalized_email,
        name=display_name,
        email_verified=True,
        yandex_id=clean_yandex_id,
        commit=True,
    )
    return user, True

