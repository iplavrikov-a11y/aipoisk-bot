from __future__ import annotations

import asyncio
import importlib.util
import os
import stat
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.exact_product import yandex_search as ys
from app.supplier_search import (
    Candidate,
    MinpromRegistryContext,
    MinpromRegistryRequirement,
    _accepted_supplier_results,
    _enrich_accepted_suppliers_with_dadata,
    _enrich_unmatched_registry_suppliers,
)


def test_shared_yandex_lock_path_matches_emailagent_and_has_shared_perms(tmp_path):
    fid = "b1g-test-folder-12345"
    tl_async = ys._shared_yandex_lock_path("async", fid)
    tl_sync = ys._shared_yandex_lock_path("sync", fid)
    assert tl_async != tl_sync
    assert "yandex_cloud_async_rps_" in tl_async
    assert "yandex_cloud_sync_rps_" in tl_sync

    # Verify identical lock path formula in EmailAgent if present on this host
    ea_service = Path("/root/projects/emailagent/backend/services/supplier_discovery/service.py")
    if ea_service.is_file():
        text = ea_service.read_text(encoding="utf-8")
        assert 'f"yandex_cloud_{kind}_rps_{digest}.lock"' in text
        assert "os.fchmod(fd, 0o666)" in text

    # Verify actual reservation creates file with world-rw permissions (0o666)
    test_fid = f"unit-test-lock-{os.getpid()}"
    lock_path = ys._shared_yandex_lock_path("async", test_fid)
    try:
        ys._LAST_ASYNC_SUBMIT_TS = 0.0
        w1 = ys._reserve_cross_process_slot(0.05, folder_id=test_fid)
        w2 = ys._reserve_cross_process_slot(0.05, folder_id=test_fid)
        assert w1 >= 0.0
        assert w2 > 0.0
        mode = stat.S_IMODE(os.stat(lock_path).st_mode)
        assert mode & 0o666 == 0o666
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass


def test_yandex_rps_defaults_and_env_overrides(monkeypatch):
    monkeypatch.delenv("AIPOISK_YANDEX_ASYNC_RPS", raising=False)
    monkeypatch.delenv("AIPOISK_YANDEX_SYNC_RPS", raising=False)
    assert ys._yandex_async_min_interval() == pytest.approx(0.10, rel=1e-3)
    assert ys._yandex_sync_min_interval() == pytest.approx(1.0 / 3.5, rel=1e-3)

    monkeypatch.setenv("AIPOISK_YANDEX_ASYNC_RPS", "12")
    monkeypatch.setenv("AIPOISK_YANDEX_SYNC_RPS", "8")
    assert ys._yandex_async_min_interval() == pytest.approx(1.0 / 12.0, rel=1e-3)
    assert ys._yandex_sync_min_interval() == pytest.approx(1.0 / 8.0, rel=1e-3)


def test_progressive_429_cooldown_sequence_and_reset():
    ys.record_yandex_async_success()
    assert ys.is_yandex_async_available() is True

    c1 = ys.record_yandex_async_429_progressive()
    c2 = ys.record_yandex_async_429_progressive()
    c3 = ys.record_yandex_async_429_progressive()
    c4 = ys.record_yandex_async_429_progressive()
    assert (c1, c2, c3, c4) == (30.0, 60.0, 120.0, 120.0)
    assert ys.is_yandex_async_available() is False

    ys.record_yandex_async_success()
    assert ys.is_yandex_async_available() is True
    assert ys.record_yandex_async_429_progressive() == 30.0
    ys.record_yandex_async_success()


