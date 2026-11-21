"""Regression tests for TenderLex exact_product and price_monitoring optimizations."""

from __future__ import annotations

import asyncio
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exact_product import deep as ep_deep
from app.exact_product import yandex_search as ys
from app.models import SystemSettings
from app.price_monitoring import extractor as pm_ext
from app.price_monitoring import pipeline as pm_pipe
from app.price_monitoring.models import ItemPriceResult, SupplierQuote


# ---------------------------------------------------------------------------
# 1. Yandex Search: B2B retailers flag, progressive 429 cooloff, sync fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_yandex_search_allow_b2b_retailers_toggle():
    engine = ys.YandexSearchEngine(api_key="test", folder_id="test")
    mock_results = [
        ys.YandexSearchResult(
            title="Товар на ВсеИнструменты",
            url="https://www.vseinstrumenti.ru/product/nasos-123/",
            snippet="Цена 5000 руб",
            domain="www.vseinstrumenti.ru",
        ),
        ys.YandexSearchResult(
            title="Товар на Ozon",
            url="https://www.ozon.ru/product/nasos-123/",
            snippet="Цена 4900 руб",
            domain="www.ozon.ru",
        ),
        ys.YandexSearchResult(
            title="Товар на Заводе",
            url="https://zavod-nasos.ru/catalog/item-1/",
            snippet="Цена 4800 руб",
            domain="zavod-nasos.ru",
        ),
    ]

    with patch.object(engine, "_search_v2", AsyncMock(return_value=mock_results)):
        strict = await engine.search("насос 123", max_results=10, allow_b2b_retailers=False)
        b2b = await engine.search("насос 123", max_results=10, allow_b2b_retailers=True)

    strict_domains = [r.domain for r in strict]
    b2b_domains = [r.domain for r in b2b]

    assert "zavod-nasos.ru" in strict_domains
    assert "www.vseinstrumenti.ru" not in strict_domains
    assert "www.ozon.ru" not in strict_domains

    assert "zavod-nasos.ru" in b2b_domains
    assert "www.vseinstrumenti.ru" in b2b_domains
    assert "www.ozon.ru" not in b2b_domains


@pytest.mark.asyncio
async def test_yandex_sync_fallback_active_and_retries_429(monkeypatch):
    monkeypatch.delenv("AIPOISK_ALLOW_YANDEX_SYNC_FALLBACK", raising=False)
    ys.record_yandex_async_success()

    engine = ys.YandexSearchEngine(api_key="key", folder_id="folder")
    xml_payload = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<yandexsearch><response><results><grouping><group><doc>"
        "<url>https://zavod-test.ru/item/1</url>"
        "<title>Насос ЦНС 180</title>"
        "<passages><passage>Цена 12000 руб</passage></passages>"
        "</doc></group></grouping></results></response></yandexsearch>"
    )
    raw_b64 = base64.b64encode(xml_payload.encode("utf-8")).decode("ascii")

    resp_429 = MagicMock(status_code=429, text="rate limited")
    resp_ok = MagicMock(status_code=200, text="ok")
    resp_ok.json.return_value = {"rawData": raw_b64}

    mock_client = MagicMock()
    # Async gets 429 (3 tries inside _paced_async_post_counted), then sync gets 429 once and 200 on retry
    mock_client.post = AsyncMock(side_effect=[resp_429, resp_429, resp_429, resp_429, resp_ok])

    recorded_cooloffs: list[float] = []
    orig_record = ys.record_yandex_async_failure_429

    def _spy_cooloff(cooloff_s: float = 180.0):
        recorded_cooloffs.append(cooloff_s)
        orig_record(cooloff_s)

    monkeypatch.setattr(ys, "record_yandex_async_failure_429", _spy_cooloff)
    monkeypatch.setattr(engine, "_get_client", AsyncMock(return_value=mock_client))

    results = await engine._search_v2("насос цнс 180", max_results=5, enrich_query=False)
    assert len(results) == 1
    assert results[0].domain == "zavod-test.ru"
    assert recorded_cooloffs == [30.0]
    assert engine.sync_requests >= 2
    ys.record_yandex_async_success()


