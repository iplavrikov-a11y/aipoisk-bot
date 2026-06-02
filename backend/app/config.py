from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIPOISK_",
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    public_base_url: str = "https://aipoisk.lexelence.ru"
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

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir).resolve()


config = AppConfig()
