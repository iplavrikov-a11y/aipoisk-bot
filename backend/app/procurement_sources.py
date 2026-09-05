from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import socket
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

SOURCE_KIND_OFFICIAL = "official_eis"
SOURCE_KIND_PROCUREMENT_URL = "procurement_url"
SOURCE_KIND_TENDERPLAN_NOTICE = "tenderplan_notice"

URL_RE = re.compile(r"https?://[^\s<>)\"']+", re.I)
NOTICE_NUMBER_RE = re.compile(r"(?<!\d)(\d{11}|\d{19})(?!\d)")
TRAILING_URL_CHARS = ".,;:!?)]}»”\"'"
OFFICIAL_FOLLOWUP_LIMIT = 4
BLOCKED_SOURCE_HOST_SUFFIXES = (".internal", ".local", ".localhost")
MAX_SOURCE_REDIRECTS = 5


@dataclass(frozen=True)
class SourceFetchResult:
    ok: bool
    context: str = ""
    source_url: str = ""
    status: str = "failed"
    error: str = ""
    extracted_chars: int = 0
    downloaded_files: list = field(default_factory=list)


def extract_source_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in URL_RE.findall(str(text or "")):
        url = normalize_source_url(match)
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def extract_notice_numbers(text: str) -> list[str]:
    without_urls = URL_RE.sub(" ", str(text or ""))
    numbers: list[str] = []
    seen: set[str] = set()
    for match in NOTICE_NUMBER_RE.findall(without_urls):
        if len(match) == 36 or match in seen:
            continue
        seen.add(match)
        numbers.append(match)
    return numbers


def normalize_source_url(value: str) -> str:
    url = str(value or "").strip().rstrip(TRAILING_URL_CHARS)
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    if port not in {None, 80, 443}:
        return ""
    if not _source_host_is_public(parsed.hostname or "", resolve=False):
        return ""
    return url


def _source_ip_is_public(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def _source_host_is_public(hostname: str, *, resolve: bool) -> bool:
    host = str(hostname or "").strip().lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(BLOCKED_SOURCE_HOST_SUFFIXES):
        return False
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        return literal.is_global
    if not resolve:
        return True
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            if item and len(item) > 4 and item[4]
        }
    except OSError:
        return False
    return bool(addresses) and all(_source_ip_is_public(address) for address in addresses)


def source_url_is_public(url: str, *, resolve: bool = True) -> bool:
    normalized = normalize_source_url(url)
    if not normalized:
        return False
    parsed = urlparse(normalized)
    return _source_host_is_public(parsed.hostname or "", resolve=resolve)


