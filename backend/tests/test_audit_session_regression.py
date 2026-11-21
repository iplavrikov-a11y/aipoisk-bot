import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Client, WebSession, WebUser, new_id
from app.web_auth import hash_password, create_web_session, verify_password, PASSWORD_ALGORITHM, PASSWORD_ITERATIONS


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_old_user_with_8_char_password_can_login_and_use_cabinet(db_session: Session):
    """
    Ensure users who registered with 8-character passwords BEFORE our changes
    can still log in, fetch their session, and have 100% normal cabinet access.
    """
    db = db_session
    client = TestClient(app)

    # 1. Create client and user with legacy 8-character password
    # Bypassing the new hash_password check by simulating pre-existing DB row
    import secrets, hashlib, base64
    salt = secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac("sha256", b"8charpwd", salt.encode("utf-8"), PASSWORD_ITERATIONS)
    legacy_hash = f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${base64.urlsafe_b64encode(digest).decode()}"

    test_client = Client(id=new_id(), telegram_id=f"web:{new_id()}", name="Legacy User", money_balance_kopeks=50000)
    db.add(test_client)
    db.flush()

    user = WebUser(
        id=new_id(),
        client_id=test_client.id,
        email="legacy8@example.com",
        password_hash=legacy_hash,
        name="Legacy Eight",
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()

    # 2. Login via API with 8-char password
    res = client.post("/api/customer/auth/login", json={"email": "legacy8@example.com", "password": "8charpwd"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["authenticated"] is True
    assert "csrf_token" in data
    csrf_token = data["csrf_token"]

    session_cookie = res.cookies.get("tenderlex_customer_session")
    assert session_cookie is not None
    client.cookies.set("tenderlex_customer_session", session_cookie)

    # 3. Fetch session
    res_session = client.get("/api/customer/auth/session")
    assert res_session.status_code == 200
    sess_data = res_session.json()
    assert sess_data["authenticated"] is True
    assert sess_data["user"]["email"] == "legacy8@example.com"
    assert sess_data["balance"]["money"]["available_kopeks"] == 50000

    # 4. User can change password from old 8-char to new 10+ char
    res_change = client.post(
        "/api/customer/auth/change-password",
        headers={"x-csrf-token": csrf_token},
        json={"current_password": "8charpwd", "new_password": "NewStrongPassword10!"},
    )
    assert res_change.status_code == 200
    assert res_change.json()["ok"] is True

    # 5. Old password no longer works, new password works
    db.refresh(user)
    assert verify_password("NewStrongPassword10!", user.password_hash) is True
    assert verify_password("8charpwd", user.password_hash) is False


def test_paid_verified_user_can_create_payment_and_invoices(db_session: Session):
    """
    Ensure existing paid/verified users have full access to payments and invoices.
    """
    db = db_session
    client = TestClient(app)

    test_client = Client(id=new_id(), telegram_id=f"web:{new_id()}", name="Paid User", money_balance_kopeks=100000)
    db.add(test_client)
    db.flush()

    user = WebUser(
        id=new_id(),
        client_id=test_client.id,
        email="paid_customer@example.com",
        password_hash="fakehash",
        name="Paid Verified",
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()

    token, csrf_token, _ = create_web_session(db, user)
    client.cookies.set("tenderlex_customer_session", token)

    # 1. Access DaData (verified & logged in)
    mock_profile = {
        "inn": "7701234567",
        "kpp": "770101001",
        "company_name": 'ООО "СТРОЙПРОЕКТ"',
        "legal_address": "г. Москва",
        "management_name": "Иванов И.И.",
    }
    with patch("app.dadata_client.enrich_company_by_inn", new=AsyncMock(return_value=mock_profile)):
        res_dadata = client.get("/api/customer/dadata/company-by-inn?inn=7701234567")
        assert res_dadata.status_code == 200
        assert res_dadata.json()["found"] is True

    # 2. Create invoice
    res_inv = client.post(
        "/api/customer/invoices",
        headers={"x-csrf-token": csrf_token},
        json={
            "amount_rub": 5000,
            "buyer_name": 'ООО "СТРОЙПРОЕКТ"',
            "buyer_inn": "7701234567",
            "buyer_kpp": "770101001",
            "buyer_address": "г. Москва",
        },
    )
    assert res_inv.status_code == 200, res_inv.text
    inv_data = res_inv.json()
    assert "invoice" in inv_data
    assert "id" in inv_data["invoice"]

    # 3. Create YooKassa payment (with valid phone format)
    from app.models import SystemSettings
    settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)
    settings.payment_provider = "yookassa"
    settings.yookassa_shop_id = "1509607"
    settings.yookassa_secret_key = "test_key"
    db.commit()

    mock_payment = {
        "id": "yoo_test_success_999",
        "status": "pending",
        "amount": {"value": "5000.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "confirmation_url": "https://yookassa.ru/checkout/999"},
    }
    with patch("app.main.create_yookassa_payment", return_value=mock_payment):
        res_pay = client.post(
            "/api/customer/payments/yookassa/create",
            headers={"x-csrf-token": csrf_token},
            json={"amount_rub": 5000, "phone": "+7 (999) 111-22-33"},
        )
        assert res_pay.status_code == 200, res_pay.text
        assert res_pay.json()["payment_id"] == "yoo_test_success_999"


def test_unverified_user_cannot_pay_or_invoice_but_is_instructed(db_session: Session):
    """
    Ensure unverified users are safely blocked from payments and invoices with clear instructions.
    """
    db = db_session
    client = TestClient(app)

    test_client = Client(id=new_id(), telegram_id=f"web:{new_id()}", name="Unverified User", money_balance_kopeks=49500)
    db.add(test_client)
    db.flush()

    user = WebUser(
        id=new_id(),
        client_id=test_client.id,
        email="unverified@example.com",
        password_hash="fakehash",
        name="Unverified",
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)
    db.commit()

    token, csrf_token, _ = create_web_session(db, user)
    client.cookies.set("tenderlex_customer_session", token)

    # Payment blocked
    res_pay = client.post(
        "/api/customer/payments/yookassa/create",
        headers={"x-csrf-token": csrf_token},
        json={"amount_rub": 3000, "phone": "+7 999 123 45 67"},
    )
    assert res_pay.status_code == 403
    assert "Подтвердите email" in res_pay.json()["detail"]

    # Invoice blocked
    res_inv = client.post(
        "/api/customer/invoices",
        headers={"x-csrf-token": csrf_token},
        json={"amount_rub": 3000, "buyer_name": "ООО Тест", "buyer_inn": "7701234567"},
    )
    assert res_inv.status_code == 403
    assert "Подтвердите email" in res_inv.json()["detail"]


def test_anonymous_caller_blocked_from_dadata(db_session: Session):
    """
    Ensure unauthenticated scrapers/bots cannot hit DaData through public endpoints.
    """
    client = TestClient(app)
    res1 = client.get("/api/customer/dadata/company-by-inn?inn=7701234567")
    assert res1.status_code == 401

    res2 = client.get("/api/dadata/company-by-inn?inn=7701234567")
    assert res2.status_code == 401
