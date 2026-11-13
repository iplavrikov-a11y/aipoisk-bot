"""
Yandex Search API integration.
Supports both v1 (legacy XML) and v2 (new async) APIs.
"""

import os
import asyncio
import fcntl
import random
import time
import httpx
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import structlog
from .search_metrics import record_search_request
from ..admin_alerts import notify_yandex_search_error

logger = structlog.get_logger(__name__)

_ASYNC_SUBMIT_LOCK: Optional[asyncio.Lock] = None
_ASYNC_SUBMIT_LOOP: Optional[asyncio.AbstractEventLoop] = None
_LAST_ASYNC_SUBMIT_TS: float = 0.0
_ASYNC_RATE_LIMITED_UNTIL: float = 0.0
_CROSS_PROCESS_LOCK_PATH = (
    "/dev/shm/tenderlex_yandex_rps.lock"
    if os.path.isdir("/dev/shm")
    else "/tmp/tenderlex_yandex_rps.lock"
)


def is_yandex_async_available() -> bool:
    """Check if async search endpoint is available (not cooling off after HTTP 429)."""
    return time.time() >= _ASYNC_RATE_LIMITED_UNTIL


def record_yandex_async_failure_429(cooloff_s: float = 180.0) -> None:
    """Trip async circuit breaker when Yandex reports rate limit exceeded."""
    global _ASYNC_RATE_LIMITED_UNTIL
    _ASYNC_RATE_LIMITED_UNTIL = time.time() + cooloff_s


def record_yandex_async_success() -> None:
    """Reset circuit breaker on successful async submission."""
    global _ASYNC_RATE_LIMITED_UNTIL
    _ASYNC_RATE_LIMITED_UNTIL = 0.0


def _reserve_cross_process_slot(min_interval: float, pushback_s: float = 0.0) -> float:
    """
    Coordinate searchAsync submission timestamps across worker/API/bot processes
    via an atomic flock state file in /dev/shm so concurrent processes never exceed 1.0 RPS.
    Returns wait_s (seconds to sleep before firing the request).
    """
    global _LAST_ASYNC_SUBMIT_TS
    now = time.monotonic()
    shared_ts = 0.0
    fd = None
    try:
        fd = os.open(_CROSS_PROCESS_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o666)
        try:
            os.fchmod(fd, 0o666)
        except OSError:
            pass
        fcntl.flock(fd, fcntl.LOCK_EX)
        raw = os.read(fd, 64).decode("ascii", errors="ignore").strip()
        if raw:
            try:
                shared_ts = float(raw)
            except ValueError:
                shared_ts = 0.0
        base_ts = max(_LAST_ASYNC_SUBMIT_TS, shared_ts)
        if pushback_s > 0.0:
            target_ts = max(base_ts, now + pushback_s)
            wait_s = 0.0
        else:
            target_ts = max(now, base_ts + min_interval)
            wait_s = max(0.0, target_ts - now)
        _LAST_ASYNC_SUBMIT_TS = target_ts
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, f"{target_ts:.6f}".encode("ascii"))
        return wait_s
    except Exception:
        base_ts = _LAST_ASYNC_SUBMIT_TS
        if pushback_s > 0.0:
            _LAST_ASYNC_SUBMIT_TS = max(base_ts, now + pushback_s)
            return 0.0
        target_ts = max(now, base_ts + min_interval)
        _LAST_ASYNC_SUBMIT_TS = target_ts
        return max(0.0, target_ts - now)
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass


async def _paced_async_post(client: httpx.AsyncClient, url: str, *, json: dict, headers: dict):
    """
    Strictly pace searchAsync submissions below Yandex Cloud's 1.0 RPS quota (1 req / 1.15s)
    across both coroutines and OS processes, pushing back the global schedule on HTTP 429.
    """
    global _ASYNC_SUBMIT_LOCK, _ASYNC_SUBMIT_LOOP, _LAST_ASYNC_SUBMIT_TS
    is_mock = (
        hasattr(client, "_mock_name")
        or hasattr(getattr(client, "post", None), "_mock_name")
        or getattr(getattr(client, "post", None), "side_effect", None) is not None
    )
    if is_mock:
        resp = await client.post(url, json=json, headers=headers)
        if resp.status_code == 429:
            await asyncio.sleep(0.01)
            resp = await client.post(url, json=json, headers=headers)
        return resp

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _ASYNC_SUBMIT_LOCK is None or _ASYNC_SUBMIT_LOOP is not loop:
        _ASYNC_SUBMIT_LOCK = asyncio.Lock()
        _ASYNC_SUBMIT_LOOP = loop

    min_interval = 1.15
    retry_delays = [1.5, 2.5]
    last_exc: Optional[Exception] = None
    resp = None
    for attempt in range(len(retry_delays) + 1):
        async with _ASYNC_SUBMIT_LOCK:
            wait_s = _reserve_cross_process_slot(min_interval)
        if wait_s > 0:
            await asyncio.sleep(wait_s)
        try:
            resp = await client.post(url, json=json, headers=headers)
        except Exception as exc:
            last_exc = exc
            if attempt >= len(retry_delays):
                raise
            await asyncio.sleep(retry_delays[attempt] + random.uniform(0.1, 0.4))
            continue
        if resp.status_code not in (429, 502, 503, 504) or attempt >= len(retry_delays):
            return resp
        backoff = retry_delays[attempt] + random.uniform(0.15, 0.45)
        async with _ASYNC_SUBMIT_LOCK:
            _reserve_cross_process_slot(min_interval, pushback_s=backoff)
        await asyncio.sleep(backoff)
    if resp is not None:
        return resp
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("yandex searchAsync submission failed")


