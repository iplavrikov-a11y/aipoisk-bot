from __future__ import annotations

import logging
import os
import re
from typing import Any
import httpx

logger = logging.getLogger(__name__)

_DADATA_CACHE: dict[str, dict[str, Any]] = {}
_MAX_CACHE_ENTRIES = 2000
_DADATA_API_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"


def _get_dadata_api_key() -> str:
    return (
        os.getenv("DADATA_API_KEY", "").strip()
        or os.getenv("DADATA_TOKEN", "").strip()
        or "ccd87470786a4729699c7e1078ef6b79967496dc"
    )


async def enrich_company_by_inn(inn: str, *, api_key: str | None = None) -> dict[str, Any]:
    """
    Enrich organization data by INN via DaData Suggestions API.
    Returns normalized company profile dictionary.
    """
    cleaned_inn = re.sub(r"\D+", "", str(inn or "")).strip()
    if not cleaned_inn or len(cleaned_inn) not in (10, 12):
        return {}

    if cleaned_inn in _DADATA_CACHE:
        return dict(_DADATA_CACHE[cleaned_inn])

    token = (api_key or _get_dadata_api_key()).strip()
    if not token:
        logger.warning("DaData API key not configured")
        return {}

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {token}",
        "User-Agent": "TenderLex-Enrichment/1.0",
    }
    payload = {"query": cleaned_inn, "count": 1}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_DADATA_API_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.warning("DaData API error HTTP %s: %s", resp.status_code, resp.text[:200])
                return {}

            data = resp.json()
            suggestions = data.get("suggestions", [])
            if not suggestions:
                return {}

            item = suggestions[0]
            d = item.get("data", {}) or {}

            # Parse names
            full_name = str(item.get("value") or "").strip()
            name_obj = d.get("name") or {}
            short_name = str(name_obj.get("short_with_opf") or name_obj.get("full_with_opf") or full_name).strip()

            # Parse status
            state_obj = d.get("state") or {}
            status = str(state_obj.get("status") or "ACTIVE").upper()

            # Parse address & region
            addr_obj = d.get("address") or {}
            addr_data = addr_obj.get("data") or {} if isinstance(addr_obj, dict) else {}
            legal_address = str(addr_obj.get("value") or "").strip() if isinstance(addr_obj, dict) else ""
            region_name = str(addr_data.get("region_with_type") or addr_data.get("region") or "").strip()
            city_name = str(addr_data.get("city_with_type") or addr_data.get("city") or "").strip()
            region = city_name if (city_name and city_name in {"г Москва", "г Санкт-Петербург", "г Севастополь"}) else (region_name or city_name)

            # Parse management
            mgmt_obj = d.get("management") or {}
            mgmt_name = str(mgmt_obj.get("name") or "").strip()
            mgmt_post = str(mgmt_obj.get("post") or "").strip()

            # Parse contacts if present
            phones_list = d.get("phones") or []
            emails_list = d.get("emails") or []
            sites_list = d.get("sites") or []

            phones = [str(p.get("value") if isinstance(p, dict) else p).strip() for p in phones_list if p]
            emails = [str(e.get("value") if isinstance(e, dict) else e).strip() for e in emails_list if e]
            sites = [str(s.get("value") if isinstance(s, dict) else s).strip() for s in sites_list if s]

            result = {
                "inn": cleaned_inn,
                "kpp": str(d.get("kpp") or "").strip(),
                "ogrn": str(d.get("ogrn") or "").strip(),
                "okpo": str(d.get("okpo") or "").strip(),
                "company_name": short_name or full_name,
                "full_name": full_name,
                "legal_address": legal_address,
                "region": region,
                "city": city_name,
                "management_name": mgmt_name,
                "management_post": mgmt_post,
                "status": status,
                "employee_count": d.get("employee_count"),
                "okved": str(d.get("okved") or "").strip(),
                "phones": [p for p in phones if p],
                "emails": [e for e in emails if e],
                "sites": [s for s in sites if s],
            }

            if len(_DADATA_CACHE) >= _MAX_CACHE_ENTRIES:
                _DADATA_CACHE.clear()
            _DADATA_CACHE[cleaned_inn] = result
            return dict(result)

    except Exception as exc:
        logger.warning("DaData request failed for INN %s: %s", cleaned_inn, exc)
        return {}
