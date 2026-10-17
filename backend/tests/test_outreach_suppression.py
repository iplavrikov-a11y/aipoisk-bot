import uuid

import pytest


@pytest.mark.parametrize(
    ("smtp_error", "expected"),
    [
        ("SMTP: 550 user unknown", True),
        ("SMTP: 550 5.1.1 mailbox does not exist", True),
        ("SMTP: 550 Message rejected under suspicion of SPAM", False),
        ("SMTP: 550 This message is blocked due to security reason", False),
        ("SMTP: 550 daily sending quota exceeded", False),
        ("SMTP: 550 temporary policy rejection", False),
    ],
)
def test_only_recipient_specific_bounces_are_shared_suppressions(smtp_error, expected):
    from app.outreach_mail import is_invalid_recipient_smtp_error

    assert is_invalid_recipient_smtp_error(smtp_error) is expected


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("Re: offer", "Стоп", True),
        ("unsubscribe", "", True),
        ("Re: offer", "\n > Отписаться\n\nСпасибо", False),
        ("Re: offer", "Пожалуйста, не надо. Внизу есть ссылка Отписаться.", False),
        ("Re: offer", "Здравствуйте\nОтписаться", False),
    ],
)
def test_explicit_optout_reply_requires_exact_unquoted_first_line(subject, body, expected):
    from app.outreach_mail import is_explicit_optout_reply

    assert is_explicit_optout_reply(subject, body) is expected


def test_quoted_body_does_not_fall_back_to_stop_subject():
    from app.outreach_mail import is_explicit_optout_reply

    assert is_explicit_optout_reply("Стоп", "> Отписаться") is False


def test_imap_exact_stop_reply_unsubscribes_matching_lead_and_mirrors_shared(monkeypatch):
    from email.message import EmailMessage

    from app.db import SessionLocal
    from app.outreach_mail import sync_imap_inbox
    from app.outreach_models import OutreachLead, OutreachSettings

    lead_id = f"imap-stop-{uuid.uuid4().hex}"
    recorded: list[tuple[str, str, str]] = []
    message = EmailMessage()
    message["From"] = "Recipient <stop-recipient@example.ru>"
    message["Subject"] = "Re: Offer"
    message["Message-ID"] = f"<stop-{uuid.uuid4().hex}@example.ru>"
    message.set_content("Стоп")

    class FakeImap:
        def login(self, *args): pass
        def select(self, *args): pass
        def search(self, *args): return "OK", [b"1"]
        def fetch(self, *args): return "OK", [(b"1", message.as_bytes())]
        def store(self, *args): pass
        def expunge(self): pass
        def logout(self): pass

    monkeypatch.setattr("app.outreach_mail.imaplib.IMAP4_SSL", lambda *args, **kwargs: FakeImap())
    monkeypatch.setattr(
        "app.outreach_mail.record_shared_suppression",
        lambda email, reason, source: recorded.append((email, reason, source)),
    )

    db = SessionLocal()
    try:
        db.add(OutreachLead(id=lead_id, email="stop-recipient@example.ru", status="sent", mx_valid=True))
        settings = OutreachSettings(imap_password="test-password")
        db.commit()

        result = sync_imap_inbox(settings, db)
        db.expire_all()
        lead = db.query(OutreachLead).filter(OutreachLead.id == lead_id).one()
        assert result["success"] is True
        assert lead.status == "unsubscribed"
        assert lead.mx_valid is False
        assert recorded == [("stop-recipient@example.ru", "unsubscribed", "tenderlex_explicit_reply")]
    finally:
        db.query(OutreachLead).filter(OutreachLead.id == lead_id).delete()
        db.commit()
        db.close()


def test_list_unsubscribe_header_uses_signed_url_without_one_click_post(monkeypatch):
    from app.outreach_mail import _list_unsubscribe_header

    monkeypatch.setattr(
        "app.outreach_mail.build_unsubscribe_url",
        lambda email: "https://tenderlex.ru/api/outreach/unsubscribe?email=recipient%40example.ru&token=signed",
    )

    header = _list_unsubscribe_header("recipient@example.ru", "info@tenderlex.ru")
    assert "https://tenderlex.ru/api/outreach/unsubscribe?" in header
    assert "/cabinet?unsubscribe=" not in header


