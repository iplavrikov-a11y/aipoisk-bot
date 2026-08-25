from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import config


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    url = config.database_url
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        sqlite_path = Path(url.removeprefix("sqlite:///"))
        if not sqlite_path.is_absolute():
            sqlite_path = (Path(__file__).resolve().parents[1] / sqlite_path).resolve()
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{sqlite_path}"
    return url


DATABASE_URL = _database_url()
SQLITE_BUSY_TIMEOUT_MS = 30000


def _sqlite_connect_args(database_url: str) -> dict:
    if not database_url.startswith("sqlite"):
        return {}
    return {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000}


def _configure_sqlite_connection(dbapi_connection) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


engine = create_engine(
    DATABASE_URL,
    connect_args=_sqlite_connect_args(DATABASE_URL),
    pool_pre_ping=True,
)

if DATABASE_URL.startswith("sqlite"):
    event.listen(engine, "connect", lambda dbapi_connection, _connection_record: _configure_sqlite_connection(dbapi_connection))

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from . import models  # noqa: F401
    from . import outreach_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema()
    _ensure_legacy_client_accounts()
    _ensure_default_tariffs()


def _ensure_schema() -> None:
    inspector = inspect(engine)
    if "job_sources" in Base.metadata.tables:
        Base.metadata.tables["job_sources"].create(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    system_settings_existing = _existing_columns(inspector, "system_settings")
    system_settings_additions = {
        "document_settings_json": "TEXT DEFAULT '{}'",
        "supplier_search_provider_order": "VARCHAR(255) DEFAULT 'yandex,google,tavily,ddgs'",
        "yandex_search_folder_id": "VARCHAR(255) DEFAULT ''",
        "yandex_search_api_key": "TEXT DEFAULT ''",
        "google_search_api_key": "TEXT DEFAULT ''",
        "google_search_cse_id": "VARCHAR(255) DEFAULT ''",
        "trial_enabled": "BOOLEAN DEFAULT 0",
        "trial_supplier_search_limit": "INTEGER DEFAULT 2",
        "trial_procurement_report_limit": "INTEGER DEFAULT 2",
        "trial_file_limit": "INTEGER DEFAULT 10",
        "onboarding_reminders_enabled": "BOOLEAN DEFAULT 0",
        "onboarding_reminders_rollout_at": "VARCHAR(40) DEFAULT ''",
        "bot_telegram": "VARCHAR(255) DEFAULT '@tenderlex_bot'",
        "contact_email": "VARCHAR(255) DEFAULT ''",
        "contact_telegram": "VARCHAR(255) DEFAULT ''",
        "contact_max": "VARCHAR(255) DEFAULT ''",
        "contact_max_link": "VARCHAR(255) DEFAULT ''",
        "contact_website": "VARCHAR(255) DEFAULT ''",
        "payment_instructions": "TEXT DEFAULT ''",
        "payment_provider": "VARCHAR(40) DEFAULT 'manual'",
        "yookassa_shop_id": "VARCHAR(255) DEFAULT ''",
        "yookassa_secret_key": "TEXT DEFAULT ''",
        "yookassa_return_url": "VARCHAR(255) DEFAULT ''",
        "supplier_ai_provider": "VARCHAR(80) DEFAULT ''",
        "supplier_ai_model": "VARCHAR(160) DEFAULT ''",
        "ai_analysis_fallback_json": "TEXT DEFAULT '[]'",
        "ai_supplier_fallback_json": "TEXT DEFAULT '[]'",
    }
    clients_existing = _existing_columns(inspector, "clients")
    client_additions = {
        "is_trial": "BOOLEAN DEFAULT 0",
        "monthly_supplier_search_limit": "INTEGER DEFAULT 100",
        "monthly_procurement_report_limit": "INTEGER DEFAULT 100",
        "money_balance_kopeks": "INTEGER DEFAULT 0",
        "money_reserved_kopeks": "INTEGER DEFAULT 0",
        "supplier_target_min": "INTEGER DEFAULT 0",
        "yandex_search_price_per_request": "REAL DEFAULT 0.04",
        "marketing_unsubscribed": "BOOLEAN DEFAULT 0",
    }
    jobs_existing = _existing_columns(inspector, "jobs")
    job_additions = {
        "created_by_telegram_id": "VARCHAR(64) DEFAULT ''",
        "supplier_search_policy": "VARCHAR(40) DEFAULT 'normal'",
        "supplier_search_run_type": "VARCHAR(40) DEFAULT 'initial'",
        "confirmation_kind": "VARCHAR(40) DEFAULT ''",
        "confirmation_outcome": "VARCHAR(40) DEFAULT ''",
        "confirmation_offered_at": "DATETIME NULL",
        "confirmation_expires_at": "DATETIME NULL",
        "confirmation_decided_at": "DATETIME NULL",
        "delivery_expires_at": "DATETIME NULL",
        "offer_delivery_outcome": "VARCHAR(40) DEFAULT ''",
        "offer_delivery_claim_token": "VARCHAR(64) DEFAULT ''",
        "offer_delivery_lease_expires_at": "DATETIME NULL",
        "offer_delivered_at": "DATETIME NULL",
        "offer_delivery_expired_at": "DATETIME NULL",
        "active_output_manifest": "VARCHAR(40) DEFAULT ''",
        "active_output_manifest_version": "INTEGER DEFAULT 0",
        "active_entitlements_json": "TEXT DEFAULT '[]'",
        "yandex_requests_count": "INTEGER DEFAULT 0",
        "yandex_cost_rub": "REAL DEFAULT 0.0",
        "ai_provider": "VARCHAR(80) DEFAULT ''",
        "ai_model": "VARCHAR(160) DEFAULT ''",
    }
    billing_transactions_existing = _existing_columns(inspector, "billing_transactions")
    client_tariff_overrides_existing = _existing_columns(inspector, "client_tariff_overrides")
    billing_transaction_additions = {
        "amount_kopeks": "INTEGER DEFAULT 0",
        "balance_after_kopeks": "INTEGER DEFAULT 0",
        "reserved_after_kopeks": "INTEGER DEFAULT 0",
        "idempotency_key": "VARCHAR(80) NULL",
    }
    web_users_existing = _existing_columns(inspector, "web_users")
    web_user_additions = {
        "is_email_verified": "BOOLEAN DEFAULT 1",
        "marketing_unsubscribed": "BOOLEAN DEFAULT 0",
        "yandex_id": "VARCHAR(64) NULL",
    }
    onboarding_reminders_existing = _existing_columns(inspector, "onboarding_reminders")
    onboarding_reminder_additions = {
        "step": "VARCHAR(40) DEFAULT 'step1'",
    }
    supplier_results_existing = _existing_columns(inspector, "supplier_results")
    supplier_results_additions = {
        "match_level": "VARCHAR(40) DEFAULT ''",
        "source": "VARCHAR(40) DEFAULT ''",
        "search_query": "TEXT DEFAULT ''",
        "quality_score": "INTEGER DEFAULT 0",
        "quality_tier": "VARCHAR(40) DEFAULT ''",
        "procurement_item_id": "VARCHAR(80) DEFAULT ''",
        "procurement_item": "TEXT DEFAULT ''",
        "ai_confidence": "INTEGER DEFAULT 0",
        "site_type": "VARCHAR(80) DEFAULT ''",
        "product_fit": "VARCHAR(80) DEFAULT ''",
        "evidence_snippet": "TEXT DEFAULT ''",
        "contact_evidence_snippet": "TEXT DEFAULT ''",
        "ai_rank_confidence": "INTEGER DEFAULT 0",
        "ai_rank_reason": "TEXT DEFAULT ''",
    }
    outreach_leads_existing = _existing_columns(inspector, "outreach_leads")
    outreach_leads_additions = {
        "task_id": "VARCHAR(32) DEFAULT ''",
        "activity_profile": "VARCHAR(255) DEFAULT ''",
        "relevance_score": "INTEGER DEFAULT 100",
    }
    outreach_campaigns_existing = _existing_columns(inspector, "outreach_campaigns")
    outreach_campaigns_additions = {
        "task_id_filter": "VARCHAR(32) DEFAULT ''",
        "selected_lead_ids": "TEXT DEFAULT ''",
    }
    outreach_inbox_existing = _existing_columns(inspector, "outreach_inbox")
    outreach_inbox_additions = {
        "category": "VARCHAR(100) DEFAULT ''",
        "is_spam": "BOOLEAN DEFAULT 0",
    }
    with engine.begin() as connection:
        for column, definition in system_settings_additions.items():
            if column not in system_settings_existing:
                connection.execute(text(f"ALTER TABLE system_settings ADD COLUMN {column} {definition}"))
        if "supplier_search_provider_order" in system_settings_existing:
            connection.execute(
                text(
                    """
                    UPDATE system_settings
                    SET supplier_search_provider_order = 'yandex,google,tavily,ddgs'
                    WHERE supplier_search_provider_order IS NULL
                       OR TRIM(supplier_search_provider_order) = ''
                       OR supplier_search_provider_order = 'tavily,ddgs'
                    """
                )
            )
        if (
            "supplier_ai_provider" not in system_settings_existing
            and "supplier_ai_model" not in system_settings_existing
            and "light_provider" in system_settings_existing
            and "light_model" in system_settings_existing
        ):
            connection.execute(
                text(
                    """
                    UPDATE system_settings
                    SET supplier_ai_provider = COALESCE(light_provider, ''),
                        supplier_ai_model = COALESCE(light_model, '')
                    WHERE (supplier_ai_provider IS NULL OR TRIM(supplier_ai_provider) = '')
                      AND (supplier_ai_model IS NULL OR TRIM(supplier_ai_model) = '')
                    """
                )
            )
        added_client_columns: set[str] = set()
        for column, definition in client_additions.items():
            if column not in clients_existing:
                connection.execute(text(f"ALTER TABLE clients ADD COLUMN {column} {definition}"))
                added_client_columns.add(column)
        if "monthly_supplier_search_limit" in added_client_columns and "monthly_job_limit" in clients_existing:
            connection.execute(text("UPDATE clients SET monthly_supplier_search_limit = monthly_job_limit"))
        if "monthly_procurement_report_limit" in added_client_columns and "monthly_job_limit" in clients_existing:
            connection.execute(text("UPDATE clients SET monthly_procurement_report_limit = monthly_job_limit"))
        for column, definition in job_additions.items():
            if column not in jobs_existing:
                connection.execute(text(f"ALTER TABLE jobs ADD COLUMN {column} {definition}"))
        for column, definition in billing_transaction_additions.items():
            if billing_transactions_existing and column not in billing_transactions_existing:
                connection.execute(text(f"ALTER TABLE billing_transactions ADD COLUMN {column} {definition}"))
        if billing_transactions_existing:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_transactions_idempotency_key "
                    "ON billing_transactions(idempotency_key) WHERE idempotency_key IS NOT NULL"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_transaction_job_kind_operation "
                    "ON billing_transactions(job_id, kind, operation) WHERE job_id IS NOT NULL"
                )
            )
        if client_tariff_overrides_existing:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_client_tariff_override_client_kind "
                    "ON client_tariff_overrides(client_id, kind)"
                )
            )
        for column, definition in web_user_additions.items():
            if web_users_existing and column not in web_users_existing:
                connection.execute(text(f"ALTER TABLE web_users ADD COLUMN {column} {definition}"))
        if web_users_existing:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_web_users_yandex_id "
                    "ON web_users(yandex_id) WHERE yandex_id IS NOT NULL"
                )
            )
        for column, definition in onboarding_reminder_additions.items():
            if onboarding_reminders_existing and column not in onboarding_reminders_existing:
                connection.execute(text(f"ALTER TABLE onboarding_reminders ADD COLUMN {column} {definition}"))
        for column, definition in supplier_results_additions.items():
            if column not in supplier_results_existing:
                connection.execute(text(f"ALTER TABLE supplier_results ADD COLUMN {column} {definition}"))
        for column, definition in outreach_leads_additions.items():
            if outreach_leads_existing and column not in outreach_leads_existing:
                connection.execute(text(f"ALTER TABLE outreach_leads ADD COLUMN {column} {definition}"))
        for column, definition in outreach_campaigns_additions.items():
            if outreach_campaigns_existing and column not in outreach_campaigns_existing:
                connection.execute(text(f"ALTER TABLE outreach_campaigns ADD COLUMN {column} {definition}"))
        for column, definition in outreach_inbox_additions.items():
            if outreach_inbox_existing and column not in outreach_inbox_existing:
                connection.execute(text(f"ALTER TABLE outreach_inbox ADD COLUMN {column} {definition}"))


