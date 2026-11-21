from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import config
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Client, Job, WebUser, new_id
from app.nurturing import generate_unsubscribe_token
from app.outreach_models import OutreachIncomingEmail
import app.procurement_report as procurement_report_mod
from app.web_auth import create_web_session


@pytest.fixture(autouse=True)
def setup_database(monkeypatch):
    if not config.admin_token or config.admin_token == "change-me":
        monkeypatch.setattr(config, "admin_token", "test-admin-secret-token")
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_customer_with_csrf(db: Session, email: str) -> tuple[Client, WebUser, str, str]:
    c_id = new_id()
    client = Client(
        id=c_id,
        telegram_id=f"web_client_{c_id}",
        name="ООО ТестСнаб",
        money_balance_kopeks=50000,
    )
    db.add(client)
    db.flush()

    user = WebUser(
        id=new_id(),
        client_id=client.id,
        email=email,
        password_hash="test_hash",
        name="Пётр Петров",
        is_email_verified=True,
    )
    db.add(user)
    db.commit()

    session_token, csrf_token, _ = create_web_session(db, user)
    return client, user, session_token, csrf_token


def test_cors_blocks_untrusted_origin():
    tc = TestClient(app)
    res = tc.options(
        "/api/public/site",
        headers={
            "Origin": "https://evil.attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") is None


def test_guest_chat_blocks_tg_prefix_and_requires_signed_cookie():
    tc = TestClient(app)

    res_tg = tc.get("/api/public/guest-chat/messages?sessionId=tg_123456789")
    assert res_tg.status_code == 403

    res_tg_post = tc.post(
        "/api/public/guest-chat/send",
        json={"sessionId": "tg_123456789", "text": "hello"},
    )
    assert res_tg_post.status_code == 403

    sid = f"sess_{new_id()[:12]}"
    with (
        patch(
            "app.main.classify_and_reply_support_message",
            new=AsyncMock(return_value={"category": "general", "reply": "", "need_human": False}),
        ),
        patch("app.main.notify_admins_of_incoming_message", new=AsyncMock()),
    ):
        send_res = tc.post(
            "/api/public/guest-chat/send",
            json={"sessionId": sid, "text": "Нужен подбор поставщиков", "contact": "+79991112233"},
        )
    assert send_res.status_code == 200
    assert "tenderlex_guest_chat" in send_res.cookies

    # Reading with the issued cookie returns the message
    own_read = tc.get(f"/api/public/guest-chat/messages?sessionId={sid}")
    assert own_read.status_code == 200
    assert len(own_read.json()["messages"]) >= 1

    # Reading from an unauthenticated third-party client without the cookie hides history & contact
    stranger = TestClient(app)
    stranger_read = stranger.get(f"/api/public/guest-chat/messages?sessionId={sid}")
    assert stranger_read.status_code == 200
    assert stranger_read.json()["messages"] == []
    assert not stranger_read.json()["contact"]


def test_csrf_enforced_on_customer_chat_invoices_and_account_delete(setup_database: Session):
    db = setup_database
    _, user, session_token, csrf_token = _create_customer_with_csrf(
        db, f"csrf_{new_id()[:8]}@romashka.ru"
    )
    tc = TestClient(app)
    tc.cookies.set("tenderlex_customer_session", session_token)

    # Without CSRF token -> 403
    assert tc.post("/api/customer/chat", data={"message": "Привет"}).status_code == 403
    assert tc.post(
        "/api/customer/invoices",
        json={
            "amount_rub": 5000,
            "buyer_inn": "7701234567",
            "buyer_name": "ООО Ромашка",
            "buyer_email": user.email,
        },
    ).status_code == 403
    assert tc.post("/api/customer/account/delete").status_code == 403

    # With valid CSRF token -> succeeds
    inv_ok = tc.post(
        "/api/customer/invoices",
        headers={"x-csrf-token": csrf_token},
        json={
            "amount_rub": 5000,
            "buyer_inn": "7701234567",
            "buyer_name": "ООО Ромашка",
            "buyer_email": user.email,
        },
    )
    assert inv_ok.status_code == 200
    inv_id = inv_ok.json()["invoice"]["id"]

    # HTML view sets strict CSP and X-Content-Type-Options
    html_res = tc.get(f"/api/customer/invoices/{inv_id}/html")
    assert html_res.status_code == 200
    assert "default-src 'none'" in html_res.headers.get("content-security-policy", "")
    assert html_res.headers.get("x-content-type-options") == "nosniff"

    # Send-email blocks third-party email relay
    bad_email_res = tc.post(
        f"/api/customer/invoices/{inv_id}/send-email",
        headers={"x-csrf-token": csrf_token},
        json={"email": "victim_third_party@otherdomain.ru"},
    )
    assert bad_email_res.status_code in (400, 403)


def test_unsubscribe_requires_signed_token(setup_database: Session):
    db = setup_database
    client_row, user, _, _ = _create_customer_with_csrf(
        db, f"unsub_{new_id()[:8]}@romashka.ru"
    )
    tc = TestClient(app)

    # Unsigned email-only unsubscribe is rejected
    assert tc.get(f"/api/customer/auth/unsubscribe?email={user.email}").status_code == 400
    assert tc.post("/api/customer/auth/unsubscribe", data={"email": user.email}).status_code == 400

    # Valid signed token succeeds
    valid_token = generate_unsubscribe_token(client_row.id, user.email)
    ok_res = tc.get(f"/api/customer/auth/unsubscribe?token={valid_token}")
    assert ok_res.status_code == 200


def test_retry_job_blocks_completed_job_and_account_self_delete(setup_database: Session):
    db = setup_database
    client_row, _, session_token, csrf_token = _create_customer_with_csrf(
        db, f"retry_{new_id()[:8]}@romashka.ru"
    )
    completed_job = Job(
        id=new_id(),
        client_id=client_row.id,
        created_by_telegram_id=client_row.telegram_id,
        mode="supplier_search",
        status="completed",
        title="Готовая задача",
    )
    db.add(completed_job)
    db.commit()

    tc = TestClient(app)
    tc.cookies.set("tenderlex_customer_session", session_token)

    # Completed job cannot be re-executed in place via /retry
    retry_res = tc.post(
        f"/api/customer/jobs/{completed_job.id}/retry",
        headers={"x-csrf-token": csrf_token},
    )
    assert retry_res.status_code == 409

    # Self-delete succeeds when no active jobs exist
    del_res = tc.post(
        "/api/customer/account/delete",
        headers={"x-csrf-token": csrf_token},
    )
    assert del_res.status_code == 200
    assert del_res.json()["ok"] is True


def test_block_inbox_sender_preserves_other_public_domain_messages(setup_database: Session):
    db = setup_database
    spammer_msg = OutreachIncomingEmail(
        id=new_id(),
        message_id=f"uid_spam_{new_id()}",
        sender_email="spammer123@gmail.com",
        subject="Spam",
        body_text="Spam",
    )
    legit_msg = OutreachIncomingEmail(
        id=new_id(),
        message_id=f"uid_legit_{new_id()}",
        sender_email="real_factory_director@gmail.com",
        subject="КП по поставке кабеля",
        body_text="Готовы поставить",
    )
    db.add_all([spammer_msg, legit_msg])
    db.commit()
    legit_id = legit_msg.id

    spammer_id = spammer_msg.id

    tc = TestClient(app)
    res = tc.post(
        f"/api/outreach/inbox/{spammer_id}/block-sender",
        headers={"X-Admin-Token": config.admin_token},
    )
    assert res.status_code == 200

    db.expire_all()
    assert db.get(OutreachIncomingEmail, legit_id) is not None


def test_extract_doc_facts_has_no_hardcoded_product_dictionaries():
    src = inspect.getsource(procurement_report_mod)
    for forbidden in ("одежд", "обув", "продукт", "лекарств"):
        assert forbidden not in src
