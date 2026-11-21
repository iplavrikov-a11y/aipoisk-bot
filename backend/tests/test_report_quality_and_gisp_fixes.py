from __future__ import annotations

import ssl
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.jobs import _set_customer_job_title_from_subject, _strip_job_mode_prefixes, create_job
from app.main import admin_rerun_job
from app.models import Base, Client, Job, SystemSettings
from app.report_builder import _format_supplier_location, _supplier_registry_note
import app.supplier_search as supplier_search
from app.supplier_search import (
    Candidate,
    MinpromRegistryContext,
    MinpromRegistryRequirement,
    PHONE_RE,
    ProcurementItem,
    ProcurementProfile,
    _accepted_supplier_results,
    _diversify_candidates_by_query,
    _enrich_unmatched_registry_suppliers,
    _interleave_candidates_by_item,
    _normalize_ru_phone,
    _review_candidates_until_target,
    fetch_page,
)


def test_phone_extraction_blocks_chinese_86_and_bank_account_numbers() -> None:
    sample_text = (
        "Тел.: +7 (495) 772-93-89, горячая линия 8 (800) 201-22-09. "
        "Р/с 40702810100000001234, к/с 30101810200000000593, ОГРН 1026406900217. "
        "China factory WhatsApp: +86 186 6170 5899, +86 153 1524 0100."
    )
    found = PHONE_RE.findall(sample_text)
    normalized = [_normalize_ru_phone(p) for p in found]
    assert "+7 (495) 772-93-89" in normalized
    assert "+7 (800) 201-22-09" in normalized
    assert all(not p.startswith("+7 (61") for p in normalized if p)
    assert all("000-00-00" not in p for p in normalized if p)

    # Direct normalization checks for invalid codes/placeholders
    assert _normalize_ru_phone("+7 (101) 000-00-00") == ""
    assert _normalize_ru_phone("+7 (102) 000-00-00") == ""
    assert _normalize_ru_phone("+7 (069) 002-17-63") == ""
    assert _normalize_ru_phone("+70000001000") == ""
    assert _normalize_ru_phone("+86 186 6170 5899") == ""
    assert _normalize_ru_phone("+7 (618) 661-70-58") == ""


def test_accepted_supplier_results_deduplicates_storefront_clones_and_blocks_foreign_in_ru_scope() -> None:
    reviewed = [
        {
            "company_name": "weller-shop.ru",
            "site": "https://weller-shop.ru/about",
            "phone": "+7 (499) 404-26-34",
            "email": "shop@weller-shop.ru",
            "evidence_status": "verified",
            "product_fit": "category",
            "supplier_country": "Россия 🇷🇺",
            "quality_score": 80,
        },
        {
            "company_name": "jbc-shop.ru",
            "site": "https://jbc-shop.ru/",
            "phone": "+7 (499) 404-26-34",
            "email": "shop@jbc-shop.ru",
            "evidence_status": "verified",
            "product_fit": "profile",
            "supplier_country": "Россия 🇷🇺",
            "quality_score": 76,
        },
        {
            "company_name": "Феррум",
            "site": "https://ferrum.ru/catalog",
            "phone": "+7 (496) 633-24-56",
            "email": "info@ferrum.ru",
            "evidence_status": "verified",
            "product_fit": "exact",
            "supplier_country": "Россия 🇷🇺",
            "quality_score": 92,
        },
        {
            "company_name": "ООО «Феррум» (ООО «Ferrum»)",
            "site": "https://ferrum-eu.com/shop/group_628/",
            "phone": "+7 (496) 633-24-56",
            "email": "",
            "evidence_status": "verified",
            "product_fit": "category",
            "supplier_country": "Россия 🇷🇺",
            "quality_score": 78,
        },
        {
            "company_name": "Qingzhou Keda Environment Protection Machinery Co., Ltd.",
            "site": "https://www.kedadredger.com/ru/",
            "phone": "",
            "email": "sales@kedadredger.com",
            "evidence_status": "verified",
            "product_fit": "category",
            "supplier_country": "Китай 🇨🇳",
            "quality_score": 82,
        },
    ]

    accepted_ru = _accepted_supplier_results(reviewed, target=10, geo_scope="ru")
    domains_ru = [supplier_search.base_domain(r["site"]) for r in accepted_ru]
    assert len(accepted_ru) == 2
    assert "ferrum.ru" in domains_ru
    assert "ferrum-eu.com" not in domains_ru
    assert "weller-shop.ru" in domains_ru
    assert "jbc-shop.ru" not in domains_ru
    assert "kedadredger.com" not in domains_ru

    accepted_world = _accepted_supplier_results(reviewed, target=10, geo_scope="world")
    domains_world = [supplier_search.base_domain(r["site"]) for r in accepted_world]
    assert "kedadredger.com" in domains_world


