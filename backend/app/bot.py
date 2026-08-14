from __future__ import annotations
import os
import sys
import time
import json
import re
import asyncio

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, ForceReply, ErrorEvent, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, MenuButtonDefault, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from fastapi import HTTPException

from .account_linking import (
    TELEGRAM_TO_WEB,
    AccountLinkError,
    cabinet_link,
    consume_web_to_telegram_token,
    create_account_link_token,
)

from .billing import (
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    STATUS_CUSTOMER_DECLINED,
    BillingError,
    charge_job_reservation,
    client_uses_trial_access,
    client_service_balance_summary,
    expire_stale_confirmations,
    job_has_unsettled_reservation,
    list_tariffs,
    release_job_reservation,
    reserve_job_units,
    tariff_to_dict,
)
from .config import config
from .db import SessionLocal, init_db
from .document_parser import sanitize_filename
from .jobs import (
    MODE_ANALYSIS_AND_SUPPLIERS,
    MODE_PROCUREMENT_REPORT,
    MODE_SUPPLIER_SEARCH,
    SUPPLIER_POLICY_MINPROM_ONLY,
    SUPPLIER_POLICY_MINPROM_PRIORITY,
    SUPPLIER_POLICY_NORMAL,
    TERMINAL_JOB_STATUSES,
    cleanup_expired_jobs,
    cancel_running_job,
    create_job,
    job_dir,
    package_job_output_files,
    package_job_output_items,
)
from .main import create_additional_supplier_search_for_client, job_can_find_more_suppliers
from .journey import claim_reminder, record_journey_event, reminder_candidates
from .legal import (
    LEGAL_DOCUMENT_PERSONAL_DATA,
    LEGAL_DOCUMENT_TERMS,
    LEGAL_INDEX_URL,
    LEGAL_VERSION,
    PERSONAL_DATA_URL,
    PRIVACY_URL,
    TERMS_URL,
    record_legal_acceptance,
)
from .models import BillingTransaction, Client, Job, now_utc
from .procurement_sources import source_label, source_payloads_from_text
from .repository import client_access_error, get_client_by_telegram_id, get_or_create_settings, get_or_create_trial_client_by_telegram_id, seed_owner_client, supplier_target_for_client
from .result_offers import (
    CONFIRMATION_KIND_REGISTRY_FALLBACK,
    ResultOfferConflict,
    ResultOfferGone,
    accept_job_result_offer,
    active_result_offer_output_items,
    billing_kinds_for_result_delivery,
    claim_job_result_offer_delivery,
    complete_job_result_offer_delivery,
    decline_job_result_offer,
    expire_result_offers,
    fail_job_result_offer_delivery,
    result_offer_to_dict,
)

router = Router(name="private_customer_bot")
group_safety_router = Router(name="group_safety")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
group_safety_router.message.filter(F.chat.type != ChatType.PRIVATE)
group_safety_router.callback_query.filter(F.message.chat.type != ChatType.PRIVATE)
logger = logging.getLogger(__name__)
PENDING_MODES: dict[int, str] = {}
PENDING_SUPPLIER_POLICIES: dict[int, str] = {}
SCENARIO_SUPPLIERS = "supplier_search"
SCENARIO_REPORT = "report"
SCENARIO_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"
BUTTON_SUPPLIERS = "🔎 Поставщики по ТЗ"
BUTTON_REPORT = "📄 Анализ закупки"
BUTTON_ANALYSIS_AND_SUPPLIERS = "📄🔎 Анализ + поиск"
BUTTON_CREATE = "🚀 Создать"
BUTTON_STATUS = "🕘 Задачи"
BUTTON_ACCESS = "📊 Кабинет"
BUTTON_TARIFFS = "💳 Тарифы"
BUTTON_HELP = "❓ Помощь"
BUTTON_CONTACTS = "📞 Контакты"
BUTTON_LEGAL = "⚖️ Правовая информация"
BUTTON_RUN_BATCH = "▶️ Запустить"
BUTTON_CANCEL_BATCH = "🗑 Очистить"
BUTTON_BACK_MAIN = "⬅️ Меню"
BUTTON_PROCESSING_STATUS = "⏳ В работе"
BUTTON_CANCEL_PROCESSING = "⛔ Отменить"

BRAND_NAME = "TenderLex"
BOT_SHORT_DESCRIPTION = "TenderLex: анализ закупок, архивы документов и поставщики."
BOT_DESCRIPTION = (
    "TenderLex помогает работать с закупками: анализирует документацию по номеру извещения, "
    "ссылке, файлам или архивам, ищет поставщиков по ТЗ и выдаёт готовые файлы в Telegram.\n\n"
    "Чтобы начать, откройте бота, нажмите «Start» или «Запустить» и используйте кнопки меню."
)
ONBOARDING_REMINDER_TEXT = (
    "👋 Добрый день! Нужна помощь с первым запуском TenderLex?\n\n"
    "У вас открыт пробный доступ — можно проверить сервис на реальной задаче. "
    "Проще всего начать с режима «🔎 Поставщики по ТЗ»: нажмите «🚀 Создать» и отправьте ТЗ, "
    "спецификацию или описание позиции.\n\n"
    "TenderLex найдёт и проверит поставщиков, подготовит список компаний и контактов.\n\n"
    "Можно работать здесь, в боте, или в личном кабинете на https://tenderlex.ru. "
    "Если не уверены, какой режим выбрать, откройте «📞 Контакты» — подскажем."
)
AI_CUSTOMER_NOTE = (
    "Важно: результат подготовлен с помощью ИИ и помогает быстрее оценить закупку. "
    "Критичные условия сверяйте с официальной документацией и первоисточниками."
)
AI_HELP_NOTE = (
    "ИИ помогает быстро подготовить первичный анализ, но важные юридические, финансовые "
    "и технические условия лучше дополнительно сверять по официальным документам."
)
INDIVIDUAL_TERMS_NOTE = (
    "Возможен индивидуальный подход: стоимость поиска, анализа и добора можно настроить под вашу задачу."
)
BOT_PAYMENT_INSTRUCTIONS = (
    "🧾 Чтобы пополнить баланс:\n"
    "1. Посмотрите стоимость функций выше.\n"
    "2. Напишите владельцу сервиса в Telegram или на email.\n"
    "3. Укажите сумму пополнения и ваш Telegram ID.\n"
    "4. После подтверждения оплаты деньги будут зачислены на баланс."
)
OWNER_ALERT_STATUSES = {"failed", "needs_review"}
OWNER_ALERTED_KEYS: set[tuple[str, str]] = set()
BOT_TERMINAL_JOB_STATUSES = set(TERMINAL_JOB_STATUSES) | {"delivery_expired"}


@dataclass
class PendingBatch:
    telegram_id: str
    mode: str
    files: list[tuple[str, bytes]]
    sources: list[dict] = field(default_factory=list)
    supplier_search_policy: str = SUPPLIER_POLICY_NORMAL


@dataclass
class JobProgressSnapshot:
    id: str
    mode: str
    status: str
    progress: int
    message: str
    error: str
    created_at: datetime | None
    confirmation_kind: str = ""
    confirmation_outcome: str = ""
    offer_delivery_outcome: str = ""
    registry_verified_count: int = 0
    alternative_verified_count: int = 0
    offer_charge_text: str = ""


PENDING_UPLOADS: dict[int, PendingBatch] = {}
CHAT_UPLOAD_LOCKS: dict[int, asyncio.Lock] = {}
JOB_DELIVERY_LOCKS: dict[str, asyncio.Lock] = {}
DELIVERED_JOB_IDS: set[str] = set()
BATCH_RUNNING_CHATS: set[int] = set()
BOT_CANCEL_NOTIFIED_JOBS: set[str] = set()
TEXT_TZ_MIN_CHARS = 50
TEXT_TZ_MIN_WORDS = 6
TELEGRAM_CAPTION_LIMIT = 1024


@router.error()
async def unhandled_bot_error(event: ErrorEvent) -> bool:
    exception = event.exception
    logger.error(
        "Unhandled Telegram update error",
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer(
                "Не удалось выполнить действие. Попробуйте ещё раз.",
                show_alert=True,
            )
        elif event.update.message:
            await event.update.message.answer(
                "⚠️ Не удалось выполнить действие. Попробуйте ещё раз или нажмите /start.",
                reply_markup=main_menu(),
            )
    except Exception as reply_error:
        logger.warning("Could not send Telegram error notice: %s", reply_error)
    return True


def _pending_input_count(pending: PendingBatch) -> int:
    return len(pending.files) + len(pending.sources)


def _scenario_accepts_source_links(scenario: str) -> bool:
    return scenario in {SCENARIO_REPORT, SCENARIO_ANALYSIS_AND_SUPPLIERS}


def _scenario_uses_supplier_policy(scenario: str) -> bool:
    return scenario in {SCENARIO_SUPPLIERS, SCENARIO_ANALYSIS_AND_SUPPLIERS}


def _scenario_job_mode(scenario: str) -> str:
    if scenario == SCENARIO_REPORT:
        return MODE_PROCUREMENT_REPORT
    if scenario == SCENARIO_ANALYSIS_AND_SUPPLIERS:
        return MODE_ANALYSIS_AND_SUPPLIERS
    return MODE_SUPPLIER_SEARCH


def _clear_pending_state(chat_id: int) -> bool:
    had_state = any(chat_id in state for state in (PENDING_UPLOADS, PENDING_MODES, PENDING_SUPPLIER_POLICIES))
    PENDING_UPLOADS.pop(chat_id, None)
    PENDING_MODES.pop(chat_id, None)
    PENDING_SUPPLIER_POLICIES.pop(chat_id, None)
    return had_state


def _select_scenario(chat_id: int, scenario: str) -> bool:
    expected_mode = _scenario_job_mode(scenario)
    pending = PENDING_UPLOADS.get(chat_id)
    cleared_incompatible = bool(pending and pending.mode != expected_mode)
    if cleared_incompatible:
        PENDING_UPLOADS.pop(chat_id, None)
    PENDING_MODES[chat_id] = scenario
    if _scenario_uses_supplier_policy(scenario):
        PENDING_SUPPLIER_POLICIES[chat_id] = SUPPLIER_POLICY_NORMAL
    else:
        PENDING_SUPPLIER_POLICIES.pop(chat_id, None)
    return cleared_incompatible


def _scenario_switch_note(cleared: bool) -> str:
    return "\n\n🗑 Материалы предыдущего сценария очищены, чтобы задачи не смешались." if cleared else ""


def _supplier_policy_for_chat(chat_id: int) -> str:
    return PENDING_SUPPLIER_POLICIES.get(chat_id, SUPPLIER_POLICY_NORMAL)


def _supplier_policy_label(policy: str) -> str:
    if policy == SUPPLIER_POLICY_MINPROM_ONLY:
        return "Только реестр"
    if policy == SUPPLIER_POLICY_MINPROM_PRIORITY:
        return "Реестр в приоритете"
    return "Обычный поиск"


def supplier_policy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Обычный поиск", callback_data=f"supplier_policy:{SUPPLIER_POLICY_NORMAL}")],
            [InlineKeyboardButton(text="Только реестр", callback_data=f"supplier_policy:{SUPPLIER_POLICY_MINPROM_ONLY}")],
            [InlineKeyboardButton(text="Реестр в приоритете", callback_data=f"supplier_policy:{SUPPLIER_POLICY_MINPROM_PRIORITY}")],
        ]
    )


def _supplier_policy_prompt_text(scenario: str) -> str:
    prefix = "📄🔎 Анализ + поиск" if scenario == SCENARIO_ANALYSIS_AND_SUPPLIERS else "🔎 Поставщики по ТЗ"
    return (
        f"{prefix}\n\n"
        "Выберите режим поиска поставщиков по реестру Минпромторга. "
        "Если не выбирать, будет обычный поиск."
    )


def _source_link_rejection_text() -> str:
    return (
        "⚠️ Номер извещения не добавлен\n\n"
        "Сейчас выбран поиск поставщиков. Для него нужен файл ТЗ/ООЗ или текстовое описание объекта закупки.\n\n"
        f"Чтобы работать по номеру извещения, сначала выберите «{BUTTON_REPORT}» "
        f"или «{BUTTON_ANALYSIS_AND_SUPPLIERS}»."
    )


def _looks_like_supplier_text_tz(text: str) -> bool:
    cleaned = str(text or "").strip()
    if len(cleaned) < TEXT_TZ_MIN_CHARS:
        return False
    words = _text_words(cleaned)
    if len(words) < TEXT_TZ_MIN_WORDS:
        return False
    lowered = cleaned.lower()
    markers = (
        "тз",
        "техничес",
        "описание объекта",
        "объект закуп",
        "закуп",
        "поставка",
        "поставщик",
        "производител",
        "требуется",
        "необходим",
        "характерист",
        "спецификац",
        "количество",
        "гост",
        " ту ",
        " шт",
    )
    return any(marker in lowered for marker in markers)


def _text_words(text: str) -> list[str]:
    return [
        word
        for word in text.replace("/", " ").replace("\\", " ").split()
        if word.strip(".,:;!?()[]{}«»\"'")
    ]


def _supplier_text_tz_payload(text: str, *, index: int | None = None) -> tuple[str, bytes, str]:
    cleaned = str(text or "").strip()
    title = _supplier_text_tz_title(cleaned)
    suffix = f"_{index}" if index is not None else ""
    filename = sanitize_filename(f"{title or 'ТЗ из сообщения'}{suffix}.txt")
    return filename, cleaned.encode("utf-8"), title or "ТЗ из сообщения"


def _supplier_text_tz_title(text: str) -> str:
    for line in str(text or "").splitlines():
        cleaned = " ".join(line.split()).strip(" .,:;\"'")
        if cleaned:
            return cleaned[:120]
    return ""


