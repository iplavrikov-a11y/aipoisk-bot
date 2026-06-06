from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, MenuButtonDefault, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from .billing import (
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    STATUS_CUSTOMER_DECLINED,
    BillingError,
    balance_counter,
    charge_job_reservation,
    client_balance_summary,
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
    TERMINAL_JOB_STATUSES,
    cleanup_expired_jobs,
    create_job,
    package_job_output_files,
)
from .models import DEFAULT_PAYMENT_INSTRUCTIONS, Client, Job, now_utc
from .procurement_sources import source_label, source_payloads_from_text
from .repository import client_access_error, get_or_create_settings, get_or_create_trial_client_by_telegram_id, seed_owner_client

router = Router()
PENDING_MODES: dict[int, str] = {}
SCENARIO_SUPPLIERS_SINGLE = "suppliers_single"
SCENARIO_SUPPLIERS_MULTI = "suppliers_multi"
SCENARIO_REPORT = "report"
SCENARIO_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"
BUTTON_SUPPLIERS_SINGLE = "🔎 Поставщики по одному ТЗ"
BUTTON_SUPPLIERS_MULTI = "🗂 Поставщики по нескольким ТЗ"
BUTTON_REPORT = "📄 Анализ документации"
BUTTON_ANALYSIS_AND_SUPPLIERS = "📄🔎 Анализ + поставщики"
BUTTON_CREATE = "🚀 Создать отчёт"
BUTTON_STATUS = "🕘 Последние задачи"
BUTTON_ACCESS = "📊 Мой кабинет"
BUTTON_TARIFFS = "💳 Тарифы и оплата"
BUTTON_HELP = "❓ Помощь"
BUTTON_CONTACTS = "📞 Контакты"
BUTTON_RUN_BATCH = "▶️ Запустить обработку"
BUTTON_CANCEL_BATCH = "🗑 Очистить документы"
BUTTON_BACK_MAIN = "⬅️ Главное меню"

BOT_SHORT_DESCRIPTION = "AI-бот для тендеров: номер извещения, документация, поставщики и отчёты."
BOT_DESCRIPTION = (
    "AI Poisk помогает по тендерам: ищет и проверяет поставщиков по ТЗ, "
    "анализирует закупочную документацию по номеру извещения, ссылке или файлам "
    "и выдаёт готовые файлы в Telegram.\n\n"
    "Чтобы начать, откройте бота и нажмите кнопку Start/Запустить, затем используйте кнопки меню."
)
AI_CUSTOMER_NOTE = (
    "Важно: результат подготовлен с помощью AI и помогает быстрее оценить закупку. "
    "Критичные условия сверяйте с официальной документацией и первоисточниками."
)
AI_HELP_NOTE = (
    "AI помогает быстро подготовить первичный анализ, но важные юридические, финансовые "
    "и технические условия лучше дополнительно сверять по официальным документам."
)
OWNER_ALERT_STATUSES = {"failed", "needs_review", STATUS_AWAITING_CUSTOMER_CONFIRMATION}
OWNER_ALERTED_KEYS: set[tuple[str, str]] = set()


@dataclass
class PendingBatch:
    telegram_id: str
    mode: str
    files: list[tuple[str, bytes]]
    sources: list[dict] = field(default_factory=list)


@dataclass
class JobProgressSnapshot:
    id: str
    mode: str
    status: str
    progress: int
    message: str
    error: str
    created_at: datetime | None


PENDING_UPLOADS: dict[int, PendingBatch] = {}
CHAT_UPLOAD_LOCKS: dict[int, asyncio.Lock] = {}
BATCH_RUNNING_CHATS: set[int] = set()
TEXT_TZ_MIN_CHARS = 50
TEXT_TZ_MIN_WORDS = 6


def _pending_input_count(pending: PendingBatch) -> int:
    return len(pending.files) + len(pending.sources)


def _scenario_accepts_source_links(scenario: str) -> bool:
    return scenario in {SCENARIO_REPORT, SCENARIO_ANALYSIS_AND_SUPPLIERS}


