from __future__ import annotations

import asyncio
import email
from email.header import decode_header
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
import html
import imaplib
import json
import logging
import re
import smtplib
import socket
import ssl
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from .outreach_models import (
    OutreachCampaign,
    OutreachIncomingEmail,
    OutreachLead,
    OutreachSendLog,
    OutreachSettings,
    now_utc,
)

logger = logging.getLogger(__name__)

ACTIVE_CAMPAIGN_TASKS: dict[str, asyncio.Task] = {}


def _decode_mime_header(header_value: str | None) -> str:
    if not header_value:
        return ""
    parts = decode_header(header_value)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(enc or "utf-8", errors="replace"))
            except Exception:
                decoded.append(part.decode("latin1", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def render_template_text(template_str: str, lead: OutreachLead | None) -> str:
    """Replaces variables in email template."""
    if not template_str:
        return ""
    if not lead:
        # Fallback when lead is None: remove or simplify placeholders
        res = template_str
        for tag in ["{company}", "{company_name}", "{компания}", "{организация}", "{name}", "{имя}", "{лпр}", "{телефон}", "{phone}", "{сайт}", "{website}", "{site}", "{город}", "{city}", "{email}", "{почта}", "{инн}", "{inn}"]:
            res = res.replace(tag, "")
        return res

    company = lead.company_name or "Компания"
    city = lead.city or ""
    site = lead.website or ""
    phone = lead.phone or ""
    email_val = lead.email or ""
    inn_val = getattr(lead, "inn", "") or ""
    name = lead.company_name or "Коллеги"

    replacements = {
        "{company}": company,
        "{company_name}": company,
        "{компания}": company,
        "{организация}": company,
        "{name}": name,
        "{имя}": name,
        "{лпр}": name,
        "{город}": city,
        "{city}": city,
        "{сайт}": site,
        "{website}": site,
        "{site}": site,
        "{телефон}": phone,
        "{phone}": phone,
        "{email}": email_val,
        "{почта}": email_val,
        "{инн}": inn_val,
        "{inn}": inn_val,
    }

    res = template_str
    for tag, val in replacements.items():
        res = res.replace(tag, val)
    return res


async def send_single_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str,
    settings: OutreachSettings,
) -> tuple[bool, str]:
    """Sends email via Relay VPS or direct SMTP."""
    from_name = settings.from_name or "TenderLex"
    from_email = settings.from_email or "info@tenderlex.ru"

    # 1. Relay VPS (Russian Post Relay on VPS 79.133.182.215)
    relay_url = (settings.relay_url or "").strip()
    relay_key = (settings.relay_api_key or "").strip()
    if relay_url and relay_key:
        payload = {
            "to": to_email,
            "subject": subject,
            "html": body_html or f"<div style='font-family:sans-serif;font-size:14px;line-height:1.6;white-space:pre-wrap;'>{html.escape(body_text)}</div>",
            "text": body_text,
            "from_name": from_name,
            "from_email": from_email,
            "reply_to": settings.reply_to or from_email,
            "attachments": [],
        }
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(
                    f"{relay_url.rstrip('/')}/send",
                    headers={"Authorization": f"Bearer {relay_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict) and data.get("success"):
                        return True, ""
                    return False, f"Relay: {data.get('error', 'unknown error')}"
                return False, f"Relay HTTP {res.status_code}: {res.text[:150]}"
        except Exception as e:
            return False, f"Relay: {str(e)}"

    # 2. SMTP fallback
    smtp_host = (settings.smtp_host or "").strip()
    if not smtp_host:
        return False, "Neither Relay URL nor SMTP Host configured"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    if settings.reply_to:
        msg["Reply-To"] = settings.reply_to

    if body_text:
        msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    elif not body_text:
        msg.set_content("Здравствуйте!")

    port = settings.smtp_port or 587
    try:
        # 1. Try Russian SOCKS5 Proxy 127.0.0.1:1080
        sent = False
        try:
            import socks
            socks.set_default_proxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 1080)
            orig_socket = socket.socket
            socket.socket = socks.socksocket
            try:
                use_ssl = settings.smtp_use_ssl or port == 465 or "jino.ru" in smtp_host
                target_port = 465 if use_ssl else port
                if use_ssl:
                    with smtplib.SMTP_SSL(smtp_host, target_port, timeout=15) as smtp:
                        smtp.ehlo()
                        if settings.smtp_user and settings.smtp_password:
                            smtp.login(settings.smtp_user, settings.smtp_password)
                        smtp.send_message(msg)
                else:
                    with smtplib.SMTP(smtp_host, target_port, timeout=15) as smtp:
                        if settings.smtp_use_tls or target_port == 587:
                            smtp.ehlo()
                            smtp.starttls()
                            smtp.ehlo()
                        if settings.smtp_user and settings.smtp_password:
                            smtp.login(settings.smtp_user, settings.smtp_password)
                        smtp.send_message(msg)
                sent = True
            finally:
                socket.socket = orig_socket
        except Exception as pe:
            logger.debug(f"Proxy SMTP error: {pe}")

        if sent:
            return True, ""

        # 2. Fallback to direct SMTP
        if settings.smtp_use_ssl or port == 465:
            with smtplib.SMTP_SSL(smtp_host, port, timeout=15) as smtp:
                if settings.smtp_user and settings.smtp_password:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, port, timeout=15) as smtp:
                if settings.smtp_use_tls or port == 587:
                    smtp.starttls()
                if settings.smtp_user and settings.smtp_password:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        return True, ""
    except Exception as e:
        return False, f"SMTP: {str(e)}"


async def run_campaign_worker(campaign_id: str, session_factory: Any) -> None:
    """Processes campaign email queue in background."""
    with session_factory() as db:
        campaign: OutreachCampaign | None = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
        if not campaign:
            return

        settings: OutreachSettings = db.query(OutreachSettings).filter(OutreachSettings.id == 1).first()
        if not settings:
            settings = OutreachSettings(id=1)
            db.add(settings)
            db.commit()

        # Eligible leads
        q = db.query(OutreachLead).filter(
            OutreachLead.mx_valid == True,
        )
        if getattr(campaign, "selected_lead_ids", None):
            try:
                ids = json.loads(campaign.selected_lead_ids)
                if ids:
                    q = q.filter(OutreachLead.id.in_(ids))
            except Exception:
                pass
        elif getattr(campaign, "task_id_filter", None):
            q = q.filter(OutreachLead.task_id == campaign.task_id_filter, OutreachLead.status.in_(["new", "queued"]))
        elif campaign.category_filter:
            q = q.filter(OutreachLead.category.ilike(f"%{campaign.category_filter}%"), OutreachLead.status.in_(["new", "queued"]))
        else:
            q = q.filter(OutreachLead.status.in_(["new", "queued"]))

        leads = q.all()
        campaign.total_recipients = len(leads)
        campaign.status = "running"
        campaign.started_at = now_utc()
        campaign.error_message = ""
        db.commit()

    for idx, lead in enumerate(leads):
        # Check if cancelled/paused
        with session_factory() as db:
            c: OutreachCampaign | None = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
            if not c or c.status in ["paused", "stopped"]:
                return

        subj = render_template_text(campaign.subject, lead)
        text_body = render_template_text(campaign.body_text, lead)
        html_body = render_template_text(campaign.body_html, lead) if campaign.body_html else ""

        success, err = await send_single_email(
            to_email=lead.email,
            subject=subj,
            body_text=text_body,
            body_html=html_body,
            settings=settings,
        )

        with session_factory() as db:
            db_lead = db.query(OutreachLead).filter(OutreachLead.id == lead.id).first()
            if db_lead:
                if success:
                    db_lead.status = "sent"
                    db_lead.sent_count += 1
                    db_lead.last_sent_at = now_utc()
                else:
                    db_lead.notes = f"Ошибка: {err}"[:150]

            log = OutreachSendLog(
                campaign_id=campaign_id,
                lead_id=lead.id,
                recipient_email=lead.email,
                recipient_company=lead.company_name,
                from_email=settings.from_email,
                subject=subj,
                status="sent" if success else "failed",
                error_message=err,
            )
            db.add(log)

            c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
            if c:
                if success:
                    c.sent_count += 1
                else:
                    c.failed_count += 1
                c.current_index = idx + 1
            db.commit()

        delay = max(1.0, float(campaign.delay_seconds or settings.delay_seconds or 2.0))
        await asyncio.sleep(delay)

    with session_factory() as db:
        c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
        if c and c.status == "running":
            c.status = "completed"
            c.completed_at = now_utc()
            db.commit()


def sync_imap_inbox(settings: OutreachSettings, db: Session, limit: int = 100) -> dict[str, Any]:
    """Syncs incoming replies from info@tenderlex.ru via IMAP."""
    imap_host = (settings.imap_host or "127.0.0.1").strip()
    imap_port = settings.imap_port or 19993
    imap_user = (settings.imap_user or settings.from_email or "info@tenderlex.ru").strip()
    imap_pass = (settings.imap_password or "").strip()

    if not imap_pass:
        return {"success": False, "error": "Пароль IMAP не указан в настройках", "new_messages": 0}

    try:
        if settings.imap_use_ssl or imap_port in (993, 19993):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            client = imaplib.IMAP4_SSL(imap_host, imap_port, ssl_context=ctx)
        else:
            client = imaplib.IMAP4(imap_host, imap_port)

        client.login(imap_user, imap_pass)
        client.select("INBOX")

        typ, data = client.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            client.logout()
            return {"success": True, "new_messages": 0, "message": "Ящик пуст"}

        msg_ids = data[0].split()
        recent_ids = msg_ids[-limit:] if len(msg_ids) > limit else msg_ids

        existing_msg_ids = {r[0] for r in db.query(OutreachIncomingEmail.message_id).filter(OutreachIncomingEmail.message_id != "").all()}
        leads_map = {r[0].lower(): r[1] for r in db.query(OutreachLead.email, OutreachLead.id).all()}

        new_count = 0
        for m_id in reversed(recent_ids):
            typ, m_data = client.fetch(m_id, "(RFC822)")
            if typ != "OK" or not m_data or not m_data[0]:
                continue

            raw_email = m_data[0][1]
            if not isinstance(raw_email, bytes):
                continue

            msg = email.message_from_bytes(raw_email)
            message_id_header = msg.get("Message-ID", "").strip()

            if message_id_header and message_id_header in existing_msg_ids:
                continue

            from_header = _decode_mime_header(msg.get("From", ""))
            sender_name, sender_email = parseaddr(from_header)
            sender_email = sender_email.strip().lower()

            subject = _decode_mime_header(msg.get("Subject", "Без темы"))

            date_tuple = email.utils.parsedate_tz(msg.get("Date"))
            if date_tuple:
                dt_utc = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple), tz=timezone.utc)
            else:
                dt_utc = now_utc()

            body_text = ""
            body_html = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    if "attachment" in content_disposition:
                        continue
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        text_content = payload.decode(charset, errors="replace")
                        if content_type == "text/plain" and not body_text:
                            body_text = text_content
                        elif content_type == "text/html" and not body_html:
                            body_html = text_content
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    text_content = payload.decode(charset, errors="replace")
                    if msg.get_content_type() == "text/html":
                        body_html = text_content
                    else:
                        body_text = text_content

            lead_id = leads_map.get(sender_email)

            inbound = OutreachIncomingEmail(
                message_id=message_id_header,
                sender_email=sender_email,
                sender_name=sender_name or from_header,
                recipient_email=settings.from_email or "info@tenderlex.ru",
                subject=subject,
                body_text=body_text[:10000],
                body_html=body_html[:50000],
                date_received=dt_utc,
                lead_id=lead_id,
            )
            db.add(inbound)

            if lead_id:
                lead_obj = db.query(OutreachLead).filter(OutreachLead.id == lead_id).first()
                if lead_obj:
                    lead_obj.reply_received = True
                    lead_obj.status = "replied"

            if message_id_header:
                existing_msg_ids.add(message_id_header)
            new_count += 1

        db.commit()
        client.logout()
        return {"success": True, "new_messages": new_count}
    except Exception as e:
        logger.error(f"IMAP sync error: {e}")
        return {"success": False, "error": str(e), "new_messages": 0}
