from __future__ import annotations

import logging
import os
import re
from typing import Any
import httpx

logger = logging.getLogger(__name__)

_DADATA_FIND_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
_DADATA_SUGGEST_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"


def _get_dadata_api_key() -> str:
    key = os.getenv("DADATA_API_KEY", "").strip() or os.getenv("DADATA_TOKEN", "").strip()
    if not key:
        try:
            from dotenv import load_dotenv
            load_dotenv("/root/projects/tenderlex/.env")
            load_dotenv()
            key = os.getenv("DADATA_API_KEY", "").strip() or os.getenv("DADATA_TOKEN", "").strip()
        except Exception:
            pass
    return key


def _parse_dadata_suggestion(item: dict[str, Any]) -> dict[str, Any]:
    """Parse single DaData suggestion item into normalized dictionary."""
    if not item or not isinstance(item, dict):
        return {}

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

    # Parse OPF & filter non-commercial entities
    opf_obj = d.get("opf") or {}
    opf_type = str(opf_obj.get("type") or "").upper()
    opf_short = str(opf_obj.get("short") or "").strip().upper()

    non_comm_markers = (
        "МКОУ", "МБОУ", "ГБОУ", "МАОУ", "МБДОУ", "МКДОУ", "ГБДОУ",
        "МБУ", "ГБУ", "МКУ", "ФКУ", "ФКУЗ", "АДМИНИСТРАЦИЯ", "ОТДЕЛ ОБРАЗОВАНИЯ",
        "ШКОЛА", "ДЕТСКИЙ САД", "ПОЛИКЛИНИКА", "БОЛЬНИЦА"
    )
    is_non_commercial = (
        opf_short in non_comm_markers
        or any(m in full_name.upper() for m in non_comm_markers)
    )

    inn_val = str(d.get("inn") or "").strip()
    return {
        "inn": inn_val,
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
        "opf_short": opf_short,
        "opf_type": opf_type,
        "is_non_commercial": is_non_commercial,
        "phones": [p for p in phones if p],
        "emails": [e for e in emails if e],
        "sites": [s for s in sites if s],
    }


async def enrich_company_by_inn(inn: str, *, api_key: str | None = None) -> dict[str, Any]:
    """
    Enrich organization data by INN via DaData Suggestions API.
    Always executed fresh in real-time without caching.
    Returns normalized company profile dictionary.
    """
    cleaned_inn = re.sub(r"\D+", "", str(inn or "")).strip()
    if not cleaned_inn or len(cleaned_inn) not in (10, 12):
        return {}

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
            resp = await client.post(_DADATA_FIND_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.warning("DaData API error HTTP %s: %s", resp.status_code, resp.text[:200])
                return {}

            data = resp.json()
            suggestions = data.get("suggestions", [])
            if not suggestions:
                return {}

            return _parse_dadata_suggestion(suggestions[0])

    except Exception as exc:
        logger.warning("DaData request failed for INN %s: %s", cleaned_inn, exc)
        return {}


async def suggest_company_by_query(query: str, *, count: int = 1, api_key: str | None = None) -> list[dict[str, Any]]:
    """
    Find company suggestions by name or keywords via DaData Suggest API.
    """
    cleaned_query = str(query or "").strip()
    if not cleaned_query or len(cleaned_query) < 3:
        return []

    token = (api_key or _get_dadata_api_key()).strip()
    if not token:
        return []

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {token}",
        "User-Agent": "TenderLex-Enrichment/1.0",
    }
    payload = {"query": cleaned_query, "count": max(1, count)}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_DADATA_SUGGEST_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                return []

            data = resp.json()
            suggestions = data.get("suggestions", [])
            results: list[dict[str, Any]] = []
            for item in suggestions:
                parsed = _parse_dadata_suggestion(item)
                if parsed and parsed.get("inn"):
                    results.append(parsed)
            return results
    except Exception as exc:
        logger.warning("DaData suggest failed for query %s: %s", cleaned_query, exc)
        return []


async def enrich_company_by_inn_or_query(
    inn: str | None = None,
    query: str | None = None,
    domain: str | None = None,
    city: str | None = None,
    *,
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Flexible enrichment with multi-tier waterfall resolution:
    1. Direct INN lookup (findById)
    2. Domain lookup via DaData Suggest (e.g. dealmed.ru, evroballon.ru, fortland.ru)
    3. Query + City lookup (e.g. "Атон Калуга", "Офисмаг Воронеж")
    4. Clean Query lookup (e.g. "Автопитер", "Деалмед")
    """
    # 1. Прямой поиск по ИНН
    if inn:
        cleaned_inn = re.sub(r"\D+", "", str(inn))
        if len(cleaned_inn) in (10, 12):
            res = await enrich_company_by_inn(cleaned_inn, api_key=api_key)
            if res and res.get("inn"):
                return res

    # 2. Поиск по чистому домену (многие компании зарегистрированы по сайту)
    if domain:
        clean_d = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        if clean_d.startswith("www."):
            clean_d = clean_d[4:]
        if "." in clean_d and len(clean_d) >= 4:
            sugs = await suggest_company_by_query(clean_d, count=3, api_key=api_key)
            stem = clean_d.split(".")[0]
            for s in sugs:
                if s.get("is_non_commercial"):
                    continue
                site_vals = [
                    st.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
                    for st in s.get("sites", [])
                ]
                if clean_d in site_vals or any(clean_d.endswith(st) or st.endswith(clean_d) for st in site_vals):
                    return s
                comp_clean = re.sub(r'[^a-zA-Zа-яА-Я0-9]', '', s.get("company_name", "")).lower()
                if len(stem) >= 4 and stem in comp_clean:
                    return s

    # 3. Поиск по связке: Название + Город/Регион
    if query and city:
        clean_q = re.sub(r'["«»]', '', query).strip()
        clean_c = re.sub(r'(г\.|город|\s)', '', city).strip()
        if len(clean_q) >= 3 and len(clean_c) >= 3:
            sugs = await suggest_company_by_query(f"{clean_q} {clean_c}", count=3, api_key=api_key)
            for s in sugs:
                if not s.get("is_non_commercial") and s.get("inn"):
                    return s

    # 4. Поиск по названию компании / бренда
    if query:
        clean_q = re.sub(r'["«»]', '', query).strip()
        if len(clean_q) >= 3:
            sugs = await suggest_company_by_query(clean_q, count=3, api_key=api_key)
            for s in sugs:
                if not s.get("is_non_commercial") and s.get("inn"):
                    return s

    return {}