def test_geo_radius_strict_local_filtering_and_nearest_fallback():
    # Case 1: Strong local pool (>= 15 within 300 km of Казань) -> strictly local only
    reviewed_strong = []
    for i in range(16):
        reviewed_strong.append(
            {
                "company_name": f"ООО Казанский Завод {i}",
                "site": f"https://kazan-plant-{i}.ru",
                "phone": f"+7 843 200-00-{i:02d}",
                "email": f"sales@kazan-plant-{i}.ru",
                "supplier_city": "Казань",
                "evidence_status": "verified",
                "quality_score": 82,
                "product_fit": "exact",
            }
        )
    for i in range(10):
        reviewed_strong.append(
            {
                "company_name": f"ООО Московский Трейдер {i}",
                "site": f"https://msk-trader-{i}.ru",
                "phone": f"+7 495 300-00-{i:02d}",
                "email": f"sales@msk-trader-{i}.ru",
                "supplier_city": "Москва",
                "evidence_status": "verified",
                "quality_score": 96,
                "product_fit": "exact",
            }
        )

    accepted_strong = _accepted_supplier_results(
        reviewed_strong,
        target=25,
        delivery_city="Казань",
        geo_radius_km=300,
        limit_to_target=True,
    )
    assert len(accepted_strong) == 16
    assert all(r.get("supplier_distance_within_radius") is True for r in accepted_strong)
    assert all(r.get("supplier_city") == "Казань" for r in accepted_strong)

    # Also must drop out-of-radius noise when limit_to_target=False (final discover_suppliers pass)
    accepted_strong_unlimited = _accepted_supplier_results(
        reviewed_strong,
        target=15,
        delivery_city="Казань",
        geo_radius_km=300,
        limit_to_target=False,
    )
    assert len(accepted_strong_unlimited) == 16
    assert all(r.get("supplier_distance_within_radius") is True for r in accepted_strong_unlimited)
    assert all(r.get("supplier_city") == "Казань" for r in accepted_strong_unlimited)

    # Case 1b: Delivery city itself (0 km) must sort strictly BEFORE nearby cities (e.g. Набережные Челны ~237 km)
    mixed_local = [
        {
            "company_name": "ООО Челны ЖБИ",
            "site": "https://chelny-gbi.ru",
            "phone": "+7 8552 11-11-11",
            "email": "info@chelny-gbi.ru",
            "supplier_city": "Набережные Челны",
            "evidence_status": "verified",
            "quality_score": 95,
            "product_fit": "exact",
        },
        {
            "company_name": "ООО Казань ЖБИ",
            "site": "https://kazan-gbi.ru",
            "phone": "+7 843 111-11-11",
            "email": "info@kazan-gbi.ru",
            "supplier_city": "Казань",
            "evidence_status": "verified",
            "quality_score": 85,
            "product_fit": "exact",
        },
    ]
    accepted_order = _accepted_supplier_results(
        mixed_local,
        target=5,
        delivery_city="Казань",
        geo_radius_km=300,
        limit_to_target=False,
    )
    assert [r["supplier_city"] for r in accepted_order] == ["Казань", "Набережные Челны"]
    assert accepted_order[0]["supplier_distance_km"] == 0

    # Case 2: Sparse local pool (2 in-radius) -> keep all local first, then nearest cities by distance
    reviewed_sparse = [
        {
            "company_name": "ООО Казань Локал",
            "site": "https://kzn-local.ru",
            "phone": "+7 843 211-11-11",
            "email": "info@kzn-local.ru",
            "supplier_city": "Казань",
            "evidence_status": "verified",
            "quality_score": 80,
            "product_fit": "exact",
        },
        {
            "company_name": "ООО Владивосток Дальный",
            "site": "https://vl-far.ru",
            "phone": "+7 423 222-22-22",
            "email": "info@vl-far.ru",
            "supplier_city": "Владивосток",
            "evidence_status": "verified",
            "quality_score": 99,
            "product_fit": "exact",
        },
        {
            "company_name": "ООО Нижний Новгород Ближе",
            "site": "https://nn-near.ru",
            "phone": "+7 831 233-33-33",
            "email": "info@nn-near.ru",
            "supplier_city": "Нижний Новгород",
            "evidence_status": "verified",
            "quality_score": 85,
            "product_fit": "exact",
        },
    ]
    accepted_sparse = _accepted_supplier_results(
        reviewed_sparse,
        target=5,
        delivery_city="Казань",
        geo_radius_km=150,
        limit_to_target=True,
    )
    assert [r["supplier_city"] for r in accepted_sparse] == ["Казань", "Нижний Новгород", "Владивосток"]


