from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class OutreachSearchTask(Base):
    __tablename__ = "outreach_search_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), default="Поиск контактов")
    prompt: Mapped[str] = mapped_column(Text, default="")
    target_count: Mapped[int] = mapped_column(Integer, default=500)
    collected_count: Mapped[int] = mapped_column(Integer, default=0)
    scanned_sites: Mapped[int] = mapped_column(Integer, default=0)
    queries_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)  # pending, running, completed, cancelled, error
    message: Mapped[str] = mapped_column(Text, default="")
    yandex_requests: Mapped[int] = mapped_column(Integer, default=0)
    yandex_cost_rub: Mapped[float] = mapped_column(Float, default=0.0)
    llm_cost_rub: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost_rub: Mapped[float] = mapped_column(Float, default=0.0)
    waves_json: Mapped[str] = mapped_column(Text, default="[]")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    def to_dict(self) -> dict[str, Any]:
        waves = []
        if self.waves_json:
            try:
                waves = json.loads(self.waves_json)
            except Exception:
                waves = []
        if not waves and (self.collected_count > 0 or self.target_count > 0):
            waves = [
                {
                    "wave": 1,
                    "name": "Основной поиск",
                    "prompt": self.prompt,
                    "target": self.target_count,
                    "collected": self.collected_count,
                    "yandex_requests": self.yandex_requests,
                    "yandex_cost_rub": round(self.yandex_cost_rub, 2),
                    "cost_rub": round(self.total_cost_rub, 2),
                    "created_at": self.created_at.isoformat() if self.created_at else None,
                }
            ]
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "target_count": self.target_count,
            "collected_count": self.collected_count,
            "scanned_sites": self.scanned_sites,
            "queries_count": self.queries_count,
            "status": self.status,
            "message": self.message,
            "yandex_requests": self.yandex_requests,
            "yandex_cost_rub": round(self.yandex_cost_rub, 2),
            "llm_cost_rub": round(self.llm_cost_rub, 2),
            "total_cost_rub": round(self.total_cost_rub, 2),
            "cost_label": f"{round(self.total_cost_rub, 2):.2f} ₽",
            "waves": waves,
            "waves_count": len(waves),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OutreachLead(Base):
    __tablename__ = "outreach_leads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    wave_index: Mapped[int] = mapped_column(Integer, default=1, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    company_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(100), default="")
    website: Mapped[str] = mapped_column(String(255), default="")
    inn: Mapped[str] = mapped_column(String(20), default="")
    category: Mapped[str] = mapped_column(String(100), default="Общая", index=True)
    activity_profile: Mapped[str] = mapped_column(String(255), default="")
    relevance_score: Mapped[int] = mapped_column(Integer, default=100)
    city: Mapped[str] = mapped_column(String(100), default="")
    source: Mapped[str] = mapped_column(String(100), default="search")
    status: Mapped[str] = mapped_column(String(40), default="new", index=True)  # new, sent, replied, invalid
    mx_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reply_received: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "wave_index": self.wave_index or 1,
            "email": self.email,
            "company_name": self.company_name,
            "phone": self.phone,
            "website": self.website,
            "inn": self.inn,
            "category": self.category,
            "activity_profile": self.activity_profile,
            "relevance_score": self.relevance_score,
            "city": self.city,
            "source": self.source,
            "status": self.status,
            "mx_valid": self.mx_valid,
            "sent_count": self.sent_count,
            "last_sent_at": self.last_sent_at.isoformat() if self.last_sent_at else None,
            "reply_received": self.reply_received,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), default="Новая рассылка")
    subject: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    category_filter: Mapped[str] = mapped_column(String(100), default="")
    task_id_filter: Mapped[str] = mapped_column(String(32), default="", index=True)
    audience_type: Mapped[str] = mapped_column(String(40), default="new")  # new, all, unanswered, follow_up, selected
    selected_lead_ids: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)  # draft, running, paused, completed, stopped
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    delay_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "category_filter": self.category_filter,
            "task_id_filter": self.task_id_filter,
            "audience_type": self.audience_type or "new",
            "selected_lead_ids": json.loads(self.selected_lead_ids) if self.selected_lead_ids else [],
            "status": self.status,
            "total_recipients": self.total_recipients,
            "sent_count": self.sent_count,
            "failed_count": self.failed_count,
            "delay_seconds": self.delay_seconds,
            "current_index": self.current_index,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OutreachSendLog(Base):
    __tablename__ = "outreach_send_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), nullable=True, index=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("outreach_leads.id", ondelete="SET NULL"), nullable=True, index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), index=True)
    recipient_company: Mapped[str] = mapped_column(String(255), default="")
    from_email: Mapped[str] = mapped_column(String(255), default="info@tenderlex.ru")
    subject: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="sent")  # sent, failed
    error_message: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "lead_id": self.lead_id,
            "recipient_email": self.recipient_email,
            "recipient_company": self.recipient_company,
            "from_email": self.from_email,
            "subject": self.subject,
            "status": self.status,
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


