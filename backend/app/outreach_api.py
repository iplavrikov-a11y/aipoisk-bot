from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from .ai import call_llm
from .db import SessionLocal
from .models import SystemSettings
from .outreach_mail import (
    ACTIVE_CAMPAIGN_TASKS,
    render_template_text,
    run_campaign_worker,
    send_single_email,
    sync_imap_inbox,
)
from .outreach_models import (
    OutreachCampaign,
    OutreachIncomingEmail,
    OutreachLead,
    OutreachSearchTask,
    OutreachSendLog,
    OutreachSettings,
    now_utc,
)
from .outreach_search import (
    ACTIVE_SEARCH_TASKS,
    run_outreach_search_task,
)
from .security import require_admin

router = APIRouter(prefix="/api/outreach", tags=["outreach"], dependencies=[Depends(require_admin)])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_or_create_outreach_settings(db: Session) -> OutreachSettings:
    settings = db.query(OutreachSettings).filter(OutreachSettings.id == 1).first()
    if not settings:
        settings = OutreachSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


# ==================== SCHEMAS ====================


class StartSearchRequest(BaseModel):
    name: str = ""
    prompt: str
    target_count: int = 500


class ManualLeadRequest(BaseModel):
    email: str
    company_name: str = ""
    phone: str = ""
    website: str = ""
    city: str = ""
    category: str = "Ручной ввод"
    task_id: str = ""


class DeleteLeadsRequest(BaseModel):
    lead_ids: list[str] = []
    all_leads: bool = False
    status_filter: str = ""
    task_id: str = ""


class CreateCampaignRequest(BaseModel):
    name: str = "Рассылка"
    subject: str
    body_text: str
    body_html: str = ""
    category_filter: str = ""
    task_id_filter: str = ""
    audience_type: str = "new"  # new, all, unanswered, follow_up, selected
    lead_ids: list[str] = []
    delay_seconds: float = 2.0


class DirectSendRequest(BaseModel):
    recipients: list[str]
    subject: str
    body_text: str
    body_html: str = ""
    lead_id: str | None = None


class ReplyInboxRequest(BaseModel):
    message_id: str
    reply_body: str
    reply_html: str = ""


class AiGenerateRequest(BaseModel):
    action: str  # cold_email, improve, shorten, grammar, subject, reply
    prompt: str = ""
    context: str = ""
    tone: str = "professional"  # professional, friendly, selling, concise
    company_name: str = ""
    incoming_message: str = ""


class TestSendRequest(BaseModel):
    to_email: str
    subject: str = "Тестовое письмо TenderLex"
    body_text: str = "Тестовая отправка из админ-панели TenderLex."
    body_html: str = ""


class UpdateSettingsRequest(BaseModel):
    from_name: str | None = None
    from_email: str | None = None
    reply_to: str | None = None
    relay_url: str | None = None
    relay_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_ssl: bool | None = None
    smtp_use_tls: bool | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_user: str | None = None
    imap_password: str | None = None
    imap_use_ssl: bool | None = None
    delay_seconds: float | None = None
    daily_limit: int | None = None


# ==================== STATS ====================


@router.get("/stats")
def get_outreach_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    total_leads = db.query(func.count(OutreachLead.id)).scalar() or 0
    new_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.status == "new").scalar() or 0
    sent_leads = db.query(func.count(OutreachLead.id)).filter(
        or_(OutreachLead.status.in_(["sent", "replied"]), OutreachLead.sent_count > 0)
    ).scalar() or 0
    replied_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.reply_received == True).scalar() or 0
    mx_valid_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.mx_valid == True).scalar() or 0
    inbox_unread = db.query(func.count(OutreachIncomingEmail.id)).filter(OutreachIncomingEmail.is_read == False).scalar() or 0
    inbox_total = db.query(func.count(OutreachIncomingEmail.id)).scalar() or 0
    total_tasks = db.query(func.count(OutreachSearchTask.id)).scalar() or 0

    return {
        "total_leads": total_leads,
        "new_leads": new_leads,
        "sent_leads": sent_leads,
        "replied_leads": replied_leads,
        "mx_valid_leads": mx_valid_leads,
        "inbox_unread": inbox_unread,
        "inbox_total": inbox_total,
        "total_tasks": total_tasks,
    }


