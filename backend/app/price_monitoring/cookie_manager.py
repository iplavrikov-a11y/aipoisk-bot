"""
TenderLex: Cookie & Anti-Bot Session Manager.
Manages domain cookies to bypass Cloudflare, WAF, and anti-bot blocks on retail/B2B sites
(etm.ru, chipdip.ru, vseinstrumenti.ru, rs24.ru, lemanapro.ru, etc.).
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

COOKIES_FILE = Path("/root/projects/tenderlex/data/cookies.json")


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

    def set_cookie(self, domain: str, cookie_value: str) -> None:
        clean_domain = domain.lower().strip()
        if clean_domain.startswith("www."):
            clean_domain = clean_domain[4:]
        self._cookies[clean_domain] = cookie_value.strip()
        self.save_cookies()

    def get_cookie_for_url(self, url: str) -> Optional[str]:
        """Finds matching cookie for given URL based on domain suffix."""
        if not self._cookies:
            return None
        try:
            netloc = urlparse(url).netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            # Exact match
            if netloc in self._cookies:
                return self._cookies[netloc]
            # Suffix match (e.g. kaluga.lidergaz.ru -> lidergaz.ru)
            for d, cookie in self._cookies.items():
                if netloc == d or netloc.endswith("." + d):
                    return cookie
            return None
        except Exception:
            return None

    def list_domains(self) -> Dict[str, int]:
        """Returns dict of configured domains and their cookie string lengths."""
        return {d: len(c) for d, c in self._cookies.items()}


# Global singleton
cookie_manager = CookieManager()
