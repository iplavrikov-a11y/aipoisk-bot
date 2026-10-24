from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.exact_product.yandex_search import YandexSearchResult
from app.price_monitoring import extractor, pipeline
from app.price_monitoring.models import SupplierQuote


def _result(url: str, *, snippet: str = "Цена 1000 руб.") -> YandexSearchResult:
    return YandexSearchResult(
        url=url,
        domain=url.split("/")[2],
        title="Коммерческое предложение",
        snippet=snippet,
    )


class _SearchEngine:
    def __init__(self, results_by_query: dict[str, list[YandexSearchResult]]) -> None:
        self.results_by_query = results_by_query
        self.queries: list[str] = []

    async def search(self, query: str, **_kwargs) -> list[YandexSearchResult]:
        self.queries.append(query)
        return list(self.results_by_query.get(query, []))


def _settings() -> SimpleNamespace:
    return SimpleNamespace(has_active_ai_provider=False)


def _quote(url: str, price: float = 1000.0) -> SupplierQuote:
    return SupplierQuote(
        company_name=f"Поставщик {url}",
        price_rub=price,
        raw_price_rub=price,
        unit="шт",
        url=url,
    )


@pytest.mark.asyncio
async def test_wave_one_cannot_starve_wave_two_with_twenty_candidate_budget(monkeypatch):
    primary = [_result(f"https://primary-{idx}.ru/product") for idx in range(20)]
    fallback_url = "https://fallback.ru/exact-product"
    engine = _SearchEngine({"wave-one": primary, "wave-two": [_result(fallback_url)]})
    extraction_urls: list[str] = []

    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: ["wave-two"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Карточка товара. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        extraction_urls.append(kwargs["url"])
        return _quote(kwargs["url"]) if kwargs["url"] == fallback_url else None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert [quote.url for quote in result.quotes] == [fallback_url]
    assert len(extraction_urls) <= 20
    assert fallback_url in extraction_urls


@pytest.mark.asyncio
async def test_failed_page_does_not_blacklist_a_second_page_on_same_domain(monkeypatch):
    first_url = "https://supplier.ru/catalog"
    second_url = "https://supplier.ru/product/exact"
    engine = _SearchEngine({"wave-one": [_result(first_url), _result(second_url)]})

    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Карточка товара. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"]) if kwargs["url"] == second_url else None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert result.quotes[0].url == second_url


@pytest.mark.asyncio
async def test_strict_identifier_is_quoted_in_every_wave_and_can_use_fallback(monkeypatch):
    code = "5ВК.568.007.2"
    primary = [_result(f"https://primary-{idx}.ru/product") for idx in range(12)]
    fallback_url = "https://factory.ru/product"
    engine = _SearchEngine({
        f'"{code}" primary': primary,
        f'"{code}" fallback': [_result(fallback_url)],
    })

    monkeypatch.setattr(pipeline, "extract_generic_nomenclature_codes", lambda _name: [code])
    monkeypatch.setattr(pipeline, "is_drawing_or_part_code", lambda _code, _name: True)
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["primary"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: ["fallback"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return f"Точная деталь {code}. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"]) if kwargs["url"] == fallback_url else None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, f"Деталь {code}", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert len(engine.queries) >= 2
    assert all(f'"{code}"' in query for query in engine.queries)


@pytest.mark.asyncio
async def test_no_result_reason_and_diagnostics_are_explicit(monkeypatch):
    engine = _SearchEngine({"wave-one": []})
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: [])

    result = await pipeline.process_single_item(
        (1, "Редкий товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "not_found"
    assert result.not_found_reason == "no_results"
    assert result.search_diagnostics["extraction_attempts"] == 0
    assert result.search_diagnostics["search_results"] == 0


def test_checkpoint_roundtrip_preserves_search_diagnostics(tmp_path):
    result = pipeline.ItemPriceResult(
        row_number=1,
        raw_name="Товар",
        clean_name="Товар",
        unit="шт",
        status="not_found",
        not_found_reason="budget_exhausted",
        search_diagnostics={"extraction_attempts": 20, "budget_exhausted": True},
    )
    checkpoint = tmp_path / "checkpoint.json"

    pipeline._save_checkpoint(str(checkpoint), [result], total=1, yandex_requests=3)
    loaded, request_count = pipeline._load_checkpoint(str(checkpoint))

    assert request_count == 3
    assert loaded[0].not_found_reason == "budget_exhausted"
    assert loaded[0].search_diagnostics == {
        "extraction_attempts": 20,
        "budget_exhausted": True,
    }


@pytest.mark.asyncio
async def test_commercial_model_identifier_is_quoted_in_all_search_waves(monkeypatch):
    code = "2.607.019.435"
    fallback_url = "https://bosch-supplier.ru/product"
    expected_primary = f'"{code}" primary'
    expected_fallback = f'"{code}" fallback'
    engine = _SearchEngine({
        expected_primary: [],
        expected_fallback: [_result(fallback_url)],
    })

    monkeypatch.setattr(pipeline, "extract_generic_nomenclature_codes", lambda _name: [code])
    monkeypatch.setattr(pipeline, "is_drawing_or_part_code", lambda _code, _name: True)
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["primary"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: ["fallback"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return f"Товар Bosch {code}. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"])

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, f"Bosch {code}", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert engine.queries == [expected_primary, expected_fallback]


@pytest.mark.asyncio
async def test_snippet_only_quote_is_marked_as_search_snippet(monkeypatch):
    url = "https://supplier.ru/product"
    engine = _SearchEngine({"wave-one": [_result(url, snippet="Товар 1000 руб.")]})
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def unavailable_page(_client, _url):
        return None, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"])

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", unavailable_page)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert result.quotes[0].evidence_level == "search_snippet"
    assert result.quotes[0].retrieved_at
    assert "Товар 1000 руб." in result.quotes[0].source_excerpt


@pytest.mark.asyncio
async def test_snippet_price_is_not_marked_as_page_content_when_body_has_no_price(monkeypatch):
    url = "https://supplier.ru/product"
    engine = _SearchEngine({"wave-one": [_result(url, snippet="Товар 1000 руб.")]})
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def page_without_price(_client, _url):
        return "Описание товара без стоимости. " * 8, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"], price=1000.0)

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", page_without_price)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.quotes[0].evidence_level == "search_snippet"
    assert "Товар 1000 руб." in result.quotes[0].source_excerpt
    assert "Описание товара без стоимости" not in result.quotes[0].source_excerpt


@pytest.mark.asyncio
async def test_page_price_is_marked_as_page_content_with_page_excerpt(monkeypatch):
    url = "https://supplier.ru/product"
    engine = _SearchEngine({"wave-one": [_result(url, snippet="Краткий сниппет 1000 руб.")]})
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    page_body = "Проверенная карточка товара. Цена на странице 1000 рублей. " * 4

    async def page_with_price(_client, _url):
        return page_body, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"], price=1000.0)

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", page_with_price)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.quotes[0].evidence_level == "page_content"
    assert result.quotes[0].source_excerpt.startswith("Проверенная карточка товара")
    assert "Краткий сниппет" not in result.quotes[0].source_excerpt


@pytest.mark.parametrize(
    ("candidate", "registered", "expected"),
    [
        ("etm.ru", "etm.ru", True),
        ("shop.etm.ru", "etm.ru", True),
        ("fake-etm.ru", "etm.ru", False),
        ("ozon.ru.evil.example", "ozon.ru", False),
    ],
)
def test_known_retailer_domain_match_is_exact_or_subdomain(candidate, registered, expected):
    assert pipeline._domain_matches(candidate, registered) is expected


@pytest.mark.asyncio
async def test_measurements_are_not_quoted_as_product_identifiers(monkeypatch):
    model = "HR03"
    fallback_url = "https://battery-supplier.ru/product"
    engine = _SearchEngine({
        f'"{model}" primary': [],
        f'"{model}" fallback': [_result(fallback_url)],
    })
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["primary"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: ["fallback"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Аккумулятор HR03. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"])

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Аккумулятор Duracell HR03 1.2В 1000мА/ч", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert engine.queries == [f'"{model}" primary', f'"{model}" fallback']


@pytest.mark.asyncio
async def test_unattempted_primary_tail_uses_budget_left_by_empty_later_waves(monkeypatch):
    winning_url = "https://primary-tail.ru/exact"
    primary = [_result(f"https://primary-{idx}.ru/product") for idx in range(12)] + [_result(winning_url)]
    engine = _SearchEngine({"wave-one": primary})
    extraction_urls: list[str] = []

    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Карточка товара. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        extraction_urls.append(kwargs["url"])
        return _quote(kwargs["url"]) if kwargs["url"] == winning_url else None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert winning_url in extraction_urls
    assert len(extraction_urls) == 13


@pytest.mark.asyncio
async def test_wave_three_can_recover_when_first_two_waves_find_no_price(monkeypatch):
    wave3_url = "https://wide-search.ru/exact"
    engine = _SearchEngine({
        "wave-one": [_result(f"https://primary-{idx}.ru/product") for idx in range(12)],
        "wave-two": [],
        "wave-three": [_result(wave3_url)],
    })

    async def fake_queries(_clean, _unit, _settings, wave=1, city=""):
        return {1: ["wave-one"], 2: ["wave-two"], 3: ["wave-three"]}[wave]

    monkeypatch.setattr(pipeline, "generate_monitoring_queries_ai", fake_queries)
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Карточка товара. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"]) if kwargs["url"] == wave3_url else None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        SimpleNamespace(has_active_ai_provider=True),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert result.quotes[0].url == wave3_url
    assert result.search_diagnostics["waves_run"] == [1, 2, 3]
    assert result.search_diagnostics["extraction_attempts"] <= 20


@pytest.mark.asyncio
async def test_successful_first_wave_does_not_run_fallback_search(monkeypatch):
    url = "https://supplier.ru/exact"
    engine = _SearchEngine({"wave-one": [_result(url)]})
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Карточка товара. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"])

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.status == "found"
    assert engine.queries == ["wave-one"]
    assert result.search_diagnostics["waves_run"] == [1]


@pytest.mark.asyncio
async def test_item_results_are_same_when_processed_serially_or_concurrently(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "build_commercial_search_queries",
        lambda clean, *_args, **_kwargs: [f"query:{clean}"],
    )
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Карточка товара. Цена 1000 рублей. " * 4, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"])

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    items = [(1, "Красный товар", "шт"), (2, "Синий товар", "шт")]
    result_map = {
        "query:Красный товар": [_result("https://red-supplier.ru/product")],
        "query:Синий товар": [_result("https://blue-supplier.ru/product")],
    }

    async def run_one(item, engine, semaphore):
        return await pipeline.process_single_item(
            item,
            engine,
            _settings(),
            object(),
            semaphore,
            max_suppliers=1,
            min_target_suppliers=1,
        )

    serial_engine = _SearchEngine(result_map)
    serial = [await run_one(item, serial_engine, asyncio.Semaphore(1)) for item in items]
    parallel_engine = _SearchEngine(result_map)
    parallel = await asyncio.gather(
        *(run_one(item, parallel_engine, asyncio.Semaphore(2)) for item in items)
    )

    def snapshot(results):
        return [
            (
                result.row_number,
                result.status,
                [quote.url for quote in result.quotes],
                result.search_diagnostics["extraction_attempts"],
            )
            for result in sorted(results, key=lambda value: value.row_number)
        ]

    assert snapshot(serial) == snapshot(parallel)


@pytest.mark.asyncio
async def test_extraction_budget_remains_capped_at_twenty(monkeypatch):
    primary = [_result(f"https://primary-{idx}.ru/product") for idx in range(30)]
    engine = _SearchEngine({"wave-one": primary})
    extraction_urls: list[str] = []
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Карточка товара. Цена не подтверждена. " * 4, None, None, None

    async def fake_extract(**kwargs):
        extraction_urls.append(kwargs["url"])
        return None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=5,
        min_target_suppliers=5,
    )

    assert result.status == "not_found"
    assert result.not_found_reason == "budget_exhausted"
    assert len(extraction_urls) == 20
    assert result.search_diagnostics["extraction_attempts"] == 20
    assert result.search_diagnostics["budget_exhausted"] is True


@pytest.mark.asyncio
async def test_unavailable_sources_have_network_reason(monkeypatch):
    url = "https://offline-supplier.ru/product"
    engine = _SearchEngine({
        "wave-one": [YandexSearchResult(url=url, domain="offline-supplier.ru", title="", snippet="")]
    })
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)

    async def unavailable_page(_client, _url):
        return None, None, None, None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", unavailable_page)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.not_found_reason == "network"
    assert result.search_diagnostics["fetch_unavailable"] == 1
    assert result.search_diagnostics["extraction_attempts"] == 0


