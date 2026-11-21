from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.billing import KIND_MONEY, OP_GRANT
from app.config import config
from app.db import SessionLocal, init_db
from app.main import _sync_open_invoice_on_admin_grant, app
from app.models import BillingTransaction, Client, Invoice, WebUser, YooKassaPayment, new_id
from app.yookassa_service import format_payment_method_type


@pytest.fixture()
def db_session_clean(monkeypatch):
    monkeypatch.setattr(config, "admin_token", "test-admin-secret-token")
    init_db()
    db = SessionLocal()
    try:
        db.query(YooKassaPayment).delete()
        db.query(Invoice).delete()
        db.query(BillingTransaction).delete()
        db.query(WebUser).delete()
        db.query(Client).delete()
        db.commit()
        yield db
    finally:
        db.close()


def _make_client(db: Session, *, name: str, email: str = "", client_number: int = 100) -> Client:
    cid = new_id()
    client = Client(
        id=cid,
        client_number=client_number,
        telegram_id=f"tg_{cid}",
        name=name,
        money_balance_kopeks=0,
    )
    db.add(client)
    db.flush()
    if email:
        db.add(
            WebUser(
                id=new_id(),
                client_id=cid,
                email=email,
                password_hash="x",
                name=name,
                is_email_verified=True,
            )
        )
    db.commit()
    return client


def test_format_payment_method_sberbank():
    assert format_payment_method_type("sberbank") == "🟢 SberPay"
    assert format_payment_method_type("b2b_sberbank") == "🟢 SberPay B2B"


def test_admin_payments_overview_requires_admin(db_session_clean: Session):
    client = TestClient(app)
    res = client.get("/api/admin/payments/overview")
    assert res.status_code == 401


