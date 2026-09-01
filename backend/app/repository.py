from __future__ import annotations

from datetime import datetime, timezone
import re

from sqlalchemy import func, not_, or_
from sqlalchemy.orm import Session

from .billing import OP_GRANT, access_error_for_units, client_uses_trial_access, grant_trial_balance, resolve_requested_billing_kinds
from .config import config
from .models import DEFAULT_PAYMENT_INSTRUCTIONS, BillingTransaction, Client, ClientTelegramAccount, Job, SystemSettings, new_id, now_utc

MODE_SUPPLIER_SEARCH = "supplier_search"
MODE_PROCUREMENT_REPORT = "procurement_report"
MODE_ANALYSIS_AND_SUPPLIERS = "analysis_and_suppliers"
MODE_EXACT_PRODUCT = "exact_product"
DEFAULT_SUPPLIER_TARGET = 50
MAX_SUPPLIER_TARGET = 100
INTERNAL_JOB_PATTERN = re.compile(
    r"(smoke|retest|patch2?|remain|pusher|ai_required|live_|worker_smoke)",
    re.IGNORECASE,
)
PENDING_TELEGRAM_ID_PREFIX = "pending:"


def normalize_telegram_username(value: str) -> str:
    return str(value or "").strip().lstrip("@").lower()


def is_pending_telegram_id(value: str) -> bool:
    return str(value or "").startswith(PENDING_TELEGRAM_ID_PREFIX)


def new_pending_telegram_id() -> str:
    return f"{PENDING_TELEGRAM_ID_PREFIX}{new_id()}"


def get_or_create_settings(db: Session) -> SystemSettings:
    settings = db.get(SystemSettings, 1)
    if settings:
        if not str(settings.payment_instructions or "").strip():
            settings.payment_instructions = DEFAULT_PAYMENT_INSTRUCTIONS
            db.commit()
            db.refresh(settings)
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
        supplier_ai_provider=config.default_supplier_ai_provider or config.default_light_provider,
        supplier_ai_model=config.default_supplier_ai_model or config.default_light_model,
        supplier_search_adapter_base_url=config.default_supplier_search_adapter_base_url,
        supplier_search_adapter_api_key=config.default_supplier_search_adapter_api_key,
        supplier_search_adapter_model=config.default_supplier_search_adapter_model,
        supplier_search_provider_order=config.default_supplier_search_provider_order,
        yandex_search_folder_id=config.default_yandex_search_folder_id,
        yandex_search_api_key=config.default_yandex_search_api_key,
        google_search_api_key=config.default_google_search_api_key,
        google_search_cse_id=config.default_google_search_cse_id,
        document_settings_json=config.default_document_settings_json,
        payment_instructions=DEFAULT_PAYMENT_INSTRUCTIONS,
        trial_enabled=True,
        trial_supplier_search_limit=2,
        trial_procurement_report_limit=2,
        trial_file_limit=10,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def supplier_target_for_client(settings: SystemSettings, client: Client | None) -> int:
    client_target = int(getattr(client, "supplier_target_min", 0) or 0)
    configured_target = client_target if client_target > 0 else int(getattr(settings, "default_supplier_target", 0) or DEFAULT_SUPPLIER_TARGET)
    return max(1, min(MAX_SUPPLIER_TARGET, configured_target))


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
    clean_username = normalize_telegram_username(username)
    clean_name = str(name or "").strip()
    if existing:
        if clean_username and not existing.username:
            existing.username = clean_username
        if clean_name and (not existing.name or existing.name.startswith("Trial ") or existing.name == "Без имени"):
            existing.name = clean_name
        if clean_username and not client.username:
            client.username = clean_username
        if clean_name and (not client.name or client.name.startswith("Trial ") or client.name == "Без имени"):
            client.name = clean_name
        return existing
    account = ClientTelegramAccount(
        client_id=client.id,
        telegram_id=normalized,
        username=clean_username or client.username,
        name=clean_name or client.name,
        is_active=True,
        notes=notes,
    )
    db.add(account)
    return account


def find_client_telegram_account_by_username(db: Session, username: str) -> ClientTelegramAccount | None:
    normalized = normalize_telegram_username(username)
    if not normalized:
        return None
    return (
        db.query(ClientTelegramAccount)
        .filter(func.lower(ClientTelegramAccount.username) == normalized)
        .order_by(ClientTelegramAccount.created_at.asc())
        .first()
    )


def ensure_pending_client_telegram_account(
    db: Session,
    client: Client,
    username: str,
    *,
    name: str = "",
    notes: str = "",
) -> ClientTelegramAccount:
    normalized_username = normalize_telegram_username(username)
    if not normalized_username:
        raise ValueError("telegram username is required")
    existing = find_client_telegram_account_by_username(db, normalized_username)
    if existing:
        if existing.client_id != client.id:
            raise ValueError("telegram username is already linked to another client")
        return existing
    account = ClientTelegramAccount(
        client_id=client.id,
        telegram_id=new_pending_telegram_id(),
        username=normalized_username,
        name=name or client.name,
        is_active=True,
        notes=notes or "Ожидает первого входа в бот",
    )
    db.add(account)
    return account


