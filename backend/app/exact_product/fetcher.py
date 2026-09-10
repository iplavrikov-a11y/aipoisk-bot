from __future__ import annotations

import asyncio
import logging
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from ..supplier_search import candidate_domain_resolves_fast

logger = logging.getLogger(__name__)


def _get_candidate_domain_resolves_fast():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "candidate_domain_resolves_fast"):
        return getattr(mod, "candidate_domain_resolves_fast")
    return candidate_domain_resolves_fast


def _get_fetch_web_or_pdf_document():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "fetch_web_or_pdf_document"):
        return getattr(mod, "fetch_web_or_pdf_document")
    return fetch_web_or_pdf_document

# Excluded domains: marketplaces, general retail, price aggregators
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
    "tiu.ru",
    "pulscen.ru",
]


async def _fetch_with_browser_fallback(url: str, domain: str) -> Optional[Dict[str, Any]]:
    """
    Fallback-загрузчик через Playwright Chromium для обхода защит (KillBot, Cloudflare, DDoS-Guard)
    и рендеринга SPA/динамических таблиц характеристик.
    """
    try:
        from ..procurement_sources import fetch_source_page_with_browser
        browser_page = await asyncio.wait_for(fetch_source_page_with_browser(url), timeout=18.0)
        if browser_page and browser_page.get("text"):
            text = str(browser_page["text"]).strip()
            if len(text) > 50:
                title = f"Официальный каталог / Спецификация ({domain})"
                return {
                    "url": url,
                    "domain": domain,
                    "type": "html_browser",
                    "title": title,
                    "text": text[:25000],
                    "pdf_links": [],
                }
    except Exception as b_exc:
        logger.debug("procurement_sources_fallback_failed for %s: %s", url, b_exc)

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                locale="ru-RU",
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(1500)
            content = await page.content()
            title = await page.title()
            await browser.close()

            if content:
                soup = BeautifulSoup(content, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                    tag.decompose()
                body_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
                if len(body_text) > 50:
                    return {
                        "url": url,
                        "domain": domain,
                        "type": "html_browser",
                        "title": title[:120],
                        "text": body_text[:25000],
                        "pdf_links": [],
                    }
    except Exception as exc:
        logger.debug("browser_fallback_failed: %s (%s)", url, exc)
    return None


def extract_pdf_links_from_html(html_text: str, base_url: str = "") -> list[str]:
    """Извлекает ссылки на технические PDF-паспорта и каталоги из HTML."""
    if not html_text:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    pdf_links: list[str] = []
    pdf_kw = ("паспорт", "passport", "инструкция", "руководство", "manual", "datasheet", "описание", "скачать", "каталог")
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        text_desc = str(a.get_text(" ", strip=True) or "").lower()
        href_lower = href.lower()
        if ".pdf" in href_lower or any(kw in text_desc for kw in pdf_kw):
            full_pdf_url = urljoin(base_url, href) if base_url else href
            if full_pdf_url.lower().endswith(".pdf") or ".pdf?" in full_pdf_url.lower():
                if full_pdf_url not in pdf_links and len(pdf_links) < 6:
                    pdf_links.append(full_pdf_url)
    return pdf_links


async def fetch_web_or_pdf_document(
    client: httpx.AsyncClient,
    url: str,
    timeout_seconds: float = 12.0,
) -> Optional[Dict[str, Any]]:
    """
    Скачивает веб-страницу или PDF-паспорт изделия.
    Для PDF извлекает структурированные таблицы параметров через PyMuPDF (fitz).
    Для HTML выявляет ссылки на PDF-паспорта и каталоги.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None

    domain = urlsplit(url).netloc.lower()
    if any(bad in domain for bad in EXCLUDED_DOMAINS):
        return None

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        response = await client.get(url, headers=headers, timeout=timeout_seconds, follow_redirects=True)
        if response.status_code in (403, 503, 429):
            return await _fetch_with_browser_fallback(url, domain)
        if response.status_code >= 400:
            return None

        ctype = (response.headers.get("content-type") or "").lower()
        url_lower = str(response.url).lower()
        is_pdf = "application/pdf" in ctype or url_lower.endswith(".pdf") or response.content.startswith(b"%PDF-")

        if is_pdf:
            pdf_bytes = response.content
            if len(pdf_bytes) > 20 * 1024 * 1024:
                pdf_bytes = pdf_bytes[: 20 * 1024 * 1024]

            from ..document_parser import extract_smart_pdf_content
            pdf_text = extract_smart_pdf_content(
                pdf_bytes,
                max_pages_to_extract=14,
                max_chars=60000,
                table_tag_label="ТАБЛИЦА ТЕХНИЧЕСКИХ ХАРАКТЕРИСТИК",
            )

            if len(pdf_text.strip()) > 50:
                doc_name = response.url.path.split("/")[-1] or "Паспорт изделия (PDF)"
                return {
                    "url": str(response.url),
                    "domain": domain,
                    "type": "pdf",
                    "title": f"Паспорт / Техническая документация: {doc_name}",
                    "text": pdf_text[:60000],
                }

        # HTML-страница
        html_text = response.text or ""
        soup = BeautifulSoup(html_text, "html.parser")

        # Поиск ссылок на технические PDF-паспорта и инструкции завода
        pdf_links = extract_pdf_links_from_html(html_text, str(response.url))

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()

        # Поиск таблиц характеристик в HTML
        spec_tables = []
        for tbl in soup.find_all("table")[:8]:
            rows = tbl.find_all("tr")
            if len(rows) >= 2:
                tbl_lines = []
                for tr in rows:
                    cols = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
                    if any(cols):
                        tbl_lines.append(" | ".join(cols))
                if tbl_lines:
                    spec_tables.append("\n".join(tbl_lines))

        # Списки параметров <dl><dt><dd>
        for dl in soup.find_all("dl")[:8]:
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            if dts and dds:
                dl_lines = []
                for dt, dd in zip(dts, dds):
                    t_k = dt.get_text(" ", strip=True)
                    t_v = dd.get_text(" ", strip=True)
                    if t_k and t_v:
                        dl_lines.append(f"{t_k}: {t_v}")
                if dl_lines:
                    spec_tables.append("\n".join(dl_lines))

        # Блоки свойств div.property, div.param, div.spec
        prop_blocks = soup.find_all(["div", "li"], class_=re.compile(r"(?i)(prop|spec|param|charact|feature|tab-pane)"))
        if prop_blocks:
            div_lines = []
            for pb in prop_blocks[:35]:
                pb_text = pb.get_text(" ", strip=True)
                if pb_text and (":" in pb_text or " - " in pb_text or "|" in pb_text) and len(pb_text) < 160:
                    div_lines.append(pb_text)
            if div_lines:
                spec_tables.append("\n".join(div_lines))

        body_text = soup.get_text(" ", strip=True)
        body_text = re.sub(r"\s+", " ", body_text).strip()

        combined_text = ""
        if spec_tables:
            combined_text += "\n[ТАБЛИЦА ТЕХНИЧЕСКИХ ХАРАКТЕРИСТИК ИЗ ДОКУМЕНТА]:\n" + "\n\n".join(spec_tables) + "\n\n"
        combined_text += body_text

        if len(combined_text) > 40:
            page_title = soup.title.get_text(strip=True) if soup.title else f"Каталог {domain}"
            return {
                "url": str(response.url),
                "domain": domain,
                "type": "html",
                "title": page_title[:120],
                "text": combined_text[:25000],
                "pdf_links": pdf_links,
            }

    except Exception as exc:
        logger.debug("fetch_doc_failed for %s: %s", url, exc)

    return None


async def fetch_batch_web_documents(
    urls: List[str],
    max_docs: int = 6,
    max_concurrency: int = 4,
) -> List[Dict[str, Any]]:
    """
    Параллельное скачивание документов с краулингом PDF-паспортов, найденных по ссылкам.
    """
    if not urls:
        return []

    # Фильтрация исключенных доменов
    valid_urls = []
    for u in urls:
        if not u or not isinstance(u, str):
            continue
        try:
            dom = urlsplit(u).netloc.lower()
            if not any(bad in dom for bad in EXCLUDED_DOMAINS):
                valid_urls.append(u)
        except Exception:
            pass

    if valid_urls:
        dns_fn = _get_candidate_domain_resolves_fast()
        dns_checks = await asyncio.gather(
            *[dns_fn(urlsplit(u).netloc) for u in valid_urls],
            return_exceptions=True,
        )
        valid_urls = [u for u, ok in zip(valid_urls, dns_checks) if ok is True]

    target_urls = valid_urls[: max_docs * 2]
    sem = asyncio.Semaphore(max_concurrency)
    results: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=14.0, follow_redirects=True) as client:
        fetch_fn = _get_fetch_web_or_pdf_document()

        async def _fetch_one(target_url: str):
            async with sem:
                return await fetch_fn(client, target_url)

        tasks = [_fetch_one(u) for u in target_urls]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)

        found_pdf_links: list[str] = []
        seen_urls = set(target_urls)

        for res in fetched:
            if isinstance(res, dict) and res.get("text"):
                results.append(res)
                for pl in (res.get("pdf_links") or []):
                    if pl and pl not in seen_urls and pl not in found_pdf_links:
                        found_pdf_links.append(pl)
                        seen_urls.add(pl)
                if len(results) >= max_docs:
                    break

        # Добор обнаруженных PDF-паспортов
        if found_pdf_links and len(results) < max_docs:
            needed = max_docs - len(results)
            pdf_tasks = [_fetch_one(pu) for pu in found_pdf_links[:needed]]
            pdf_res = await asyncio.gather(*pdf_tasks, return_exceptions=True)
            for pr in pdf_res:
                if isinstance(pr, dict) and pr.get("text"):
                    results.append(pr)

    return results[:max_docs]
