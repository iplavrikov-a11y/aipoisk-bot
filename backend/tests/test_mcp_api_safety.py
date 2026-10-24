from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.mcp_api import (
    cancel_api_job,
    claim_api_operation,
    complete_api_operation,
    finalize_api_job_success,
    generate_api_key,
    start_api_job_with_reservation,
    McpSupplierSearchRequest,
    build_report_download_signature,
    verify_report_download_signature,
)
from app.models import ApiKey, ApiOperation, Client, ClientTariffOverride, Job, SystemSettings
from app.jobs import next_job_number


def _standalone_key(*, quota: int = 1) -> ApiKey:
    _raw, key_hash, key_prefix = generate_api_key()
    return ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="Safety test key",
        quota_supplier_search=quota,
        quota_exact_product=quota,
        quota_procurement_report=quota,
    )


def test_late_success_finalizer_does_not_overwrite_cancelled_job_or_consume_key_quota():
    db = SessionLocal()
    try:
        key = _standalone_key()
        job = Job(
            job_number=next_job_number(db),
            mode="supplier_search",
            status="cancelled",
            title="Cancelled API request",
        )
        db.add_all([key, job])
        db.commit()

        finalize_api_job_success(db, key, job, "supplier_search")

        db.refresh(key)
        db.refresh(job)
        assert job.status == "cancelled"
        assert key.spent_supplier_search == 0
    finally:
        db.close()


def test_standalone_quota_is_reserved_before_work_so_second_request_is_rejected():
    db = SessionLocal()
    try:
        key = _standalone_key(quota=1)
        db.add(key)
        db.commit()

        start_api_job_with_reservation(db, key, "supplier_search", "first")

        with pytest.raises(HTTPException) as error:
            start_api_job_with_reservation(db, key, "supplier_search", "second")
        assert error.value.status_code == 402
    finally:
        db.close()


def test_two_simultaneous_requests_cannot_spend_the_last_standalone_slot():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    with SessionLocal() as db:
        key = _standalone_key(quota=1)
        db.add(key); db.commit()
        key_id = key.id
    barrier = Barrier(2)

    def request_slot():
        with SessionLocal() as db:
            key = db.get(ApiKey, key_id)
            barrier.wait(timeout=5)
            try:
                job, _ = start_api_job_with_reservation(db, key, "supplier_search", "Concurrent request")
                return 200, job.id
            except HTTPException as error:
                return error.status_code, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(request_slot) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(code for code, _ in results) == [200, 402]
    with SessionLocal() as db:
        key = db.get(ApiKey, key_id)
        assert key.reserved_supplier_search == 1
        jobs = db.query(Job).filter(Job.created_by_telegram_id == f"api:{key_id}").all()
        assert len(jobs) == 1
        assert cancel_api_job(db, jobs[0])
        db.refresh(key)
        assert key.reserved_supplier_search == 0


def test_api_cancel_claims_running_job_before_a_late_finalizer_can_settle_it():
    db = SessionLocal()
    try:
        key = _standalone_key()
        job = Job(job_number=next_job_number(db), mode="supplier_search", status="running", title="API request")
        db.add_all([key, job])
        db.commit()

        assert cancel_api_job(db, job) is True
        finalize_api_job_success(db, key, job, "supplier_search")

        db.refresh(job)
        db.refresh(key)
        assert job.status == "cancelled"
        assert key.spent_supplier_search == 0
    finally:
        db.close()


def test_stale_session_finalizer_cannot_charge_after_another_session_cancels_job():
    """The worker must re-read state inside the settlement lock, not trust its stale Job."""
    db_worker = SessionLocal()
    db_cancel = SessionLocal()
    try:
        key = _standalone_key()
        job = Job(job_number=next_job_number(db_worker), mode="supplier_search", status="running", title="API request")
        db_worker.add_all([key, job])
        db_worker.commit()
        job_id, key_id = job.id, key.id

        stale_job = db_worker.get(Job, job_id)
        assert stale_job is not None and stale_job.status == "running"
        cancel_job = db_cancel.get(Job, job_id)
        assert cancel_job is not None
        assert cancel_api_job(db_cancel, cancel_job) is True

        finalize_api_job_success(db_worker, db_worker.get(ApiKey, key_id), stale_job, "supplier_search")

        db_worker.expire_all()
        assert db_worker.get(Job, job_id).status == "cancelled"
        assert db_worker.get(ApiKey, key_id).spent_supplier_search == 0
    finally:
        db_worker.close()
        db_cancel.close()


