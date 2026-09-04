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
    step: str  # "step1" | "step2" | "step3" | "step1_final" | "step4_reengage"
    name: str
    client: Client


def get_due_nurturing_candidates(
    db: Session,
    settings: SystemSettings,
    *,
    current_time: datetime | None = None,
    enforce_work_hours: bool = True,
) -> list[NurturingCandidate]:
    onboarding_active = bool(settings.onboarding_reminders_enabled)
    reengage_active = bool(getattr(settings, "reengagement_reminders_enabled", False))
    if not onboarding_active and not reengage_active:
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

        if onboarding_active:
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

            # Step 1 Final Check: registered >= 14 days ago, 0 jobs, step1 was sent.
            # Последнее касание для тех, кто проигнорировал step1 — после него тишина навсегда.
            step1_reminder = existing_reminders.get("step1")
            if (
                "step1_final" not in existing_reminders
                and step1_reminder is not None
                and step1_reminder.status == "sent"
                and len(jobs) == 0
                and (now - client_created).total_seconds() >= 14 * 86400.0
            ):
                results.append(
                    NurturingCandidate(
                        client_id=client.id,
                        channel=channel,
                        recipient=recipient,
                        step="step1_final",
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

        # Step 4 Re-engage Check (opt-in flag): had >= 1 completed job, no active jobs,
        # silent for >= 10 days (past step2's 240h window). One message ever.
        if (
            reengage_active
            and "step4_reengage" not in existing_reminders
            and len(completed_jobs) >= 1
            and len(pending_or_running_jobs) == 0
        ):
            latest_completed = max((_ensure_utc(j.created_at) for j in completed_jobs), default=client_created)
            if (now - latest_completed).total_seconds() >= 10 * 86400.0:
                results.append(
                    NurturingCandidate(
                        client_id=client.id,
                        channel=channel,
                        recipient=recipient,
                        step="step4_reengage",
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

def build_nurturing_email_html(step: str, client_id: str, email: str, base_url: str = "https://tenderlex.ru", trial_summary: str = "") -> tuple[str, str]:
    unsub_token = generate_unsubscribe_token(client_id, email)
    unsub_link = html_lib.escape(f"{base_url}/api/customer/auth/unsubscribe?token={unsub_token}", quote=True)
    cabinet_link = html_lib.escape(f"{base_url}/cabinet", quote=True)
    article_link = html_lib.escape(f"{base_url}/baza-znaniy/kak-naiti-postavshchika-po-tz", quote=True)

    if step == "step1":
        subject = "Ваш пробный доступ в TenderLex: как запустить первый расчет за 1 минуту"
        body_content = (
            '<tr><td style="padding-top:16px;padding-bottom:8px;">'
            '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Как запустить первый расчет по вашему ТЗ</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:10px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:16px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">'
            'Если вы участвуете в госзакупках или рассчитываете спецификации по 44-ФЗ и 223-ФЗ, то знаете главную сложность — оперативно найти прямых производителей оборудования и материалов без лишних наценок посредников, когда сроки подачи горят.'
            '<br><br>'
            'На вашем балансе в <b>TenderLex</b> активен <b>бесплатный пробный доступ</b> (без привязки карты).'
            '<br><br>'
            'Сервис берет на себя рутину снабжения и тендерного расчета:<br>'
            '• <b>Разбирает спецификации любого формата:</b> Word, Excel, PDF, сканы — извлекает ГОСТы, маркоразмеры и характеристики;<br>'
            '• <b>За 2–3 минуты находит прямые контакты отделов сбыта:</b> email, телефоны, сайты заводов РФ и дилеров, сверяя продукцию с Реестром Минпромторга (ГИСП, ПП 616/617);<br>'
            '• <b>Формирует официальный Запрос КП:</b> готовый файл DOCX для отправки поставщикам одним кликом;<br>'
            '• <b>Подбирает товар и аналоги:</b> находит эквиваленты с обоснованием соответствия параметрам ТЗ заказчика;<br>'
            '• <b>Проводит экспресс-аудит документации:</b> выявляет скрытые штрафы, риски и нереалистичные сроки поставки.'
            '<br><br>'
            'Чтобы проверить сервис на реальной задаче, просто прикрепите файл ТЗ или укажите номер закупки ЕИС в личном кабинете.'
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
    elif step == "step1_final":
        subject = "Последнее напоминание: ваш пробный доступ в TenderLex ещё активен"
        body_content = (
            '<tr><td style="padding-top:16px;padding-bottom:8px;">'
            '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Ваш пробный доступ всё ещё активен</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:10px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:16px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">'
            'Напоминаем, что на вашем балансе в <b>TenderLex</b> сохранен <b>бесплатный пробный доступ</b>.'
            '<br><br>'
            'Если у вас прямо сейчас в работе есть спецификация, тендер 44-ФЗ / 223-ФЗ или расчет проекта — загрузите файл ТЗ. Сервис за пару минут соберет прямые контакты заводов, подготовит официальный Запрос КП, подберет аналоги или проверит проект контракта на скрытые риски.'
            '<br><br>'
            '<i>Это последнее напоминание — больше не побеспокоим. Если автоматизация снабжения сейчас не актуальна, просто нажмите «Отписаться» ниже.</i>'
            '</div></td></tr>'
            '<tr><td align="center" style="padding-bottom:18px;">'
            '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 auto;">'
            '<tr><td align="center" bgcolor="#0f766e" style="border-radius:8px;">'
            f'<a href="{cabinet_link}" target="_blank" style="display:inline-block;padding:12px 32px;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;line-height:1.2;text-align:center;">Запустить первую задачу</a>'
            '</td></tr></table></td></tr>'
        )
    elif step == "step2":
        subject = "3 ключевые возможности TenderLex для экономии времени тендерного отдела"
        body_content = (
            '<tr><td style="padding-top:16px;padding-bottom:8px;">'
            '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Возможности TenderLex для работы с закупками</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:10px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:16px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">'
            'Вы уже запустили первые расчеты в TenderLex. Напоминаем о трех ключевых инструментах сервиса, где снабженцы и тендерные специалисты экономят часы рутины:'
            '<br><br>'
            '1️⃣ <b>Поиск прямых производителей и дилеров:</b> сбор прямых email отделов сбыта, телефонов, сайтов, проверка по Реестру Минпромторга (ГИСП) и готовый файл Запроса КП (DOCX).<br>'
            '2️⃣ <b>Подбор товара и аналогов по ТЗ:</b> точный подбор моделей и эквивалентов по техническим характеристикам с формированием обоснования для заказчика (выгрузка в DOCX).<br>'
            '3️⃣ <b>Экспресс-аудит документации:</b> выявление кабальных штрафов, скрытых обязательств, нереалистичных сроков и требований нацрежима в проектах контрактов 44-ФЗ / 223-ФЗ.'
            '<br><br>'
            'На вашем балансе ещё есть средства — протестируйте эти возможности на ваших текущих закупках.'
            '</div></td></tr>'
            '<tr><td align="center" style="padding-bottom:18px;">'
            '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 auto;">'
            '<tr><td align="center" bgcolor="#0f766e" style="border-radius:8px;">'
            f'<a href="{cabinet_link}" target="_blank" style="display:inline-block;padding:12px 32px;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;line-height:1.2;text-align:center;">Перейти в личный кабинет</a>'
            '</td></tr></table></td></tr>'
        )
    elif step == "step4_reengage":
        subject = "Помощь с поиском заводов и расчетом ТЗ: TenderLex на связи"
        body_content = (
            '<tr><td style="padding-top:16px;padding-bottom:8px;">'
            '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Нужна помощь с текущими закупками?</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:10px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:16px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">'
            'Вы ранее рассчитывали задачи в TenderLex. Если прямо сейчас у вас в работе появились новые сложные спецификации, закупки по 44-ФЗ / 223-ФЗ или требуется срочно выйти на прямых изготовителей — сервис готов подключиться.'
            '<br><br>'
            'Загрузите ТЗ в личный кабинет: сервис за пару минут соберет контакты отделов сбыта заводов, сформирует Запрос КП, подберет аналоги или проверит проект контракта.'
            '<br><br>'
            'Если требуется разобрать нестандартную спецификацию или предоставить тестовые лимиты отделу снабжения — просто ответьте на это письмо.'
            '</div></td></tr>'
            '<tr><td align="center" style="padding-bottom:18px;">'
            '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 auto;">'
            '<tr><td align="center" bgcolor="#0f766e" style="border-radius:8px;">'
            f'<a href="{cabinet_link}" target="_blank" style="display:inline-block;padding:12px 32px;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;line-height:1.2;text-align:center;">Открыть кабинет TenderLex</a>'
            '</td></tr></table></td></tr>'
        )
    else:  # step3
        subject = "Тестовые расчеты в TenderLex выполнены: как подключить регулярный доступ"
        body_content = (
            '<tr><td style="padding-top:16px;padding-bottom:8px;">'
            '<div style="font-size:17px;font-weight:bold;color:#0f172a;line-height:1.3;">Тестовый доступ успешно завершён</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:10px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">Здравствуйте!</div>'
            '</td></tr>'
            '<tr><td style="padding-bottom:16px;">'
            '<div style="font-size:14px;line-height:1.5;color:#334155;">'
            'Вы использовали стартовый баланс в TenderLex. Надеемся, сервис помог оперативно найти прямые заводы, подобрать эквиваленты и защитить контракт от скрытых рисков.'
            '<br><br>'
            'Чтобы продолжить работу без пауз, выберите подходящий пакет в личном кабинете. А если требуется подключение для тендерного отдела или отдела снабжения — мы оперативно подготовим договор и счет для юрлица со всеми закрывающими документами (УПД/ЭДО).'
            '</div></td></tr>'
            '<tr><td align="center" style="padding-bottom:18px;">'
            '<table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 auto;">'
            '<tr><td align="center" bgcolor="#0f766e" style="border-radius:8px;">'
            f'<a href="{cabinet_link}" target="_blank" style="display:inline-block;padding:12px 32px;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;line-height:1.2;text-align:center;">Выбрать тариф в кабинете</a>'
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


def build_nurturing_telegram_message(step: str, base_url: str = "https://tenderlex.ru", trial_summary: str = "") -> tuple[str, list[list[dict[str, str]]]]:
    if step == "step1":
        text = (
            "👋 <b>Здравствуйте!</b>\n\n"
            "На вашем балансе в <b>TenderLex</b> активен <b>бесплатный пробный доступ</b> (без привязки карты).\n\n"
            "Сервис автоматизирует ключевую рутину снабжения и расчетов под 44-ФЗ и 223-ФЗ:\n\n"
            "1️⃣ <b>Поиск поставщиков по ТЗ:</b>\n"
            "• Разбирает спецификации любого формата: Word, Excel, PDF, сканы — извлекая ГОСТы и маркоразмеры;\n"
            "• За 2–3 минуты находит прямые контакты отделов сбыта заводов РФ и дилеров (email, телефоны, сайты);\n"
            "• Формирует готовый официальный Запрос КП (.docx) для оперативной отправки поставщикам;\n"
            "• Проверяет номенклатуру по реестру Минпромторга (ГИСП, ПП 616/617).\n\n"
            "2️⃣ <b>Подбор товара и аналогов:</b>\n"
            "• Точный подбор моделей и российских эквивалентов по характеристикам ТЗ с выгрузкой в Word (.docx).\n\n"
            "3️⃣ <b>Анализ документации:</b>\n"
            "• Экспресс-аудит проектов контрактов на кабальные штрафы, скрытые риски и нереалистичные сроки.\n\n"
            "👉 Чтобы протестировать на вашей закупке, отправьте в этот чат <b>номер закупки ЕИС</b> или прикрепите <b>файл ТЗ</b>.\n\n"
            "💳 <i>Списание средств происходит только после успешной выдачи готового результата.</i>\n\n"
            "📖 <i>Статья из Базы знаний:</i> <a href=\"https://tenderlex.ru/baza-znaniy/kak-naiti-postavshchika-po-tz\">Как быстро найти прямых производителей по ТЗ и ГОСТам</a>"
        )
        buttons = [
            [{"text": "📖 Читать Базу знаний", "url": f"{base_url}/baza-znaniy"}],
            [{"text": "🔕 Отписаться от подсказок", "callback_data": "nurturing_unsubscribe"}],
        ]
    elif step == "step1_final":
        text = (
            "👋 <b>Здравствуйте!</b>\n\n"
            "Напоминаем: на вашем балансе в <b>TenderLex</b> сохранен <b>бесплатный пробный доступ</b>.\n\n"
            "Если у вас прямо сейчас в работе есть спецификация или расчет к закупке 44-ФЗ / 223-ФЗ — отправьте файл ТЗ в этот чат:\n"
            "• За 2–3 минуты соберем контакты отделов сбыта заводов РФ и подготовим Запрос КП (.docx);\n"
            "• Подберем аналоги и эквиваленты под параметры заказчика;\n"
            "• Проверим проект контракта на кабальные штрафы и риски сроков.\n\n"
            "💳 <i>Списание средств происходит только после успешного отчёта.</i>\n\n"
            "<i>Это последнее напоминание — больше не побеспокоим. Если сервис сейчас не актуален, нажмите кнопку ниже.</i>"
        )
        buttons = [
            [{"text": "📖 Читать Базу знаний", "url": f"{base_url}/baza-znaniy"}],
            [{"text": "🔕 Не напоминать больше", "callback_data": "nurturing_unsubscribe"}],
        ]
    elif step == "step2":
        text = (
            "💡 <b>3 ключевые возможности TenderLex для работы с ТЗ:</b>\n\n"
            "Вы уже протестировали первую задачу! Напоминаем о полном арсенале сервиса под 44-ФЗ и 223-ФЗ:\n\n"
            "1️⃣ <b>Поиск поставщиков и Запрос КП:</b>\n"
            "Прямые заводы РФ и дилеры по маркоразмерам и ГОСТам ТЗ, email отделов продаж, телефоны, сайты и готовый файл Запроса КП (.docx). Проверка реестра Минпромторга (ГИСП).\n\n"
            "2️⃣ <b>Подбор товара и аналогов:</b>\n"
            "Расшифровка сложных характеристик, подбор эквивалентов под ТЗ заказчика с выгрузкой в Word (.docx).\n\n"
            "3️⃣ <b>Анализ документации:</b>\n"
            "Мгновенный аудит проектов контрактов по номеру закупки ЕИС — выявление штрафов выше нормы, скрытых обязательств и ловушек нацрежима.\n\n"
            "На вашем балансе ещё есть средства — протестируйте эти сценарии на текущих расчетах!"
        )
        buttons = [
            [{"text": "🔕 Отписаться от подсказок", "callback_data": "nurturing_unsubscribe"}],
        ]
    elif step == "step4_reengage":
        text = (
            "👋 <b>Здравствуйте! Давно не виделись — TenderLex на связи.</b>\n\n"
            "Вы ранее уже выполняли расчеты в сервисе. Если прямо сейчас у вас в работе появились новые сложные спецификации по 44-ФЗ / 223-ФЗ, горят сроки подачи или требуется срочно выйти на прямых изготовителей — сервис готов подключиться:\n\n"
            "1️⃣ <b>Поиск прямых производителей РФ и дилеров:</b>\n"
            "Сбор контактов отделов сбыта (email, телефоны, сайты), оформление Запроса КП (.docx), сверка с реестром Минпромторга (ГИСП, ПП 616/617).\n\n"
            "2️⃣ <b>Подбор товара и аналогов по ТЗ:</b>\n"
            "Точный подбор моделей и эквивалентов под требования заказчика с выгрузкой в Word (.docx).\n\n"
            "3️⃣ <b>Экспресс-аудит документации:</b>\n"
            "Проверка проектов контрактов на кабальные штрафы, скрытые риски и нереалистичные сроки.\n\n"
            "Просто отправьте файл спецификации или номер ЕИС в чат — результат будет готов за 2–3 минуты.\n\n"
            "Если для отдела снабжения нужны дополнительные лимиты для тестирования сложных закупок — напишите нам в ответ, поможем!"
        )
        buttons = [
            [{"text": "🔕 Отписаться от подсказок", "callback_data": "nurturing_unsubscribe"}],
        ]
    else:  # step3
        text = (
            "🏁 <b>Тестовые расчеты в TenderLex выполнены!</b>\n\n"
            "Вы использовали стартовый баланс сервиса. Надеемся, TenderLex сэкономил вам часы работы при поиске прямых заводов, подборе аналогов и анализе документации.\n\n"
            "Чтобы продолжить регулярную работу без пауз:\n"
            "• Пополните баланс или выберите пакет в кабинете: https://tenderlex.ru/cabinet\n"
            "• Если требуется подключение для тендерного отдела или отдела снабжения — напишите нам в ответ, оперативно выставим счет для юрлица со всеми закрывающими документами (УПД/ЭДО)."
        )
        buttons = [
            [{"text": "🔕 Отписаться от подсказок", "callback_data": "nurturing_unsubscribe"}],
        ]

    return text, buttons


async def dispatch_nurturing_candidate(db: Session, candidate: NurturingCandidate, bot: Any = None) -> bool:
    from .billing import trial_grant_summary_text

    reminder = claim_nurturing_step(db, candidate.client_id, candidate.channel, candidate.step)
    if not reminder:
        return False

    success = False
    failure_reason = ""

    try:
        trial_summary = trial_grant_summary_text(db, candidate.client)
        if candidate.channel == "telegram":
            if not bot:
                reminder.status = "failed"
                reminder.failed_at = now_utc()
                reminder.failure_code = "BotNotProvided"
                db.commit()
                return False

            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            text, button_rows = build_nurturing_telegram_message(candidate.step, trial_summary=trial_summary)
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
            subject, html_body = build_nurturing_email_html(
                candidate.step, candidate.client_id, candidate.recipient, trial_summary=trial_summary
            )
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


# =========================================================================
# Funnel Analytics (P3)
# =========================================================================

NURTURING_STEPS = ("step1", "step1_final", "step2", "step3", "step4_reengage")


def get_nurturing_funnel_stats(db: Session, settings: SystemSettings) -> dict:
    """Конверсия воронки напоминаний: регистрации → задачи, отправки по шагам."""
    rollout_at = _parse_rollout_at(settings.onboarding_reminders_rollout_at)

    clients_q = db.query(Client).filter(Client.is_active.is_(True))
    if rollout_at is not None:
        clients_q = clients_q.filter(Client.created_at >= rollout_at)
    clients = clients_q.all()
    client_ids = [c.id for c in clients]

    stats: dict[str, Any] = {
        "registered_since_rollout": len(clients),
        "unsubscribed": sum(1 for c in clients if c.marketing_unsubscribed),
        "steps": {},
        "funnel": {},
    }

    # Отправки по шагам + конверсия каждого шага в первую задачу
    sent_reminders = (
        db.query(OnboardingReminder)
        .filter(
            OnboardingReminder.status == "sent",
            OnboardingReminder.step.in_(NURTURING_STEPS),
            OnboardingReminder.client_id.in_(client_ids),
        )
        .all()
        if client_ids
        else []
    )
    sent_by_step: dict[str, list[str]] = {}
    for reminder in sent_reminders:
        sent_by_step.setdefault(reminder.step, []).append(reminder.client_id)

    clients_with_jobs = (
        {
            row[0]
            for row in db.query(Job.client_id)
            .filter(Job.client_id.in_(client_ids))
            .distinct()
            .all()
        }
        if client_ids
        else set()
    )

    for step in NURTURING_STEPS:
        sent_ids = sent_by_step.get(step, [])
        converted = sum(1 for cid in sent_ids if cid in clients_with_jobs)
        stats["steps"][step] = {
            "sent": len(sent_ids),
            "converted_to_first_job": converted,
            "conversion_rate": round(converted / len(sent_ids), 3) if sent_ids else None,
        }

    activated = sum(1 for cid in client_ids if cid in clients_with_jobs)
    stats["funnel"] = {
        "registered": len(clients),
        "activated_created_job": activated,
        "activation_rate": round(activated / len(clients), 3) if clients else None,
    }
    return stats
