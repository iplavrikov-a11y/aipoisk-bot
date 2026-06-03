from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import config
from .models import Client, Job, SystemSettings, now_utc

MODE_SUPPLIER_SEARCH = "supplier_search"
MODE_PROCUREMENT_REPORT = "procurement_report"
MODE_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"


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
    existing = db.query(Client).filter(Client.telegram_id == telegram_id).first()
    if existing:
        return
    db.add(
        Client(
            telegram_id=telegram_id,
            name="Owner",
            username="",
            is_active=True,
            allowed_supplier_search=True,
            allowed_procurement_report=True,
            monthly_job_limit=10000,
            monthly_file_limit=10000,
            notes="Seeded from AIPOISK_OWNER_TELEGRAM_ID",
        )
    )
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


def client_access_error(
    db: Session,
    client: Client | None,
    mode: str,
    *,
    incoming_file_count: int = 0,
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

    job_count, file_count = current_month_usage(db, client)
    if client.monthly_job_limit >= 0 and job_count >= client.monthly_job_limit:
        return f"Месячный лимит задач исчерпан: {job_count}/{client.monthly_job_limit}."
    projected_files = file_count + max(0, incoming_file_count)
    if client.monthly_file_limit >= 0 and projected_files > client.monthly_file_limit:
        return f"Месячный лимит файлов исчерпан: {file_count}/{client.monthly_file_limit}."
    return ""