@pytest.mark.asyncio
async def test_candidates_rejected_by_validation_have_all_rejected_reason(monkeypatch):
    url = "https://supplier.ru/product"
    engine = _SearchEngine({"wave-one": [_result(url)]})
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def page_with_wrong_product(_client, _url):
        return "Карточка другого товара. Цена 1000 рублей. " * 4, None, None, None

    async def reject_candidate(**_kwargs):
        return None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", page_with_wrong_product)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", reject_candidate)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    assert result.not_found_reason == "all_rejected"
    assert result.search_diagnostics["extraction_rejected"] == 1


@pytest.mark.asyncio
async def test_budget_exhausted_diagnostic_is_set_for_partial_found_result(monkeypatch):
    primary = [_result(f"https://supplier-{idx}.ru/product") for idx in range(30)]
    first_url = primary[0].url
    engine = _SearchEngine({"wave-one": primary})
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "build_fallback_broad_queries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)

    async def fake_fetch(_client, _url):
        return "Карточка товара. Цена 1000 рублей. " * 4, None, None, None

    async def one_valid_quote(**kwargs):
        return _quote(kwargs["url"]) if kwargs["url"] == first_url else None

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", fake_fetch)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", one_valid_quote)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=5,
        min_target_suppliers=5,
    )

    assert result.status == "found"
    assert result.not_found_reason == ""
    assert len(result.quotes) == 1
    assert result.search_diagnostics["extraction_attempts"] == 20
    assert result.search_diagnostics["budget_exhausted"] is True


