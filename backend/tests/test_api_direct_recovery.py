from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import config
from app.db import Base
from app.jobs import claim_next_job, recover_interrupted_jobs
from app.mcp_api import cancel_api_job, finalize_api_job_success, generate_api_key, start_api_job_with_reservation
from app.models import ApiKey, Client, ClientTariffOverride, Job, now_utc


@pytest.fixture
def direct_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "storage_dir", str(tmp_path))
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db
    engine.dispose()


def _key(db, *, linked=False):
    _, digest, prefix = generate_api_key()
    key = ApiKey(key_hash=digest, key_prefix=prefix, quota_supplier_search=2)
    if linked:
        key.client = Client(name="Direct recovery", telegram_id="direct-recovery", is_active=True,
                            money_balance_kopeks=100_000, money_reserved_kopeks=0)
    db.add(key)
    db.commit()
    if linked:
        db.add(ClientTariffOverride(client_id=key.client_id, kind="supplier_search", price_kopeks=9900, is_enabled=True))
        db.commit()
    return key


def test_standalone_cancellation_returns_exactly_its_reserved_slot(direct_db):
    db = direct_db
    key = _key(db)
    first, _ = start_api_job_with_reservation(db, key, "supplier_search", "cancel")
    second, _ = start_api_job_with_reservation(db, key, "supplier_search", "keep")
    assert cancel_api_job(db, first)
    assert not cancel_api_job(db, first)
    finalize_api_job_success(db, key, first, "supplier_search")
    db.refresh(key)
    assert key.reserved_supplier_search == 1
    assert key.spent_supplier_search == 0
    finalize_api_job_success(db, key, second, "supplier_search")
    db.refresh(key)
    assert key.reserved_supplier_search == 0
    assert key.spent_supplier_search == 1


def test_generic_worker_never_replays_stale_direct_api_call(direct_db):
    db = direct_db
    key = _key(db)
    job, _ = start_api_job_with_reservation(db, key, "supplier_search", "long direct")
    job.updated_at = now_utc() - timedelta(minutes=20)
    db.commit()
    assert recover_interrupted_jobs(db) == []
    assert claim_next_job(db, worker_id="direct-recovery-test") is None
    db.refresh(job)
    assert job.status == "running"
    db.refresh(key)
    assert key.reserved_supplier_search == 1


@pytest.mark.parametrize("linked", [False, True])
def test_stale_direct_call_releases_reservation_once_without_market_replay(direct_db, linked):
    from app.mcp_api import recover_stale_direct_api_jobs

    db = direct_db
    key = _key(db, linked=linked)
    job, _ = start_api_job_with_reservation(db, key, "supplier_search", "interrupted")
    if linked:
        db.refresh(key.client)
        assert key.client.money_reserved_kopeks == 9900
    job.updated_at = now_utc() - timedelta(minutes=61)
    db.commit()
    assert recover_stale_direct_api_jobs(db) == [job.id]
    assert recover_stale_direct_api_jobs(db) == []
    finalize_api_job_success(db, key, job, "supplier_search")
    db.refresh(job)
    db.refresh(key)
    assert job.status == "failed"
    assert key.spent_supplier_search == 0
    assert key.reserved_supplier_search == 0
    if linked:
        db.refresh(key.client)
        assert key.client.money_reserved_kopeks == 0
        assert key.client.money_balance_kopeks == 100_000
    assert claim_next_job(db, worker_id="direct-recovery-test") is None


def test_worker_poll_recovers_expired_direct_call_but_keeps_web_api_job_eligible(direct_db):
    db = direct_db
    key = _key(db)
    direct, _ = start_api_job_with_reservation(db, key, "supplier_search", "expired")
    direct.updated_at = now_utc() - timedelta(minutes=61)
    queued = Job(mode="supplier_search", status="pending", created_by_telegram_id="web:api:test", title="Queued API")
    db.add(queued)
    db.commit()
    assert claim_next_job(db, worker_id="direct-recovery-test") == queued.id
    db.refresh(direct)
    db.refresh(key)
    assert direct.status == "failed"
    assert key.reserved_supplier_search == 0


@pytest.mark.parametrize("terminal", ["cancelled", "failed"])
def test_late_api_response_cannot_overwrite_terminal_operation_status(direct_db, terminal):
    from app.mcp_api import claim_api_operation, complete_api_operation, recover_stale_direct_api_jobs

    db = direct_db
    key = _key(db)
    operation = claim_api_operation(db, key, "supplier_search", "terminal-operation", {"spec": "test"})
    job, _ = start_api_job_with_reservation(db, key, "supplier_search", "late")
    complete_api_operation(db, operation, status_value="processing", job=job)
    if terminal == "cancelled":
        cancel_api_job(db, job)
    else:
        job.updated_at = now_utc() - timedelta(minutes=61)
        db.commit()
        recover_stale_direct_api_jobs(db)
    complete_api_operation(db, operation, status_value="completed", job=job)
    db.refresh(operation)
    assert operation.status == terminal