def _source_link_rejection_text() -> str:
    return (
        "Я распознал номер извещения или ссылку на закупку, но не добавил источник в режим поиска поставщиков.\n\n"
        "Для поиска поставщиков нужен файл ТЗ/ООЗ или текстовое описание объекта закупки. "
        "Номер извещения запускает работу с закупочной документацией, а это отдельные режимы "
        "с отдельными доступами и лимитами.\n\n"
        "Чтобы работать по номеру извещения, сначала выберите «Анализ документации» "
        "или «Анализ + поставщики»."
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


def _trial_restricted_text(scenario: str) -> str:
    if scenario == SCENARIO_SUPPLIERS_MULTI:
        return "В бесплатном доступе массовая обработка ТЗ недоступна. Отправьте одно ТЗ для поиска поставщиков."
    return "В бесплатном доступе режим «Анализ + поставщики» недоступен. Запустите анализ и поиск поставщиков отдельно."


async def _reject_trial_restricted_scenario(message: Message, scenario: str) -> bool:
    telegram_id, username, name = _telegram_user_fields(message)
    db = SessionLocal()
    try:
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        if account_error:
            await message.answer(account_error, reply_markup=main_menu())
            return True
        if client and client.is_trial:
            await message.answer(_trial_restricted_text(scenario), reply_markup=main_menu())
            return True
    finally:
        db.close()
    return False


def _chat_upload_lock(chat_id: int) -> asyncio.Lock:
    lock = CHAT_UPLOAD_LOCKS.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        CHAT_UPLOAD_LOCKS[chat_id] = lock
    return lock


def _supplier_multi_intro_text() -> str:
    return (
        "Массовый поиск поставщиков по нескольким ТЗ.\n\n"
        "Каждый файл считается отдельным ТЗ. По каждому ТЗ я запущу отдельный поиск "
        "и пришлю отдельный Excel-файл с поставщиками.\n\n"
        "1. Отправьте все файлы ТЗ.\n"
        "2. Дождитесь сообщений «ТЗ добавлено».\n"
        "3. Нажмите «Запустить обработку»."
    )


def _pending_added_text(pending: PendingBatch, *, max_files: int, added_sources: int = 0) -> str:
    if pending.mode == MODE_SUPPLIER_SEARCH:
        return (
            f"ТЗ добавлено: {len(pending.files)}/{max_files}.\n"
            "Можно отправить ещё ТЗ или нажать «Запустить обработку».\n"
            "После запуска по каждому ТЗ будет отдельный Excel-файл."
        )
    source_text = f"\nИсточников добавлено: {added_sources}. Всего источников: {len(pending.sources)}." if added_sources else ""
    return f"Документ добавлен: {len(pending.files)}/{max_files}.{source_text}\nРежим: {_mode_label(pending.mode)}."


def _batch_running_text() -> str:
    return (
        "Обработка уже запущена.\n"
        "Кнопки добавления документов временно скрыты. Я буду обновлять статус и пришлю файлы по мере готовности."
    )


async def _download_document_content(message: Message, bot: Bot) -> tuple[str, bytes]:
    document = message.document
    filename = sanitize_filename(document.file_name or "document")
    temp_dir = config.storage_path / "telegram" / str(message.chat.id)
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / filename
    last_error: Exception | None = None
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


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_CREATE), KeyboardButton(text=BUTTON_ACCESS)],
            [KeyboardButton(text=BUTTON_TARIFFS), KeyboardButton(text=BUTTON_HELP)],
            [KeyboardButton(text=BUTTON_CONTACTS), KeyboardButton(text=BUTTON_STATUS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def create_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_SUPPLIERS_SINGLE)],
            [KeyboardButton(text=BUTTON_SUPPLIERS_MULTI)],
            [KeyboardButton(text=BUTTON_REPORT)],
            [KeyboardButton(text=BUTTON_ANALYSIS_AND_SUPPLIERS)],
            [KeyboardButton(text=BUTTON_BACK_MAIN)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите тип отчёта",
    )


def batch_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_RUN_BATCH)],
            [KeyboardButton(text=BUTTON_SUPPLIERS_SINGLE)],
            [KeyboardButton(text=BUTTON_SUPPLIERS_MULTI)],
            [KeyboardButton(text=BUTTON_REPORT)],
            [KeyboardButton(text=BUTTON_ANALYSIS_AND_SUPPLIERS)],
            [KeyboardButton(text=BUTTON_STATUS), KeyboardButton(text=BUTTON_ACCESS)],
            [KeyboardButton(text=BUTTON_CANCEL_BATCH)],
            [KeyboardButton(text=BUTTON_BACK_MAIN)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Добавьте материалы или запустите обработку",
    )


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
        STATUS_AWAITING_CUSTOMER_CONFIRMATION: "ожидает решения",
        STATUS_CUSTOMER_DECLINED: "отклонено клиентом",
        STATUS_CONFIRMATION_EXPIRED: "подтверждение истекло",
    }
    return labels.get(status, status)


def _progress_bar(progress: int) -> str:
    safe_progress = max(0, min(100, int(progress or 0)))
    filled = safe_progress // 10
    return "🟩" * filled + "⬜" * (10 - filled)


def _progress_heading(snapshot: JobProgressSnapshot) -> str:
    if snapshot.status == "failed":
        return "⚠️ Не удалось подготовить файл"
    if snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
        return "⚠️ Нужно подтвердить выдачу отчёта"
    if snapshot.status == STATUS_CUSTOMER_DECLINED:
        return "Отчёт не отправлен"
    if snapshot.status == STATUS_CONFIRMATION_EXPIRED:
        return "Подтверждение истекло"
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
    if "анализ документации" in lowered or "формирую отчёт" in lowered or "формирую отчет" in lowered:
        return "готовлю анализ документации"
    if "готово" in lowered:
        return "готовлю файл к отправке"
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
    if snapshot.status in TERMINAL_JOB_STATUSES:
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
                "Я не отправлю файл и не спишу генерацию без вашего согласия.",
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
    if snapshot.status in {"completed", "partial", "needs_review"}:
        return "\n".join(
            [
                _progress_heading(snapshot),
                "",
                _friendly_stage_text(snapshot.message),
                f"Прошло: {elapsed}",
            ]
        )
    lines = [
        _progress_heading(snapshot),
        "",
        f"{_progress_bar(snapshot.progress)} {snapshot.progress}%",
        f"Сейчас: {_friendly_stage_text(snapshot.message)}",
        f"Прошло: {elapsed}",
        f"Ориентир: {_job_eta_text(snapshot, now=now)}",
    ]
    return "\n".join(lines)