def test_stale_client_job_finalizer_cannot_charge_after_another_session_cancels():
    db_worker = SessionLocal()
    db_cancel = SessionLocal()
    try:
        client = Client(
            name="API cancellation race",
            telegram_id="api-cancel-race",
            is_active=True,
            money_balance_kopeks=100_000,
            money_reserved_kopeks=0,
        )
        key = _standalone_key()
        key.client = client
        db_worker.add_all([client, key])
        db_worker.commit()

        job, _ = start_api_job_with_reservation(db_worker, key, "supplier_search", "client race")
        assert job is not None
        job_id, key_id, client_id = job.id, key.id, client.id
        stale_job = db_worker.get(Job, job_id)
        assert stale_job.status == "running"

        assert cancel_api_job(db_cancel, db_cancel.get(Job, job_id)) is True
        finalize_api_job_success(db_worker, db_worker.get(ApiKey, key_id), stale_job, "supplier_search")

        db_worker.expire_all()
        settled_client = db_worker.get(Client, client_id)
        settled_key = db_worker.get(ApiKey, key_id)
        assert db_worker.get(Job, job_id).status == "cancelled"
        assert settled_client.money_reserved_kopeks == 0
        assert settled_client.money_balance_kopeks == 100_000
        assert settled_key.spent_supplier_search == 0
    finally:
        db_worker.close()
        db_cancel.close()


def test_repeated_standalone_finalizer_consumes_reserved_quota_only_once():
    db = SessionLocal()
    try:
        key = _standalone_key(quota=1)
        db.add(key)
        db.commit()
        job, _ = start_api_job_with_reservation(db, key, "supplier_search", "only once")

        finalize_api_job_success(db, key, job, "supplier_search")
        finalize_api_job_success(db, key, job, "supplier_search")

        db.refresh(key)
        assert key.spent_supplier_search == 1
        assert key.reserved_supplier_search == 0
    finally:
        db.close()


def test_repeated_standalone_settlement_cannot_consume_another_calls_slot():
    from app.mcp_api import release_api_job_reservation

    with SessionLocal() as db:
        key = _standalone_key(quota=2)
        db.add(key); db.commit()
        first, _ = start_api_job_with_reservation(db, key, "supplier_search", "First")
        second, _ = start_api_job_with_reservation(db, key, "supplier_search", "Second")
        finalize_api_job_success(db, key, first, "supplier_search")
        finalize_api_job_success(db, key, first, "supplier_search")
        release_api_job_reservation(db, key, first, "supplier_search", error="late failure")
        db.refresh(key)
        assert key.spent_supplier_search == 1
        assert key.reserved_supplier_search == 1
        finalize_api_job_success(db, key, second, "supplier_search")
        db.refresh(key)
        assert key.spent_supplier_search == 2
        assert key.reserved_supplier_search == 0


def test_persisted_rate_limit_sets_retry_headers_and_survives_memory_reset():
    from app.mcp_api import _RATE_LIMIT_STORE

    client = TestClient(app)
    db = SessionLocal()
    try:
        raw, key_hash, key_prefix = generate_api_key()
        key = ApiKey(key_hash=key_hash, key_prefix=key_prefix, rate_limit_per_minute=1)
        db.add(key)
        db.commit()
        headers = {"Authorization": f"Bearer {raw}"}

        first = client.get("/api/v1/mcp/balance", headers=headers)
        assert first.status_code == 200
        assert first.headers["X-RateLimit-Limit"] == "1"
        _RATE_LIMIT_STORE.clear()
        second = client.get("/api/v1/mcp/balance", headers=headers)
        assert second.status_code == 429
        assert second.headers.get("Retry-After")
        assert second.headers["X-RateLimit-Remaining"] == "0"
    finally:
        db.close()


