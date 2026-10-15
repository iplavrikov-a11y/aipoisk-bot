"""Public, signed opt-out endpoint for TenderLex commercial outreach."""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import SessionLocal
from .outreach_models import OutreachLead
from .outreach_suppression import record_shared_suppression, verify_unsubscribe_token


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/outreach", tags=["outreach-public"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _valid_token_or_400(email: str, token: str) -> str:
    clean_email = (email or "").strip().lower()
    if not clean_email or not token or not verify_unsubscribe_token(clean_email, token):
        raise HTTPException(status_code=400, detail="Недействительная ссылка отписки.")
    return clean_email


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    response = HTMLResponse(
        f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)}</title></head><body><main><h1>{html.escape(title)}</h1>{body}</main></body></html>",
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/unsubscribe", response_class=HTMLResponse)
def confirm_unsubscribe(email: str = "", token: str = "") -> HTMLResponse:
    _valid_token_or_400(email, token)
    escaped_email = html.escape(email, quote=True)
    escaped_token = html.escape(token, quote=True)
    return _page(
        "Подтвердите отписку",
        "<p>Мы прекратим коммерческие рассылки TenderLex на этот адрес.</p>"
        "<form method='post' action='/api/outreach/unsubscribe'>"
        f"<input type='hidden' name='email' value='{escaped_email}'>"
        f"<input type='hidden' name='token' value='{escaped_token}'>"
        "<button type='submit'>Отписаться</button></form>",
    )


@router.post("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(email: str = Form(""), token: str = Form(""), db: Session = Depends(get_db)) -> HTMLResponse:
    clean_email = _valid_token_or_400(email, token)

    leads = db.query(OutreachLead).filter(func.lower(OutreachLead.email) == clean_email).all()
    for lead in leads:
        lead.status = "unsubscribed"
        lead.mx_valid = False
    db.commit()

    try:
        record_shared_suppression(clean_email, "unsubscribed", "tenderlex_public_unsubscribe")
    except Exception:
        logger.exception("Could not mirror public outreach unsubscribe to shared suppression")
        return _page("Отписка обрабатывается", "<p>Повторите запрос позже.</p>", status_code=503)

    return _page("Вы отписаны", "<p>Коммерческие рассылки TenderLex больше не будут приходить на этот адрес.</p>")
