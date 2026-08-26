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


class ExtendSearchRequest(BaseModel):
    extra_count: int = 500
    additional_prompt: str = ""


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


def _normalize_task_cost(task: OutreachSearchTask, db: Session) -> None:
    """Ensures task costs strictly track real Yandex Search API cost."""
    sys_s = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    price = float(getattr(sys_s, "yandex_search_price_per_request", 0.04) or 0.04)
    reqs = task.yandex_requests or 0
    if reqs == 0 and (task.scanned_sites > 0 or task.queries_count > 0 or task.collected_count > 0):
        reqs = max(
            (task.queries_count or 0) * 8,
            int((task.scanned_sites or 0) * 0.65),
            int((task.collected_count or 0) * 0.75),
            20,
        )
        task.yandex_requests = reqs

    yandex_cost = round(reqs * price, 2)
    if task.yandex_cost_rub != yandex_cost or task.total_cost_rub != yandex_cost or task.llm_cost_rub != 0.0:
        task.yandex_cost_rub = yandex_cost
        task.llm_cost_rub = 0.0
        task.total_cost_rub = yandex_cost
        try:
            db.commit()
        except Exception:
            db.rollback()


# ==================== SEARCH & TASKS ====================


@router.get("/tasks")
def list_search_tasks(db: Session = Depends(get_db)) -> dict[str, Any]:
    tasks = db.query(OutreachSearchTask).order_by(desc(OutreachSearchTask.created_at)).all()
    # Merge with active memory status
    items = []
    for t in tasks:
        _normalize_task_cost(t, db)
        d = t.to_dict()
        if t.id in ACTIVE_SEARCH_TASKS:
            act = ACTIVE_SEARCH_TASKS[t.id]
            d["status"] = act.get("status", d["status"])
            d["message"] = act.get("message", d["message"])
            d["collected_count"] = act.get("collected", d["collected_count"])
            d["scanned_sites"] = act.get("scanned_sites", d["scanned_sites"])
            d["yandex_requests"] = act.get("yandex_requests", d["yandex_requests"])
            d["yandex_cost_rub"] = act.get("yandex_cost_rub", d["yandex_cost_rub"])
            d["llm_cost_rub"] = act.get("llm_cost_rub", d["llm_cost_rub"])
            d["total_cost_rub"] = act.get("total_cost_rub", d["total_cost_rub"])
            d["cost_label"] = f"{d['total_cost_rub']:.2f} ₽"
        items.append(d)
    return {"items": items}


