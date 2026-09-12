from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .billing import grant_money_balance
from .config import config
from .models import Client, ClientTelegramAccount, Job, now_utc

logger = logging.getLogger(__name__)

REFERRAL_WELCOME_BONUS_KOPEKS = 100_000  # 1 000 ₽ (10 tasks at 99 ₽)
REFERRAL_INVITER_REWARD_KOPEKS = 100_000  # 1 000 ₽ (credited when referral completes 1st task)
MAX_REGISTRATIONS_PER_IP_HOUR = 10
MAX_REFERRALS_PER_INVITER_CAP = 100

DISPOSABLE_EMAIL_DOMAINS: set[str] = {
    "10minutemail.com",
    "10minutemail.net",
    "burnermail.io",
    "crazymailing.com",
    "dispostable.com",
    "dropmail.me",
    "fakemailgenerator.com",
    "getairmail.com",
    "guerrillamail.biz",
    "guerrillamail.block",
    "guerrillamail.com",
    "guerrillamail.de",
    "guerrillamail.info",
    "guerrillamail.net",
    "guerrillamail.org",
    "guerrillamailblock.com",
    "inboxkitten.com",
    "mailcatch.com",
    "mailinator.com",
    "mailnesia.com",
    "mohmal.com",
    "mytrashmail.com",
    "nada.ltd",
    "sharklasers.com",
    "spam4.me",
    "spambog.com",
    "spamevader.com",
    "temp-mail.org",
    "temp-mail.ru",
    "tempail.com",
    "tempm.com",
    "tempmail.com",
    "tempmail.net",
    "throwawaymail.com",
    "trashmail.com",
    "trashmail.net",
    "yopmail.com",
    "yopmail.fr",
    "yopmail.net",
}


def is_disposable_email(email: str) -> bool:
    clean = str(email or "").strip().lower()
    if "@" not in clean:
        return False
    domain = clean.split("@", 1)[1].strip()
    return domain in DISPOSABLE_EMAIL_DOMAINS


def ensure_client_referral_code(client: Client, db: Session | None = None) -> str:
    current = str(getattr(client, "referral_code", "") or "").strip()
    if current:
        return current
    code = f"tlx_{client.id[:8]}"
    client.referral_code = code
    if db:
        db.flush()
    return code


