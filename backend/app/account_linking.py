from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import AccountLinkToken, Client, ClientTelegramAccount, WebUser, now_utc
from .repository import is_pending_telegram_id

WEB_TO_TELEGRAM = "web_to_telegram"
TELEGRAM_TO_WEB = "telegram_to_web"
ACTIVE = "active"
LINKED = "linked"
CONFLICT = "conflict"
REVOKED = "revoked"
TOKEN_TTL = timedelta(minutes=15)


class AccountLinkError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TelegramLinkResult:
    status: str
    client_id: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_account_link_token(
    db: Session,
    *,
    client: Client,
    direction: str,
    web_user: WebUser | None = None,
    telegram_id: str = "",
    request: Request | object | None = None,
) -> tuple[str, AccountLinkToken]:
    if direction not in {WEB_TO_TELEGRAM, TELEGRAM_TO_WEB}:
        raise ValueError("Unsupported account-link direction")
    now = now_utc()
    db.query(AccountLinkToken).filter(
        AccountLinkToken.client_id == client.id,
        AccountLinkToken.direction == direction,
        AccountLinkToken.status == ACTIVE,
    ).update({AccountLinkToken.status: REVOKED, AccountLinkToken.consumed_at: now}, synchronize_session=False)
    raw = secrets.token_urlsafe(24)
    headers = getattr(request, "headers", {}) or {}
    requester = getattr(request, "client", None)
    record = AccountLinkToken(
        direction=direction,
        client_id=client.id,
        web_user_id=web_user.id if web_user else None,
        token_hash=_hash_token(raw),
        status=ACTIVE,
        telegram_id=str(telegram_id or "")[:64],
        requested_ip=str(getattr(requester, "host", "") or "")[:80],
        user_agent=str(headers.get("user-agent", ""))[:1000] if hasattr(headers, "get") else "",
        expires_at=now + TOKEN_TTL,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return raw, record


def active_account_link_token(db: Session, raw_token: str, *, direction: str) -> AccountLinkToken:
    token = str(raw_token or "").strip()
    record = db.query(AccountLinkToken).filter(AccountLinkToken.token_hash == _hash_token(token)).first() if token else None
    if not record or record.direction != direction or record.status != ACTIVE or record.consumed_at is not None:
        raise AccountLinkError("Ссылка привязки недействительна или уже использована.", code="invalid")
    if _aware(record.expires_at) < now_utc():
        record.status = REVOKED
        record.consumed_at = now_utc()
        db.commit()
        raise AccountLinkError("Срок действия ссылки привязки истёк. Создайте новую ссылку.", code="expired")
    return record


def consume_web_to_telegram_token(
    db: Session,
    raw_token: str,
    *,
    telegram_id: str,
    username: str = "",
    name: str = "",
) -> TelegramLinkResult:
    record = active_account_link_token(db, raw_token, direction=WEB_TO_TELEGRAM)
    client = db.get(Client, record.client_id)
    if not client or not client.is_active:
        raise AccountLinkError("Кабинет для привязки не найден или отключён.", code="inactive")
    normalized_telegram_id = str(telegram_id or "").strip()
    existing = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == normalized_telegram_id).first()
    now = now_utc()
    if existing and existing.client_id != client.id:
        record.status = CONFLICT
        record.conflict_client_id = existing.client_id
        record.telegram_id = normalized_telegram_id
        record.consumed_at = now
        db.commit()
        raise AccountLinkError(
            "Этот Telegram уже относится к другому профилю. Мы ничего не объединили и не изменили; напишите в поддержку для безопасной сверки.",
            code="conflict",
        )
    if not existing:
        db.add(
            ClientTelegramAccount(
                client_id=client.id,
                telegram_id=normalized_telegram_id,
                username=str(username or "")[:255],
                name=str(name or "")[:255],
                is_active=True,
                notes="Secure self-service link from web cabinet",
            )
        )
    else:
        existing.username = str(username or existing.username)[:255]
        existing.name = str(name or existing.name)[:255]
        existing.is_active = True
    if not str(client.telegram_id or "").strip() or str(client.telegram_id).startswith("web:") or is_pending_telegram_id(client.telegram_id):
        client.telegram_id = normalized_telegram_id
        client.username = str(username or client.username)[:255]
    record.status = LINKED
    record.telegram_id = normalized_telegram_id
    record.consumed_at = now
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == normalized_telegram_id).first()
        refreshed = db.query(AccountLinkToken).filter(AccountLinkToken.token_hash == _hash_token(raw_token)).first()
        if winner and winner.client_id == client.id and refreshed and refreshed.status == LINKED:
            return TelegramLinkResult(status=LINKED, client_id=client.id)
        if refreshed and refreshed.status == ACTIVE:
            refreshed.status = CONFLICT
            refreshed.conflict_client_id = winner.client_id if winner else None
            refreshed.telegram_id = normalized_telegram_id
            refreshed.consumed_at = now_utc()
            db.commit()
        raise AccountLinkError(
            "Этот Telegram уже относится к другому профилю. Данные и балансы не изменены; напишите в поддержку для безопасной сверки.",
            code="conflict",
        )
    return TelegramLinkResult(status=LINKED, client_id=client.id)


def consume_telegram_to_web_token(db: Session, record: AccountLinkToken, user: WebUser) -> None:
    if record.direction != TELEGRAM_TO_WEB or record.status != ACTIVE:
        raise AccountLinkError("Ссылка привязки недействительна или уже использована.")
    if record.client_id != user.client_id:
        record.status = CONFLICT
        record.conflict_client_id = user.client_id
        record.consumed_at = now_utc()
        db.commit()
        raise AccountLinkError(
            "Telegram и этот кабинет уже относятся к разным профилям. Данные и балансы не изменены; напишите в поддержку для безопасной сверки.",
            code="conflict",
        )
    record.web_user_id = user.id
    record.status = LINKED
    record.consumed_at = now_utc()


def telegram_deep_link(bot_telegram: str, raw_token: str) -> str:
    handle = str(bot_telegram or "@tenderlex_bot").strip()
    if handle.startswith("https://t.me/"):
        handle = handle.split("https://t.me/", 1)[1].split("?", 1)[0].strip("/")
    else:
        handle = handle.lstrip("@").strip("/")
    return f"https://t.me/{handle or 'tenderlex_bot'}?start={quote(f'link_{raw_token}', safe='')}"


def cabinet_link(public_base_url: str, raw_token: str) -> str:
    base = str(public_base_url or "https://tenderlex.ru").strip().rstrip("/")
    return f"{base}/cabinet?telegram_link={quote(raw_token, safe='')}"