@pytest.mark.asyncio
async def test_page_excerpt_is_windowed_around_late_grounded_price(monkeypatch):
    url = "https://supplier.ru/product"
    engine = _SearchEngine({"wave-one": [_result(url, snippet="Краткое описание без цены")]})
    monkeypatch.setattr(pipeline, "build_commercial_search_queries", lambda *_args, **_kwargs: ["wave-one"])
    monkeypatch.setattr(pipeline, "is_valid_domain", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(pipeline, "is_foreign_source", lambda *_args, **_kwargs: False)
    long_page = "Код партии 41000. " + ("Длинное описание товара без стоимости. " * 35) + " КОНТЕКСТ ЦЕНЫ: 1000 рублей за штуку."

    async def late_price_page(_client, _url):
        return long_page, None, None, None

    async def fake_extract(**kwargs):
        return _quote(kwargs["url"], price=1000.0)

    monkeypatch.setattr(pipeline, "fetch_page_content_and_meta", late_price_page)
    monkeypatch.setattr(pipeline, "extract_supplier_quote", fake_extract)

    result = await pipeline.process_single_item(
        (1, "Тестовый товар", "шт"),
        engine,
        _settings(),
        object(),
        asyncio.Semaphore(1),
        max_suppliers=1,
        min_target_suppliers=1,
    )

    quote = result.quotes[0]
    assert quote.evidence_level == "page_content"
    assert "КОНТЕКСТ ЦЕНЫ: 1000 рублей" in quote.source_excerpt
    assert len(quote.source_excerpt) <= 500


@pytest.mark.parametrize(
    ("raw_price", "text"),
    [
        (100.0, "Цена другого товара 41000 руб."),
        (100.0, "Цена другого товара 100 000 руб."),
        (100.0, "Цена другого товара 100\xa0000 руб."),
        (100.0, "Цена другого товара 100\u202f000 руб."),
        (100.0, "Цена другого товара 1 100 руб."),
        (100.0, "Цена другого товара 1,100 руб."),
        (24.45, "В тексте встречаются только числа 24 и 2445."),
    ],
)
def test_price_grounding_rejects_partial_numeric_matches(raw_price, text):
    assert extractor.find_price_grounding_match(raw_price, text) is None
    assert extractor.is_price_grounded_in_text(raw_price, text) is False


@pytest.mark.parametrize(
    ("raw_price", "text", "matched_text"),
    [
        (1000.0, "Цена 1 000 руб.", "1 000"),
        (1000.0, "Цена 1\xa0000 руб.", "1\xa0000"),
        (1000.0, "Цена 1.000 руб.", "1.000"),
        (1000.0, "Цена 1,000 руб.", "1,000"),
        (1000.0, "Цена 1000.00 ₽", "1000.00"),
        (1000.0, "Цена 1000,00 ₽", "1000,00"),
        (1000.0, "Цена 1000.0 ₽", "1000.0"),
        (1000.0, "Цена 1000,0 ₽", "1000,0"),
        (24.5, "Цена 24,50 ₽", "24,50"),
        (24.5, "Цена 24.5 ₽", "24.5"),
        (24.45, "Цена 24.45 ₽", "24.45"),
    ],
)
def test_price_grounding_returns_exact_numeric_match(raw_price, text, matched_text):
    match = extractor.find_price_grounding_match(raw_price, text)
    assert match is not None
    assert match.group(0) == matched_text
    assert extractor.is_price_grounded_in_text(raw_price, text) is True
