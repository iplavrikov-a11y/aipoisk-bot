from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsPatch(BaseModel):
    public_base_url: str | None = None
    storage_retention_days: int | None = Field(default=None, ge=1, le=3650)
    completed_job_retention_days: int | None = Field(default=None, ge=1, le=3650)
    failed_job_retention_days: int | None = Field(default=None, ge=1, le=3650)
    max_upload_mb: int | None = Field(default=None, ge=1, le=500)
    max_files_per_batch: int | None = Field(default=None, ge=1, le=200)
    default_supplier_target: int | None = Field(default=None, ge=1, le=100)
    allow_partial_supplier_reports: bool | None = None
    logistics_enabled: bool | None = None
    primary_provider: str | None = None
    primary_model: str | None = None
    light_provider: str | None = None
    light_model: str | None = None
    custom_ai_providers_json: str | None = None
    saved_models_json: str | None = None
    ai_function_models_json: str | None = None
    supplier_search_adapter_base_url: str | None = None
    supplier_search_adapter_api_key: str | None = None
    supplier_search_adapter_model: str | None = None
    supplier_search_provider_order: str | None = None
    yandex_search_folder_id: str | None = None
    yandex_search_api_key: str | None = None
    google_search_api_key: str | None = None
    google_search_cse_id: str | None = None
    prompt_settings_json: str | None = None
    report_settings_json: str | None = None
    document_settings_json: str | None = None
    bot_messages_json: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ClientCreate(BaseModel):
    telegram_id: str
    name: str = ""
    username: str = ""
    is_active: bool = True
    access_until: str = ""
    allowed_supplier_search: bool = True
    allowed_procurement_report: bool = False
    monthly_job_limit: int = Field(default=100, ge=0)
    monthly_file_limit: int = Field(default=300, ge=0)
    notes: str = ""


class ClientPatch(BaseModel):
    name: str | None = None
    username: str | None = None
    is_active: bool | None = None
    access_until: str | None = None
    allowed_supplier_search: bool | None = None
    allowed_procurement_report: bool | None = None
    monthly_job_limit: int | None = Field(default=None, ge=0)
    monthly_file_limit: int | None = Field(default=None, ge=0)
    notes: str | None = None


class AiTestRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    routing_key: str | None = None
    prompt: str = "Ответь одним словом: ok"


class ManualJobCreate(BaseModel):
    telegram_id: str
    mode: str = "supplier_search"
    title: str = ""
    target_suppliers: int | None = None