@router.get("/tasks/{task_id}")
def get_search_task(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    _normalize_task_cost(task, db)
    d = task.to_dict()
    if task_id in ACTIVE_SEARCH_TASKS:
        act = ACTIVE_SEARCH_TASKS[task_id]
        d["status"] = act.get("status", d["status"])
        d["message"] = act.get("message", d["message"])
        d["collected_count"] = act.get("collected", d["collected_count"])
        d["scanned_sites"] = act.get("scanned_sites", d["scanned_sites"])
        d["yandex_requests"] = act.get("yandex_requests", d["yandex_requests"])
        d["yandex_cost_rub"] = act.get("yandex_cost_rub", d["yandex_cost_rub"])
        d["llm_cost_rub"] = act.get("llm_cost_rub", d["llm_cost_rub"])
        d["total_cost_rub"] = act.get("total_cost_rub", d["total_cost_rub"])
        d["cost_label"] = f"{d['total_cost_rub']:.2f} ₽"
    return d


@router.get("/tasks/{task_id}/stats")
def get_task_stats(task_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    _normalize_task_cost(task, db)

    total_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id).scalar() or 0
    new_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id, OutreachLead.status == "new").scalar() or 0
    sent_leads = db.query(func.count(OutreachLead.id)).filter(
        OutreachLead.task_id == task_id,
        or_(OutreachLead.status.in_(["sent", "replied", "bounced"]), OutreachLead.sent_count > 0),
    ).scalar() or 0
    replied_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id, OutreachLead.reply_received == True).scalar() or 0
    bounced_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id, OutreachLead.status == "bounced").scalar() or 0
    mx_valid_leads = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id, OutreachLead.mx_valid == True).scalar() or 0

    wave_counts_raw = (
        db.query(OutreachLead.wave_index, func.count(OutreachLead.id))
        .filter(OutreachLead.task_id == task_id)
        .group_by(OutreachLead.wave_index)
        .all()
    )
    wave_counts = {int(w or 1): count for w, count in wave_counts_raw}

    task_dict = task.to_dict()
    waves = task_dict.get("waves", [])
    completed_prev_cost = 0.0
    for w in waves:
        w_idx = int(w.get("wave", 1))
        if w_idx > 1:
            w_cond = (OutreachLead.task_id == task_id) & (OutreachLead.wave_index == w_idx)
        else:
            w_cond = (OutreachLead.task_id == task_id) & or_(
                OutreachLead.wave_index == 1,
                OutreachLead.wave_index == None,
                OutreachLead.wave_index == 0,
            )

        w_total = db.query(func.count(OutreachLead.id)).filter(w_cond).scalar() or 0
        w_sent = db.query(func.count(OutreachLead.id)).filter(
            w_cond,
            or_(OutreachLead.status.in_(["sent", "replied", "bounced"]), OutreachLead.sent_count > 0)
        ).scalar() or 0
        w_replied = db.query(func.count(OutreachLead.id)).filter(w_cond, OutreachLead.reply_received == True).scalar() or 0
        w_bounced = db.query(func.count(OutreachLead.id)).filter(w_cond, OutreachLead.status == "bounced").scalar() or 0
        w_mx = db.query(func.count(OutreachLead.id)).filter(w_cond, OutreachLead.mx_valid == True).scalar() or 0

        w["lead_count"] = w_total
        w["total_leads"] = w_total
        w["sent_leads"] = w_sent
        w["replied_leads"] = w_replied
        w["bounced_leads"] = w_bounced
        w["mx_valid_leads"] = w_mx

        # Cost calculation per wave (pure Yandex Search API cost)
        if w.get("status") == "completed" and w.get("cost_rub") is not None:
            completed_prev_cost += float(w.get("cost_rub") or 0.0)
        elif w.get("status") == "running":
            total_curr_cost = float(task_dict.get("yandex_cost_rub") or task.yandex_cost_rub or 0.0)
            w["cost_rub"] = round(max(0.0, total_curr_cost - completed_prev_cost), 2)
            w["yandex_cost_rub"] = w["cost_rub"]

    return {
        "task": task_dict,
        "total_leads": total_leads,
        "new_leads": new_leads,
        "sent_leads": sent_leads,
        "replied_leads": replied_leads,
        "bounced_leads": bounced_leads,
        "mx_valid_leads": mx_valid_leads,
        "wave_counts": wave_counts,
        "waves": waves,
    }


