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
        for column, definition in supplier_results_additions.items():
            if column not in supplier_results_existing:
                connection.execute(text(f"ALTER TABLE supplier_results ADD COLUMN {column} {definition}"))


def _existing_columns(inspector, table_name: str) -> set[str]:
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
