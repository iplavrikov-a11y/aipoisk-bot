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


DISPOSABLE_DOMAINS = {
    "tempmail.com", "mailinator.com", "10minutemail.com", "trashmail.com", "guerrillamail.com",
    "yopmail.com", "sharklasers.com", "dispostable.com", "getairmail.com", "throwawaymail.com",
    "temp-mail.org", "fakeinbox.com", "burnermail.io", "mytemp.email", "temp-mail.io"
}


def render_spintax(text: str) -> str:
    """Recursively evaluates spintax syntax like {opt1|opt2|opt3} (only braces containing '|') to generate randomized text variations."""
    if not text or "{" not in text or "|" not in text:
        return text or ""
    import random
    pattern = re.compile(r"\{([^{}]+?\|[^{}]+?)\}")
    res = text
    for _ in range(6):
        if not pattern.search(res):
            break
        res = pattern.sub(lambda m: random.choice(m.group(1).split("|")), res)
    return res


def render_template_text(template_str: str, lead: OutreachLead | None) -> str:
    """Evaluates spintax and replaces variables in email template."""
    if not template_str:
        return ""
    
    # 1. Evaluate spintax variations first
    res = render_spintax(template_str)

    if not lead:
        # Fallback when lead is None: remove or simplify placeholders
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


async def verify_email_deliverability(email_str: str) -> tuple[bool, str]:
    """Deep deliverability check: syntax, disposable domains, MX records, and safe mailbox ping."""
    from .outreach_search import _clean_email
    cleaned = _clean_email(email_str)
    if not cleaned:
        return False, "Некорректный синтаксис, плейсхолдер или адрес техподдержки"

    user, domain = cleaned.split("@", 1)
    if domain in DISPOSABLE_DOMAINS:
        return False, "Одноразовый почтовый сервис"

    # 1. Check MX records
    try:
        from .supplier_search import email_has_valid_mx
        has_mx = await asyncio.wait_for(email_has_valid_mx(cleaned), timeout=2.5)
        if not has_mx:
            return False, "Отсутствуют валидные MX-записи почтового домена"
    except Exception as e:
        logger.debug(f"MX check error for {cleaned}: {e}")

    # 2. Fast direct SMTP Handshake check (for domains with open port 25)
    try:
        def _ping_smtp(target_email: str, target_domain: str) -> tuple[bool, str]:
            import dns.resolver
            import smtplib

            try:
                records = dns.resolver.resolve(target_domain, "MX", lifetime=2.0)
                mx_hosts = sorted([(r.preference, str(r.exchange).rstrip(".")) for r in records])
                if not mx_hosts:
                    return True, "MX OK"
                primary_mx = mx_hosts[0][1]
            except Exception:
                return True, "MX OK"

            try:
                with smtplib.SMTP(primary_mx, 25, timeout=2.5) as server:
                    server.helo("mail.tenderlex.ru")
                    server.mail("check@tenderlex.ru")
                    code, resp = server.rcpt(target_email)
                    resp_str = resp.decode("utf-8", errors="ignore") if isinstance(resp, bytes) else str(resp)
                    if code in (550, 551, 552, 553, 554):
                        return False, f"Почтовый ящик отклонен (SMTP {code}: {resp_str[:80]})"
                    return True, "Адрес подтвержден"
            except Exception:
                return True, "MX подтвержден"

        return await asyncio.to_thread(_ping_smtp, cleaned, domain)
    except Exception:
        return True, "MX подтвержден"


async def send_single_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str,
    settings: OutreachSettings,
) -> tuple[bool, str]:
    """Sends email via Relay VPS or direct SMTP with anti-spam deliverability headers."""
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
            "headers": {
                "List-Unsubscribe": f"<mailto:{from_email}?subject=Unsubscribe>, <https://tenderlex.ru/cabinet?unsubscribe={to_email}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                "Precedence": "bulk",
                "X-Auto-Response-Suppress": "OOF, AutoReply",
            },
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

    # Normalize Cyrillic/IDN domains to ASCII punycode for reliable SMTP transport
    normalized_to = to_email.strip()
    if "@" in normalized_to:
        u_part, d_part = normalized_to.split("@", 1)
        try:
            if any(ord(c) > 127 for c in d_part):
                d_part = d_part.encode("idna").decode("ascii")
                normalized_to = f"{u_part}@{d_part}"
        except Exception:
            pass

    # 2. SMTP via threadpool with RFC anti-spam deliverability headers
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = normalized_to
    if settings.reply_to:
        msg["Reply-To"] = settings.reply_to
    msg["List-Unsubscribe"] = f"<mailto:{from_email}?subject=Unsubscribe>, <https://tenderlex.ru/cabinet?unsubscribe={normalized_to}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["Precedence"] = "bulk"
    msg["X-Auto-Response-Suppress"] = "OOF, AutoReply"

    if body_text:
        msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    elif not body_text:
        msg.set_content("Здравствуйте!")

    return await asyncio.to_thread(_send_smtp_sync, msg, settings, normalized_to)