def _source_payloads_for_scenario(scenario: str, text: str) -> list[dict]:
    if not _scenario_accepts_source_links(scenario):
        return []
    return source_payloads_from_text(text)


def _add_pending_sources(pending: PendingBatch, sources: list[dict]) -> int:
    existing = {str(item.get("value") or "") for item in pending.sources}
    added = 0
    for source in sources:
        if source["value"] not in existing:
            pending.sources.append(source)
            existing.add(source["value"])
            added += 1
    return added


def _supplier_multi_job_specs(pending: PendingBatch) -> list[tuple[str, list[tuple[str, bytes]]]]:
    if pending.mode != MODE_SUPPLIER_SEARCH:
        return []
    return [
        (Path(filename).stem[:120], [(filename, content)])
        for filename, content in pending.files
    ]


def _telegram_user_fields(message: Message) -> tuple[str, str, str]:
    user = message.from_user
    telegram_id = str(user.id if user else "")
    username = str(getattr(user, "username", "") or "")
    name = " ".join(
        item
        for item in [
            str(getattr(user, "first_name", "") or "").strip(),
            str(getattr(user, "last_name", "") or "").strip(),
        ]
        if item
    )
    return telegram_id, username, name


def _record_telegram_event(
    message: Message,
    event_name: str,
    *,
    mode: str = "",
    outcome: str = "",
    reason_code: str = "",
) -> None:
    telegram_id = str(message.from_user.id if message.from_user else "")
    db = SessionLocal()
    try:
        client, account_error = get_client_by_telegram_id(db, telegram_id)
        if client and not account_error:
            record_journey_event(
                db,
                client.id,
                channel="telegram",
                event_name=event_name,
                mode=mode,
                outcome=outcome,
                reason_code=reason_code,
            )
    except Exception as exc:
        rollback = getattr(db, "rollback", None)
        if callable(rollback):
            rollback()
        logger.warning("Telegram journey event was skipped: %s", exc)
    finally:
        db.close()


def _chat_upload_lock(chat_id: int) -> asyncio.Lock:
    lock = CHAT_UPLOAD_LOCKS.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        CHAT_UPLOAD_LOCKS[chat_id] = lock
    return lock


def _supplier_multi_intro_text() -> str:
    return (
        "🔎 Поставщики по ТЗ\n\n"
        "Отправьте ТЗ файлом, текстом или архивом. Если ТЗ несколько, по каждому будет отдельный поиск поставщиков.\n"
        "Если одно ТЗ состоит из нескольких файлов, загрузите эти файлы одним архивом.\n\n"
        "1. Отправьте одно или несколько ТЗ.\n"
        "2. Проверьте количество добавленных ТЗ.\n"
        f"3. Нажмите «{BUTTON_RUN_BATCH}»."
    )


def _pending_added_text(pending: PendingBatch, *, max_files: int, added_sources: int = 0) -> str:
    if pending.mode == MODE_SUPPLIER_SEARCH:
        lines = [
            "✅ ТЗ добавлено",
            f"• В комплекте: {len(pending.files)}/{max_files}",
            "",
        ]
        if len(pending.files) > 1:
            lines.append(
                "⚠️ Эти файлы будут обработаны как разные ТЗ. "
                "Если это части одного ТЗ, очистите комплект и загрузите их одним архивом."
            )
        else:
            lines.append("Если одно ТЗ состоит из нескольких файлов, загрузите эти файлы одним архивом.")
        lines.append(f"Добавьте ещё отдельное ТЗ или нажмите «{BUTTON_RUN_BATCH}».")
        return "\n".join(lines)
    lines = [
        "✅ Материалы добавлены",
        f"• Файлов: {len(pending.files)}/{max_files}",
    ]
    if pending.sources:
        lines.append(f"• Источников: {len(pending.sources)}")
    lines.extend(["", f"Добавьте ещё документы или нажмите «{BUTTON_RUN_BATCH}»."])
    return "\n".join(lines)


def _source_added_text(pending: PendingBatch) -> str:
    return (
        "📎 Источник добавлен\n\n"
        f"✅ Источников: {len(pending.sources)}\n"
        f"Можно добавить документы или нажать «{BUTTON_RUN_BATCH}»."
    )


def _batch_running_text() -> str:
    return (
        "⏳ Обработка уже идёт\n\n"
        "Новые действия пока не запускаются. Я обновляю статус и пришлю файл, когда он будет готов.\n"
        f"Если запуск ошибочный, нажмите «{BUTTON_CANCEL_PROCESSING}»."
    )


async def _download_document_content(message: Message, bot: Bot) -> tuple[str, bytes]:
    document = message.document
    filename = sanitize_filename(document.file_name or "document")
    temp_dir = config.storage_path / "telegram" / str(message.chat.id)
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / filename
    last_error: Exception | None = None
    try:
        for attempt in range(3):
            try:
                file = await bot.get_file(document.file_id, request_timeout=60)
                await bot.download_file(file.file_path, destination=temp_path, timeout=120)
                return filename, temp_path.read_bytes()
            except (TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Не удалось загрузить файл из Telegram: {filename}") from last_error
    finally:
        temp_path.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def _cleanup_telegram_temp_storage(*, max_age_hours: int = 24, now: datetime | None = None) -> int:
    root = config.storage_path / "telegram"
    if not root.exists():
        return 0
    cutoff = (now or now_utc()) - timedelta(hours=max(1, max_age_hours))
    removed = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    for directory in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    return removed


def _reserve_created_job(db, client: Client, job: Job) -> str:
    try:
        reserve_job_units(db, client, job)
    except BillingError as exc:
        job.status = "failed"
        job.progress = 100
        job.message = "Задача не запущена"
        job.error = str(exc)
        job.completed_at = now_utc()
        db.commit()
        return str(exc)
    return ""


def _discard_unlaunched_jobs(db, jobs: list[Job]) -> None:
    for job in reversed(jobs):
        release_job_reservation(db, job, note="Резерв возвращён: комплект не был запущен")
        db.query(BillingTransaction).filter(BillingTransaction.job_id == job.id).delete(synchronize_session=False)
        shutil.rmtree(job_dir(job.id), ignore_errors=True)
        db.delete(job)
        db.commit()


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_CREATE), KeyboardButton(text=BUTTON_STATUS)],
            [KeyboardButton(text=BUTTON_ACCESS), KeyboardButton(text=BUTTON_TARIFFS)],
            [KeyboardButton(text=BUTTON_HELP), KeyboardButton(text=BUTTON_CONTACTS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def create_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_SUPPLIERS), KeyboardButton(text=BUTTON_REPORT)],
            [KeyboardButton(text=BUTTON_ANALYSIS_AND_SUPPLIERS)],
            [KeyboardButton(text=BUTTON_BACK_MAIN)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите сценарий",
    )


def batch_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_RUN_BATCH), KeyboardButton(text=BUTTON_CANCEL_BATCH)],
            [KeyboardButton(text=BUTTON_BACK_MAIN)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Добавьте материалы или запустите обработку",
    )


def processing_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_PROCESSING_STATUS), KeyboardButton(text=BUTTON_STATUS)],
            [KeyboardButton(text=BUTTON_CANCEL_PROCESSING)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Дождитесь завершения обработки",
    )


def _chat_has_processing_job(chat_id: int) -> bool:
    if chat_id in BATCH_RUNNING_CHATS:
        return True
    db = SessionLocal()
    try:
        return bool(
            db.query(Job.id)
            .filter(Job.created_by_telegram_id == str(chat_id))
            .filter(Job.status.in_(["pending", "running"]))
            .first()
        )
    except Exception:
        return False
    finally:
        try:
            db.close()
        except Exception:
            pass


def _active_processing_jobs_for_chat(db, chat_id: int) -> list[Job]:
    return (
        db.query(Job)
        .filter(Job.created_by_telegram_id == str(chat_id))
        .filter(Job.status.in_(["pending", "running"]))
        .order_by(Job.created_at.desc())
        .all()
    )


def _cancel_processing_job(db, job: Job, *, note: str, message: str) -> bool:
    if job.status not in {"pending", "running"}:
        return False
    release_job_reservation(db, job, note=note)
    now = now_utc()
    job.status = "cancelled"
    job.progress = 100
    job.error = ""
    job.message = message
    job.completed_at = now
    job.updated_at = now
    db.commit()
    cancel_running_job(str(job.id))
    BOT_CANCEL_NOTIFIED_JOBS.add(str(job.id))
    return True


def _cancel_processing_jobs_for_chat(chat_id: int) -> int:
    db = SessionLocal()
    try:
        jobs = _active_processing_jobs_for_chat(db, chat_id)
        if not jobs:
            return 0
        cancelled_count = 0
        for job in jobs:
            if _cancel_processing_job(
                db,
                job,
                note="Резерв возвращён: задача отменена в Telegram",
                message="Задача отменена в Telegram",
            ):
                cancelled_count += 1
        return cancelled_count
    finally:
        db.close()


def _menu_for_chat(chat_id: int) -> ReplyKeyboardMarkup:
    if _chat_has_processing_job(chat_id):
        return processing_menu()
    return main_menu()


async def _reject_if_chat_processing(message: Message) -> bool:
    if not _chat_has_processing_job(message.chat.id):
        return False
    await message.answer(_batch_running_text(), reply_markup=processing_menu())
    return True


def _mode_label(mode: str) -> str:
    if mode == MODE_PROCUREMENT_REPORT:
        return "анализ документации"
    if mode == MODE_ANALYSIS_AND_SUPPLIERS:
        return "анализ и поиск поставщиков"
    return "поиск поставщиков"


def _job_mode_for_scenario(scenario: str) -> str:
    if scenario == SCENARIO_REPORT:
        return MODE_PROCUREMENT_REPORT
    if scenario == SCENARIO_ANALYSIS_AND_SUPPLIERS:
        return MODE_ANALYSIS_AND_SUPPLIERS
    return MODE_SUPPLIER_SEARCH


def _status_label(status: str) -> str:
    labels = {
        "pending": "в очереди",
        "running": "в работе",
        "completed": "готово",
        "partial": "частично готово",
        "needs_review": "нужна проверка",
        "failed": "ошибка",
        "cancelled": "отменено",
        STATUS_AWAITING_CUSTOMER_CONFIRMATION: "ожидает решения",
        STATUS_CUSTOMER_DECLINED: "отклонено клиентом",
        STATUS_CONFIRMATION_EXPIRED: "подтверждение истекло",
        "delivery_expired": "срок выдачи истёк",
    }
    return labels.get(status, status)


def _progress_bar(progress: int) -> str:
    safe_progress = max(0, min(100, int(progress or 0)))
    filled = safe_progress // 10
    return "🟩" * filled + "⬜" * (10 - filled)


def _progress_heading(snapshot: JobProgressSnapshot) -> str:
    if snapshot.status == "cancelled":
        return "⛔ Задача отменена"
    if snapshot.status == "failed":
        return "⚠️ Не удалось подготовить файл"
    if snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        return "⚠️ Нужно подтвердить выдачу отчёта"
    if snapshot.status == STATUS_CUSTOMER_DECLINED:
        return "Отчёт не отправлен"
    if snapshot.status == STATUS_CONFIRMATION_EXPIRED:
        return "Подтверждение истекло"
    if snapshot.status == "delivery_expired":
        return "Срок выдачи результата истёк"
    if snapshot.status == "partial":
        return "✅ Готово частично"
    if snapshot.status in {"completed", "needs_review"}:
        return "✅ Файл готов"
    if snapshot.mode == MODE_ANALYSIS_AND_SUPPLIERS:
        return "📄🔎 Готовлю анализ и поставщиков"
    if snapshot.mode == MODE_PROCUREMENT_REPORT:
        return "📄 Анализирую документацию"
    return "🔎 Ищу поставщиков"


def _friendly_stage_text(message: str) -> str:
    raw = str(message or "").strip()
    lowered = raw.lower()
    if not raw:
        return "ожидаю обновления"
    if "задача создана" in lowered or "взята в обработку" in lowered:
        return "готовлю документы к обработке"
    if "номер извещения" in lowered or "ссылку закупки" in lowered:
        return "читаю карточку закупки"
    if "читаю документы" in lowered or "извлекаю" in lowered or "текст тз" in lowered:
        return "читаю ТЗ"
    if "анализирую тз" in lowered or "закупаемые позиции" in lowered:
        return "разбираю, что нужно найти"
    if "поисковые запросы" in lowered:
        return "подбираю варианты поиска"
    if "ищу сайты" in lowered:
        return "ищу сайты компаний"
    if "отбираю" in lowered or "ранжирует" in lowered:
        return "отбираю подходящие компании"
    if "проверяю сайты" in lowered or "проверено сайтов" in lowered:
        return "проверяю сайты и контакты"
    if "готовлю результат" in lowered or "сохраняю" in lowered or "формирую xlsx" in lowered:
        return "собираю файл с поставщиками"
    if "анализ документации готов" in lowered:
        return "анализ документации готов"
    if "анализ и поставщики готовы" in lowered:
        return "анализ и поставщики готовы"
    if lowered.startswith("готово") or lowered.endswith(" готов") or lowered.endswith(" готово"):
        return "файл готов к отправке"
    if "анализ документации" in lowered or "формирую отчёт" in lowered or "формирую отчет" in lowered:
        return "готовлю анализ документации"
    if "ошибка" in lowered:
        return "поиск остановлен"
    return raw


