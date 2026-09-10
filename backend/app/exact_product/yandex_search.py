"""
Yandex Search API integration.
Supports both v1 (legacy XML) and v2 (new async) APIs.
"""

import os
import asyncio
import httpx
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import structlog

logger = structlog.get_logger(__name__)


# Excluded domains (marketplaces)
EXCLUDED_DOMAINS = [
    "ozon.ru",
    "wildberries.ru",
    "avito.ru",
    "aliexpress.ru",
    "aliexpress.com",
    "market.yandex.ru",
    "sbermegamarket.ru",
    "yandex.ru",
    "google.com",
    "wikipedia.org",
    "youtube.com",
    "vk.com",
    "ok.ru",
    "dzen.ru",
    "2gis.ru",
    "maps.yandex.ru",
    "irecommend.ru",
    "otzovik.com",
    "vc.ru",
    "habr.com",
    "pikabu.ru",
    "drive2.ru",
    "avto.ru",
    "vseinstrumenti.ru",
    "dns-shop.ru",
    "citilink.ru",
    "leroymerlin.ru",
    "lemanapro.ru",
    "megamarket.ru",
]


@dataclass
class YandexSearchResult:
    """Single search result."""

    url: str
    domain: str
    title: str
    snippet: str = ""
    position: int = 0