# ==================== SEARCH & TASKS ====================


@router.get("/tasks")
def list_search_tasks(db: Session = Depends(get_db)) -> dict[str, Any]:
    tasks = db.query(OutreachSearchTask).order_by(desc(OutreachSearchTask.created_at)).all()
    # Merge with active memory status
    items = []
    for t in tasks:
        d = t.to_dict()
        if t.id in ACTIVE_SEARCH_TASKS:
            act = ACTIVE_SEARCH_TASKS[t.id]
            d["status"] = act.get("status", d["status"])
            d["message"] = act.get("message", d["message"])
            d["collected_count"] = act.get("collected", d["collected_count"])
            d["scanned_sites"] = act.get("scanned_sites", d["scanned_sites"])
            d["yandex_requests"] = act.get("yandex_requests", d["yandex_requests"])
            d["yandex_cost_rub"] = act.get("yandex_cost_rub", d["yandex_cost_rub"])
            d["total_cost_rub"] = act.get("total_cost_rub", d["total_cost_rub"])
            d["cost_label"] = f"{d['total_cost_rub']:.2f} ₽"
        items.append(d)
    return {"items": items}


@router.get("/tasks/{task_id}")
def get_search_task(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    d = task.to_dict()
    if task_id in ACTIVE_SEARCH_TASKS:
        act = ACTIVE_SEARCH_TASKS[task_id]
        d["status"] = act.get("status", d["status"])
        d["message"] = act.get("message", d["message"])
        d["collected_count"] = act.get("collected", d["collected_count"])
        d["scanned_sites"] = act.get("scanned_sites", d["scanned_sites"])
        d["yandex_requests"] = act.get("yandex_requests", d["yandex_requests"])
        d["yandex_cost_rub"] = act.get("yandex_cost_rub", d["yandex_cost_rub"])
        d["total_cost_rub"] = act.get("total_cost_rub", d["total_cost_rub"])
        d["cost_label"] = f"{d['total_cost_rub']:.2f} ₽"
    return d


@router.get("/tasks/{task_id}/stats")
def get_task_stats(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    total_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id).scalar() or 0
    new_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id, OutreachLead.status == "new").scalar() or 0
    sent_leads = db.query(func.count(OutreachLead.id)).filter(
        OutreachLead.task_id == task_id,
        or_(OutreachLead.status.in_(["sent", "replied"]), OutreachLead.sent_count > 0),
    ).scalar() or 0
    replied_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id, OutreachLead.reply_received == True).scalar() or 0
    mx_valid_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id, OutreachLead.mx_valid == True).scalar() or 0

    return {
        "task": task.to_dict(),
        "total_leads": total_leads,
        "new_leads": new_leads,
        "sent_leads": sent_leads,
        "replied_leads": replied_leads,
        "mx_valid_leads": mx_valid_leads,
    }