def _friendly_error_text(error: str) -> str:
    lowered = str(error or "").lower()
    if "supplier query generation" in lowered:
        return "не удалось подготовить поисковые запросы для поставщиков"
    if "procurement profile" in lowered:
        return "не удалось надёжно разобрать предмет закупки в ТЗ"
    if "candidate reranking" in lowered or "reranker" in lowered:
        return "не удалось надёжно отобрать подходящие сайты поставщиков"
    if "ai provider" in lowered or "timeout" in lowered or "timed out" in lowered:
        return "временно недоступен сервис анализа"
    if "текст документов" in lowered or "documents" in lowered:
        return "не удалось прочитать текст документа"
    return "возникла техническая ошибка при обработке"


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours} ч {minutes} мин"
    if minutes:
        return f"{minutes} мин {remaining_seconds} сек"
    return f"{remaining_seconds} сек"


def _job_elapsed_seconds(snapshot: JobProgressSnapshot, *, now: datetime | None = None) -> float:
    if not snapshot.created_at:
        return 0.0
    current = now or datetime.now(timezone.utc)
    created_at = snapshot.created_at
    if created_at.tzinfo is None and current.tzinfo is not None:
        created_at = created_at.replace(tzinfo=current.tzinfo)
    return max(0.0, (current - created_at).total_seconds())


def _job_eta_text(snapshot: JobProgressSnapshot, *, now: datetime | None = None) -> str:
    if snapshot.status in BOT_TERMINAL_JOB_STATUSES:
        return "завершено"
    progress = max(0, min(99, int(snapshot.progress or 0)))
    if progress < 10:
        return "появится после первых этапов"
    elapsed = _job_elapsed_seconds(snapshot, now=now)
    if elapsed < 30:
        return "рассчитываю время"
    remaining = elapsed * (100 - progress) / max(1, progress)
    return f"около {_format_duration(remaining)}"


def _format_job_progress(snapshot: JobProgressSnapshot, *, now: datetime | None = None) -> str:
    elapsed = _format_duration(_job_elapsed_seconds(snapshot, now=now))
    if snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        return "\n".join(
            [
                _progress_heading(snapshot),
                "",
                _friendly_stage_text(snapshot.message),
                f"Прошло: {elapsed}",
                "",
                "Я не отправлю файл и не спишу деньги без вашего согласия.",
            ]
        )
    if snapshot.status == STATUS_CUSTOMER_DECLINED:
        return "\n".join(
            [
                _progress_heading(snapshot),
                "",
                "Вы отказались получать неполный отчёт. Списания нет.",
                f"Прошло: {elapsed}",
            ]
        )
    if snapshot.status == STATUS_CONFIRMATION_EXPIRED:
        return "\n".join(
            [
                _progress_heading(snapshot),
                "",
                "Подтверждение не было получено в течение 24 часов. Списания нет.",
                f"Прошло: {elapsed}",
            ]
        )
    if snapshot.status == "delivery_expired":
        return "\n".join(
            [
                _progress_heading(snapshot),
                "",
                "Вы согласились получить вариант без подтверждения реестра, но файл не был выдан в течение 24 часов.",
                "За поиск поставщиков списания нет.",
                f"Прошло: {elapsed}",
            ]
        )
    if snapshot.status == "failed":
        return "\n".join(
            [
                _progress_heading(snapshot),
                "",
                "На этом запуске файл не сформировался из-за технического сбоя.",
                f"Причина: {_friendly_error_text(snapshot.error)}.",
                f"Прошло: {elapsed}",
                "",
                "Баланс не списан. Можно запустить повторно позже или передать материалы владельцу сервиса для проверки.",
            ]
        )
    if snapshot.status == "cancelled":
        reason = _friendly_stage_text(snapshot.message)
        return "\n".join(
            [
                _progress_heading(snapshot),
                "",
                f"• Статус: {reason}",
                f"• Прошло: {elapsed}",
                "",
                "Резерв возвращён. Можно запустить новую обработку.",
            ]
        )
    if snapshot.status in {"completed", "partial", "needs_review"}:
        return "\n".join(
            [
                _progress_heading(snapshot),
                "",
                f"• Результат: {_friendly_stage_text(snapshot.message)}",
                f"• Прошло: {elapsed}",
            ]
        )
    lines = [
        _progress_heading(snapshot),
        "",
        f"{_progress_bar(snapshot.progress)} {snapshot.progress}%",
        f"• Этап: {_friendly_stage_text(snapshot.message)}",
        f"• Прошло: {elapsed}",
        f"• Ориентир: {_job_eta_text(snapshot, now=now)}",
    ]
    return "\n".join(lines)


def _format_launch_progress(snapshot: JobProgressSnapshot, accepted_text: str) -> str:
    base = _format_job_progress(snapshot)
    accepted = str(accepted_text or "").strip()
    if not accepted:
        return base
    parts = base.split("\n\n", 1)
    if len(parts) == 2:
        return f"{parts[0]}\n\n{accepted}\n\n{parts[1]}"
    return f"{accepted}\n\n{base}"


def _accepted_batch_text(pending: PendingBatch) -> str:
    details = f"✅ Принято: файлов {len(pending.files)}, источников {len(pending.sources)}"
    if pending.mode in {MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS}:
        details += f"\nРежим поиска: {_supplier_policy_label(pending.supplier_search_policy)}"
    return details


def _accepted_single_tz_text(*, from_text: bool = False) -> str:
    return "✅ ТЗ принято" if not from_text else "✅ ТЗ из сообщения принято"


def _job_result_offer_charge_text(db, job: Job) -> str:
    if db is None or not getattr(job, "id", None):
        return ""
    try:
        kinds = ["supplier_search"]
        if str(getattr(job, "mode", "") or "") == MODE_ANALYSIS_AND_SUPPLIERS:
            kinds.append("procurement_report")
        rows = (
            db.query(
                BillingTransaction.kind,
                BillingTransaction.operation,
                BillingTransaction.units,
                BillingTransaction.amount_kopeks,
            )
            .filter(BillingTransaction.job_id == job.id)
            .filter(BillingTransaction.kind.in_(kinds))
            .all()
        )
    except Exception:
        return ""
    reserved_amount = sum(
        max(0, int(amount or 0)) for _kind, operation, _units, amount in rows if operation == "reserve"
    )
    settled_amount = sum(
        max(0, int(amount or 0))
        for _kind, operation, _units, amount in rows
        if operation in {"charge", "release"}
    )
    remaining_amount = max(0, reserved_amount - settled_amount)
    if remaining_amount:
        return _price_text(remaining_amount)
    unit_parts: list[str] = []
    labels = {
        "supplier_search": "поиска поставщиков",
        "procurement_report": "анализа документации",
    }
    for kind in kinds:
        reserved_units = sum(
            max(0, int(units or 0))
            for row_kind, operation, units, _amount in rows
            if row_kind == kind and operation == "reserve"
        )
        settled_units = sum(
            max(0, int(units or 0))
            for row_kind, operation, units, _amount in rows
            if row_kind == kind and operation in {"charge", "release"}
        )
        remaining_units = max(0, reserved_units - settled_units)
        if remaining_units:
            operation_word = "операция" if remaining_units == 1 else "операции"
            unit_parts.append(f"{remaining_units} {operation_word} {labels[kind]}")
    return " + ".join(unit_parts)


def _job_snapshot(job: Job, db=None) -> JobProgressSnapshot:
    confirmation_kind = str(getattr(job, "confirmation_kind", "") or "")
    offer = result_offer_to_dict(db, job) if db is not None and confirmation_kind else None
    charge_amount = max(0, int((offer or {}).get("charge_amount_kopeks") or 0))
    return JobProgressSnapshot(
        id=job.id,
        mode=job.mode,
        status=job.status,
        progress=job.progress,
        message=job.message,
        error=job.error,
        created_at=job.created_at,
        confirmation_kind=confirmation_kind,
        confirmation_outcome=str((offer or {}).get("decision_outcome") or getattr(job, "confirmation_outcome", "") or ""),
        offer_delivery_outcome=str((offer or {}).get("delivery_outcome") or getattr(job, "offer_delivery_outcome", "") or ""),
        registry_verified_count=max(
            0,
            int((offer or {}).get("registry_verified_count") or getattr(job, "registry_verified_count", 0) or 0),
        ),
        alternative_verified_count=(
            max(
                0,
                int((offer or {}).get("alternative_verified_count") or getattr(job, "alternative_verified_count", 0) or 0),
            )
            or (max(0, int(getattr(job, "verified_count", 0) or 0)) if confirmation_kind == "registry_fallback" else 0)
        ),
        offer_charge_text=(
            _price_text(charge_amount)
            if charge_amount
            else (_job_result_offer_charge_text(db, job) if confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK else "")
        ),
    )


def _load_job_snapshot(job_id: str) -> JobProgressSnapshot | None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        return _job_snapshot(job, db) if job else None
    finally:
        db.close()


def _short_owner_alert_value(value: object, limit: int = 700) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,:;") + "..."


def _owner_problem_alert_text(
    snapshot: JobProgressSnapshot,
    *,
    title: str = "",
    client_telegram_id: str = "",
    evidence_path: str = "",
    result_path: str = "",
    output_missing: bool = False,
) -> str:
    lines = [
        f"⚠️ {BRAND_NAME}: нужна проверка задачи",
        f"ID: {snapshot.id}",
        f"Режим: {_mode_label(snapshot.mode)}",
        f"Статус: {_status_label(snapshot.status)}",
    ]
    if title:
        lines.append(f"Закупка: {_short_owner_alert_value(title, 180)}")
    if client_telegram_id:
        lines.append(f"Клиент Telegram ID: {client_telegram_id}")
    if snapshot.message:
        lines.append(f"Сообщение: {_short_owner_alert_value(snapshot.message, 260)}")
    if snapshot.error:
        lines.append(f"Причина для клиента: {_friendly_error_text(snapshot.error)}")
        lines.append(f"Технически: {_short_owner_alert_value(snapshot.error)}")
    if output_missing:
        lines.append("Файл не найден или не был сформирован.")
    if result_path:
        lines.append(f"Файл: {result_path}")
    if evidence_path:
        lines.append(f"Данные проверки: {evidence_path}")
    lines.append("Что сделать: проверить настройки модели, данные проверки и последние логи обработки.")
    return "\n".join(lines)


def _job_owner_alert_context(job_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return {}
        return {
            "title": str(job.title or ""),
            "client_telegram_id": str(job.created_by_telegram_id or (job.client.telegram_id if job.client else "") or ""),
            "evidence_path": str(job.evidence_path or ""),
            "result_path": str(job.result_path or ""),
        }
    finally:
        db.close()


def _message_bot(message: Message) -> Bot | None:
    try:
        return getattr(message, "bot", None)
    except Exception:
        return None


async def _send_owner_alert(bot: Bot | None, text: str) -> None:
    owner_id = str(config.owner_telegram_id or "").strip()
    if not owner_id or bot is None:
        return
    try:
        await bot.send_message(owner_id, text[:3900])
    except Exception:
        return


async def _alert_owner_about_job(
    message: Message,
    snapshot: JobProgressSnapshot,
    *,
    reason: str,
    output_missing: bool = False,
) -> None:
    if not output_missing and snapshot.status not in OWNER_ALERT_STATUSES:
        return
    owner_id = str(config.owner_telegram_id or "").strip()
    chat_id = str(getattr(getattr(message, "chat", None), "id", "") or "").strip()
    if owner_id and chat_id == owner_id:
        return
    key = (snapshot.id, reason)
    if key in OWNER_ALERTED_KEYS:
        return
    OWNER_ALERTED_KEYS.add(key)
    await _send_owner_alert(
        _message_bot(message),
        _owner_problem_alert_text(
            snapshot,
            output_missing=output_missing,
            **_job_owner_alert_context(snapshot.id),
        ),
    )


def _cancel_job_inline_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛔ Отменить задачу", callback_data=f"cancel_job:{job_id}")],
        ]
    )


def _progress_status_keyboard(snapshot: JobProgressSnapshot) -> InlineKeyboardMarkup | None:
    if snapshot.status in {"pending", "running"}:
        return _cancel_job_inline_keyboard(snapshot.id)
    return None


async def _edit_or_send_status(
    status_message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    clear_reply_markup: bool = False,
) -> Message:
    try:
        if reply_markup is None and not clear_reply_markup:
            await status_message.edit_text(text)
        else:
            await status_message.edit_text(text, reply_markup=reply_markup)
        return status_message
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return status_message
        if reply_markup is None and not clear_reply_markup:
            replacement = await status_message.answer(text)
        else:
            replacement = await status_message.answer(text, reply_markup=reply_markup)
        try:
            await status_message.delete()
        except Exception:
            pass
        return replacement