def classify_source_url(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").lower()
    if host == "zakupki.gov.ru" or host.endswith(".zakupki.gov.ru"):
        return SOURCE_KIND_OFFICIAL
    return SOURCE_KIND_PROCUREMENT_URL


def source_payloads_from_text(text: str) -> list[dict]:
    payloads = [
        {
            "kind": classify_source_url(url),
            "label": source_label(url),
            "value": url,
        }
        for url in extract_source_urls(text)
    ]
    payloads.extend(
        {
            "kind": SOURCE_KIND_TENDERPLAN_NOTICE,
            "label": source_label(number),
            "value": number,
        }
        for number in extract_notice_numbers(text)
    )
    return payloads


def official_notice_number_from_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    if host != "zakupki.gov.ru" and not host.endswith(".zakupki.gov.ru"):
        return ""
    query = parse_qs(parsed.query)
    for key in ("regNumber", "purchaseNoticeNumber", "reestrNumber", "purchaseNumber"):
        for value in query.get(key) or []:
            number = str(value or "").strip()
            if NOTICE_NUMBER_RE.fullmatch(number):
                return number
    return ""


def source_label(value: str) -> str:
    raw = str(value or "").strip()
    if raw.isdigit() and len(raw) in {11, 19}:
        return f"Закупка {raw}"
    host = (urlparse(raw).hostname or "").lower().removeprefix("www.")
    if classify_source_url(raw) == SOURCE_KIND_OFFICIAL:
        return "ЕИС / zakupki.gov.ru"
    return host or "площадка закупки"


def build_source_context_block(*, kind: str, url: str, text: str) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return ""
    if kind == SOURCE_KIND_TENDERPLAN_NOTICE:
        title = f"=== ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ ПО НОМЕРУ ИЗВЕЩЕНИЯ ({url}) ==="
        instruction = (
            "Это структурированные данные по номеру извещения: карточка, сроки, "
            "нацрежим, документы и разъяснения из ЕИС. Используй эти данные как "
            "основной источник критичных полей карточки закупки; даты ниже считай московским временем, "
            "если источник явно не говорит иное. Разъяснения и ответы заказчика имеют приоритет над "
            "исходной редакцией ТЗ."
        )
    elif kind == SOURCE_KIND_OFFICIAL:
        title = f"=== ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ: ЕИС ({url}) ==="
        instruction = (
            "Это официальный источник закупки. Эти данные имеют прямой приоритет для номера "
            "извещения, заказчика, ИНН/КПП, сроков подачи заявок, даты итогов, НМЦК, способа "
            "закупки, площадки, правового режима и карточки закупки. Не пиши "
            "'данных недостаточно' по этим полям, если они есть в тексте ниже. Все даты "
            "по возможности бери отсюда, потому что карточка ЕИС может быть актуальнее "
            "приложенных файлов. Если здесь есть структурированное ТЗ/ООЗ с товарами, "
            "характеристиками, единицами и количеством, оно имеет высший приоритет для "
            "товарной таблицы. Если товарной таблицы здесь нет, используй приложенные "
            "документы ТЗ/ООЗ."
        )
    else:
        title = f"=== ССЫЛКА НА ПЛОЩАДКУ ЗАКУПКИ ({url}) ==="
        instruction = (
            "Это опубликованная страница закупки на площадке или сайте заказчика. "
            "Используй её как важный источник карточечных данных, сроков, НМЦК, площадки "
            "и описания закупки. Если данные страницы расходятся с приложенными документами, "
            "зафиксируй расхождение в анализе, а товарную таблицу бери из наиболее полного ТЗ/ООЗ."
        )
    return f"{title}\n{instruction}\n\n{text[:500000]}\n"


async def fetch_source_context(kind: str, url: str) -> SourceFetchResult:
    if kind == SOURCE_KIND_TENDERPLAN_NOTICE:
        from .tenderplan import fetch_tenderplan_source_sync

        result = await asyncio.to_thread(fetch_tenderplan_source_sync, url)
        return SourceFetchResult(
            ok=result.ok,
            context=result.context,
            source_url=result.notice_number or url,
            status=result.status,
            error=result.error,
            extracted_chars=len(result.context),
            downloaded_files=result.downloaded_files,
        )

    normalized_url = normalize_source_url(url)
    if not normalized_url or not await asyncio.to_thread(source_url_is_public, normalized_url):
        return SourceFetchResult(ok=False, source_url=url, status="invalid_url", error="Ссылка ведёт на недоступный внутренний адрес")

    official_notice_number = official_notice_number_from_url(normalized_url) if kind == SOURCE_KIND_OFFICIAL else ""
    if official_notice_number:
        from .tenderplan import fetch_tenderplan_source_sync

        result = await asyncio.to_thread(fetch_tenderplan_source_sync, official_notice_number)
        if result.ok and result.context:
            return SourceFetchResult(
                ok=True,
                context=result.context,
                source_url=result.notice_number or official_notice_number,
                status=result.status or "ok",
                error=result.error,
                extracted_chars=len(result.context),
                downloaded_files=result.downloaded_files,
            )

    pages: list[dict] = []
    candidates = candidate_source_urls(normalized_url, kind)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=headers) as client:
            pages.extend(await fetch_source_pages_http(client, candidates[:8], kind))
    except Exception:
        pages = []

    browser_candidates = candidates[:4] if kind == SOURCE_KIND_OFFICIAL else [normalized_url]
    if kind == SOURCE_KIND_OFFICIAL or not pages:
        browser_pages = await fetch_source_pages_with_browser(browser_candidates, kind)
        seen_urls = {page["url"] for page in pages}
        for page in browser_pages:
            if page["url"] not in seen_urls:
                pages.append(page)
                seen_urls.add(page["url"])

    if kind == SOURCE_KIND_OFFICIAL and pages:
        followup_urls = official_followup_urls_from_pages(pages)
        if followup_urls:
            followup_pages: list[dict] = []
            try:
                async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=headers) as client:
                    followup_pages.extend(await fetch_source_pages_http(client, followup_urls[:OFFICIAL_FOLLOWUP_LIMIT], kind))
            except Exception:
                followup_pages = []
            followup_pages.extend(await fetch_source_pages_with_browser(followup_urls[:OFFICIAL_FOLLOWUP_LIMIT], kind))
            seen_urls = {page["url"] for page in pages}
            for page in followup_pages:
                if page["url"] not in seen_urls:
                    pages.append(page)
                    seen_urls.add(page["url"])

    if not pages:
        return SourceFetchResult(
            ok=False,
            source_url=normalized_url,
            status="fetch_failed",
            error="Не удалось получить текст страницы закупки",
        )

    text = "\n\n".join(f"--- {page['url']} ---\n{page['text']}" for page in pages)
    block = build_source_context_block(kind=kind, url=normalized_url, text=text)
    return SourceFetchResult(
        ok=True,
        context=block,
        source_url=normalized_url,
        status="ok",
        extracted_chars=len(block),
    )