def _job_snapshot(job: Job) -> JobProgressSnapshot:
    return JobProgressSnapshot(
        id=job.id,
        mode=job.mode,
        status=job.status,
        progress=job.progress,
        message=job.message,
        error=job.error,
        created_at=job.created_at,
    )


def _load_job_snapshot(job_id: str) -> JobProgressSnapshot | None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        return _job_snapshot(job) if job else None
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
        "⚠️ AI Poisk: нужна проверка задачи",
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
        lines.append(f"Evidence: {evidence_path}")
    lines.append("Что сделать: проверить настройки модели, evidence и последние логи worker.")
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


async def _edit_or_send_status(status_message: Message, text: str) -> Message:
    try:
        await status_message.edit_text(text)
        return status_message
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return status_message
        return await status_message.answer(text)


async def watch_job_progress(message: Message, job_id: str, *, timeout_seconds: int = 3600, poll_interval: float = 5.0) -> JobProgressSnapshot | None:
    started = asyncio.get_running_loop().time()
    snapshot = _load_job_snapshot(job_id)
    if snapshot is None:
        await message.answer("Задача не найдена. Сообщите владельцу сервиса.", reply_markup=main_menu())
        return None
    status_message = await message.answer(_format_job_progress(snapshot))
    last_key = (snapshot.status, snapshot.progress, snapshot.message, snapshot.error)
    last_heartbeat = started

    while snapshot.status not in TERMINAL_JOB_STATUSES:
        if asyncio.get_running_loop().time() - started >= timeout_seconds:
            await _edit_or_send_status(
                status_message,
                _format_job_progress(snapshot)
                + "\n\nЗадача всё ещё выполняется. Я продолжу обработку на сервере, статус можно проверить кнопкой «Последние задачи».",
            )
            return snapshot
        await asyncio.sleep(poll_interval)
        current = _load_job_snapshot(job_id)
        if current is None:
            await _edit_or_send_status(status_message, "Задача не найдена. Сообщите владельцу сервиса.")
            return None
        snapshot = current
        key = (snapshot.status, snapshot.progress, snapshot.message, snapshot.error)
        now = asyncio.get_running_loop().time()
        if key != last_key or now - last_heartbeat >= 60:
            status_message = await _edit_or_send_status(status_message, _format_job_progress(snapshot))
            last_key = key
            last_heartbeat = now

    await _edit_or_send_status(status_message, _format_job_progress(snapshot))
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
        return SCENARIO_SUPPLIERS_SINGLE
    return PENDING_MODES.get(message.chat.id, SCENARIO_SUPPLIERS_SINGLE)


def _start_text() -> str:
    return (
        "👋 Добро пожаловать в AI Poisk.\n\n"
        "Я помогаю по закупкам:\n"
        "🔎 найти и проверить поставщиков по ТЗ;\n"
        "📄 подготовить анализ закупочной документации;\n"
        "📄🔎 сделать анализ и отдельный файл с поставщиками.\n\n"
        "Как начать:\n"
        "1. Нажмите «Создать отчёт».\n"
        "2. Выберите тип отчёта.\n"
        "3. Отправьте ТЗ, документацию, архив, номер извещения или ссылку, если режим это поддерживает.\n"
        "4. Дождитесь статуса и готового файла.\n\n"
        "💳 Генерации списываются только после выдачи результата. Если задача не подготовила файл, списания нет.\n"
        "📊 Остатки доступны в «Мой кабинет»."
    )


def _contacts_text(settings, telegram_id: str = "") -> str:
    lines = ["📞 Контакты"]
    if settings.contact_telegram:
        lines.append(f"Telegram: {settings.contact_telegram}")
    if settings.contact_email:
        lines.append(f"Email: {settings.contact_email}")
    if getattr(settings, "contact_website", ""):
        lines.append(f"Сайт: {settings.contact_website}")
    if not settings.contact_telegram and not settings.contact_email and not getattr(settings, "contact_website", ""):
        lines.append("Контакты для покупки пока не указаны владельцем сервиса.")
    if telegram_id:
        lines.extend(["", f"Ваш Telegram ID: {telegram_id}"])
    return "\n".join(lines)


def _balance_line(counter: dict) -> str:
    return (
        f"{counter['label']}: доступно {counter['available']}, "
        f"в обработке {counter['reserved']}, списано {counter['spent']}"
    )


