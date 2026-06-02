from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from .ai import call_llm, parse_json_object
from .models import SystemSettings

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+7|8)\s*[\(\- ]?\d{3}[\)\- ]?\s*\d{3}[\- ]?\d{2}[\- ]?\d{2}")
URL_RE = re.compile(r"https?://[^\s<>)\"']+", re.I)

BLOCKED_DOMAINS = {
    "2gis.ru",
    "allbiz.ru",
    "all-pribors.ru",
    "alibaba.com",
    "avito.ru",
    "b2b.house",
    "b2b-postavki.ru",
    "barahla.net",
    "bizorg.su",
    "consultant.ru",
    "clearspending.ru",
    "cntd.ru",
    "edufire37.ru",
    "dprom.online",
    "eb24.ru",
    "flagma.ru",
    "flowex-pipe.com",
    "fabricators.ru",
    "fireman.club",
    "gov.ru",
    "market.yandex.ru",
    "kontur.ru",
    "made-in-china.com",
    "mchs.gov.ru",
    "metaprom.ru",
    "optlist.ru",
    "orgs.biz",
    "otc.ru",
    "ozon.ru",
    "opt-union.ru",
    "poleznayamodel.ru",
    "prostanki.com",
    "pulscen.ru",
    "pandapipe.com",
    "profiminer.ru",
    "productcenter.ru",
    "qrrussia.ru",
    "rostender.info",
    "rts-tender.ru",
    "rusprofile.ru",
    "sbis.ru",
    "sovok.ru",
    "spravker.ru",
    "synapsenet.ru",
    "sino-fire.com",
    "monitoring-crm.ru",
    "supl.biz",
    "tek-all.ru",
    "tenderguru.ru",
    "tebiz.ru",
    "tiu.ru",
    "tradedir.ru",
    "tgko.ru",
    "wildberries.ru",
    "wiki-prom.ru",
    "vk.com",
    "vseinstrumenti.ru",
    "yandex.ru",
    "ya.ru",
    "zakupki.gov.ru",
    "b2b-center.ru",
    "bicotender.ru",
}

BLOCKED_HOST_SUFFIXES = (
    ".gov.ru",
    ".zakupki.gov.ru",
    ".consultant.ru",
    ".cntd.ru",
    ".wikipedia.org",
    ".ua",
    ".kz",
    ".by",
)


@dataclass(frozen=True)
class Candidate:
    url: str
    domain: str
    title: str = ""
    snippet: str = ""
    source: str = ""
    query: str = ""


@dataclass(frozen=True)
class CandidateMatch:
    accepted: bool
    level: str
    product: str
    reason: str
    matched_terms: tuple[str, ...] = ()


def base_domain(url_or_domain: str) -> str:
    value = str(url_or_domain or "").strip().lower()
    if "://" in value:
        value = urlparse(value).netloc
    value = value.removeprefix("www.").split(":")[0]
    parts = [part for part in value.split(".") if part]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return value


def is_blocked(url_or_domain: str) -> bool:
    host = hostname(url_or_domain)
    domain = base_domain(host)
    return (
        host in BLOCKED_DOMAINS
        or domain in BLOCKED_DOMAINS
        or any(host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES)
    )


def hostname(url_or_domain: str) -> str:
    value = str(url_or_domain or "").strip().lower()
    if "://" in value:
        value = urlparse(value).netloc
    return value.removeprefix("www.").split(":")[0]


def normalize_url(value: str) -> str:
    value = str(value or "").strip().rstrip(".,;])")
    if not value:
        return ""
    if value.startswith("//"):
        value = f"https:{value}"
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if is_blocked(parsed.netloc):
        return ""
    return value


async def build_supplier_queries(settings: SystemSettings, context: str, target: int) -> list[str]:
    fallback = _deterministic_queries(context)
    if not settings.has_active_ai_provider:
        return fallback
    prompt = f"""По тексту ТЗ сформируй 6-10 коротких поисковых запросов для поиска российских заводов, производителей, дилеров и B2B-поставщиков.
Не добавляй агрегаторы, маркетплейсы и тендерные площадки.
Ответ строго JSON:
{{"queries": ["..."]}}

ТЗ:
{context[:12000]}"""
    try:
        raw = await call_llm(
            settings,
            prompt,
            system_prompt="Ты закупочный исследователь. Формируешь только поисковые запросы.",
            tier="light",
            routing_key="supplier_query_generation",
            json_mode=True,
            timeout_seconds=75,
        )
        parsed = parse_json_object(raw)
        queries = [str(item).strip() for item in parsed.get("queries", []) if str(item).strip()]
        return list(dict.fromkeys([*fallback, *queries]))[:28] or fallback
    except Exception:
        return fallback


async def discover_suppliers(settings: SystemSettings, context: str, target: int) -> tuple[list[dict], dict]:
    queries = await build_supplier_queries(settings, context, target)
    candidates, search_meta = await discover_candidates(settings, queries, max_results=max(target * 10, 120))
    candidates = _rank_candidates(candidates, context)[: max(target * 5, 60)]
    accepted, reviewed, review_meta = await _review_candidates_until_target(settings, candidates, context, target)

    evidence = {
        "target": target,
        "search_provider": "multi",
        "search": search_meta,
        "review": review_meta,
        "candidate_source_counts": _source_counts(candidates),
        "accepted_source_counts": _source_counts(
            Candidate(
                url=str(item.get("site") or ""),
                domain=base_domain(str(item.get("site") or "")),
                source=str(item.get("source") or ""),
                query=str(item.get("search_query") or ""),
            )
            for item in accepted
        ),
        "queries": queries,
        "candidates": [candidate.__dict__ for candidate in candidates],
        "accepted_count": len(accepted),
        "accepted": accepted,
        "reviewed": reviewed,
    }
    return accepted[:target], evidence


async def _review_candidates_until_target(
    settings: SystemSettings,
    candidates: list[Candidate],
    context: str,
    target: int,
) -> tuple[list[dict], list[dict], dict]:
    reviewed: list[dict] = []
    batch_size = _candidate_review_batch_size(target)
    stopped_after = 0

    async def review(index: int, candidate: Candidate) -> dict | None:
        result = await verify_candidate(settings, candidate, context)
        if result:
            result["_source_rank"] = index
        return result

    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start : batch_start + batch_size]
        tasks = [
            asyncio.create_task(review(batch_start + offset, candidate))
            for offset, candidate in enumerate(batch)
        ]
        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                reviewed.append(result)
        await asyncio.gather(*tasks, return_exceptions=True)
        stopped_after = batch_start + len(batch)
        accepted = _accepted_supplier_results(reviewed, target)
        if len(accepted) >= target:
            return accepted, reviewed, {
                "batch_size": batch_size,
                "reviewed_count": len(reviewed),
                "candidate_count": len(candidates),
                "stopped_after_candidates": stopped_after,
                "early_stop": stopped_after < len(candidates),
            }

    return _accepted_supplier_results(reviewed, target), reviewed, {
        "batch_size": batch_size,
        "reviewed_count": len(reviewed),
        "candidate_count": len(candidates),
        "stopped_after_candidates": stopped_after,
        "early_stop": False,
    }


