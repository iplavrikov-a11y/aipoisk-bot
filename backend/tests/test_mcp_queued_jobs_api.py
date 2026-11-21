from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, db_session
from app.mcp_api import generate_api_key
from app.models import ApiKey, Client, Job, SystemSettings


def test_queued_router_is_registered_on_public_application():
    from app.main import app
    paths = {route.path for route in app.routes}
    assert "/api/v1/mcp/jobs" in paths
    assert "/api/v1/mcp/jobs/{job_id}/position-selection" in paths


@pytest.fixture()
def queued_api(monkeypatch):
    # The public application registers this router in main.py.  A small app keeps
    # this contract test isolated from unrelated customer/admin routes.
    from app.mcp_jobs_api import router

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def database():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[db_session] = database
    db = factory()
    db.add(SystemSettings(id=1, geo_radius_search_enabled_global=True))
    linked = Client(
        telegram_id="queued-linked",
        is_active=True,
        allowed_supplier_search=True,
        allowed_exact_product=True,
        allowed_procurement_report=True,
        allowed_price_monitoring=True,
        allowed_geo_radius=True,
        money_balance_kopeks=100_000,
    )
    orphan = Client(telegram_id="queued-orphan", is_active=True)
    db.add_all([linked, orphan])
    db.flush()
    raw_linked, linked_hash, linked_prefix = generate_api_key()
    raw_orphan, orphan_hash, orphan_prefix = generate_api_key()
    db.add_all([
        ApiKey(
            key_hash=linked_hash, key_prefix=linked_prefix, client_id=linked.id,
            is_active=True, allowed_supplier_search=True, allowed_exact_product=True,
            allowed_procurement_report=True, allowed_price_monitoring=True,
        ),
        ApiKey(
            key_hash=orphan_hash, key_prefix=orphan_prefix, is_active=True,
            allowed_supplier_search=True, allowed_exact_product=True,
            allowed_procurement_report=True,
        ),
    ])
    db.commit()

    async def fake_create_customer_job_api(**kwargs):
        job = Job(
            client_id=kwargs["context"].user.client_id,
            created_by_telegram_id="api:test",
            mode=kwargs["mode"],
            status="pending",
            title="Queued request",
            delivery_city=kwargs["delivery_city"],
            geo_radius_km=kwargs["geo_radius_km"],
        )
        kwargs["db"].add(job)
        kwargs["db"].commit()
        if kwargs["text"] == "batch":
            sibling = Job(
                client_id=job.client_id,
                created_by_telegram_id="api:test",
                mode=job.mode,
                status="pending",
                title="Queued sibling",
            )
            kwargs["db"].add(sibling)
            kwargs["db"].commit()
            return {
                "batch": True,
                "count": 2,
                "jobs": [{"id": job.id, "status": job.status, "mode": job.mode}, {"id": sibling.id, "status": sibling.status, "mode": sibling.mode}],
            }
        return {
            "batch": False,
            "count": 1,
            "job": {
                "id": job.id,
                "status": job.status,
                "mode": job.mode,
                "delivery_city": job.delivery_city,
                "geo_radius_km": job.geo_radius_km,
            },
        }

    import app.main as main
    monkeypatch.setattr(main, "create_customer_job_api", fake_create_customer_job_api)
    yield TestClient(app), factory, raw_linked, raw_orphan
    app.dependency_overrides.clear()
    engine.dispose()


def test_create_queued_job_requires_linked_client_key(queued_api):
    client, _factory, _linked, orphan = queued_api
    response = client.post(
        "/api/v1/mcp/jobs",
        data={"mode": "supplier_search", "text": "Кабель ВВГнг"},
        headers={"Authorization": f"Bearer {orphan}"},
    )
    assert response.status_code == 403
    assert "linked" in response.json()["detail"].lower()