async def run_campaign_worker(campaign_id: str, session_factory: Any) -> None:
    """Processes campaign email queue in background with pre-flight check, bounce suppression, and jitter."""
    import random

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

        # Eligible leads (strictly exclude bounced/invalid leads)
        q = db.query(OutreachLead).filter(
            OutreachLead.mx_valid == True,
            OutreachLead.status.notin_(["bounced", "invalid", "irrelevant"]),
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

        # Pre-flight verify deliverability
        is_deliverable, deliverable_reason = await verify_email_deliverability(lead_item["email"])
        if not is_deliverable:
            logger.warning(f"Skipping undeliverable lead {lead_item['email']}: {deliverable_reason}")
            with session_factory() as db:
                db_lead = db.query(OutreachLead).filter(OutreachLead.id == lead_item["id"]).first()
                if db_lead:
                    db_lead.status = "invalid"
                    db_lead.mx_valid = False
                    db_lead.notes = f"Предстартовая валидация: {deliverable_reason}"[:150]
                c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
                if c:
                    c.failed_count = (c.failed_count or 0) + 1
                    c.current_index = idx + 1
                db.commit()
            continue

        # Render templates with lead mock object (Spintax evaluated per-email)
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
                    err_low = err.lower()
                    # Auto-suppress bounce
                    if any(k in err_low for k in ["550", "no such user", "mailbox unavailable", "user unknown", "invalid mailbox", "disabled", "does not exist"]):
                        db_lead.status = "bounced"
                        db_lead.mx_valid = False
                        db_lead.notes = f"Авто-подавление (550): {err}"[:150]
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

        # Adaptive jitter delay (random ±25% to prevent robotic spam signatures)
        jitter_delay = max(1.0, delay_seconds * random.uniform(0.85, 1.35))
        await asyncio.sleep(jitter_delay)

    with session_factory() as db:
        c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
        if c and c.status == "running":
            c.status = "completed"
            c.completed_at = now_utc()
            db.commit()


RE_GENERIC_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE)
RE_GENERIC_URL = re.compile(r"(?:https?://|www\.)[a-zA-Z0-9-.]+\.[a-zA-Z]{2,}", re.IGNORECASE)
RE_BOUNCE_SENDER = re.compile(r"mailer-daemon|postmaster|antispam|ksmg|mail delivery", re.IGNORECASE)
RE_BOUNCE_SUBJECT = re.compile(r"undelivered|не удается доставить|delivery status|failure|undeliverable|returned to sender|mail delivery failed|не удалось доставить", re.IGNORECASE)
RE_DIAGNOSTIC_REASON = re.compile(r"(?:said:|Diagnostic-Code:.*?|Status:.*?|error:)\s*([0-9]{3}[^\n\r]+|Access Denied|User unknown|Mailbox unavailable[^\n\r]*)", re.IGNORECASE)

GENERIC_EMAIL_DOMAINS = {
    "mail.ru", "bk.ru", "inbox.ru", "list.ru", "yandex.ru", "ya.ru",
    "gmail.com", "rambler.ru", "internet.ru", "ro.ru", "mail.com",
    "outlook.com", "icloud.com", "hotmail.com", "yahoo.com"
}


def clean_domain_name(val: str) -> str:
    if not val:
        return ""
    s = val.lower().strip()
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\.", "", s)
    s = s.split("/")[0].split("@")[-1].split(":")[0].strip().rstrip(".")
    return s