def test_procurement_idempotency_operation_is_queryable_without_market_result_cache():
    db = SessionLocal()
    try:
        raw, key_hash, key_prefix = generate_api_key()
        key = ApiKey(key_hash=key_hash, key_prefix=key_prefix)
        db.add(key)
        db.commit()
        operation = claim_api_operation(
            db,
            key,
            "procurement_report",
            "procurement-retry-1",
            {"document_text": "Тестовый контракт"},
        )
        assert operation is not None
        complete_api_operation(db, operation, status_value="completed")

        client = TestClient(app)
        response = client.get(
            f"/api/v1/mcp/operations/{operation.id}",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "operation_id": operation.id,
            "service": "procurement_report",
            "status": "completed",
            "job_id": None,
            "job_ids": [],
            "job_status": None,
        }
    finally:
        db.close()


def test_geo_preflight_rejection_does_not_claim_idempotency_key(monkeypatch):
    db = SessionLocal()
    try:
        raw, key_hash, key_prefix = generate_api_key(is_admin=True)
        key = ApiKey(key_hash=key_hash, key_prefix=key_prefix, is_admin=True)
        db.add(key)
        db.commit()
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {raw}", "Idempotency-Key": "geo-preflight"}

        invalid = client.post(
            "/api/v1/mcp/suppliers/search",
            headers=headers,
            json={"specification": "Кабель", "geo_radius_km": 100},
        )
        assert invalid.status_code == 400
        assert db.query(ApiOperation).filter(ApiOperation.api_key_id == key.id).count() == 0

        monkeypatch.setattr("app.mcp_api.extract_supplier_search_context", AsyncMock(return_value="Кабель"))
        monkeypatch.setattr("app.mcp_api.discover_suppliers", AsyncMock(return_value=([], {"subject": "Кабель"})))
        corrected = client.post(
            "/api/v1/mcp/suppliers/search",
            headers=headers,
            json={"specification": "Кабель", "city": "Казань", "geo_radius_km": 100},
        )
        assert corrected.status_code == 200
        assert db.query(ApiOperation).filter(ApiOperation.api_key_id == key.id).count() == 1
    finally:
        db.close()


def test_insufficient_funds_does_not_orphan_idempotency_claim_and_retry_is_allowed(monkeypatch):
    db = SessionLocal()
    try:
        client_account = Client(
            name="API top up",
            telegram_id="api-top-up",
            is_active=True,
            money_balance_kopeks=0,
            money_reserved_kopeks=0,
        )
        raw, key_hash, key_prefix = generate_api_key()
        key = ApiKey(key_hash=key_hash, key_prefix=key_prefix, client=client_account)
        db.add_all([client_account, key])
        db.flush()
        db.add(ClientTariffOverride(client_id=client_account.id, kind="supplier_search", price_kopeks=1_000, is_enabled=True))
        db.commit()
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {raw}", "Idempotency-Key": "top-up-retry"}
        payload = {"specification": "Промышленный клапан"}

        denied = client.post("/api/v1/mcp/suppliers/search", headers=headers, json=payload)
        assert denied.status_code == 402
        assert db.query(ApiOperation).filter(ApiOperation.api_key_id == key.id).count() == 0

        client_account.money_balance_kopeks = 5_000
        db.commit()
        monkeypatch.setattr("app.mcp_api.extract_supplier_search_context", AsyncMock(return_value="Промышленный клапан"))
        monkeypatch.setattr("app.mcp_api.discover_suppliers", AsyncMock(return_value=([], {"subject": "Клапан"})))
        retried = client.post("/api/v1/mcp/suppliers/search", headers=headers, json=payload)
        assert retried.status_code == 200
        assert db.query(ApiOperation).filter(ApiOperation.api_key_id == key.id).count() == 1
    finally:
        db.close()


def test_api_remaining_runs_uses_geo_surcharged_price_not_base_price():
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).first()
        settings.geo_radius_surcharge_pct = 30.0
        client = Client(
            name="Geo API",
            telegram_id="api-geo-remaining",
            is_active=True,
            allowed_geo_radius=True,
            money_balance_kopeks=10_000,
            money_reserved_kopeks=0,
        )
        raw, key_hash, key_prefix = generate_api_key()
        key = ApiKey(key_hash=key_hash, key_prefix=key_prefix, client=client)
        db.add_all([client, key])
        db.flush()
        db.add(ClientTariffOverride(client_id=client.id, kind="supplier_search", price_kopeks=1_000, is_enabled=True))
        db.commit()

        _job, remaining = start_api_job_with_reservation(
            db,
            key,
            "supplier_search",
            "Geo price",
            delivery_city="Казань",
            geo_radius_km=100,
        )
        # 100 ₽ base + 30% geo = 130 ₽; after the first reserve, 87 ₽ remains.
        assert remaining == 6
    finally:
        db.close()


