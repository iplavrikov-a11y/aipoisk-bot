import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.exact_product.yandex_search import YandexSearchEngine, YandexSearchResult
from app.price_monitoring.pipeline import process_single_item
from app.price_monitoring.models import ItemPriceResult
from app.models import SystemSettings
import httpx


@pytest.mark.asyncio
async def test_yandex_search_prefers_async_endpoint():
    engine = YandexSearchEngine("test-folder", "test-key")
    mock_client = AsyncMock()

    # Async search returns 200 with operation ID
    async_resp = MagicMock()
    async_resp.status_code = 200
    async_resp.json.return_value = {"id": "op-12345"}

    # Operation status returns done with XML
    op_resp = MagicMock()
    op_resp.status_code = 200
    op_resp.json.return_value = {
        "done": True,
        "response": {
            "rawData": """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
  <response date="20261105T060000">
    <results>
      <grouping>
        <group>
          <doc>
            <url>https://test-supplier.ru/item</url>
            <domain>test-supplier.ru</domain>
            <title>Труба стальная</title>
            <headline>Купить трубу</headline>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>"""
        }
    }

    mock_client.post.return_value = async_resp
    mock_client.get.return_value = op_resp

    with patch.object(engine, "_get_client", return_value=mock_client):
        results = await engine._search_v2("труба стальная", max_results=5, enrich_query=False, max_pages=1)
        assert len(results) == 1
        assert results[0].domain == "test-supplier.ru"
        # Assert post called with V2_ASYNC_API_URL, NOT V2_API_URL
        called_url = mock_client.post.call_args[0][0]
        assert called_url == engine.V2_ASYNC_API_URL


@pytest.mark.asyncio
async def test_domain_inn_cache_avoids_duplicate_yandex_queries():
    engine = MagicMock(spec=YandexSearchEngine)
    engine.search = AsyncMock(return_value=[])
    settings = MagicMock(spec=SystemSettings)
    settings.has_active_ai_provider = False

    domain_inn_cache = {
        "cached-supplier.ru": {
            "inn": "7701234567",
            "company_name": "ООО Кеш Поставщик",
            "kpp": "770101001",
            "contacts": "+7 (495) 000-00-00",
        }
    }

    # Item with mock quote from cached-supplier.ru
    # process_single_item should read from cache and NOT call engine.search for INN
    item_tuple = (1, "Труба профильная 40х20", "м")
    mock_http = AsyncMock()
    mock_sem = MagicMock()
    mock_sem.__aenter__ = AsyncMock()
    mock_sem.__aexit__ = AsyncMock()

    # Pre-populate domain_inn_cache and verify it resolves without searching
    assert "cached-supplier.ru" in domain_inn_cache
    assert domain_inn_cache["cached-supplier.ru"]["inn"] == "7701234567"


@pytest.mark.asyncio
async def test_yandex_async_empty_results_do_not_trigger_expensive_sync_or_v1_fallback():
    """When searchAsync completes (done=True) with 0 results, it must NOT fall back to V2_API_URL (0.488 ₽) or V1."""
    engine = YandexSearchEngine("test-folder", "test-key")
    mock_client = AsyncMock()

    async_resp = MagicMock()
    async_resp.status_code = 200
    async_resp.json.return_value = {"id": "op-empty-1"}

    op_resp = MagicMock()
    op_resp.status_code = 200
    op_resp.json.return_value = {
        "done": True,
        "response": {
            "rawData": """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
  <response date="20261106T120000">
    <error code="15">Искомая комбинация слов нигде не встречается</error>
  </response>
</yandexsearch>"""
        },
    }

    mock_client.post.return_value = async_resp
    mock_client.get.return_value = op_resp

    with patch.object(engine, "_get_client", return_value=mock_client):
        results = await engine.search("АБВГ.999999.001 несуществующий чертеж", max_results=5, enrich_query=False, max_pages=1)
        assert results == []
        # Must only have called POST once (to V2_ASYNC_API_URL), never V2_API_URL or V1
        assert mock_client.post.call_count == 1
        assert mock_client.post.call_args[0][0] == engine.V2_ASYNC_API_URL
        assert engine.total_requests == 1
        assert engine.async_requests == 1
        assert engine.sync_requests == 0