def resolve_referrer(db: Session, code_or_id: str) -> Client | None:
    raw = str(code_or_id or "").strip()
    if not raw:
        return None
    # Strip prefixes if passed like ref_tlx_123 or ref_123
    clean = raw
    for prefix in ("ref_", "ref-", "link_"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break
    clean = clean.strip()
    if not clean:
        return None

    # 1. Match referral_code directly (exact match or with ref_ prefix)
    referrer = db.query(Client).filter(
        (Client.referral_code == clean) | (Client.referral_code == raw) | (Client.referral_code == f"tlx_{clean}")
    ).first()
    if referrer:
        return referrer

    # 2. Match Client.id (primary key)
    referrer = db.query(Client).filter(Client.id == clean).first()
    if referrer:
        return referrer

    # 3. Match Telegram ID
    referrer = db.query(Client).filter(Client.telegram_id == clean).first()
    if referrer:
        return referrer

    # 4. Partial id match (first 8 chars)
    if len(clean) >= 8:
        referrer = db.query(Client).filter(Client.id.startswith(clean)).first()
        if referrer:
            return referrer

    return None


def validate_referral_linkage(
    db: Session,
    referrer: Client,
    invitee: Client | None = None,
    *,
    invitee_telegram_id: str = "",
    invitee_email: str = "",
    invitee_ip: str = "",
) -> tuple[bool, str]:
    if not referrer.is_active:
        return False, "Пригласивший пользователь не активен"

    # Self-referral check by Client ID
    if invitee and referrer.id == invitee.id:
        return False, "Нельзя пригласить самого себя"

    # Self-referral check by Telegram ID
    clean_tg = str(invitee_telegram_id or "").strip()
    if clean_tg and referrer.telegram_id == clean_tg:
        return False, "Нельзя пригласить свой же Telegram-аккаунт"

    # Check registered telegram accounts of referrer
    if clean_tg:
        linked = db.query(ClientTelegramAccount).filter(
            ClientTelegramAccount.client_id == referrer.id,
            ClientTelegramAccount.telegram_id == clean_tg,
        ).first()
        if linked:
            return False, "Этот Telegram-аккаунт уже привязан к кабинету"

    # Ping-Pong / Cycle detection: A invited B, so B cannot invite A
    if invitee and referrer.referrer_id == invitee.id:
        return False, "Циклическое приглашение невозможно"

    # Disposable email
    if invitee_email and is_disposable_email(invitee_email):
        return False, "Временные почтовые адреса не поддерживаются"

    # Rate limiting on registrations per IP
    if invitee_ip and invitee_ip not in {"127.0.0.1", "localhost", "::1", ""}:
        recent_cutoff = now_utc() - timedelta(hours=1)
        ip_count = db.query(Client).filter(
            Client.registration_ip == invitee_ip,
            Client.created_at >= recent_cutoff,
        ).count()
        if ip_count >= MAX_REGISTRATIONS_PER_IP_HOUR:
            return False, "Превышен лимит регистраций с одного IP-адреса"

    # Ceiling cap on inviter
    active_referrals = db.query(Client).filter(
        Client.referrer_id == referrer.id,
        Client.referral_reward_granted.is_(True),
    ).count()
    if active_referrals >= MAX_REFERRALS_PER_INVITER_CAP:
        return False, "Достигнут максимальный лимит рефералов для аккаунта"

    return True, ""


def link_referral_and_grant_welcome(
    db: Session,
    invitee: Client,
    referrer: Client,
    *,
    client_ip: str = "",
    invitee_email: str = "",
    invitee_telegram_id: str = "",
) -> bool:
    if invitee.referrer_id:
        # Already linked to a referrer
        return False

    is_valid, reason = validate_referral_linkage(
        db,
        referrer,
        invitee,
        invitee_telegram_id=invitee_telegram_id or invitee.telegram_id,
        invitee_email=invitee_email,
        invitee_ip=client_ip,
    )
    if not is_valid:
        logger.warning(
            "referral_linkage_rejected",
            extra={"referrer_id": referrer.id, "invitee_id": invitee.id, "reason": reason},
        )
        return False

    invitee.referrer_id = referrer.id
    if client_ip:
        invitee.registration_ip = client_ip
    ensure_client_referral_code(invitee, db=db)
    db.commit()

    # Grant 1 000 ₽ welcome gift to invitee
    try:
        grant_money_balance(
            db,
            invitee,
            amount_kopeks=REFERRAL_WELCOME_BONUS_KOPEKS,
            note="Приветственный подарок 1 000 ₽ по приглашению коллеги",
            idempotency_key=f"ref_welcome_{invitee.id}",
            created_by="referral_program",
        )
        return True
    except Exception as exc:
        logger.error("referral_welcome_grant_failed", extra={"error": str(exc), "invitee_id": invitee.id})
        return False


def process_referral_on_job_completion(db: Session, job: Job) -> bool:
    if not job.client_id:
        return False

    client = db.get(Client, job.client_id)
    if not client or not client.referrer_id:
        return False

    if client.referral_reward_granted:
        return False

    # Check job validity: must be completed and not cancelled or internal smoke test
    status = str(getattr(job, "status", "") or "").lower()
    if status not in {"completed", "done"}:
        return False

    # Check for internal test tokens
    job_text = f"{getattr(job, 'title', '')} {getattr(job, 'message', '')}".lower()
    if any(tok in job_text for tok in ("smoke", "worker_smoke", "test_runner")):
        return False

    referrer = db.get(Client, client.referrer_id)
    if not referrer or not referrer.is_active:
        return False

    if referrer.id == client.id:
        return False

    # Award 1 000 ₽ to inviter
    try:
        grant_money_balance(
            db,
            referrer,
            amount_kopeks=REFERRAL_INVITER_REWARD_KOPEKS,
            note=f"Бонус 1 000 ₽ за первую выполненную задачу реферала {client.id[:8]}",
            idempotency_key=f"ref_reward_{client.id}",
            created_by="referral_program",
        )
        client.referral_reward_granted = True
        db.commit()
        logger.info(
            "referral_inviter_reward_granted",
            extra={"referrer_id": referrer.id, "referred_client_id": client.id},
        )
    except Exception as exc:
        logger.error("referral_inviter_reward_failed", extra={"error": str(exc), "referrer_id": referrer.id})
        return False

    # Notify inviter in Telegram if Telegram is linked
    tg_id = _get_client_primary_telegram_id(db, referrer)
    if tg_id:
        import asyncio
        asyncio.create_task(
            _send_telegram_inviter_notification(
                tg_id,
                "🎉 Вам начислено 1 000 ₽ на баланс!\n\n"
                "Приглашенный вами коллега успешно выполнил свою первую задачу в TenderLex.\n"
                "Ваш баланс пополнен на 1 000 ₽. Спасибо за рекомендацию!"
            )
        )

    return True


def _get_client_primary_telegram_id(db: Session, client: Client) -> str:
    tg_id = str(client.telegram_id or "").strip()
    if tg_id and tg_id.isdigit():
        return tg_id
    acc = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == client.id).first()
    if acc and acc.telegram_id and acc.telegram_id.isdigit():
        return acc.telegram_id
    return ""


async def _send_telegram_inviter_notification(chat_id: str, text: str) -> bool:
    token = config.bot_token
    if not token or not chat_id:
        return False
    try:
        from aiogram import Bot
        bot = Bot(token=token)
        try:
            await bot.send_message(chat_id=int(chat_id), text=text)
            return True
        finally:
            await bot.session.close()
    except Exception as exc:
        logger.warning("telegram_inviter_notification_error", extra={"error": str(exc), "chat_id": chat_id})
        return False


def get_referral_stats(db: Session, client: Client) -> dict[str, Any]:
    code = ensure_client_referral_code(client)
    db.commit()

    invited_count = db.query(Client.id).filter(Client.referrer_id == client.id).count()
    activated_count = db.query(Client.id).filter(
        Client.referrer_id == client.id,
        Client.referral_reward_granted.is_(True),
    ).count()

    bonus_earned_rub = activated_count * 1000
    balance_rub = max(0, int(client.money_balance_kopeks or 0)) // 100

    from .models import SystemSettings
    settings = db.query(SystemSettings).first()
    bot_raw = getattr(settings, "bot_telegram", "") if settings else ""
    bot_username = (bot_raw or "tenderlex_bot").replace("@", "").strip() or "tenderlex_bot"

    return {
        "referral_code": code,
        "invited_count": invited_count,
        "activated_count": activated_count,
        "bonus_earned_rub": bonus_earned_rub,
        "balance_rub": balance_rub,
        "invite_url_web": f"https://tenderlex.ru/cabinet?ref={code}",
        "invite_url_bot": f"https://t.me/{bot_username}?start=ref_{code}",
    }