@pytest.mark.asyncio
async def test_gisp_enrichment_searches_beyond_six_blocks_directories_and_sets_city_and_item() -> None:
    settings = SystemSettings(yandex_search_folder_id="folder", yandex_search_api_key="key")
    entries = [
        {
            "manufacturer": f'ООО "ЗАВОД №{idx}"',
            "product": f"Тележка инструментальная ТИ-{idx}",
            "inn": f"77010000{idx:02d}",
            "registry_number": f"106000{idx:02d}",
            "procurement_item_id": f"item-{(idx % 3) + 1}",
            "procurement_item": f"Позиция {(idx % 3) + 1}",
        }
        for idx in range(1, 11)
    ]
    ctx = MinpromRegistryContext(
        requirement=MinpromRegistryRequirement(required=True, measure_type="restriction", evidence="test", reason="test"),
        status="ok",
        entries=tuple(entries),
    )

    async def fake_dadata(inn: str) -> dict:
        return {
            "inn": inn,
            "company_name": f'ООО "ЗАВОД {inn[-2:]}"',
            "region": "г Санкт-Петербург",
            "city": "г Санкт-Петербург",
            "legal_address": "190000, г Санкт-Петербург, пр. Стачек, 1",
            "management_name": "Иванов И.И.",
            "phones": [],
            "emails": [],
            "sites": [],
        }

    async def fake_yandex(_settings, queries, **_kwargs):
        q = queries[0]
        # Return blocked directory elec.ru first, then real factory domain
        num = q.split('"')[1].split()[-1]
        return [
            Candidate(url=f"https://www.elec.ru/org/{num}/", domain="elec.ru", title="Elec Directory"),
            Candidate(url="https://icatalog.expocentr.ru/ru/exhibitors/1", domain="expocentr.ru", title="Expocentr"),
            Candidate(url="https://tatmontazh.sberb2b.ru/catalog", domain="sberb2b.ru", title="SberB2B"),
            Candidate(url="https://xn--b1aedfedwrdfl5a6k.xn--p1ai/producer/test", domain="xn--b1aedfedwrdfl5a6k.xn--p1ai", title="Catalog"),
            Candidate(url=f"https://zavod-{num}.ru/contacts", domain=f"zavod-{num}.ru", title=f"Завод {num}"),
        ], 1

    async def fake_collect_pages(url: str) -> list[dict]:
        assert "elec.ru" not in url
        num = url.split("zavod-")[1].split(".")[0]
        return [{
            "url": url,
            "html": "<p>Контакты</p>",
            "text": f"Отдел продаж завода {num}: +7 (812) 335-37-{int(num):02d}, sales@zavod-{num}.ru",
        }]

    with (
        patch.object(supplier_search, "enrich_company_by_inn", side_effect=fake_dadata),
        patch.object(supplier_search, "_search_with_yandex", side_effect=fake_yandex),
        patch.object(supplier_search, "collect_pages", side_effect=fake_collect_pages),
    ):
        enriched = await _enrich_unmatched_registry_suppliers(settings, [], ctx, limit=15)

    assert len(enriched) == 10
    # Every single one of the 10 entries (including #7..#10!) got its real site, phone, email, city, and item_id
    for idx, row in enumerate(enriched, start=1):
        assert row["site"].startswith("https://zavod-")
        assert row["phone"].startswith("+7 (812) 335-37-")
        assert row["email"].startswith("sales@zavod-")
        assert row["supplier_city"].lower() == "санкт-петербург"
        assert row["procurement_item_id"] == f"item-{(idx % 3) + 1}"
        assert _format_supplier_location(row).lower() == "санкт-петербург"