# ---------------------------------------------------------------------------
# 2. Exact Product: Glued brands, analog dedup/filtering, URL verification
# ---------------------------------------------------------------------------


def test_sanitize_glued_brands_preserves_decimals_and_prefers_domestic():
    pos = {
        "identified_brand": "Wenzhou Trading Co., Ltd / РосЗавод",
        "identified_model": "ALT-200 / КР-12,5",
        "manufacturer": "Shenzhen Export Co., Ltd / АО РосЗавод",
        "alternative_brands": [],
    }
    ep_deep.sanitize_glued_brands_and_models(pos)
    assert pos["identified_brand"] == "РосЗавод"
    assert pos["identified_model"] == "КР-12,5"
    assert "РосЗавод" in pos["manufacturer"]
    assert any(a["model"] == "ALT-200" for a in pos["alternative_brands"])


def test_drop_nonconforming_analogs_dedups_translit_sku_mismatch_and_gauge():
    positions = [
        {
            "name_in_tz": "Игла инъекционная 21G",
            "identified_brand": "Armed",
            "identified_model": "ВА-431 21230DEK 21G",
            "manufacturer": "Armed",
            "specs_breakdown": [{"param_name": "Размер", "tz_requirement": "21G", "product_fact": "21G", "status": "match"}],
            "alternative_brands": [
                # Duplicate Cyrillic transliteration of primary brand
                {
                    "brand": "Армед",
                    "model": "ВА-431 21230DEK 21G",
                    "specs_breakdown": [{"param_name": "Размер", "status": "match"}],
                },
                # Different brand but identical/overlapping SKU
                {
                    "brand": "Гемопласт",
                    "model": "ВА-431 21230DEK",
                    "specs_breakdown": [{"param_name": "Размер", "status": "match"}],
                },
                # Has mismatch -> must be dropped
                {
                    "brand": "БрендМисматч",
                    "model": "М-500",
                    "specs_breakdown": [
                        {"param_name": "Размер", "status": "match"},
                        {"param_name": "Мощность", "status": "mismatch"},
                    ],
                },
                # Gauge conflict (24G vs 21G) -> must be dropped
                {
                    "brand": "МедЗавод",
                    "model": "Игла 24G",
                    "specs_breakdown": [{"param_name": "Размер", "tz_requirement": "21G", "product_fact": "24G", "status": "match"}],
                },
                # Valid clean analog -> must survive
                {
                    "brand": "Микрон",
                    "model": "КР-210 21G",
                    "specs_breakdown": [{"param_name": "Размер", "tz_requirement": "21G", "product_fact": "21G", "status": "match"}],
                },
            ],
        }
    ]
    ep_deep.drop_nonconforming_analogs(positions)
    surviving = positions[0]["alternative_brands"]
    assert len(surviving) == 1
    assert surviving[0]["brand"] == "Микрон"


@pytest.mark.asyncio
async def test_sanitize_and_verify_urls_rejects_soft_404_and_demotes_assembly_pdf(monkeypatch):
    positions = [
        {
            "identified_brand": "ЗаводТест",
            "identified_model": "Т-100",
            "source_url": "https://zavod-test.ru/docs/sborka_t100.pdf",
            "datasheet_url": "https://zavod-test.ru/dead-404/",
            "web_sources": [
                "https://zavod-test.ru/docs/sborka_t100.pdf",
                "https://zavod-test.ru/dead-404/",
                "https://zavod-test.ru/product/t-100/",
            ],
            "verified_documents": [
                {"url": "https://zavod-test.ru/product/t-100/", "domain": "zavod-test.ru", "title": "Т-100"},
            ],
            "alternative_brands": [],
        }
    ]

    async def fake_get(self, url, **kwargs):
        resp = MagicMock()
        resp.url = url
        if "dead-404" in url:
            resp.status_code = 200
            resp.headers = {"content-type": "text/html"}
            resp.text = "<html><head><title>404 Страница не найдена</title></head><body><h1>Ошибка 404</h1></body></html>"
        elif url.endswith(".pdf"):
            resp.status_code = 200
            resp.headers = {"content-type": "application/pdf"}
            resp.text = ""
        else:
            resp.status_code = 200
            resp.headers = {"content-type": "text/html"}
            resp.text = "<html><head><title>ЗаводТест Т-100</title></head><body>Характеристики Т-100</body></html>"
        return resp

    with patch("app.ssrf_guard.async_is_safe_public_http_url", AsyncMock(return_value=True)):
        with patch("httpx.AsyncClient.get", new=fake_get):
            await ep_deep.sanitize_and_verify_all_position_urls(positions, force_http=True)

    pos = positions[0]
    assert pos["source_url"] == "https://zavod-test.ru/product/t-100/"
    assert pos["datasheet_url"] == ""
    assert "https://zavod-test.ru/dead-404/" not in pos["web_sources"]


