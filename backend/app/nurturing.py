from __future__ import annotations

import base64
import hashlib
import hmac
import html as html_lib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .config import config
from .db import SessionLocal
from .journey import _parse_rollout_at, record_journey_event
from .models import (
    Client,
    ClientTelegramAccount,
    Job,
    OnboardingReminder,
    SystemSettings,
    UserJourneyEvent,
    WebUser,
    now_utc,
)
from .web_auth import _send_email_verification_via_relay, _send_email_verification_via_smtp

logger = logging.getLogger("aipoisk.nurturing")

UNSUBSCRIBE_SECRET_SALT = "tenderlex-nurturing-unsub-salt-v1"


def get_unsubscribe_secret() -> bytes:
    key = str(config.admin_token or config.smtp_password or "tenderlex-default-unsub-key").strip()
    return f"{key}:{UNSUBSCRIBE_SECRET_SALT}".encode("utf-8")


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return now_utc()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def generate_unsubscribe_token(client_id: str, email_or_tg: str) -> str:
    payload = json.dumps({"cid": client_id, "rec": email_or_tg, "ts": int(now_utc().timestamp())})
    b64_payload = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")
    sig = hmac.new(get_unsubscribe_secret(), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return f"{b64_payload}.{sig}"


def verify_unsubscribe_token(token: str) -> tuple[str, str] | None:
    try:
        parts = token.strip().split(".")
        if len(parts) != 2:
            return None
        b64_payload, sig = parts
        expected_sig = hmac.new(get_unsubscribe_secret(), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        padded = b64_payload + "=" * (-len(b64_payload) % 4)
        raw_json = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        data = json.loads(raw_json)
        client_id = str(data.get("cid") or "").strip()
        recipient = str(data.get("rec") or "").strip()
        if not client_id:
            return None
        return client_id, recipient
    except Exception:
        return None


def unsubscribe_client(db: Session, client_id: str, reason: str = "user_request") -> bool:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return False
    client.marketing_unsubscribed = True
    for web_user in client.web_users:
        web_user.marketing_unsubscribed = True
    db.commit()
    record_journey_event(
        db,
        client_id,
        channel="web" if not client.telegram_id.isdigit() else "telegram",
        event_name="marketing_unsubscribed",
        outcome="success",
        reason_code=reason[:80],
    )
    return True


def unsubscribe_by_token(db: Session, token: str) -> tuple[bool, str]:
    verified = verify_unsubscribe_token(token)
    if not verified:
        return False, "Недействительная или устаревшая ссылка отписки."
    client_id, _ = verified
    ok = unsubscribe_client(db, client_id, reason="email_link")
    if ok:
        return True, "Вы успешно отписались от уведомлений и рассылок TenderLex."
    return False, "Клиент не найден."


def unsubscribe_by_telegram_id(db: Session, telegram_id: str | int) -> bool:
    tid_str = str(telegram_id).strip()
    account = (
        db.query(ClientTelegramAccount)
        .filter(ClientTelegramAccount.telegram_id == tid_str)
        .first()
    )
    client_id = account.client_id if account else None
    if not client_id:
        client = db.query(Client).filter(Client.telegram_id == tid_str).first()
        if client:
            client_id = client.id
    if not client_id:
        return False
    return unsubscribe_client(db, client_id, reason="telegram_inline_button")


@dataclass
class NurturingCandidate:
    client_id: str
    channel: str  # "telegram" | "email"
    recipient: str  # telegram_id or email
    step: str  # "step1" | "step2" | "step3"
    name: str
    client: Client


def get_due_nurturing_candidates(
    db: Session,
    settings: SystemSettings,
    *,
    current_time: datetime | None = None,
    enforce_work_hours: bool = True,
) -> list[NurturingCandidate]:
    if not bool(settings.onboarding_reminders_enabled):
        return []
    rollout_at = _parse_rollout_at(settings.onboarding_reminders_rollout_at)
    if rollout_at is None:
        return []

    now = _ensure_utc(current_time)
    if enforce_work_hours:
        moscow_hour = now.astimezone(ZoneInfo("Europe/Moscow")).hour
        if moscow_hour < 9 or moscow_hour >= 20:
            return []

    # All active, subscribed clients created after rollout
    clients = (
        db.query(Client)
        .filter(
            Client.is_active.is_(True),
            Client.marketing_unsubscribed.is_(False),
            Client.created_at >= rollout_at,
        )
        .all()
    )

    results: list[NurturingCandidate] = []

    for client in clients:
        # Determine channel & recipient
        channel = ""
        recipient = ""
        tg_account = next(
            (acc for acc in sorted(client.telegram_accounts, key=lambda a: a.created_at) if acc.is_active and str(acc.telegram_id or "").isdigit()),
            None,
        )
        if tg_account:
            channel = "telegram"
            recipient = tg_account.telegram_id
        elif client.web_users:
            web_user = next(
                (wu for wu in sorted(client.web_users, key=lambda u: u.created_at) if wu.is_active and wu.is_email_verified and not wu.marketing_unsubscribed),
                None,
            )
            if web_user and web_user.email:
                channel = "email"
                recipient = web_user.email

        if not channel or not recipient:
            continue

        # Get job counts and history
        jobs = db.query(Job).filter(Job.client_id == client.id).all()
        completed_jobs = [j for j in jobs if j.status == "completed"]
        pending_or_running_jobs = [j for j in jobs if j.status in ("pending", "running")]

        # Existing reminders for this client
        existing_reminders = {
            r.step: r
            for r in db.query(OnboardingReminder)
            .filter(OnboardingReminder.client_id == client.id, OnboardingReminder.status.in_(["claimed", "sent"]))
            .all()
        }

        client_created = _ensure_utc(client.created_at)

        # Step 1 Check: Registered >= 24h ago, <= 120h ago, 0 jobs created
        if "step1" not in existing_reminders:
            age_hours = (now - client_created).total_seconds() / 3600.0
            if 24.0 <= age_hours <= 120.0 and len(jobs) == 0:
                results.append(
                    NurturingCandidate(
                        client_id=client.id,
                        channel=channel,
                        recipient=recipient,
                        step="step1",
                        name=client.name or "Пользователь",
                        client=client,
                    )
                )
                continue

        # Step 2 Check: Completed >= 1 job, < 4 completed jobs, latest completed job >= 48h ago
        if "step2" not in existing_reminders and len(completed_jobs) in (1, 2, 3) and len(pending_or_running_jobs) == 0:
            latest_completed = max((_ensure_utc(j.created_at) for j in completed_jobs), default=client_created)
            job_age_hours = (now - latest_completed).total_seconds() / 3600.0
            if 48.0 <= job_age_hours <= 240.0:
                results.append(
                    NurturingCandidate(
                        client_id=client.id,
                        channel=channel,
                        recipient=recipient,
                        step="step2",
                        name=client.name or "Пользователь",
                        client=client,
                    )
                )
                continue

        # Step 3 Check: Completed >= 4 jobs, trial exhausted (balance < 99 RUB / 9900 kopeks)
        if "step3" not in existing_reminders and len(completed_jobs) >= 4 and client.money_balance_kopeks < 9900:
            latest_completed = max((_ensure_utc(j.created_at) for j in completed_jobs), default=client_created)
            completion_age_hours = (now - latest_completed).total_seconds() / 3600.0
            if 2.0 <= completion_age_hours <= 168.0:
                results.append(
                    NurturingCandidate(
                        client_id=client.id,
                        channel=channel,
                        recipient=recipient,
                        step="step3",
                        name=client.name or "Пользователь",
                        client=client,
                    )
                )
                continue

    return results


def claim_nurturing_step(db: Session, client_id: str, channel: str, step: str) -> OnboardingReminder | None:
    existing = (
        db.query(OnboardingReminder)
        .filter(
            OnboardingReminder.client_id == client_id,
            OnboardingReminder.channel == channel,
            OnboardingReminder.step == step,
        )
        .first()
    )
    if existing:
        if existing.status in ("claimed", "sent"):
            return None
        existing.status = "claimed"
        existing.claimed_at = now_utc()
        db.commit()
        return existing

    reminder = OnboardingReminder(
        client_id=client_id,
        channel=channel,
        step=step,
        status="claimed",
        claimed_at=now_utc(),
    )
    db.add(reminder)
    try:
        db.commit()
    except Exception:
        db.rollback()
        return None
    return reminder


# =========================================================================
# Content Generators
# =========================================================================

def build_nurturing_email_html(step: str, client_id: str, email: str, base_url: str = "https://tenderlex.ru") -> tuple[str, str]:
    unsub_token = generate_unsubscribe_token(client_id, email)
    unsub_link = html_lib.escape(f"{base_url}/api/customer/auth/unsubscribe?token={unsub_token}", quote=True)
    cabinet_link = html_lib.escape(f"{base_url}/cabinet", quote=True)
    article_link = html_lib.escape(f"{base_url}/baza-znaniy/kak-naiti-postavshchika-po-tz", quote=True)

    if step == "step1":
        subject = "Ваш тестовый доступ в TenderLex: как запустить первый поиск за 1 минуту"
        body_content = (
            '<tr><td style="padding-top:16px;padding-bottom:8px;">'
            '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Как запустить первый поиск по вашему ТЗ</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:10px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:16px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">'
            'На вашем балансе в <b>TenderLex</b> активен тестовый доступ на <b>4 бесплатные задачи (396 ₽)</b>.'
            '<br><br>'
            'Чтобы проверить работу сервиса, не нужно ничего настраивать — просто вставьте номер закупки ЕИС или прикрепите файл ТЗ (Word/PDF/Excel). '
            'Сервис за 2 минуты подберёт поставщиков с проверенными контактами и выделит ключевые риски.'
            '</div></td></tr>'
            '<tr><td align="center" style="padding-bottom:18px;">'
            '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 auto;">'
            '<tr><td align="center" bgcolor="#0f766e" style="border-radius:8px;">'
            f'<a href="{cabinet_link}" target="_blank" style="display:inline-block;padding:12px 32px;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;line-height:1.2;text-align:center;">Запустить первую задачу</a>'
            '</td></tr></table></td></tr>'
            '<tr><td style="padding-bottom:14px;">'
            '<div style="background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px;">'
            '<div style="font-size:11px;color:#64748b;margin-bottom:4px;font-weight:bold;">📖 Полезная статья из Базы знаний:</div>'
            f'<a href="{article_link}" target="_blank" style="color:#0f766e;font-size:12px;line-height:1.4;font-weight:bold;text-decoration:underline;">Как быстро найти прямых производителей по ТЗ и ГОСТам</a>'
            '</div></td></tr>'
        )
    elif step == "step2":
        subject = "3 полезные функции TenderLex, которые экономят часы работы снабженца"
        body_content = (
            '<tr><td style="padding-top:16px;padding-bottom:8px;">'
            '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Возможности TenderLex для работы с закупками</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:10px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:16px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">'
            'Вы уже протестировали первую задачу в TenderLex. Знаете ли вы, что сервис также умеет:'
            '<br><br>'
            '1️⃣ <b>Формировать официальный Запрос КП (DOCX)</b> по позициям вашего ТЗ для быстрой рассылки поставщикам.<br>'
            '2️⃣ <b>Сверять продукцию с Реестром Минпромторга (ГИСП)</b> под нацрежим ПП РФ № 616 и № 617.<br>'
            '3️⃣ <b>Находить скрытые штрафы и нетипичные ловушки</b> в документации 44-ФЗ / 223-ФЗ.'
            '<br><br>'
            'На вашем балансе ещё остались бесплатные задачи для проверки!'
            '</div></td></tr>'
            '<tr><td align="center" style="padding-bottom:18px;">'
            '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 auto;">'
            '<tr><td align="center" bgcolor="#0f766e" style="border-radius:8px;">'
            f'<a href="{cabinet_link}" target="_blank" style="display:inline-block;padding:12px 32px;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;line-height:1.2;text-align:center;">Перейти в личный кабинет</a>'
            '</td></tr></table></td></tr>'
        )
    else:  # step3
        subject = "Тестовые задачи TenderLex выполнены: как получить больше лимитов"
        body_content = (
            '<tr><td style="padding-top:16px;padding-bottom:8px;">'
            '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Тестовый доступ успешно завершён</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:10px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:16px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">'
            'Вы использовали стартовый баланс на 4 задачи в TenderLex. Надеемся, отчёты помогли сэкономить время при подборе поставщиков и анализе документации.'
            '<br><br>'
            'Если вашей компании требуются дополнительные лимиты для тестирования или корпоративный тариф для отдела снабжения — ответьте на это письмо или напишите нам в Telegram.'
            '</div></td></tr>'
            '<tr><td align="center" style="padding-bottom:18px;">'
            '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 auto;">'
            '<tr><td align="center" bgcolor="#0f766e" style="border-radius:8px;">'
            f'<a href="{cabinet_link}" target="_blank" style="display:inline-block;padding:12px 32px;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;line-height:1.2;text-align:center;">Открыть кабинет TenderLex</a>'
            '</td></tr></table></td></tr>'
        )

    html = (
        '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        f'<title>{html_lib.escape(subject)}</title></head>'
        '<body style="margin:0;padding:0;background:#ffffff;font-family:Arial,Helvetica,sans-serif;color:#1e293b;">'
        '<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;">'
        '<tr><td align="center" style="padding:16px 8px;">'
        '<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:580px;border-collapse:collapse;text-align:left;">'
        '<tr><td style="padding-bottom:12px;border-bottom:2px solid #0f766e;">'
        '<div style="font-size:22px;font-weight:bold;color:#0f766e;line-height:1.2;">TenderLex</div>'
        '<div style="font-size:12px;color:#64748b;margin-top:2px;">Сервис подбора поставщиков и анализа ТЗ</div>'
        '</td></tr>'
        f'{body_content}'
        '<tr><td style="border-top:1px solid #e2e8f0;padding-top:12px;padding-bottom:8px;">'
        '<div style="font-size:11px;color:#94a3b8;line-height:1.4;">'
        '© TenderLex • Сервис снабжения и аудита 44-ФЗ / 223-ФЗ • '
        f'<a href="{base_url}" target="_blank" style="color:#0f766e;text-decoration:none;font-weight:bold;">tenderlex.ru</a>'
        '</div></td></tr>'
        '<tr><td>'
        f'<div style="font-size:10px;color:#94a3b8;line-height:1.4;">Вы получили это письмо как зарегистрированный пользователь TenderLex. <a href="{unsub_link}" target="_blank" style="color:#94a3b8;text-decoration:underline;">Отписаться от рассылки</a></div>'
        '</td></tr>'
        '</table></td></tr></table></body></html>'
    )
    return subject, html


def build_nurturing_telegram_message(step: str, base_url: str = "https://tenderlex.ru") -> tuple[str, list[list[dict[str, str]]]]:
    if step == "step1":
        text = (
            "👋 <b>Здравствуйте!</b>\n\n"
            "На вашем балансе в TenderLex активен стартовый доступ на <b>4 бесплатные задачи</b> (396 ₽).\n\n"
            "Чтобы протестировать сервис, не нужно ничего настраивать — просто отправьте в чат <b>номер закупки ЕИС</b> или прикрепите <b>файл ТЗ</b> (Word/PDF/Excel).\n\n"
            "📖 <i>Полезный материал:</i> <a href=\"https://tenderlex.ru/baza-znaniy/kak-naiti-postavshchika-po-tz\">Как найти прямых поставщиков и производителей по ТЗ</a>"
        )
        buttons = [
            [{"text": "📖 Читать Базу знаний", "url": f"{base_url}/baza-znaniy"}],
            [{"text": "🔕 Отписаться от подсказок", "callback_data": "nurturing_unsubscribe"}],
        ]
    elif step == "step2":
        text = (
            "💡 <b>3 полезные возможности TenderLex для работы с ТЗ:</b>\n\n"
            "Вы уже протестировали первую задачу! Знаете ли вы, что в сервисе также можно:\n\n"
            "1️⃣ <b>Сформировать Запрос КП (DOCX)</b> по позициям ТЗ для быстрой рассылки поставщикам.\n"
            "2️⃣ <b>Сверить продукцию с Реестром Минпромторга (ГИСП)</b> под нацрежим ПП РФ № 616 и № 617.\n"
            "3️⃣ <b>Провести экспресс-аудит рисков</b> — найти скрытые штрафы и нетипичные требования в документации 44-ФЗ / 223-ФЗ.\n\n"
            "У вас на балансе ещё есть бесплатные задачи для проверки!"
        )
        buttons = [
            [{"text": "🔕 Отписаться от подсказок", "callback_data": "nurturing_unsubscribe"}],
        ]
    else:  # step3
        text = (
            "🏁 <b>Тестовые задачи успешно выполнены!</b>\n\n"
            "Вы использовали стартовые задачи TenderLex. Надеемся, отчёты помогли сэкономить время при подборе поставщиков и анализе документации.\n\n"
            "Если вам или отделу снабжения требуются дополнительные лимиты для тестирования, либо корпоративный тариф — напишите нам, начислим задачи или подготовим счёт."
        )
        buttons = [
            [{"text": "🔕 Отписаться от подсказок", "callback_data": "nurturing_unsubscribe"}],
        ]

    return text, buttons


async def dispatch_nurturing_candidate(db: Session, candidate: NurturingCandidate, bot: Any = None) -> bool:
    reminder = claim_nurturing_step(db, candidate.client_id, candidate.channel, candidate.step)
    if not reminder:
        return False

    success = False
    failure_reason = ""

    try:
        if candidate.channel == "telegram":
            if not bot:
                reminder.status = "failed"
                reminder.failed_at = now_utc()
                reminder.failure_code = "BotNotProvided"
                db.commit()
                return False

            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            text, button_rows = build_nurturing_telegram_message(candidate.step)
            inline_keyboard = [
                [InlineKeyboardButton(text=btn["text"], url=btn.get("url"), callback_data=btn.get("callback_data")) for btn in row]
                for row in button_rows
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

            await bot.send_message(
                chat_id=int(candidate.recipient),
                text=text,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=False,
            )
            success = True

        elif candidate.channel == "email":
            subject, html_body = build_nurturing_email_html(candidate.step, candidate.client_id, candidate.recipient)
            relay_url = str(config.email_relay_url or "").strip()
            web_user = db.query(WebUser).filter(WebUser.client_id == candidate.client_id).first()
            if not web_user:
                web_user = WebUser(client_id=candidate.client_id, email=candidate.recipient, name=candidate.name)

            if relay_url:
                success = _send_email_verification_via_relay(web_user, subject, html_body)
            else:
                success = _send_email_verification_via_smtp(web_user, subject, html_body, html_body)

            if not success:
                failure_reason = "EmailSendFailed"
    except Exception as exc:
        logger.exception("Failed to dispatch nurturing message for client %s: %s", candidate.client_id, exc)
        failure_reason = type(exc).__name__[:80]
        success = False

    if success:
        reminder.status = "sent"
        reminder.sent_at = now_utc()
        db.commit()
        record_journey_event(
            db,
            candidate.client_id,
            channel=candidate.channel,
            event_name="onboarding_reminder_sent",
            outcome="sent",
            reason_code=candidate.step,
        )
        return True
    else:
        reminder.status = "failed"
        reminder.failed_at = now_utc()
        reminder.failure_code = failure_reason or "UnknownError"
        db.commit()
        return False
