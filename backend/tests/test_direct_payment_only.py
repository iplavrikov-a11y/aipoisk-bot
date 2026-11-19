from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bot import (
    cabinet_inline_keyboard,
    low_balance_inline_keyboard,
    status_inline_keyboard,
    tariffs_inline_keyboard,
)
from app.db import SessionLocal, init_db
from app.main import app, require_admin
from app.models import Client, Invoice, SystemSettings, WebSession, WebUser, new_id
from app.web_auth import create_web_session


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_customer(db: Session, *, email: str, direct_payment_only: bool = False) -> tuple[Client, WebUser, str, str]:
    c_id = new_id()
    client = Client(
        id=c_id,
        telegram_id=f"direct_{c_id}",
        name="Direct Pay Test Client",
        money_balance_kopeks=0,
        direct_payment_only=direct_payment_only,
    )
    db.add(client)
    db.flush()

    user = WebUser(
        id=new_id(),
        client_id=client.id,
        email=email,
        password_hash="test_hash",
        name="Тестовый Клиент",
        is_email_verified=True,
    )
    db.add(user)
    db.commit()

    token, csrf_token, _session = create_web_session(db, user)
    return client, user, token, csrf_token


def _ensure_yookassa_settings(db: Session) -> SystemSettings:
    settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)
    settings.payment_provider = "yookassa"
    settings.yookassa_shop_id = "1509607"
    settings.yookassa_secret_key = "live_secret_test_123"
    settings.contact_telegram = "@lexelence"
    db.commit()
    return settings


def test_direct_payment_only_blocks_yookassa_and_invoices_and_can_be_re_enabled(setup_database: Session):
    db = setup_database
    _ensure_yookassa_settings(db)
    client_obj, user, token, csrf = _create_customer(
        db,
        email=f"direct_only_{new_id()}@example.com",
        direct_payment_only=True,
    )

    http = TestClient(app)
    http.cookies.set("tenderlex_customer_session", token)

    # 1. Session exposes direct_payment_only=True
    me_resp = http.get("/api/customer/me")
    assert me_resp.status_code == 200, me_resp.text
    me_data = me_resp.json()
    assert me_data["user"]["direct_payment_only"] is True
    assert me_data["payment"]["direct_payment_only"] is True

    # 2. YooKassa creation is blocked with 403 and never hits gateway
    with patch("app.main.create_yookassa_payment") as mock_yoo:
        yk_resp = http.post(
            "/api/customer/payments/yookassa/create",
            headers={"X-CSRF-Token": csrf},
            json={"amount_rub": 3000},
        )
        assert yk_resp.status_code == 403, yk_resp.text
        assert "менеджер" in yk_resp.json()["detail"].lower()
        mock_yoo.assert_not_called()

    # 3. B2B invoice creation is blocked with 403 and creates no invoice
    before_invoices = db.query(Invoice).filter(Invoice.client_id == client_obj.id).count()
    inv_resp = http.post(
        "/api/customer/invoices",
        headers={"X-CSRF-Token": csrf},
        json={
            "amount_rub": 5000,
            "buyer_inn": "7707083893",
            "buyer_name": "ООО Тест",
        },
    )
    assert inv_resp.status_code == 403, inv_resp.text
    assert "менеджер" in inv_resp.json()["detail"].lower()
    after_invoices = db.query(Invoice).filter(Invoice.client_id == client_obj.id).count()
    assert after_invoices == before_invoices

    # 4. Admin disables direct_payment_only -> official payment methods work again immediately
    app.dependency_overrides[require_admin] = lambda: None
    try:
        patch_resp = http.patch(
            f"/api/clients/{client_obj.id}",
            json={"direct_payment_only": False},
        )
        assert patch_resp.status_code == 200, patch_resp.text
        assert patch_resp.json()["direct_payment_only"] is False
    finally:
        app.dependency_overrides.pop(require_admin, None)

    me_after = http.get("/api/customer/me")
    assert me_after.status_code == 200
    assert me_after.json()["user"]["direct_payment_only"] is False
    assert me_after.json()["payment"]["direct_payment_only"] is False

    mock_resp = {
        "id": f"yoo_re_enabled_{new_id()}",
        "status": "pending",
        "amount": {"value": "3000.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "confirmation_url": "https://yoomoney.ru/test"},
    }
    with patch("app.main.create_yookassa_payment", return_value=mock_resp):
        yk_ok = http.post(
            "/api/customer/payments/yookassa/create",
            headers={"X-CSRF-Token": csrf},
            json={"amount_rub": 3000},
        )
        assert yk_ok.status_code == 200, yk_ok.text
        assert yk_ok.json()["success"] is True


def test_bot_keyboards_hide_online_and_b2b_for_direct_payment_only(setup_database: Session):
    db = setup_database
    settings = _ensure_yookassa_settings(db)
    client = Client(
        id=new_id(),
        telegram_id=f"bot_direct_{new_id()}",
        name="Bot Direct Client",
        direct_payment_only=True,
    )

    def _callbacks_and_texts(kb):
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        return callbacks, texts

    for kb in (
        cabinet_inline_keyboard("https://tenderlex.ru/cabinet", has_web_user=True, contact_url="https://t.me/lexelence", direct_payment_only=True),
        status_inline_keyboard(direct_payment_only=True, contact_url="https://t.me/lexelence"),
        tariffs_inline_keyboard("https://tenderlex.ru/cabinet", direct_payment_only=True, contact_url="https://t.me/lexelence"),
        low_balance_inline_keyboard(settings, client),
    ):
        callbacks, texts = _callbacks_and_texts(kb)
        assert "topup_online_menu" not in callbacks
        assert "topup_b2b_menu" not in callbacks
        assert any("менеджер" in t.lower() for t in texts)