def _mock_direct_market(monkeypatch, db, *, service, terminate, verified=True):
    from types import SimpleNamespace
    from app import mcp_api
    from app.exact_product.models import ExactProductPosition, ExactProductReport

    async def market(*args, **kwargs):
        job = db.query(Job).filter(Job.status == "running").one()
        if terminate == "cancelled":
            cancel_api_job(db, job)
        elif terminate == "failed":
            job.updated_at = now_utc() - timedelta(minutes=61)
            db.commit()
            mcp_api.recover_stale_direct_api_jobs(db)
        if service == "supplier_search":
            return [{"company_name": "Protected result", "site": "https://example.test"}], {"subject": "Protected result"}
        if service == "exact_product":
            position = ExactProductPosition(
                1, "Protected result",
                "Brand" if verified else "",
                "Model" if verified else "",
                "Factory" if verified else "",
                0.95 if verified else 0.0,
                "Evidence",
                status="found" if verified else "needs_clarification",
            )
            return ExactProductReport("Protected result", 1, [position], "Protected summary")
        return SimpleNamespace(report="Protected procurement report", ai_model="mock")

    if service == "supplier_search":
        async def context(*args):
            return "Specification"
        monkeypatch.setattr(mcp_api, "extract_supplier_search_context", context)
        monkeypatch.setattr(mcp_api, "discover_suppliers", market)
        return mcp_api.mcp_supplier_search, mcp_api.McpSupplierSearchRequest(specification="Specification", include_quote_request=False)
    if service == "exact_product":
        monkeypatch.setattr(mcp_api, "analyze_exact_product", market)
        return mcp_api.mcp_exact_product, mcp_api.McpExactProductRequest(specification="Specification")
    monkeypatch.setattr(mcp_api, "generate_procurement_report", market)
    return mcp_api.mcp_procurement_analyze, mcp_api.McpProcurementAnalyzeRequest(document_text="Procurement document")


@pytest.mark.parametrize("service,verified", [("supplier_search", True), ("exact_product", True), ("exact_product", False), ("procurement_report", True)])
@pytest.mark.parametrize("terminate", ["cancelled", "failed"])
def test_late_direct_endpoint_does_not_deliver_cancelled_or_interrupted_result(direct_db, monkeypatch, service, verified, terminate):
    import asyncio
    from fastapi import HTTPException

    db = direct_db
    key = _key(db, linked=True)
    if service != "supplier_search":
        db.add(ClientTariffOverride(client_id=key.client_id, kind=service, price_kopeks=9900, is_enabled=True))
        db.commit()
    handler, request = _mock_direct_market(monkeypatch, db, service=service, terminate=terminate, verified=verified)
    with pytest.raises(HTTPException) as error:
        asyncio.run(handler(request, idempotency_key="late-result", api_key=key, db=db))
    assert error.value.status_code == 409
    assert "Protected" not in str(error.value.detail)
    job = db.query(Job).one()
    db.refresh(job)
    db.refresh(key)
    db.refresh(key.client)
    assert job.status == terminate
    assert not job.result_path
    assert not job.evidence_path
    assert key.client.money_balance_kopeks == 100_000
    assert key.client.money_reserved_kopeks == 0
    assert getattr(key, f"spent_{service}") == 0


def test_zero_confirmed_exact_report_is_deliverable_free_after_cas(direct_db, monkeypatch):
    import asyncio
    from pathlib import Path

    db = direct_db
    key = _key(db, linked=True)
    db.add(ClientTariffOverride(client_id=key.client_id, kind="exact_product", price_kopeks=9900, is_enabled=True))
    db.commit()
    handler, request = _mock_direct_market(monkeypatch, db, service="exact_product", terminate=None, verified=False)
    response = asyncio.run(handler(request, idempotency_key="free-result", api_key=key, db=db))
    assert response.ok
    assert response.confirmed_positions == 0
    assert response.docx_download_url
    job = db.query(Job).one()
    db.refresh(job)
    db.refresh(key.client)
    assert job.status == "completed"
    assert Path(job.result_path).is_file()
    assert Path(job.evidence_path).is_file()
    assert key.client.money_balance_kopeks == 100_000
    assert key.client.money_reserved_kopeks == 0