def _candidate_review_batch_size(target: int) -> int:
    return max(12, min(32, max(1, target) * 2))


def _accepted_supplier_results(reviewed: list[dict], target: int) -> list[dict]:
    accepted: list[dict] = []
    seen_domains: set[str] = set()
    seen_companies: set[str] = set()
    verified = [item for item in reviewed if item.get("evidence_status") == "verified"]
    for result in sorted(verified, key=_supplier_result_sort_key):
        domain = base_domain(result.get("site", ""))
        company_key = _normalize_company_key(result.get("company_name") or domain)
        if domain and domain not in seen_domains and company_key not in seen_companies:
            accepted.append(result)
            seen_domains.add(domain)
            if company_key:
                seen_companies.add(company_key)
        if len(accepted) >= target:
            break
    return accepted


async def discover_candidates(settings: SystemSettings, queries: list[str], max_results: int) -> tuple[list[Candidate], dict]:
    candidates: list[Candidate] = []
    reports: list[dict] = []
    provider_order = _provider_order(settings)

    for provider in provider_order:
        before = len(candidates)
        provider_candidates: list[Candidate] = []
        status = "skipped"
        error = ""
        try:
            existing_domains = {candidate.domain for candidate in candidates}
            if provider == "yandex":
                provider_candidates = await _search_with_yandex(settings, queries, max_results, existing_domains=existing_domains)
            elif provider == "google":
                provider_candidates = await _search_with_google(settings, queries, max_results, existing_domains=existing_domains)
            elif provider == "tavily":
                provider_candidates = await _search_with_tavily(settings, queries, max_results, existing_domains=existing_domains)
            elif provider == "ddgs":
                provider_candidates = await _search_with_ddgs(queries, max_results, existing_domains=existing_domains)
            status = "ok" if provider_candidates else "empty"
        except Exception as exc:
            status = "error"
            error = f"{type(exc).__name__}: {str(exc)[:180]}"
        candidates = _merge_candidates(candidates, provider_candidates, max_results=max_results)
        reports.append(
            {
                "provider": provider,
                "status": status,
                "added": len(candidates) - before,
                "returned": len(provider_candidates),
                "total_after": len(candidates),
                "error": error,
            }
        )
        if len(candidates) >= max_results:
            break

    return candidates[:max_results], {"provider_order": provider_order, "reports": reports}


def _provider_order(settings: SystemSettings) -> list[str]:
    configured = str(getattr(settings, "supplier_search_provider_order", "") or os.getenv("AIPOISK_SUPPLIER_SEARCH_PROVIDER_ORDER", ""))
    raw_items = [item.strip().lower() for item in configured.split(",") if item.strip()]
    supported = {"yandex", "google", "tavily", "ddgs"}
    order = [item for item in raw_items if item in supported]
    return list(dict.fromkeys(order)) or ["yandex", "google", "tavily", "ddgs"]


def _provider_query_limit(settings: SystemSettings, provider: str) -> int:
    specific = os.getenv(f"AIPOISK_{provider.upper()}_SEARCH_QUERY_LIMIT", "")
    configured = specific or os.getenv("AIPOISK_SEARCH_QUERY_LIMIT", "")
    try:
        return max(1, min(48, int(configured)))
    except ValueError:
        return 14 if provider == "google" else 18


def _merge_candidates(*groups: list[Candidate] | tuple[Candidate, ...], max_results: int) -> list[Candidate]:
    merged: list[Candidate] = []
    seen_domains: set[str] = set()
    for group in groups:
        for candidate in group:
            domain = base_domain(candidate.domain or candidate.url)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            merged.append(candidate)
            if len(merged) >= max_results:
                return merged
    return merged


def _source_counts(candidates: list[Candidate] | tuple[Candidate, ...] | object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        source = str(getattr(candidate, "source", "") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items()))


def _yandex_credentials(settings: SystemSettings) -> tuple[str, str]:
    folder_id = str(getattr(settings, "yandex_search_folder_id", "") or os.getenv("AIPOISK_YANDEX_SEARCH_FOLDER_ID", "") or os.getenv("YANDEX_FOLDER_ID", "")).strip()
    api_key = str(getattr(settings, "yandex_search_api_key", "") or os.getenv("AIPOISK_YANDEX_SEARCH_API_KEY", "") or os.getenv("YANDEX_API_KEY", "")).strip()
    return folder_id, api_key


async def _search_with_yandex(
    settings: SystemSettings,
    queries: list[str],
    max_results: int,
    *,
    existing_domains: set[str] | None = None,
) -> list[Candidate]:
    folder_id, api_key = _yandex_credentials(settings)
    if not folder_id or not api_key:
        return []
    search_queries = _expand_search_queries(queries, max_queries=_provider_query_limit(settings, "yandex"))
    semaphore = asyncio.Semaphore(3)

    async def search_one(client: httpx.AsyncClient, query: str) -> list[Candidate]:
        async with semaphore:
            headers = {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}
            body = {
                "query": {"searchType": "SEARCH_TYPE_RU", "queryText": query},
                "folderId": folder_id,
                "responseFormat": "FORMAT_XML",
                "groupBy": {"groupsOnPage": 10, "docsInGroup": 1},
            }
            response = await client.post("https://searchapi.api.cloud.yandex.net/v2/web/searchAsync", headers=headers, json=body)
            if response.status_code != 200:
                return []
            operation_id = str(response.json().get("id") or "")
            if not operation_id:
                return []
            for _ in range(24):
                await asyncio.sleep(0.75)
                operation = await client.get(f"https://operation.api.cloud.yandex.net/operations/{operation_id}", headers=headers)
                if operation.status_code != 200:
                    continue
                data = operation.json()
                if not data.get("done"):
                    continue
                raw_data = str(data.get("response", {}).get("rawData") or "")
                return _parse_yandex_xml(raw_data, query=query) if raw_data else []
            return []

    candidates: list[Candidate] = []
    seen = set(existing_domains or set())
    async with httpx.AsyncClient(timeout=35, follow_redirects=True) as client:
        tasks = [asyncio.create_task(search_one(client, query)) for query in search_queries]
        for task in asyncio.as_completed(tasks):
            for candidate in await task:
                if candidate.domain in seen:
                    continue
                seen.add(candidate.domain)
                candidates.append(candidate)
                if len(candidates) >= max_results:
                    for pending in tasks:
                        if not pending.done():
                            pending.cancel()
                    break
            if len(candidates) >= max_results:
                break
        await asyncio.gather(*tasks, return_exceptions=True)
    return candidates[:max_results]


