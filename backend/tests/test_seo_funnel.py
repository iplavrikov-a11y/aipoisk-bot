from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Client, Invoice, Job, WebUser, YooKassaPayment


def test_funnel_counts_one_consenting_visit_through_verified_service_records():
    from app.seo_funnel import attach_registration, create_entry, funnel_report, preserve_expired_job

    now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
    started = now - timedelta(days=2)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert create_entry(db, "google", "/cabinet", started) is None
        assert create_entry(db, "google", "/baza-znaniy/kp?q=private", started) is None
        assert create_entry(db, "unknown", "/", started) is None
        entry = create_entry(db, "google", "/baza-znaniy/kp", started)
        create_entry(db, "yandex", "/", started)
        create_entry(db, "bing", "/", now)
        client = Client(id="client", telegram_id="test", created_at=started + timedelta(hours=1))
        user = WebUser(id="user", client_id=client.id, email="user@example.com", created_at=client.created_at)
        db.add_all([client, user])
        db.flush()
        assert attach_registration(db, entry, user)
        assert not attach_registration(db, entry, user)
        db.add_all([
            Job(client_id=client.id, created_at=started, status="completed", completed_at=started, result_path="old"),
            Job(client_id=client.id, created_at=client.created_at, status="completed", completed_at=now, result_path="admin", is_admin_rerun=True),
            Job(client_id=client.id, created_at=client.created_at, status="awaiting_customer_confirmation", completed_at=now, result_path="not-available"),
            Invoice(invoice_number="proof", client_id=client.id, status="proof_submitted", paid_at=now, amount_rub=500),
            YooKassaPayment(payment_id="pending", client_id=client.id, status="pending", paid_at=now, amount_rub=500),
        ])
        db.commit()
        partial = funnel_report(db, now)["totals"]
        assert partial == {"entries": 2, "registrations": 1, "task_started": 1, "result_ready": 0, "first_payment": 0}

        job = Job(client_id=client.id, created_at=client.created_at, status="completed", completed_at=now, result_path="ready")
        db.add_all([job, YooKassaPayment(payment_id="paid", client_id=client.id, status="succeeded", paid_at=now, amount_rub=500)])
        db.commit()
        preserve_expired_job(db, job)
        db.delete(job)
        db.commit()

        report = funnel_report(db, now)
        assert report["totals"] == {"entries": 2, "registrations": 1, "task_started": 1, "result_ready": 1, "first_payment": 1}
        assert report["rows"][0] == {"source": "google", "landing": "/baza-znaniy/kp", "entries": 1, "registrations": 1, "task_started": 1, "result_ready": 1, "first_payment": 1}


def test_consent_withdrawal_removes_linked_cohort_and_pruning_removes_expired_entry():
    from app.seo_funnel import attach_registration, create_entry, delete_entry, funnel_report, prune_entries

    now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        client = Client(id="client", telegram_id="test", created_at=now - timedelta(days=2))
        user = WebUser(id="user", client_id=client.id, email="user@example.com", created_at=client.created_at)
        db.add_all([client, user])
        db.flush()
        entry = create_entry(db, "yandex", "/", now - timedelta(days=3))
        old = create_entry(db, "yandex", "/", now - timedelta(days=91))
        assert attach_registration(db, entry, user)
        assert not attach_registration(db, old, user)
        db.commit()
        assert delete_entry(db, entry, None) == 1
        assert prune_entries(db, now) == 1
        db.commit()
        assert funnel_report(db, now)["totals"]["entries"] == 0


def test_entry_http_route_enforces_same_origin_and_clears_linkage(monkeypatch):
    from app.db import db_session
    from app.main import app
    from app.models import SeoEntry
    from app.seo_funnel import ENTRY_COOKIE

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, db_session, test_db)
    site = "https://tenderlex.ru"
    endpoint = "/api/customer/seo-entry"
    payload = {"source": "google", "landing": "/"}
    headers = {"Origin": site, "Sec-Fetch-Site": "same-origin"}
    client = TestClient(app, base_url=site)
    try:
        assert client.post(endpoint, json=payload, headers={"Origin": "https://other.example"}).status_code == 403
        assert client.post(endpoint, json=payload, headers={**headers, "Sec-Fetch-Site": "cross-site"}).status_code == 403
        response = client.post(endpoint, json=payload, headers=headers)
        assert response.status_code == 204 and response.content == b""
        cookie = response.headers["set-cookie"]
        assert all(flag in cookie for flag in ["HttpOnly", "Secure", "Path=/api/customer", "SameSite=lax"])
        assert client.cookies.get(ENTRY_COOKIE)
        assert client.post(endpoint, json=payload, headers=headers).status_code == 204
        assert client.delete(endpoint, headers={"Origin": "https://other.example"}).status_code == 403
        with Session(engine) as db:
            row = db.query(SeoEntry).one()
            assert row.token_hash != client.cookies.get(ENTRY_COOKIE)
            assert row.source == "google" and row.landing == "/"
        assert client.delete(endpoint, headers=headers).status_code == 204
        assert not client.cookies.get(ENTRY_COOKIE)
        with Session(engine) as db:
            assert db.query(SeoEntry).count() == 0
    finally:
        client.close()
        engine.dispose()
