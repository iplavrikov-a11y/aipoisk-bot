from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
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


engine = create_engine(
    _database_url(),
    connect_args={"check_same_thread": False} if _database_url().startswith("sqlite") else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema()
    _ensure_legacy_client_accounts()


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
        "trial_supplier_search_limit": "INTEGER DEFAULT 0",
        "trial_procurement_report_limit": "INTEGER DEFAULT 0",
        "trial_file_limit": "INTEGER DEFAULT 10",
        "bot_telegram": "VARCHAR(255) DEFAULT '@tenderlex_bot'",
        "contact_email": "VARCHAR(255) DEFAULT ''",
        "contact_telegram": "VARCHAR(255) DEFAULT ''",
        "contact_website": "VARCHAR(255) DEFAULT ''",
        "payment_instructions": "TEXT DEFAULT ''",
    }
    clients_existing = _existing_columns(inspector, "clients")
    client_additions = {
        "is_trial": "BOOLEAN DEFAULT 0",
        "monthly_supplier_search_limit": "INTEGER DEFAULT 100",
        "monthly_procurement_report_limit": "INTEGER DEFAULT 100",
    }
    jobs_existing = _existing_columns(inspector, "jobs")
    job_additions = {
        "created_by_telegram_id": "VARCHAR(64) DEFAULT ''",
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
        for column, definition in supplier_results_additions.items():
            if column not in supplier_results_existing:
                connection.execute(text(f"ALTER TABLE supplier_results ADD COLUMN {column} {definition}"))


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
            if not telegram_id:
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


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
