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


def _send_smtp_sync(msg: EmailMessage, settings: OutreachSettings, to_email: str) -> tuple[bool, str]:
    import socks
    import ssl
    import smtplib

    smtp_host = (settings.smtp_host or "smtp.jino.ru").strip()
    port = settings.smtp_port or 465
    user = (settings.smtp_user or "info@tenderlex.ru").strip()
    password = settings.smtp_password or ""

    # 1. Try SOCKS5 Proxy 127.0.0.1:1080 (Primary for VPS bypass)
    try:
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, "127.0.0.1", 1080)
        s.settimeout(15)
        s.connect((smtp_host, port))

        use_ssl = settings.smtp_use_ssl or port == 465 or "jino.ru" in smtp_host
        if use_ssl:
            ctx = ssl.create_default_context()
            ss = ctx.wrap_socket(s, server_hostname=smtp_host)
            smtp = smtplib.SMTP_SSL()
            smtp.sock = ss
            smtp.file = ss.makefile("rb")
            smtp.getreply()
        else:
            smtp = smtplib.SMTP()
            smtp.sock = s
            smtp.file = s.makefile("rb")
            smtp.getreply()
            if settings.smtp_use_tls or port == 587:
                smtp.starttls()

        if user and password:
            smtp.login(user, password)
        smtp.send_message(msg)
        smtp.close()
        return True, ""
    except Exception as pe:
        logger.warning(f"SOCKS5 SMTP attempt failed: {pe}, trying direct SMTP fallback...")

    # 2. Fallback to direct SMTP
    try:
        if settings.smtp_use_ssl or port == 465:
            with smtplib.SMTP_SSL(smtp_host, port, timeout=15) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, port, timeout=15) as smtp:
                if settings.smtp_use_tls or port == 587:
                    smtp.starttls()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
        return True, ""
    except Exception as e:
        logger.error(f"Email send error to {to_email}: {e}")
        return False, f"SMTP: {str(e)}"


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

    # 2. SMTP via threadpool
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

    return await asyncio.to_thread(_send_smtp_sync, msg, settings, to_email)


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

        subject_template = campaign.subject
        body_text_template = campaign.body_text
        body_html_template = campaign.body_html
        delay_seconds = max(1.0, float(campaign.delay_seconds or settings.delay_seconds or 2.0))
        aud_type = getattr(campaign, "audience_type", "new") or "new"

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
            if aud_type in ["unanswered", "follow_up"]:
                q = q.filter(
                    OutreachLead.task_id == campaign.task_id_filter,
                    OutreachLead.status == "sent",
                    OutreachLead.reply_received == False,
                )
            elif aud_type == "all":
                q = q.filter(OutreachLead.task_id == campaign.task_id_filter)
            else:
                q = q.filter(OutreachLead.task_id == campaign.task_id_filter, OutreachLead.status.in_(["new", "queued"]))
        elif campaign.category_filter:
            if aud_type in ["unanswered", "follow_up"]:
                q = q.filter(
                    OutreachLead.category.ilike(f"%{campaign.category_filter}%"),
                    OutreachLead.status == "sent",
                    OutreachLead.reply_received == False,
                )
            else:
                q = q.filter(OutreachLead.category.ilike(f"%{campaign.category_filter}%"), OutreachLead.status.in_(["new", "queued"]))
        else:
            if aud_type in ["unanswered", "follow_up"]:
                q = q.filter(OutreachLead.status == "sent", OutreachLead.reply_received == False)
            else:
                q = q.filter(OutreachLead.status.in_(["new", "queued"]))

        leads_data = [
            {
                "id": l.id,
                "email": l.email,
                "company_name": l.company_name or "",
                "city": l.city or "",
                "phone": l.phone or "",
                "website": l.website or "",
                "inn": l.inn or "",
            }
            for l in q.all()
        ]
        if not campaign.total_recipients or campaign.total_recipients == 0:
            campaign.total_recipients = len(leads_data)
        elif campaign.total_recipients < len(leads_data) + (campaign.sent_count or 0) + (campaign.failed_count or 0):
            campaign.total_recipients = (campaign.sent_count or 0) + (campaign.failed_count or 0) + len(leads_data)
        campaign.status = "running"
        if not campaign.started_at:
            campaign.started_at = now_utc()
        campaign.error_message = ""
        db.commit()

    for idx, lead_item in enumerate(leads_data):
        # Check if cancelled/paused
        with session_factory() as db:
            c: OutreachCampaign | None = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
            if not c or c.status in ["paused", "stopped"]:
                return
            current_settings = db.query(OutreachSettings).filter(OutreachSettings.id == 1).first() or OutreachSettings(id=1)

        # Render templates with lead mock object
        mock_lead = OutreachLead(
            id=lead_item["id"],
            email=lead_item["email"],
            company_name=lead_item["company_name"],
            city=lead_item["city"],
            phone=lead_item["phone"],
            website=lead_item["website"],
            inn=lead_item["inn"],
        )
        subj = render_template_text(subject_template, mock_lead)
        text_body = render_template_text(body_text_template, mock_lead)
        html_body = render_template_text(body_html_template, mock_lead) if body_html_template else ""

        success, err = await send_single_email(
            to_email=lead_item["email"],
            subject=subj,
            body_text=text_body,
            body_html=html_body,
            settings=current_settings,
        )

        with session_factory() as db:
            db_lead = db.query(OutreachLead).filter(OutreachLead.id == lead_item["id"]).first()
            if db_lead:
                if success:
                    db_lead.status = "sent"
                    db_lead.sent_count = (db_lead.sent_count or 0) + 1
                    db_lead.last_sent_at = now_utc()
                else:
                    db_lead.notes = f"Ошибка: {err}"[:150]

            log = OutreachSendLog(
                campaign_id=campaign_id,
                lead_id=lead_item["id"],
                recipient_email=lead_item["email"],
                recipient_company=lead_item["company_name"],
                from_email=current_settings.from_email,
                subject=subj,
                status="sent" if success else "failed",
                error_message=err,
            )
            db.add(log)

            c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
            if c:
                if success:
                    c.sent_count = (c.sent_count or 0) + 1
                else:
                    c.failed_count = (c.failed_count or 0) + 1
                c.current_index = idx + 1
            db.commit()

        await asyncio.sleep(delay_seconds)

    with session_factory() as db:
        c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
        if c and c.status == "running":
            c.status = "completed"
            c.completed_at = now_utc()
            db.commit()