def build_leads_lookup(db: Session) -> tuple[dict[str, str], dict[str, str]]:
    """Builds (email_to_lead_id, domain_to_lead_id) maps."""
    email_map: dict[str, str] = {}
    domain_map: dict[str, str] = {}

    leads = db.query(OutreachLead.id, OutreachLead.email, OutreachLead.website).all()
    for lid, em, web in leads:
        if em:
            em_clean = em.lower().strip().rstrip(".")
            email_map[em_clean] = lid
            em_dom = clean_domain_name(em_clean)
            if em_dom and em_dom not in GENERIC_EMAIL_DOMAINS and em_dom not in domain_map:
                domain_map[em_dom] = lid
        if web:
            web_dom = clean_domain_name(web)
            if web_dom and web_dom not in GENERIC_EMAIL_DOMAINS and web_dom not in domain_map:
                domain_map[web_dom] = lid

    return email_map, domain_map


def find_matched_lead_id(
    sender_email: str,
    sender_name: str,
    subject: str,
    body_text: str,
    email_map: dict[str, str],
    domain_map: dict[str, str]
) -> str | None:
    """Finds lead ID using exact email, corporate domain, quoted email, or URL in body."""
    s_clean = (sender_email or "").lower().strip().rstrip(".")
    if s_clean in email_map:
        return email_map[s_clean]

    s_dom = clean_domain_name(s_clean)
    if s_dom and s_dom not in GENERIC_EMAIL_DOMAINS and s_dom in domain_map:
        return domain_map[s_dom]

    # Quoted emails in body
    for cand in RE_GENERIC_EMAIL.findall(body_text or ""):
        c_clean = cand.lower().rstrip(".,;:>)")
        if c_clean != "info@tenderlex.ru" and c_clean in email_map:
            return email_map[c_clean]

    # URLs/domains in body
    for cand_url in RE_GENERIC_URL.findall(body_text or ""):
        cand_dom = clean_domain_name(cand_url)
        if cand_dom and cand_dom not in GENERIC_EMAIL_DOMAINS and cand_dom in domain_map:
            return domain_map[cand_dom]

    return None


def parse_bounce_info(
    sender_email: str,
    sender_name: str,
    subject: str,
    body_text: str,
    email_map: dict[str, str],
    domain_map: dict[str, str] | None = None
) -> tuple[bool, str | None, str, str]:
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
            if cand in email_map:
                matched_lead_id = email_map[cand]
                target_email = cand
                break
            cand_dom = clean_domain_name(cand)
            if domain_map and cand_dom and cand_dom not in GENERIC_EMAIL_DOMAINS and cand_dom in domain_map:
                matched_lead_id = domain_map[cand_dom]
                target_email = cand
                break

    reason_m = RE_DIAGNOSTIC_REASON.search(body_text)
    reason = reason_m.group(1).strip() if reason_m else "Не доставлено (ошибка почтового сервера получателя)"
    reason = re.sub(r"\s+", " ", reason)[:150]
    return True, matched_lead_id, target_email, reason


def is_auto_reply_message(subject: str, body_text: str, sender_name: str = "", sender_email: str = "") -> bool:
    """
    Accurately classifies whether an incoming email is an automated reply,
    helpdesk ticket notification, vacation responder, bot acknowledgement, or robot message.
    """
    subj_clean = re.sub(r"\s+", " ", (subject or "").lower()).strip()
    body_clean = re.sub(r"\s+", " ", (body_text or "").lower()).strip()
    name_clean = re.sub(r"\s+", " ", (sender_name or "").lower()).strip()
    email_clean = (sender_email or "").lower().strip()

    # Senders / Names indicating bot/support/ticket systems
    bot_names = [
        "поддержк", "support", "helpdesk", "service desk", "служба заботы",
        "бот", "bot", "информационная служба", "robot", "noreply", "no-reply", "ticket",
        "sd@", "hd@", "help@", "info@", "support@"
    ]
    if any(bn in name_clean or bn in email_clean for bn in bot_names):
        if any(w in subj_clean or w in body_clean for w in [
            "обращени", "заявк", "тикет", "ticket", "получен", "принят", "зарегистрирован",
            "спешит на помощь", "в порядке очереди", "вернёмся с ответом", "номер",
            "техническ", "служб", "порядок", "запрос", "рассмотрен"
        ]):
            return True

    # Subject keywords
    subj_patterns = [
        "автоматический ответ", "автоответ", "automatic reply", "auto-reply", "auto reply",
        "out of office", "в отпуске", "ваше обращение", "обращение принято", "обращение [",
        "обращение #", "заявка принята", "заявка [", "заявка №", "запрос получен",
        "мы получили ваше письмо", "получили запрос", "ваше письмо получено", "ticket-",
        "[#", "[заявка"
    ]
    if any(p in subj_clean for p in subj_patterns):
        return True

    # Body keywords
    body_patterns = [
        "автоматический ответ", "автоматическое уведомление", "это письмо отправлено автоматически",
        "робот", "я бот", "ваше обращение зарегистрировано", "зарегистрирована заявка",
        "зарегистрирован инцидент", "зарегистрировано под номером", "присвоен номер #",
        "принято в обработку", "дождитесь ответа менеджера", "наш менеджер свяжется с вами",
        "специалист службы поддержки ответит", "вернёмся с ответом в течение",
        "нахожусь в отпуске", "в отпуске до", "out of the office", "out of office",
        "служба заботы о клиентах получила", "вы обратились в службу поддержки",
        "вы обратились в техническую службу", "команда техподдержки", "зарегистрировано в пао",
        "необходимая информация от вас получена", "для сокращения времени обработки обращений",
        "наш менеджер свяжется с вами в ближайшее время", "спасибо за обращение! оно будет рассмотрено",
        "все запросы обрабатываются в порядке очереди", "мы получили ваше письмо и уже спешим",
        "спасибо за обращение в компанию", "письмо получено и принято в обработку",
        "спасибо что обратились к нашему сервису", "спасибо, что обратились к нашему сервису"
    ]
    if any(p in body_clean for p in body_patterns):
        return True

    return False