@router.post("/search/start")
async def start_outreach_search(data: StartSearchRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    prompt = data.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Введите описание ниши для поиска")
    
    target_count = max(1, min(10000, data.target_count))
    task_id = uuid.uuid4().hex
    task_name = data.name.strip() or prompt[:60]

    task_rec = OutreachSearchTask(
        id=task_id,
        name=task_name,
        prompt=prompt,
        target_count=target_count,
        status="running",
        started_at=now_utc(),
        message="Запуск поиска...",
    )
    db.add(task_rec)
    db.commit()

    sys_settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not sys_settings:
        sys_settings = SystemSettings(id=1)

    asyncio.create_task(
        run_outreach_search_task(
            task_id=task_id,
            name=task_name,
            prompt=prompt,
            target_count=target_count,
            session_factory=SessionLocal,
            settings=sys_settings,
        )
    )

    return {"ok": True, "task_id": task_id, "task": task_rec.to_dict()}


@router.get("/search/status/{task_id}")
def get_search_status(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    if task_id in ACTIVE_SEARCH_TASKS:
        return ACTIVE_SEARCH_TASKS[task_id]
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if task:
        return task.to_dict()
    return {"status": "not_found", "message": "Задача не найдена"}


@router.post("/search/cancel/{task_id}")
def cancel_search_task(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    if task_id in ACTIVE_SEARCH_TASKS:
        ACTIVE_SEARCH_TASKS[task_id]["cancel"] = True
        ACTIVE_SEARCH_TASKS[task_id]["status"] = "cancelling"
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if task:
        task.status = "cancelled"
        task.completed_at = now_utc()
        task.message = "Остановлено пользователем"
        db.commit()
    return {"ok": True}


@router.delete("/tasks/{task_id}")
def delete_search_task(
    task_id: str,
    delete_leads: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if task_id in ACTIVE_SEARCH_TASKS:
        ACTIVE_SEARCH_TASKS[task_id]["cancel"] = True
        ACTIVE_SEARCH_TASKS.pop(task_id, None)

    if delete_leads:
        db.query(OutreachLead).filter(OutreachLead.task_id == task_id).delete(synchronize_session=False)

    db.delete(task)
    db.commit()
    return {"ok": True}


# ==================== LEADS ====================


@router.get("/leads")
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query("", max_length=100),
    status: str = Query("", max_length=50),
    category: str = Query("", max_length=100),
    task_id: str = Query("", max_length=50),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = db.query(OutreachLead)

    if task_id:
        query = query.filter(OutreachLead.task_id == task_id)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                OutreachLead.email.ilike(s),
                OutreachLead.company_name.ilike(s),
                OutreachLead.phone.ilike(s),
                OutreachLead.website.ilike(s),
                OutreachLead.city.ilike(s),
                OutreachLead.activity_profile.ilike(s),
            )
        )
    if status:
        if status == "replied":
            query = query.filter(OutreachLead.reply_received == True)
        elif status == "sent":
            query = query.filter(or_(OutreachLead.status.in_(["sent", "replied"]), OutreachLead.sent_count > 0))
        else:
            query = query.filter(OutreachLead.status == status)
    if category:
        query = query.filter(OutreachLead.category.ilike(f"%{category}%"))

    total = query.count()
    items = query.order_by(desc(OutreachLead.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [lead.to_dict() for lead in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/leads")
def add_lead_manual(data: ManualLeadRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    em = data.email.strip().lower()
    if "@" not in em or "." not in em.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Некорректный email")

    existing = db.query(OutreachLead).filter(OutreachLead.email == em).first()
    if existing:
        return {"ok": True, "lead": existing.to_dict(), "existed": True}

    lead = OutreachLead(
        email=em,
        company_name=data.company_name.strip(),
        phone=data.phone.strip(),
        website=data.website.strip(),
        city=data.city.strip(),
        category=data.category.strip() or "Ручной ввод",
        source="manual",
        status="new",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return {"ok": True, "lead": lead.to_dict(), "existed": False}


@router.delete("/leads")
@router.post("/leads/delete")
def delete_leads(data: DeleteLeadsRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    if data.all_leads:
        q = db.query(OutreachLead)
        if data.task_id:
            q = q.filter(OutreachLead.task_id == data.task_id)
        if data.status_filter:
            if data.status_filter == "replied":
                q = q.filter(OutreachLead.reply_received == True)
            else:
                q = q.filter(OutreachLead.status == data.status_filter)
        deleted = q.delete(synchronize_session=False)
        db.commit()
        return {"ok": True, "deleted": deleted}
    
    if data.lead_ids:
        deleted = db.query(OutreachLead).filter(OutreachLead.id.in_(data.lead_ids)).delete(synchronize_session=False)
        db.commit()
        return {"ok": True, "deleted": deleted}

    return {"ok": True, "deleted": 0}


# ==================== CAMPAIGNS & SENDING ====================


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)) -> dict[str, Any]:
    campaigns = db.query(OutreachCampaign).order_by(desc(OutreachCampaign.created_at)).limit(50).all()
    return {"items": [c.to_dict() for c in campaigns]}


@router.post("/campaigns")
async def create_campaign(data: CreateCampaignRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not data.subject.strip() or not data.body_text.strip():
        raise HTTPException(status_code=400, detail="Укажите тему и текст письма")

    selected_ids_str = json.dumps(data.lead_ids) if data.lead_ids else ""
    campaign = OutreachCampaign(
        name=data.name.strip() or "Рассылка",
        subject=data.subject.strip(),
        body_text=data.body_text.strip(),
        body_html=data.body_html.strip(),
        category_filter=data.category_filter.strip(),
        task_id_filter=data.task_id_filter.strip(),
        audience_type=data.audience_type.strip() or "new",
        selected_lead_ids=selected_ids_str,
        delay_seconds=max(1.0, data.delay_seconds),
        status="draft",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # Immediately start in background
    task = asyncio.create_task(run_campaign_worker(campaign.id, SessionLocal))
    ACTIVE_CAMPAIGN_TASKS[campaign.id] = task

    return {"ok": True, "campaign": campaign.to_dict()}


@router.post("/campaigns/{campaign_id}/pause")
def pause_campaign(campaign_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    c.status = "paused"
    db.commit()
    return {"ok": True, "status": "paused"}


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    c.status = "running"
    db.commit()
    task = asyncio.create_task(run_campaign_worker(campaign_id, SessionLocal))
    ACTIVE_CAMPAIGN_TASKS[campaign_id] = task
    return {"ok": True, "status": "running"}


@router.post("/campaigns/{campaign_id}/stop")
def stop_campaign(campaign_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    c.status = "stopped"
    db.commit()
    return {"ok": True, "status": "stopped"}


@router.post("/send-direct")
async def send_direct_email(data: DirectSendRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _get_or_create_outreach_settings(db)
    if not data.recipients:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одного получателя")
    if not data.subject.strip() or not data.body_text.strip():
        raise HTTPException(status_code=400, detail="Укажите тему и текст письма")

    sent_count = 0
    errors = []
    for em in data.recipients:
        clean_to = em.strip()
        if not clean_to or "@" not in clean_to:
            continue

        lead = None
        if data.lead_id:
            lead = db.query(OutreachLead).filter(OutreachLead.id == data.lead_id).first()
        if not lead:
            lead = db.query(OutreachLead).filter(OutreachLead.email == clean_to).first()

        subj = render_template_text(data.subject.strip(), lead)
        text_body = render_template_text(data.body_text.strip(), lead)
        html_body = render_template_text(data.body_html.strip(), lead) if data.body_html else ""

        ok, err = await send_single_email(
            to_email=clean_to,
            subject=subj,
            body_text=text_body,
            body_html=html_body,
            settings=settings,
        )
        if ok:
            sent_count += 1
            log = OutreachSendLog(
                campaign_id="",
                lead_id=lead.id if lead else data.lead_id,
                recipient_email=clean_to,
                recipient_company=lead.company_name if lead else "",
                from_email=settings.from_email,
                subject=subj,
                status="sent",
            )
            db.add(log)
            if lead:
                lead.status = "sent"
                lead.sent_count += 1
                lead.last_sent_at = now_utc()
        else:
            errors.append(f"{clean_to}: {err}")

    db.commit()
    if sent_count == 0 and errors:
        raise HTTPException(status_code=500, detail=f"Не удалось отправить: {', '.join(errors)}")
    return {"ok": True, "sent_count": sent_count, "errors": errors}


@router.post("/test-send")
async def send_test_email(data: TestSendRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _get_or_create_outreach_settings(db)
    to_em = data.to_email.strip()
    if not to_em or "@" not in to_em:
        raise HTTPException(status_code=400, detail="Укажите корректный email получателя")

    sample_lead = OutreachLead(
        company_name="ООО «РосСнабКомплект»",
        phone="+7 (495) 123-45-67",
        website="https://rossnab.ru",
        city="Москва",
        email=to_em,
        inn="7701234567",
    )
    subj = render_template_text(data.subject.strip(), sample_lead)
    text_body = render_template_text(data.body_text.strip(), sample_lead)
    html_body = render_template_text(data.body_html.strip(), sample_lead) if data.body_html else ""

    ok, err = await send_single_email(
        to_email=to_em,
        subject=subj,
        body_text=text_body,
        body_html=html_body,
        settings=settings,
    )
    if not ok:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки: {err}")
    return {"ok": True, "message": f"Тестовое письмо успешно отправлено на {to_em}"}


@router.get("/send-logs")
def list_send_logs(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)) -> dict[str, Any]:
    logs = db.query(OutreachSendLog).order_by(desc(OutreachSendLog.sent_at)).limit(limit).all()
    return {"items": [log.to_dict() for log in logs]}


# ==================== INBOX (IMAP) ====================


@router.get("/inbox")
def list_inbox_messages(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    is_spam: bool = Query(False),
    search: str = Query(""),
    task_id: str = Query(""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task_id_str = str(task_id).strip() if isinstance(task_id, str) else ""
    search_str = str(search).strip() if isinstance(search, str) else ""
    unread_bool = bool(unread_only) if isinstance(unread_only, bool) else False
    is_spam_bool = bool(is_spam) if isinstance(is_spam, bool) else False
    limit_int = int(limit) if isinstance(limit, (int, float)) else 50
    offset_int = int(offset) if isinstance(offset, (int, float)) else 0

    q = db.query(OutreachIncomingEmail)
    if is_spam_bool:
        q = q.filter(OutreachIncomingEmail.is_spam == True)
    else:
        q = q.filter(OutreachIncomingEmail.is_spam == False)

    if task_id_str:
        lead_ids = [l.id for l in db.query(OutreachLead.id).filter(OutreachLead.task_id == task_id_str).all()]
        if lead_ids:
            q = q.filter(OutreachIncomingEmail.lead_id.in_(lead_ids))
        else:
            return {"items": [], "total": 0}

    if unread_bool:
        q = q.filter(OutreachIncomingEmail.is_read == False)
    if search_str:
        term = f"%{search_str}%"
        q = q.filter(
            or_(
                OutreachIncomingEmail.sender_email.ilike(term),
                OutreachIncomingEmail.sender_name.ilike(term),
                OutreachIncomingEmail.subject.ilike(term),
                OutreachIncomingEmail.body_text.ilike(term),
            )
        )

    total_count = q.count()
    messages = q.order_by(desc(OutreachIncomingEmail.date_received)).offset(offset_int).limit(limit_int).all()

    lead_ids = [m.lead_id for m in messages if m.lead_id]
    leads_map = {l.id: l for l in db.query(OutreachLead).filter(OutreachLead.id.in_(lead_ids)).all()} if lead_ids else {}
    task_ids = [l.task_id for l in leads_map.values() if l.task_id]
    tasks_map = {t.id: t.name for t in db.query(OutreachSearchTask).filter(OutreachSearchTask.id.in_(task_ids)).all()} if task_ids else {}

    items = []
    for m in messages:
        d = m.to_dict()
        if m.lead_id and m.lead_id in leads_map:
            lead = leads_map[m.lead_id]
            d["lead_company"] = lead.company_name
            d["lead_phone"] = lead.phone
            d["task_id"] = lead.task_id
            d["task_name"] = tasks_map.get(lead.task_id, "")
        else:
            d["lead_company"] = ""
            d["lead_phone"] = ""
            d["task_id"] = ""
            d["task_name"] = ""
        items.append(d)

    return {"items": items, "total": total_count}


@router.post("/inbox/sync")
def trigger_inbox_sync(db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _get_or_create_outreach_settings(db)
    result = sync_imap_inbox(settings=settings, db=db, limit=100)
    return result


@router.patch("/inbox/{message_id}/read")
def mark_inbox_read(message_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    msg = db.query(OutreachIncomingEmail).filter(OutreachIncomingEmail.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Письмо не найдено")
    msg.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/inbox/{message_id}/spam")
def toggle_inbox_spam(message_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    msg = db.query(OutreachIncomingEmail).filter(OutreachIncomingEmail.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Письмо не найдено")
    msg.is_spam = not getattr(msg, "is_spam", False)
    if msg.lead_id:
        lead = db.query(OutreachLead).filter(OutreachLead.id == msg.lead_id).first()
        if lead:
            lead.status = "spam" if msg.is_spam else "new"
    db.commit()
    return {"ok": True, "is_spam": msg.is_spam}


@router.delete("/inbox/{message_id}")
def delete_inbox_message(message_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    msg = db.query(OutreachIncomingEmail).filter(OutreachIncomingEmail.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Письмо не найдено")
    db.delete(msg)
    db.commit()
    return {"ok": True}


@router.post("/inbox/reply")
async def reply_inbox_message(data: ReplyInboxRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    msg = db.query(OutreachIncomingEmail).filter(OutreachIncomingEmail.id == data.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Входящее письмо не найдено")

    settings = _get_or_create_outreach_settings(db)
    subj = msg.subject
    if not subj.lower().startswith("re:"):
        subj = f"Re: {subj}"

    quoted_orig = f"\n\n--- Исходное сообщение от {msg.sender_email} ---\n{msg.body_text}"
    full_body = f"{data.reply_body.strip()}{quoted_orig}"

    ok, err = await send_single_email(
        to_email=msg.sender_email,
        subject=subj,
        body_text=full_body,
        body_html=data.reply_html.strip(),
        settings=settings,
    )
    if not ok:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки ответа: {err}")

    msg.is_read = True
    msg.replied_at = now_utc()
    log = OutreachSendLog(
        campaign_id="",
        lead_id=msg.lead_id,
        recipient_email=msg.sender_email,
        from_email=settings.from_email,
        subject=subj,
        status="sent",
    )
    db.add(log)
    db.commit()
    return {"ok": True, "message": "Ответ успешно отправлен"}


# ==================== LEAD HISTORY ====================


@router.get("/leads/{lead_id}/history")
def get_lead_history(lead_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    lead = db.query(OutreachLead).filter(OutreachLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")

    sent_logs = (
        db.query(OutreachSendLog)
        .filter(or_(OutreachSendLog.lead_id == lead.id, OutreachSendLog.recipient_email == lead.email))
        .order_by(desc(OutreachSendLog.sent_at))
        .all()
    )
    incoming = (
        db.query(OutreachIncomingEmail)
        .filter(or_(OutreachIncomingEmail.lead_id == lead.id, OutreachIncomingEmail.sender_email == lead.email))
        .order_by(desc(OutreachIncomingEmail.date_received))
        .all()
    )

    return {
        "lead": lead.to_dict(),
        "sent": [l.to_dict() for l in sent_logs],
        "incoming": [m.to_dict() for m in incoming],
    }


# ==================== AI ASSISTANT ====================


@router.post("/ai/generate")
async def generate_ai_email(data: AiGenerateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    sys_settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not sys_settings:
        sys_settings = SystemSettings(id=1)

    tone_desc = {
        "professional": "деловой, профессиональный, уважительный, четкий",
        "friendly": "дружелюбный, открытый, располагающий к диалогу",
        "selling": "убедительный, продающий, с фокусом на ценность и выгоду для клиента",
        "concise": "максимально краткий, без воды, суть в 2-3 предложениях",
    }.get(data.tone, "деловой и профессиональный")

    company = data.company_name or "компания"

    if data.action == "cold_email":
        sys_prompt = (
            f"Ты — опытный B2B копирайтер для сервиса TenderLex (сервис быстрого поиска поставщиков и аналитики закупок по 44-ФЗ и 223-ФЗ).\n"
            f"Напиши холодное коммерческое письмо для {company}.\n"
            f"Тон: {tone_desc}.\n"
            f"Используй переменные: {{company}} для названия компании.\n"
            f"Письмо должно содержать: четкую ценность, решение проблемы поиска поставщиков/субподрядчиков, призыв к простому действию (ответить на письмо).\n"
            f"Верни ответ в формате:\nТЕМА: [тема письма]\nТЕКСТ: [текст письма]"
        )
        user_prompt = f"Контекст/пожелания: {data.prompt or 'Предложение сервиса автоматизации закупок и поиска производителей'}"
        res = await call_llm(
            settings=sys_settings,
            prompt=user_prompt,
            system_prompt=sys_prompt,
            tier="light",
        )
        subject = "Сотрудничество с TenderLex"
        body = res.strip()
        if "ТЕМА:" in res and "ТЕКСТ:" in res:
            parts = res.split("ТЕКСТ:", 1)
            subject = parts[0].replace("ТЕМА:", "").strip()
            body = parts[1].strip()
        return {"ok": True, "subject": subject, "body_text": body}

    elif data.action == "improve":
        sys_prompt = f"Ты — редактор деловой B2B переписки. Улучши текст письма, сделай его более убедительным и профессиональным (тон: {tone_desc}). Сохрани структуру и переменные. Верни ТОЛЬКО улучшенный текст."
        body = await call_llm(
            settings=sys_settings,
            prompt=data.context or data.prompt,
            system_prompt=sys_prompt,
            tier="light",
        )
        return {"ok": True, "body_text": body.strip()}

    elif data.action == "shorten":
        sys_prompt = "Ты — эксперт по лаконичным B2B письмам. Сократи текст письма, убрав всю воду, оставь только самую суть и понятный призыв к действию. Верни ТОЛЬКО сокращенный текст."
        body = await call_llm(
            settings=sys_settings,
            prompt=data.context or data.prompt,
            system_prompt=sys_prompt,
            tier="light",
        )
        return {"ok": True, "body_text": body.strip()}

    elif data.action == "grammar":
        sys_prompt = "Исправь все орфографические, пунктуационные и стилистические ошибки в тексте. Верни ТОЛЬКО исправленный текст без пояснений."
        body = await call_llm(
            settings=sys_settings,
            prompt=data.context or data.prompt,
            system_prompt=sys_prompt,
            tier="light",
        )
        return {"ok": True, "body_text": body.strip()}

    elif data.action == "subject":
        sys_prompt = "Придумай 3 цепляющих, профессиональных варианта темы письма для B2B рассылки на русском языке. Верни список через перенос строки, без лишних фраз."
        res = await call_llm(
            settings=sys_settings,
            prompt=data.context or data.prompt or "Предложение сотрудничества по госзакупкам и поставкам",
            system_prompt=sys_prompt,
            tier="light",
        )
        lines = [l.strip().lstrip("0123456789.- ") for l in res.split("\n") if l.strip()]
        return {"ok": True, "subjects": lines[:5]}

    elif data.action == "reply":
        sys_prompt = (
            f"Ты — менеджер компании TenderLex. Напиши профессиональный ответ на входящее письмо от клиента/поставщика.\n"
            f"Тон: {tone_desc}.\n"
            f"Пожелание/тип ответа: {data.prompt or 'вежливый позитивный ответ'}\n"
            f"Верни ТОЛЬКО текст ответа."
        )
        user_prompt = f"Входящее письмо:\n{data.incoming_message}"
        body = await call_llm(
            settings=sys_settings,
            prompt=user_prompt,
            system_prompt=sys_prompt,
            tier="light",
        )
        return {"ok": True, "reply_body": body.strip()}

    return {"ok": False, "error": "Неизвестное действие"}


# ==================== SETTINGS ====================


@router.get("/settings")
def get_outreach_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _get_or_create_outreach_settings(db)
    return settings.to_dict(include_secrets=False)


@router.patch("/settings")
def update_outreach_settings(data: UpdateSettingsRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _get_or_create_outreach_settings(db)

    if data.from_name is not None:
        settings.from_name = data.from_name.strip()
    if data.from_email is not None:
        settings.from_email = data.from_email.strip()
    if data.reply_to is not None:
        settings.reply_to = data.reply_to.strip()
    if data.relay_url is not None:
        settings.relay_url = data.relay_url.strip()
    if data.relay_api_key is not None and data.relay_api_key.strip():
        settings.relay_api_key = data.relay_api_key.strip()
    if data.smtp_host is not None:
        settings.smtp_host = data.smtp_host.strip()
    if data.smtp_port is not None:
        settings.smtp_port = data.smtp_port
    if data.smtp_user is not None:
        settings.smtp_user = data.smtp_user.strip()
    if data.smtp_password is not None and data.smtp_password.strip():
        settings.smtp_password = data.smtp_password.strip()
    if data.smtp_use_ssl is not None:
        settings.smtp_use_ssl = data.smtp_use_ssl
    if data.smtp_use_tls is not None:
        settings.smtp_use_tls = data.smtp_use_tls
    if data.imap_host is not None:
        settings.imap_host = data.imap_host.strip()
    if data.imap_port is not None:
        settings.imap_port = data.imap_port
    if data.imap_user is not None:
        settings.imap_user = data.imap_user.strip()
    if data.imap_password is not None and data.imap_password.strip():
        settings.imap_password = data.imap_password.strip()
    if data.imap_use_ssl is not None:
        settings.imap_use_ssl = data.imap_use_ssl
    if data.delay_seconds is not None:
        settings.delay_seconds = max(0.5, data.delay_seconds)
    if data.daily_limit is not None:
        settings.daily_limit = max(10, data.daily_limit)

    db.commit()
    db.refresh(settings)
    return {"ok": True, "settings": settings.to_dict(include_secrets=False)}
