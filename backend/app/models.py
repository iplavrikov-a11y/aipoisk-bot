from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

DEFAULT_PAYMENT_INSTRUCTIONS = (
    "🧾 Чтобы купить пакет:\n"
    "1. Выберите нужный пакет в списке выше.\n"
    "2. Напишите менеджеру в Telegram (приоритетно), MAX или на email.\n"
    "3. Укажите название пакета и ваш Telegram ID.\n"
    "4. После подтверждения оплаты генерации будут начислены вручную.\n\n"
    "✅ Пакеты не сгорают и действуют до полного исчерпания."
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    public_base_url: Mapped[str] = mapped_column(String(255), default="https://tenderlex.ru")

    storage_retention_days: Mapped[int] = mapped_column(Integer, default=90)
    completed_job_retention_days: Mapped[int] = mapped_column(Integer, default=90)
    failed_job_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    max_upload_mb: Mapped[int] = mapped_column(Integer, default=50)
    max_files_per_batch: Mapped[int] = mapped_column(Integer, default=20)
    default_supplier_target: Mapped[int] = mapped_column(Integer, default=25)
    allow_partial_supplier_reports: Mapped[bool] = mapped_column(Boolean, default=True)
    logistics_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_supplier_search_limit: Mapped[int] = mapped_column(Integer, default=0)
    yandex_search_price_per_request: Mapped[float] = mapped_column(Float, default=0.04)
    trial_procurement_report_limit: Mapped[int] = mapped_column(Integer, default=0)
    trial_file_limit: Mapped[int] = mapped_column(Integer, default=10)
    onboarding_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_reminders_rollout_at: Mapped[str] = mapped_column(String(40), default="")

    primary_provider: Mapped[str] = mapped_column(String(80), default="")
    primary_model: Mapped[str] = mapped_column(String(160), default="")
    light_provider: Mapped[str] = mapped_column(String(80), default="")
    light_model: Mapped[str] = mapped_column(String(160), default="")
    supplier_ai_provider: Mapped[str] = mapped_column(String(80), default="")
    supplier_ai_model: Mapped[str] = mapped_column(String(160), default="")
    custom_ai_providers_json: Mapped[str] = mapped_column(Text, default="[]")
    saved_models_json: Mapped[str] = mapped_column(Text, default="[]")
    ai_function_models_json: Mapped[str] = mapped_column(Text, default="{}")
    ai_analysis_fallback_json: Mapped[str] = mapped_column(Text, default="[]")
    ai_supplier_fallback_json: Mapped[str] = mapped_column(Text, default="[]")

    supplier_search_adapter_base_url: Mapped[str] = mapped_column(Text, default="")
    supplier_search_adapter_api_key: Mapped[str] = mapped_column(Text, default="")
    supplier_search_adapter_model: Mapped[str] = mapped_column(String(160), default="")
    supplier_search_provider_order: Mapped[str] = mapped_column(String(255), default="yandex,google,tavily,ddgs")
    yandex_search_folder_id: Mapped[str] = mapped_column(String(255), default="")
    yandex_search_api_key: Mapped[str] = mapped_column(Text, default="")
    google_search_api_key: Mapped[str] = mapped_column(Text, default="")
    google_search_cse_id: Mapped[str] = mapped_column(String(255), default="")

    prompt_settings_json: Mapped[str] = mapped_column(Text, default="{}")
    report_settings_json: Mapped[str] = mapped_column(Text, default="{}")
    document_settings_json: Mapped[str] = mapped_column(Text, default="{}")
    bot_messages_json: Mapped[str] = mapped_column(Text, default="{}")
    bot_telegram: Mapped[str] = mapped_column(String(255), default="@tenderlex_bot")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    contact_telegram: Mapped[str] = mapped_column(String(255), default="")
    contact_max: Mapped[str] = mapped_column(String(255), default="")
    contact_max_link: Mapped[str] = mapped_column(String(255), default="")
    contact_website: Mapped[str] = mapped_column(String(255), default="")
    payment_instructions: Mapped[str] = mapped_column(Text, default=DEFAULT_PAYMENT_INSTRUCTIONS)
    payment_provider: Mapped[str] = mapped_column(String(40), default="manual")
    yookassa_shop_id: Mapped[str] = mapped_column(String(255), default="")
    yookassa_secret_key: Mapped[str] = mapped_column(Text, default="")
    yookassa_return_url: Mapped[str] = mapped_column(String(255), default="")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    def to_dict(self, include_secrets: bool = False) -> dict:
        data = {
            "public_base_url": self.public_base_url,
            "storage_retention_days": self.storage_retention_days,
            "completed_job_retention_days": self.completed_job_retention_days,
            "failed_job_retention_days": self.failed_job_retention_days,
            "max_upload_mb": self.max_upload_mb,
            "max_files_per_batch": self.max_files_per_batch,
            "default_supplier_target": self.default_supplier_target,
            "allow_partial_supplier_reports": self.allow_partial_supplier_reports,
            "logistics_enabled": self.logistics_enabled,
            "trial_enabled": self.trial_enabled,
            "trial_supplier_search_limit": self.trial_supplier_search_limit,
            "trial_procurement_report_limit": self.trial_procurement_report_limit,
            "trial_file_limit": self.trial_file_limit,
            "onboarding_reminders_enabled": self.onboarding_reminders_enabled,
            "onboarding_reminders_rollout_at": self.onboarding_reminders_rollout_at,
            "primary_provider": self.primary_provider,
            "primary_model": self.primary_model,
            "light_provider": self.light_provider,
            "light_model": self.light_model,
            "supplier_ai_provider": self.supplier_ai_provider,
            "supplier_ai_model": self.supplier_ai_model,
            "custom_ai_providers_json": self.custom_ai_providers_json,
            "saved_models_json": self.saved_models_json,
            "ai_function_models_json": self.ai_function_models_json,
            "ai_analysis_fallback_json": self.ai_analysis_fallback_json,
            "ai_supplier_fallback_json": self.ai_supplier_fallback_json,
            "supplier_search_adapter_base_url": self.supplier_search_adapter_base_url,
            "supplier_search_adapter_api_key_set": bool(self.supplier_search_adapter_api_key),
            "supplier_search_adapter_model": self.supplier_search_adapter_model,
            "supplier_search_provider_order": self.supplier_search_provider_order,
            "yandex_search_folder_id": self.yandex_search_folder_id,
            "yandex_search_api_key_set": bool(self.yandex_search_api_key),
            "google_search_api_key_set": bool(self.google_search_api_key),
            "google_search_cse_id": self.google_search_cse_id,
            "prompt_settings_json": self.prompt_settings_json,
            "report_settings_json": self.report_settings_json,
            "document_settings_json": self.document_settings_json,
            "bot_messages_json": self.bot_messages_json,
            "bot_telegram": self.bot_telegram,
            "contact_email": self.contact_email,
            "contact_telegram": self.contact_telegram,
            "contact_max": self.contact_max,
            "contact_max_link": self.contact_max_link,
            "contact_website": self.contact_website,
            "payment_instructions": self.payment_instructions or DEFAULT_PAYMENT_INSTRUCTIONS,
            "payment_provider": self.payment_provider or "manual",
            "yookassa_shop_id": self.yookassa_shop_id,
            "yookassa_secret_key_set": bool(self.yookassa_secret_key),
            "yookassa_return_url": self.yookassa_return_url,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_secrets:
            data["supplier_search_adapter_api_key"] = self.supplier_search_adapter_api_key
            data["yandex_search_api_key"] = self.yandex_search_api_key
            data["google_search_api_key"] = self.google_search_api_key
            data["yookassa_secret_key"] = self.yookassa_secret_key
        return data

    @property
    def has_active_ai_provider(self) -> bool:
        for item in parse_json_list(self.custom_ai_providers_json):
            if str(item.get("apiKey") or "").strip() and str(item.get("baseUrl") or "").strip():
                return True
        return False


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    telegram_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    access_until: Mapped[str] = mapped_column(String(32), default="")
    allowed_supplier_search: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_procurement_report: Mapped[bool] = mapped_column(Boolean, default=False)
    monthly_job_limit: Mapped[int] = mapped_column(Integer, default=0)
    monthly_supplier_search_limit: Mapped[int] = mapped_column(Integer, default=0)
    monthly_procurement_report_limit: Mapped[int] = mapped_column(Integer, default=0)
    monthly_file_limit: Mapped[int] = mapped_column(Integer, default=300)
    money_balance_kopeks: Mapped[int] = mapped_column(Integer, default=0)
    money_reserved_kopeks: Mapped[int] = mapped_column(Integer, default=0)
    supplier_target_min: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    jobs: Mapped[list["Job"]] = relationship(back_populates="client")
    telegram_accounts: Mapped[list["ClientTelegramAccount"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    web_users: Mapped[list["WebUser"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    tariff_overrides: Mapped[list["ClientTariffOverride"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    billing_transactions: Mapped[list["BillingTransaction"]] = relationship(back_populates="client")


class ClientTelegramAccount(Base):
    __tablename__ = "client_telegram_accounts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    telegram_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), default="")
    name: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    client: Mapped[Client] = relationship(back_populates="telegram_accounts")


class WebUser(Base):
    __tablename__ = "web_users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, default="")
    name: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    client: Mapped[Client] = relationship(back_populates="web_users")
    sessions: Mapped[list["WebSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    password_reset_requests: Mapped[list["WebPasswordResetRequest"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    email_verification_tokens: Mapped[list["WebEmailVerificationToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class WebSession(Base):
    __tablename__ = "web_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("web_users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(128), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[str] = mapped_column(String(80), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped[WebUser] = relationship(back_populates="sessions")


class WebPasswordResetRequest(Base):
    __tablename__ = "web_password_reset_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("web_users.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    requested_ip: Mapped[str] = mapped_column(String(80), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    resolved_by: Mapped[str] = mapped_column(String(80), default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user: Mapped[WebUser] = relationship(back_populates="password_reset_requests")


class WebEmailVerificationToken(Base):
    __tablename__ = "web_email_verification_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("web_users.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    requested_ip: Mapped[str] = mapped_column(String(80), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)

    user: Mapped[WebUser] = relationship(back_populates="email_verification_tokens")


class WebRegistrationAttempt(Base):
    __tablename__ = "web_registration_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), index=True)
    ip_address: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="", index=True)
    user_agent: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "document_type",
            "document_version",
            name="uq_legal_acceptance_subject_document_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    subject_type: Mapped[str] = mapped_column(String(40), index=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    document_type: Mapped[str] = mapped_column(String(40), index=True)
    document_version: Mapped[str] = mapped_column(String(40), index=True)
    source: Mapped[str] = mapped_column(String(40), default="")
    ip_address: Mapped[str] = mapped_column(String(80), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class AccountLinkToken(Base):
    __tablename__ = "account_link_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    direction: Mapped[str] = mapped_column(String(40), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    web_user_id: Mapped[str | None] = mapped_column(ForeignKey("web_users.id"), nullable=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    telegram_id: Mapped[str] = mapped_column(String(64), default="")
    conflict_client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    requested_ip: Mapped[str] = mapped_column(String(80), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class UserJourneyEvent(Base):
    __tablename__ = "user_journey_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    actor_ref: Mapped[str] = mapped_column(String(64), default="")
    event_name: Mapped[str] = mapped_column(String(80), index=True)
    mode: Mapped[str] = mapped_column(String(40), default="")
    outcome: Mapped[str] = mapped_column(String(40), default="")
    reason_code: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class OnboardingReminder(Base):
    __tablename__ = "onboarding_reminders"
    __table_args__ = (UniqueConstraint("client_id", "channel", name="uq_onboarding_reminder_client_channel"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="telegram")
    status: Mapped[str] = mapped_column(String(20), default="claimed", index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str] = mapped_column(String(80), default="")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    created_by_telegram_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    mode: Mapped[str] = mapped_column(String(40), default="supplier_search")
    supplier_search_policy: Mapped[str] = mapped_column(String(40), default="normal")
    supplier_search_run_type: Mapped[str] = mapped_column(String(40), default="initial")
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(Text, default="")
    target_suppliers: Mapped[int] = mapped_column(Integer, default=15)
    verified_count: Mapped[int] = mapped_column(Integer, default=0)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    result_path: Mapped[str] = mapped_column(Text, default="")
    evidence_path: Mapped[str] = mapped_column(Text, default="")
    confirmation_kind: Mapped[str] = mapped_column(String(40), default="")
    confirmation_outcome: Mapped[str] = mapped_column(String(40), default="")
    confirmation_offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_delivery_outcome: Mapped[str] = mapped_column(String(40), default="")
    offer_delivery_claim_token: Mapped[str] = mapped_column(String(64), default="")
    offer_delivery_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_delivery_expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_output_manifest: Mapped[str] = mapped_column(String(40), default="")
    active_output_manifest_version: Mapped[int] = mapped_column(Integer, default=0)
    active_entitlements_json: Mapped[str] = mapped_column(Text, default="[]")
    yandex_requests_count: Mapped[int] = mapped_column(Integer, default=0)
    yandex_cost_rub: Mapped[float] = mapped_column(Float, default=0.0)
    ai_provider: Mapped[str] = mapped_column(String(80), default="")
    ai_model: Mapped[str] = mapped_column(String(160), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped[Client | None] = relationship(back_populates="jobs")
    files: Mapped[list["JobFile"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    sources: Mapped[list["JobSource"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    suppliers: Mapped[list["SupplierResult"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    billing_transactions: Mapped[list["BillingTransaction"]] = relationship(back_populates="job")


class TariffPackage(Base):
    __tablename__ = "tariff_packages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    units: Mapped[int] = mapped_column(Integer, default=1)
    price_kopeks: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class BillingTransaction(Base):
    __tablename__ = "billing_transactions"
    __table_args__ = (
        UniqueConstraint("job_id", "kind", "operation", name="uq_billing_transaction_job_kind_operation"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    package_id: Mapped[str] = mapped_column(String(32), default="")
    kind: Mapped[str] = mapped_column(String(40), index=True)
    operation: Mapped[str] = mapped_column(String(40), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    units: Mapped[int] = mapped_column(Integer, default=0)
    amount_kopeks: Mapped[int] = mapped_column(Integer, default=0)
    balance_after_kopeks: Mapped[int] = mapped_column(Integer, default=0)
    reserved_after_kopeks: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)

    client: Mapped[Client] = relationship(back_populates="billing_transactions")
    job: Mapped[Job | None] = relationship(back_populates="billing_transactions")


class ClientTariffOverride(Base):
    __tablename__ = "client_tariff_overrides"
    __table_args__ = (
        UniqueConstraint("client_id", "kind", name="uq_client_tariff_override_client_kind"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    price_kopeks: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    client: Mapped[Client] = relationship(back_populates="tariff_overrides")


class JobFile(Base):
    __tablename__ = "job_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    original_filename: Mapped[str] = mapped_column(Text)
    stored_path: Mapped[str] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(40), default="pending")
    extracted_chars: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    job: Mapped[Job] = relationship(back_populates="files")


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="procurement_url")
    label: Mapped[str] = mapped_column(Text, default="")
    value: Mapped[str] = mapped_column(Text, default="")
    parse_status: Mapped[str] = mapped_column(String(40), default="pending")
    context_path: Mapped[str] = mapped_column(Text, default="")
    extracted_chars: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    job: Mapped[Job] = relationship(back_populates="sources")


class SupplierResult(Base):
    __tablename__ = "supplier_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    company_name: Mapped[str] = mapped_column(Text, default="")
    region: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(80), default="")
    product: Mapped[str] = mapped_column(Text, default="")
    contact_person: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str] = mapped_column(Text, default="")
    email: Mapped[str] = mapped_column(Text, default="")
    site: Mapped[str] = mapped_column(Text, default="")
    evidence_url: Mapped[str] = mapped_column(Text, default="")
    contact_url: Mapped[str] = mapped_column(Text, default="")
    comments: Mapped[str] = mapped_column(Text, default="")
    evidence_status: Mapped[str] = mapped_column(String(40), default="weak")
    match_level: Mapped[str] = mapped_column(String(40), default="")
    source: Mapped[str] = mapped_column(String(40), default="")
    search_query: Mapped[str] = mapped_column(Text, default="")
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    quality_tier: Mapped[str] = mapped_column(String(40), default="")
    procurement_item_id: Mapped[str] = mapped_column(String(80), default="")
    procurement_item: Mapped[str] = mapped_column(Text, default="")
    ai_confidence: Mapped[int] = mapped_column(Integer, default=0)
    site_type: Mapped[str] = mapped_column(String(80), default="")
    product_fit: Mapped[str] = mapped_column(String(80), default="")
    evidence_snippet: Mapped[str] = mapped_column(Text, default="")
    contact_evidence_snippet: Mapped[str] = mapped_column(Text, default="")
    ai_rank_confidence: Mapped[int] = mapped_column(Integer, default=0)
    ai_rank_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    job: Mapped[Job] = relationship(back_populates="suppliers")


def parse_json_list(value: str) -> list[dict]:
    try:
        parsed = json.loads(value or "[]")
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def parse_json_dict(value: str) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}