def test_create_queued_job_persists_idempotent_operation_and_passes_geo(queued_api):
    client, factory, linked, _orphan = queued_api
    headers = {"Authorization": f"Bearer {linked}", "Idempotency-Key": "queued-job-1"}
    data = {
        "mode": "price_monitoring",
        "text": "Насос центробежный",
        "delivery_city": "Казань",
        "geo_radius_km": "250",
    }
    created = client.post("/api/v1/mcp/jobs", data=data, headers=headers)
    assert created.status_code == 201
    assert created.json()["job"]["mode"] == "price_monitoring"
    assert created.json()["job"]["geo_radius_km"] == 250

    duplicate = client.post("/api/v1/mcp/jobs", data=data, headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["job_id"] == created.json()["job"]["id"]
    with Session(factory.kw["bind"]) as db:
        assert db.query(Job).count() == 1


def test_paid_client_can_queue_procurement_when_key_scope_is_allowed(queued_api):
    client, factory, linked, _orphan = queued_api
    with Session(factory.kw["bind"]) as db:
        key = db.query(ApiKey).filter(ApiKey.client_id.isnot(None)).first()
        account = db.get(Client, key.client_id)
        # This flag is an access toggle for a separate legacy/client surface;
        # normal paid cabinet access is decided by the tariff/balance helper.
        account.allowed_procurement_report = False
        db.commit()
    response = client.post(
        "/api/v1/mcp/jobs",
        data={"mode": "procurement_report", "text": "Проект контракта"},
        headers={"Authorization": f"Bearer {linked}"},
    )
    assert response.status_code == 201
    assert response.json()["job"]["mode"] == "procurement_report"


def test_batch_job_idempotency_retains_every_created_job_id(queued_api):
    client, factory, linked, _orphan = queued_api
    response = client.post(
        "/api/v1/mcp/jobs",
        data={"mode": "supplier_search", "text": "batch"},
        headers={"Authorization": f"Bearer {linked}", "Idempotency-Key": "batch-queued-job-1"},
    )
    assert response.status_code == 201
    job_ids = [item["id"] for item in response.json()["jobs"]]
    from app.models import ApiOperation
    with Session(factory.kw["bind"]) as db:
        operation = db.query(ApiOperation).one()
        assert json.loads(operation.job_ids_json) == job_ids
        assert operation.job_id == job_ids[0]
    duplicate = client.post(
        "/api/v1/mcp/jobs", data={"mode": "supplier_search", "text": "batch"},
        headers={"Authorization": f"Bearer {linked}", "Idempotency-Key": "batch-queued-job-1"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["job_ids"] == job_ids


def test_restricted_key_cannot_enumerate_or_read_other_module_jobs(queued_api):
    client, factory, linked, _orphan = queued_api
    with Session(factory.kw["bind"]) as db:
        key = db.query(ApiKey).filter(ApiKey.client_id.isnot(None)).one()
        key.allowed_exact_product = False
        key.allowed_price_monitoring = False
        key.allowed_procurement_report = False
        allowed = Job(client_id=key.client_id, mode="supplier_search", status="completed", title="Visible")
        hidden = Job(client_id=key.client_id, mode="exact_product", status="completed", title="Hidden")
        combined = Job(client_id=key.client_id, mode="analysis_and_suppliers", status="completed", title="Hidden combined")
        db.add_all([allowed, hidden, combined]); db.commit()
        allowed_id, hidden_id, combined_id = allowed.id, hidden.id, combined.id
    headers = {"Authorization": f"Bearer {linked}"}
    listing = client.get("/api/v1/mcp/jobs", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] == 1
    assert [row["id"] for row in listing.json()["jobs"]] == [allowed_id]
    assert client.get(f"/api/v1/mcp/jobs/{hidden_id}", headers=headers).status_code == 403
    assert client.get(f"/api/v1/mcp/jobs/{combined_id}", headers=headers).status_code == 403


def test_job_routes_hide_another_clients_job_and_allow_owner_status(queued_api):
    client, factory, linked, _orphan = queued_api
    with Session(factory.kw["bind"]) as db:
        key = db.query(ApiKey).filter(ApiKey.key_hash.isnot(None), ApiKey.client_id.isnot(None)).first()
        other = Client(telegram_id="queued-other", is_active=True)
        db.add(other); db.flush()
        job = Job(client_id=other.id, mode="supplier_search", status="completed", title="Other")
        own = Job(client_id=key.client_id, mode="supplier_search", status="completed", title="Own")
        db.add_all([job, own]); db.commit()
        foreign_id, own_id = job.id, own.id
    headers = {"Authorization": f"Bearer {linked}"}
    assert client.get(f"/api/v1/mcp/jobs/{foreign_id}", headers=headers).status_code == 404
    own = client.get(f"/api/v1/mcp/jobs/{own_id}", headers=headers)
    assert own.status_code == 200
    assert own.json()["job"]["id"] == own_id


@pytest.mark.parametrize('mode', ['supplier_search', 'analysis_and_suppliers'])
def test_queued_supplier_strategy_preserves_input_revision_for_both_search_modes(queued_api, monkeypatch, mode):
    import app.main as main
    client, factory, raw_key, _ = queued_api
    with factory() as db:
        owner = db.query(ApiKey).filter(ApiKey.client_id.isnot(None)).first()
        job = Job(client_id=owner.client_id, mode=mode, status='awaiting_customer_confirmation',
                  confirmation_kind='multi_item_strategy')
        db.add(job); db.commit(); job_id = job.id
    calls = []
    def choose(jid, **kwargs):
        calls.append((jid, kwargs))
        return {'job': {'id': jid, 'status': 'pending'}}
    monkeypatch.setattr(main, 'choose_customer_multi_item_strategy_api', choose)

    response = client.post(f'/api/v1/mcp/jobs/{job_id}/choose-strategy',
        headers={'Authorization': f'Bearer {raw_key}'},
        json={'multi_item_mode': 'balanced', 'selected_item_ids': ['item-2'], 'revision': 'source-revision'})

    assert response.status_code == 200, response.json()
    assert calls[0][1]['revision'] == 'source-revision'
    assert calls[0][1]['selected_item_ids'] == ['item-2']