def _cabinet_text(db, client: Client, settings) -> str:
    balances = client_balance_summary(db, client)
    lines = [
        "📊 Мой кабинет",
        "",
        f"Статус: {'включён' if client.is_active else 'выключен'}",
        f"Тип: {'бесплатный доступ' if client.is_trial else 'клиент'}",
        "",
        "Баланс генераций:",
        _balance_line(balances["supplier_search"]),
        _balance_line(balances["procurement_report"]),
    ]
    low = [item["label"] for item in balances.values() if item.get("low")]
    if low:
        lines.extend(["", f"⚠️ Заканчивается баланс: {', '.join(low)}."])
    lines.extend(["", "Пополнить пакет можно в разделе «Тарифы и оплата»."])
    if settings.contact_telegram or settings.contact_email or getattr(settings, "contact_website", ""):
        lines.extend(["", _contacts_text(settings)])
    return "\n".join(lines)


def _price_text(price_kopeks: int) -> str:
    if int(price_kopeks or 0) <= 0:
        return "цену уточните у владельца"
    rubles = int(price_kopeks) / 100
    if rubles.is_integer():
        return f"{int(rubles):,} ₽".replace(",", " ")
    return f"{rubles:,.2f} ₽".replace(",", " ")


def _tariffs_text(db, settings) -> str:
    packages = [tariff_to_dict(item) for item in list_tariffs(db, active_only=True)]
    supplier = [item for item in packages if item["kind"] == "supplier_search"]
    reports = [item for item in packages if item["kind"] == "procurement_report"]
    lines = [
        "💳 Тарифы и оплата",
        "",
        "Пакеты не сгорают и действуют до полного исчерпания.",
    ]
    if supplier:
        lines.extend(["", "🔎 Поставщики:"])
        for item in supplier:
            lines.append(f"• {item['name']} — {item['units']} генераций, {_price_text(item['price_kopeks'])}")
    if reports:
        lines.extend(["", "📄 Анализ документации:"])
        for item in reports:
            lines.append(f"• {item['name']} — {item['units']} генераций, {_price_text(item['price_kopeks'])}")
    if not supplier and not reports:
        lines.extend(["", "Тарифы пока не настроены в админ-панели."])
    lines.extend(["", settings.payment_instructions or DEFAULT_PAYMENT_INSTRUCTIONS])
    lines.extend(["", AI_HELP_NOTE])
    lines.extend(["", _contacts_text(settings)])
    return "\n".join(lines)


def _partial_confirmation_text(snapshot: JobProgressSnapshot) -> str:
    return (
        "⚠️ Найдено меньше поставщиков, чем обычно удаётся подготовить по отчёту.\n\n"
        "Я проверил сайты и контакты. В файл попали только подтверждённые компании.\n\n"
        f"Результат: {_friendly_stage_text(snapshot.message)}.\n\n"
        "Могу отправить отчёт, но после успешной отправки будет списана генерация из пакета.\n\n"
        "Отправить отчёт?"
    )


def _partial_confirmation_keyboard(job_id: str) -> InlineKeyboardMarkup:
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


@router.message(Command("start"))
async def start(message: Message) -> None:
    telegram_id, username, name = _telegram_user_fields(message)
    access_note = ""
    db = SessionLocal()
    try:
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        if account_error:
            access_note = f"\n\n⚠️ {account_error}"
        elif client:
            access_note = "\n\n✅ Telegram-аккаунт подключён. Можно работать через кнопки меню."
    finally:
        db.close()
    await message.answer(_start_text() + access_note, reply_markup=main_menu())


@router.message(Command("id"))
async def show_id(message: Message) -> None:
    telegram_id = str(message.from_user.id if message.from_user else "")
    await message.answer(
        f"Ваш Telegram ID: {telegram_id}\n\n"
        "Если доступ ещё не подключён, отправьте этот ID владельцу сервиса.",
        reply_markup=main_menu(),
    )