def fetch_source_context_sync(kind: str, url: str) -> SourceFetchResult:
    return asyncio.run(fetch_source_context(kind, url))


def candidate_source_urls(url: str, kind: str) -> list[str]:
    urls = [url]
    if kind != SOURCE_KIND_OFFICIAL:
        return urls

    parsed = urlparse(url)
    if "common-info.html" in url:
        urls.append(url.replace("common-info.html", "lot-list.html"))
        urls.append(url.replace("common-info.html", "documents.html"))
    query = parse_qs(parsed.query)
    reg_number = official_notice_number_from_url(url) or (query.get("regNumber") or [""])[0]
    if reg_number and reg_number.isdigit():
        urls.extend(
            [
                f"https://zakupki.gov.ru/epz/order/notice/printForm/view.html?regNumber={reg_number}",
                f"https://zakupki.gov.ru/epz/order/notice/printForm/listModal.html?regNumber={reg_number}",
            ]
        )
        current_notice_kind = ""
        match = re.search(r"/notice/([^/]+)/view/", parsed.path)
        if match:
            current_notice_kind = match.group(1)
        notice_kinds = [current_notice_kind, "ea44", "ea20", "zk20"]
        for notice_kind in list(dict.fromkeys(item for item in notice_kinds if item)):
            base = f"https://zakupki.gov.ru/epz/order/notice/{notice_kind}/view"
            urls.extend(
                [
                    f"{base}/common-info.html?regNumber={reg_number}",
                    f"{base}/lot-list.html?regNumber={reg_number}",
                    f"{base}/documents.html?regNumber={reg_number}",
                ]
            )
    return list(dict.fromkeys(urls))


def official_followup_urls_from_pages(pages: list[dict]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for page in pages:
        text = str(page.get("text") if isinstance(page, dict) else "")
        for raw_url in extract_source_urls(text):
            if not _is_official_followup_url(raw_url) or raw_url in seen:
                continue
            seen.add(raw_url)
            result.append(raw_url)
    return result


def _is_official_followup_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    if host != "zakupki.gov.ru" and not host.endswith(".zakupki.gov.ru"):
        return False
    path = parsed.path.lower()
    if "/epz/organization/view/info.html" in path:
        return True
    if "/epz/order/notice/printform/view.html" in path and "entityid=" in parsed.query.lower():
        return True
    return False


async def fetch_source_page(client: httpx.AsyncClient, url: str, kind: str = "") -> dict | None:
    try:
        current_url = url
        response = None
        for _ in range(MAX_SOURCE_REDIRECTS + 1):
            if not await asyncio.to_thread(source_url_is_public, current_url):
                return None
            response = await client.get(current_url, follow_redirects=False)
            if response.is_redirect:
                location = response.headers.get("location", "")
                current_url = urljoin(str(response.url), location)
                if not normalize_source_url(current_url):
                    return None
                continue
            break
        if response is None or response.is_redirect:
            return None
        if response.status_code >= 400:
            return None
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type and not response.text:
            return None
        return html_text_to_source_page(response.text[:500000], str(response.url), kind=kind)
    except Exception:
        return None


async def fetch_source_pages_http(client: httpx.AsyncClient, urls: list[str], kind: str = "") -> list[dict]:
    semaphore = asyncio.Semaphore(4)

    async def load_url(url: str) -> dict | None:
        async with semaphore:
            return await fetch_source_page(client, url, kind)

    loaded = await asyncio.gather(*(load_url(url) for url in urls), return_exceptions=True)
    return [item for item in loaded if isinstance(item, dict)]


async def fetch_source_page_with_browser(url: str, kind: str = "") -> dict | None:
    pages = await fetch_source_pages_with_browser([url], kind)
    return pages[0] if pages else None


async def fetch_source_pages_with_browser(urls: list[str], kind: str = "") -> list[dict]:
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        return []
    result: list[dict] = []
    try:
        async with async_playwright() as playwright:
            launch_options = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"],
            }
            proxy = _browser_proxy_config()
            if proxy:
                launch_options["proxy"] = proxy
            browser = await playwright.chromium.launch(**launch_options)
            try:
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="ru-RU",
                    viewport={"width": 1920, "height": 1080},
                    ignore_https_errors=True,
                )
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
                semaphore = asyncio.Semaphore(2)

                async def load_url(url: str) -> dict | None:
                    async with semaphore:
                        return await _fetch_source_page_in_context(context, url, kind)

                loaded = await asyncio.gather(*(load_url(url) for url in urls), return_exceptions=True)
                for item in loaded:
                    if isinstance(item, dict):
                        result.append(item)
                await context.close()
            finally:
                await browser.close()
    except Exception:
        return []
    return result