class YandexSearchEngine:
    """Yandex Search API client with fallback support."""

    # API endpoints
    V1_API_URL = "https://yandex.ru/search/xml"
    V2_API_URL = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
    V2_OPERATION_URL = "https://operation.api.cloud.yandex.net/operations"

    def __init__(self, folder_id: str, api_key: str):
        self.folder_id = folder_id
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_query(self, query: str) -> str:
        """Add manufacturer keywords."""
        keywords = ["производитель", "завод", "оптом", "официальный сайт"]
        has_keyword = any(k in query.lower() for k in keywords)

        if has_keyword:
            return query
        else:
            return f"{query} производитель"

    async def search(
        self, query: str, max_results: int = 10, enrich_query: bool = True, max_pages: int = 1
    ) -> list[YandexSearchResult]:
        """
        Search using Yandex API. Tries v2 first, falls back to v1.
        """
        logger.info("yandex_search_start", query=query[:80], max_pages=max_pages)

        if not self.folder_id or not self.api_key:
            logger.warning("yandex_api_not_configured")
            return []

        # Try v2 API first
        results = await self._search_v2(query, max_results, enrich_query, max_pages)

        if not results:
            # Fallback to v1 (works until 31.12.2025)
            logger.info("yandex_fallback_v1")
            results = await self._search_v1(query, max_results, enrich_query)

        # Filter excluded domains
        filtered = [r for r in results if r.domain not in EXCLUDED_DOMAINS]
        logger.info(
            "yandex_search_complete", query=query[:80], results_count=len(filtered)
        )

        return filtered[:max_results]

    async def _search_v2(
        self, query: str, max_results: int, enrich_query: bool, max_pages: int = 1
    ) -> list[YandexSearchResult]:
        """Search using v2 async API with pagination."""
        try:
            search_query = self._build_query(query) if enrich_query else query
            client = await self._get_client()
            headers = {
                "Authorization": f"Api-Key {self.api_key}",
                "Content-Type": "application/json",
            }

            all_results: list[YandexSearchResult] = []
            seen_domains: set[str] = set()

            groups_on_page = 70
            try:
                configured_gop = os.getenv("AIPOISK_YANDEX_GROUPS_ON_PAGE", "")
                if configured_gop:
                    groups_on_page = max(10, min(100, int(configured_gop)))
            except Exception:
                groups_on_page = 70

            for page in range(max_pages):
                body = {
                    "query": {"searchType": "SEARCH_TYPE_RU", "queryText": search_query, "page": str(page)},
                    "folderId": self.folder_id,
                    "responseFormat": "FORMAT_XML",
                    "groupSpec": {"groupsOnPage": groups_on_page, "docsInGroup": 1},
                }

                response = await client.post(self.V2_API_URL, json=body, headers=headers)

                if response.status_code != 200:
                    logger.warning("yandex_v2_error", status_code=response.status_code, page=page)
                    break

                data = response.json()
                operation_id = data.get("id")

                if not operation_id:
                    break

                page_results = await self._wait_for_v2_operation(operation_id, headers)
                if not page_results:
                    break

                for r in page_results:
                    if r.domain not in seen_domains:
                        seen_domains.add(r.domain)
                        all_results.append(r)

                if len(all_results) >= max_results:
                    break

            return all_results[:max_results]

        except Exception as e:
            logger.warning("yandex_v2_exception", error=str(e))
            return []

    async def _wait_for_v2_operation(
        self, operation_id: str, headers: dict
    ) -> list[YandexSearchResult]:
        """Wait for v2 async operation."""
        client = await self._get_client()

        poll_delays = [0.3, 0.5, 0.8, 1.2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5]
        for attempt in range(30):
            await asyncio.sleep(poll_delays[attempt])

            try:
                response = await client.get(
                    f"{self.V2_OPERATION_URL}/{operation_id}", headers=headers
                )
                if response.status_code != 200:
                    continue

                data = response.json()
                if data.get("done"):
                    if "error" in data:
                        return []

                    raw_data = data.get("response", {}).get("rawData", "")
                    if raw_data:
                        return self._parse_v2_xml(raw_data)
                    return []
            except Exception:
                continue

        return []

    def _parse_v2_xml(self, xml_data: str) -> list[YandexSearchResult]:
        """Parse v2 XML response (base64 encoded)."""
        import base64

        try:
            decoded = base64.b64decode(xml_data).decode("utf-8")
            return self._parse_xml(decoded)
        except Exception:
            return self._parse_xml(xml_data)

    async def _search_v1(
        self, query: str, max_results: int, enrich_query: bool
    ) -> list[YandexSearchResult]:
        """Search using legacy v1 XML API (works until 31.12.2025)."""
        try:
            search_query = self._build_query(query) if enrich_query else query

            # Build exclusions
            exclusions = " ".join(f"~~{d}" for d in EXCLUDED_DOMAINS[:10])
            full_query = f"{search_query} {exclusions}"

            params = {
                "folderid": self.folder_id,
                "apikey": self.api_key,
                "query": full_query,
                "l10n": "ru",
                "sortby": "rlv",
                "filter": "strict",
                "groupby": f"attr=d.mode=deep.groups-on-page={max_results}.docs-in-group=1",
            }

            client = await self._get_client()
            response = await client.get(self.V1_API_URL, params=params)

            if response.status_code != 200:
                logger.warning("yandex_v1_error", status_code=response.status_code)
                # Check for deprecation warning
                if "4002" in response.text:
                    logger.warning(
                        "yandex_v1_blocked", reason="API v1 deprecated, need v2 key"
                    )
                return []

            return self._parse_xml(response.text)

        except Exception as e:
            logger.error("yandex_v1_exception", error=str(e))
            return []

    def _parse_xml(self, xml_text: str) -> list[YandexSearchResult]:
        """Parse Yandex XML response."""
        results = []

        try:
            root = ET.fromstring(xml_text)

            # Check for errors
            error = root.find(".//error")
            if error is not None:
                code = error.get("code", "")
                text = error.text or ""
                logger.warning("yandex_xml_error", code=code, text=text[:50])
                return []

            position = 0
            for group in root.findall(".//group"):
                for doc in group.findall(".//doc"):
                    url_elem = doc.find("url")
                    title_elem = doc.find("title")

                    if url_elem is None or not url_elem.text:
                        continue

                    url = url_elem.text.strip()
                    title = (
                        title_elem.text.strip()
                        if title_elem is not None and title_elem.text
                        else ""
                    )

                    try:
                        domain = urlparse(url).netloc.lower().replace("www.", "")
                    except Exception:
                        continue

                    snippet = ""
                    passages = doc.find("passages")
                    if passages is not None:
                        passage = passages.find("passage")
                        if passage is not None and passage.text:
                            snippet = passage.text.strip()

                    position += 1
                    results.append(
                        YandexSearchResult(
                            url=url,
                            domain=domain,
                            title=title,
                            snippet=snippet,
                            position=position,
                        )
                    )

            return results

        except ET.ParseError as e:
            logger.error("yandex_xml_parse_error", error=str(e))
            return []