# ---------------------------------------------------------------------------
# 3. Price Monitoring: soft-404, catalog drilldown, dimensional conversion, batching
# ---------------------------------------------------------------------------


def test_price_monitoring_soft_404_and_catalog_drilldown():
    assert pm_ext.is_soft_404("<html><head><title>404 - Страница не найдена</title></head><body></body></html>") is True
    assert pm_ext.is_soft_404("<html><head><title>Насос КМ 80-65-160</title></head><body>Цена 45 000 руб</body></html>") is False

    catalog_html = """
    <html><body>
      <a href="/cart/">Корзина</a>
      <a href="/product/other-item/">Клапан обратный ДУ50</a>
      <a href="/goods/nasos-km-80-65-160/">Насос консольный КМ 80-65-160 11 кВт</a>
    </body></html>
    """
    card_url = pm_ext.find_exact_product_card_in_html(
        catalog_html,
        "https://pumpshop.ru/catalog/nasosy/",
        keywords=["насос", "80-65-160"],
    )
    assert card_url == "https://pumpshop.ru/goods/nasos-km-80-65-160/"


@pytest.mark.asyncio
async def test_price_monitoring_accepts_evidenced_dimensional_conversion_and_rejects_raw_pack():
    settings = SystemSettings()
    page_text = "Пленка пароизоляционная Изоспан B рулон 1.5х50 м (75 м2). Цена 3000 руб за рулон с НДС 20%."

    # Case A: AI provides evidenced dimensional conversion (3000 / 75 = 40 руб/м2)
    ai_converted = {
        "target_identifiers": ["Изоспан B"],
        "site_identifiers": ["Изоспан B"],
        "identifier_conflict": False,
        "category_conflict": False,
        "specification_conflict": False,
        "material_conflict": False,
        "is_relevant": True,
        "is_price_found": True,
        "company_name": "ООО СтройСнаб",
        "inn": "7701234567",
        "kpp": "",
        "contacts": "+7 495 111-22-33",
        "raw_price_rub": 3000.0,
        "site_unit": "рулон",
        "price_rub": 40.0,
        "unit": "м2",
        "conversion_comment": "Рулон 1.5х50 м = 75 м2; 3000 / 75 = 40 руб/м2",
    }
    with patch("app.price_monitoring.extractor.call_llm", AsyncMock(return_value=json.dumps(ai_converted))):
        quote_ok = await pm_ext.extract_supplier_quote(
            settings,
            "Пленка пароизоляционная Изоспан B",
            "м2",
            "https://stroysnab.ru/product/izospan-b/",
            page_text,
            pre_inn="7701234567",
        )
    assert quote_ok is not None
    assert quote_ok.price_rub == pytest.approx(40.0)
    assert quote_ok.raw_price_rub == pytest.approx(3000.0)

    # Case B: AI fails to convert (price_rub == raw_price_rub) -> MUST be rejected (Rule 14)
    ai_unconverted = {
        **ai_converted,
        "price_rub": 3000.0,
        "raw_price_rub": 3000.0,
        "conversion_comment": "",
    }
    with patch("app.price_monitoring.extractor.call_llm", AsyncMock(return_value=json.dumps(ai_unconverted))):
        quote_bad = await pm_ext.extract_supplier_quote(
            settings,
            "Пленка пароизоляционная Изоспан B",
            "м2",
            "https://stroysnab.ru/product/izospan-b/",
            page_text,
            pre_inn="7701234567",
        )
    assert quote_bad is None


