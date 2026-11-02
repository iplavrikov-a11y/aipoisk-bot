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
    save_invoice_payment_proof,
)
from app.config import config


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


@pytest.mark.asyncio
async def test_payment_proof_helper_isolated_storage_and_zero_balance(setup_database: Session, tmp_path, monkeypatch):
    db = setup_database
    client, _, _ = _create_test_customer(db, "proof@test.ru")
    invoice = Invoice(id=new_id(), invoice_number="TL-TEST-PROOF", client_id=client.id, amount_rub=5000, total_credit_rub=5000, buyer_name="Proof")
    db.add(invoice); db.commit(); db.refresh(invoice)
    monkeypatch.setattr(config, "storage_dir", str(tmp_path))
    path = await save_invoice_payment_proof(invoice, b"%PDF-proof", original_name="../../evil.pdf", content_type="application/pdf")
    assert str(tmp_path) in path
    assert invoice.status == "proof_submitted"
    assert invoice.proof_size == 10
    assert client.money_balance_kopeks == 0


@pytest.mark.asyncio
async def test_payment_proof_helper_rejects_invalid_and_closed(setup_database: Session):
    db = setup_database
    client, _, _ = _create_test_customer(db, "proof2@test.ru")
    for status in ("issued", "paid", "cancelled"):
        invoice = Invoice(id=new_id(), invoice_number=f"TL-{status}", client_id=client.id, amount_rub=500, total_credit_rub=500, status=status)
        db.add(invoice); db.commit()
        if status == "issued":
            with pytest.raises(ValueError):
                await save_invoice_payment_proof(invoice, b"", original_name="x.pdf", content_type="application/pdf")
            with pytest.raises(ValueError):
                await save_invoice_payment_proof(invoice, b"x", original_name="x.exe", content_type="application/octet-stream")
        else:
            with pytest.raises(ValueError):
                await save_invoice_payment_proof(invoice, b"%PDF", original_name="x.pdf", content_type="application/pdf")