@pytest.mark.asyncio
async def test_marketing_send_adds_visible_signed_footer_to_relay_payload(monkeypatch):
    from app.outreach_mail import send_single_email
    from app.outreach_models import OutreachSettings

    payloads: list[dict] = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"success": True}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            payloads.append(kwargs["json"])
            return Response()

    monkeypatch.setattr("app.outreach_mail.build_unsubscribe_url", lambda email: "https://tenderlex.ru/api/outreach/unsubscribe?token=signed")
    monkeypatch.setattr("app.outreach_mail.httpx.AsyncClient", lambda **kwargs: Client())
    settings = OutreachSettings(relay_url="https://relay.example", relay_api_key="test-key")

    ok, error = await send_single_email(
        to_email="recipient@example.ru",
        subject="Offer",
        body_text="Hello",
        body_html="<p>Hello</p>",
        settings=settings,
        is_marketing=True,
    )

    assert (ok, error) == (True, "")
    assert "https://tenderlex.ru/api/outreach/unsubscribe?token=signed" in payloads[0]["text"]
    assert "https://tenderlex.ru/api/outreach/unsubscribe?token=signed" in payloads[0]["html"]
    assert "List-Unsubscribe-Post" not in payloads[0]["headers"]


@pytest.mark.asyncio
async def test_marketing_send_adds_visible_signed_footer_to_smtp_body(monkeypatch):
    from app.outreach_mail import send_single_email
    from app.outreach_models import OutreachSettings

    sent = []
    monkeypatch.setattr("app.outreach_mail.build_unsubscribe_url", lambda email: "https://tenderlex.ru/api/outreach/unsubscribe?token=signed")
    monkeypatch.setattr("app.outreach_mail._send_smtp_sync", lambda message, settings, email: (sent.append(message) or True, ""))

    ok, error = await send_single_email(
        to_email="recipient@example.ru",
        subject="Offer",
        body_text="Hello",
        body_html="<p>Hello</p>",
        settings=OutreachSettings(),
        is_marketing=True,
    )

    assert (ok, error) == (True, "")
    assert "https://tenderlex.ru/api/outreach/unsubscribe?token=signed" in sent[0].get_body(("plain",)).get_content()
    assert "https://tenderlex.ru/api/outreach/unsubscribe?token=signed" in sent[0].get_body(("html",)).get_content()


@pytest.mark.asyncio
async def test_non_marketing_send_does_not_add_optout_footer(monkeypatch):
    from app.outreach_mail import send_single_email
    from app.outreach_models import OutreachSettings

    sent = []
    monkeypatch.setattr("app.outreach_mail.build_unsubscribe_url", lambda email: "https://tenderlex.ru/api/outreach/unsubscribe?token=signed")
    monkeypatch.setattr("app.outreach_mail._send_smtp_sync", lambda message, settings, email: (sent.append(message) or True, ""))

    await send_single_email(
        to_email="recipient@example.ru",
        subject="Re: Offer",
        body_text="Reply text",
        body_html="",
        settings=OutreachSettings(),
    )

    assert "https://tenderlex.ru/api/outreach/unsubscribe?token=signed" not in sent[0].get_content()


@pytest.mark.asyncio
async def test_direct_marketing_send_stops_before_network_when_shared_suppressed(monkeypatch):
    from app.outreach_mail import send_single_email
    from app.outreach_models import OutreachSettings

    monkeypatch.setattr("app.outreach_mail.get_shared_suppression_reason", lambda email: "unsubscribed")
    monkeypatch.setattr(
        "app.outreach_mail.httpx.AsyncClient",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not reach relay")),
    )

    assert await send_single_email(
        to_email="opted-out@example.ru",
        subject="Offer",
        body_text="Hello",
        body_html="",
        settings=OutreachSettings(relay_url="https://relay.example", relay_api_key="test-key"),
        is_marketing=True,
    ) == (False, "suppressed:unsubscribed")