class OutreachIncomingEmail(Base):
    __tablename__ = "outreach_inbox"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(String(255), index=True, default="")
    sender_email: Mapped[str] = mapped_column(String(255), index=True)
    sender_name: Mapped[str] = mapped_column(String(255), default="")
    recipient_email: Mapped[str] = mapped_column(String(255), default="info@tenderlex.ru")
    subject: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    date_received: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("outreach_leads.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message_id": self.message_id,
            "sender_email": self.sender_email,
            "sender_name": self.sender_name,
            "recipient_email": self.recipient_email,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "category": self.category,
            "is_spam": self.is_spam,
            "date_received": self.date_received.isoformat() if self.date_received else None,
            "is_read": self.is_read,
            "replied_at": self.replied_at.isoformat() if self.replied_at else None,
            "lead_id": self.lead_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OutreachSettings(Base):
    __tablename__ = "outreach_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    from_name: Mapped[str] = mapped_column(String(255), default="TenderLex")
    from_email: Mapped[str] = mapped_column(String(255), default="info@tenderlex.ru")
    reply_to: Mapped[str] = mapped_column(String(255), default="info@tenderlex.ru")
    
    # Relay
    relay_url: Mapped[str] = mapped_column(String(255), default="")
    relay_api_key: Mapped[str] = mapped_column(Text, default="")
    
    # SMTP
    smtp_host: Mapped[str] = mapped_column(String(255), default="smtp.jino.ru")
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_user: Mapped[str] = mapped_column(String(255), default="info@tenderlex.ru")
    smtp_password: Mapped[str] = mapped_column(Text, default="")
    smtp_use_ssl: Mapped[bool] = mapped_column(Boolean, default=False)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True)

    # IMAP
    imap_host: Mapped[str] = mapped_column(String(255), default="127.0.0.1")
    imap_port: Mapped[int] = mapped_column(Integer, default=19993)
    imap_user: Mapped[str] = mapped_column(String(255), default="info@tenderlex.ru")
    imap_password: Mapped[str] = mapped_column(Text, default="")
    imap_use_ssl: Mapped[bool] = mapped_column(Boolean, default=False)

    # Sending throttles
    delay_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    daily_limit: Mapped[int] = mapped_column(Integer, default=500)
    spam_rules_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        data = {
            "from_name": self.from_name,
            "from_email": self.from_email,
            "reply_to": self.reply_to,
            "relay_url": self.relay_url,
            "relay_api_key_set": bool(self.relay_api_key),
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user,
            "smtp_password_set": bool(self.smtp_password),
            "smtp_use_ssl": self.smtp_use_ssl,
            "smtp_use_tls": self.smtp_use_tls,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "imap_user": self.imap_user,
            "imap_password_set": bool(self.imap_password),
            "imap_use_ssl": self.imap_use_ssl,
            "delay_seconds": self.delay_seconds,
            "daily_limit": self.daily_limit,
            "spam_rules": json.loads(self.spam_rules_json) if self.spam_rules_json else [],
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_secrets:
            data["relay_api_key"] = self.relay_api_key
            data["smtp_password"] = self.smtp_password
            data["imap_password"] = self.imap_password
        return data
