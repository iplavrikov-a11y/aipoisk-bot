from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Client, Invoice, WebSession, WebUser, new_id, now_utc
from app.invoice_service import (
    SELLER_ACCOUNT,
    SELLER_BANK_BIK,
    SELLER_INN,
    SELLER_NAME,
    num_to_words_ru,
    format_rubles_num,
    generate_invoice_xlsx,
    generate_invoice_pdf,
    render_invoice_html,
)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_test_customer(db: Session, email: str = "b2b_client@example.com") -> tuple[Client, WebUser, str]:
    c_id = new_id()
    client = Client(id=c_id, telegram_id=f"web_client_{c_id}", name="B2B Client Company", money_balance_kopeks=0)
    db.add(client)
    db.flush()

    user = WebUser(
        id=new_id(),
        client_id=client.id,
        email=email,
        password_hash="test_hash",
        name="Иван Иванов",
        is_email_verified=True,
    )
    db.add(user)
    db.commit()

    from app.web_auth import create_web_session
    token, csrf_token, session = create_web_session(db, user)
    return client, user, token


def test_num_to_words_and_formatting():
    assert num_to_words_ru(5000) == "Пять тысяч рублей 00 копеек. Без НДС."
    assert num_to_words_ru(10000) == "Десять тысяч рублей 00 копеек. Без НДС."
    assert num_to_words_ru(25001) == "Двадцать пять тысяч один рубль 00 копеек. Без НДС."
    assert format_rubles_num(10000) == "10 000,00"


def test_dadata_company_by_inn_api(setup_database: Session):
    client = TestClient(app)

    # Invalid INN
    res = client.get("/api/customer/dadata/company-by-inn?inn=123")
    assert res.status_code == 400

    # Mock DaData response for valid INN
    mock_profile = {
        "inn": "7701234567",
        "kpp": "770101001",
        "company_name": 'ООО "СТРОЙПРОЕКТ"',
        "legal_address": "125009, г. Москва, ул. Тверская, д. 10",
        "management_name": "Петров П.П.",
    }
    with patch("app.dadata_client.enrich_company_by_inn", new=AsyncMock(return_value=mock_profile)):
        res = client.get("/api/customer/dadata/company-by-inn?inn=7701234567")
        assert res.status_code == 200
        data = res.json()
        assert data["found"] is True
        assert data["company"]["company_name"] == 'ООО "СТРОЙПРОЕКТ"'
        assert data["company"]["kpp"] == "770101001"


def test_create_and_manage_invoices_pipeline(setup_database: Session, tmp_path):
    db = setup_database
    test_client, test_user, token = _create_test_customer(db, "director@romashka.ru")

    client = TestClient(app)
    client.cookies.set("tenderlex_customer_session", token)

    # 1. Create invoice for 10 000 RUB (package with 40% bonus -> +4 000 RUB bonus, total 14 000 RUB)
    with patch("app.invoice_service.notify_admin_telegram", new=AsyncMock()) as mock_notify:
        payload = {
            "amount_rub": 10000,
            "tariff_name": "Пакет «Оптимальный»",
            "buyer_inn": "7701234567",
            "buyer_kpp": "770101001",
            "buyer_name": 'ООО "РОМАШКА"',
            "buyer_address": "г. Москва, ул. Арбат, 1",
            "buyer_email": "director@romashka.ru",
        }
        res = client.post("/api/customer/invoices", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        inv = data["invoice"]
        assert inv["invoice_number"].startswith("TL-")
        assert inv["amount_rub"] == 10000
        assert inv["bonus_rub"] == 4000
        assert inv["total_credit_rub"] == 14000
        assert inv["buyer_name"] == 'ООО "РОМАШКА"'
        assert inv["status"] == "issued"
        invoice_id = inv["id"]

    # 2. List customer invoices
    res = client.get("/api/customer/invoices")
    assert res.status_code == 200
    invoices = res.json()["invoices"]
    assert any(i["id"] == invoice_id for i in invoices)

    # 3. Get single invoice details
    res = client.get(f"/api/customer/invoices/{invoice_id}")
    assert res.status_code == 200
    assert res.json()["invoice"]["id"] == invoice_id

    # 4. Render HTML invoice view
    res = client.get(f"/api/customer/invoices/{invoice_id}/html")
    assert res.status_code == 200
    html = res.text
    assert SELLER_NAME in html
    assert SELLER_INN in html
    assert SELLER_BANK_BIK in html
    assert SELLER_ACCOUNT in html
    assert 'ООО "РОМАШКА"' in html
    assert "10 000,00" in html
    assert "Четырнадцать тысяч рублей" not in html  # sum to pay is 10 000
    assert "Десять тысяч рублей 00 копеек. Без НДС." in html

    # 5. Download Excel (.xlsx) and PDF (.pdf)
    res_xlsx = client.get(f"/api/customer/invoices/{invoice_id}/download?format=xlsx")
    assert res_xlsx.status_code == 200
    assert len(res_xlsx.content) > 1000
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_xlsx.headers["content-type"]

    res_pdf = client.get(f"/api/customer/invoices/{invoice_id}/download?format=pdf")
    assert res_pdf.status_code == 200
    assert len(res_pdf.content) > 1000
    assert res_pdf.headers["content-type"] == "application/pdf"

    # 6. Admin marks invoice as paid
    from app.config import config
    admin_headers = {"X-Admin-Token": config.admin_token or "change-me"}

    res = client.post(f"/api/admin/invoices/{invoice_id}/mark-paid", headers=admin_headers)
    assert res.status_code == 200, res.text
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["invoice"]["status"] == "paid"

    # Verify balance was credited: 14 000 RUB = 1 400 000 kopeks
    db.refresh(test_client)
    assert test_client.money_balance_kopeks == 1_400_000

    # Idempotent second call
    res2 = client.post(f"/api/admin/invoices/{invoice_id}/mark-paid", headers=admin_headers)
    assert res2.status_code == 200
    db.refresh(test_client)
    assert test_client.money_balance_kopeks == 1_400_000


def test_custom_manual_amount_and_ip_buyer(setup_database: Session):
    db = setup_database
    test_client, test_user, token = _create_test_customer(db, "ip_buyer@test.ru")

    client = TestClient(app)
    client.cookies.set("tenderlex_customer_session", token)

    # Invoice for custom amount (e.g. 50 000 RUB -> 50% bonus -> +25 000 RUB, total 75 000 RUB)
    # Buyer is an Individual Entrepreneur (12-digit INN, no KPP)
    payload = {
        "amount_rub": 50000,
        "tariff_name": "Пополнение баланса (ручная сумма)",
        "buyer_inn": "352812345678",
        "buyer_kpp": "",
        "buyer_name": "ИП Сидоров Алексей Михайлович",
        "buyer_address": "162600, Вологодская обл., г. Череповец, ул. Ленина, д. 5",
        "buyer_email": "ip_buyer@test.ru",
    }
    res = client.post("/api/customer/invoices", json=payload)
    assert res.status_code == 200
    data = res.json()
    inv = data["invoice"]
    assert inv["amount_rub"] == 50000
    assert inv["bonus_rub"] == 25000
    assert inv["total_credit_rub"] == 75000
    assert inv["buyer_kpp"] == ""

    # Verify HTML render has the right text and no empty КПП
    res_html = client.get(f"/api/customer/invoices/{inv['id']}/html")
    assert res_html.status_code == 200
    assert "Пятьдесят тысяч рублей 00 копеек. Без НДС." in res_html.text
    assert "ИП Сидоров Алексей Михайлович" in res_html.text