def _existing_columns(inspector, table_name: str) -> set[str]:
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _ensure_legacy_client_accounts() -> None:
    from .models import Client, ClientTelegramAccount

    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        clients = db.query(Client).all()
        changed = False
        for client in clients:
            telegram_id = str(client.telegram_id or "").strip()
            if not telegram_id or telegram_id.startswith(("web:", "pending:")):
                continue
            existing = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.telegram_id == telegram_id).first()
            if existing:
                continue
            db.add(
                ClientTelegramAccount(
                    client_id=client.id,
                    telegram_id=telegram_id,
                    username=client.username,
                    name=client.name,
                    is_active=True,
                    notes="Migrated from clients.telegram_id",
                )
            )
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _ensure_default_tariffs() -> None:
    from .models import TariffPackage

    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        has_tariffs = db.query(TariffPackage).filter(TariffPackage.kind == "supplier_search").first()
        if has_tariffs:
            extra_exists = db.query(TariffPackage).filter(TariffPackage.kind == "supplier_search_extra").first()
            if not extra_exists:
                db.add(
                    TariffPackage(
                        kind="supplier_search_extra",
                        name="1 добор поставщиков (по тому же ТЗ)",
                        units=1,
                        price_kopeks=4900,
                        sort_order=10,
                        is_active=True,
                    )
                )
                db.commit()
    finally:
        db.close()


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