def resolve_pending_telegram_account_by_username(
    db: Session,
    telegram_id: str,
    *,
    username: str = "",
    name: str = "",
) -> tuple[Client | None, str]:
    normalized_id = str(telegram_id or "").strip()
    normalized_username = normalize_telegram_username(username)
    if not normalized_id or not normalized_username:
        return None, ""
    account = (
        db.query(ClientTelegramAccount)
        .filter(func.lower(ClientTelegramAccount.username) == normalized_username)
        .filter(ClientTelegramAccount.telegram_id.like(f"{PENDING_TELEGRAM_ID_PREFIX}%"))
        .order_by(ClientTelegramAccount.created_at.asc())
        .first()
    )
    if not account:
        return None, ""
    existing_account = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == normalized_id).first()
    if existing_account and existing_account.id != account.id:
        return existing_account.client, "Этот Telegram ID уже привязан к другому доступу."
    existing_client = db.query(Client).filter(Client.telegram_id == normalized_id).first()
    if existing_client and existing_client.id != account.client_id:
        return existing_client, "Этот Telegram ID уже привязан к другому доступу."
    account.telegram_id = normalized_id
    account.username = normalized_username
    if name:
        account.name = name
    if account.notes == "Ожидает первого входа в бот":
        account.notes = ""
    client = account.client
    if is_pending_telegram_id(client.telegram_id) or not str(client.telegram_id or "").strip():
        client.telegram_id = normalized_id
    if not client.username:
        client.username = normalized_username
    if not client.name and name:
        client.name = name
    return client, ""


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
        if client and not account_error:
            ensure_client_telegram_account(db, client, telegram_id, username=username, name=name)
            ensure_unused_trial_balance(db, client)
            db.commit()
        return client, account_error
    pending_client, pending_error = resolve_pending_telegram_account_by_username(
        db,
        telegram_id,
        username=username,
        name=name,
    )
    if pending_client or pending_error:
        if pending_client and not pending_error:
            ensure_unused_trial_balance(db, pending_client)
        db.commit()
        if pending_client:
            db.refresh(pending_client)
        return pending_client, pending_error
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
    grant_trial_balance(
        db,
        client,
        supplier_search_units=settings.trial_supplier_search_limit,
        procurement_report_units=settings.trial_procurement_report_limit,
    )
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


def ensure_unused_trial_balance(db: Session, client: Client) -> bool:
    if not client_uses_trial_access(db, client):
        return False
    if db.query(Job.id).filter(Job.client_id == client.id).first():
        return False
    settings = get_or_create_settings(db)
    if not settings.trial_enabled:
        return False
    before_count = (
        db.query(BillingTransaction.id)
        .filter(BillingTransaction.client_id == client.id)
        .filter(BillingTransaction.operation == OP_GRANT)
        .count()
    )
    grant_trial_balance(
        db,
        client,
        supplier_search_units=settings.trial_supplier_search_limit,
        procurement_report_units=settings.trial_procurement_report_limit,
    )
    db.flush()
    after_count = (
        db.query(BillingTransaction.id)
        .filter(BillingTransaction.client_id == client.id)
        .filter(BillingTransaction.operation == OP_GRANT)
        .count()
    )
    if after_count <= before_count:
        return False
    db.commit()
    db.refresh(client)
    return True


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
    supplier_search_run_type: str = "initial",
) -> str:
    if not client:
        return "Доступ не подключён. Отправьте администратору ваш Telegram ID через команду /id."
    if not client.is_active:
        return "Доступ отключён. Свяжитесь с администратором."
    if mode not in {MODE_SUPPLIER_SEARCH, MODE_PROCUREMENT_REPORT, MODE_ANALYSIS_AND_SUPPLIERS, MODE_EXACT_PRODUCT}:
        return "Неизвестный режим обработки."
    supplier_units, report_units = requested_function_units(mode, supplier_search_count=supplier_search_count)
    uses_trial_access = client_uses_trial_access(db, client)
    if uses_trial_access and mode == MODE_SUPPLIER_SEARCH and supplier_units > 1:
        return "В бесплатном доступе массовая обработка ТЗ недоступна. Отправьте одно ТЗ за один запуск."

    return access_error_for_units(
        db,
        client,
        resolve_requested_billing_kinds(
            db,
            client,
            mode,
            supplier_search_count=supplier_search_count,
            supplier_search_run_type=supplier_search_run_type,
        ),
    )
