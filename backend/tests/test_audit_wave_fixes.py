from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.billing import (
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    OP_RESERVE,
    reconcile_stuck_client_reservations,
)
from app.db import SessionLocal, init_db
from app.main import app
from app.models import BillingTransaction, Client, Job, WebSession, WebUser, new_id
from app.nurturing import unsubscribe_client
from app.report_builder import UNASSIGNED_SUPPLIER_SECTION, write_supplier_xlsx
from app.repository import get_or_create_settings
from app.security_shield import create_human_challenge, verify_human_challenge
from app.web_auth import (
    create_web_session,
    get_or_create_yandex_web_user,
    hash_password,
    verify_password,
)
from app.yookassa_service import YooKassaTransientError, is_trusted_yookassa_webhook_ip


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_yandex_oauth_prevents_unverified_pre_account_takeover(db_session: Session):
    db = db_session
    victim_email = f"victim-{new_id()[:8]}@yandex.ru"

    pre_client = Client(
        id=new_id(),
        telegram_id=f"web:{new_id()}",
        name="Attacker Squat",
    )
    db.add(pre_client)
    db.flush()

    attacker_user = WebUser(
        id=new_id(),
        client_id=pre_client.id,
        email=victim_email,
        password_hash=hash_password("AttackerKnownPass123!"),
        name="Attacker",
        is_active=True,
        is_email_verified=False,
    )
    db.add(attacker_user)
    db.commit()

    attacker_token, _, _ = create_web_session(db, attacker_user)
    assert attacker_token
    assert db.query(WebSession).filter(WebSession.user_id == attacker_user.id).count() == 1

    claimed_user, created = get_or_create_yandex_web_user(
        db,
        yandex_user_id=f"ya-{new_id()[:10]}",
        email=victim_email,
        name="Real Owner",
    )
    assert created is False
    assert claimed_user.id == attacker_user.id
    assert claimed_user.is_email_verified is True
    assert verify_password("AttackerKnownPass123!", claimed_user.password_hash) is False
    assert db.query(WebSession).filter(WebSession.user_id == claimed_user.id).count() == 0


def test_human_challenge_single_use_replay_blocked():
    ch = create_human_challenge()
    token = ch["token"]

    # Too-fast check does not burn token before min_elapsed_sec elapses
    ok_fast, reason_fast = verify_human_challenge(token, min_elapsed_sec=60.0)
    assert ok_fast is False
    assert reason_fast == "submitted_too_fast"

    # First valid verification succeeds
    ok1, reason1 = verify_human_challenge(token, min_elapsed_sec=0.0)
    assert ok1 is True
    assert reason1 == "ok"

    # Replay of the exact same challenge token is rejected
    ok2, reason2 = verify_human_challenge(token, min_elapsed_sec=0.0)
    assert ok2 is False
    assert reason2 == "challenge_replayed"


def test_yookassa_webhook_ip_allowlist_and_transient_retry_503(db_session: Session):
    assert is_trusted_yookassa_webhook_ip("185.71.76.5") is True
    assert is_trusted_yookassa_webhook_ip("77.75.153.10") is True
    assert is_trusted_yookassa_webhook_ip("203.0.113.99") is False

    settings = get_or_create_settings(db_session)
    settings.yookassa_shop_id = "test_shop_id"
    settings.yookassa_secret_key = "test_secret_key"
    db_session.commit()

    client = TestClient(app, client=("127.0.0.1", 50000))
    payload = {
        "event": "payment.succeeded",
        "object": {"id": "2d000000-0000-4000-8000-000000000099", "status": "succeeded"},
    }

    res_untrusted = client.post(
        "/api/payments/yookassa/webhook",
        headers={"X-Real-IP": "203.0.113.99"},
        json=payload,
    )
    assert res_untrusted.status_code == 403

    with patch(
        "app.main.fetch_yookassa_payment",
        side_effect=YooKassaTransientError("Temporary upstream timeout"),
    ):
        res_transient = client.post(
            "/api/payments/yookassa/webhook",
            headers={"X-Real-IP": "185.71.76.5"},
            json=payload,
        )
    assert res_transient.status_code == 503