def test_cluster_and_reconcile_skips_already_converted_quotes():
    q1 = SupplierQuote(
        company_name="Поставщик 1",
        url="https://s1.ru/p1",
        price_rub=40.0,
        raw_price_rub=3000.0,
        site_unit="рулон",
        unit="м2",
        conversion_comment="Рулон 75 м2: 3000 / 75 = 40 руб/м2",
    )
    q2 = SupplierQuote(
        company_name="Поставщик 2",
        url="https://s2.ru/p2",
        price_rub=420.0,
        raw_price_rub=420.0,
        site_unit="м2",
        unit="м2",
        conversion_comment="",
    )
    q3 = SupplierQuote(
        company_name="Поставщик 3",
        url="https://s3.ru/p3",
        price_rub=430.0,
        raw_price_rub=430.0,
        site_unit="м2",
        unit="м2",
        conversion_comment="",
    )
    item_res = ItemPriceResult(
        row_number=1,
        raw_name="Изоспан B",
        clean_name="Изоспан B",
        unit="м2",
        quantity="100",
        quotes=[q1, q2, q3],
    )
    pm_pipe.cluster_and_reconcile_item_quotes(item_res)
    # Quote 1 already has conversion_comment and raw_price_rub != price_rub, so it must NOT be multiplied by 10x
    assert q1.price_rub == pytest.approx(40.0)


@pytest.mark.asyncio
async def test_process_single_item_parallel_batches_respect_budget_and_distinct_domains(monkeypatch):
    import httpx

    settings = SystemSettings()
    active = 0
    max_concurrent = 0

    class DummyEngine:
        async def search(self, query, max_results=10, allow_b2b_retailers=False, **kwargs):
            return [
                ys.YandexSearchResult(
                    title=f"Клапан {i}",
                    url=f"https://shop-{i}.ru/product/item-{i}/",
                    snippet="Цена 1000 руб",
                    domain=f"shop-{i}.ru",
                )
                for i in range(1, 6)
            ]

    async def fake_fetch(client, url, *args, **kwargs):
        nonlocal active, max_concurrent
        active += 1
        max_concurrent = max(max_concurrent, active)
        await asyncio.sleep(0.04)
        active -= 1
        idx = int(url.split("-")[-1].strip("/"))
        price = 1000 + idx * 10
        return (f"Описание товара Клапан ДУ50 и цена {price} руб с НДС " * 15, "", "", "")

    async def fake_extract(*args, url="", **kwargs):
        idx = int(url.split("-")[-1].strip("/"))
        return SupplierQuote(
            company_name=f"ООО Поставщик {idx}",
            inn=f"770000000{idx}",
            url=url,
            price_rub=1000.0 + idx * 10,
            raw_price_rub=1000.0 + idx * 10,
            site_unit="шт",
            unit="шт",
        )

    monkeypatch.setattr(pm_pipe, "generate_monitoring_queries_ai", AsyncMock(return_value=["клапан ду50 купить цена"]))
    monkeypatch.setattr(pm_pipe, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pm_pipe, "extract_supplier_quote", fake_extract)

    async with httpx.AsyncClient() as http_client:
        res = await pm_pipe.process_single_item(
            item_tuple=(1, "Клапан ДУ50", "шт"),
            engine=DummyEngine(),
            settings=settings,
            http_client=http_client,
            search_semaphore=asyncio.Semaphore(4),
            max_suppliers=3,
            min_target_suppliers=3,
        )
    assert len(res.quotes) == 3
    assert max_concurrent >= 2