async def watch_job_progress(
    message: Message,
    job_id: str,
    *,
    status_message: Message | None = None,
    timeout_seconds: int = 3600,
    poll_interval: float = 5.0,
) -> JobProgressSnapshot | None:
    started = asyncio.get_running_loop().time()
    snapshot = _load_job_snapshot(job_id)
    if snapshot is None:
        await message.answer(
            "⚠️ Задача не найдена\n\nСообщите владельцу сервиса.",
            reply_markup=_menu_for_chat(message.chat.id),
        )
        return None
    if status_message is None:
        status_message = await message.answer(_format_job_progress(snapshot), reply_markup=_progress_status_keyboard(snapshot))
    else:
        status_message = await _edit_or_send_status(
            status_message,
            _format_job_progress(snapshot),
            reply_markup=_progress_status_keyboard(snapshot),
        )
    last_key = (snapshot.status, snapshot.progress, snapshot.message, snapshot.error)
    last_heartbeat = started

    while snapshot.status not in BOT_TERMINAL_JOB_STATUSES:
        if asyncio.get_running_loop().time() - started >= timeout_seconds:
            await _edit_or_send_status(
                status_message,
                _format_job_progress(snapshot)
                + f"\n\nЗадача всё ещё выполняется. Я продолжу обработку на сервере, статус можно проверить кнопкой «{BUTTON_STATUS}».",
                reply_markup=_progress_status_keyboard(snapshot),
            )
            return snapshot
        await asyncio.sleep(poll_interval)
        current = _load_job_snapshot(job_id)
        if current is None:
            await _edit_or_send_status(status_message, "Задача не найдена. Сообщите владельцу сервиса.")
            return None
        snapshot = current
        if snapshot.status in BOT_TERMINAL_JOB_STATUSES:
            break
        key = (snapshot.status, snapshot.progress, snapshot.message, snapshot.error)
        now = asyncio.get_running_loop().time()
        if key != last_key or now - last_heartbeat >= 60:
            status_message = await _edit_or_send_status(
                status_message,
                _format_job_progress(snapshot),
                reply_markup=_progress_status_keyboard(snapshot),
            )
            last_key = key
            last_heartbeat = now

    if snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        await _edit_or_send_status(
            status_message,
            _partial_confirmation_text(snapshot),
            reply_markup=_partial_confirmation_keyboard(job_id, snapshot.confirmation_kind),
        )
    else:
        await _edit_or_send_status(status_message, _format_job_progress(snapshot), clear_reply_markup=True)
        if snapshot.status == "cancelled" and snapshot.id not in BOT_CANCEL_NOTIFIED_JOBS:
            BOT_CANCEL_NOTIFIED_JOBS.add(snapshot.id)
            await message.answer(
                "⛔ Задача отменена. Резерв возвращён, можно запустить новую обработку.",
                reply_markup=main_menu(),
            )
    return snapshot


def _scenario_for_message(message: Message) -> str:
    caption = str(message.caption or "").lower()
    wants_analysis = any(marker in caption for marker in ("word", "docx", "отчёт", "отчет", "анализ"))
    wants_suppliers = any(marker in caption for marker in ("поставщик", "supplier", "xlsx"))
    if wants_analysis and wants_suppliers:
        return SCENARIO_ANALYSIS_AND_SUPPLIERS
    if wants_analysis:
        return SCENARIO_REPORT
    if wants_suppliers:
        return SCENARIO_SUPPLIERS
    return PENDING_MODES.get(message.chat.id, SCENARIO_SUPPLIERS)


def _start_text() -> str:
    return (
        f"👋 Добро пожаловать в {BRAND_NAME}.\n\n"
        "Помогу найти и проверить поставщиков или разобрать закупочную документацию.\n\n"
        "Выберите, что нужно:\n"
        f"{BUTTON_SUPPLIERS}\n"
        f"{BUTTON_REPORT}\n"
        f"{BUTTON_ANALYSIS_AND_SUPPLIERS}\n\n"
        "Отправьте материалы — дальше подскажу следующий шаг.\n"
        "💳 Списание только после готового результата."
    )


def _contacts_text(settings, telegram_id: str = "") -> str:
    lines = ["📞 Контакты"]
    telegram_url = _telegram_contact_url(getattr(settings, "contact_telegram", ""))
    if telegram_url:
        lines.append(f'Telegram: <a href="{html_escape(telegram_url, quote=True)}">Написать в Telegram</a>')
    if settings.contact_email:
        lines.append(f"Email: {html_escape(settings.contact_email)}")
    if getattr(settings, "contact_website", ""):
        lines.append(f"Сайт: {html_escape(settings.contact_website)}")
    if (
        not telegram_url
        and not settings.contact_email
        and not getattr(settings, "contact_website", "")
    ):
        lines.append("Контакты для покупки пока не указаны владельцем сервиса.")
    if telegram_id:
        lines.extend(["", f"Ваш Telegram ID: {telegram_id}"])
    return "\n".join(lines)


def _telegram_contact_url(value: str) -> str:
    contact = str(value or "").strip()
    if not contact:
        return ""
    if contact.startswith(("http://", "https://", "tg://")):
        return contact
    if contact.startswith("t.me/"):
        return f"https://{contact}"
    handle = contact.lstrip("@").strip("/")
    if handle:
        return f"https://t.me/{handle}"
    return ""


def _contact_message_options() -> dict:
    return {"parse_mode": ParseMode.HTML, "disable_web_page_preview": True}


def _balance_line(counter: dict) -> str:
    if int(counter.get("price_kopeks") or 0) > 0:
        return f"{counter['label']}: {_price_text(counter['price_kopeks'])}"
    return (
        f"{counter['label']}: доступно {counter['available']}, "
        f"в обработке {counter['reserved']}, списано {counter['spent']}"
    )


def _money_balance_warning(balances: dict) -> str:
    money = balances.get("money")
    if isinstance(money, dict) and money.get("low"):
        return "⚠️ Баланс заканчивается."
    return ""


def _cabinet_text(db, client: Client, settings) -> str:
    balances = client_service_balance_summary(db, client)
    lines = [
        "📊 Мой кабинет",
        "",
        f"Статус: {'включён' if client.is_active else 'выключен'}",
        f"Тип: {'бесплатный доступ' if client_uses_trial_access(db, client) else 'клиент'}",
        "",
        f"Баланс: {_money_text(balances['money']['available_kopeks'])}",
        "",
        "Стоимость услуг:",
        _balance_line(balances["supplier_search"]),
        _balance_line(balances["procurement_report"]),
        _balance_line(balances["supplier_search_extra"]),
    ]
    warning = _money_balance_warning(balances)
    if warning:
        lines.extend(["", warning])
    lines.extend(["", f"Пополнить баланс можно в разделе «{BUTTON_TARIFFS}»."])
    if (
        _telegram_contact_url(getattr(settings, "contact_telegram", ""))
        or settings.contact_email
        or getattr(settings, "contact_website", "")
    ):
        lines.extend(["", _contacts_text(settings)])
    return "\n".join(lines)


def _price_text(price_kopeks: int) -> str:
    if int(price_kopeks or 0) <= 0:
        return "цену уточните у владельца"
    rubles = int(price_kopeks) / 100
    if rubles.is_integer():
        return f"{int(rubles):,} ₽".replace(",", " ")
    return f"{rubles:,.2f} ₽".replace(",", " ")


def _money_text(amount_kopeks: int) -> str:
    rubles = int(amount_kopeks or 0) / 100
    if rubles.is_integer():
        return f"{int(rubles):,} ₽".replace(",", " ")
    return f"{rubles:,.2f} ₽".replace(",", " ")


def _tariffs_text(db, settings) -> str:
    packages = [tariff_to_dict(item) for item in list_tariffs(db, active_only=True)]
    supplier = [item for item in packages if item["kind"] == "supplier_search"]
    reports = [item for item in packages if item["kind"] == "procurement_report"]
    extra = [item for item in packages if item["kind"] == "supplier_search_extra"]
    lines = [
        "💳 Тарифы и оплата",
        "",
        "Баланс пополняется в рублях. При запуске стоимость услуги резервируется по тарифу, после успешной выдачи результата — списывается.",
    ]
    if supplier:
        lines.extend(["", "🔎 Поставщики:"])
        for item in supplier:
            lines.append(f"• {html_escape(item['name'])} — {_price_text(item['price_kopeks'])}")
    if reports:
        lines.extend(["", "📄 Анализ документации:"])
        for item in reports:
            lines.append(f"• {html_escape(item['name'])} — {_price_text(item['price_kopeks'])}")
    if extra:
        lines.extend(["", "🔎 Добор поставщиков:"])
        for item in extra:
            lines.append(f"• {html_escape(item['name'])} — {_price_text(item['price_kopeks'])}")
    elif supplier:
        unit_price = _default_extra_supplier_price_kopeks(supplier[0])
        lines.extend(["", "🔎 Добор поставщиков:"])
        lines.append(f"• 1 добор поставщиков — {_price_text(unit_price)} (50% от цены поиска поставщиков)")
    if not supplier and not reports and not extra:
        lines.extend(["", "Тарифы пока не настроены в админ-панели."])
    lines.extend(["", _bot_payment_instructions(settings)])
    lines.extend(["", INDIVIDUAL_TERMS_NOTE])
    lines.extend(["", AI_HELP_NOTE])
    lines.extend(["", _contacts_text(settings)])
    return "\n".join(lines)


def _tariff_unit_price_kopeks(item: dict) -> int:
    units = max(1, int(item.get("units") or 1))
    return max(0, round(int(item.get("price_kopeks") or 0) / units))


def _default_extra_supplier_price_kopeks(item: dict) -> int:
    return max(0, round(_tariff_unit_price_kopeks(item) * 0.5))


def _bot_payment_instructions(settings) -> str:
    instructions = str(settings.payment_instructions or "").strip()
    lowered = instructions.casefold()
    if "max" in lowered or "макс" in lowered:
        instructions = ""
    return html_escape(instructions or BOT_PAYMENT_INSTRUCTIONS)


def _partial_confirmation_text(snapshot: JobProgressSnapshot) -> str:
    if snapshot.confirmation_kind == "registry_fallback":
        return _registry_fallback_confirmation_text(snapshot)
    return (
        "⚠️ Найдено меньше поставщиков, чем обычно удаётся подготовить по отчёту.\n\n"
        "Я проверил сайты и контакты. В файл попали только подтверждённые компании.\n\n"
        f"Результат: {_friendly_stage_text(snapshot.message)}.\n\n"
        "Могу отправить отчёт, но после успешной отправки будет списана стоимость результата.\n\n"
        "Отправить отчёт?"
    )


def _registry_fallback_confirmation_text(snapshot: JobProgressSnapshot) -> str:
    alternative_count = max(0, int(snapshot.alternative_verified_count or 0))
    charge_line = (
        f"К списанию после успешной отправки: {snapshot.offer_charge_text}."
        if snapshot.offer_charge_text
        else "После успешной отправки будет списана стоимость поиска поставщиков."
    )
    return (
        "⚠️ По реестру Минпромторга подходящие поставщики не подтверждены.\n\n"
        f"• Подтверждено по реестру: {max(0, int(snapshot.registry_verified_count or 0))}\n"
        f"• Найдено и проверено вне реестра: {alternative_count}\n\n"
        "Могу отправить отчёт с этими поставщиками и заметной отметкой, что их соответствие реестру не подтверждено.\n\n"
        f"{charge_line}\n"
        "При отказе списания за поиск поставщиков не будет.\n\n"
        "Получить отчёт без подтверждения реестра?"
    )


def _partial_confirmation_keyboard(job_id: str, confirmation_kind: str = "") -> InlineKeyboardMarkup:
    if confirmation_kind == "registry_fallback":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Получить без реестра и списать",
                        callback_data=f"result_offer_yes:{job_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отказаться без списания",
                        callback_data=f"result_offer_no:{job_id}",
                    ),
                ],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, отправить и списать", callback_data=f"partial_yes:{job_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Нет, не списывать", callback_data=f"partial_no:{job_id}"),
            ],
        ]
    )


def _find_more_suppliers_offer_text() -> str:
    return (
        "Можно добрать ещё поставщиков по этому ТЗ. "
        "Нажмите «Найти ещё», если нужен дополнительный поиск."
    )


def _find_more_suppliers_offer_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔎 Найти ещё", callback_data=f"find_more_prompt:{job_id}"),
            ]
        ]
    )


def _find_more_suppliers_confirmation_text() -> str:
    return (
        "Найти ещё поставщиков по этому ТЗ?\n\n"
        "Будет списана стоимость добора поставщиков. "
        "Новый поиск исключит уже найденные компании."
    )


def _find_more_suppliers_confirmation_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, запустить добор", callback_data=f"find_more_yes:{job_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"find_more_no:{job_id}"),
            ],
        ]
    )


def _callback_user_fields(callback: CallbackQuery) -> tuple[str, str, str]:
    user = callback.from_user
    telegram_id = str(user.id if user else "")
    username = str(getattr(user, "username", "") or "")
    name = " ".join(
        item
        for item in [
            str(getattr(user, "first_name", "") or "").strip(),
            str(getattr(user, "last_name", "") or "").strip(),
        ]
        if item
    )
    return telegram_id, username, name


def _legal_keyboard(_accepted: set[str] | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Оферта", url=TERMS_URL),
                InlineKeyboardButton(text="Политика", url=PRIVACY_URL),
            ],
            [InlineKeyboardButton(text="Согласие на обработку ПД", url=PERSONAL_DATA_URL)],
        ]
    )


def _legal_text(_accepted: set[str] | None = None) -> str:
    return (
        "⚖️ Документы TenderLex\n\n"
        "Оферта, политика обработки персональных данных и отдельное согласие доступны по кнопкам ниже.\n\n"
        f"Все документы и реквизиты: {LEGAL_INDEX_URL}"
    )


def _record_telegram_terms_acceptance(db, telegram_id: str) -> None:
    record_legal_acceptance(
        db,
        subject_type="telegram",
        subject_id=telegram_id,
        document_type=LEGAL_DOCUMENT_TERMS,
        document_version=LEGAL_VERSION,
        source="telegram_job_launch",
        user_agent="Telegram Bot API",
    )