def test_master_key_read_is_metadata_only_and_explicit_post_reveals_new_secret_once():
    from app.security import _admin_token

    client = TestClient(app)
    headers = {"X-Admin-Token": _admin_token()}
    read = client.get("/api/admin/api-keys/master", headers=headers)
    assert read.status_code == 200
    assert read.json().get("raw_api_key") is None

    created = client.post("/api/admin/api-keys/master", headers=headers)
    assert created.status_code == 200
    raw_key = created.json()["raw_api_key"]
    assert raw_key.startswith("tl_admin_")

    reread = client.get("/api/admin/api-keys/master", headers=headers)
    assert reread.status_code == 200
    assert reread.json().get("raw_api_key") is None


def test_supplier_api_preserves_explicit_delivery_radius_in_request_contract():
    request = McpSupplierSearchRequest(
        specification="Кабель силовой",
        delivery_city="Казань",
        radius_km=300,
    )
    assert request.city == "Казань"
    assert request.geo_radius_km == 300


def test_new_standalone_admin_key_has_bounded_defaults_and_expiry():
    from app.mcp_api import AdminCreateApiKeyRequest, create_api_key
    from app.models import now_utc

    with SessionLocal() as db:
        response = create_api_key(AdminCreateApiKeyRequest(name="Limited test key"), db=db)
        key = db.get(ApiKey, response.item.id)
        assert key.quota_supplier_search == 20
        assert key.quota_exact_product == 10
        assert key.quota_procurement_report == 10
        assert key.expires_at is not None
        expiry = key.expires_at.replace(tzinfo=now_utc().tzinfo)
        assert 29 <= (expiry - now_utc()).days <= 30
        assert not key.secret_token


def test_admin_key_payload_rejects_negative_or_unbounded_limits():
    from app.mcp_api import AdminCreateApiKeyRequest, AdminUpdateApiKeyRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AdminCreateApiKeyRequest(name="Invalid", quota_supplier_search=999999)
    with pytest.raises(ValidationError):
        AdminUpdateApiKeyRequest(quota_exact_product=-1)
    with pytest.raises(ValidationError):
        AdminUpdateApiKeyRequest(rate_limit_per_minute=0)


def test_report_download_signature_is_bound_to_key_and_expiry():
    signature = build_report_download_signature("report.docx", "key-a", 2_000_000_000)
    assert verify_report_download_signature("report.docx", "key-a", 2_000_000_000, signature, now=1_999_999_999)
    assert not verify_report_download_signature("report.docx", "key-b", 2_000_000_000, signature, now=1_999_999_999)
    assert not verify_report_download_signature("report.docx", "key-a", 2_000_000_000, signature, now=2_000_000_001)


def test_signed_download_works_without_header_and_revocation_invalidates_it(tmp_path, monkeypatch):
    from app.config import config

    db = SessionLocal()
    previous_storage = config.storage_dir
    try:
        raw, key_hash, key_prefix = generate_api_key()
        key = ApiKey(key_hash=key_hash, key_prefix=key_prefix)
        db.add(key)
        db.commit()
        report_dir = tmp_path / "mcp_reports"
        report_dir.mkdir()
        report_name = "report.docx"
        (report_dir / report_name).write_bytes(b"report")
        monkeypatch.setattr(config, "storage_dir", str(tmp_path))
        expires = 2_000_000_000
        signature = build_report_download_signature(report_name, key_hash, expires)
        client = TestClient(app)

        response = client.get(f"/api/v1/mcp/downloads/{report_name}?expires={expires}&key_id={key.id}&signature={signature}")
        assert response.status_code == 200
        assert response.content == b"report"

        from datetime import timedelta
        from app.models import now_utc
        key.expires_at = now_utc() - timedelta(seconds=1)
        db.commit()
        expired = client.get(f"/api/v1/mcp/downloads/{report_name}?expires={expires}&key_id={key.id}&signature={signature}")
        assert expired.status_code == 403
        key.expires_at = None
        key.is_active = False
        db.commit()
        denied = client.get(f"/api/v1/mcp/downloads/{report_name}?expires={expires}&key_id={key.id}&signature={signature}")
        assert denied.status_code == 403
    finally:
        config.storage_dir = previous_storage
        db.close()