@pytest.mark.asyncio
async def test_balanced_multi_item_review_does_not_early_stop_before_uncovered_items() -> None:
    profile = ProcurementProfile(
        summary="Производственная мебель",
        items=(
            ProcurementItem(id="item-1", name="Тележки ЧПУ"),
            ProcurementItem(id="item-9", name="Перегородки металлические"),
        ),
    )
    # 40 candidates for item-1 followed by 3 candidates for item-9 at the tail
    candidates = [
        Candidate(url=f"https://cart-{i}.ru", domain=f"cart-{i}.ru", query="тележки", procurement_item_id="item-1")
        for i in range(40)
    ] + [
        Candidate(url=f"https://part-{i}.ru", domain=f"part-{i}.ru", query="перегородки", procurement_item_id="item-9")
        for i in range(3)
    ]

    # Query diversification & item interleaving bring item-9 forward
    diversified = _diversify_candidates_by_query(candidates, 10)
    assert any(c.procurement_item_id == "item-9" for c in diversified[:4])
    interleaved = _interleave_candidates_by_item(candidates, profile)
    assert interleaved[1].procurement_item_id == "item-9"

    # Even if un-interleaved candidates are passed to _review_candidates_until_target,
    # early_stop must NOT abandon item-9 candidates at the tail after item-1 exceeds target=10!
    async def fake_verify(_settings, cand: Candidate, _context: str, **_kwargs):
        return {
            "company_name": f"Компания {cand.domain}",
            "site": cand.url,
            "phone": "+7 (495) 123-45-67",
            "email": f"info@{cand.domain}",
            "evidence_status": "verified",
            "product_fit": "exact",
            "procurement_item_id": cand.procurement_item_id,
            "procurement_item": "Тележки ЧПУ" if cand.procurement_item_id == "item-1" else "Перегородки металлические",
            "quality_score": 88,
        }

    with patch.object(supplier_search, "_verify_candidate_with_limits", side_effect=fake_verify):
        accepted, _reviewed, _meta = await _review_candidates_until_target(
            SystemSettings(),
            candidates,  # raw un-interleaved order: item-9 is at indices 40..42!
            "ТЗ",
            target=10,
            profile=profile,
            multi_item_mode="balanced",
        )

    item9_accepted = [r for r in accepted if r.get("procurement_item_id") == "item-9"]
    assert len(item9_accepted) == 3


def test_admin_rerun_direct_call_preserves_minprom_policy_and_strips_prefixes() -> None:
    with TemporaryDirectory() as tmp:
        engine = create_engine(f"sqlite:///{Path(tmp) / 'test.db'}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            client = Client(name="Marina", telegram_id="marina_tg", supplier_target_min=70)
            db.add(client)
            db.flush()
            with patch("app.jobs.minprom_registry_preflight_error", return_value=""):
                parent = create_job(
                    db,
                    client_id=client.id,
                    mode="supplier_search",
                    title="ТЗ: Вагон-дом передвижной",
                    target_suppliers=70,
                    files=[],
                    supplier_search_policy="minprom_registry_priority",
                    multi_item_mode="balanced",
                )
            parent.status = "completed"
            db.commit()

            with (
                patch("app.main.job_dir", side_effect=lambda jid: Path(tmp) / jid),
                patch("app.main.enqueue_job"),
            ):
                # Direct Python call leaves policy=Query(None) and multi_item_mode=Query(None)
                resp = admin_rerun_job(parent.id, reparse=True, db=db)

            rerun_id = resp["job"]["id"]
            rerun_job = db.get(Job, rerun_id)
            assert rerun_job is not None
            assert rerun_job.supplier_search_policy == "minprom_registry_priority"
            assert rerun_job.multi_item_mode == "balanced"
        finally:
            db.close()

    assert _strip_job_mode_prefixes("[Админ] Подбор товаров: [Админ] Подбор товаров: Георешетка СД-30") == "Георешетка СД-30"
    exact_admin_job = Job(mode="exact_product", title="[Админ] Подбор товаров: technical assignment", is_admin_rerun=True)
    _set_customer_job_title_from_subject(exact_admin_job, "[Админ] Подбор товаров: Георешетка двуосная СД-30")
    assert exact_admin_job.title == "[Админ] Подбор товаров: Георешетка двуосная СД-30"


@pytest.mark.asyncio
async def test_fetch_page_retries_with_ssl_verify_false_on_expired_cert() -> None:
    html_body = "<html><body><h1>Завод металлоизделий</h1><p>" + ("Промышленная мебель тележки ЧПУ. " * 6) + "Тел: +7 (495) 222-33-44, info@zavod.ru</p></body></html>"

    class FakeCertErrorClient:
        headers = {"User-Agent": "test"}

        async def get(self, url: str, follow_redirects: bool = False):
            ssl_err = ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired")
            raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired") from ssl_err

    mock_resp = httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8"},
        text=html_body,
        request=httpx.Request("GET", "https://zavodzmi.example/contacts/"),
    )

    with (
        patch("app.ssrf_guard.async_validate_public_http_url", new=AsyncMock(return_value=None)),
        patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)),
    ):
        page = await fetch_page(FakeCertErrorClient(), "https://zavodzmi.example/contacts/")  # type: ignore[arg-type]

    assert page is not None
    assert "+7 (495) 222-33-44" in page["text"]
    assert "info@zavod.ru" in page["text"]

    # Also verify registry_only note displays INN clearly when contacts are absent
    note = _supplier_registry_note({
        "supplier_search_policy": "minprom_registry_priority",
        "minprom_registry_match": {"matched": True, "inn": "1650123456"},
        "phone": "",
        "email": "",
    })
    assert "1650123456" in note