def _parse_yandex_xml(xml_data: str, *, query: str) -> list[Candidate]:
    raw = str(xml_data or "").strip()
    if not raw:
        return []
    if not raw.startswith("<"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except Exception:
            pass
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    candidates: list[Candidate] = []
    for doc in root.findall(".//doc"):
        url_elem = doc.find("url")
        if url_elem is None or not url_elem.text:
            continue
        url = normalize_url(url_elem.text)
        domain = base_domain(url)
        if not url or not domain:
            continue
        title_elem = doc.find("title")
        title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""
        snippets: list[str] = []
        for passage in doc.findall(".//passage"):
            snippets.append("".join(passage.itertext()).strip())
        candidates.append(Candidate(url=url, domain=domain, title=title, snippet=" ".join(snippets), source="yandex", query=query))
    return candidates


def _google_credentials(settings: SystemSettings) -> tuple[str, str]:
    api_key = str(getattr(settings, "google_search_api_key", "") or os.getenv("AIPOISK_GOOGLE_SEARCH_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")).strip()
    cse_id = str(getattr(settings, "google_search_cse_id", "") or os.getenv("AIPOISK_GOOGLE_CSE_ID", "") or os.getenv("GOOGLE_CSE_ID", "")).strip()
    return api_key, cse_id


async def _search_with_google(
    settings: SystemSettings,
    queries: list[str],
    max_results: int,
    *,
    existing_domains: set[str] | None = None,
) -> list[Candidate]:
    api_key, cse_id = _google_credentials(settings)
    if not api_key or not cse_id:
        return []
    search_queries = _expand_search_queries(queries, max_queries=_provider_query_limit(settings, "google"))
    semaphore = asyncio.Semaphore(4)

    async def search_one(client: httpx.AsyncClient, query: str) -> list[Candidate]:
        async with semaphore:
            response = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": api_key,
                    "cx": cse_id,
                    "q": query,
                    "num": 10,
                    "gl": "ru",
                    "cr": "countryRU",
                    "lr": "lang_ru",
                    "safe": "off",
                },
            )
            if response.status_code != 200:
                return []
            return _parse_google_items(list(response.json().get("items", [])), query=query)

    candidates: list[Candidate] = []
    seen = set(existing_domains or set())
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        tasks = [asyncio.create_task(search_one(client, query)) for query in search_queries]
        for task in asyncio.as_completed(tasks):
            for candidate in await task:
                if candidate.domain in seen:
                    continue
                seen.add(candidate.domain)
                candidates.append(candidate)
                if len(candidates) >= max_results:
                    for pending in tasks:
                        if not pending.done():
                            pending.cancel()
                    break
            if len(candidates) >= max_results:
                break
        await asyncio.gather(*tasks, return_exceptions=True)
    return candidates[:max_results]