RE_GENERIC_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE)
RE_BOUNCE_SENDER = re.compile(r"mailer-daemon|postmaster|antispam|ksmg|mail delivery", re.IGNORECASE)
RE_BOUNCE_SUBJECT = re.compile(r"undelivered|не удается доставить|delivery status|failure|undeliverable|returned to sender|mail delivery failed|не удалось доставить", re.IGNORECASE)
RE_DIAGNOSTIC_REASON = re.compile(r"(?:said:|Diagnostic-Code:.*?|Status:.*?|error:)\s*([0-9]{3}[^\n\r]+|Access Denied|User unknown|Mailbox unavailable[^\n\r]*)", re.IGNORECASE)


def parse_bounce_info(sender_email: str, sender_name: str, subject: str, body_text: str, leads_map: dict[str, str]) -> tuple[bool, str | None, str, str]:
    """
    Checks if email is an NDR / delivery failure, extracts target lead email, lead_id and failure reason.
    Returns (is_bounce, matched_lead_id, target_email, failure_reason).
    """
    is_bounce = False
    sender_clean = sender_email.lower().strip()
    name_clean = sender_name.lower().strip()
    subj_clean = subject.lower().strip()
    body_clean = body_text.lower()

    if RE_BOUNCE_SENDER.search(sender_clean) or RE_BOUNCE_SENDER.search(name_clean) or RE_BOUNCE_SUBJECT.search(subj_clean):
        is_bounce = True
    elif "this is the mail system" in body_clean or "permanent error" in body_clean or "could not be delivered" in body_clean:
        is_bounce = True

    if not is_bounce:
        return False, None, "", ""

    matched_lead_id = None
    target_email = ""
    for raw_em in RE_GENERIC_EMAIL.findall(body_text):
        cand = raw_em.lower().rstrip('.,;:>)')
        if cand and cand != "info@tenderlex.ru" and cand != sender_clean.rstrip('.,;:>)'):
            if cand in leads_map:
                matched_lead_id = leads_map[cand]
                target_email = cand
                break

    reason_m = RE_DIAGNOSTIC_REASON.search(body_text)
    reason = reason_m.group(1).strip() if reason_m else "Не доставлено (ошибка почтового сервера получателя)"
    reason = re.sub(r"\s+", " ", reason)[:150]
    return True, matched_lead_id, target_email, reason