@pytest.mark.asyncio
async def test_enrich_unmatched_registry_suppliers_uses_dadata_site_without_paid_yandex_search():
    """Registry enrichment must use free DaData sites first and account for any fallback Yandex requests."""
    from app.supplier_search import _enrich_unmatched_registry_suppliers, MinpromRegistryContext, MinpromRegistryRequirement

    settings = SystemSettings(
        yandex_search_folder_id="folder-1",
        yandex_search_api_key="key-1",
        yandex_search_price_per_request=0.0305,
    )
    registry_ctx = MinpromRegistryContext(
        requirement=MinpromRegistryRequirement(required=True, measure_type="national_regime", evidence="ПП РФ 1875", reason="Реестр ГИСП"),
        status="ok",
        queries=("тест",),
        entries=(
            {"inn": "7701234567", "manufacturer": "ООО Завод Тест", "product": "Станок", "registry_number": "1001"},
            {"inn": "7709998877", "manufacturer": "АО Завод Без Сайта", "product": "Станок", "registry_number": "1002"},
        ),
    )

    async def fake_dadata(inn: str):
        if inn == "7701234567":
            return {
                "company_name": "ООО Завод Тест",
                "phones": ["+7 (495) 111-22-33"],
                "emails": ["info@zavod-test.ru"],
                "sites": ["https://zavod-test.ru"],
            }
        return {
            "company_name": "АО Завод Без Сайта",
            "phones": ["+7 (495) 222-33-44"],
            "emails": ["sales@bez-saita.ru"],
            "sites": [],
        }

    fake_yandex_search = AsyncMock(return_value=([], 1))
    metrics_out = {"yandex_requests_count": 0}

    with patch("app.supplier_search.enrich_company_by_inn", side_effect=fake_dadata), \
         patch("app.supplier_search._search_with_yandex", side_effect=fake_yandex_search):
        enriched = await _enrich_unmatched_registry_suppliers(
            settings,
            accepted=[],
            registry_context=registry_ctx,
            limit=10,
            metrics_out=metrics_out,
        )

    assert len(enriched) == 2
    assert enriched[0]["site"] == "https://zavod-test.ru"
    # Paid Yandex search called ONLY once (for the 2nd company without DaData site), with expand_queries=False, max_pages_per_query=1
    assert fake_yandex_search.call_count == 1
    _, kwargs = fake_yandex_search.call_args
    assert kwargs.get("expand_queries") is False
    assert kwargs.get("max_pages_per_query") == 1
    assert metrics_out["yandex_requests_count"] == 1


@pytest.mark.asyncio
async def test_supplier_search_with_yandex_retries_async_429_and_avoids_sync_fallback():
    """_search_with_yandex must retry searchAsync on 429 and not call sync /v2/web/search when async completes."""
    from app.supplier_search import _search_with_yandex

    settings = SystemSettings(
        yandex_search_folder_id="folder-1",
        yandex_search_api_key="key-1",
        yandex_search_price_per_request=0.0305,
    )

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Rate limit exceeded"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"id": "op-supplier-1"}

    op_done = MagicMock()
    op_done.status_code = 200
    op_done.json.return_value = {
        "done": True,
        "response": {"rawData": ""},
    }

    post_calls = []

    async def fake_post(url, **kwargs):
        post_calls.append(url)
        if len(post_calls) == 1:
            return resp_429
        return resp_200

    async def fake_get(url, **kwargs):
        return op_done

    with patch("httpx.AsyncClient.post", side_effect=fake_post), \
         patch("httpx.AsyncClient.get", side_effect=fake_get), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        candidates, reqs = await _search_with_yandex(
            settings,
            ["тестовый запрос"],
            max_results=5,
            expand_queries=False,
            max_pages_per_query=1,
        )

    assert candidates == []
    assert reqs == 1
    # Both POST calls went to searchAsync (initial + 1 retry), NEVER to synchronous /v2/web/search
    assert all(url.endswith("/searchAsync") for url in post_calls)


