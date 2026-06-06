from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIPOISK_",
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    public_base_url: str = "https://tenderlex.ru"
    database_url: str = "sqlite:///../data/aipoisk.db"
    storage_dir: str = "../storage"
    admin_token: str = "change-me"
    admin_username: str = "admin"
    admin_password: str = ""
    admin_session_hours: int = 24
    bot_token: str = ""
    owner_telegram_id: str = ""
    default_custom_ai_providers_json: str = "[]"
    default_saved_models_json: str = "[]"
    default_ai_function_models_json: str = "{}"
    default_primary_provider: str = ""
    default_primary_model: str = ""
    default_light_provider: str = ""
    default_light_model: str = ""
    default_supplier_search_adapter_base_url: str = ""
    default_supplier_search_adapter_api_key: str = ""
    default_supplier_search_adapter_model: str = ""
    default_supplier_search_provider_order: str = "yandex,google,tavily,ddgs"
    default_yandex_search_folder_id: str = ""
    default_yandex_search_api_key: str = ""
    default_google_search_api_key: str = ""
    default_google_search_cse_id: str = ""
    default_document_settings_json: str = "{}"
    tenderplan_api_token: str = ""
    tenderplan_base_url: str = "https://tenderplan.ru"
    tenderplan_timeout_seconds: int = 20
    tender_source_service_url: str = "http://127.0.0.1:8096"
    tender_source_service_timeout_seconds: int = 60
    tenderplan_download_proxy_url: str = ""
    tenderplan_download_timeout_seconds: int = 30
    tenderplan_download_retries: int = 2
    tenderplan_max_documents: int = 60
    tenderplan_max_document_mb: int = 80

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir).resolve()


config = AppConfig()
