from __future__ import annotations

from datetime import datetime, timezone
import re

from sqlalchemy import func, not_, or_
from sqlalchemy.orm import Session

from .config import config
from .models import Client, ClientTelegramAccount, Job, SystemSettings, now_utc

MODE_SUPPLIER_SEARCH = "supplier_search"
MODE_PROCUREMENT_REPORT = "procurement_report"
MODE_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"
INTERNAL_JOB_PATTERN = re.compile(
    r"(smoke|retest|patch2?|remain|pusher|ai_required|live_|worker_smoke)",
    re.IGNORECASE,
)


def get_or_create_settings(db: Session) -> SystemSettings:
    settings = db.get(SystemSettings, 1)
    if settings:
        return settings
    settings = SystemSettings(
        id=1,
        public_base_url=config.public_base_url,
        custom_ai_providers_json=config.default_custom_ai_providers_json,
        saved_models_json=config.default_saved_models_json,
        ai_function_models_json=config.default_ai_function_models_json,
        primary_provider=config.default_primary_provider,
        primary_model=config.default_primary_model,
        light_provider=config.default_light_provider,
        light_model=config.default_light_model,
        supplier_search_adapter_base_url=config.default_supplier_search_adapter_base_url,
        supplier_search_adapter_api_key=config.default_supplier_search_adapter_api_key,
        supplier_search_adapter_model=config.default_supplier_search_adapter_model,
        supplier_search_provider_order=config.default_supplier_search_provider_order,
        yandex_search_folder_id=config.default_yandex_search_folder_id,
        yandex_search_api_key=config.default_yandex_search_api_key,
        google_search_api_key=config.default_google_search_api_key,
        google_search_cse_id=config.default_google_search_cse_id,
        document_settings_json=config.default_document_settings_json,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def seed_owner_client(db: Session) -> None:
    telegram_id = str(config.owner_telegram_id or "").strip()
    if not telegram_id:
        return
    existing, _account_error = get_client_by_telegram_id(db, telegram_id)
    if existing:
        ensure_client_telegram_account(db, existing, telegram_id)
        return
    client = Client(
        telegram_id=telegram_id,
        name="Owner",
        username="",
        is_active=True,
        allowed_supplier_search=True,
        allowed_procurement_report=True,
        monthly_job_limit=10000,
        monthly_supplier_search_limit=10000,
        monthly_procurement_report_limit=10000,
        monthly_file_limit=10000,
        notes="Seeded from AIPOISK_OWNER_TELEGRAM_ID",
    )
    db.add(client)
    db.flush()
    ensure_client_telegram_account(db, client, telegram_id)
    db.commit()


def parse_access_until(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        if len(normalized) == 10:
            parsed_date = datetime.fromisoformat(normalized).date()
            return datetime(parsed_date.year, parsed_date.month, parsed_date.day, 23, 59, 59, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def current_month_usage(db: Session, client: Client) -> tuple[int, int]:
    now = now_utc()
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    job_count, file_count = (
        db.query(func.count(Job.id), func.coalesce(func.sum(Job.file_count), 0))
        .filter(Job.client_id == client.id)
        .filter(Job.created_at >= month_start)
        .one()
    )
    return int(job_count or 0), int(file_count or 0)


def current_function_usage(db: Session, client: Client) -> tuple[int, int, int]:
    now = now_utc()
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    base = commercial_jobs_query(db, client).filter(Job.created_at >= month_start)
    supplier_search_count = (
        base.filter(Job.mode.in_([MODE_SUPPLIER_SEARCH, MODE_ANALYSIS_AND_SUPPLIERS]))
        .with_entities(func.count(Job.id))
        .scalar()
    )
    procurement_report_count = (
        base.filter(Job.mode.in_([MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS]))
        .with_entities(func.count(Job.id))
        .scalar()
    )
    file_count = base.with_entities(func.coalesce(func.sum(Job.file_count), 0)).scalar()
    return int(supplier_search_count or 0), int(procurement_report_count or 0), int(file_count or 0)


def is_internal_job_record(job: Job | object) -> bool:
    text = " ".join(
        str(getattr(job, attr, "") or "")
        for attr in ("title", "message", "error")
    ).lower()
    return bool(INTERNAL_JOB_PATTERN.search(text))


def commercial_jobs_query(db: Session, client: Client):
    internal_filters = [
        func.coalesce(Job.title, "").ilike("%smoke%"),
        func.coalesce(Job.title, "").ilike("%retest%"),
        func.coalesce(Job.title, "").ilike("%patch%"),
        func.coalesce(Job.title, "").ilike("%remain%"),
        func.coalesce(Job.title, "").ilike("%pusher%"),
        func.coalesce(Job.title, "").ilike("%ai_required%"),
        func.coalesce(Job.title, "").ilike("%live_%"),
        func.coalesce(Job.title, "").ilike("%worker_smoke%"),
        func.coalesce(Job.message, "").ilike("%smoke%"),
        func.coalesce(Job.message, "").ilike("%retest%"),
        func.coalesce(Job.message, "").ilike("%patch%"),
        func.coalesce(Job.message, "").ilike("%remain%"),
        func.coalesce(Job.message, "").ilike("%pusher%"),
        func.coalesce(Job.message, "").ilike("%ai_required%"),
        func.coalesce(Job.message, "").ilike("%live_%"),
        func.coalesce(Job.message, "").ilike("%worker_smoke%"),
        func.coalesce(Job.error, "").ilike("%smoke%"),
        func.coalesce(Job.error, "").ilike("%retest%"),
        func.coalesce(Job.error, "").ilike("%patch%"),
        func.coalesce(Job.error, "").ilike("%remain%"),
        func.coalesce(Job.error, "").ilike("%pusher%"),
        func.coalesce(Job.error, "").ilike("%ai_required%"),
        func.coalesce(Job.error, "").ilike("%live_%"),
        func.coalesce(Job.error, "").ilike("%worker_smoke%"),
    ]
    return db.query(Job).filter(Job.client_id == client.id).filter(not_(or_(*internal_filters)))


def ensure_client_telegram_account(
    db: Session,
    client: Client,
    telegram_id: str,
    *,
    username: str = "",
    name: str = "",
    notes: str = "",
) -> ClientTelegramAccount:
    normalized = str(telegram_id or "").strip()
    if not normalized:
        raise ValueError("telegram_id is required")
    existing = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == normalized).first()
    if existing:
        return existing
    account = ClientTelegramAccount(
        client_id=client.id,
        telegram_id=normalized,
        username=username or client.username,
        name=name or client.name,
        is_active=True,
        notes=notes,
    )
    db.add(account)
    return account


def get_client_by_telegram_id(db: Session, telegram_id: str) -> tuple[Client | None, str]:
    normalized = str(telegram_id or "").strip()
    if not normalized:
        return None, "Не удалось определить Telegram ID."
    account = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == normalized).first()
    if account:
        if not account.is_active:
            return account.client, "Telegram-аккаунт отключён для этого доступа. Свяжитесь с администратором."
        return account.client, ""
    legacy_client = db.query(Client).filter(Client.telegram_id == normalized).first()
    if legacy_client:
        ensure_client_telegram_account(db, legacy_client, normalized)
        db.commit()
        return legacy_client, ""
    return None, ""


def get_or_create_trial_client_by_telegram_id(
    db: Session,
    telegram_id: str,
    *,
    username: str = "",
    name: str = "",
) -> tuple[Client | None, str]:
    client, account_error = get_client_by_telegram_id(db, telegram_id)
    if client or account_error:
        return client, account_error
    settings = get_or_create_settings(db)
    if not settings.trial_enabled:
        return None, ""
    normalized = str(telegram_id or "").strip()
    if not normalized:
        return None, "Не удалось определить Telegram ID."
    display_name = str(name or username or f"Trial {normalized}").strip()
    client = Client(
        telegram_id=normalized,
        name=display_name,
        username=username,
        is_active=True,
        is_trial=True,
        allowed_supplier_search=True,
        allowed_procurement_report=True,
        monthly_job_limit=max(0, settings.trial_supplier_search_limit + settings.trial_procurement_report_limit),
        monthly_supplier_search_limit=settings.trial_supplier_search_limit,
        monthly_procurement_report_limit=settings.trial_procurement_report_limit,
        monthly_file_limit=settings.trial_file_limit,
        notes="Trial auto-created from Telegram",
    )
    db.add(client)
    db.flush()
    ensure_client_telegram_account(
        db,
        client,
        normalized,
        username=username,
        name=display_name,
        notes="Trial Telegram account",
    )
    db.commit()
    db.refresh(client)
    return client, ""


def requested_function_units(mode: str, *, supplier_search_count: int = 1) -> tuple[int, int]:
    supplier_units = max(1, int(supplier_search_count or 1))
    if mode == MODE_SUPPLIER_SEARCH:
        return supplier_units, 0
    if mode == MODE_PROCUREMENT_REPORT:
        return 0, 1
    if mode == MODE_ANALYSIS_AND_SUPPLIERS:
        return 1, 1
    return 0, 0


def client_access_error(
    db: Session,
    client: Client | None,
    mode: str,
    *,
    incoming_file_count: int = 0,
    supplier_search_count: int = 1,
) -> str:
    if not client:
        return "Доступ не подключён. Отправьте администратору ваш Telegram ID через команду /id."
    if not client.is_active:
        return "Доступ отключён. Свяжитесь с администратором."
    access_until = parse_access_until(client.access_until)
    if access_until and access_until < now_utc():
        return "Срок доступа истёк. Свяжитесь с администратором."
    if mode == MODE_PROCUREMENT_REPORT and not client.allowed_procurement_report:
        return "Функция анализа документации пока не включена для вашего доступа."
    if mode == MODE_SUPPLIER_SEARCH and not client.allowed_supplier_search:
        return "Функция поиска поставщиков не включена для вашего доступа."
    if mode == MODE_ANALYSIS_AND_SUPPLIERS:
        if not client.allowed_procurement_report:
            return "Функция анализа документации пока не включена для вашего доступа."
        if not client.allowed_supplier_search:
            return "Функция поиска поставщиков не включена для вашего доступа."
    if mode not in {MODE_SUPPLIER_SEARCH, MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS}:
        return "Неизвестный режим обработки."
    supplier_units, report_units = requested_function_units(mode, supplier_search_count=supplier_search_count)
    if client.is_trial and mode == MODE_ANALYSIS_AND_SUPPLIERS:
        return "В бесплатном доступе режим «Анализ + поставщики» недоступен. Запустите анализ и поиск поставщиков отдельно."
    if client.is_trial and mode == MODE_SUPPLIER_SEARCH and supplier_units > 1:
        return "В бесплатном доступе массовая обработка ТЗ недоступна. Отправьте одно ТЗ за один запуск."

    supplier_used, report_used, _file_count = current_function_usage(db, client)
    if supplier_units and client.monthly_supplier_search_limit >= 0:
        projected_supplier = supplier_used + supplier_units
        if projected_supplier > client.monthly_supplier_search_limit:
            return f"Месячный лимит поиска поставщиков исчерпан: {supplier_used}/{client.monthly_supplier_search_limit}."
    if report_units and client.monthly_procurement_report_limit >= 0:
        projected_reports = report_used + report_units
        if projected_reports > client.monthly_procurement_report_limit:
            return f"Месячный лимит анализа документации исчерпан: {report_used}/{client.monthly_procurement_report_limit}."
    return ""