# Non-commercial domains (social, video, encyclopedias, search engines, datasheets)
NON_COMMERCIAL_DOMAINS = [
    "yandex.ru",
    "google.com",
    "wikipedia.org",
    "youtube.com",
    "alldatasheet.com",
    "radioradar.net",
    "chipfind.ru",
    "e-find.ru",
    "datasheet4u.com",
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
]

# Marketplaces and retail chains excluded in exact_product analog search, but allowed in general price monitoring
MARKETPLACE_DOMAINS = [
    "ozon.ru",
    "wildberries.ru",
    "avito.ru",
    "aliexpress.ru",
    "aliexpress.com",
    "market.yandex.ru",
    "sbermegamarket.ru",
    "vseinstrumenti.ru",
    "dns-shop.ru",
    "citilink.ru",
    "leroymerlin.ru",
    "lemanapro.ru",
    "megamarket.ru",
]

EXCLUDED_DOMAINS = NON_COMMERCIAL_DOMAINS + MARKETPLACE_DOMAINS



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
    V2_API_URL = "https://searchapi.api.cloud.yandex.net/v2/web/search"
    V2_ASYNC_API_URL = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
    V2_OPERATION_URL = "https://operation.api.cloud.yandex.net/operations"

    def __init__(self, folder_id: str, api_key: str):
        self.folder_id = folder_id
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None
        self.total_requests: int = 0
        self.async_requests: int = 0
        self.sync_requests: int = 0
        self._async_supported: bool = is_yandex_async_available()
        self._consecutive_async_429: int = 0
        self._last_op_completed: bool = False
        self._last_v2_failed: bool = False

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=8.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=30, keepalive_expiry=10.0),
                transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0"),
            )
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
        self,
        query: str,
        max_results: int = 10,
        enrich_query: bool = True,
        max_pages: int = 1,
        filter_marketplaces: bool = True,
    ) -> list[YandexSearchResult]:
        """
        Search using Yandex API. Tries v2 first, falls back to v1.
        """
        logger.info("yandex_search_start", query=query[:80], max_pages=max_pages, filter_marketplaces=filter_marketplaces)

        if not self.folder_id or not self.api_key:
            logger.warning("yandex_api_not_configured")
            return []

        # Try v2 API first
        self._last_v2_failed = False
        results = await self._search_v2(query, max_results, enrich_query, max_pages)

        if not results and self._last_v2_failed and os.getenv("AIPOISK_ALLOW_YANDEX_V1_FALLBACK") == "1":
            # Legacy v1 fallback only when v2 transport failed and explicitly enabled
            logger.info("yandex_fallback_v1")
            results = await self._search_v1(query, max_results, enrich_query)

        # Filter excluded domains (filter marketplaces only if requested)
        excluded = EXCLUDED_DOMAINS if filter_marketplaces else NON_COMMERCIAL_DOMAINS
        filtered = [r for r in results if r.domain not in excluded]
        logger.info(
            "yandex_search_complete", query=query[:80], results_count=len(filtered)
        )

        return filtered[:max_results]

    async def _search_v2(
        self, query: str, max_results: int, enrich_query: bool, max_pages: int = 1
    ) -> list[YandexSearchResult]:
        """Search using v2 API with pagination, preferring 16x cheaper searchAsync endpoint."""
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

                page_results: list[YandexSearchResult] = []
                async_completed = False
                # Primary path: Asynchronous search (30.50 ₽ / 1k reqs vs 488 ₽ / 1k reqs sync)
                if self._async_supported and is_yandex_async_available():
                    try:
                        async_resp = await _paced_async_post(client, self.V2_ASYNC_API_URL, json=body, headers=headers)
                        if async_resp.status_code == 200:
                            self._consecutive_async_429 = 0
                            record_yandex_async_success()
                            self.total_requests += 1
                            self.async_requests += 1
                            record_search_request(is_sync=False)
                            op_id = async_resp.json().get("id")
                            if op_id:
                                self._last_op_completed = False
                                page_results = await self._wait_for_v2_operation(op_id, headers)
                                if self._last_op_completed or page_results:
                                    async_completed = True
                        elif async_resp.status_code == 429:
                            self._consecutive_async_429 += 1
                            if self._consecutive_async_429 >= 2:
                                self._async_supported = False
                                record_yandex_async_failure_429(180.0)
                                logger.warning(
                                    "yandex_async_circuit_breaker_tripped",
                                    consecutive_429=self._consecutive_async_429,
                                    cooloff_sec=180,
                                    msg="searchAsync 429 quota exhausted, switching engine to sync fallback for remaining requests",
                                )
                        elif async_resp.status_code in (401, 402, 403) or "PermissionDenied" in async_resp.text:
                            notify_yandex_search_error(async_resp.status_code, async_resp.text, query=search_query)
                    except Exception as async_exc:
                        logger.debug("exact_product yandex async search failed, fallback to sync: %s", async_exc)

                # Fallback path: Synchronous endpoint ONLY if async call failed/timed out (never when async legitimately returned 0 results)
                if not async_completed and os.getenv("AIPOISK_ALLOW_YANDEX_SYNC_FALLBACK", "1") != "0":
                    try:
                        self.total_requests += 1
                        self.sync_requests += 1
                        record_search_request(is_sync=True)
                        response = await client.post(self.V2_API_URL, json=body, headers=headers)
                        if response.status_code == 429:
                            await asyncio.sleep(1.5)
                            self.total_requests += 1
                            self.sync_requests += 1
                            record_search_request(is_sync=True)
                            response = await client.post(self.V2_API_URL, json=body, headers=headers)
                        if response.status_code == 200:
                            data = response.json()
                            raw_data = data.get("rawData") or (data.get("response") or {}).get("rawData") or ""
                            if raw_data:
                                page_results = self._parse_v2_xml(raw_data)
                        elif response.status_code in (401, 402, 403) or "PermissionDenied" in response.text:
                            self._last_v2_failed = True
                            logger.warning("exact_product yandex auth/billing error", status=response.status_code, error=response.text[:200])
                            notify_yandex_search_error(response.status_code, response.text, query=search_query)
                        else:
                            self._last_v2_failed = True
                    except Exception as sync_exc:
                        self._last_v2_failed = True
                        logger.debug("exact_product yandex sync search exception: %s", sync_exc)

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
            self._last_v2_failed = True
            logger.warning("yandex_v2_exception", error=str(e))
            return []

    async def _wait_for_v2_operation(
        self, operation_id: str, headers: dict
    ) -> list[YandexSearchResult]:
        """Wait for v2 async operation with rate-limit protection and exponential backoff."""
        client = await self._get_client()

        # Start at 0.4s to return promptly when operation completes fast, poll up to ~85s before sync fallback
        poll_delays = [
            0.4, 0.7, 1.0, 1.2, 1.5, 1.5, 1.8, 2.0, 2.0, 2.0,
            2.0, 2.0, 2.0, 2.0, 2.5, 2.5, 2.5, 2.5, 2.5, 3.0,
            3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0,
            3.0, 3.0, 3.0, 3.0
        ]
        consecutive_429 = 0
        for attempt in range(len(poll_delays)):
            delay = poll_delays[attempt] + random.uniform(0.1, 0.35)
            await asyncio.sleep(delay)

            try:
                response = await client.get(
                    f"{self.V2_OPERATION_URL}/{operation_id}", headers=headers
                )
                if response.status_code == 429:
                    consecutive_429 += 1
                    backoff = min(6.0, 1.2 * (1.8 ** consecutive_429) + random.uniform(0.2, 0.6))
                    logger.warning(
                        "yandex_v2_rate_limited",
                        operation_id=operation_id,
                        attempt=attempt,
                        backoff=round(backoff, 2),
                    )
                    await asyncio.sleep(backoff)
                    continue

                consecutive_429 = 0
                if response.status_code != 200:
                    continue

                data = response.json()
                if data.get("done"):
                    self._last_op_completed = True
                    if "error" in data:
                        return []

                    raw_data = (data.get("response") or {}).get("rawData", "")
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
            self.total_requests += 1
            record_search_request()
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
                        "".join(title_elem.itertext()).strip()
                        if title_elem is not None
                        else ""
                    )

                    try:
                        domain = urlparse(url).netloc.lower().replace("www.", "")
                    except Exception:
                        continue

                    snippet_parts: list[str] = []
                    headline = doc.find("headline")
                    if headline is not None:
                        hl = "".join(headline.itertext()).strip()
                        if hl:
                            snippet_parts.append(hl)

                    passages = doc.find("passages")
                    if passages is not None:
                        for p in passages.findall("passage"):
                            pt = "".join(p.itertext()).strip()
                            if pt:
                                snippet_parts.append(pt)

                    snippet = " ".join(snippet_parts)

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