def test_reconcile_stuck_client_reservations_unfreezes_orphaned_funds(db_session: Session):
    db = db_session
    c = Client(
        id=new_id(),
        telegram_id=f"web:{new_id()}",
        name="Stuck Reserve Test",
        money_balance_kopeks=50_000,
        money_reserved_kopeks=29_800,
    )
    db.add(c)
    db.flush()

    done_job = Job(
        id=new_id(),
        client_id=c.id,
        mode="analysis_and_suppliers",
        status="completed",
        title="Done job with leaked report reserve",
    )
    running_job = Job(
        id=new_id(),
        client_id=c.id,
        mode="supplier_search",
        status="running",
        title="Active running job",
    )
    db.add_all([done_job, running_job])
    db.flush()

    db.add_all(
        [
            BillingTransaction(
                id=new_id(),
                client_id=c.id,
                job_id=done_job.id,
                kind=KIND_PROCUREMENT_REPORT,
                operation=OP_RESERVE,
                units=1,
                amount_kopeks=9_900,
                balance_after_kopeks=50_000,
                reserved_after_kopeks=9_900,
                note="Reserve report",
            ),
            BillingTransaction(
                id=new_id(),
                client_id=c.id,
                job_id=running_job.id,
                kind=KIND_SUPPLIER_SEARCH,
                operation=OP_RESERVE,
                units=1,
                amount_kopeks=19_900,
                balance_after_kopeks=50_000,
                reserved_after_kopeks=29_800,
                note="Reserve active search",
            ),
        ]
    )
    db.commit()

    repaired = reconcile_stuck_client_reservations(db, client_ids=[c.id])
    assert len(repaired) == 1
    assert repaired[0]["reserved_before_kopeks"] == 29_800
    assert repaired[0]["reserved_after_kopeks"] == 19_900
    assert repaired[0]["unfrozen_kopeks"] == 9_900
    assert done_job.id in repaired[0]["released_orphan_jobs"]

    db.refresh(c)
    assert c.money_reserved_kopeks == 19_900
    assert c.money_balance_kopeks == 50_000


def test_report_builder_multi_item_unassigned_section_and_clean_phones():
    profile = {
        "items": [
            {"id": "item-1", "name": "Трансформатор силовой ТМГ-1000"},
            {"id": "item-2", "name": "Ячейка КСО-298 высоковольтная"},
        ]
    }
    rows = [
        {
            "company_name": "ООО Завод Трансформаторов",
            "site": "https://trans-zavod.ru",
            "phone": "+7 (495) 111-22-33, +7 (800) 555-35-35 доб. 104",
            "email": "sales@trans-zavod.ru",
            "product_fit": "exact",
            "procurement_item_id": "item-1",
            "procurement_item": "Трансформатор силовой ТМГ-1000",
        },
        {
            "company_name": "ООО ЭлектроКомплект Общий",
            "site": "https://electro-obsh.ru",
            "phone": "+7 812 300-40-50",
            "email": "info@electro-obsh.ru",
            "product_fit": "category",
            "procurement_item_id": "",
            "procurement_item": "Комплексные поставки кабельно-проводниковой продукции",
        },
    ]
    with tempfile.TemporaryDirectory() as tmp:
        xlsx_path = Path(tmp) / "multi_clean.xlsx"
        write_supplier_xlsx(
            xlsx_path,
            rows,
            title="Электрооборудование подстанции",
            target=2,
            profile=profile,
        )
        wb = load_workbook(xlsx_path)
        ws = wb["Сводный реестр"]
        # Inspect table body rows starting from row 6 (below header row 5)
        body_a = [str(ws.cell(row=r, column=1).value or "") for r in range(6, ws.max_row + 1)]
        col_c = [str(ws.cell(row=r, column=3).value or "") for r in range(6, ws.max_row + 1)]
        wb.close()

    pos1_idx = next(i for i, v in enumerate(body_a) if "Позиция 1:" in v)
    pos2_idx = next(i for i, v in enumerate(body_a) if "Позиция 2:" in v)
    unassigned_idx = next(i for i, v in enumerate(body_a) if UNASSIGNED_SUPPLIER_SECTION in v)
    assert pos1_idx < pos2_idx < unassigned_idx
    assert "ООО ЭлектроКомплект Общий" not in body_a[pos1_idx:pos2_idx]
    assert "ООО ЭлектроКомплект Общий" in body_a[unassigned_idx:]

    # Multi-phone cell does not get an ugly visible leading apostrophe
    assert any(v == "+7 (495) 111-22-33, +7 (800) 555-35-35 доб. 104" for v in col_c)


def test_nurturing_unsubscribe_handles_empty_or_none_telegram_id(db_session: Session):
    db = db_session
    c = Client(
        id=new_id(),
        telegram_id="",
        name="Empty TG Client",
        marketing_unsubscribed=False,
    )
    db.add(c)
    db.commit()

    assert unsubscribe_client(db, c.id, reason="test_empty_tg") is True
    db.refresh(c)
    assert c.marketing_unsubscribed is True