@router.message(Command("status"))
async def show_status(message: Message) -> None:
    telegram_id, username, name = _telegram_user_fields(message)
    partial_confirmations: list[tuple[str, JobProgressSnapshot]] = []
    recoverable_outputs: list[tuple[str, JobProgressSnapshot]] = []
    db = SessionLocal()
    try:
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        if account_error:
            await message.answer(account_error, reply_markup=main_menu())
            return
        if not client:
            await message.answer(
                "Доступ не подключён.\n\n"
                "Нажмите «Контакты»: там будет ваш Telegram ID для подключения доступа.",
                reply_markup=main_menu(),
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
            await message.answer("Задач пока нет. Выберите режим и отправьте материалы закупки.", reply_markup=main_menu())
            return
        lines = ["Последние обращения:"]
        for index, job in enumerate(jobs, start=1):
            snapshot = _job_snapshot(job)
            lines.append(
                f"{index}. {_progress_heading(snapshot)} — {_status_label(snapshot.status)}, {snapshot.progress}%\n"
                f"   {_friendly_stage_text(snapshot.message)}"
            )
        await message.answer("\n".join(lines), reply_markup=main_menu())
        for job in jobs:
            snapshot = _job_snapshot(job)
            job_id = str(job.id)
            if snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
                partial_confirmations.append((job_id, snapshot))
            elif snapshot.status in {"completed", "partial", "needs_review"} and job_has_unsettled_reservation(db, job):
                recoverable_outputs.append((job_id, snapshot))
    finally:
        db.close()
    for job_id, snapshot in partial_confirmations:
        await _send_partial_confirmation(message, job_id, snapshot)
    for job_id, snapshot in recoverable_outputs:
        await message.answer("Нашёл готовый результат, который ещё не был отправлен. Отправляю файл сейчас.")
        await _send_job_outputs(message, job_id, snapshot)


@router.message(Command("suppliers"))
async def supplier_mode(message: Message) -> None:
    PENDING_MODES[message.chat.id] = SCENARIO_SUPPLIERS_SINGLE
    await message.answer(
        "Поиск поставщиков по одному ТЗ.\n\n"
        "Отправьте один файл ТЗ или описание объекта закупки. Я сразу запущу поиск и подготовлю Excel-файл с поставщиками.",
        reply_markup=main_menu(),
    )


@router.message(Command("report"))
async def report_mode(message: Message) -> None:
    PENDING_MODES[message.chat.id] = SCENARIO_REPORT
    await message.answer(
        "Анализ документации.\n\n"
        "Отправьте комплект закупочной документации отдельными файлами или одним архивом. "
        "Можно также добавить номер извещения или ссылку на страницу закупки: ЕИС, ЭТП или сайт заказчика. "
        "Когда все документы будут добавлены, нажмите «Запустить обработку».",
        reply_markup=batch_menu(),
    )


@router.message(F.text == BUTTON_SUPPLIERS_SINGLE)
async def supplier_single_button(message: Message) -> None:
    await supplier_mode(message)


@router.message(F.text == BUTTON_CREATE)
async def create_button(message: Message) -> None:
    await message.answer(
        "Выберите тип отчёта.\n\n"
        "Если не уверены, начните с «Поставщики по одному ТЗ» для одного файла или с «Анализ документации» по номеру извещения, файлам, архиву или ссылке.",
        reply_markup=create_menu(),
    )


@router.message(F.text == BUTTON_BACK_MAIN)
async def back_main_button(message: Message) -> None:
    await message.answer("Главное меню.", reply_markup=main_menu())


@router.message(F.text == BUTTON_SUPPLIERS_MULTI)
async def supplier_multi_button(message: Message) -> None:
    if await _reject_trial_restricted_scenario(message, SCENARIO_SUPPLIERS_MULTI):
        return
    PENDING_MODES[message.chat.id] = SCENARIO_SUPPLIERS_MULTI
    await message.answer(_supplier_multi_intro_text(), reply_markup=batch_menu())


@router.message(F.text == BUTTON_REPORT)
async def report_button(message: Message) -> None:
    await report_mode(message)


@router.message(F.text == BUTTON_ANALYSIS_AND_SUPPLIERS)
async def analysis_and_suppliers_button(message: Message) -> None:
    if await _reject_trial_restricted_scenario(message, SCENARIO_ANALYSIS_AND_SUPPLIERS):
        return
    PENDING_MODES[message.chat.id] = SCENARIO_ANALYSIS_AND_SUPPLIERS
    await message.answer(
        "Анализ документации + поиск поставщиков.\n\n"
        "Отправьте комплект документации отдельными файлами, одним архивом или добавьте номер извещения/ссылку на закупку. "
        "Я подготовлю анализ и отдельно Excel-файл с поставщиками по найденному ТЗ.",
        reply_markup=batch_menu(),
    )


@router.message(F.text == BUTTON_STATUS)
async def status_button(message: Message) -> None:
    await show_status(message)


@router.message(F.text == BUTTON_CANCEL_BATCH)
async def cancel_batch_button(message: Message) -> None:
    PENDING_UPLOADS.pop(message.chat.id, None)
    await message.answer("Документы очищены.", reply_markup=main_menu())


@router.message(F.text == BUTTON_RUN_BATCH)
async def run_batch_button(message: Message) -> None:
    if message.chat.id in BATCH_RUNNING_CHATS:
        await message.answer(_batch_running_text(), reply_markup=ReplyKeyboardRemove())
        return
    pending = PENDING_UPLOADS.get(message.chat.id)
    if not pending or _pending_input_count(pending) == 0:
        scenario = PENDING_MODES.get(message.chat.id, SCENARIO_SUPPLIERS_SINGLE)
        if _scenario_accepts_source_links(scenario):
            text = "Документы или источник закупки пока не добавлены. Отправьте файлы закупки, архив, номер извещения или ссылку на закупку."
        else:
            text = "ТЗ пока не добавлены. Отправьте файлы ТЗ или описание объекта закупки."
        await message.answer(text, reply_markup=main_menu())
        return
    BATCH_RUNNING_CHATS.add(message.chat.id)
    job: Job | None = None
    job_id: str | None = None
    batch_jobs: list[tuple[str, str]] = []
    launch_started = False
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
            BATCH_RUNNING_CHATS.discard(message.chat.id)
            await message.answer(error, reply_markup=batch_menu())
            return
        assert client is not None
        settings = get_or_create_settings(db)
        if supplier_job_specs:
            for title, files in supplier_job_specs:
                created = create_job(
                    db,
                    client_id=client.id,
                    created_by_telegram_id=pending.telegram_id,
                    mode=MODE_SUPPLIER_SEARCH,
                    title=title,
                    target_suppliers=settings.default_supplier_target,
                    files=files,
                    sources=[],
                )
                reserve_error = _reserve_created_job(db, client, created)
                if reserve_error:
                    BATCH_RUNNING_CHATS.discard(message.chat.id)
                    await message.answer(reserve_error, reply_markup=main_menu())
                    return
                batch_jobs.append((str(created.id), files[0][0]))
        else:
            title = Path(pending.files[0][0]).stem[:120] if pending.files else source_label(pending.sources[0]["value"])[:120]
            job = create_job(
                db,
                client_id=client.id,
                created_by_telegram_id=pending.telegram_id,
                mode=pending.mode,
                title=title,
                target_suppliers=settings.default_supplier_target,
                files=pending.files,
                sources=pending.sources,
            )
            reserve_error = _reserve_created_job(db, client, job)
            if reserve_error:
                BATCH_RUNNING_CHATS.discard(message.chat.id)
                await message.answer(reserve_error, reply_markup=main_menu())
                return
            job_id = str(job.id)
        PENDING_UPLOADS.pop(message.chat.id, None)
        PENDING_MODES.pop(message.chat.id, None)
        launch_started = True
        if batch_jobs:
            await message.answer(
                f"Обработка запущена: ТЗ {len(batch_jobs)}.\n"
                "Кнопки добавления документов скрыты, чтобы случайно не запустить обработку повторно.\n"
                "По каждому ТЗ пришлю отдельный Excel-файл.",
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            await message.answer(
                f"Принял: файлов {len(pending.files)}, источников {len(pending.sources)}.\nСейчас начну обработку и буду обновлять статус здесь.",
                reply_markup=ReplyKeyboardRemove(),
            )
    finally:
        db.close()
        if not launch_started:
            BATCH_RUNNING_CHATS.discard(message.chat.id)

    try:
        if batch_jobs:
            await _watch_supplier_multi_outputs(message, batch_jobs)
            return
        if job_id is not None:
            snapshot = await watch_job_progress(message, job_id)
            if snapshot and snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
                await _send_partial_confirmation(message, job_id, snapshot)
            else:
                await _send_job_outputs(message, job_id, snapshot)
                await message.answer("Обработка завершена. Можно выбрать следующее действие.", reply_markup=main_menu())
    finally:
        BATCH_RUNNING_CHATS.discard(message.chat.id)


async def _watch_supplier_multi_outputs(message: Message, jobs: list[tuple[str, str]]) -> None:
    total = len(jobs)
    for index, (job_id, filename) in enumerate(jobs, start=1):
        title = Path(filename).stem[:80]
        await message.answer(f"Обрабатываю ТЗ {index}/{total}: {title}")
        snapshot = await watch_job_progress(message, job_id)
        if snapshot and snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
            await _send_partial_confirmation(message, job_id, snapshot)
        else:
            await _send_job_outputs(message, job_id, snapshot)
    await message.answer("Массовая обработка ТЗ завершена.", reply_markup=main_menu())


async def _send_job_outputs(message: Message, job_id: str, snapshot: JobProgressSnapshot | None = None) -> bool:
    db = SessionLocal()
    try:
        done_job = db.get(Job, job_id)
        if not done_job:
            await message.answer("Задача потеряна. Сообщите владельцу сервиса.", reply_markup=main_menu())
            return False
        outputs = package_job_output_files(done_job)
        if outputs:
            for output in outputs:
                await message.answer_document(FSInputFile(output), caption=_output_caption(done_job.mode, output))
            charge_job_reservation(db, done_job)
            if snapshot and snapshot.status in OWNER_ALERT_STATUSES:
                await _alert_owner_about_job(message, snapshot, reason=f"problem_status:{snapshot.status}")
            if done_job.client:
                await message.answer(_after_delivery_balance_text(db, done_job.client), reply_markup=main_menu())
            return True
        elif snapshot and snapshot.status not in TERMINAL_JOB_STATUSES:
            await message.answer("Обработка продолжается. Статус можно проверить кнопкой «Последние задачи».", reply_markup=main_menu())
        elif snapshot:
            await _alert_owner_about_job(message, snapshot, reason="missing_output", output_missing=True)
        return False
    finally:
        db.close()


def _after_delivery_balance_text(db, client: Client) -> str:
    balances = client_balance_summary(db, client)
    lines = ["✅ Результат отправлен. Баланс обновлён."]
    low = [item["label"] for item in balances.values() if item.get("low")]
    if low:
        lines.append(f"⚠️ Заканчивается баланс: {', '.join(low)}.")
    lines.extend(["", AI_CUSTOMER_NOTE])
    return "\n".join(lines)


async def _send_partial_confirmation(message: Message, job_id: str, snapshot: JobProgressSnapshot) -> None:
    await _alert_owner_about_job(message, snapshot, reason="awaiting_customer_confirmation")
    await message.answer(
        _partial_confirmation_text(snapshot),
        reply_markup=_partial_confirmation_keyboard(job_id),
    )


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
            await message.answer(account_error, reply_markup=main_menu())
            return
        if not client:
            await message.answer(
                "Доступ не подключён.\n\n"
                f"Ваш Telegram ID: {telegram_id}\n"
                "Отправьте этот ID владельцу сервиса, чтобы он включил доступ.\n\n"
                + _contacts_text(settings),
                reply_markup=main_menu(),
            )
            return
        await message.answer(_cabinet_text(db, client, settings), reply_markup=main_menu())
    finally:
        db.close()


@router.message(F.text == BUTTON_TARIFFS)
async def tariffs_button(message: Message) -> None:
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        await message.answer(_tariffs_text(db, settings), reply_markup=main_menu())
    finally:
        db.close()


@router.message(F.text == BUTTON_CONTACTS)
async def contacts_button(message: Message) -> None:
    telegram_id = str(message.from_user.id if message.from_user else "")
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        await message.answer(_contacts_text(settings, telegram_id=telegram_id), reply_markup=main_menu())
    finally:
        db.close()


@router.message(F.text == BUTTON_HELP)
async def help_button(message: Message) -> None:
    await message.answer(
        "❓ Помощь\n\n"
        "1. Нажмите «Создать отчёт».\n"
        "2. Выберите нужный режим.\n"
        "3. Отправьте документы.\n\n"
        "Режимы:\n"
        "🔎 «Поставщики по одному ТЗ» — один файл ТЗ или описание объекта закупки.\n"
        "🗂 «Поставщики по нескольким ТЗ» — несколько файлов ТЗ/ООЗ, каждый файл обрабатывается отдельно.\n"
        "📄 «Анализ документации» — номер извещения, комплект документации, архив или ссылка на закупку.\n"
        "📄🔎 «Анализ + поставщики» — анализ документации и отдельный Excel с поставщиками по найденному ТЗ.\n\n"
        "💳 Генерация списывается только после выдачи результата.\n"
        "📊 Остатки смотрите в «Мой кабинет».\n\n"
        f"{AI_HELP_NOTE}\n\n"
        "Если доступа нет, нажмите «Контакты»: там будет ваш Telegram ID для подключения доступа.",
        reply_markup=main_menu(),
    )


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


@router.callback_query(F.data.startswith("partial_no:"))
async def partial_report_decline(callback: CallbackQuery) -> None:
    job_id = str(callback.data or "").split(":", 1)[1]
    if not _callback_job_allowed(callback, job_id):
        await callback.answer("Эта задача относится к другому доступу.", show_alert=True)
        return
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
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
        job.message = _supplier_count_message("Частично готово", job.verified_count, job.target_suppliers)
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
    scenario = _scenario_for_message(message)
    mode = _job_mode_for_scenario(scenario)
    job_id: str | None = None
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
                reply_markup=batch_menu() if scenario != SCENARIO_SUPPLIERS_SINGLE else main_menu(),
            )
            return
        caption_sources = _source_payloads_for_scenario(scenario, str(message.caption or ""))
        if scenario == SCENARIO_SUPPLIERS_SINGLE:
            title = Path(filename).stem[:120]
            job = create_job(
                db,
                client_id=client.id,
                created_by_telegram_id=telegram_id,
                mode=mode,
                title=title,
                target_suppliers=settings.default_supplier_target,
                files=[(filename, content)],
                sources=[],
            )
            reserve_error = _reserve_created_job(db, client, job)
            if reserve_error:
                await message.answer(reserve_error, reply_markup=main_menu())
                return
            job_id = str(job.id)
            PENDING_UPLOADS.pop(message.chat.id, None)
            PENDING_MODES.pop(message.chat.id, None)
            await message.answer(
                "Принял ТЗ. Запускаю поиск поставщиков и буду обновлять статус здесь.",
                reply_markup=main_menu(),
            )
        else:
            job = None
        pending = PENDING_UPLOADS.get(message.chat.id)
        if job is None and pending and pending.mode != mode:
            PENDING_UPLOADS.pop(message.chat.id, None)
            pending = None
        if job is None and not pending:
            pending = PendingBatch(telegram_id=telegram_id, mode=mode, files=[])
            PENDING_UPLOADS[message.chat.id] = pending
        if job is None:
            if len(pending.files) >= settings.max_files_per_batch:
                await message.answer(f"В комплекте уже максимум файлов: {settings.max_files_per_batch}.", reply_markup=batch_menu())
                return
            pending.files.append((filename, content))
            added_sources = _add_pending_sources(pending, caption_sources)
            await message.answer(_pending_added_text(pending, max_files=settings.max_files_per_batch, added_sources=added_sources), reply_markup=batch_menu())
    finally:
        db.close()
    if job_id is not None:
        snapshot = await watch_job_progress(message, job_id)
        if snapshot and snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
            await _send_partial_confirmation(message, job_id, snapshot)
        else:
            await _send_job_outputs(message, job_id, snapshot)


async def _handle_supplier_text_tz(message: Message) -> bool:
    async with _chat_upload_lock(message.chat.id):
        return await _handle_supplier_text_tz_locked(message)


async def _handle_supplier_text_tz_locked(message: Message) -> bool:
    scenario = PENDING_MODES.get(message.chat.id, SCENARIO_SUPPLIERS_SINGLE)
    if scenario not in {SCENARIO_SUPPLIERS_SINGLE, SCENARIO_SUPPLIERS_MULTI}:
        return False
    text = str(message.text or "").strip()
    if not _looks_like_supplier_text_tz(text):
        return False
    if message.chat.id in BATCH_RUNNING_CHATS:
        await message.answer(_batch_running_text(), reply_markup=ReplyKeyboardRemove())
        return True

    mode = MODE_SUPPLIER_SEARCH
    job_id: str | None = None
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
        if scenario == SCENARIO_SUPPLIERS_MULTI:
            if pending and pending.mode != mode:
                PENDING_UPLOADS.pop(message.chat.id, None)
                pending = None
            if not pending:
                pending = PendingBatch(telegram_id=telegram_id, mode=mode, files=[])
                PENDING_UPLOADS[message.chat.id] = pending
            if len(pending.files) >= settings.max_files_per_batch:
                await message.answer(f"В комплекте уже максимум ТЗ: {settings.max_files_per_batch}.", reply_markup=batch_menu())
                return True
            filename, content, _title = _supplier_text_tz_payload(text, index=len(pending.files) + 1)
            pending.files.append((filename, content))
            await message.answer(_pending_added_text(pending, max_files=settings.max_files_per_batch), reply_markup=batch_menu())
            return True

        filename, content, title = _supplier_text_tz_payload(text)
        job = create_job(
            db,
            client_id=client.id,
            created_by_telegram_id=telegram_id,
            mode=mode,
            title=title,
            target_suppliers=settings.default_supplier_target,
            files=[(filename, content)],
            sources=[],
        )
        reserve_error = _reserve_created_job(db, client, job)
        if reserve_error:
            await message.answer(reserve_error, reply_markup=main_menu())
            return True
        job_id = str(job.id)
        PENDING_UPLOADS.pop(message.chat.id, None)
        PENDING_MODES.pop(message.chat.id, None)
        await message.answer(
            "Принял ТЗ из сообщения. Запускаю поиск поставщиков и буду обновлять статус здесь.",
            reply_markup=main_menu(),
        )
    finally:
        db.close()

    if job_id is not None:
        snapshot = await watch_job_progress(message, job_id)
        if snapshot and snapshot.status == STATUS_AWAITING_CUSTOMER_CONFIRMATION:
            await _send_partial_confirmation(message, job_id, snapshot)
        else:
            await _send_job_outputs(message, job_id, snapshot)
    return True


async def _handle_source_text(message: Message) -> bool:
    sources = source_payloads_from_text(str(message.text or ""))
    if not sources:
        return False

    scenario = PENDING_MODES.get(message.chat.id, SCENARIO_SUPPLIERS_SINGLE)
    if not _scenario_accepts_source_links(scenario):
        await message.answer(_source_link_rejection_text(), reply_markup=main_menu())
        return True
    mode = _job_mode_for_scenario(scenario)
    db = SessionLocal()
    job_id: str | None = None
    try:
        telegram_id, username, name = _telegram_user_fields(message)
        client, account_error = get_or_create_trial_client_by_telegram_id(db, telegram_id, username=username, name=name)
        error = account_error or client_access_error(db, client, mode, incoming_file_count=0)
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
            pending = PendingBatch(telegram_id=telegram_id, mode=mode, files=[])
            PENDING_UPLOADS[message.chat.id] = pending
        _add_pending_sources(pending, sources)
        text = f"Источник добавлен: {len(pending.sources)}. Можно добавить документы или нажать «Запустить обработку»."
        await message.answer(text, reply_markup=batch_menu())
    finally:
        db.close()

    if job_id:
        snapshot = await watch_job_progress(message, job_id)
        await _send_job_outputs(message, job_id, snapshot)
    return True


@router.message(F.text)
async def unknown_text(message: Message) -> None:
    if await _handle_supplier_text_tz(message):
        return
    if await _handle_source_text(message):
        return
    await message.answer(
        "Выберите действие кнопкой ниже. Для поставщиков отправьте ТЗ/ООЗ, для анализа документации можно добавить номер извещения, файлы или ссылку на закупку.",
        reply_markup=main_menu(),
    )


async def run_bot() -> None:
    if not config.bot_token:
        raise RuntimeError("AIPOISK_BOT_TOKEN is empty")
    init_db()
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        seed_owner_client(db)
        cleanup_expired_jobs(db, settings)
        expire_stale_confirmations(db)
    finally:
        db.close()
    bot = Bot(config.bot_token)
    await configure_bot_profile(bot)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


async def configure_bot_profile(bot: Bot) -> None:
    await bot.set_my_short_description(short_description=BOT_SHORT_DESCRIPTION)
    await bot.set_my_description(description=BOT_DESCRIPTION)
    await bot.delete_my_commands()
    await bot.set_chat_menu_button(menu_button=MenuButtonDefault())


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