def test_gisp_enrichment_uses_soft_fallback_query_without_inn():
    queries_seen: list[str] = []

    async def fake_yandex(settings, queries, **kwargs):
        q = queries[0]
        queries_seen.append(q)
        # Strict query with INN returns nothing; fallback without INN returns real site
        if "7810000001" in q:
            return [], 1
        return [
            Candidate(
                url="https://npo-process-test.ru",
                domain="npo-process-test.ru",
                title="НПО Процесс",
                snippet="Официальный сайт",
                source="yandex",
                query=q,
            )
        ], 1

    async def fake_collect_pages(url):
        return [
            {
                "url": url,
                "text": "ООО НПО Процесс. Контакты: +7 (812) 555-44-33, sales@npo-process-test.ru",
            }
        ]

    class DummySettings:
        yandex_search_folder_id = "folder-test"
        yandex_search_api_key = "key-test"
        google_search_api_key = ""
        google_search_cse_id = ""

    reg_ctx = MinpromRegistryContext(
        requirement=MinpromRegistryRequirement(required=True, measure_type="restriction", evidence="", reason=""),
        status="ok",
        entries=[
            {
                "inn": "7810000001",
                "manufacturer": 'ООО "НПО "ПРОЦЕСС"',
                "product": "Линия химического никелирования",
                "registry_number": "10346262",
            }
        ],
    )

    with (
        patch("app.supplier_search.enrich_company_by_inn", new=AsyncMock(return_value={"city": "Санкт-Петербург", "region": "Санкт-Петербург"})),
        patch("app.supplier_search._search_with_yandex", new=fake_yandex),
        patch("app.supplier_search.collect_pages", new=fake_collect_pages),
    ):
        result = asyncio.run(_enrich_unmatched_registry_suppliers(DummySettings(), [], reg_ctx))

    assert len(queries_seen) == 2
    assert "7810000001" in queries_seen[0]
    assert "7810000001" not in queries_seen[1]
    assert len(result) == 1
    assert result[0]["evidence_status"] == "verified"
    assert result[0]["site"] == "https://npo-process-test.ru"
    assert result[0]["email"] == "sales@npo-process-test.ru"
    assert "+7" in result[0]["phone"]


def test_parallel_dadata_enrichment_deduplicates_inns():
    calls: list[str] = []

    async def fake_dadata(inn: str):
        calls.append(inn)
        await asyncio.sleep(0.01)
        return {
            "region": "Республика Татарстан",
            "city": "Казань",
            "management_name": f"Директор {inn}",
        }

    accepted = [
        {"company_name": "A1", "inn": "1655000001", "region": "", "supplier_city": "", "contact_person": ""},
        {"company_name": "A2", "inn": "1655000001", "region": "", "supplier_city": "", "contact_person": ""},
        {"company_name": "B1", "inn": "7707000002", "region": "", "supplier_city": "", "contact_person": ""},
    ]

    with patch("app.supplier_search.enrich_company_by_inn", new=fake_dadata):
        asyncio.run(_enrich_accepted_suppliers_with_dadata(accepted))

    assert sorted(calls) == ["1655000001", "7707000002"]
    assert all(r["supplier_city"] == "Казань" for r in accepted)
    assert accepted[0]["contact_person"] == "Директор 1655000001"
    assert accepted[1]["contact_person"] == "Директор 1655000001"


def test_claim_yandex_async_attempt_single_probe_daytime_and_parallel_night(monkeypatch):
    # Reset circuit breaker state
    ys._ASYNC_RATE_LIMITED_UNTIL = 0.0
    ys._ASYNC_PROVEN_UNTIL = 0.0
    ys._ASYNC_CONSECUTIVE_429 = 0

    # Outside 00:00-06:00 MSK when not recently proven -> only ONE caller claims probe slot
    monkeypatch.setattr(ys, "_is_msk_deferred_window", lambda now_ts=None: False)
    assert ys.claim_yandex_async_attempt() is True
    assert ys.claim_yandex_async_attempt() is False

    # Once async succeeds, all concurrent callers can run async within proven window
    ys.record_yandex_async_success()
    assert ys.claim_yandex_async_attempt() is True
    assert ys.claim_yandex_async_attempt() is True

    # Inside 00:00-06:00 MSK -> parallel allowed without proven gate
    ys._ASYNC_PROVEN_UNTIL = 0.0
    monkeypatch.setattr(ys, "_is_msk_deferred_window", lambda now_ts=None: True)
    assert ys.claim_yandex_async_attempt() is True
    assert ys.claim_yandex_async_attempt() is True

    # Cleanup
    ys.record_yandex_async_success()


def test_extract_yandex_job_metrics_prices_sync_fallback_accurately():
    from app.jobs import extract_yandex_job_metrics

    evidence = {
        "search": {
            "yandex_requests_count": 10,
            "yandex_async_requests": 2,
            "yandex_sync_requests": 8,
        }
    }
    reqs, cost = extract_yandex_job_metrics(evidence, price_per_request=0.0305)
    assert reqs == 10
    assert cost == pytest.approx(round(2 * 0.0305 + 8 * 0.488, 2))