@router.message(Command("start"))
async def start(message: Message, command: CommandObject | None = None) -> None:
    telegram_id, username, name = _telegram_user_fields(message)
    access_note = ""
    first_use = False
    db = SessionLocal()
    try:
        link_token = ""
        command_args = str(getattr(command, "args", "") or "").strip()
        if command_args.startswith("link_"):
            link_token = command_args.removeprefix("link_")
        if link_token:
            try:
                link_result = consume_web_to_telegram_token(
                    db,
                    link_token,
                    telegram_id=telegram_id,
                    username=username,
                    name=name,
                )
                client = db.get(Client, link_result.client_id)
                account_error = ""
                access_note = "\n\n✅ Telegram безопасно привязан к вашему кабинету. Баланс и история сохранены."
                record_journey_event(db, client.id if client else None, channel="telegram", event_name="link_succeeded", outcome="linked")
            except AccountLinkError as exc:
                await message.answer(f"⚠️ {exc}", reply_markup=main_menu())
                return
        else:
            client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        if account_error:
            access_note = f"\n\n⚠️ {account_error}"
        elif client and not access_note:
            access_note = "\n\n✅ Telegram-аккаунт подключён. Можно работать через кнопки меню."
        if client:
            first_use = not bool(db.query(Job.id).filter(Job.client_id == client.id).first())
            record_journey_event(db, client.id, channel="telegram", event_name="bot_started")
    finally:
        db.close()
    menu = create_menu() if first_use and not _chat_has_processing_job(message.chat.id) else _menu_for_chat(message.chat.id)
    await message.answer(_start_text() + access_note, reply_markup=menu)


@router.message(Command("legal"))
@router.message(F.text == BUTTON_LEGAL)
async def legal_info(message: Message) -> None:
    await message.answer(_legal_text(), reply_markup=_legal_keyboard())