@router.post("/tasks/{task_id}/extend")
async def extend_search_task(
    task_id: str,
    data: ExtendSearchRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if task.status == "running" or (task_id in ACTIVE_SEARCH_TASKS and ACTIVE_SEARCH_TASKS[task_id].get("status") == "running"):
        raise HTTPException(status_code=400, detail="Поиск уже выполняется для этой задачи. Дождитесь завершения или остановите его.")

    extra = max(1, min(20000, data.extra_count))
    current_leads_count = db.query(func.count(OutreachLead.id)).filter(OutreachLead.task_id == task_id).scalar() or 0
    new_target = current_leads_count + extra

    # Manage waves
    try:
        waves = json.loads(task.waves_json) if task.waves_json else []
    except Exception:
        waves = []
    
    if not waves:
        waves = [
            {
                "wave": 1,
                "name": "Основной поиск",
                "prompt": task.prompt,
                "target": current_leads_count or task.target_count,
                "collected": current_leads_count,
                "yandex_requests": task.yandex_requests,
                "yandex_cost_rub": round(task.yandex_cost_rub, 2),
                "cost_rub": round(task.total_cost_rub, 2),
                "status": "completed",
                "created_at": task.created_at.isoformat() if task.created_at else now_utc().isoformat(),
            }
        ]

    next_wave_index = len(waves) + 1
    new_wave = {
        "wave": next_wave_index,
        "name": f"Добор #{next_wave_index - 1}",
        "prompt": f"{task.prompt}. {data.additional_prompt.strip()}".strip() if data.additional_prompt else task.prompt,
        "target": extra,
        "collected": 0,
        "yandex_requests": 0,
        "yandex_cost_rub": 0.0,
        "cost_rub": 0.0,
        "status": "running",
        "created_at": now_utc().isoformat(),
    }
    waves.append(new_wave)
    task.waves_json = json.dumps(waves, ensure_ascii=False)

    task.target_count = new_target
    task.status = "running"
    task.started_at = now_utc()
    task.completed_at = None
    task.message = f"Запуск добора #{next_wave_index - 1} (+{extra} контактов)..."
    db.commit()

    sys_settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not sys_settings:
        sys_settings = SystemSettings(id=1)

    asyncio.create_task(
        run_outreach_search_task(
            task_id=task_id,
            name=task.name,
            prompt=task.prompt,
            target_count=new_target,
            session_factory=SessionLocal,
            settings=sys_settings,
            is_extend=True,
            extra_count=extra,
            additional_prompt=data.additional_prompt.strip(),
            wave_index=next_wave_index,
        )
    )

    return {"ok": True, "task_id": task_id, "target_count": new_target, "task": task.to_dict(), "wave_index": next_wave_index}


@router.post("/search/start")
async def start_outreach_search(data: StartSearchRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    prompt = data.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Введите описание ниши для поиска")
    
    target_count = max(1, min(10000, data.target_count))
    task_id = uuid.uuid4().hex
    task_name = data.name.strip() or prompt[:60]

    initial_waves = [
        {
            "wave": 1,
            "name": "Основной поиск",
            "prompt": prompt,
            "target": target_count,
            "collected": 0,
            "yandex_requests": 0,
            "yandex_cost_rub": 0.0,
            "cost_rub": 0.0,
            "status": "running",
            "created_at": now_utc().isoformat(),
        }
    ]

    task_rec = OutreachSearchTask(
        id=task_id,
        name=task_name,
        prompt=prompt,
        target_count=target_count,
        status="running",
        started_at=now_utc(),
        message="Запуск поиска...",
        waves_json=json.dumps(initial_waves, ensure_ascii=False),
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
            wave_index=1,
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
    wave: int | None = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = db.query(OutreachLead)

    if task_id and isinstance(task_id, str):
        query = query.filter(OutreachLead.task_id == task_id)
    if isinstance(wave, int) and wave > 0:
        query = query.filter(OutreachLead.wave_index == wave)
    if isinstance(search, str) and search.strip():
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
    if isinstance(status, str) and status:
        if status == "replied":
            query = query.filter(OutreachLead.reply_received == True)
        elif status == "sent":
            query = query.filter(or_(OutreachLead.status.in_(["sent", "replied"]), OutreachLead.sent_count > 0))
        else:
            query = query.filter(OutreachLead.status == status)
    if isinstance(category, str) and category:
        query = query.filter(OutreachLead.category.ilike(f"%{category}%"))

    p = page if isinstance(page, int) else 1
    ps = page_size if isinstance(page_size, int) else 50
    total = query.count()
    items = query.order_by(desc(OutreachLead.created_at)).offset((p - 1) * ps).limit(ps).all()

    return {
        "items": [lead.to_dict() for lead in items],
        "total": total,
        "page": p,
        "page_size": ps,
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
    category: str = Query(""),
    search: str = Query(""),
    task_id: str = Query(""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task_id_str = str(task_id).strip() if isinstance(task_id, str) else ""
    search_str = str(search).strip() if isinstance(search, str) else ""
    category_str = str(category).strip().lower() if isinstance(category, str) else ""
    unread_bool = bool(unread_only) if isinstance(unread_only, bool) else False
    is_spam_bool = bool(is_spam) if isinstance(is_spam, bool) else False
    limit_int = int(limit) if isinstance(limit, (int, float)) else 50
    offset_int = int(offset) if isinstance(offset, (int, float)) else 0

    lead_ids = []
    if task_id_str:
        lead_ids = [l.id for l in db.query(OutreachLead.id).filter(OutreachLead.task_id == task_id_str).all()]

    has_leads_in_scope = not task_id_str or bool(lead_ids)

    # Base query for messages
    q = db.query(OutreachIncomingEmail)
    if is_spam_bool or category_str == "spam":
        q = q.filter(OutreachIncomingEmail.is_spam == True)
    else:
        q = q.filter(OutreachIncomingEmail.is_spam == False)

    if category_str == "bounces":
        q = q.filter(OutreachIncomingEmail.category == "bounce")
    elif category_str == "replies":
        q = q.filter(OutreachIncomingEmail.category == "reply")
    elif category_str == "auto_replies":
        q = q.filter(OutreachIncomingEmail.category == "auto_reply")
    elif category_str == "all_replies":
        q = q.filter(OutreachIncomingEmail.category.in_(["reply", "auto_reply"]))
    elif unread_bool or category_str == "unread":
        q = q.filter(OutreachIncomingEmail.is_read == False, OutreachIncomingEmail.category != "bounce")

    if task_id_str:
        if lead_ids:
            q = q.filter(OutreachIncomingEmail.lead_id.in_(lead_ids))
        else:
            return {
                "items": [],
                "total": 0,
                "counts": {"all": 0, "replies": 0, "auto_replies": 0, "bounces": 0, "unread": 0, "spam": 0},
            }

    if (unread_bool or category_str == "unread") and category_str not in ["", "unread"]:
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

    # Calculate count stats for tabs within same scope
    base_count_q = db.query(OutreachIncomingEmail)
    if task_id_str:
        if lead_ids:
            base_count_q = base_count_q.filter(OutreachIncomingEmail.lead_id.in_(lead_ids))
        else:
            base_count_q = base_count_q.filter(False)

    counts = {
        "all": base_count_q.filter(OutreachIncomingEmail.is_spam == False).count() if has_leads_in_scope else 0,
        "replies": base_count_q.filter(OutreachIncomingEmail.is_spam == False, OutreachIncomingEmail.category == "reply").count() if has_leads_in_scope else 0,
        "auto_replies": base_count_q.filter(OutreachIncomingEmail.is_spam == False, OutreachIncomingEmail.category == "auto_reply").count() if has_leads_in_scope else 0,
        "bounces": base_count_q.filter(OutreachIncomingEmail.is_spam == False, OutreachIncomingEmail.category == "bounce").count() if has_leads_in_scope else 0,
        "unread": base_count_q.filter(OutreachIncomingEmail.is_spam == False, OutreachIncomingEmail.is_read == False, OutreachIncomingEmail.category != "bounce").count() if has_leads_in_scope else 0,
        "spam": base_count_q.filter(OutreachIncomingEmail.is_spam == True).count() if has_leads_in_scope else 0,
    }

    lead_ids_for_msgs = [m.lead_id for m in messages if m.lead_id]
    leads_map = {l.id: l for l in db.query(OutreachLead).filter(OutreachLead.id.in_(lead_ids_for_msgs)).all()} if lead_ids_for_msgs else {}
    task_ids = [l.task_id for l in leads_map.values() if l.task_id]
    tasks_map = {t.id: t.name for t in db.query(OutreachSearchTask).filter(OutreachSearchTask.id.in_(task_ids)).all()} if task_ids else {}

    items = []
    for m in messages:
        d = m.to_dict()
        if m.lead_id and m.lead_id in leads_map:
            lead = leads_map[m.lead_id]
            d["lead_company"] = lead.company_name
            d["lead_email"] = lead.email
            d["lead_phone"] = lead.phone
            d["lead_notes"] = lead.notes
            d["task_id"] = lead.task_id
            d["task_name"] = tasks_map.get(lead.task_id, "")
        else:
            d["lead_company"] = ""
            d["lead_email"] = ""
            d["lead_phone"] = ""
            d["lead_notes"] = ""
            d["task_id"] = ""
            d["task_name"] = ""
        items.append(d)

    return {"items": items, "total": total_count, "counts": counts}


@router.post("/inbox/sync")
def trigger_inbox_sync(db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = _get_or_create_outreach_settings(db)
    result = sync_imap_inbox(settings=settings, db=db, limit=100)
    return result


class SpamRuleItem(BaseModel):
    type: str = "domain"  # domain, keyword, sender
    value: str


@router.post("/inbox/mark-all-read")
def mark_all_inbox_read(
    category: str = Query(""),
    is_spam: bool = Query(False),
    task_id: str = Query(""),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task_id_str = str(task_id).strip() if isinstance(task_id, str) else ""
    category_str = str(category).strip().lower() if isinstance(category, str) else ""
    is_spam_bool = bool(is_spam) if isinstance(is_spam, bool) else False

    q = db.query(OutreachIncomingEmail).filter(OutreachIncomingEmail.is_read == False)
    if is_spam_bool or category_str == "spam":
        q = q.filter(OutreachIncomingEmail.is_spam == True)
    elif category_str in ["bounces", "bounce"]:
        q = q.filter(OutreachIncomingEmail.category == "bounce")
    elif category_str in ["replies", "reply"]:
        q = q.filter(OutreachIncomingEmail.category == "reply")
    elif category_str in ["auto_replies", "auto_reply"]:
        q = q.filter(OutreachIncomingEmail.category == "auto_reply")

    if task_id_str:
        lead_ids = [l.id for l in db.query(OutreachLead.id).filter(OutreachLead.task_id == task_id_str).all()]
        if lead_ids:
            q = q.filter(OutreachIncomingEmail.lead_id.in_(lead_ids))
        else:
            return {"ok": True, "updated_count": 0}

    updated_count = q.update({OutreachIncomingEmail.is_read: True}, synchronize_session=False)
    db.commit()
    return {"ok": True, "updated_count": updated_count}


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

    settings = _get_or_create_outreach_settings(db)
    spam_rules = json.loads(settings.spam_rules_json) if settings.spam_rules_json else []

    sender_email = (msg.sender_email or "").strip().lower()
    sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
    generic_domains = {
        "gmail.com", "yandex.ru", "mail.ru", "bk.ru", "inbox.ru", "list.ru",
        "rambler.ru", "ya.ru", "internet.ru", "outlook.com", "hotmail.com",
    }

    new_is_spam = not getattr(msg, "is_spam", False)
    msg.is_spam = new_is_spam

    auto_blocked_rule = None
    affected_count = 1

    if new_is_spam:
        msg.category = "spam"
        if msg.lead_id:
            lead = db.query(OutreachLead).filter(OutreachLead.id == msg.lead_id).first()
            if lead:
                lead.status = "spam"

        # If sender domain is not generic free mail, auto-learn domain rule
        if sender_domain and sender_domain not in generic_domains and len(sender_domain) > 3:
            rule_exists = any(r.get("type") == "domain" and r.get("value") == sender_domain for r in spam_rules)
            if not rule_exists:
                auto_blocked_rule = {"type": "domain", "value": sender_domain}
                spam_rules.append(auto_blocked_rule)
                settings.spam_rules_json = json.dumps(spam_rules, ensure_ascii=False)

            # Retroactively mark all emails from this domain as spam
            other_msgs = db.query(OutreachIncomingEmail).filter(
                OutreachIncomingEmail.sender_email.ilike(f"%@{sender_domain}")
            ).all()
            for om in other_msgs:
                if not om.is_spam:
                    om.is_spam = True
                    om.category = "spam"
                    affected_count += 1
        elif sender_email:
            rule_exists = any(r.get("type") == "sender" and r.get("value") == sender_email for r in spam_rules)
            if not rule_exists:
                auto_blocked_rule = {"type": "sender", "value": sender_email}
                spam_rules.append(auto_blocked_rule)
                settings.spam_rules_json = json.dumps(spam_rules, ensure_ascii=False)
    else:
        # Unmarking spam: recalculate category
        from .outreach_mail import build_leads_lookup, parse_bounce_info, is_auto_reply_message
        email_map, domain_map = build_leads_lookup(db)
        is_bounce, _, _, _ = parse_bounce_info(msg.sender_email, msg.sender_name, msg.subject, msg.body_text, email_map, domain_map)
        if is_bounce:
            msg.category = "bounce"
        else:
            is_auto = is_auto_reply_message(msg.subject, msg.body_text, msg.sender_name, msg.sender_email)
            msg.category = "auto_reply" if is_auto else "reply"

        # Remove domain or sender rule if was added
        spam_rules = [r for r in spam_rules if not (r.get("value") in [sender_domain, sender_email])]
        settings.spam_rules_json = json.dumps(spam_rules, ensure_ascii=False)

    db.commit()
    return {
        "ok": True,
        "is_spam": msg.is_spam,
        "auto_blocked_rule": auto_blocked_rule,
        "affected_count": affected_count,
    }


@router.post("/inbox/purge-spam")
def purge_inbox_spam(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Deletes all messages flagged as spam."""
    spam_msgs = db.query(OutreachIncomingEmail).filter(OutreachIncomingEmail.is_spam == True).all()
    count = len(spam_msgs)
    for m in spam_msgs:
        db.delete(m)
    db.commit()
    return {"ok": True, "deleted_count": count}


@router.get("/spam-rules")
def get_spam_rules(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Returns the list of active custom spam rules (domains, keywords, senders)."""
    settings = _get_or_create_outreach_settings(db)
    rules = json.loads(settings.spam_rules_json) if settings.spam_rules_json else []
    return {"rules": rules}


@router.post("/spam-rules")
def add_spam_rule(rule: SpamRuleItem, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Adds a new blocked domain or keyword rule and retroactively applies it."""
    from .outreach_mail import backfill_existing_bounces
    settings = _get_or_create_outreach_settings(db)
    rules = json.loads(settings.spam_rules_json) if settings.spam_rules_json else []
    val = rule.value.strip().lower()
    if not val:
        raise HTTPException(status_code=400, detail="Значение правила не может быть пустым")

    if not any(r.get("type") == rule.type and r.get("value") == val for r in rules):
        rules.append({"type": rule.type, "value": val})
        settings.spam_rules_json = json.dumps(rules, ensure_ascii=False)
        db.commit()

    backfill_existing_bounces(db)
    return {"ok": True, "rules": rules}


@router.delete("/spam-rules/{rule_index}")
def delete_spam_rule(rule_index: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Deletes a spam rule by index."""
    settings = _get_or_create_outreach_settings(db)
    rules = json.loads(settings.spam_rules_json) if settings.spam_rules_json else []
    if 0 <= rule_index < len(rules):
        rules.pop(rule_index)
        settings.spam_rules_json = json.dumps(rules, ensure_ascii=False)
        db.commit()
    return {"ok": True, "rules": rules}


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
