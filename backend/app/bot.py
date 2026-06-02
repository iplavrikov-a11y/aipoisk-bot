from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, KeyboardButton, Message, ReplyKeyboardMarkup

from .config import config
from .db import SessionLocal, init_db
from .document_parser import sanitize_filename
from .jobs import cleanup_expired_jobs, create_job, package_job_outputs, process_job
from .models import Client, Job
from .repository import client_access_error, get_or_create_settings, seed_owner_client

router = Router()
PENDING_MODES: dict[int, str] = {}
BUTTON_SUPPLIERS = "🔎 Поиск поставщиков"
BUTTON_REPORT = "📄 Word-отчёт"
BUTTON_STATUS = "📊 Последние задачи"
BUTTON_ACCESS = "🔐 Мой доступ"
BUTTON_HELP = "❓ Помощь"
BUTTON_ID = "🆔 Мой Telegram ID"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_SUPPLIERS), KeyboardButton(text=BUTTON_REPORT)],
            [KeyboardButton(text=BUTTON_STATUS), KeyboardButton(text=BUTTON_ACCESS)],
            [KeyboardButton(text=BUTTON_HELP), KeyboardButton(text=BUTTON_ID)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или отправьте файл",
    )


def _mode_label(mode: str) -> str:
    return "Word-отчёт" if mode == "procurement_report" else "поиск поставщиков"


def _mode_for_message(message: Message) -> str:
    caption = str(message.caption or "").lower()
    if any(marker in caption for marker in ("word", "docx", "отчёт", "отчет", "анализ")):
        return "procurement_report"
    if any(marker in caption for marker in ("поставщик", "supplier", "xlsx")):
        return "supplier_search"
    return PENDING_MODES.get(message.chat.id, "supplier_search")


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(
        "AI Poisk готов к работе.\n\n"
        "Выберите действие кнопкой ниже, затем отправьте файл закупки или ТЗ. "
        "Команды знать не нужно.",
        reply_markup=main_menu(),
    )


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
    telegram_id = str(message.from_user.id if message.from_user else "")
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.telegram_id == telegram_id).first()
        if not client:
            await message.answer(
                "Доступ не подключён.\n\n"
                "Нажмите «Мой Telegram ID» и отправьте ID владельцу сервиса.",
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
            await message.answer("Задач пока нет. Выберите режим и отправьте файл закупки.", reply_markup=main_menu())
            return
        lines = ["Последние задачи:"]
        for job in jobs:
            lines.append(f"{job.id[:8]} — {_mode_label(job.mode)} — {job.status}, {job.progress}% — {job.message}")
        await message.answer("\n".join(lines), reply_markup=main_menu())
    finally:
        db.close()


@router.message(Command("suppliers"))
async def supplier_mode(message: Message) -> None:
    PENDING_MODES[message.chat.id] = "supplier_search"
    await message.answer(
        "Режим: поиск поставщиков.\n\n"
        "Теперь отправьте файл закупки или ТЗ. Я подготовлю XLSX/отчёт по поставщикам.",
        reply_markup=main_menu(),
    )


@router.message(Command("report"))
async def report_mode(message: Message) -> None:
    PENDING_MODES[message.chat.id] = "procurement_report"
    await message.answer(
        "Режим: Word-отчёт.\n\n"
        "Теперь отправьте файл закупки. Я подготовлю стандартный Word-отчёт.",
        reply_markup=main_menu(),
    )


@router.message(F.text == BUTTON_SUPPLIERS)
async def supplier_button(message: Message) -> None:
    await supplier_mode(message)


@router.message(F.text == BUTTON_REPORT)
async def report_button(message: Message) -> None:
    await report_mode(message)


@router.message(F.text == BUTTON_STATUS)
async def status_button(message: Message) -> None:
    await show_status(message)


@router.message(F.text == BUTTON_ID)
async def id_button(message: Message) -> None:
    await show_id(message)


@router.message(F.text == BUTTON_ACCESS)
async def access_button(message: Message) -> None:
    telegram_id = str(message.from_user.id if message.from_user else "")
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.telegram_id == telegram_id).first()
        if not client:
            await message.answer(
                "Доступ не подключён.\n\n"
                f"Ваш Telegram ID: {telegram_id}\n"
                "Отправьте этот ID владельцу сервиса, чтобы он включил доступ.",
                reply_markup=main_menu(),
            )
            return
        features = []
        if client.allowed_supplier_search:
            features.append("поиск поставщиков")
        if client.allowed_procurement_report:
            features.append("Word-отчёт")
        await message.answer(
            "Ваш доступ:\n"
            f"Статус: {'включён' if client.is_active else 'выключен'}\n"
            f"Срок: {client.access_until or 'без даты'}\n"
            f"Функции: {', '.join(features) if features else 'не включены'}\n"
            f"Лимит задач в месяц: {client.monthly_job_limit}\n"
            f"Лимит файлов в месяц: {client.monthly_file_limit}",
            reply_markup=main_menu(),
        )
    finally:
        db.close()


@router.message(F.text == BUTTON_HELP)
async def help_button(message: Message) -> None:
    await message.answer(
        "Как пользоваться:\n\n"
        "1. Нажмите «Поиск поставщиков» или «Word-отчёт».\n"
        "2. Отправьте файл закупки, ТЗ или документацию.\n"
        "3. Дождитесь результата, бот пришлёт готовый файл отчёта.\n\n"
        "Если доступа нет, нажмите «Мой Telegram ID» и отправьте ID владельцу сервиса.",
        reply_markup=main_menu(),
    )


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    mode = _mode_for_message(message)
    db = SessionLocal()
    try:
        telegram_id = str(message.from_user.id if message.from_user else "")
        client = db.query(Client).filter(Client.telegram_id == telegram_id).first()
        error = client_access_error(db, client, mode, incoming_file_count=1)
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
        file = await bot.get_file(document.file_id)
        temp_dir = config.storage_path / "telegram" / str(message.chat.id)
        temp_dir.mkdir(parents=True, exist_ok=True)
        filename = sanitize_filename(document.file_name or "document")
        temp_path = temp_dir / filename
        await bot.download_file(file.file_path, destination=temp_path)
        content = temp_path.read_bytes()
        title = Path(filename).stem[:120]
        job = create_job(
            db,
            client_id=client.id,
            mode=mode,
            title=title,
            target_suppliers=settings.default_supplier_target,
            files=[(filename, content)],
        )
        PENDING_MODES.pop(message.chat.id, None)
        await message.answer(
            f"Задача создана: {job.id[:8]} ({_mode_label(mode)}). Начинаю обработку.",
            reply_markup=main_menu(),
        )
    finally:
        db.close()

    await process_job(job.id)
    db = SessionLocal()
    try:
        done_job = db.get(Job, job.id)
        if not done_job:
            await message.answer("Задача потеряна. Сообщите владельцу сервиса.", reply_markup=main_menu())
            return
        output = package_job_outputs(done_job)
        await message.answer(done_job.message, reply_markup=main_menu())
        if output and output.exists():
            await message.answer_document(FSInputFile(output))
    finally:
        db.close()


@router.message(F.text)
async def unknown_text(message: Message) -> None:
    await message.answer(
        "Выберите действие кнопкой ниже или отправьте файл закупки.",
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
    finally:
        db.close()
    bot = Bot(config.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
