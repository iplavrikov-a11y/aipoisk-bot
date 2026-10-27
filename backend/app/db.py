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
    with engine.begin() as connection:
        if "job_sources" in Base.metadata.tables:
            Base.metadata.tables["job_sources"].create(bind=connection, checkfirst=True)
        if "web_password_reset_tokens" in Base.metadata.tables:
            Base.metadata.tables["web_password_reset_tokens"].create(bind=connection, checkfirst=True)
        if "invoices" in Base.metadata.tables:
            Base.metadata.tables["invoices"].create(bind=connection, checkfirst=True)
        inspector = inspect(connection)
        system_settings_existing = _existing_columns(inspector, "system_settings")
        system_settings_additions = {
            "document_settings_json": "TEXT DEFAULT '{}'",
            "supplier_search_provider_order": "VARCHAR(255) DEFAULT 'yandex'",
            "yandex_search_folder_id": "VARCHAR(255) DEFAULT ''",
            "yandex_search_api_key": "TEXT DEFAULT ''",
            "google_search_api_key": "TEXT DEFAULT ''",
            "google_search_cse_id": "VARCHAR(255) DEFAULT ''",
            "trial_enabled": "BOOLEAN DEFAULT 0",
            "trial_supplier_search_limit": "INTEGER DEFAULT 2",
            "trial_procurement_report_limit": "INTEGER DEFAULT 2",
            "trial_file_limit": "INTEGER DEFAULT 10",
            "trial_balance_rub": "INTEGER DEFAULT 495",
            "onboarding_reminders_enabled": "BOOLEAN DEFAULT 0",
            "onboarding_reminders_rollout_at": "VARCHAR(40) DEFAULT ''",
            "reengagement_reminders_enabled": "BOOLEAN DEFAULT 0",
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
            "price_monitoring_default_price_kopeks": "INTEGER DEFAULT 5000",
            "price_monitoring_max_suppliers": "INTEGER DEFAULT 3",
            "price_monitoring_max_positions": "INTEGER DEFAULT 1000",
            "price_monitoring_concurrency": "INTEGER DEFAULT 4",
            "price_monitoring_cluster_ratio": "REAL DEFAULT 1.4",
            "price_monitoring_filter_marketplaces": "BOOLEAN DEFAULT 1",
            "price_monitoring_filter_foreign": "BOOLEAN DEFAULT 1",
            "price_monitoring_max_variation_pct": "REAL DEFAULT 33.0",
            "geo_radius_search_enabled_global": "BOOLEAN DEFAULT 0",
            "geo_radius_surcharge_pct": "REAL DEFAULT 30.0",
        }
        clients_existing = _existing_columns(inspector, "clients")
        client_additions = {
            "is_active": "BOOLEAN DEFAULT 1",
            "is_trial": "BOOLEAN DEFAULT 0",
            "access_until": "VARCHAR(32) DEFAULT ''",
            "allowed_supplier_search": "BOOLEAN DEFAULT 1",
            "allowed_procurement_report": "BOOLEAN DEFAULT 0",
            "allowed_exact_product": "BOOLEAN DEFAULT 1",
            "allowed_price_monitoring": "BOOLEAN DEFAULT 0",
            "allowed_geo_radius": "BOOLEAN DEFAULT 0",
            "monthly_supplier_search_limit": "INTEGER DEFAULT 100",
            "monthly_procurement_report_limit": "INTEGER DEFAULT 100",
            "money_balance_kopeks": "INTEGER DEFAULT 0",
            "money_reserved_kopeks": "INTEGER DEFAULT 0",
            "supplier_target_min": "INTEGER DEFAULT 0",
            "custom_exclude_marketplaces": "BOOLEAN NULL",
            "custom_exclude_foreign": "BOOLEAN NULL",
            "custom_max_suppliers": "INTEGER NULL",
            "custom_max_variation_pct": "REAL NULL",
            "yandex_search_price_per_request": "REAL DEFAULT 0.04",
            "marketing_unsubscribed": "BOOLEAN DEFAULT 0",
            "referrer_id": "VARCHAR(32) NULL",
            "referral_reward_granted": "BOOLEAN DEFAULT 0",
            "referral_code": "VARCHAR(32) DEFAULT ''",
            "registration_ip": "VARCHAR(64) DEFAULT ''",
            "client_number": "INTEGER NULL",
        }
        jobs_existing = _existing_columns(inspector, "jobs")
        job_additions = {
            "created_by_telegram_id": "VARCHAR(64) DEFAULT ''",
            "supplier_search_policy": "VARCHAR(40) DEFAULT 'normal'",
            "supplier_search_run_type": "VARCHAR(40) DEFAULT 'initial'",
            "multi_item_mode": "VARCHAR(40) DEFAULT 'balanced'",
            "delivery_city": "VARCHAR(255) DEFAULT ''",
            "geo_radius_km": "INTEGER NULL",
            "position_selection_json": "TEXT DEFAULT ''",
            "filter_marketplaces": "BOOLEAN NULL",
            "filter_foreign": "BOOLEAN NULL",
            "max_suppliers": "INTEGER NULL",
            "max_variation_pct": "REAL NULL",
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
            "admin_comment": "TEXT DEFAULT ''",
            "admin_supplement_path": "TEXT DEFAULT ''",
            "admin_supplement_name": "TEXT DEFAULT ''",
            "admin_supplement_at": "DATETIME NULL",
            "parent_job_id": "VARCHAR(32) DEFAULT ''",
            "is_admin_rerun": "BOOLEAN DEFAULT 0",
            "job_number": "INTEGER NULL",
            "geo_scope": "VARCHAR(32) DEFAULT 'ru'",
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
            "supplier_city": "VARCHAR(255) DEFAULT ''",
            "supplier_distance_km": "INTEGER NULL",
        }
        outreach_leads_existing = _existing_columns(inspector, "outreach_leads")
        outreach_leads_additions = {
            "task_id": "VARCHAR(32) DEFAULT ''",
            "wave_index": "INTEGER DEFAULT 1",
            "activity_profile": "VARCHAR(255) DEFAULT ''",
            "relevance_score": "INTEGER DEFAULT 100",
        }
        outreach_search_tasks_existing = _existing_columns(inspector, "outreach_search_tasks")
        outreach_search_tasks_additions = {
            "waves_json": "TEXT DEFAULT '[]'",
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
        added_settings_columns: set[str] = set()
        for column, definition in system_settings_additions.items():
            if column not in system_settings_existing:
                connection.execute(text(f"ALTER TABLE system_settings ADD COLUMN {column} {definition}"))
                added_settings_columns.add(column)
        if "supplier_search_provider_order" in system_settings_existing:
            connection.execute(
                text(
                    """
                    UPDATE system_settings
                    SET supplier_search_provider_order = 'yandex'
                    WHERE supplier_search_provider_order IS NULL
                       OR TRIM(supplier_search_provider_order) = ''
                       OR supplier_search_provider_order LIKE '%tavily%'
                       OR supplier_search_provider_order LIKE '%ddgs%'
                    """
                )
            )
        if "supplier_ai_provider" in added_settings_columns and "light_provider" in system_settings_existing:
            connection.execute(
                text(
                    """
                    UPDATE system_settings
                    SET supplier_ai_provider = light_provider
                    WHERE light_provider IS NOT NULL AND TRIM(light_provider) != ''
                    """
                )
            )
        if "supplier_ai_model" in added_settings_columns and "light_model" in system_settings_existing:
            connection.execute(
                text(
                    """
                    UPDATE system_settings
                    SET supplier_ai_model = light_model
                    WHERE light_model IS NOT NULL AND TRIM(light_model) != ''
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
        if "created_at" in clients_existing or "created_at" in added_client_columns:
            connection.execute(
                text(
                    "UPDATE clients SET client_number = ("
                    "SELECT COUNT(*) FROM clients c2 WHERE c2.created_at <= clients.created_at"
                    ") WHERE client_number IS NULL"
                )
            )
        else:
            connection.execute(text("UPDATE clients SET client_number = rowid WHERE client_number IS NULL"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_client_number "
                "ON clients(client_number) WHERE client_number IS NOT NULL"
            )
        )
        connection.execute(
            text(
                """
            CREATE TRIGGER IF NOT EXISTS trg_clients_assign_number
            AFTER INSERT ON clients
            WHEN NEW.client_number IS NULL
            BEGIN
                UPDATE clients
                SET client_number = (SELECT COALESCE(MAX(client_number), 0) + 1 FROM clients)
                WHERE id = NEW.id;
            END;
        """
            )
        )
        for column, definition in job_additions.items():
            if column not in jobs_existing:
                connection.execute(text(f"ALTER TABLE jobs ADD COLUMN {column} {definition}"))
        connection.execute(text("UPDATE jobs SET job_number = rowid WHERE job_number IS NULL"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_job_number ON jobs(job_number) WHERE job_number IS NOT NULL"))
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_jobs_assign_number
            AFTER INSERT ON jobs
            WHEN NEW.job_number IS NULL
            BEGIN
                UPDATE jobs
                SET job_number = (SELECT COALESCE(MAX(job_number), 0) + 1 FROM jobs)
                WHERE id = NEW.id;
            END;
        """))
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
        for column, definition in outreach_search_tasks_additions.items():
            if outreach_search_tasks_existing and column not in outreach_search_tasks_existing:
                connection.execute(text(f"ALTER TABLE outreach_search_tasks ADD COLUMN {column} {definition}"))
        for column, definition in outreach_campaigns_additions.items():
            if outreach_campaigns_existing and column not in outreach_campaigns_existing:
                connection.execute(text(f"ALTER TABLE outreach_campaigns ADD COLUMN {column} {definition}"))
        for column, definition in outreach_inbox_additions.items():
            if outreach_inbox_existing and column not in outreach_inbox_existing:
                connection.execute(text(f"ALTER TABLE outreach_inbox ADD COLUMN {column} {definition}"))
        outreach_settings_existing = _existing_columns(inspector, "outreach_settings")
        outreach_settings_additions = {
            "spam_rules_json": "TEXT DEFAULT '[]'",
        }
        for column, definition in outreach_settings_additions.items():
            if outreach_settings_existing and column not in outreach_settings_existing:
                connection.execute(text(f"ALTER TABLE outreach_settings ADD COLUMN {column} {definition}"))
        api_keys_existing = _existing_columns(inspector, "api_keys")
        api_keys_additions = {
            "secret_token": "VARCHAR(120) NULL",
            "reserved_supplier_search": "INTEGER DEFAULT 0",
            "reserved_exact_product": "INTEGER DEFAULT 0",
            "reserved_procurement_report": "INTEGER DEFAULT 0",
            "allowed_price_monitoring": "BOOLEAN DEFAULT 0",
            "quota_price_monitoring": "INTEGER DEFAULT 0",
            "spent_price_monitoring": "INTEGER DEFAULT 0",
            "reserved_price_monitoring": "INTEGER DEFAULT 0",
        }
        for column, definition in api_keys_additions.items():
            if api_keys_existing and column not in api_keys_existing:
                connection.execute(text(f"ALTER TABLE api_keys ADD COLUMN {column} {definition}"))
        # Hashes are sufficient for authentication.  Remove legacy plaintext
        # secrets without rotating or invalidating existing API keys.
        if api_keys_existing and "secret_token" in api_keys_existing:
            connection.execute(text("UPDATE api_keys SET secret_token = NULL WHERE secret_token IS NOT NULL"))
        api_operations_existing = _existing_columns(inspector, "api_operations")
        if api_operations_existing and "job_ids_json" not in api_operations_existing:
            connection.execute(text("ALTER TABLE api_operations ADD COLUMN job_ids_json TEXT DEFAULT '[]'"))
        tariff_packages_existing = _existing_columns(inspector, "tariff_packages")
        tariff_package_additions = {
            "bonus_kopeks": "INTEGER DEFAULT 0",
            "badge": "VARCHAR(40) DEFAULT ''",
        }
        for column, definition in tariff_package_additions.items():
            if tariff_packages_existing and column not in tariff_packages_existing:
                connection.execute(text(f"ALTER TABLE tariff_packages ADD COLUMN {column} {definition}"))


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
        if not has_tariffs:
            default_packages = [
                ("supplier_search", "1 поиск поставщиков", 1, 9900, 1),
                ("supplier_search", "5 поисков поставщиков", 5, 49000, 2),
                ("supplier_search", "10 поисков поставщиков", 10, 89000, 3),
                ("supplier_search", "25 поисков поставщиков", 25, 199000, 4),
                ("supplier_search", "50 поисков поставщиков", 50, 379000, 5),
                ("procurement_report", "1 анализ документации", 1, 14900, 1),
                ("procurement_report", "5 анализов документации", 5, 69000, 2),
                ("procurement_report", "10 анализов документации", 10, 129000, 3),
                ("procurement_report", "25 анализов документации", 25, 299000, 4),
                ("procurement_report", "50 анализов документации", 50, 549000, 5),
            ]
            for kind, name, units, price, order in default_packages:
                db.add(
                    TariffPackage(
                        kind=kind,
                        name=name,
                        units=units,
                        price_kopeks=price,
                        sort_order=order,
                        is_active=True,
                    )
                )
            db.commit()

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

        exact_product_exists = db.query(TariffPackage).filter(TariffPackage.kind == "exact_product").first()
        if not exact_product_exists:
            exact_defaults = [
                ("1 подбор товара и аналогов", 1, 9900, 1),
                ("5 подборов товара и аналогов", 5, 49000, 2),
                ("10 подборов товара и аналогов", 10, 89000, 3),
                ("25 подборов товара и аналогов", 25, 199000, 4),
                ("50 подборов товара и аналогов", 50, 379000, 5),
            ]
            for name, units, price, order in exact_defaults:
                db.add(
                    TariffPackage(
                        kind="exact_product",
                        name=name,
                        units=units,
                        price_kopeks=price,
                        sort_order=order,
                        is_active=True,
                    )
                )
            db.commit()

        deposit_exists = db.query(TariffPackage).filter(TariffPackage.kind == "deposit").first()
        if not deposit_exists:
            deposit_defaults = [
                ("Старт", 10, 100000, 0, "", "Для разовых процедур и тестирования в бою", 10),
                ("Оптимальный", 35, 300000, 50000, "", "Для регулярной работы специалиста", 20),
                ("Про", 65, 500000, 150000, "Хит", "Для активного отдела закупок (несколько тендеров в неделю)", 30),
                ("Бизнес", 140, 1000000, 400000, "", "Для дистрибьюторов, интеграторов и работы по API", 40),
                ("Корпоративный", 375, 2500000, 1250000, "Максимум", "Для масштабных процедур и CRM-интеграций", 50),
            ]
            for name, units, price, bonus, badge, desc, order in deposit_defaults:
                db.add(
                    TariffPackage(
                        kind="deposit",
                        name=name,
                        units=units,
                        price_kopeks=price,
                        bonus_kopeks=bonus,
                        badge=badge,
                        description=desc,
                        sort_order=order,
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