async def _fetch_source_page_in_context(context, url: str, kind: str = "") -> dict | None:
    page = await context.new_page()
    try:
        async def guard_public_network(route) -> None:
            request_url = str(route.request.url or "")
            parsed = urlparse(request_url)
            if parsed.scheme not in {"http", "https"}:
                await route.continue_()
                return
            if await asyncio.to_thread(source_url_is_public, request_url):
                await route.continue_()
            else:
                await route.abort("blockedbyclient")

        await page.route("**/*", guard_public_network)
        if not await asyncio.to_thread(source_url_is_public, url):
            return None
        timeout = 18000 if kind == SOURCE_KIND_OFFICIAL else 15000
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        if not await asyncio.to_thread(source_url_is_public, page.url):
            return None
        await page.wait_for_timeout(1800 if kind == SOURCE_KIND_OFFICIAL else 1200)
        html_text = await page.content()
        return html_text_to_source_page(html_text[:500000], page.url, kind=kind)
    except Exception:
        return None
    finally:
        await page.close()


def _browser_proxy_config() -> dict | None:
    proxy_url = (os.getenv("AIPOISK_PROXY_URL") or os.getenv("PROXY_URL") or "").strip()
    if not proxy_url:
        return None
    if "127.0.0.1" in proxy_url or "localhost" in proxy_url:
        try:
            parsed = urlparse(proxy_url)
            if not parsed.hostname or not parsed.port:
                return None
            with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
                pass
        except OSError:
            return None
    return {"server": proxy_url}


def html_text_to_source_page(html_text: str, url: str, *, kind: str = "") -> dict | None:
    soup = BeautifulSoup(str(html_text or ""), "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "footer", "nav"]):
        tag.decompose()
    for element in soup.find_all(["input", "textarea"]):
        value = str(element.get("value") or "").strip()
        if value and element.name == "input" and str(element.get("type") or "").lower() != "hidden":
            element.insert_after(f" {value} ")
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if href:
            anchor.append(f" {urljoin(url, href)}")
    text = unescape(soup.get_text("\n", strip=True))
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not _is_useful_source_text(text, kind):
        return None
    return {"url": url, "text": text[:120000]}


def _is_useful_source_text(text: str, kind: str = "") -> bool:
    value = str(text or "")
    if kind == SOURCE_KIND_OFFICIAL:
        if len(value) < 200:
            return False
        blocked_markers = ("Доступ ограничен", "Access Denied", "DDoS-Guard")
        if any(marker in value for marker in blocked_markers):
            return False
        useful_markers = (
            "Закупка",
            "Объект закупки",
            "Заказчик",
            "НМЦК",
            "Начальная",
            "Цена",
            "44-ФЗ",
            "223-ФЗ",
            "Срок",
            "Дата",
            "Извещение",
        )
        return any(marker in value for marker in useful_markers)
    return len(value) >= 80
