"""
TenderLex: Cookie & Anti-Bot Session Manager.
Manages domain cookies to bypass Cloudflare, WAF, and anti-bot blocks on retail/B2B sites
(etm.ru, chipdip.ru, vseinstrumenti.ru, rs24.ru, lemanapro.ru, ozon.ru, wildberries.ru, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote, urlparse

import httpx

logger = logging.getLogger(__name__)

COOKIES_FILE = Path("/root/projects/tenderlex/data/cookies.json")

# Catalog of known and recommended domains for procurement price monitoring
CATALOG_DOMAINS: List[Dict[str, str]] = [
    {
        "domain": "ozon.ru",
        "name": "Ozon (Маркетплейс)",
        "category": "Маркетплейсы",
        "description": "Электроника, инструмент, расходники, хозтовары, спецодежда",
        "test_url": "https://www.ozon.ru",
        "waf_type": "Cloudflare + Kasada",
    },
    {
        "domain": "wildberries.ru",
        "name": "Wildberries",
        "category": "Маркетплейсы",
        "description": "Спецодежда, бытовая химия, инструмент, расходные материалы",
        "test_url": "https://www.wildberries.ru",
        "waf_type": "WBAAS Token",
    },
    {
        "domain": "market.yandex.ru",
        "name": "Яндекс Маркет",
        "category": "Маркетплейсы",
        "description": "Широкий каталог потребительских и промышленных товаров",
        "test_url": "https://market.yandex.ru",
        "waf_type": "Yandex SmartCaptcha / skid",
    },
    {
        "domain": "avito.ru",
        "name": "Авито (Опт и B2B)",
        "category": "Маркетплейсы",
        "description": "Оборудование, стройматериалы, запчасти, металлопрокат",
        "test_url": "https://www.avito.ru",
        "waf_type": "PerimeterX / Qrator",
    },
    {
        "domain": "megamarket.ru",
        "name": "Мегамаркет",
        "category": "Маркетплейсы",
        "description": "Электроника, инструмент, стройтовары, бытовая техника",
        "test_url": "https://megamarket.ru",
        "waf_type": "Sber Security",
    },
    {
        "domain": "vseinstrumenti.ru",
        "name": "ВсеИнструменты.ру",
        "category": "Инструменты и стройка",
        "description": "Строительный инструмент, сантехника, метизы, климатика, силовая техника",
        "test_url": "https://www.vseinstrumenti.ru",
        "waf_type": "CSRF + Akamai",
    },
    {
        "domain": "lemanapro.ru",
        "name": "Лемана ПРО (Леруа Мерлен)",
        "category": "Инструменты и стройка",
        "description": "Строительные материалы, плитка, сантехника, кровля, изоляция, металл",
        "test_url": "https://lemanapro.ru",
        "waf_type": "Qrator + JWT Session",
    },
    {
        "domain": "petrovich.ru",
        "name": "СТД Петрович",
        "category": "Инструменты и стройка",
        "description": "Общестроительные материалы, сухие смеси, гипсокартон, цемент",
        "test_url": "https://petrovich.ru",
        "waf_type": "Cloudflare",
    },
    {
        "domain": "dns-shop.ru",
        "name": "ДНС Ритейл",
        "category": "Электроника и IT",
        "description": "Компьютеры, серверы, сетевое оборудование, оргтехника, ТВ",
        "test_url": "https://www.dns-shop.ru",
        "waf_type": "Service-sid + CSRF",
    },
    {
        "domain": "citilink.ru",
        "name": "Ситилинк",
        "category": "Электроника и IT",
        "description": "Серверы, ПК, мониторы, сетевые коммутаторы, кабели",
        "test_url": "https://www.citilink.ru",
        "waf_type": "Qrator / RateLimit",
    },
    {
        "domain": "chipdip.ru",
        "name": "Чип и Дип",
        "category": "Электроника и IT",
        "description": "Радиодетали, электронные компоненты, измерительные приборы, паяльники",
        "test_url": "https://www.chipdip.ru",
        "waf_type": ".ASPXAUTH + AntiBot",
    },
    {
        "domain": "etm.ru",
        "name": "ЭТМ (Электротехника)",
        "category": "Электротехника и Кабель",
        "description": "Кабель, провод, лотки, трансформаторы, щитовое оборудование, автоматика",
        "test_url": "https://www.etm.ru",
        "waf_type": "Qrator / BotProtect",
    },
    {
        "domain": "rs24.ru",
        "name": "Русский Свет",
        "category": "Электротехника и Кабель",
        "description": "Светотехника, опоры, кабели, электромонтажные изделия",
        "test_url": "https://rs24.ru",
        "waf_type": "Ngenix WAF + Challenge",
    },
    {
        "domain": "komus.ru",
        "name": "Комус",
        "category": "Расходные материалы",
        "description": "Бумага, канцтовары, упаковочные материалы, бытовая химия, спецодежда",
        "test_url": "https://www.komus.ru",
        "waf_type": "Qrator + domain_sid",
    },
    {
        "domain": "lunda.ru",
        "name": "Лунда (Инженерная сантехника)",
        "category": "Сантехника и Трубопроводы",
        "description": "Трубы, фитинги, шаровые краны, задвижки, насосы, теплоизоляция",
        "test_url": "https://lunda.ru",
        "waf_type": "Qrator / WAF",
    },
    {
        "domain": "tstn.ru",
        "name": "ТД Технониколь (ТСТН)",
        "category": "Инструменты и стройка",
        "description": "Кровля, утеплители XPS/минвата, гидроизоляция, праймеры, герметики",
        "test_url": "https://www.tstn.ru",
        "waf_type": "DDoS-Guard / Challenge",
    },
    {
        "domain": "stroylandiya.ru",
        "name": "Стройландия",
        "category": "Инструменты и стройка",
        "description": "Строительные и отделочные материалы, электротовары, крепеж",
        "test_url": "https://stroylandiya.ru",
        "waf_type": "AntiBot WAF",
    },
    {
        "domain": "santech.ru",
        "name": "Сантехкомплект",
        "category": "Сантехника и Трубопроводы",
        "description": "Трубопроводная арматура, фланцы, компенсаторы, отопительные приборы",
        "test_url": "https://www.santech.ru",
        "waf_type": "Standard Session",
    },
    {
        "domain": "mc.ru",
        "name": "Металлсервис",
        "category": "Металлопрокат и Метизы",
        "description": "Стальные трубы, сортовой прокат, арматура, балки, швеллеры",
        "test_url": "https://mc.ru",
        "waf_type": "Direct Session",
    },
    {
        "domain": "pulscen.ru",
        "name": "Пульс Цен (B2B)",
        "category": "B2B Порталы",
        "description": "Промышленный B2B каталог поставщиков и заводов РФ",
        "test_url": "https://pulscen.ru",
        "waf_type": "Standard WAF",
    },
]


def normalize_cookie_string(raw: Any) -> str:
    """
    Parses and cleans cookies from any format:
    - Raw Cookie HTTP header string: 'name=val; name2=val2'
    - JSON array of objects (from Cookie-Editor, DevTools): [{'name': '..', 'value': '..'}]
    - JSON object with 'cookies' array: {'cookies': [...]}
    - Tab-separated text from DevTools Application Cookies table
    Returns clean ASCII-safe 'name=val; name2=val2' string.
    """
    if raw is None:
        return ""

    # If dict with 'cookies' key
    if isinstance(raw, dict) and "cookies" in raw and isinstance(raw["cookies"], list):
        raw = raw["cookies"]

    # If list of dicts with 'name' and 'value'
    if isinstance(raw, list):
        pairs: list[str] = []
        for item in raw:
            if isinstance(item, dict) and "name" in item and "value" in item:
                k = str(item["name"]).strip()
                v = str(item["value"]).strip()
                # URL-encode non-ascii bytes
                v_encoded = quote(unquote(v), safe="!#$%&'()*+,-./:<=>?@[]^_`{|}~")
                pairs.append(f"{k}={v_encoded}")
        return "; ".join(pairs)

    raw_str = str(raw).strip()
    if not raw_str:
        return ""

    # Try parsing as JSON first
    if (raw_str.startswith("[") and raw_str.endswith("]")) or (raw_str.startswith("{") and raw_str.endswith("}")):
        try:
            parsed = json.loads(raw_str)
            return normalize_cookie_string(parsed)
        except Exception:
            pass

    # Check for tab-separated rows from DevTools Application tab
    if "\t" in raw_str:
        pairs = []
        for line in raw_str.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                k = parts[0].strip()
                v = parts[1].strip()
                if k and v:
                    v_encoded = quote(unquote(v), safe="!#$%&'()*+,-./:<=>?@[]^_`{|}~")
                    pairs.append(f"{k}={v_encoded}")
        if pairs:
            return "; ".join(pairs)

    # Standard semicolon-separated string
    cleaned_pairs: list[str] = []
    for item in raw_str.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k and v:
            # Ensure safe ASCII encoding for HTTP header
            try:
                v.encode("latin-1")
                cleaned_pairs.append(f"{k}={v}")
            except UnicodeEncodeError:
                v_encoded = quote(unquote(v), safe="!#$%&'()*+,-./:<=>?@[]^_`{|}~")
                cleaned_pairs.append(f"{k}={v_encoded}")

    return "; ".join(cleaned_pairs)


class CookieManager:
    """Manages custom cookies for target domains."""

    def __init__(self, cookies_path: Path = COOKIES_FILE) -> None:
        self.cookies_path = cookies_path
        self._cookies: Dict[str, str] = {}
        self.load_cookies()

    def load_cookies(self) -> None:
        if not self.cookies_path.exists():
            self._cookies = {}
            return
        try:
            with open(self.cookies_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._cookies = {k.lower().strip(): str(v).strip() for k, v in data.items()}
        except Exception as e:
            logger.warning("Failed to load cookies from %s: %s", self.cookies_path, e)
            self._cookies = {}

    def save_cookies(self) -> None:
        try:
            self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cookies_path, "w", encoding="utf-8") as f:
                json.dump(self._cookies, f, ensure_ascii=False, indent=2)
            logger.info("Saved %d domain cookies to %s", len(self._cookies), self.cookies_path)
        except Exception as e:
            logger.error("Failed to save cookies to %s: %s", self.cookies_path, e)

    def set_cookie(self, domain: str, raw_cookie: Any) -> str:
        clean_domain = domain.lower().strip()
        if clean_domain.startswith("www."):
            clean_domain = clean_domain[4:]
        normalized = normalize_cookie_string(raw_cookie)
        self._cookies[clean_domain] = normalized
        self.save_cookies()
        return normalized

    def delete_cookie(self, domain: str) -> bool:
        clean_domain = domain.lower().strip()
        if clean_domain.startswith("www."):
            clean_domain = clean_domain[4:]
        if clean_domain in self._cookies:
            del self._cookies[clean_domain]
            self.save_cookies()
            return True
        return False

    def get_cookie(self, domain: str) -> Optional[str]:
        clean_domain = domain.lower().strip()
        if clean_domain.startswith("www."):
            clean_domain = clean_domain[4:]
        return self._cookies.get(clean_domain)

    def get_cookie_for_url(self, url: str) -> Optional[str]:
        """Finds matching cookie for given URL based on domain suffix."""
        if not self._cookies:
            return None
        try:
            netloc = urlparse(url).netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            if netloc in self._cookies:
                return self._cookies[netloc]
            for d, cookie in self._cookies.items():
                if netloc == d or netloc.endswith("." + d):
                    return cookie
            return None
        except Exception:
            return None

    def list_domains(self) -> Dict[str, int]:
        """Returns dict of configured domains and their cookie string lengths."""
        return {d: len(c) for d, c in self._cookies.items()}

    def get_all_cookies(self) -> Dict[str, str]:
        return dict(self._cookies)

    def get_catalog_with_status(self) -> List[Dict[str, Any]]:
        """Returns the full catalog of domains, augmented with their active cookie status."""
        catalog_map = {item["domain"]: dict(item) for item in CATALOG_DOMAINS}
        
        # Add any user-configured domains that aren't in the default catalog
        for domain, cookie_str in self._cookies.items():
            if domain not in catalog_map:
                catalog_map[domain] = {
                    "domain": domain,
                    "name": domain.capitalize(),
                    "category": "Пользовательские площадки",
                    "description": f"Пользовательский домен для сбора цен ({domain})",
                    "test_url": f"https://www.{domain}",
                    "waf_type": "Custom",
                }

        result = []
        for domain, meta in catalog_map.items():
            cookie = self._cookies.get(domain)
            has_cookie = bool(cookie and len(cookie) > 0)
            cookie_len = len(cookie) if cookie else 0
            
            # Key cookies snippet preview (first 40 chars)
            preview = (cookie[:60] + "...") if cookie and len(cookie) > 60 else (cookie or "")
            
            meta_copy = dict(meta)
            meta_copy["has_cookie"] = has_cookie
            meta_copy["cookie_length"] = cookie_len
            meta_copy["cookie_preview"] = preview
            meta_copy["cookie_value"] = cookie or ""
            result.append(meta_copy)

        # Sort: first domains with active cookies, then by category
        result.sort(key=lambda x: (not x["has_cookie"], x["category"], x["name"]))
        return result

    async def test_domain(self, domain: str, custom_cookie: Optional[str] = None) -> Dict[str, Any]:
        """Performs a live network test request from the server to the target domain."""
        clean_domain = domain.lower().strip()
        if clean_domain.startswith("www."):
            clean_domain = clean_domain[4:]

        # Find test url from catalog, or fallback to standard https
        test_url = f"https://www.{clean_domain}"
        for item in CATALOG_DOMAINS:
            if item["domain"] == clean_domain:
                test_url = item["test_url"]
                break

        cookie = normalize_cookie_string(custom_cookie) if custom_cookie is not None else self.get_cookie(clean_domain)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        if cookie:
            headers["Cookie"] = cookie

        start_time = time.time()
        proxy_url = os.getenv("PRICE_MONITORING_PROXY") or os.getenv("HTTPS_PROXY")
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, proxy=proxy_url) as client:
                resp = await client.get(test_url, headers=headers)
                duration_ms = int((time.time() - start_time) * 1000)
                status_code = resp.status_code
                resp_size = len(resp.text)

                # Extract page title if available
                title = ""
                m_title = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
                if m_title:
                    title = re.sub(r"\s+", " ", m_title.group(1)).strip()[:80]

                # Determine accessibility
                is_ok = status_code in (200, 301, 302, 307)
                if status_code in (401, 403, 444, 503):
                    status_text = f"Блокировка WAF (HTTP {status_code})"
                elif status_code == 429:
                    status_text = "Превышен лимит запросов (Rate Limit 429)"
                elif is_ok:
                    status_text = f"Доступен (HTTP {status_code})"
                else:
                    status_text = f"HTTP {status_code}"

                return {
                    "domain": clean_domain,
                    "url": test_url,
                    "status_code": status_code,
                    "status_text": status_text,
                    "accessible": is_ok,
                    "response_size": resp_size,
                    "duration_ms": duration_ms,
                    "title": title,
                    "has_cookie_applied": bool(cookie),
                    "cookie_length": len(cookie) if cookie else 0,
                }
        except httpx.TimeoutException:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "domain": clean_domain,
                "url": test_url,
                "status_code": 504,
                "status_text": "Таймаут соединения (WAF drop / timeout)",
                "accessible": False,
                "response_size": 0,
                "duration_ms": duration_ms,
                "title": "",
                "has_cookie_applied": bool(cookie),
                "cookie_length": len(cookie) if cookie else 0,
            }
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "domain": clean_domain,
                "url": test_url,
                "status_code": 500,
                "status_text": f"Ошибка сети: {exc}",
                "accessible": False,
                "response_size": 0,
                "duration_ms": duration_ms,
                "title": "",
                "has_cookie_applied": bool(cookie),
                "cookie_length": len(cookie) if cookie else 0,
            }


# Global singleton
cookie_manager = CookieManager()