@router.callback_query(F.data.startswith("legal_accept:"))
async def legal_acceptance_callback(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    document_type = str(callback.data or "").split(":", 1)[1]
    if document_type not in {LEGAL_DOCUMENT_TERMS, LEGAL_DOCUMENT_PERSONAL_DATA}:
        await callback.answer("Неизвестный документ.", show_alert=True)
        return
    await callback.answer("Порядок обновлён. Актуальные документы доступны по ссылкам.")
    try:
        await callback.message.edit_text(_legal_text(), reply_markup=_legal_keyboard())
    except TelegramBadRequest:
        pass


@router.message(Command("id"))
async def show_id(message: Message) -> None:
    telegram_id = str(message.from_user.id if message.from_user else "")
    await message.answer(
        f"🆔 Ваш Telegram ID: {telegram_id}\n\n"
        "Если доступ ещё не подключён, отправьте этот ID владельцу сервиса.",
        reply_markup=_menu_for_chat(message.chat.id),
    )


@router.message(Command("status"))
async def show_status(message: Message) -> None:
    telegram_id, username, name = _telegram_user_fields(message)
    partial_confirmations: list[tuple[str, JobProgressSnapshot]] = []
    recoverable_result_offers: list[tuple[str, JobProgressSnapshot]] = []
    recoverable_outputs: list[tuple[str, JobProgressSnapshot]] = []
    db = SessionLocal()
    try:
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        if account_error:
            await message.answer(account_error, reply_markup=_menu_for_chat(message.chat.id))
            return
        if not client:
            await message.answer(
                "⚠️ Доступ не подключён\n\n"
                "Нажмите «Контакты»: там будет ваш Telegram ID для подключения доступа.",
                reply_markup=_menu_for_chat(message.chat.id),
            )
            return
        jobs = (
            db.query(Job)
            .filter(Job.client_id == client.id)
            .order_by(Job.created_at.desc())
            .limit(5)
            .all()
        )
        if not jobs:
            await message.answer(
                "🕘 Задач пока нет\n\n"
                "Выберите режим и отправьте материалы закупки.",
                reply_markup=_menu_for_chat(message.chat.id),
            )
            return
        lines = ["🕘 Последние задачи"]
        for index, job in enumerate(jobs, start=1):
            snapshot = _job_snapshot(job, db)
            lines.append(
                f"{index}. {_progress_heading(snapshot)} — {_status_label(snapshot.status)}, {snapshot.progress}%\n"
                f"   {_friendly_stage_text(snapshot.message)}"
            )
        await message.answer("\n".join(lines), reply_markup=_menu_for_chat(message.chat.id))
        for job in jobs:
            snapshot = _job_snapshot(job, db)
            job_id = str(job.id)
            if (
                snapshot.confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK
                and snapshot.confirmation_outcome == "accepted"
                and snapshot.offer_delivery_outcome == "pending"
            ):
                recoverable_result_offers.append((job_id, snapshot))
            elif (
                snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION
                and snapshot.confirmation_outcome not in {"accepted", "declined", "expired"}
            ):
                partial_confirmations.append((job_id, snapshot))
            elif snapshot.status in {"completed", "partial", "needs_review"} and job_has_unsettled_reservation(db, job):
                recoverable_outputs.append((job_id, snapshot))
    finally:
        db.close()
    for job_id, snapshot in partial_confirmations:
        await _send_partial_confirmation(message, job_id, snapshot)
    for job_id, _snapshot in recoverable_result_offers:
        await message.answer("✅ Вы уже согласились получить вариант без подтверждения реестра. Повторяю выдачу файла.")
        try:
            await _send_result_offer_outputs(message, job_id, accept_if_pending=False)
        except (ResultOfferConflict, ResultOfferGone) as exc:
            await message.answer(str(exc), reply_markup=_menu_for_chat(message.chat.id))
        except Exception:
            logger.exception("Could not recover registry fallback delivery for job %s", job_id)
            await message.answer("Не удалось отправить все файлы. Списания нет; попробуйте ещё раз через «Задачи».", reply_markup=_menu_for_chat(message.chat.id))
    for job_id, snapshot in recoverable_outputs:
        await message.answer("✅ Нашёл готовый результат, который ещё не был отправлен. Отправляю файл сейчас.")
        await _send_job_outputs(message, job_id, snapshot)


@router.message(Command("suppliers"))
async def supplier_mode(message: Message) -> None:
    if await _reject_if_chat_processing(message):
        return
    cleared = _select_scenario(message.chat.id, SCENARIO_SUPPLIERS)
    _record_telegram_event(message, "mode_selected", mode=MODE_SUPPLIER_SEARCH)
    await message.answer(_supplier_policy_prompt_text(SCENARIO_SUPPLIERS), reply_markup=supplier_policy_keyboard())
    await message.answer(_supplier_multi_intro_text() + _scenario_switch_note(cleared), reply_markup=batch_menu())


@router.message(Command("report"))
async def report_mode(message: Message) -> None:
    if await _reject_if_chat_processing(message):
        return
    cleared = _select_scenario(message.chat.id, SCENARIO_REPORT)
    _record_telegram_event(message, "mode_selected", mode=MODE_PROCUREMENT_REPORT)
    await message.answer(
        "📄 Анализ закупки\n\n"
        "Отправьте номер извещения, ссылку, архив или документы закупки.\n"
        f"Когда материалы добавлены, нажмите «{BUTTON_RUN_BATCH}»." + _scenario_switch_note(cleared),
        reply_markup=batch_menu(),
    )


@router.message(F.text == BUTTON_SUPPLIERS)
async def supplier_single_button(message: Message) -> None:
    await supplier_mode(message)


@router.message(F.text == BUTTON_CREATE)
async def create_button(message: Message) -> None:
    if await _reject_if_chat_processing(message):
        return
    _record_telegram_event(message, "create_opened")
    await message.answer(
        "🚀 Создать\n\n"
        "Выберите сценарий:\n"
        "🔎 Поставщики по ТЗ — файл, текст или архив с одним ТЗ.\n"
        "📄 Анализ закупки — номер, ссылка или документы закупки.\n"
        "📄🔎 Анализ + поиск — анализ закупки и поставщики по найденному ТЗ.",
        reply_markup=create_menu(),
    )


@router.message(F.text == BUTTON_BACK_MAIN)
async def back_main_button(message: Message) -> None:
    if await _reject_if_chat_processing(message):
        return
    _clear_pending_state(message.chat.id)
    await message.answer("🏠 Меню", reply_markup=main_menu())


@router.message(F.text == BUTTON_REPORT)
async def report_button(message: Message) -> None:
    await report_mode(message)


@router.message(F.text == BUTTON_ANALYSIS_AND_SUPPLIERS)
async def analysis_and_suppliers_button(message: Message) -> None:
    if await _reject_if_chat_processing(message):
        return
    cleared = _select_scenario(message.chat.id, SCENARIO_ANALYSIS_AND_SUPPLIERS)
    _record_telegram_event(message, "mode_selected", mode=MODE_ANALYSIS_AND_SUPPLIERS)
    await message.answer(_supplier_policy_prompt_text(SCENARIO_ANALYSIS_AND_SUPPLIERS), reply_markup=supplier_policy_keyboard())
    await message.answer(
        "📄🔎 Анализ + поиск\n\n"
        "Отправьте номер извещения, ссылку, архив или документы закупки.\n"
        "Результат: анализ закупки и отдельный список поставщиков по найденному ТЗ." + _scenario_switch_note(cleared),
        reply_markup=batch_menu(),
    )


@router.callback_query(F.data.startswith("supplier_policy:"))
async def supplier_policy_callback(callback: CallbackQuery) -> None:
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    policy = str(callback.data or "").split(":", 1)[1]
    if policy not in {SUPPLIER_POLICY_NORMAL, SUPPLIER_POLICY_MINPROM_ONLY, SUPPLIER_POLICY_MINPROM_PRIORITY}:
        await callback.answer("Неизвестный режим.", show_alert=True)
        return
    chat_id = int(callback.message.chat.id)
    scenario = PENDING_MODES.get(chat_id, SCENARIO_SUPPLIERS)
    if not _scenario_uses_supplier_policy(scenario):
        await callback.answer("Для этого сценария режим не нужен.", show_alert=True)
        return
    PENDING_SUPPLIER_POLICIES[chat_id] = policy
    pending = PENDING_UPLOADS.get(chat_id)
    if pending:
        pending.supplier_search_policy = policy
    await callback.answer("Режим выбран.")
    await callback.message.answer(f"Режим поиска: {_supplier_policy_label(policy)}.", reply_markup=batch_menu())


@router.message(F.text == BUTTON_STATUS)
async def status_button(message: Message) -> None:
    await show_status(message)


@router.message(F.text == BUTTON_PROCESSING_STATUS)
async def processing_status_button(message: Message) -> None:
    if _chat_has_processing_job(message.chat.id):
        await message.answer(_batch_running_text(), reply_markup=processing_menu())
        return
    await message.answer("✅ Активной обработки сейчас нет", reply_markup=main_menu())


@router.message(Command("cancel"))
@router.message(F.text == BUTTON_CANCEL_PROCESSING)
async def cancel_processing_button(message: Message) -> None:
    cancelled_count = _cancel_processing_jobs_for_chat(message.chat.id)
    BATCH_RUNNING_CHATS.discard(message.chat.id)
    had_pending_state = _clear_pending_state(message.chat.id)
    if cancelled_count:
        text = "⛔ Задача отменена. Резерв возвращён." if cancelled_count == 1 else f"⛔ Отменено задач: {cancelled_count}. Резервы возвращены."
        await message.answer(f"{text}\n\nМожно запустить новую обработку.", reply_markup=main_menu())
        return
    if had_pending_state:
        await message.answer("🗑 Материалы очищены. Активной обработки не было.", reply_markup=main_menu())
        return
    await message.answer("✅ Активной обработки сейчас нет", reply_markup=main_menu())


@router.callback_query(F.data.startswith("cancel_job:"))
async def cancel_job_callback(callback: CallbackQuery) -> None:
    job_id = str(callback.data or "").split(":", 1)[1]
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    if not _callback_job_allowed(callback, job_id):
        await callback.answer("Эта задача относится к другому доступу.", show_alert=True)
        return

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            await callback.answer("Задача не найдена.", show_alert=True)
            return
        if job.status not in {"pending", "running"}:
            await callback.answer("Эту задачу уже нельзя отменить.", show_alert=True)
            await _edit_or_send_status(callback.message, _format_job_progress(_job_snapshot(job)), clear_reply_markup=True)
            return
        _cancel_processing_job(
            db,
            job,
            note="Резерв возвращён: задача отменена в Telegram",
            message="Задача отменена в Telegram",
        )
        snapshot = _job_snapshot(job)
    finally:
        db.close()

    BATCH_RUNNING_CHATS.discard(callback.message.chat.id)
    await callback.answer("Задача отменена.")
    await _edit_or_send_status(callback.message, _format_job_progress(snapshot), clear_reply_markup=True)
    await callback.message.answer(
        "⛔ Задача отменена. Резерв возвращён, можно запустить новую обработку.",
        reply_markup=main_menu(),
    )


@router.message(F.text == BUTTON_CANCEL_BATCH)
async def cancel_batch_button(message: Message) -> None:
    if await _reject_if_chat_processing(message):
        return
    _clear_pending_state(message.chat.id)
    await message.answer("🗑 Материалы очищены", reply_markup=main_menu())


@router.message(F.text == BUTTON_RUN_BATCH)
async def run_batch_button(message: Message) -> None:
    if message.chat.id in BATCH_RUNNING_CHATS:
        await message.answer(_batch_running_text(), reply_markup=processing_menu())
        return
    pending = PENDING_UPLOADS.get(message.chat.id)
    if not pending or _pending_input_count(pending) == 0:
        scenario = PENDING_MODES.get(message.chat.id, SCENARIO_SUPPLIERS)
        if _scenario_accepts_source_links(scenario):
            text = (
                "📎 Материалы не добавлены\n\n"
                "Отправьте файлы закупки, архив, номер извещения или ссылку на закупку."
            )
        else:
            text = (
                "📎 ТЗ не добавлено\n\n"
                "Отправьте файл ТЗ/ООЗ, архив с несколькими файлами или текстовое описание объекта закупки."
            )
        await message.answer(text, reply_markup=batch_menu())
        return
    _record_telegram_event(message, "launch_attempted", mode=pending.mode)
    BATCH_RUNNING_CHATS.add(message.chat.id)
    job: Job | None = None
    job_id: str | None = None
    batch_jobs: list[tuple[str, str]] = []
    created_batch_entities: list[Job] = []
    launch_started = False
    launch_message: Message | None = None
    db = SessionLocal()
    try:
        client, account_error = get_or_create_trial_client_by_telegram_id(db, pending.telegram_id)
        supplier_job_specs = _supplier_multi_job_specs(pending)
        supplier_search_count = len(supplier_job_specs) if supplier_job_specs else 1
        error = account_error or client_access_error(
            db,
            client,
            pending.mode,
            incoming_file_count=len(pending.files),
            supplier_search_count=supplier_search_count,
        )
        if error:
            if client:
                record_journey_event(db, client.id, channel="telegram", event_name="launch_blocked", mode=pending.mode, reason_code="access")
            BATCH_RUNNING_CHATS.discard(message.chat.id)
            await message.answer(error, reply_markup=batch_menu())
            return
        assert client is not None
        settings = get_or_create_settings(db)
        target_suppliers = supplier_target_for_client(settings, client)
        if supplier_job_specs:
            for title, files in supplier_job_specs:
                created = create_job(
                    db,
                    client_id=client.id,
                    created_by_telegram_id=pending.telegram_id,
                    mode=MODE_SUPPLIER_SEARCH,
                    title=title,
                    target_suppliers=target_suppliers,
                    files=files,
                    sources=[],
                    supplier_search_policy=pending.supplier_search_policy,
                    initial_status="draft",
                )
                created_batch_entities.append(created)
                reserve_error = _reserve_created_job(db, client, created)
                if reserve_error:
                    BATCH_RUNNING_CHATS.discard(message.chat.id)
                    await message.answer(reserve_error, reply_markup=main_menu())
                    return
                batch_jobs.append((str(created.id), files[0][0]))
            _record_telegram_terms_acceptance(db, pending.telegram_id)
            for created in created_batch_entities:
                created.status = "pending"
                created.message = "Задача создана"
            db.commit()
        else:
            title = Path(pending.files[0][0]).stem[:120] if pending.files else source_label(pending.sources[0]["value"])[:120]
            job = create_job(
                db,
                client_id=client.id,
                created_by_telegram_id=pending.telegram_id,
                mode=pending.mode,
                title=title,
                target_suppliers=target_suppliers,
                files=pending.files,
                sources=pending.sources,
                supplier_search_policy=pending.supplier_search_policy,
                initial_status="draft",
            )
            reserve_error = _reserve_created_job(db, client, job)
            if reserve_error:
                _discard_unlaunched_jobs(db, [job])
                BATCH_RUNNING_CHATS.discard(message.chat.id)
                await message.answer(reserve_error, reply_markup=main_menu())
                return
            _record_telegram_terms_acceptance(db, pending.telegram_id)
            job.status = "pending"
            job.message = "Задача создана"
            db.commit()
            job_id = str(job.id)
        record_journey_event(
            db,
            client.id,
            channel="telegram",
            event_name="job_created",
            mode=pending.mode,
            outcome="batch" if batch_jobs else "created",
        )
        _clear_pending_state(message.chat.id)
        launch_started = True
        if batch_jobs:
            launch_message = await message.answer(
                f"🗂 Обработка запущена\n\n"
                f"✅ Принято ТЗ: {len(batch_jobs)}\n"
                "Буду обновлять это сообщение и пришлю файлы по мере готовности.",
                reply_markup=processing_menu(),
            )
        else:
            launch_message = await message.answer(
                _format_launch_progress(_job_snapshot(job), _accepted_batch_text(pending)),
                reply_markup=processing_menu(),
            )
    finally:
        if not launch_started and created_batch_entities:
            _discard_unlaunched_jobs(db, created_batch_entities)
        db.close()
        if not launch_started:
            BATCH_RUNNING_CHATS.discard(message.chat.id)

    try:
        if batch_jobs:
            await _watch_supplier_multi_outputs(message, batch_jobs, status_message=launch_message)
            return
        if job_id is not None:
            snapshot = await watch_job_progress(message, job_id, status_message=launch_message)
            if not (snapshot and snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION):
                await _send_job_outputs(message, job_id, snapshot)
    finally:
        BATCH_RUNNING_CHATS.discard(message.chat.id)


async def _watch_supplier_multi_outputs(
    message: Message,
    jobs: list[tuple[str, str]],
    *,
    status_message: Message | None = None,
) -> None:
    total = len(jobs)
    for index, (job_id, filename) in enumerate(jobs, start=1):
        title = Path(filename).stem[:80]
        if status_message is not None:
            status_message = await _edit_or_send_status(status_message, f"Обрабатываю ТЗ {index}/{total}: {title}")
        else:
            status_message = await message.answer(f"Обрабатываю ТЗ {index}/{total}: {title}")
        snapshot = await watch_job_progress(message, job_id, status_message=status_message)
        if snapshot and snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
            status_message = None
        elif snapshot and snapshot.status == "cancelled":
            status_message = None
            break
        else:
            delivered = await _send_job_outputs(
                message,
                job_id,
                snapshot,
                reply_markup=main_menu() if index == total else processing_menu(),
            )
            if not delivered and snapshot and snapshot.status in BOT_TERMINAL_JOB_STATUSES:
                status_message = None
    if status_message is not None:
        final_text = "Обработка ТЗ завершена. Файл отправлен ниже." if total == 1 else "Обработка ТЗ завершена. Файлы отправлены ниже."
        await _edit_or_send_status(status_message, final_text)


async def _send_job_outputs(
    message: Message,
    job_id: str,
    snapshot: JobProgressSnapshot | None = None,
    *,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
) -> bool:
    lookup_db = SessionLocal()
    try:
        lookup_job = lookup_db.get(Job, job_id)
        use_result_offer_delivery = bool(
            lookup_job
            and str(getattr(lookup_job, "confirmation_kind", "") or "")
            and str(getattr(lookup_job, "confirmation_outcome", "") or "") == "accepted"
            and str(getattr(lookup_job, "offer_delivery_outcome", "") or "") == "pending"
        )
    finally:
        lookup_db.close()
    if use_result_offer_delivery:
        return await _send_result_offer_outputs(
            message,
            job_id,
            accept_if_pending=False,
            reply_markup=reply_markup,
        )
    lock = JOB_DELIVERY_LOCKS.setdefault(str(job_id), asyncio.Lock())
    async with lock:
        if str(job_id) in DELIVERED_JOB_IDS:
            return True
        return await _send_job_outputs_locked(
            message,
            job_id,
            snapshot,
            reply_markup=reply_markup,
        )


async def _send_result_offer_outputs(
    message: Message,
    job_id: str,
    *,
    accept_if_pending: bool,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
) -> bool:
    """Accept/claim/send/settle a typed result offer without a second charge or send."""
    lock = JOB_DELIVERY_LOCKS.setdefault(str(job_id), asyncio.Lock())
    async with lock:
        if str(job_id) in DELIVERED_JOB_IDS:
            return False
        final_reply_markup = reply_markup or main_menu()
        db = SessionLocal()
        token = ""
        job: Job | None = None
        try:
            job = db.get(Job, job_id)
            if not job or not str(getattr(job, "confirmation_kind", "") or ""):
                raise ResultOfferGone("Предложение результата не найдено.")
            decision = str(getattr(job, "confirmation_outcome", "") or "")
            if decision == "pending" and accept_if_pending:
                job = accept_job_result_offer(db, job, channel="telegram")
                decision = str(job.confirmation_outcome or "")
            if decision != "accepted":
                raise ResultOfferConflict("Подтверждение уже не актуально.")
            token = claim_job_result_offer_delivery(db, job, channel="telegram")
            if not token:
                DELIVERED_JOB_IDS.add(str(job_id))
                return False
            selected_offer_items = active_result_offer_output_items(job)
            output_items = selected_offer_items if selected_offer_items is not None else package_job_output_items(job)
            if not output_items:
                raise ResultOfferGone("Файл результата не сформирован.")
            prepared_items: list[tuple[dict, Path]] = []
            for item in output_items:
                output = Path(str(item.get("path") or ""))
                if not output.is_file():
                    raise ResultOfferGone("Файл результата не сформирован.")
                prepared_items.append((item, output))

            sent_output_message: Message | None = None
            sent_output_base_caption = ""
            for index, (item, output) in enumerate(prepared_items):
                is_last = index == len(prepared_items) - 1
                sent_output_base_caption = _output_caption_for_item(job.mode, str(item.get("kind") or ""), output)
                sent_output_message = await message.answer_document(
                    FSInputFile(output),
                    caption=sent_output_base_caption,
                    reply_markup=final_reply_markup if is_last else None,
                )

            completed = complete_job_result_offer_delivery(
                db,
                job,
                token,
                billing_kinds=billing_kinds_for_result_delivery(job),
                channel="telegram",
                note=(
                    "Вариант без подтверждения реестра отправлен клиенту в Telegram"
                    if str(getattr(job, "confirmation_kind", "") or "") == CONFIRMATION_KIND_REGISTRY_FALLBACK
                    else "Неполный отчёт отправлен клиенту в Telegram"
                ),
            )
            token = ""
            if not completed:
                DELIVERED_JOB_IDS.add(str(job_id))
                return False
            DELIVERED_JOB_IDS.add(str(job_id))
            if job.client and sent_output_message is not None:
                await _edit_output_delivery_caption(
                    sent_output_message,
                    sent_output_base_caption,
                    _after_delivery_balance_text(db, job.client),
                    reply_markup=final_reply_markup,
                )
            if job_can_find_more_suppliers(job):
                await _send_find_more_suppliers_offer(message, job.id)
            return True
        except Exception:
            if token and job is not None:
                try:
                    fail_job_result_offer_delivery(db, job, token)
                except Exception:
                    logger.exception("Could not release result-offer delivery claim for job %s", job_id)
            raise
        finally:
            db.close()


async def _send_job_outputs_locked(
    message: Message,
    job_id: str,
    snapshot: JobProgressSnapshot | None = None,
    *,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
) -> bool:
    final_reply_markup = reply_markup or main_menu()
    db = SessionLocal()
    try:
        done_job = db.get(Job, job_id)
        if not done_job:
            await message.answer(
                "⚠️ Задача не найдена\n\nСообщите владельцу сервиса.",
                reply_markup=final_reply_markup,
            )
            return False
        done_status = str(getattr(done_job, "status", "") or "")
        confirmation_kind = str(getattr(done_job, "confirmation_kind", "") or "")
        confirmation_outcome = str(getattr(done_job, "confirmation_outcome", "") or "")
        delivery_outcome = str(getattr(done_job, "offer_delivery_outcome", "") or "")
        analysis_only = (
            str(getattr(done_job, "mode", "") or "") == MODE_ANALYSIS_AND_SUPPLIERS
            and str(getattr(done_job, "active_output_manifest", "") or "") == "analysis_only"
        )
        if done_status in {"cancelled", "delivery_expired", STATUS_CUSTOMER_DECLINED, STATUS_CONFIRMATION_EXPIRED}:
            return False
        if snapshot and snapshot.status in {"cancelled", "delivery_expired", STATUS_CUSTOMER_DECLINED, STATUS_CONFIRMATION_EXPIRED}:
            return False
        if confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK and not analysis_only:
            if delivery_outcome == "delivered":
                return True
            if delivery_outcome == "expired" or confirmation_outcome != "accepted":
                return False
        output_items = package_job_output_items(done_job) if (
            getattr(done_job, "evidence_path", None) or getattr(done_job, "result_path", None)
        ) else []
        if not output_items:
            output_items = [{"kind": "", "path": str(path)} for path in package_job_output_files(done_job)]
        if output_items:
            sent_output_message: Message | None = None
            sent_output_base_caption = ""
            for index, item in enumerate(output_items):
                output = Path(str(item.get("path") or ""))
                is_last = index == len(output_items) - 1
                sent_output_base_caption = _output_caption_for_item(done_job.mode, str(item.get("kind") or ""), output)
                sent_output_message = await message.answer_document(
                    FSInputFile(output),
                    caption=sent_output_base_caption,
                    reply_markup=final_reply_markup if is_last else None,
                )
            charge_job_reservation(db, done_job)
            DELIVERED_JOB_IDS.add(str(job_id))
            if snapshot and snapshot.status in OWNER_ALERT_STATUSES:
                await _alert_owner_about_job(message, snapshot, reason=f"problem_status:{snapshot.status}")
            if done_job.client and sent_output_message is not None:
                await _edit_output_delivery_caption(
                    sent_output_message,
                    sent_output_base_caption,
                    _after_delivery_balance_text(db, done_job.client),
                    reply_markup=final_reply_markup,
                )
            if job_can_find_more_suppliers(done_job):
                await _send_find_more_suppliers_offer(message, done_job.id)
            return True
        if snapshot and snapshot.status not in BOT_TERMINAL_JOB_STATUSES:
            await message.answer(
                f"⏳ Обработка продолжается\n\nСтатус можно проверить кнопкой «{BUTTON_STATUS}».",
                reply_markup=processing_menu(),
            )
        elif snapshot:
            await _alert_owner_about_job(message, snapshot, reason="missing_output", output_missing=True)
        return False
    finally:
        db.close()


def _after_delivery_balance_text(db, client: Client) -> str:
    balances = client_service_balance_summary(db, client)
    lines = ["✅ Результат отправлен. Баланс обновлён."]
    warning = _money_balance_warning(balances)
    if warning:
        lines.append(warning)
    lines.extend(["", AI_CUSTOMER_NOTE])
    return "\n".join(lines)


def _join_caption(*parts: str) -> str:
    text = "\n\n".join(str(part or "").strip() for part in parts if str(part or "").strip())
    if len(text) <= TELEGRAM_CAPTION_LIMIT:
        return text
    return text[: TELEGRAM_CAPTION_LIMIT - 1].rstrip() + "…"


async def _edit_output_delivery_caption(
    sent_message: Message,
    base_caption: str,
    delivery_text: str,
    *,
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
) -> None:
    try:
        await sent_message.edit_caption(
            caption=_join_caption(base_caption, delivery_text),
            reply_markup=reply_markup or main_menu(),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
    except Exception:
        return


async def _send_partial_confirmation(message: Message, job_id: str, snapshot: JobProgressSnapshot) -> None:
    await message.answer(
        _partial_confirmation_text(snapshot),
        reply_markup=_partial_confirmation_keyboard(job_id, snapshot.confirmation_kind),
    )


async def _send_find_more_suppliers_offer(message: Message, job_id: str) -> None:
    await message.answer(
        _find_more_suppliers_offer_text(),
        reply_markup=_find_more_suppliers_offer_keyboard(job_id),
    )


def _output_caption_for_item(mode: str, kind: str, output: Path) -> str:
    if kind == "quote_request":
        return "Запрос КП во вложении."
    if kind == "analysis":
        return "Анализ документации во вложении."
    if kind == "suppliers":
        return "Поставщики по ТЗ во вложении."
    return _output_caption(mode, output)


def _output_caption(mode: str, output: Path) -> str:
    suffix = output.suffix.lower()
    if mode == MODE_ANALYSIS_AND_SUPPLIERS and suffix == ".docx":
        return "Анализ документации во вложении."
    if mode == MODE_ANALYSIS_AND_SUPPLIERS and suffix == ".xlsx":
        return "Поставщики по ТЗ во вложении."
    if mode == MODE_PROCUREMENT_REPORT:
        return "Анализ документации во вложении."
    return "Поставщики по ТЗ во вложении."


@router.message(F.text == BUTTON_ACCESS)
async def access_button(message: Message) -> None:
    telegram_id, username, name = _telegram_user_fields(message)
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        if account_error:
            await message.answer(account_error, reply_markup=_menu_for_chat(message.chat.id))
            return
        if not client:
            await message.answer(
                "⚠️ Доступ не подключён\n\n"
                f"Ваш Telegram ID: {telegram_id}\n"
                "Отправьте этот ID владельцу сервиса, чтобы он включил доступ.\n\n"
                + _contacts_text(settings),
                reply_markup=_menu_for_chat(message.chat.id),
                **_contact_message_options(),
            )
            return
        cabinet_text = _cabinet_text(db, client, settings)
        if client.web_users:
            web_url = f"{str(settings.public_base_url or 'https://tenderlex.ru').rstrip('/')}/cabinet"
            cabinet_text += f'\n\n🌐 <a href="{html_escape(web_url, quote=True)}">Открыть веб-кабинет</a>'
        else:
            raw_token, _record = create_account_link_token(
                db,
                client=client,
                direction=TELEGRAM_TO_WEB,
                telegram_id=telegram_id,
            )
            web_url = cabinet_link(settings.public_base_url, raw_token)
            record_journey_event(db, client.id, channel="telegram", event_name="link_requested")
            cabinet_text += (
                f'\n\n🌐 <a href="{html_escape(web_url, quote=True)}">Создать связанный веб-кабинет</a>\n'
                "Ссылка одноразовая и действует 15 минут. Новый отдельный баланс не создаётся."
            )
        await message.answer(cabinet_text, reply_markup=_menu_for_chat(message.chat.id), **_contact_message_options())
    finally:
        db.close()


@router.message(F.text == BUTTON_TARIFFS)
async def tariffs_button(message: Message) -> None:
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        await message.answer(
            _tariffs_text(db, settings) + f"\n\nОплата и запуск услуги регулируются офертой: {TERMS_URL}",
            reply_markup=_menu_for_chat(message.chat.id),
            **_contact_message_options(),
        )
    finally:
        db.close()


@router.message(F.text == BUTTON_CONTACTS)
async def contacts_button(message: Message) -> None:
    telegram_id = str(message.from_user.id if message.from_user else "")
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        await message.answer(_contacts_text(settings, telegram_id=telegram_id), reply_markup=_menu_for_chat(message.chat.id), **_contact_message_options())
    finally:
        db.close()


@router.message(F.text == BUTTON_HELP)
async def help_button(message: Message) -> None:
    await message.answer(
        "❓ Помощь\n\n"
        f"1. Нажмите «{BUTTON_CREATE}».\n"
        "2. Выберите нужный режим.\n"
        "3. Отправьте ТЗ, документы, номер извещения или ссылку — в зависимости от режима.\n\n"
        "Режимы:\n"
        f"{BUTTON_SUPPLIERS} — ТЗ файлом, текстом или архивом.\n"
        f"{BUTTON_REPORT} — номер извещения, документы, архив или ссылка.\n"
        f"{BUTTON_ANALYSIS_AND_SUPPLIERS} — анализ закупки и поставщики по найденному ТЗ.\n\n"
        "💳 Генерация списывается только после выдачи результата.\n"
        f"📊 Остатки смотрите в «{BUTTON_ACCESS}».\n\n"
        f"{INDIVIDUAL_TERMS_NOTE}\n\n"
        f"{AI_HELP_NOTE}\n\n"
        f"⚖️ Правовая информация: {LEGAL_INDEX_URL}\n\n"
        "Если доступа нет, нажмите «Контакты»: там будет ваш Telegram ID для подключения доступа.",
        reply_markup=_menu_for_chat(message.chat.id),
    )


@router.callback_query(F.data.startswith("find_more_prompt:"))
async def find_more_suppliers_prompt(callback: CallbackQuery) -> None:
    job_id = str(callback.data or "").split(":", 1)[1]
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    if not _callback_job_allowed(callback, job_id):
        await callback.answer("Эта задача относится к другому доступу.", show_alert=True)
        return
    await callback.answer()
    try:
        await callback.message.edit_text(
            _find_more_suppliers_confirmation_text(),
            reply_markup=_find_more_suppliers_confirmation_keyboard(job_id),
        )
    except TelegramBadRequest:
        await callback.message.answer(
            _find_more_suppliers_confirmation_text(),
            reply_markup=_find_more_suppliers_confirmation_keyboard(job_id),
        )


@router.callback_query(F.data.startswith("find_more_no:"))
async def find_more_suppliers_decline(callback: CallbackQuery) -> None:
    job_id = str(callback.data or "").split(":", 1)[1]
    if not _callback_job_allowed(callback, job_id):
        await callback.answer("Эта задача относится к другому доступу.", show_alert=True)
        return
    await callback.answer("Поиск не запущен.")
    if callback.message:
        try:
            await callback.message.edit_text("Дополнительный поиск не запущен.")
        except TelegramBadRequest:
            await callback.message.answer("Дополнительный поиск не запущен.", reply_markup=main_menu())


@router.callback_query(F.data.startswith("find_more_yes:"))
async def find_more_suppliers_accept(callback: CallbackQuery) -> None:
    job_id = str(callback.data or "").split(":", 1)[1]
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    chat_id = int(callback.message.chat.id)
    if _chat_has_processing_job(chat_id):
        await callback.answer("У вас уже есть задача в работе. Дождитесь результата.", show_alert=True)
        return

    telegram_id, username, name = _callback_user_fields(callback)
    db = SessionLocal()
    new_job_id = ""
    launch_snapshot: JobProgressSnapshot | None = None
    try:
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        if account_error:
            await callback.answer(account_error, show_alert=True)
            return
        if not client:
            await callback.answer("Доступ не подключён. Откройте «Контакты» и отправьте владельцу ваш Telegram ID.", show_alert=True)
            return
        original_job = db.get(Job, job_id)
        if not original_job or original_job.client_id != client.id:
            await callback.answer("Эта задача относится к другому доступу.", show_alert=True)
            return
        new_job = create_additional_supplier_search_for_client(
            db,
            client=client,
            original_job=original_job,
            created_by_telegram_id=telegram_id,
        )
        new_job_id = new_job.id
        launch_snapshot = _job_snapshot(new_job)
    except HTTPException as exc:
        detail = str(exc.detail or "Не удалось запустить дополнительный поиск.")
        await callback.answer(detail, show_alert=True)
        return
    finally:
        db.close()

    BATCH_RUNNING_CHATS.add(chat_id)
    await callback.answer("Дополнительный поиск запущен.")
    launch_message = await callback.message.answer(
        _format_launch_progress(launch_snapshot, "✅ Дополнительный поиск поставщиков запущен."),
        reply_markup=processing_menu(),
    )
    try:
        snapshot = await watch_job_progress(callback.message, new_job_id, status_message=launch_message)
        if not (snapshot and snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION):
            await _send_job_outputs(callback.message, new_job_id, snapshot)
    finally:
        BATCH_RUNNING_CHATS.discard(chat_id)


@router.callback_query(F.data.startswith("result_offer_yes:"))
@router.callback_query(F.data.startswith("partial_yes:"))
async def partial_report_accept(callback: CallbackQuery) -> None:
    job_id = str(callback.data or "").split(":", 1)[1]
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    if not _callback_job_allowed(callback, job_id):
        await callback.answer("Эта задача относится к другому доступу.", show_alert=True)
        return
    db = SessionLocal()
    try:
        candidate = db.get(Job, job_id)
        confirmation_kind = str(getattr(candidate, "confirmation_kind", "") or "") if candidate else ""
    finally:
        db.close()
    if confirmation_kind:
        try:
            delivered = await _send_result_offer_outputs(
                callback.message,
                job_id,
                accept_if_pending=True,
            )
        except (ResultOfferConflict, ResultOfferGone) as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        except Exception:
            logger.exception("Could not deliver registry fallback for job %s", job_id)
            await callback.answer("Не удалось отправить все файлы. Списания нет.", show_alert=True)
            return
        if not delivered:
            await callback.answer("Результат уже был выдан; повторного списания нет.", show_alert=True)
            return
        await callback.answer("Отчёт отправлен.")
        delivered_text = (
            "Отчёт без подтверждения реестра отправлен. Списание выполнено только после успешной отправки."
            if confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK
            else "Неполный отчёт отправлен. Списание выполнено только после успешной отправки."
        )
        await callback.message.answer(delivered_text, reply_markup=main_menu())
        return
    db = SessionLocal()
    try:
        expire_stale_confirmations(db)
        job = db.get(Job, job_id)
        if not job or job.status != STATUS_AWAITING_CUSTOMER_CONFIRMATION:
            await callback.answer("Подтверждение уже не актуально.", show_alert=True)
            return
        snapshot = _job_snapshot(job)
    finally:
        db.close()
    try:
        delivered = await _send_job_outputs(callback.message, job_id, snapshot)
    except Exception:
        await callback.answer("Не удалось отправить файл. Списания нет.", show_alert=True)
        return
    if not delivered:
        await callback.answer("Файл не найден. Списания нет.", show_alert=True)
        return
    _mark_partial_delivered(job_id)
    await callback.answer("Отчёт отправлен.")
    await callback.message.answer("Неполный отчёт отправлен. Генерация списана после успешной отправки.", reply_markup=main_menu())
    await _send_find_more_suppliers_offer(callback.message, job_id)


@router.callback_query(F.data.startswith("result_offer_no:"))
@router.callback_query(F.data.startswith("partial_no:"))
async def partial_report_decline(callback: CallbackQuery) -> None:
    job_id = str(callback.data or "").split(":", 1)[1]
    if not _callback_job_allowed(callback, job_id):
        await callback.answer("Эта задача относится к другому доступу.", show_alert=True)
        return
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        confirmation_kind = str(getattr(job, "confirmation_kind", "") or "") if job else ""
        if job and confirmation_kind:
            try:
                decline_job_result_offer(db, job, channel="telegram")
            except (ResultOfferConflict, ResultOfferGone) as exc:
                await callback.answer(str(exc), show_alert=True)
                return
            decline_answer = (
                "Списания за поиск поставщиков нет."
                if confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK
                else "Списания нет."
            )
            await callback.answer(decline_answer)
            if callback.message:
                decline_text = (
                    "Вариант без подтверждения реестра не отправлен. Списания за поиск поставщиков нет."
                    if confirmation_kind == CONFIRMATION_KIND_REGISTRY_FALLBACK
                    else "Неполный отчёт не отправлен. Резерв возвращён, списания нет."
                )
                await callback.message.answer(
                    decline_text,
                    reply_markup=main_menu(),
                )
            return
        if not job or job.status != STATUS_AWAITING_CUSTOMER_CONFIRMATION:
            await callback.answer("Подтверждение уже не актуально.", show_alert=True)
            return
        release_job_reservation(db, job, note="Резерв возвращён: клиент отказался от неполного отчёта")
        job.status = STATUS_CUSTOMER_DECLINED
        job.message = "Клиент отказался от неполного отчёта"
        job.error = ""
        job.completed_at = now_utc()
        job.updated_at = now_utc()
        db.commit()
    finally:
        db.close()
    await callback.answer("Списания нет.")
    if callback.message:
        await callback.message.answer("Отчёт не отправлен. Резерв возвращён, списания нет.", reply_markup=main_menu())


def _callback_job_allowed(callback: CallbackQuery, job_id: str) -> bool:
    telegram_id = str(callback.from_user.id if callback.from_user else "")
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job or not job.client_id:
            return False
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id)
        return bool(client and not account_error and client.id == job.client_id)
    finally:
        db.close()


def _mark_partial_delivered(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return
        job.status = "partial"
        job.message = (
            f"Частично готово: отобрано кандидатов {job.verified_count}. "
            "Уровень технического совпадения указан в отчёте"
        )
        job.error = ""
        job.completed_at = now_utc()
        job.updated_at = now_utc()
        db.commit()
    finally:
        db.close()


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    async with _chat_upload_lock(message.chat.id):
        await _handle_document_locked(message, bot)


async def _handle_document_locked(message: Message, bot: Bot) -> None:
    if await _reject_if_chat_processing(message):
        return
    scenario = _scenario_for_message(message)
    mode = _job_mode_for_scenario(scenario)
    db = SessionLocal()
    try:
        telegram_id, username, name = _telegram_user_fields(message)
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        error = account_error or client_access_error(db, client, mode, incoming_file_count=1)
        if error:
            await message.answer(error, reply_markup=main_menu())
            return
        assert client is not None
        settings = get_or_create_settings(db)
        max_mb = settings.max_upload_mb
        document = message.document
        if document.file_size and document.file_size > max_mb * 1024 * 1024:
            await message.answer(f"Файл слишком большой. Лимит: {max_mb} МБ.", reply_markup=main_menu())
            return
        try:
            filename, content = await _download_document_content(message, bot)
        except RuntimeError:
            await message.answer(
                "Не удалось загрузить файл из Telegram.\n"
                "Отправьте этот файл ещё раз отдельно или загрузите документы одним архивом.",
                reply_markup=batch_menu(),
            )
            return
        caption_sources = _source_payloads_for_scenario(scenario, str(message.caption or ""))
        pending = PENDING_UPLOADS.get(message.chat.id)
        if pending and pending.mode != mode:
            PENDING_UPLOADS.pop(message.chat.id, None)
            pending = None
        if not pending:
            pending = PendingBatch(
                telegram_id=telegram_id,
                mode=mode,
                files=[],
                supplier_search_policy=_supplier_policy_for_chat(message.chat.id),
            )
            PENDING_UPLOADS[message.chat.id] = pending
        if len(pending.files) >= settings.max_files_per_batch:
            await message.answer(f"В комплекте уже максимум файлов: {settings.max_files_per_batch}.", reply_markup=batch_menu())
            return
        pending.files.append((filename, content))
        added_sources = _add_pending_sources(pending, caption_sources)
        record_journey_event(db, client.id, channel="telegram", event_name="input_added", mode=mode, outcome="document")
        await message.answer(_pending_added_text(pending, max_files=settings.max_files_per_batch, added_sources=added_sources), reply_markup=batch_menu())
    finally:
        db.close()


async def _handle_supplier_text_tz(message: Message) -> bool:
    async with _chat_upload_lock(message.chat.id):
        return await _handle_supplier_text_tz_locked(message)


async def _handle_supplier_text_tz_locked(message: Message) -> bool:
    scenario = PENDING_MODES.get(message.chat.id, SCENARIO_SUPPLIERS)
    if scenario != SCENARIO_SUPPLIERS:
        return False
    text = str(message.text or "").strip()
    if not _looks_like_supplier_text_tz(text):
        return False
    if message.chat.id in BATCH_RUNNING_CHATS:
        await message.answer(_batch_running_text(), reply_markup=processing_menu())
        return True

    mode = MODE_SUPPLIER_SEARCH
    db = SessionLocal()
    try:
        telegram_id, username, name = _telegram_user_fields(message)
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        error = account_error or client_access_error(db, client, mode, incoming_file_count=1)
        if error:
            await message.answer(error, reply_markup=main_menu())
            return True
        assert client is not None
        settings = get_or_create_settings(db)

        pending = PENDING_UPLOADS.get(message.chat.id)
        if pending and pending.mode != mode:
            PENDING_UPLOADS.pop(message.chat.id, None)
            pending = None
        if not pending:
            pending = PendingBatch(
                telegram_id=telegram_id,
                mode=mode,
                files=[],
                supplier_search_policy=_supplier_policy_for_chat(message.chat.id),
            )
            PENDING_UPLOADS[message.chat.id] = pending
        if len(pending.files) >= settings.max_files_per_batch:
            await message.answer(f"В комплекте уже максимум ТЗ: {settings.max_files_per_batch}.", reply_markup=batch_menu())
            return True
        filename, content, _title = _supplier_text_tz_payload(text, index=len(pending.files) + 1)
        pending.files.append((filename, content))
        record_journey_event(db, client.id, channel="telegram", event_name="input_added", mode=mode, outcome="text")
        await message.answer(_pending_added_text(pending, max_files=settings.max_files_per_batch), reply_markup=batch_menu())
        return True
    finally:
        db.close()


async def _handle_source_text(message: Message) -> bool:
    if await _reject_if_chat_processing(message):
        return True
    sources = source_payloads_from_text(str(message.text or ""))
    if not sources:
        return False

    scenario = PENDING_MODES.get(message.chat.id, SCENARIO_SUPPLIERS)
    if not _scenario_accepts_source_links(scenario):
        await message.answer(_source_link_rejection_text(), reply_markup=main_menu())
        return True
    mode = _job_mode_for_scenario(scenario)
    db = SessionLocal()
    try:
        telegram_id, username, name = _telegram_user_fields(message)
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        error = account_error or client_access_error(db, client, mode, incoming_file_count=0)
        if error:
            await message.answer(error, reply_markup=main_menu())
            return True
        assert client is not None
        pending = PENDING_UPLOADS.get(message.chat.id)
        if pending and pending.mode != mode:
            PENDING_UPLOADS.pop(message.chat.id, None)
            pending = None
        if not pending:
            pending = PendingBatch(
                telegram_id=telegram_id,
                mode=mode,
                files=[],
                supplier_search_policy=_supplier_policy_for_chat(message.chat.id),
            )
            PENDING_UPLOADS[message.chat.id] = pending
        _add_pending_sources(pending, sources)
        record_journey_event(db, client.id, channel="telegram", event_name="input_added", mode=mode, outcome="source")
        await message.answer(_source_added_text(pending), reply_markup=batch_menu())
    finally:
        db.close()
    return True



# --- SITE CHAT OPERATOR RELAY HANDLERS ---
CHAT_SESSIONS_FILE = "/root/projects/aipoisk-bot/data/chat_sessions.json"
OPERATOR_REPLY_SESSIONS: dict[int, str] = {}

def _load_chat_sessions() -> dict:
    for attempt in range(5):
        try:
            if not os.path.exists(CHAT_SESSIONS_FILE):
                return {}
            with open(CHAT_SESSIONS_FILE, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                return json.loads(raw) if raw else {}
        except Exception as e:
            time.sleep(0.1)
    return {}

def _save_chat_sessions(data: dict) -> None:
    try:
        d = os.path.dirname(CHAT_SESSIONS_FILE)
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        with open(CHAT_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving chat sessions: {e}")

@router.callback_query(F.data.startswith("reply:"))
async def handle_site_chat_reply_btn(callback: CallbackQuery) -> None:
    if not callback.message:
        return
    session_id = str(callback.data or "").split(":", 1)[1]
    OPERATOR_REPLY_SESSIONS[callback.message.chat.id] = session_id
    await callback.answer("Режим ответа активирован")
    await callback.message.answer(
        f"✍️ *Введите ответ для клиента* `{session_id}` *(просто отправьте текст ниже):*",
        parse_mode="Markdown",
        reply_markup=ForceReply(input_field_placeholder=f"Ответ для {session_id}..."),
    )

@router.callback_query(F.data.startswith("close:"))
async def handle_site_chat_close_btn(callback: CallbackQuery) -> None:
    if not callback.message:
        return
    session_id = str(callback.data or "").split(":", 1)[1]
    OPERATOR_REPLY_SESSIONS.pop(callback.message.chat.id, None)
    
    sessions = _load_chat_sessions()
    if session_id in sessions:
        sessions[session_id].setdefault("messages", []).append({
            "id": "sys_" + str(int(time.time() * 1000)),
            "sender": "system",
            "text": "Диалог завершен администратором. Спасибо за обращение!",
            "timestamp": now_utc().isoformat(),
        })
        _save_chat_sessions(sessions)
        
    await callback.answer("Диалог закрыт")
    try:
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔒 Диалог закрыт", callback_data="none")]
            ])
        )
    except Exception:
        pass
    await callback.message.answer(
        f"🔒 *Диалог по сессии* `{session_id}` *закрыт.*\n\nКлавиатура бота снова активна:",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

async def _handle_operator_chat_message(message: Message) -> bool:
    chat_id = message.chat.id
    text = str(message.text or "").strip() if message.text else ""
    if not text:
        return False

    session_id = OPERATOR_REPLY_SESSIONS.get(chat_id)
    if not session_id and message.reply_to_message and message.reply_to_message.text:
        match = re.search(r"sess_[a-z0-9_]+", message.reply_to_message.text, re.IGNORECASE)
        if match:
            session_id = match.group(0)

    if not session_id and text.startswith("/reply "):
        parts = text.split(" ", 2)
        if len(parts) >= 3:
            session_id = parts[1]
            text = parts[2]

    if session_id:
        session_id = session_id.strip("`'\" \t\r\n")
        sessions = _load_chat_sessions()
        matched_key = None
        if session_id in sessions:
            matched_key = session_id
        else:
            for k in sessions.keys():
                if k.lower() == session_id.lower() or session_id.lower() in k.lower():
                    matched_key = k
                    break
        
        if not matched_key and session_id:
            matched_key = session_id
            sessions[matched_key] = {
                "sessionId": session_id,
                "created": now_utc().isoformat(),
                "messages": [],
                "updated": now_utc().isoformat(),
            }

        sessions[matched_key].setdefault("messages", []).append({
            "id": "admin_" + str(int(time.time() * 1000)),
            "sender": "admin",
            "text": text,
            "timestamp": now_utc().isoformat(),
        })
        sessions[matched_key]["updated"] = now_utc().isoformat()
        _save_chat_sessions(sessions)
        OPERATOR_REPLY_SESSIONS.pop(chat_id, None)
        await message.answer(
            f"✅ *Ответ успешно доставлен клиенту на сайт!*\n\n💬 *Текст:* {text}",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return True

    return False
# --- END SITE CHAT HANDLERS ---


@router.message(F.text)
async def unknown_text(message: Message) -> None:
    if await _handle_operator_chat_message(message):
        return
    if await _handle_supplier_text_tz(message):
        return
    if await _handle_source_text(message):
        return
    await message.answer(
        "ℹ️ Выберите действие кнопкой ниже\n\n"
        "Для поставщиков отправьте ТЗ/ООЗ. Для анализа документации можно добавить номер извещения, файлы или ссылку на закупку.",
        reply_markup=_menu_for_chat(message.chat.id),
    )


@router.message()
async def unsupported_message(message: Message) -> None:
    await message.answer(
        "⚠️ Этот тип сообщения не поддерживается.\n\n"
        "Отправьте документ, архив, текст ТЗ, номер извещения или ссылку на закупку.",
        reply_markup=_menu_for_chat(message.chat.id),
    )


@group_safety_router.message()
async def reject_group_message(message: Message) -> None:
    await message.answer(
        "🔒 Для защиты документов, баланса и результатов TenderLex работает только в личном чате с ботом."
    )


@group_safety_router.callback_query()
async def reject_group_callback(callback: CallbackQuery) -> None:
    await callback.answer("Для защиты данных откройте личный чат с ботом.", show_alert=True)


async def run_bot() -> None:
    if not config.bot_token:
        raise RuntimeError("AIPOISK_BOT_TOKEN is empty")
    init_db()
    removed_temp_files = _cleanup_telegram_temp_storage()
    if removed_temp_files:
        logger.info("Removed %s stale Telegram temporary files", removed_temp_files)
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        seed_owner_client(db)
        cleanup_expired_jobs(db, settings)
        expire_result_offers(db)
        expire_stale_confirmations(db)
    finally:
        db.close()
    bot = Bot(config.bot_token) 
    try:
        import asyncio; await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    await configure_bot_profile(bot)
    dispatcher = Dispatcher()
    dispatcher.include_router(group_safety_router)
    dispatcher.include_router(router)
    reminder_task = asyncio.create_task(_onboarding_reminder_loop(bot))
    try:
        await dispatcher.start_polling(bot)
    finally:
        reminder_task.cancel()
        await asyncio.gather(reminder_task, return_exceptions=True)


async def _send_due_onboarding_reminders(bot: Bot) -> int:
    db = SessionLocal()
    sent = 0
    try:
        settings = get_or_create_settings(db)
        expire_result_offers(db)
        expire_stale_confirmations(db)
        candidates = reminder_candidates(db, settings)
        for client, telegram_id in candidates:
            reminder = claim_reminder(db, client.id)
            if not reminder:
                continue
            try:
                await bot.send_message(
                    chat_id=int(telegram_id),
                    text=ONBOARDING_REMINDER_TEXT,
                    reply_markup=main_menu(),
                )
            except Exception as exc:
                reminder.status = "failed"
                reminder.failed_at = now_utc()
                reminder.failure_code = type(exc).__name__[:80]
                db.commit()
                continue
            reminder.status = "sent"
            reminder.sent_at = now_utc()
            db.commit()
            record_journey_event(db, client.id, channel="telegram", event_name="onboarding_reminder_sent", outcome="sent")
            sent += 1
    finally:
        db.close()
    return sent


async def _onboarding_reminder_loop(bot: Bot) -> None:
    while True:
        try:
            await _send_due_onboarding_reminders(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(3600)


async def configure_bot_profile(bot: Bot) -> None:
    await bot.set_my_short_description(short_description=BOT_SHORT_DESCRIPTION)
    await bot.set_my_description(description=BOT_DESCRIPTION)
    await bot.delete_my_commands()
    await bot.set_chat_menu_button(menu_button=MenuButtonDefault())


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
