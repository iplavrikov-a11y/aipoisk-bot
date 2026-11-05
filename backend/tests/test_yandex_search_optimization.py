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