HOMOGLYPH_TABLE = str.maketrans({
    "а": "a", "с": "c", "е": "e", "о": "o", "р": "p", "х": "x", "у": "y", "і": "i", "ј": "j",
})


def normalize_homoglyphs(text: str) -> str:
    """Normalizes lookalike Cyrillic characters to Latin equivalents for spam matching."""
    if not text:
        return ""
    return text.lower().translate(HOMOGLYPH_TABLE)


KNOWN_SPAM_DOMAINS = {
    "rumixos.shop", "thespacebanana.com", "prorucane.pro", "rabbitandjohn.com",
    "rulane.life", "mojim.com", "doublewin.co.ke", "baza-email-rf.ru",
    "fin-broker77.ru", "aispiritdigital.store", "garden-tech24.ru",
    "boiler-opt.ru", "prom-tool.ru",
}

SPAM_KEYWORDS = [
    r"m[aа]k[iі1l]t[aа]|макита",
    r"аккумуляторн\w+\s+(болгарка|секатор|пила|дрель|шуруповерт|гайковерт|инструмент)",
    r"дрель-шуруповерт",
    r"разошл[её]м ваше коммерческое предложение",
    r"база данных\s+кол-во адресов",
    r"базы данных компаний рф",
    r"рассылка по whatsapp",
    r"рассылк[аи]\s+по\s+email",
    r"аккумуляторный секатор",
    r"аккумуляторная болгарка",
    r"инструмент\s+makita",
    r"dewalt,?\s+bosch\s+со\s+скидкой",
    r"горячая вода за 3 секунды",
    r"получить горячую воду за",
    r"водонагревател[ей|и|ь].*оптом",
    r"бойлеры косвенного нагрева",
    r"таро с нуля",
    r"таро для женщин",
    r"секрета ярких любовных отношений",
    r"секрета женщин, которых мужчины не забывают",
    r"женщиной, которую невозможно забыть",
    r"выйти на 150 000 руб.*с помощью ии",
    r"заработок на ии",
    r"банковские гарантии 44-фз\s*/\s*223-фз от",
    r"постельное белье от производителя",
    r"умное зеркало - всё необходимое",
    r"маркетолог-сеошник",
    r"500 on-бонусов",
    r"продвину ваш сайт",
]


