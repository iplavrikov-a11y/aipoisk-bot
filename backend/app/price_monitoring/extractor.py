from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from ..ai import call_llm, parse_json_object
from ..models import SystemSettings
from .models import SupplierQuote

logger = logging.getLogger(__name__)

# Сайты, которые не содержат коммерческих цен или являются соцсетями/видео
BLOCKED_DOMAINS = {
    "youtube.com", "vk.com", "ok.ru", "dzen.ru", "wikipedia.org", "gosuslugi.ru",
    "zakupki.gov.ru", "consultant.ru", "garant.ru", "nalog.gov.ru", "tass.ru", "ria.ru"
}


def is_valid_domain(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain not in BLOCKED_DOMAINS
    except Exception:
        return False


async def fetch_page_content(client: httpx.AsyncClient, url: str) -> Optional[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        resp = await client.get(url, headers=headers, timeout=8.0)
        if resp.status_code != 200 or not resp.text:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
            tag.decompose()
        text = " ".join(soup.stripped_strings)
        return text[:4000] if text else None
    except Exception:
        return None


async def extract_supplier_quote(
    settings: SystemSettings,
    target_item_name: str,
    target_unit: str,
    url: str,
    page_text: str,
) -> Optional[SupplierQuote]:
    """Анализирует текст страницы и извлекает цену, название поставщика, ИНН и контакты."""
    domain = urlparse(url).netloc

    prompt = f'''Ты эксперт по закупкам и мониторингу цен. Проанализируй текст веб-страницы поставщика.
Искомый товар: "{target_item_name}" (единица измерения: {target_unit})
URL страницы: {url}

Текст страницы:
{page_text}

КРИТИЧЕСКИЕ ПРАВИЛА:
1. РЕЛЕВАНТНОСТЬ: Убедись, что на странице продается именно этот товар или его прямой точный аналог/марка (например, если ищем подшипник — это должен быть подшипник, если электрод — электрод, если деталь крана — деталь крана). Если на странице совсем другой товар (например, лекарство, косметика, статья или новость) — ответь is_price_found: false, price_rub: null.
2. ЦЕНА: Ищи РЕАЛЬНУЮ числовую цену в рублях. Если цена указана "по запросу", "уточняйте цену", 0 руб или "нет в наличии" — ответь is_price_found: false, price_rub: null.
3. ПОСТАВЩИК: Укажи краткое официальное наименование компании/интернет-магазина (например, "ВсеИнструменты.ру", "ООО Металлсервис", "ЭТМ", "ПромСнаб").
4. ИНН: Укажи ИНН организации (10 или 12 цифр), если он указан в тексте, на странице или в реквизитах. Если нет — null.
5. КОНТАКТЫ: Телефон, email или город компании.

Ответь СТРОГО JSON-объектом:
{{
  "is_relevant": true,
  "is_price_found": true,
  "company_name": "ООО Металлсервис",
  "inn": "7701234567",
  "contacts": "+7 (495) 123-45-67, info@site.ru",
  "price_rub": 4500.0,
  "unit": "{target_unit}"
}}
'''
    try:
        raw_response = await call_llm(settings, prompt, tier="light")
        parsed = parse_json_object(raw_response)
        if not parsed or not isinstance(parsed, dict):
            return None

        if not parsed.get("is_relevant") or not parsed.get("is_price_found"):
            return None

        price = parsed.get("price_rub")
        if price is None:
            return None
        price_val = float(price)
        if price_val <= 0 or price_val > 500_000_000:
            return None

        comp_name = str(parsed.get("company_name") or "").strip() or domain
        inn = str(parsed.get("inn") or "").strip() or None
        if inn and not re.match(r'^\d{10,12}$', inn):
            inn = None
        contacts = str(parsed.get("contacts") or "").strip() or None

        return SupplierQuote(
            company_name=comp_name,
            inn=inn,
            contacts=contacts,
            price_rub=round(price_val, 2),
            unit=str(parsed.get("unit") or target_unit).strip(),
            url=url,
            is_price_found=True,
        )
    except Exception as exc:
        logger.debug("Quote extraction failed for %s: %s", url, exc)
        return None