def backfill_existing_bounces(db: Session) -> int:
    """Retroactively identifies and links existing unlinked bounces in outreach_inbox."""
    leads_map = {r[0].lower().rstrip('.'): r[1] for r in db.query(OutreachLead.email, OutreachLead.id).all()}
    unlinked = db.query(OutreachIncomingEmail).all()
    updated_count = 0

    for msg in unlinked:
        body = msg.body_text or ""
        is_bounce, matched_id, target_em, reason = parse_bounce_info(
            msg.sender_email, msg.sender_name, msg.subject, body, leads_map
        )
        if is_bounce:
            msg.category = "bounce"
            if matched_id and not msg.lead_id:
                msg.lead_id = matched_id
                lead = db.query(OutreachLead).filter(OutreachLead.id == matched_id).first()
                if lead:
                    lead.status = "bounced"
                    lead.notes = f"Ошибка доставки: {reason}"
                updated_count += 1
            elif msg.lead_id and not msg.category:
                msg.category = "bounce"
                updated_count += 1
        else:
            if not msg.category:
                subj_low = (msg.subject or "").lower()
                body_low = body.lower()
                if "автоматический ответ" in subj_low or "automatic reply" in subj_low or "обращение" in subj_low or "заявка принята" in body_low:
                    msg.category = "auto_reply"
                else:
                    msg.category = "reply"

    if updated_count > 0:
        db.commit()
    return updated_count


def sync_imap_inbox(settings: OutreachSettings, db: Session, limit: int = 100) -> dict[str, Any]:
    """Syncs incoming replies and bounce notifications from info@tenderlex.ru via IMAP."""
    imap_host = (settings.imap_host or "127.0.0.1").strip()
    imap_port = settings.imap_port or 19993
    imap_user = (settings.imap_user or settings.from_email or "info@tenderlex.ru").strip()
    imap_pass = (settings.imap_password or "").strip()

    if not imap_pass:
        return {"success": False, "error": "Пароль IMAP не указан в настройках", "new_messages": 0}

    # Run backfill on existing unlinked records
    try:
        backfill_existing_bounces(db)
    except Exception as be:
        logger.warning(f"Error backfilling existing bounces: {be}")

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
        leads_map = {r[0].lower().rstrip('.'): r[1] for r in db.query(OutreachLead.email, OutreachLead.id).all()}

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

            is_bounce, matched_lead_id, target_em, bounce_reason = parse_bounce_info(
                sender_email, sender_name, subject, body_text, leads_map
            )

            lead_id = leads_map.get(sender_email.rstrip('.')) or matched_lead_id
            
            category = "bounce" if is_bounce else "reply"
            if not is_bounce:
                subj_low = subject.lower()
                body_low = body_text.lower()
                if "автоматический ответ" in subj_low or "automatic reply" in subj_low or "обращение" in subj_low or "заявка принята" in body_low:
                    category = "auto_reply"

            inbound = OutreachIncomingEmail(
                message_id=message_id_header,
                sender_email=sender_email,
                sender_name=sender_name or from_header,
                recipient_email=settings.from_email or "info@tenderlex.ru",
                subject=subject,
                body_text=body_text[:10000],
                body_html=body_html[:50000],
                category=category,
                date_received=dt_utc,
                lead_id=lead_id,
            )
            db.add(inbound)

            if lead_id:
                lead_obj = db.query(OutreachLead).filter(OutreachLead.id == lead_id).first()
                if lead_obj:
                    if is_bounce:
                        lead_obj.status = "bounced"
                        lead_obj.notes = f"Ошибка доставки: {bounce_reason}"
                    else:
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