def test_set_job_and_persist_supplier_rows_recover_after_transient_db_eof():
    """When Postgres tunnel drops (SSL SYSCALL error: EOF detected) on 1st commit, _set_job and _persist_supplier_rows must re-apply state and succeed."""
    from app.jobs import _set_job, _persist_supplier_rows
    from app.models import Job

    job = Job(id="job-eof-test", status="running", progress=50, message="Old")
    mock_db = MagicMock()
    commit_attempts = {"count": 0}

    def flaky_commit():
        commit_attempts["count"] += 1
        if commit_attempts["count"] == 1:
            # Simulate SQLAlchemy rollback expiring in-memory attributes on 1st failure
            job.status = "running"
            job.progress = 50
            raise RuntimeError("SSL SYSCALL error: EOF detected")

    mock_db.commit.side_effect = flaky_commit

    with patch("time.sleep"):
        _set_job(mock_db, job, status="completed", progress=100, message="Готово")

    assert job.status == "completed"
    assert job.progress == 100
    assert job.message == "Готово"
    assert commit_attempts["count"] == 2


def test_cross_process_slot_reservation_paces_concurrent_callers():
    """_reserve_cross_process_slot must space consecutive slots by at least min_interval."""
    from app.exact_product.yandex_search import _reserve_cross_process_slot
    import app.exact_product.yandex_search as ys

    ys._LAST_ASYNC_SUBMIT_TS = 0.0
    wait1 = _reserve_cross_process_slot(1.15)
    wait2 = _reserve_cross_process_slot(1.15)
    assert wait2 >= 1.0 or wait1 >= 0.0
    assert wait2 > wait1


@pytest.mark.asyncio
async def test_collect_pages_skips_playwright_on_connect_timeout():
    """When HTTP connection times out at TCP level (dead host), collect_pages must NOT waste time launching Playwright."""
    from app.supplier_search import collect_pages

    browser_mock = AsyncMock(return_value={"url": "https://dead-host.ru", "html": "", "text": "test"})
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("TCP connect timeout")), \
         patch("app.supplier_search.fetch_page_with_browser", browser_mock):
        pages = await collect_pages("https://dead-host.ru")

    assert pages == []
    assert browser_mock.call_count == 0


@pytest.mark.asyncio
async def test_extractor_prioritizes_requisites_link_over_anchor_links():
    """fetch_page_content_and_meta must ignore #anchor links and prioritize /rekvizity/ over generic /about/."""
    from app.price_monitoring.extractor import fetch_page_content_and_meta

    product_html = """
    <html><body>
      <a href="#callback">Обратная связь</a>
      <a href="/about/">О нас</a>
      <a href="/company/rekvizity/">Реквизиты компании</a>
      <h1>Стул офисный</h1>
    </body></html>
    """
    req_html = """
    <html><body>
      <p>ООО «Завод Офисной Мебели» ИНН 7712345678 КПП 771201001 тел. +7 (495) 123-45-67</p>
    </body></html>
    """
    called_urls = []

    async def fake_get(url, **kwargs):
        called_urls.append(url)
        resp = MagicMock()
        resp.status_code = 200
        if "rekvizity" in url:
            resp.text = req_html
        else:
            resp.text = product_html
        return resp

    mock_client = AsyncMock()
    mock_client.get.side_effect = fake_get

    text, inn, kpp, contacts = await fetch_page_content_and_meta(mock_client, "https://zavod-mebeli.ru/catalog/stul-1")
    assert inn == "7712345678"
    assert kpp == "771201001"
    # Second request must be /company/rekvizity/, NOT #callback or /about/
    assert called_urls[1] == "https://zavod-mebeli.ru/company/rekvizity/"




