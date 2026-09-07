from __future__ import annotations

import asyncio
from typing import List, Union
import structlog

from .llm_bridge import get_settings
from .yandex_search import YandexSearchEngine

logger = structlog.get_logger(__name__)


async def _fetch_search_results_for_specs(query: Union[str, list], max_results: int = 6) -> list:
    """
    Поиск технических спецификаций, паспортов и каталогов через Яндекс Search API (v2/v1).
    100% идентично реализации в EmailAgent.
    """
    settings = get_settings()
    search_results = []

    if isinstance(query, (list, tuple)):
        query = " ".join(str(q).strip() for q in query if str(q).strip())
    query = str(query or "").strip()
    if not query:
        return []

    seen_urls = set()

    # 1. Yandex Search FIRST (primary engine for Russian B2B, catalogues, factory passports)
    folder_id = getattr(settings, "yandex_folder_id", "") or ""
    api_key = getattr(settings, "yandex_api_key", "") or ""

    if folder_id and api_key:
        yandex = YandexSearchEngine(folder_id, api_key)
        try:
            yandex_res = await yandex.search(
                query, max_results=max_results, enrich_query=False
            )
            for y_res in yandex_res:
                u = getattr(y_res, "url", "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    search_results.append(y_res)
        except Exception as e:
            logger.warning("product_search_yandex_failed", error=str(e))
        finally:
            await yandex.close()

    return search_results