def is_spam_message(
    subject: str,
    body_text: str,
    sender_name: str = "",
    sender_email: str = "",
    has_lead_match: bool = False,
    custom_rules: list[dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    """
    Evaluates whether an incoming email is spam/mass unsolicited advertising.
    Returns (is_spam, reason).
    """
    subj_clean = re.sub(r"\s+", " ", (subject or "").lower()).strip()
    body_clean = re.sub(r"\s+", " ", (body_text or "").lower()).strip()
    name_clean = re.sub(r"\s+", " ", (sender_name or "").lower()).strip()
    email_clean = (sender_email or "").lower().strip()
    domain = email_clean.split("@")[-1] if "@" in email_clean else ""

    subj_norm = normalize_homoglyphs(subj_clean)
    body_norm = normalize_homoglyphs(body_clean)
    name_norm = normalize_homoglyphs(name_clean)

    # 1. Custom rules from DB/Settings
    if custom_rules:
        for rule in custom_rules:
            rtype = rule.get("type", "domain")
            rval = str(rule.get("value", "")).lower().strip()
            if not rval:
                continue
            rval_norm = normalize_homoglyphs(rval)
            if rtype == "domain":
                if domain == rval or domain.endswith("." + rval) or rval == email_clean:
                    return True, f"Заблокированный домен: {rval}"
            elif rtype == "keyword":
                if (
                    rval in subj_clean
                    or rval in body_clean
                    or rval in name_clean
                    or rval_norm in subj_norm
                    or rval_norm in body_norm
                    or rval_norm in name_norm
                ):
                    return True, f"Спам-ключ: {rval}"
            elif rtype == "sender":
                if (
                    rval in email_clean
                    or rval in name_clean
                    or rval_norm in name_norm
                ):
                    return True, f"Заблокированный отправитель: {rval}"

    # 2. Known Spam Domains & TLDs
    if domain in KNOWN_SPAM_DOMAINS:
        return True, f"Известный спам-домен: {domain}"

    if domain.endswith((".shop", ".pro", ".co.ke", ".store", ".fun", ".click", ".top", ".loan", ".life")):
        if not has_lead_match:
            return True, f"Подозрительный спам-домен: {domain}"

    # 3. Makita Spammer / Tool Botnet Detection (High-priority exact match)
    if (
        re.search(r"m[aа]k[iі1l]t[aа]|макита", name_clean, re.IGNORECASE)
        or re.search(r"m[aа]k[iі1l]t[aа]|макита", subj_clean, re.IGNORECASE)
        or re.search(r"m[aа]k[iі1l]t[aа]|макита", name_norm, re.IGNORECASE)
        or re.search(r"m[aа]k[iі1l]t[aа]|макита", subj_norm, re.IGNORECASE)
    ):
        return True, "Спам-рассылка инструментов Makita"

    # 4. Sender Name Patterns
    if re.search(r"рассылк\w*\d{6,}", name_clean) or re.search(r"рассылка\s*\+?7", name_clean):
        return True, f"Спам в имени отправителя: {sender_name}"

    name_personas = [
        "makita", "mаkitа", "садовый сезон", "водонагреватель", "женские секреты",
        "love-коуч", "карты таро", "тотальная распродажа", "заработок на ии",
    ]
    if any(k in name_clean or k in name_norm for k in name_personas):
        return True, f"Спам-отправитель: {sender_name}"

    # 5. Numeric mail.ru/bk.ru/inbox.ru free email accounts sending forms
    if re.match(r"^\d{6,}@(mail\.ru|bk\.ru|inbox\.ru|list\.ru)$", email_clean):
        if "docs.google.com/forms" in body_clean or "forms.gle" in body_clean or len(subj_clean.split()) <= 2:
            return True, "Массовый спам-бот с номерного ящика mail.ru"

    # 6. Content Keywords
    for kw_pattern in SPAM_KEYWORDS:
        if re.search(kw_pattern, subj_clean) or re.search(kw_pattern, body_clean):
            return True, f"Спам-паттерн в тексте: {kw_pattern}"

    return False, ""


def html_to_plain_text(html_content: str) -> str:
    """Converts HTML email body to clean readable text."""
    if not html_content:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(p|div|tr|h[1-6]|li|blockquote|pre)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def backfill_existing_bounces(db: Session) -> int:
    """Retroactively identifies and links existing unlinked bounces, auto_replies, and spam."""
    settings = db.query(OutreachSettings).filter(OutreachSettings.id == 1).first()
    custom_rules = json.loads(settings.spam_rules_json) if settings and settings.spam_rules_json else []
    email_map, domain_map = build_leads_lookup(db)
    unlinked = db.query(OutreachIncomingEmail).all()
    updated_count = 0

    for msg in unlinked:
        body = msg.body_text or ""
        if not body.strip() and msg.body_html:
            body = html_to_plain_text(msg.body_html)
            msg.body_text = body[:10000]
            updated_count += 1

        matched_lead_id = find_matched_lead_id(
            msg.sender_email, msg.sender_name, msg.subject, body, email_map, domain_map
        )
        has_lead_match = bool(matched_lead_id)

        # 1. Check Spam first!
        is_sp, spam_reason = is_spam_message(
            msg.subject, body, msg.sender_name, msg.sender_email, has_lead_match, custom_rules
        )
        if is_sp:
            if not msg.is_spam or msg.category != "spam":
                msg.is_spam = True
                msg.category = "spam"
                updated_count += 1
            continue

        # 2. Check Bounce
        is_bounce, matched_id, target_em, reason = parse_bounce_info(
            msg.sender_email, msg.sender_name, msg.subject, body, email_map, domain_map
        )
        if is_bounce:
            msg.is_spam = False
            if msg.category != "bounce":
                msg.category = "bounce"
                updated_count += 1
            if matched_id and msg.lead_id != matched_id:
                msg.lead_id = matched_id
                updated_count += 1
            if msg.lead_id:
                lead = db.query(OutreachLead).filter(OutreachLead.id == msg.lead_id).first()
                if lead and lead.status != "bounced":
                    lead.status = "bounced"
                    lead.notes = f"Ошибка доставки: {reason}"
                    updated_count += 1
            continue

        # 3. Check Auto-Reply vs Live Reply
        is_auto = is_auto_reply_message(msg.subject, body, msg.sender_name, msg.sender_email)
        new_cat = "auto_reply" if is_auto else "reply"
        msg.is_spam = False
        if msg.category != new_cat:
            msg.category = new_cat
            updated_count += 1

        if matched_lead_id and msg.lead_id != matched_lead_id:
            msg.lead_id = matched_lead_id
            updated_count += 1

        if msg.lead_id:
            lead = db.query(OutreachLead).filter(OutreachLead.id == msg.lead_id).first()
            if lead:
                lead.reply_received = True
                if new_cat == "reply" or lead.status not in ["replied", "bounced", "spam"]:
                    lead.status = "replied"
                updated_count += 1

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
        email_map, domain_map = build_leads_lookup(db)
        custom_rules = json.loads(settings.spam_rules_json) if settings.spam_rules_json else []

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

            if not body_text.strip() and body_html:
                body_text = html_to_plain_text(body_html)

            # 1. Lead Match & Spam Check
            matched_lead_id = find_matched_lead_id(
                sender_email, sender_name, subject, body_text, email_map, domain_map
            )
            has_lead_match = bool(matched_lead_id)
            is_spam, spam_reason = is_spam_message(
                subject, body_text, sender_name, sender_email, has_lead_match, custom_rules
            )

            is_bounce, matched_bounce_id, target_em, bounce_reason = parse_bounce_info(
                sender_email, sender_name, subject, body_text, email_map, domain_map
            )

            if is_spam:
                lead_id = None
                category = "spam"
                is_spam_val = True
                try:
                    client.store(m_id, "+FLAGS", "\\Deleted")
                except Exception as de:
                    logger.debug(f"Could not flag spam as \\Deleted in IMAP: {de}")
            elif is_bounce:
                lead_id = matched_bounce_id
                category = "bounce"
                is_spam_val = False
            else:
                lead_id = matched_lead_id
                category = "auto_reply" if is_auto_reply_message(subject, body_text, sender_name, sender_email) else "reply"
                is_spam_val = False

            inbound = OutreachIncomingEmail(
                message_id=message_id_header,
                sender_email=sender_email,
                sender_name=sender_name or from_header,
                recipient_email=settings.from_email or "info@tenderlex.ru",
                subject=subject,
                body_text=body_text[:10000],
                body_html=body_html[:50000],
                category=category,
                is_spam=is_spam_val,
                date_received=dt_utc,
                lead_id=lead_id,
            )
            db.add(inbound)

            if lead_id and not is_spam_val:
                lead_obj = db.query(OutreachLead).filter(OutreachLead.id == lead_id).first()
                if lead_obj:
                    if is_bounce:
                        lead_obj.status = "bounced"
                        lead_obj.notes = f"Ошибка доставки: {bounce_reason}"
                    else:
                        lead_obj.reply_received = True
                        if category == "reply" or lead_obj.status not in ["replied", "bounced", "spam"]:
                            lead_obj.status = "replied"

            if message_id_header:
                existing_msg_ids.add(message_id_header)
            new_count += 1

        db.commit()
        try:
            client.expunge()
        except Exception:
            pass
        client.logout()
        return {"success": True, "new_messages": new_count}
    except Exception as e:
        logger.error(f"IMAP sync error: {e}")
        return {"success": False, "error": str(e), "new_messages": 0}