def _parse_google_items(items: list[dict], *, query: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    for item in items:
        url = normalize_url(str(item.get("link") or item.get("url") or ""))
        domain = base_domain(url)
        if not url or not domain:
            continue
        candidates.append(
            Candidate(
                url=url,
                domain=domain,
                title=str(item.get("title") or ""),
                snippet=str(item.get("snippet") or item.get("body") or ""),
                source="google",
                query=query,
            )
        )
    return candidates


async def _search_with_tavily(
    settings: SystemSettings,
    queries: list[str],
    max_results: int,
    *,
    existing_domains: set[str] | None = None,
) -> list[Candidate]:
    key_candidates = _tavily_key_candidates(settings)
    if not key_candidates:
        return []

    base_url = _tavily_base_url(settings)
    search_queries = _expand_search_queries(queries, max_queries=max(32, min(48, len(queries) * 3)))

    async with httpx.AsyncClient(timeout=28, follow_redirects=True) as client:
        candidates, followups = await _run_tavily_queries(
            client,
            base_url,
            key_candidates,
            search_queries,
            max_results,
            existing_domains=existing_domains,
        )
        if len(candidates) >= max_results:
            return candidates[:max_results]
        followup_queries = list(dict.fromkeys(followups))[:24]
        if followup_queries:
            extra_candidates, _ = await _run_tavily_queries(
                client,
                base_url,
                key_candidates,
                followup_queries,
                max_results,
                existing_domains={candidate.domain for candidate in candidates},
            )
            candidates.extend(extra_candidates)
    return candidates[:max_results]


async def _run_tavily_queries(
    client: httpx.AsyncClient,
    base_url: str,
    key_candidates: list[str],
    queries: list[str],
    max_results: int,
    *,
    existing_domains: set[str] | None = None,
) -> tuple[list[Candidate], list[str]]:
    semaphore = asyncio.Semaphore(6)

    async def search_one(query: str) -> tuple[str, list[dict]]:
        async with semaphore:
            for api_key in key_candidates:
                try:
                    response = await client.post(
                        f"{base_url}/search",
                        json={
                            "api_key": api_key,
                            "query": query,
                            "max_results": 10,
                            "search_depth": "advanced",
                            "include_raw_content": False,
                            "include_images": False,
                        },
                    )
                    if response.status_code in {401, 403}:
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return query, list(data.get("results", []))
                except Exception:
                    continue
        return query, []

    candidates: list[Candidate] = []
    followups: list[str] = []
    seen_domains: set[str] = set(existing_domains or set())
    tasks = [asyncio.create_task(search_one(query)) for query in queries]
    for task in asyncio.as_completed(tasks):
        query, items = await task
        for item in items:
            title = str(item.get("title") or "")
            snippet = str(item.get("content") or "")
            followups.extend(_lead_queries_from_result(title, snippet, query))
            url = normalize_url(str(item.get("url") or ""))
            domain = base_domain(url)
            if not url or not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            candidates.append(Candidate(url=url, domain=domain, title=title, snippet=snippet or query, source="tavily", query=query))
            if len(candidates) >= max_results:
                for pending in tasks:
                    if not pending.done():
                        pending.cancel()
                break
        if len(candidates) >= max_results:
            break
    await asyncio.gather(*tasks, return_exceptions=True)
    return candidates, followups


async def _search_with_ddgs(
    queries: list[str],
    max_results: int,
    *,
    existing_domains: set[str] | None = None,
) -> list[Candidate]:
    try:
        from ddgs import DDGS  # type: ignore
    except ImportError:
        return []

    search_queries = _ddgs_search_queries(queries)

    def search_all_sync() -> list[Candidate]:
        candidates: list[Candidate] = []
        seen_domains = set(existing_domains or set())
        with DDGS() as client:
            for query in search_queries:
                if len(candidates) >= max_results:
                    break
                try:
                    items = list(client.text(query, region="ru-ru", backend="auto", max_results=10))
                except Exception:
                    continue
                for item in items:
                    url = normalize_url(str(item.get("href") or item.get("url") or ""))
                    domain = base_domain(url)
                    if not url or not domain or domain in seen_domains:
                        continue
                    seen_domains.add(domain)
                    candidates.append(
                        Candidate(
                            url=url,
                            domain=domain,
                            title=str(item.get("title") or ""),
                            snippet=str(item.get("body") or item.get("description") or "") or query,
                            source="ddgs",
                            query=query,
                        )
                    )
                    if len(candidates) >= max_results:
                        break
        return candidates

    return await asyncio.to_thread(search_all_sync)


def _ddgs_search_queries(queries: list[str]) -> list[str]:
    preferred = [
        "СШУ-22 сверло шахтное поставщик",
        "сверло шахтное универсальное СШУ-22 купить",
        "горноспасательное оборудование завод поставщик купить",
        "горноспасательное оборудование поставщик официальный сайт",
        "пожарная арматура головка ГМ 70 купить поставщик",
        "головка муфтовая ГМ-70 пожарная купить поставщик",
        "соединительные головки пожарные рукава поставщик официальный сайт",
        "пожарные переходники рукава головки поставщик",
        "оборудование для пожарных рукавов купить поставщик",
        "пожарные рукава головки ГМ-70 купить",
        "противопожарное оборудование для шахт поставщик",
        "пожарное оборудование для шахт дилер",
    ]
    for query in queries:
        clean = re.sub(r"\s+", " ", str(query or "")).strip(" .,:;")
        if not clean or len(clean) > 110:
            continue
        if clean.startswith('"') and clean.count('"') >= 2 and len(clean) > 70:
            continue
        preferred.append(clean)
    return list(dict.fromkeys(preferred))[:28]


def _tavily_base_url(settings: SystemSettings) -> str:
    configured = str(settings.supplier_search_adapter_base_url or "").strip().rstrip("/")
    if "tavily.com" in configured:
        return configured
    return "https://api.tavily.com"


def _tavily_key_candidates(settings: SystemSettings) -> list[str]:
    keys: list[str] = []
    configured_base = str(settings.supplier_search_adapter_base_url or "").lower()
    configured_model = str(settings.supplier_search_adapter_model or "").lower()
    configured_key = str(settings.supplier_search_adapter_api_key or "").strip()
    if configured_key and ("tavily" in configured_base or configured_model == "tavily"):
        keys.append(configured_key)
    for name in ("AIPOISK_TAVILY_API_KEY", "TAVILY_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            keys.append(value)
    hermes_env = Path("/home/hermes/.hermes/.env")
    if hermes_env.exists():
        for line in hermes_env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("TAVILY_API_KEY="):
                keys.append(line.split("=", 1)[1].strip().strip('"').strip("'"))
                break
    return [key for key in dict.fromkeys(keys) if key]


def _expand_search_queries(queries: list[str], *, max_queries: int) -> list[str]:
    base_queries: list[str] = []
    secondary_variants: list[str] = []
    for query in queries:
        clean = re.sub(r"\s+", " ", str(query or "")).strip(" .,:;")
        if not clean:
            continue
        base_queries.append(clean)
        variants = [
            f"{clean} официальный сайт",
            f"{clean} контакты",
            f"{clean} каталог",
        ]
        if not re.search(r"производ|завод|изготов", clean, re.I):
            variants.append(f"{clean} производитель")
        if not re.search(r"купить|поставщик|цена", clean, re.I):
            variants.append(f"{clean} купить поставщик")
        if not re.search(r"дилер|дистриб", clean, re.I):
            variants.append(f"{clean} дилер дистрибьютор")
        for item in variants:
            secondary_variants.append(item)

    expanded: list[str] = []
    for item in [*base_queries, *secondary_variants]:
        if item not in expanded:
            expanded.append(item)
        if len(expanded) >= max_queries:
            return expanded
    return expanded


def _lead_queries_from_result(title: str, snippet: str, original_query: str) -> list[str]:
    text = f"{title} {snippet}"
    leads: list[str] = []
    for marker in ("|", "—", "–"):
        for part in title.split(marker)[1:]:
            value = re.sub(r"\s+", " ", part).strip(" .,:;")
            if _looks_like_company_fragment(value):
                leads.append(f"{value} официальный сайт контакты")
    for match in re.finditer(
        r"((?:ООО|АО|ЗАО|ПАО|НПО|НПП|ТД|ГК)\s+[«\"A-Za-zА-Яа-яЁё0-9][^.,;|]{2,80})",
        text,
        re.I,
    ):
        leads.append(f"{match.group(1).strip()} официальный сайт контакты")
    if "завод" in text.lower():
        words = re.findall(r"[А-Яа-яЁёA-Za-z0-9\-]{3,}", text)
        for index, word in enumerate(words):
            if word.lower().startswith("завод"):
                fragment = " ".join(words[max(0, index - 4) : min(len(words), index + 6)])
                if _looks_like_company_fragment(fragment):
                    leads.append(f"{fragment} официальный сайт контакты")
    product = re.sub(r"\s+", " ", original_query).strip()
    return [f"{lead} {product}" for lead in dict.fromkeys(leads) if lead][:4]


def _looks_like_company_fragment(value: str) -> bool:
    lowered = value.lower()
    return len(value) >= 8 and any(
        marker in lowered
        for marker in (
            "завод",
            "компания",
            "предприят",
            "производ",
            "снаб",
            "сервис",
            "тд ",
            "ооо",
            "ао ",
        )
    )


async def _search_with_adapter(settings: SystemSettings, queries: list[str], max_results: int) -> list[Candidate]:
    base_url = str(settings.supplier_search_adapter_base_url or "").strip().rstrip("/")
    api_key = str(settings.supplier_search_adapter_api_key or "").strip()
    model = str(settings.supplier_search_adapter_model or "").strip()
    if not base_url or not api_key:
        return []
    if not base_url.endswith("/chat/completions"):
        base_url = f"{base_url}/chat/completions"

    candidates: list[Candidate] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=35, follow_redirects=True) as client:
        for query in queries:
            payload = {
                "web_search": True,
                "messages": [
                    {
                        "role": "system",
                        "content": "Ищи официальные сайты российских производителей, заводов, дилеров и B2B-поставщиков. Не возвращай каталоги и маркетплейсы как финальный сайт.",
                    },
                    {
                        "role": "user",
                        "content": f"Найди до 10 официальных сайтов компаний по запросу: {query}. Верни URL и краткое описание.",
                    },
                ],
                "temperature": 0.1,
                "max_tokens": 1600,
            }
            if model:
                payload["model"] = model
            try:
                response = await client.post(base_url, headers={"Authorization": f"Bearer {api_key}"}, json=payload)
                response.raise_for_status()
                data = response.json()
            except Exception:
                continue
            content = json.dumps(data, ensure_ascii=False)
            for raw_url in URL_RE.findall(content):
                url = normalize_url(raw_url)
                domain = base_domain(url)
                if not url or not domain or domain in seen or is_blocked(domain):
                    continue
                seen.add(domain)
                candidates.append(Candidate(url=url, domain=domain, title="", snippet=query, source="adapter", query=query))
                if len(candidates) >= max_results:
                    return candidates
    return candidates


async def verify_candidate(settings: SystemSettings, candidate: Candidate, context: str) -> dict | None:
    pages = await collect_pages(candidate.url)
    if not pages:
        return None
    combined_text = "\n\n".join(page["text"] for page in pages)
    match = assess_candidate_match(candidate, context, pages)
    if not match.accepted:
        return {
            "company_name": candidate.domain,
            "site": candidate.url,
            "evidence_status": "weak",
            "source": candidate.source,
            "search_query": candidate.query,
            "comments": match.reason or "Страница открыта, но связь с ТЗ или профиль поставщика не подтверждены.",
        }
    emails = prioritize_emails(EMAIL_RE.findall(combined_text), candidate.domain)
    phones = sorted(set(PHONE_RE.findall(combined_text)))
    if not emails and not phones:
        return {
            "company_name": candidate.domain,
            "site": candidate.url,
            "evidence_status": "weak",
            "source": candidate.source,
            "search_query": candidate.query,
            "comments": "На открытых страницах сайта не найдены телефон или email.",
        }

    if match.level == "exact":
        decision = await ai_verify(settings, candidate, context, pages, emails, phones, match)
        if decision.get("action") != "accept":
            decision = keyword_verify(candidate, context, pages, emails, phones, match)
    else:
        decision = keyword_verify(candidate, context, pages, emails, phones, match)

    evidence_url = decision.get("evidence_url") or best_evidence_page_url(pages, match) or pages[0]["url"]
    contact_url = decision.get("contact_url") or contact_page_url(pages, emails, phones) or pages[0]["url"]
    site_url = evidence_url if match.level == "exact" else candidate.url
    return {
        "company_name": decision.get("company_name") or candidate.domain,
        "region": decision.get("region") or "",
        "status": decision.get("status") or "поставщик",
        "product": decision.get("product") or match.product,
        "contact_person": decision.get("contact_person") or "",
        "phone": decision.get("phone") or (phones[0] if phones else ""),
        "email": decision.get("email") or (emails[0] if emails else ""),
        "site": site_url,
        "evidence_url": evidence_url,
        "contact_url": contact_url,
        "comments": decision.get("comments") or match.reason or "Официальный сайт открыт, релевантность и контакты проверены.",
        "evidence_status": "verified",
        "match_level": match.level,
        "source": candidate.source,
        "search_query": candidate.query,
    }


async def collect_pages(url: str) -> list[dict]:
    pages: list[dict] = []
    async with httpx.AsyncClient(timeout=18, follow_redirects=True, headers={"User-Agent": "AI Poisk supplier verifier"}) as client:
        first = await fetch_page(client, url)
        if not first:
            return []
        pages.append(first)
        links = extract_internal_links(first["html"], first["url"])
        for link in links[:5]:
            page = await fetch_page(client, link)
            if page:
                pages.append(page)
            if len(pages) >= 6:
                break
    return pages


async def fetch_page(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        response = await client.get(url)
        ctype = response.headers.get("content-type", "")
        if response.status_code >= 400 or "text/html" not in ctype:
            return None
        html_text = response.text[:300000]
    except Exception:
        return None
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = unescape(soup.get_text("\n", strip=True))
    if len(text.strip()) < 80:
        return None
    return {"url": str(response.url), "html": html_text, "text": text[:80000]}


def extract_internal_links(html_text: str, base_url_value: str) -> list[str]:
    base = base_domain(base_url_value)
    soup = BeautifulSoup(html_text, "html.parser")
    scored: list[tuple[int, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url_value, str(anchor.get("href") or ""))
        parsed = urlparse(href)
        if base_domain(parsed.netloc) != base:
            continue
        label = f"{anchor.get_text(' ', strip=True)} {href}".lower()
        score = 0
        if any(word in label for word in ["контакт", "contact", "отдел", "sales"]):
            score += 4
        if any(word in label for word in ["каталог", "product", "produk", "товар", "оборуд"]):
            score += 3
        if any(word in label for word in ["о компании", "about", "производ", "завод"]):
            score += 2
        if score:
            scored.append((score, href))
    unique: list[str] = []
    for _, href in sorted(scored, reverse=True):
        if href not in unique:
            unique.append(href)
    return unique


async def ai_verify(
    settings: SystemSettings,
    candidate: Candidate,
    context: str,
    pages: list[dict],
    emails: list[str],
    phones: list[str],
    match: CandidateMatch,
) -> dict:
    if not settings.has_active_ai_provider:
        return keyword_verify(candidate, context, pages, emails, phones, match)
    payload = {
        "target_tz_excerpt": context[:6000],
        "candidate": candidate.__dict__,
        "local_match": {
            "level": match.level,
            "product": match.product,
            "reason": match.reason,
            "matched_terms": list(match.matched_terms),
        },
        "emails": emails,
        "phones": phones[:5],
        "pages": [{"url": page["url"], "text": page["text"][:2500]} for page in pages[:4]],
    }
    prompt = f"""Проверь поставщика для закупочного ТЗ.
Принимай официальный сайт компании, если:
- виден точный товар, аналогичная позиция, релевантная категория или профильная специализация поставщика;
- компания выглядит как завод, производитель, дилер, дистрибьютор или B2B-поставщик;
- контакт опубликован на открытой странице сайта. Email может быть на публичном домене, если он указан на сайте компании; телефон тоже считается контактом.

Не принимай маркетплейсы, агрегаторы, тендерные площадки, справочники, патенты, учебные/госстраницы и нерелевантные обычные сверла для дрелей.
Ответ строго JSON:
{{
  "action": "accept|reject",
  "company_name": "",
  "region": "",
  "status": "завод|дилер|дистрибьютор|поставщик",
  "product": "",
  "email": "",
  "phone": "",
  "evidence_url": "",
  "contact_url": "",
  "comments": ""
}}

Данные:
{json.dumps(payload, ensure_ascii=False)}"""
    try:
        raw = await call_llm(
            settings,
            prompt,
            system_prompt="Ты закупочный аудитор. Не выдумываешь компании и контакты, но не отбрасываешь реального профильного поставщика только из-за отсутствия точного артикула.",
            tier="primary",
            routing_key="supplier_candidate_verifier",
            json_mode=True,
            timeout_seconds=90,
        )
        return parse_json_object(raw)
    except Exception:
        return keyword_verify(candidate, context, pages, emails, phones, match)


def keyword_verify(
    candidate: Candidate,
    context: str,
    pages: list[dict],
    emails: list[str],
    phones: list[str],
    match: CandidateMatch | None = None,
) -> dict:
    match = match or assess_candidate_match(candidate, context, pages)
    if not match.accepted:
        return {"action": "reject", "comments": match.reason or "Недостаточно совпадений с ТЗ без AI-проверки."}
    context_words = set(important_terms(context))
    text = "\n".join(page["text"].lower() for page in pages)
    overlap = [word for word in context_words if word in text]
    name = extract_company_name(candidate, pages)
    return {
        "action": "accept",
        "company_name": name,
        "status": infer_supplier_status(text),
        "product": match.product or ", ".join(overlap[:8]),
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "evidence_url": pages[0]["url"],
        "contact_url": contact_page_url(pages, emails, phones) or pages[0]["url"],
        "comments": match.reason or "Проверка выполнена по официальной странице, профилю поставщика и контактам.",
    }


def email_matches_domain(email: str, domain: str) -> bool:
    email_domain = base_domain(email.split("@")[-1])
    return bool(email_domain and email_domain == base_domain(domain))


def prioritize_emails(values: list[str], domain: str) -> list[str]:
    unique = sorted({str(value or "").strip().lower() for value in values if str(value or "").strip()})
    return sorted(unique, key=lambda item: (not email_matches_domain(item, domain), item))


def contact_page_url(pages: list[dict], emails: list[str], phones: list[str]) -> str:
    email_set = {email.lower() for email in emails}
    for page in pages:
        text = page["text"].lower()
        if any(email in text for email in email_set):
            return page["url"]
        if any(phone and phone in page["text"] for phone in phones):
            return page["url"]
    return ""


def best_evidence_page_url(pages: list[dict], match: CandidateMatch) -> str:
    terms = [term.lower() for term in match.matched_terms if len(term) >= 4]
    if not terms:
        return ""
    for page in pages:
        text = page["text"].lower()
        if any(term in text for term in terms):
            return page["url"]
    return ""


def _normalize_company_key(value: str) -> str:
    cleaned = re.sub(r"\b(ооо|ао|зао|пао|нпо|нпп|тд|гк|ип)\b", " ", str(value or "").lower())
    cleaned = re.sub(r"[^a-zа-яё0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_company_name(candidate: Candidate, pages: list[dict]) -> str:
    generic_lines = {"компания", "о компании", "производство", "о производстве", "главная"}
    first_text = pages[0]["text"] if pages else ""
    for line in first_text.splitlines()[:20]:
        line = re.sub(r"\s+", " ", line).strip(" -|")
        if line.lower() in generic_lines:
            continue
        if 4 <= len(line) <= 120 and _looks_like_company_fragment(line):
            return line
    title = re.sub(r"\s+", " ", candidate.title).strip(" -|")
    if title:
        for separator in ("|", "—", "–", "-"):
            title = title.split(separator)[0].strip()
        title_lower = title.lower()
        if title_lower in generic_lines:
            return candidate.domain
        if any(word in title_lower for word in ("купить", "каталог", "рукав", "сверло", "головк", "оборудован", "переходник")):
            return candidate.domain
        if 4 <= len(title) <= 120:
            return title
    return candidate.domain


def infer_supplier_status(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("завод", "производитель", "производство", "изготовитель")):
        return "завод"
    if "дистриб" in lowered:
        return "дистрибьютор"
    if "дилер" in lowered:
        return "дилер"
    return "поставщик"


def _supplier_result_sort_key(item: dict) -> tuple[int, int]:
    priority = {"exact": 0, "adjacent": 1, "profile": 2}
    return (priority.get(str(item.get("match_level") or ""), 9), int(item.get("_source_rank") or 9999))


def _deterministic_queries(context: str) -> list[str]:
    product_phrases = _product_phrases(context)
    exact_codes = _exact_codes(context)
    queries: list[str] = []

    for phrase in product_phrases[:4]:
        queries.extend(
            [
                f'"{phrase}" поставщик',
                f'"{phrase}" купить',
                f'"{phrase}" производитель',
            ]
        )
    supplier_codes = [code for code in exact_codes if not re.fullmatch(r"ГМ-\d+", code)]
    for code in supplier_codes[:5]:
        queries.extend(
            [
                f'"{code}" поставщик официальный сайт',
                f'"{code}" купить цена',
            ]
        )

    lowered = context.lower()
    if "сверло шахтное" in lowered or "сшу" in lowered:
        queries.extend(
            [
                '"Сверло шахтное универсальное" поставщик',
                '"СШУ-22" "сверло шахтное"',
                '"СШУ-22" купить',
                '"сверло шахтное" "пожарных рукавов"',
            ]
        )
    if any(word in lowered for word in ("шахт", "горно", "горн")):
        queries.extend(
            [
                "горноспасательное оборудование поставщик официальный сайт",
                "горношахтное противопожарное оборудование поставщик",
                "средства безопасности угольных шахт поставщик",
                "оборудование ВГСЧ поставщик производитель",
                "горноспасательное оборудование завод поставщик купить",
            ]
        )
    if "пожар" in lowered:
        queries.extend(
            [
                "противопожарное оборудование для шахт поставщик",
                "пожарное оборудование для шахт дилер",
                "пожарные рукава трубопровод ГМ 70 поставщик",
                "соединительная арматура пожарных рукавов поставщик",
                "оборудование для обслуживания пожарных рукавов поставщик",
                "пожарные головки ГМ-70 поставщик",
                "переходники пожарных рукавов поставщик",
                "пожарные рукава головки ГМ-70 купить",
                "головка муфтовая ГМ-70 пожарная купить поставщик",
                "соединительные головки пожарные рукава поставщик официальный сайт",
                "пожарные переходники рукава головки поставщик",
                "оборудование для пожарных рукавов купить поставщик",
            ]
        )
    if any(word in lowered for word in ("трубопровод", "магистрал", "врезк")):
        queries.extend(
            [
                "оборудование для врезки в трубопровод поставщик",
                "приспособление для подсоединения пожарных рукавов к трубопроводу",
            ]
        )

    words = important_terms(context)
    keywords = []
    for word in words:
        value = word.strip("-").lower()
        if value not in keywords:
            keywords.append(value)
        if len(keywords) >= 8:
            break
    base = " ".join(keywords[:6]) or "промышленное оборудование"
    queries.extend(
        [
        f"{base} производитель официальный сайт",
        f"{base} завод контакты",
        f"{base} поставщик отдел продаж",
        ]
    )
    return list(dict.fromkeys(query for query in queries if query.strip()))[:32]


def _fallback_queries(context: str) -> list[str]:
    return _deterministic_queries(context)


def _product_phrases(context: str) -> list[str]:
    text = re.sub(r"\s+", " ", context)
    phrases: list[str] = []
    table_match = re.search(r"\b1\s*\|\s*([^|]{12,240})\|", text)
    if table_match:
        phrases.append(table_match.group(1).strip())
    for match in re.finditer(r"\(([^()]{8,120})\)", text):
        phrase = match.group(1).strip()
        if not re.search(r"ста|кг|см|мм|мпа|копировать|наружн|не более|рабоч|диам|дней|месяц", phrase, re.I):
            phrases.append(phrase)
    title_match = re.search(r"ТЕХНИЧЕСКОЕ ЗАДАНИЕ\s+(.{12,220}?)(?:Техническое задание|Условия поставки|===|$)", text, re.I)
    if title_match:
        title = title_match.group(1).strip(" -")
        title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
        phrases.append(title)
    cleaned: list[str] = []
    for phrase in phrases:
        phrase = re.sub(r"\s+", " ", phrase).strip(" .,:;")
        if 8 <= len(phrase) <= 220 and phrase.lower() not in [item.lower() for item in cleaned]:
            cleaned.append(phrase)
    return cleaned


def _exact_codes(context: str) -> list[str]:
    result: list[str] = []
    for match in re.finditer(r"\b[А-ЯЁA-Z]{2,}[-\s]?\d{1,4}\b", context):
        code = re.sub(r"\s+", "-", match.group(0).upper())
        if code not in result and not re.fullmatch(r"(?:TABLE|МПА|ГОСТ|ТУ)-?\d*", code):
            result.append(code)
    return result


def _rank_candidates(candidates: list[Candidate], context: str) -> list[Candidate]:
    return sorted(candidates, key=lambda item: _candidate_score(item, context), reverse=True)


def _candidate_score(candidate: Candidate, context: str) -> int:
    text = f"{candidate.url} {candidate.title} {candidate.snippet}".lower()
    score = 0
    exact_terms = _exact_match_terms(context)
    if any(term in text for term in exact_terms):
        score += 18
    category_hits = _category_hits(text)
    score += len(category_hits) * 3
    for term in important_terms(context)[:16]:
        if term in text:
            score += 3 if len(term) >= 8 else 2
    if any(word in text for word in ("производ", "завод", "изготов", "официаль")):
        score += 4
    if any(word in text for word in ("catalog", "product", "produkt", "товар", "каталог")):
        score += 2
    if any(word in text for word in ("контакт", "contact", "mail", "email")):
        score += 1
    return score


def assess_candidate_match(candidate: Candidate, context: str, pages: list[dict]) -> CandidateMatch:
    text = f"{candidate.title} {candidate.snippet}\n" + "\n".join(page["text"][:20000] for page in pages)
    front_text = f"{candidate.url} {candidate.title} {candidate.snippet}".lower()
    lowered = text.lower()
    if _looks_like_reference_or_non_supplier(candidate, lowered):
        return CandidateMatch(
            accepted=False,
            level="reject",
            product="",
            reason="Страница похожа на справочник, тендер, учебный/госресурс или нерелевантный источник, а не на сайт поставщика.",
        )

    commercial = _has_commercial_supplier_signal(lowered)
    exact_terms = _exact_match_terms(context)
    exact_matches = tuple(term for term in exact_terms if term in lowered)
    category_hits = _category_hits(lowered)
    front_category_hits = _category_hits(front_text)
    target_groups = _target_category_groups(context)
    product = _best_product_label(context, exact_matches)
    if not exact_matches and "сумк" in front_text:
        return CandidateMatch(
            accepted=False,
            level="reject",
            product="",
            reason="Найдена сумка/аксессуар, а не само приспособление или профильный поставщик оборудования.",
            matched_terms=tuple(sorted(category_hits)),
        )

    if exact_matches and commercial:
        return CandidateMatch(
            accepted=True,
            level="exact",
            product=product,
            reason="На сайте найдено прямое совпадение с товаром/кодом из ТЗ и опубликованы признаки поставщика.",
            matched_terms=exact_matches,
        )

    if exact_matches and any(hit in category_hits for hit in ("fire", "mine", "pipeline")):
        return CandidateMatch(
            accepted=True,
            level="exact",
            product=product,
            reason="На сайте найдено прямое совпадение с товаром/кодом из ТЗ и профильная категория.",
            matched_terms=exact_matches,
        )

    if not exact_matches and target_groups and not (front_category_hits & target_groups):
        return CandidateMatch(
            accepted=False,
            level="reject",
            product="",
            reason="В заголовке/сниппете нет явной связи с товаром или отраслью ТЗ.",
            matched_terms=tuple(sorted(category_hits)),
        )
    if not exact_matches and "pipeline" in front_category_hits and (target_groups - {"pipeline"}) and not (
        front_category_hits & (target_groups - {"pipeline"})
    ):
        return CandidateMatch(
            accepted=False,
            level="reject",
            product="",
            reason="Найдена общая трубопроводная тематика без пожарного или шахтного контекста ТЗ.",
            matched_terms=tuple(sorted(category_hits)),
        )

    if commercial and _is_adjacent_category(category_hits, context):
        return CandidateMatch(
            accepted=True,
            level="adjacent",
            product=product or "Профильная категория по ТЗ",
            reason="Официальный сайт профильного поставщика: категория близка к ТЗ, наличие точной позиции нужно запросить у отдела продаж.",
            matched_terms=tuple(sorted(category_hits)),
        )

    if commercial and _is_profile_supplier(category_hits, context):
        return CandidateMatch(
            accepted=True,
            level="profile",
            product=product or "Профильный поставщик категории",
            reason="Официальный сайт профильного поставщика по отрасли ТЗ; строка добавлена как лид для запроса наличия/аналога.",
            matched_terms=tuple(sorted(category_hits)),
        )

    terms = important_terms(context)
    matches = [term for term in terms[:24] if term in lowered]
    if len(matches) >= 3 and commercial:
        return CandidateMatch(
            accepted=True,
            level="profile",
            product=product or ", ".join(matches[:6]),
            reason="Официальный сайт поставщика содержит несколько терминов из ТЗ и контактную коммерческую информацию.",
            matched_terms=tuple(matches[:8]),
        )

    return CandidateMatch(
        accepted=False,
        level="reject",
        product="",
        reason="Страница открыта, но не подтверждает точный товар, близкую категорию или профильного поставщика по ТЗ.",
        matched_terms=tuple(matches[:8]),
    )


def candidate_matches_context(candidate: Candidate, context: str, pages: list[dict]) -> bool:
    return assess_candidate_match(candidate, context, pages).accepted


def _exact_match_terms(context: str) -> list[str]:
    phrases = _product_phrases(context)
    result: list[str] = []
    for phrase in phrases:
        lowered = phrase.lower()
        if len(lowered) <= 80:
            result.append(lowered)
        if "(" in phrase and ")" in phrase:
            result.extend(part.lower().strip() for part in re.findall(r"\(([^()]{6,120})\)", phrase))
    result.extend(
        code.lower().replace(" ", "-")
        for code in _exact_codes(context)
        if not re.fullmatch(r"ГМ-\d+", code)
    )
    lowered_context = context.lower()
    if "сверло шахтное универсальное" in lowered_context:
        result.extend(["сверло шахтное универсальное", "сверло шахтное", "сшу-22", "сшу 22"])
    if "промежуточного подсоединения пожарных рукавов" in lowered_context:
        result.extend(
            [
                "приспособление для промежуточного подсоединения",
                "промежуточного подсоединения пожарных рукавов",
            ]
        )
    return [item for item in dict.fromkeys(re.sub(r"\s+", " ", term).strip(" .,:;") for term in result) if len(item) >= 5]


def _best_product_label(context: str, exact_matches: tuple[str, ...]) -> str:
    phrases = _product_phrases(context)
    if phrases:
        return phrases[0][:220]
    if exact_matches:
        return exact_matches[0]
    words = important_terms(context)
    return " ".join(words[:6])


def _category_hits(text: str) -> set[str]:
    hits: set[str] = set()
    if any(word in text for word in ("пожар", "противопожар", "пожаротуш", "рукав", "гм 70", "гм-70")):
        hits.add("fire")
    if any(word in text for word in ("шахт", "горношахт", "горно-шахт", "горноспас", "вгсч", "угольн")):
        hits.add("mine")
    if any(word in text for word in ("трубопровод", "магистрал", "врезк", "подсоедин", "забор воды", "водн")):
        hits.add("pipeline")
    if any(word in text for word in ("средств безопасности", "средства безопасности", "аварийно", "спасатель")):
        hits.add("safety")
    if any(word in text for word in ("оборудован", "арматур", "инвентар", "снабжен", "комплект")):
        hits.add("equipment")
    return hits


def _has_commercial_supplier_signal(text: str) -> bool:
    return any(
        word in text
        for word in (
            "производ",
            "завод",
            "изготов",
            "постав",
            "дилер",
            "дистриб",
            "купить",
            "цена",
            "каталог",
            "отдел продаж",
            "заявк",
            "заказать",
            "оптом",
            "снабжен",
            "оборудован",
        )
    )


def _is_adjacent_category(category_hits: set[str], context: str) -> bool:
    lowered = context.lower()
    if "пожар" in lowered and "шахт" in lowered and {"fire", "mine"} <= category_hits:
        return True
    if "пожар" in lowered and any(word in lowered for word in ("трубопровод", "магистрал", "врезк")) and {"fire", "pipeline"} <= category_hits:
        return True
    if "шахт" in lowered and any(word in lowered for word in ("трубопровод", "магистрал", "врезк")) and {"mine", "pipeline"} <= category_hits:
        return True
    return len(category_hits & {"fire", "mine", "pipeline", "safety"}) >= 3


def _is_profile_supplier(category_hits: set[str], context: str) -> bool:
    target_groups = _target_category_groups(context)
    if {"fire", "equipment"} <= category_hits:
        return "fire" in target_groups
    if {"mine", "equipment"} <= category_hits:
        return "mine" in target_groups
    if {"pipeline", "equipment"} <= category_hits and not (target_groups - {"pipeline"}):
        return "pipeline" in target_groups
    return bool(target_groups & category_hits) and "safety" in category_hits


def _target_category_groups(context: str) -> set[str]:
    lowered = context.lower()
    target_groups: set[str] = set()
    if "пожар" in lowered:
        target_groups.add("fire")
    if any(word in lowered for word in ("шахт", "горно", "горн", "уголь")):
        target_groups.add("mine")
    if any(word in lowered for word in ("трубопровод", "магистрал", "врезк", "подсоедин")):
        target_groups.add("pipeline")
    return target_groups


def _looks_like_reference_or_non_supplier(candidate: Candidate, text: str) -> bool:
    host = hostname(candidate.url)
    front = f"{candidate.url} {candidate.title} {candidate.snippet}".lower()
    path = urlparse(candidate.url).path.lower()
    if is_blocked(host):
        return True
    if any(marker in path for marker in ("/news", "/article", "/articles", "/info/", "/pravila", "/instruk")):
        if not any(marker in path for marker in ("/catalog", "/product", "/shop")):
            return True
    if any(word in front for word in ("инструкц", "новост", "статья", "article", "news", "forum", "форум")):
        if not any(word in front for word in ("купить", "каталог", "цена", "продаж", "постав")):
            return True
    if any(word in text[:4000] for word in ("патент", "реферат", "википедия", "академия", "университет", "фгбоу", "мчс россии")):
        return True
    if any(word in text[:4000] for word in ("тендер", "закупк")) and not _has_commercial_supplier_signal(text):
        return True
    if "сверл" in front and not any(word in front for word in ("шахт", "горн", "сшу", "шсу", "пожар", "трубопровод")):
        return True
    if "сверл" in text and not any(word in text for word in ("пожар", "шахт", "горноспас", "трубопровод", "гм 70", "гм-70")):
        return True
    if any(word in text for word in ("радиоламп", "триод", "анод", "модуляторн", "электровакуум")):
        return True
    return False


def important_terms(context: str) -> list[str]:
    stopwords = {
        "техническое",
        "задание",
        "условия",
        "поставки",
        "поставка",
        "товара",
        "товар",
        "требования",
        "договор",
        "договора",
        "срок",
        "дней",
        "даты",
        "дата",
        "город",
        "получения",
        "предложений",
        "коммерческого",
        "заключения",
        "рабочих",
        "календарных",
    }
    result: list[str] = []
    for word in re.findall(r"[А-Яа-яЁёA-Za-z0-9\-]{5,}", context.lower()):
        value = word.strip("-")
        if not value or value in stopwords or value.isdigit():
            continue
        if value not in result:
            result.append(value)
        if len(result) >= 40:
            break
    return result