@pytest.mark.asyncio
async def test_direct_marketing_send_stops_before_network_when_lookup_fails(monkeypatch):
    from app.outreach_mail import send_single_email
    from app.outreach_models import OutreachSettings

    def lookup_error(email):
        raise RuntimeError("shared registry unavailable")

    monkeypatch.setattr("app.outreach_mail.get_shared_suppression_reason", lookup_error)
    monkeypatch.setattr(
        "app.outreach_mail.httpx.AsyncClient",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not reach relay")),
    )

    assert await send_single_email(
        to_email="recipient@example.ru",
        subject="Offer",
        body_text="Hello",
        body_html="",
        settings=OutreachSettings(relay_url="https://relay.example", relay_api_key="test-key"),
        is_marketing=True,
    ) == (False, "suppression_lookup_failed")


@pytest.mark.asyncio
async def test_direct_marketing_send_stops_when_shared_database_is_missing(monkeypatch, tmp_path):
    from app import outreach_suppression
    from app.outreach_mail import send_single_email
    from app.outreach_models import OutreachSettings

    monkeypatch.setenv("GLOBAL_OUTREACH_DB", str(tmp_path / "missing-global-outreach.db"))
    outreach_suppression._shared_suppression_module.cache_clear()
    monkeypatch.setattr(
        "app.outreach_mail.httpx.AsyncClient",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not reach relay")),
    )

    assert await send_single_email(
        to_email="recipient@example.ru",
        subject="Offer",
        body_text="Hello",
        body_html="",
        settings=OutreachSettings(relay_url="https://relay.example", relay_api_key="test-key"),
        is_marketing=True,
    ) == (False, "suppression_lookup_failed")


def test_campaign_does_not_send_to_shared_suppressed_recipient(monkeypatch):
    from app.db import SessionLocal
    from app.outreach_mail import run_campaign_worker
    from app.outreach_models import OutreachCampaign, OutreachLead, OutreachSettings

    lead_id = f"shared-suppressed-{uuid.uuid4().hex}"
    campaign_id = f"shared-suppressed-{uuid.uuid4().hex}"
    sent_to: list[str] = []

    async def should_not_verify(email: str):
        raise AssertionError(f"suppressed recipient reached deliverability check: {email}")

    async def should_not_send(**kwargs):
        sent_to.append(kwargs["to_email"])
        return True, ""

    monkeypatch.setattr("app.outreach_mail.get_shared_suppression_reason", lambda email: "unsubscribed")
    monkeypatch.setattr("app.outreach_mail.verify_email_deliverability", should_not_verify)
    monkeypatch.setattr("app.outreach_mail.send_single_email", should_not_send)

    db = SessionLocal()
    try:
        db.merge(OutreachSettings(id=1))
        db.add(OutreachLead(id=lead_id, email="opted-out@example.ru", status="new", mx_valid=True))
        db.add(OutreachCampaign(id=campaign_id, selected_lead_ids=f'["{lead_id}"]', subject="Test", body_text="Test"))
        db.commit()
    finally:
        db.close()

    import asyncio
    asyncio.run(run_campaign_worker(campaign_id, SessionLocal))

    db = SessionLocal()
    try:
        lead = db.query(OutreachLead).filter(OutreachLead.id == lead_id).one()
        assert sent_to == []
        assert lead.status == "new"
    finally:
        db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).delete()
        db.query(OutreachLead).filter(OutreachLead.id == lead_id).delete()
        db.commit()
        db.close()