def test_admin_payments_overview_full_accounting_and_dedup(db_session_clean: Session):
    db = db_session_clean
    now = datetime.now(timezone.utc)
    five_days_ago = now - timedelta(days=5)
    ten_days_ago = now - timedelta(days=10)

    c_yk = _make_client(db, name="Владислав Дмитриев", email="vlad@example.com", client_number=120)
    c_inv = _make_client(db, name="ИП Будин", email="budin@example.com", client_number=80)
    c_manual = _make_client(db, name="Олег Тендеры", email="oleg@example.com", client_number=55)

    # 1. YooKassa succeeded today via sberbank + canceled attempt + waiting_for_capture
    db.add(
        YooKassaPayment(
            id=new_id(),
            payment_id="32935725-000f-5000-b000-1f93a0822038",
            client_id=c_yk.id,
            status="succeeded",
            amount_rub=1000,
            bonus_rub=0,
            total_credit_rub=1000,
            package_name="Старт",
            payment_method_type="sberbank",
            created_at=five_days_ago,  # created earlier, paid today -> must appear in today!
            paid_at=now,
        )
    )
    db.add(
        YooKassaPayment(
            id=new_id(),
            payment_id="canceled-000f-5000-b000-000000000001",
            client_id=c_yk.id,
            status="canceled",
            amount_rub=3000,
            bonus_rub=500,
            total_credit_rub=3500,
            package_name="Оптимальный",
            payment_method_type="",
            created_at=now,
        )
    )
    db.add(
        YooKassaPayment(
            id=new_id(),
            payment_id="waiting-000f-5000-b000-000000000002",
            client_id=c_yk.id,
            status="waiting_for_capture",
            amount_rub=2000,
            bonus_rub=0,
            total_credit_rub=2000,
            package_name="Старт",
            payment_method_type="sbp",
            created_at=now,
        )
    )

    # 2. Invoices:
    # - manual_grant paid 5 days ago (5000 + 1500 bonus = 6500) + matching admin BillingTransaction (must dedup!)
    # - manual_closed (must NOT count in revenue!)
    # - proof_submitted 10 days ago (must appear in proof_submitted_all_time even for period='today')
    # - orphaned client_id (must NOT drop and must return client_exists=False)
    db.add(
        Invoice(
            id=new_id(),
            invoice_number="TL-2026-0006",
            client_id=c_inv.id,
            amount_rub=5000,
            bonus_rub=1500,
            total_credit_rub=6500,
            tariff_name="Про",
            buyer_inn="180501757839",
            buyer_name="ИП Будин Андрей Николаевич",
            status="paid",
            settlement_mode="manual_grant",
            created_at=ten_days_ago.replace(tzinfo=None),
            paid_at=five_days_ago.replace(tzinfo=None),
        )
    )
    db.add(
        Invoice(
            id=new_id(),
            invoice_number="TL-2026-0011",
            client_id=c_inv.id,
            amount_rub=5000,
            bonus_rub=0,
            total_credit_rub=5000,
            tariff_name="Про",
            buyer_inn="3500011486",
            buyer_name='ООО "ДП"',
            status="paid",
            settlement_mode="manual_closed",
            created_at=five_days_ago.replace(tzinfo=None),
            paid_at=now.replace(tzinfo=None),
        )
    )
    db.add(
        Invoice(
            id=new_id(),
            invoice_number="TL-2026-0012",
            client_id=c_inv.id,
            amount_rub=4000,
            bonus_rub=0,
            total_credit_rub=4000,
            tariff_name="Про",
            buyer_inn="7701234567",
            buyer_name='ООО "Платёжка"',
            status="proof_submitted",
            proof_original_name="plat.pdf",
            proof_path="/tmp/fake.pdf",
            created_at=ten_days_ago.replace(tzinfo=None),
            proof_submitted_at=ten_days_ago.replace(tzinfo=None),
        )
    )
    db.add(
        Invoice(
            id=new_id(),
            invoice_number="TL-2026-0003",
            client_id="deleted_client_id_xyz",
            amount_rub=3000,
            bonus_rub=500,
            total_credit_rub=3500,
            tariff_name="Оптимальный",
            buyer_inn="3500011486",
            buyer_name="ООО Удалённый",
            status="issued",
            created_at=five_days_ago.replace(tzinfo=None),
        )
    )

    # 3. Manual admin grants:
    # - linked to TL-2026-0006 (6500 RUB within 30 mins of paid_at) -> invoice_linked
    # - refund (120 RUB) -> refund
    # - direct topup (1000 RUB) -> direct_topup
    db.add(
        BillingTransaction(
            id=new_id(),
            client_id=c_inv.id,
            kind=KIND_MONEY,
            operation=OP_GRANT,
            amount_kopeks=650000,
            created_by="admin",
            note="Пополнение баланса (оплата 5000 ₽, бонус +1500 ₽)",
            created_at=five_days_ago + timedelta(minutes=30),
        )
    )
    db.add(
        BillingTransaction(
            id=new_id(),
            client_id=c_manual.id,
            kind=KIND_MONEY,
            operation=OP_GRANT,
            amount_kopeks=12000,
            created_by="admin",
            idempotency_key="refund_test_1",
            note="Возврат за неполный запуск",
            created_at=five_days_ago,
        )
    )
    db.add(
        BillingTransaction(
            id=new_id(),
            client_id=c_manual.id,
            kind=KIND_MONEY,
            operation=OP_GRANT,
            amount_kopeks=100000,
            created_by="admin",
            note="Пополнение баланса по индивидуальному тарифу (1000 ₽)",
            created_at=five_days_ago,
        )
    )
    db.commit()

    http = TestClient(app)
    headers = {"X-Admin-Token": "test-admin-secret-token"}

    # All time, tab=all, status=active (default view)
    res = http.get("/api/admin/payments/overview?period=all&tab=all&status=active", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    s = body["summary"]
    assert s["yookassa"]["succeeded_rub"] == 1000
    assert s["yookassa"]["succeeded_count"] == 1
    assert s["yookassa"]["pending_count"] == 1
    assert s["yookassa"]["canceled_count"] == 1
    assert s["invoices"]["paid_rub"] == 5000  # TL-2026-0011 manual_closed excluded!
    assert s["invoices"]["paid_count"] == 1
    assert s["invoices"]["manual_closed_count"] == 1
    assert s["invoices"]["proof_submitted_all_time"] == 1
    assert s["total_revenue_rub"] == 6000
    assert s["manual"]["direct_rub"] == 1000.0
    assert s["manual"]["refund_rub"] == 120.0
    assert s["manual"]["invoice_linked_rub"] == 6500.0

    # Active all-tab must hide canceled YooKassa, manual_closed, refund, and invoice_linked duplicate
    item_refs = [i["reference_id"] for i in body["items"]]
    assert "32935725-000f-5000-b000-1f93a0822038" in item_refs
    assert "waiting-000f-5000-b000-000000000002" in item_refs
    assert "TL-2026-0006" in item_refs
    assert "TL-2026-0003" in item_refs
    assert "canceled-000f-5000-b000-000000000001" not in item_refs
    assert "TL-2026-0011" not in item_refs
    # Only 1 manual item (direct_topup 1000 RUB), not 3
    manual_in_all = [i for i in body["items"] if i["source"] == "manual"]
    assert len(manual_in_all) == 1
    assert manual_in_all[0]["amount_rub"] == 1000.0

    # SberPay label & orphaned invoice check
    yk_item = next(i for i in body["items"] if i["reference_id"] == "32935725-000f-5000-b000-1f93a0822038")
    assert yk_item["payment_method_label"] == "🟢 SberPay"
    assert yk_item["client_exists"] is True
    assert yk_item["client_number"] == 120

    orphan_item = next(i for i in body["items"] if i["reference_id"] == "TL-2026-0003")
    assert orphan_item["client_exists"] is False
    assert orphan_item["client_id"] is None

    # Today filter must include YooKassa paid today (even though created 5 days ago) AND keep global proof_submitted_all_time=1
    res_today = http.get("/api/admin/payments/overview?period=today&tab=all&status=active", headers=headers)
    assert res_today.status_code == 200
    today_body = res_today.json()
    assert today_body["summary"]["total_revenue_rub"] == 1000
    assert today_body["summary"]["invoices"]["proof_submitted_all_time"] == 1
    today_refs = [i["reference_id"] for i in today_body["items"]]
    assert "32935725-000f-5000-b000-1f93a0822038" in today_refs
    assert "TL-2026-0006" not in today_refs

    # Manual tab with status=all shows all 3 manual rows with correct categories
    res_manual = http.get("/api/admin/payments/overview?period=all&tab=manual&status=all", headers=headers)
    assert res_manual.status_code == 200
    cats = {i["manual_category"]: i["linked_invoice_number"] for i in res_manual.json()["items"]}
    assert cats == {"direct_topup": "", "refund": "", "invoice_linked": "TL-2026-0006"}

    # Search by client_number (#120) and by INN
    res_q = http.get("/api/admin/payments/overview?period=all&tab=all&status=all&q=%23120", headers=headers)
    assert res_q.status_code == 200
    assert all(i["client_number"] == 120 for i in res_q.json()["items"])
    assert res_q.json()["total"] == 3


def test_sync_open_invoice_includes_proof_submitted(db_session_clean: Session):
    db = db_session_clean
    c = _make_client(db, name="Клиент с платёжкой", client_number=201)
    inv = Invoice(
        id=new_id(),
        invoice_number="TL-2026-0099",
        client_id=c.id,
        amount_rub=5000,
        bonus_rub=1000,
        total_credit_rub=6000,
        status="proof_submitted",
    )
    db.add(inv)
    db.commit()

    synced = _sync_open_invoice_on_admin_grant(db, c, pay_kopeks=500000, total_amount_kopeks=600000)
    assert synced is not None
    assert synced.id == inv.id
    assert synced.status == "paid"
    assert synced.settlement_mode == "admin_grant_sync"
