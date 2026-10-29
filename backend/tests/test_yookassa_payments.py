from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.main import app
from app.models import BillingTransaction, Client, SystemSettings, WebUser, YooKassaPayment, new_id
from app.yookassa_service import YooKassaError, create_yookassa_payment, fetch_yookassa_payment


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_test_customer(db: Session, email: str = "payer@example.com") -> tuple[Client, WebUser, str]:
    c_id = new_id()
    client = Client(id=c_id, telegram_id=f"payer_{c_id}", name="Test Payer", money_balance_kopeks=0)
    db.add(client)
    db.flush()

    user = WebUser(
        id=new_id(),
        client_id=client.id,
        email=email,
        password_hash="test_hash",
        name="Алексей Тестов",
        is_email_verified=True,
    )
    db.add(user)
    db.commit()

    from app.web_auth import create_web_session
    token, csrf_token, session = create_web_session(db, user)
    return client, user, token


def test_yookassa_service_create_payment_unit():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "2d89b142-000f-5000-8000-1c0b39be82ee",
        "status": "pending",
        "amount": {"value": "5000.00", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=2d89b142-000f-5000-8000-1c0b39be82ee",
        },
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = create_yookassa_payment(
            shop_id="1509607",
            secret_key="test_secret_key",
            amount_rub=5000,
            return_url="https://tenderlex.ru/cabinet?payment_status=check",
            description="Пополнение баланса",
            metadata={"user_id": "u123"},
        )
        assert res["id"] == "2d89b142-000f-5000-8000-1c0b39be82ee"
        assert "yoomoney.ru" in res["confirmation"]["confirmation_url"]

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["amount"]["value"] == "5000.00"
        assert call_kwargs["json"]["capture"] is True


def test_customer_create_payment_api(setup_database: Session):
    db = setup_database
    client_obj, user, token = _create_test_customer(db, "customer_pay@example.com")

    # Configure YooKassa in settings
    settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)
    settings.payment_provider = "yookassa"
    settings.yookassa_shop_id = "1509607"
    settings.yookassa_secret_key = "live_secret_test_123"
    db.commit()

    http_client = TestClient(app)
    http_client.cookies.set("tenderlex_customer_session", token)

    mock_resp = {
        "id": "yoo_test_payment_1",
        "status": "pending",
        "amount": {"value": "5000.00", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=1",
        },
    }

    with patch("app.main.create_yookassa_payment", return_value=mock_resp):
        resp = http_client.post(
            "/api/customer/payments/yookassa/create",
            json={"amount_rub": 5000},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["payment_id"] == "yoo_test_payment_1"
        assert data["amount_rub"] == 5000
        assert data["bonus_rub"] == 1500  # Progressive bonus: 5000 -> +1500
        assert data["total_credit_rub"] == 6500
        assert "confirmation_url" in data

    # Verify payment record in DB
    record = db.query(YooKassaPayment).filter(YooKassaPayment.payment_id == "yoo_test_payment_1").first()
    assert record is not None
    assert record.client_id == client_obj.id
    assert record.status == "pending"
    assert record.total_credit_rub == 6500


def test_yookassa_webhook_and_idempotent_crediting(setup_database: Session):
    db = setup_database
    client_obj, user, token = _create_test_customer(db, "webhook_user@example.com")

    settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    settings.payment_provider = "yookassa"
    settings.yookassa_shop_id = "1509607"
    settings.yookassa_secret_key = "live_secret_test_123"
    db.commit()

    # Pre-create payment record
    payment_rec = YooKassaPayment(
        payment_id="yoo_webhook_test_99",
        client_id=client_obj.id,
        user_id=user.id,
        status="pending",
        amount_rub=5000,
        bonus_rub=1500,
        total_credit_rub=6500,
        package_name="Про 5 000 ₽",
    )
    db.add(payment_rec)
    db.commit()

    initial_balance = client_obj.money_balance_kopeks

    webhook_payload = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": "yoo_webhook_test_99",
            "status": "succeeded",
            "amount": {"value": "5000.00", "currency": "RUB"},
            "payment_method": {"type": "sbp"},
            "metadata": {
                "client_id": client_obj.id,
                "amount_rub": "5000",
                "bonus_rub": "1500",
                "total_credit_rub": "6500",
            },
        },
    }

    mock_live_payment = {
        "id": "yoo_webhook_test_99",
        "status": "succeeded",
        "amount": {"value": "5000.00", "currency": "RUB"},
        "payment_method": {"type": "sbp"},
        "metadata": {
            "client_id": client_obj.id,
            "amount_rub": "5000",
            "bonus_rub": "1500",
            "total_credit_rub": "6500",
        },
    }

    http_client = TestClient(app)

    # First webhook invocation -> balance should be credited
    with patch("app.main.fetch_yookassa_payment", return_value=mock_live_payment):
        resp = http_client.post("/api/payments/yookassa/webhook", json=webhook_payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    db.refresh(client_obj)
    db.refresh(payment_rec)
    assert payment_rec.status == "succeeded"
    assert payment_rec.payment_method_type == "sbp"
    assert client_obj.money_balance_kopeks == initial_balance + 650000  # 6500 RUB = 650000 kopeks

    # Second webhook invocation (duplicate/retry from YooKassa) -> must NOT double-credit!
    with patch("app.main.fetch_yookassa_payment", return_value=mock_live_payment):
        resp2 = http_client.post("/api/payments/yookassa/webhook", json=webhook_payload)
        assert resp2.status_code == 200

    db.refresh(client_obj)
    assert client_obj.money_balance_kopeks == initial_balance + 650000  # Strictly identical!


def test_customer_check_payment_status_api(setup_database: Session):
    db = setup_database
    client_obj, user, token = _create_test_customer(db, "check_status@example.com")

    settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    settings.payment_provider = "yookassa"
    settings.yookassa_shop_id = "1509607"
    settings.yookassa_secret_key = "live_secret_test_123"
    db.commit()

    payment_rec = YooKassaPayment(
        payment_id="yoo_check_status_42",
        client_id=client_obj.id,
        user_id=user.id,
        status="succeeded",
        amount_rub=3000,
        bonus_rub=500,
        total_credit_rub=3500,
    )
    db.add(payment_rec)
    db.commit()

    http_client = TestClient(app)
    http_client.cookies.set("tenderlex_customer_session", token)

    resp = http_client.get(f"/api/customer/payments/{payment_rec.payment_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "succeeded"
    assert data["amount_rub"] == 3000
    assert data["total_credit_rub"] == 3500