def test_payment_proof_api_auth_validation_and_no_credit(setup_database: Session, tmp_path, monkeypatch):
    db = setup_database
    owner, owner_user, token = _create_test_customer(db, "api-proof@test.ru")
    other, other_user, other_token = _create_test_customer(db, "other-proof@test.ru")
    invoice = Invoice(id=new_id(), invoice_number="TL-API-PROOF", client_id=owner.id, amount_rub=5000, total_credit_rub=5000, buyer_name="API")
    db.add(invoice); db.commit(); db.refresh(invoice)
    monkeypatch.setattr(config, "storage_dir", str(tmp_path))
    client = TestClient(app)
    client.cookies.set("tenderlex_customer_session", other_token)
    other_csrf = db.query(WebSession).filter(WebSession.user_id == other_user.id).first().csrf_token
    denied = client.post(f"/api/customer/invoices/{invoice.id}/proof", headers={"X-CSRF-Token": other_csrf}, files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")})
    assert denied.status_code == 404
    client.cookies.set("tenderlex_customer_session", token)
    csrf = db.query(WebSession).filter(WebSession.user_id == owner_user.id).first().csrf_token
    no_csrf = client.post(f"/api/customer/invoices/{invoice.id}/proof", files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")})
    assert no_csrf.status_code == 403
    proof_headers = {"X-CSRF-Token": csrf}
    bad_type = client.post(f"/api/customer/invoices/{invoice.id}/proof", headers=proof_headers, files={"file": ("p.exe", b"MZ", "application/octet-stream")})
    assert bad_type.status_code == 400
    bad_sig = client.post(f"/api/customer/invoices/{invoice.id}/proof", headers=proof_headers, files={"file": ("p.pdf", b"not-pdf", "application/pdf")})
    assert bad_sig.status_code == 400
    too_big = client.post(f"/api/customer/invoices/{invoice.id}/proof", headers=proof_headers, files={"file": ("p.pdf", b"%PDF" + b"x" * (10 * 1024 * 1024), "application/pdf")})
    assert too_big.status_code in {400, 413}
    ok = client.post(f"/api/customer/invoices/{invoice.id}/proof", headers=proof_headers, files={"file": ("p.pdf", b"%PDF-1.4 proof", "application/pdf")})
    assert ok.status_code == 200, ok.text
    assert ok.json()["invoice"]["status"] == "proof_submitted"
    db.refresh(owner)
    assert owner.money_balance_kopeks == 0
    # Invoice documents are private to the owning customer.
    client.cookies.set("tenderlex_customer_session", other_token)
    other_html = client.get(f"/api/customer/invoices/{invoice.id}/html")
    other_download = client.get(f"/api/customer/invoices/{invoice.id}/download?format=pdf")
    assert other_html.status_code == 404
    assert other_download.status_code == 404
    client.cookies.delete("tenderlex_customer_session")
    assert client.get(f"/api/customer/invoices/{invoice.id}/html").status_code in {401, 403, 404}


def test_paid_cancelled_proof_download_and_manual_close(setup_database: Session, tmp_path, monkeypatch):
    db = setup_database
    owner, owner_user, token = _create_test_customer(db, "closed-proof@test.ru")
    invoice = Invoice(id=new_id(), invoice_number="TL-CLOSED", client_id=owner.id, amount_rub=500, total_credit_rub=500, buyer_name="Closed")
    db.add(invoice); db.commit(); db.refresh(invoice)
    monkeypatch.setattr(config, "storage_dir", str(tmp_path))
    client = TestClient(app); client.cookies.set("tenderlex_customer_session", token)
    csrf = db.query(WebSession).filter(WebSession.user_id == owner_user.id).first().csrf_token
    assert client.post(f"/api/customer/invoices/{invoice.id}/proof", headers={"X-CSRF-Token": csrf}, files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")}).status_code == 200
    admin = {"X-Admin-Token": config.admin_token or "change-me"}
    proof = client.get(f"/api/admin/invoices/{invoice.id}/proof", headers=admin)
    assert proof.status_code == 200
    assert client.post(f"/api/admin/invoices/{invoice.id}/close-manually", headers=admin, json={}).status_code == 400
    assert client.post(f"/api/admin/invoices/{invoice.id}/close-manually", headers=admin, json={"confirm": True}).status_code == 200
    db.refresh(owner)
    assert owner.money_balance_kopeks == 0
    again = client.post(f"/api/admin/invoices/{invoice.id}/mark-paid", headers=admin)
    assert again.status_code == 200
    db.refresh(owner)
    assert owner.money_balance_kopeks == 0
    paid_proof = client.post(f"/api/customer/invoices/{invoice.id}/proof", headers={"X-CSRF-Token": csrf}, files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")})
    assert paid_proof.status_code == 400
    db.refresh(invoice)
    assert invoice.status == "paid"
    invoice.status = "cancelled"
    db.commit()
    cancelled_proof = client.post(f"/api/customer/invoices/{invoice.id}/proof", headers={"X-CSRF-Token": csrf}, files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")})
    assert cancelled_proof.status_code == 400
    assert client.post(f"/api/admin/invoices/{invoice.id}/mark-paid", headers=admin).status_code == 409
    db.refresh(owner)
    assert owner.money_balance_kopeks == 0


def test_admin_invoice_list_pagination_and_proof_requires_admin(setup_database: Session):
    db = setup_database
    owner, _, token = _create_test_customer(db, "paging@test.ru")
    for idx in range(2):
        db.add(Invoice(id=new_id(), invoice_number=f"TL-PAGE-{idx}", client_id=owner.id, amount_rub=500 + idx, total_credit_rub=500 + idx, buyer_name="Paging"))
    db.commit()
    client = TestClient(app)
    admin = {"X-Admin-Token": config.admin_token or "change-me"}
    first = client.get("/api/admin/invoices?limit=1&offset=0", headers=admin)
    second = client.get("/api/admin/invoices?limit=1&offset=1", headers=admin)
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["invoices"]) == 1
    assert len(second.json()["invoices"]) == 1
    assert first.json()["invoices"][0]["id"] != second.json()["invoices"][0]["id"]
    assert first.json()["total"] >= 2
    unauth = client.get(f"/api/admin/invoices/{first.json()['invoices'][0]['id']}/proof")
    assert unauth.status_code in {401, 403}
