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
    trial_enabled: bool | None = None
    trial_supplier_search_limit: int | None = Field(default=None, ge=0, le=10000)
    trial_procurement_report_limit: int | None = Field(default=None, ge=0, le=10000)
    trial_file_limit: int | None = Field(default=None, ge=0, le=100000)
    primary_provider: str | None = None
    primary_model: str | None = None
    light_provider: str | None = None
    light_model: str | None = None
    supplier_ai_provider: str | None = None
    supplier_ai_model: str | None = None
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
    bot_telegram: str | None = None
    contact_email: str | None = None
    contact_telegram: str | None = None
    contact_website: str | None = None
    payment_instructions: str | None = None
    payment_provider: str | None = None
    yookassa_shop_id: str | None = None
    yookassa_secret_key: str | None = None
    yookassa_return_url: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class WebRegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=256)
    name: str = ""
    website: str = ""


class WebLoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=256)


class WebPasswordResetRequestCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class WebEmailVerificationConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class WebEmailChangeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class WebPasswordResetComplete(BaseModel):
    password: str = Field(default="", max_length=256)
    note: str = ""


class ClientCreate(BaseModel):
    telegram_id: str = ""
    name: str = ""
    username: str = ""
    telegram_usernames: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_trial: bool = False
    access_until: str = ""
    allowed_supplier_search: bool = True
    allowed_procurement_report: bool = False
    monthly_job_limit: int = Field(default=0, ge=0)
    monthly_supplier_search_limit: int = Field(default=0, ge=0)
    monthly_procurement_report_limit: int = Field(default=0, ge=0)
    monthly_file_limit: int = Field(default=300, ge=0)
    supplier_target_min: int = Field(default=0, ge=0, le=100)
    notes: str = ""


class ClientPatch(BaseModel):
    name: str | None = None
    username: str | None = None
    is_active: bool | None = None
    is_trial: bool | None = None
    access_until: str | None = None
    allowed_supplier_search: bool | None = None
    allowed_procurement_report: bool | None = None
    monthly_job_limit: int | None = Field(default=None, ge=0)
    monthly_supplier_search_limit: int | None = Field(default=None, ge=0)
    monthly_procurement_report_limit: int | None = Field(default=None, ge=0)
    monthly_file_limit: int | None = Field(default=None, ge=0)
    supplier_target_min: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None


class ClientTelegramAccountCreate(BaseModel):
    telegram_id: str = ""
    username: str = ""
    name: str = ""
    is_active: bool = True
    notes: str = ""
    transfer_existing: bool = False


class ClientTelegramAccountPatch(BaseModel):
    telegram_id: str | None = None
    username: str | None = None
    name: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class ClientMergeRequest(BaseModel):
    source_client_id: str = Field(min_length=1, max_length=64)


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


class TariffPackageCreate(BaseModel):
    kind: str
    name: str
    units: int = Field(default=1, ge=1, le=100000)
    price_kopeks: int = Field(default=0, ge=0, le=1000000000)
    description: str = ""
    is_active: bool = True
    sort_order: int = Field(default=100, ge=0, le=100000)


class TariffPackagePatch(BaseModel):
    kind: str | None = None
    name: str | None = None
    units: int | None = Field(default=None, ge=1, le=100000)
    price_kopeks: int | None = Field(default=None, ge=0, le=1000000000)
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class BillingGrantCreate(BaseModel):
    kind: str
    units: int = Field(default=1, ge=1, le=100000)
    package_id: str = ""
    note: str = ""