def test_shared_lookup_failure_prevents_campaign_send(monkeypatch):
    from app.db import SessionLocal
    from app.outreach_mail import run_campaign_worker
    from app.outreach_models import OutreachCampaign, OutreachLead, OutreachSettings

    lead_id = f"shared-error-{uuid.uuid4().hex}"
    campaign_id = f"shared-error-{uuid.uuid4().hex}"

    def lookup_error(email: str):
        raise RuntimeError("shared database unavailable")

    async def should_not_send(**kwargs):
        raise AssertionError("shared lookup failure must not send email")

    monkeypatch.setattr("app.outreach_mail.get_shared_suppression_reason", lookup_error)
    monkeypatch.setattr("app.outreach_mail.send_single_email", should_not_send)

    db = SessionLocal()
    try:
        db.merge(OutreachSettings(id=1))
        db.add(OutreachLead(id=lead_id, email="lookup-failure@example.ru", status="new", mx_valid=True))
        db.add(OutreachCampaign(id=campaign_id, selected_lead_ids=f'["{lead_id}"]', subject="Test", body_text="Test"))
        db.commit()
    finally:
        db.close()

    import asyncio
    asyncio.run(run_campaign_worker(campaign_id, SessionLocal))

    db = SessionLocal()
    try:
        assert db.query(OutreachLead).filter(OutreachLead.id == lead_id).one().status == "new"
    finally:
        db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).delete()
        db.query(OutreachLead).filter(OutreachLead.id == lead_id).delete()
        db.commit()
        db.close()


def test_manual_unsubscribe_keeps_local_stoplist_when_shared_write_fails(monkeypatch):
    from app.db import SessionLocal
    from app.outreach_api import unsubscribe_lead
    from app.outreach_models import OutreachLead

    lead_id = f"local-optout-{uuid.uuid4().hex}"

    def write_error(*args, **kwargs):
        raise RuntimeError("shared database unavailable")

    monkeypatch.setattr("app.outreach_api.record_shared_suppression", write_error)
    db = SessionLocal()
    try:
        db.add(OutreachLead(id=lead_id, email="keep-local@example.ru", status="new", mx_valid=True))
        db.commit()

        result = unsubscribe_lead(lead_id, db)
        db.expire_all()
        lead = db.query(OutreachLead).filter(OutreachLead.id == lead_id).one()
        assert result["ok"] is True
        assert lead.status == "unsubscribed"
        assert lead.mx_valid is False
    finally:
        db.query(OutreachLead).filter(OutreachLead.id == lead_id).delete()
        db.commit()
        db.close()


def test_permanent_smtp_bounce_is_mirrored_to_shared_suppression(monkeypatch):
    from app.db import SessionLocal
    from app.outreach_mail import run_campaign_worker
    from app.outreach_models import OutreachCampaign, OutreachLead, OutreachSettings

    lead_id = f"shared-bounce-{uuid.uuid4().hex}"
    campaign_id = f"shared-bounce-{uuid.uuid4().hex}"
    recorded: list[tuple[str, str, str]] = []

    async def deliverable(email: str):
        return True, "MX confirmed"

    async def permanent_bounce(**kwargs):
        return False, "SMTP: 550 user unknown"

    monkeypatch.setattr("app.outreach_mail.get_shared_suppression_reason", lambda email: None)
    monkeypatch.setattr("app.outreach_mail.verify_email_deliverability", deliverable)
    monkeypatch.setattr("app.outreach_mail.send_single_email", permanent_bounce)
    monkeypatch.setattr(
        "app.outreach_mail.record_shared_suppression",
        lambda email, reason, source: recorded.append((email, reason, source)),
    )

    db = SessionLocal()
    try:
        db.merge(OutreachSettings(id=1))
        db.add(OutreachLead(id=lead_id, email="bounced@example.ru", status="new", mx_valid=True))
        db.add(OutreachCampaign(id=campaign_id, selected_lead_ids=f'["{lead_id}"]', subject="Test", body_text="Test"))
        db.commit()
    finally:
        db.close()

    import asyncio
    asyncio.run(run_campaign_worker(campaign_id, SessionLocal))

    db = SessionLocal()
    try:
        lead = db.query(OutreachLead).filter(OutreachLead.id == lead_id).one()
        assert lead.status == "bounced"
        assert lead.mx_valid is False
        assert recorded == [("bounced@example.ru", "invalid_recipient", "tenderlex_smtp_bounce")]
    finally:
        db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).delete()
        db.query(OutreachLead).filter(OutreachLead.id == lead_id).delete()
        db.commit()
        db.close()
