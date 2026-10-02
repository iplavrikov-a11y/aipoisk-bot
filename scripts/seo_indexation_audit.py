#!/usr/bin/env python3
"""Read-only Yandex/Google indexation and backlink evidence collector.

The script deliberately does not add Important URLs, request recrawls, submit
URLs, or change either search-service account. Its outputs contain public URLs
and documented status fields only; authentication details never leave memory.
"""
from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SITEMAP_URL = "https://tenderlex.ru/sitemap.xml"
DEFAULT_SITE_URL = "sc-domain:tenderlex.ru"
REQUEST_TIMEOUT_SECONDS = 20
MAX_YANDEX_ITEMS = 50_000
MAX_GOOGLE_WORKERS = 3


def normalize_public_url(value: object) -> str | None:
    """Normalize equivalent public web URLs without retaining query or fragment."""
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower().rstrip(".")
    port = parsed.port
    if port and port not in {80, 443}:
        host = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, "", ""))


def _safe_error(response: object, provider: str) -> str:
    """Return a stable diagnostic without URLs, headers, tokens, or exception text."""
    code = response.get("error_code") if isinstance(response, dict) else None
    allowed_codes = {"HOST_NOT_VERIFIED", "HOST_NOT_FOUND", "HOST_NOT_LOADED", "INVALID_USER_ID", "ACCESS_DENIED"}
    suffix = f" ({code})" if code in allowed_codes else ""
    return f"{provider} data is unavailable{suffix}."


def collect_paginated_samples(
    get_page: Callable[[int, int], dict], *, page_size: int = 100, items_key: str = "samples"
) -> dict:
    """Read documented offset pages while retaining unknown data as null, never zero."""
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")
    offset = 0
    api_count: int | None = None
    items: list[dict] = []
    while offset < MAX_YANDEX_ITEMS:
        try:
            response = get_page(offset, page_size)
        except Exception as exc:
            return {"status": "unavailable", "api_count": None, "returned_count": None, "items": [],
                    "error": _safe_error(exc, "Yandex Webmaster")}
        if not isinstance(response, dict) or response.get("error") or response.get("error_code"):
            return {"status": "unavailable", "api_count": None, "returned_count": None, "items": [],
                    "error": _safe_error(response, "Yandex Webmaster")}
        count = response.get("count")
        batch = response.get(items_key)
        if not isinstance(count, int) or count < 0 or not isinstance(batch, list):
            return {"status": "unavailable", "api_count": None, "returned_count": None, "items": [],
                    "error": "Yandex Webmaster response is incomplete."}
        if api_count is None:
            api_count = min(count, MAX_YANDEX_ITEMS)
        elif api_count != min(count, MAX_YANDEX_ITEMS):
            return {"status": "unavailable", "api_count": None, "returned_count": None, "items": [],
                    "error": "Yandex Webmaster page count changed during collection."}
        items.extend(item for item in batch if isinstance(item, dict))
        offset += len(batch)
        if offset >= api_count or len(batch) < page_size:
            break
    status = "available" if api_count is not None and len(items) >= api_count else "partial"
    return {"status": status, "api_count": api_count, "returned_count": len(items), "items": items,
            "error": None if status == "available" else "Yandex Webmaster returned fewer samples than reported."}


def _public_observation(item: dict, *, searchable: bool | None = None) -> dict | None:
    url = normalize_public_url(item.get("url"))
    if not url:
        return None
    target_url = normalize_public_url(item.get("target_url"))
    return {
        "url": url,
        "searchable": searchable if searchable is not None else item.get("searchable"),
        "excluded_url_status": item.get("excluded_url_status") if isinstance(item.get("excluded_url_status"), str) else None,
        "target_url": target_url,
        "last_access": item.get("last_access") if isinstance(item.get("last_access"), str) else None,
        "http_code": item.get("bad_http_status") if isinstance(item.get("bad_http_status"), int) else None,
    }


def match_sitemap_urls(sitemap_urls: list[str], observations: list[dict]) -> dict:
    """Match canonical public URLs, allowing a reported redirect/canonical target."""
    canonical_sitemap = {url for raw in sitemap_urls if (url := normalize_public_url(raw))}
    matched: dict[str, dict] = {}
    for item in observations:
        if not isinstance(item, dict):
            continue
        candidate = _public_observation(item)
        if not candidate:
            continue
        if candidate["url"] in canonical_sitemap:
            key = candidate["url"]
            previous = matched.get(key)
            if previous is None or previous["url"] != key:
                matched[key] = candidate
            elif not previous.get("status_conflict") and previous["searchable"] is not None and candidate["searchable"] is not None and previous["searchable"] != candidate["searchable"]:
                matched[key] = {**previous, "searchable": None, "status_conflict": True}
        elif candidate["target_url"] in canonical_sitemap:
            key = candidate["target_url"]
            # A source redirect is not an indexation verdict for its target.
            if key not in matched:
                matched[key] = {**candidate, "searchable": None}
    searchable_matches = sum(1 for item in matched.values() if item["searchable"] is True)
    not_searchable_matches = sum(1 for item in matched.values() if item["searchable"] is False)
    return {"sitemap_urls": len(canonical_sitemap), "observed_urls": len({item["url"] for item in matched.values()}),
            "matched_urls": len(matched), "searchable_matches": searchable_matches,
            "not_searchable_matches": not_searchable_matches,
            "unknown_matches": len(matched) - searchable_matches - not_searchable_matches,
            "conflicting_matches": sum(bool(item.get("status_conflict")) for item in matched.values())}


def build_event_history(events: dict) -> dict:
    """Preserve Yandex events as history; they cannot be current-exclusion totals."""
    if events.get("status") not in {"available", "partial"}:
        return {"status": "unavailable", "scope": "historical_search_events", "api_count": None,
                "returned_count": None, "removed_event_count": None, "current_exclusion_count": None,
                "events": [], "error": events.get("error")}
    public_events = []
    for item in events.get("items", []):
        public = _public_observation(item)
        if public and item.get("event") in {"APPEARED_IN_SEARCH", "REMOVED_FROM_SEARCH"}:
            public_events.append({**public, "event": item["event"],
                                  "event_date": item.get("event_date") if isinstance(item.get("event_date"), str) else None})
    return {"status": events["status"], "scope": "historical_search_events", "api_count": events.get("api_count"),
            "returned_count": len(public_events),
            "removed_event_count": sum(item["event"] == "REMOVED_FROM_SEARCH" for item in public_events),
            "current_exclusion_count": None, "events": public_events, "error": events.get("error")}


def _fetch_sitemap_urls(url: str = DEFAULT_SITEMAP_URL) -> dict:
    try:
        request = Request(url, headers={"User-Agent": "TenderLex-SEO-Audit/1.0"})
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            root = ElementTree.fromstring(response.read())
    except Exception:
        return {"status": "unavailable", "url": normalize_public_url(url), "count": None, "urls": [],
                "error": "Sitemap is unavailable."}
    urls = []
    for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
        normalized = normalize_public_url(node.text)
        if normalized:
            urls.append(normalized)
    return {"status": "available", "url": normalize_public_url(url), "count": len(set(urls)),
            "urls": sorted(set(urls)), "error": None}


def inspect_google_urls(
    urls: list[str], *, service_factory: Callable[[], Any] | None = None, site_url: str = DEFAULT_SITE_URL,
    max_workers: int = MAX_GOOGLE_WORKERS,
) -> dict:
    """Inspect Google-index versions concurrently, creating one service per worker thread."""
    public_urls = sorted({url for raw in urls if (url := normalize_public_url(raw))})
    if not public_urls:
        return {"status": "available", "requested_count": 0, "inspected_count": 0, "unknown_count": 0,
                "results": [], "error": None}
    if service_factory is None:
        from app.google_seo import get_gsc_service
        service_factory = get_gsc_service
    local = threading.local()

    def inspect(url: str) -> dict:
        try:
            if not hasattr(local, "service"):
                local.service = service_factory()
                if not local.service:
                    raise RuntimeError("unavailable")
                # googleapiclient keeps the transport on the service. Bound each
                # inspection request just like the Yandex and Sitemap requests.
                if hasattr(local.service, "_http"):
                    local.service._http.timeout = REQUEST_TIMEOUT_SECONDS
            body = {"inspectionUrl": url, "siteUrl": site_url, "languageCode": "ru-RU"}
            response = local.service.urlInspection().index().inspect(body=body).execute()
            index = response.get("inspectionResult", {}).get("indexStatusResult", {}) if isinstance(response, dict) else {}
            if not isinstance(index, dict) or not index:
                raise RuntimeError("missing inspection result")
            return {"url": url, "status": "available", "verdict": index.get("verdict"),
                    "coverage_state": index.get("coverageState"), "robots_txt_state": index.get("robotsTxtState"),
                    "indexing_state": index.get("indexingState"), "page_fetch_state": index.get("pageFetchState"),
                    "last_crawl_time": index.get("lastCrawlTime"),
                    "google_canonical": normalize_public_url(index.get("googleCanonical")),
                    "user_canonical": normalize_public_url(index.get("userCanonical")), "error": None}
        except Exception:
            return {"url": url, "status": "unavailable", "verdict": None, "coverage_state": None,
                    "robots_txt_state": None, "indexing_state": None, "page_fetch_state": None,
                    "last_crawl_time": None, "google_canonical": None, "user_canonical": None,
                    "error": "Google URL Inspection is unavailable."}

    workers = min(MAX_GOOGLE_WORKERS, max(1, max_workers), len(public_urls))
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(inspect, url) for url in public_urls]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["url"])
    inspected_count = sum(item["status"] == "available" for item in results)
    unknown_count = len(results) - inspected_count
    status = "available" if inspected_count == len(results) else "partial" if inspected_count else "unavailable"
    return {"status": status, "requested_count": len(public_urls),
            "inspected_count": inspected_count if inspected_count else None, "unknown_count": unknown_count,
            "results": results, "error": None if status == "available" else "Google URL Inspection data is partially or fully unavailable."}


def _yandex_reader() -> tuple[Callable[[str, int, int], dict] | None, dict]:
    """Create a private-only reader over the existing token loader and safe HTTP helper."""
    from app.yandex_seo import _http_json, _load_env_tokens

    tokens = _load_env_tokens()
    token = tokens.get("webmaster")
    if not token:
        return None, {"status": "unavailable", "error": "Yandex Webmaster credentials are unavailable."}
    headers = {"Authorization": f"OAuth {token}"}
    user = _http_json("https://api.webmaster.yandex.net/v4/user", headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    user_id = user.get("user_id") if isinstance(user, dict) else None
    host_id = tokens.get("host_id")
    if not user_id or not host_id:
        return None, {"status": "unavailable", "error": _safe_error(user, "Yandex Webmaster")}
    base = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}"

    def read(path: str, offset: int = 0, limit: int = 100) -> dict:
        joiner = "&" if "?" in path else "?"
        return _http_json(f"{base}{path}{joiner}offset={offset}&limit={limit}", headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)

    return read, {"status": "available", "error": None}


def _important_urls(read: Callable[[str, int, int], dict] | None, state: dict) -> dict:
    if not read:
        return {"status": "unavailable", "returned_count": None, "items": [], "error": state["error"]}
    response = read("/important-urls")
    if not isinstance(response, dict) or response.get("error") or response.get("error_code") or not isinstance(response.get("urls"), list):
        return {"status": "unavailable", "returned_count": None, "items": [],
                "error": _safe_error(response, "Yandex Webmaster")}
    items = []
    for item in response["urls"]:
        if not isinstance(item, dict):
            continue
        merged = {**item, **(item.get("search_status") if isinstance(item.get("search_status"), dict) else {})}
        public = _public_observation(merged)
        if public:
            items.append(public)
    return {"status": "available", "returned_count": len(items), "items": items, "error": None}


def _external_backlinks(read: Callable[[str, int, int], dict] | None, state: dict) -> dict:
    if not read:
        unavailable = {"status": "unavailable", "api_count": None, "returned_count": None, "links": [], "error": state["error"]}
        return {"external_samples": unavailable, "history": {"status": "unavailable", "link_total_count": None, "error": state["error"]}}
    samples = collect_paginated_samples(lambda offset, limit: read("/links/external/samples", offset, limit), items_key="links")
    links = []
    for item in samples.get("items", []):
        source = normalize_public_url(item.get("source_url"))
        destination = normalize_public_url(item.get("destination_url"))
        if source and destination:
            links.append({"source_url": source, "destination_url": destination,
                          "discovery_date": item.get("discovery_date") if isinstance(item.get("discovery_date"), str) else None,
                          "source_last_access_date": item.get("source_last_access_date") if isinstance(item.get("source_last_access_date"), str) else None})
    history = read("/links/external/history?indicator=LINKS_TOTAL_COUNT")
    if not isinstance(history, dict) or history.get("error") or history.get("error_code"):
        history_out = {"status": "unavailable", "link_total_count": None,
                       "error": _safe_error(history, "Yandex Webmaster")}
    else:
        values = history.get("indicators", {}).get("LINKS_TOTAL_COUNT")
        history_out = {"status": "available" if isinstance(values, list) else "unavailable",
                       "link_total_count": values if isinstance(values, list) else None,
                       "error": None if isinstance(values, list) else "Yandex Webmaster backlink history is unavailable."}
    return {"external_samples": {**samples, "links": links, "items": None}, "history": history_out}


def collect_audit() -> tuple[dict, dict]:
    sitemap = _fetch_sitemap_urls()
    read, reader_state = _yandex_reader()
    search = collect_paginated_samples(lambda offset, limit: read("/search-urls/in-search/samples", offset, limit)) if read else {
        "status": "unavailable", "api_count": None, "returned_count": None, "items": [], "error": reader_state["error"]}
    events = collect_paginated_samples(lambda offset, limit: read("/search-urls/events/samples", offset, limit)) if read else {
        "status": "unavailable", "api_count": None, "returned_count": None, "items": [], "error": reader_state["error"]}
    important = _important_urls(read, reader_state)
    search_observations = [{**item, "searchable": True} for item in search.get("items", [])]
    observations = search_observations + important.get("items", [])
    indexation = {
        "collected_at": datetime.now(timezone.utc).isoformat(), "scope": "read_only_indexation_audit",
        "sitemap": sitemap,
        "yandex": {"search_samples": {**search, "items": [_public_observation(item, searchable=True) for item in search.get("items", []) if _public_observation(item, searchable=True)]},
                   "important_urls": important, "event_history": build_event_history(events),
                   "sitemap_match": match_sitemap_urls(sitemap.get("urls", []), observations) if sitemap["status"] == "available" else None},
        "google": inspect_google_urls(sitemap.get("urls", [])) if sitemap["status"] == "available" else {
            "status": "unavailable", "requested_count": None, "inspected_count": None, "unknown_count": None,
            "results": [], "error": "Sitemap URL list is unavailable."},
        "limitations": ["Yandex search/event endpoints return documented samples, not a derived sitemap exclusion count.",
                        "Google URL Inspection returns status for the Google-indexed version, not live URL indexability.",
                        "Unavailable or permission-limited data remains null, not zero."],
    }
    backlinks = {"collected_at": indexation["collected_at"], "scope": "read_only_external_backlinks",
                 "yandex": _external_backlinks(read, reader_state),
                 "limitations": ["Yandex Webmaster API exposes external-link samples and LINKS_TOTAL_COUNT history.",
                                 "It does not expose a trusted-backlinks or backlink-quality score."]}
    return indexation, backlinks


def _review_markdown(indexation: dict, backlinks: dict) -> str:
    sitemap = indexation["sitemap"]
    yandex = indexation["yandex"]
    google = indexation["google"]
    return "\n".join([
        "# Indexation review", "", f"Collected: {indexation['collected_at']}",
        "", "## Sitemap", f"- Status: {sitemap['status']}", f"- Canonical public URL count: {sitemap['count']}",
        "", "## Yandex Webmaster", f"- Search samples: {yandex['search_samples']['status']}; API count: {yandex['search_samples']['api_count']}",
        f"- Important URL watchlist: {yandex['important_urls']['status']}; returned: {yandex['important_urls']['returned_count']}",
        f"- Events: {yandex['event_history']['status']}; historical removed events: {yandex['event_history']['removed_event_count']}",
        "- Current exclusion total from events: unknown (events are historical, not a current exclusion report).",
        "", "## Google URL Inspection", f"- Status: {google['status']}; inspected: {google['inspected_count']}; unknown: {google['unknown_count']}",
        "- Scope: indexed Google version only; no live-indexability or ranking claim.",
        "", "## Backlinks", f"- External samples: {backlinks['yandex']['external_samples']['status']}; API count: {backlinks['yandex']['external_samples']['api_count']}",
        f"- LINKS_TOTAL_COUNT history: {backlinks['yandex']['history']['status']}",
        "- No trusted-backlink metric is exposed by the documented API.",
        "", "## Official sources", "- https://yandex.ru/dev/webmaster/doc/ru/reference/hosts-indexing-insearch-samples",
        "- https://yandex.ru/dev/webmaster/doc/ru/reference/hosts-search-events-samples",
        "- https://yandex.ru/dev/webmaster/doc/ru/reference/host-id-important-urls",
        "- https://yandex.ru/dev/webmaster/doc/ru/reference/host-links-external-samples",
        "- https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect", "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only TenderLex indexation evidence collector")
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / ".agent/tasks/2026-10-01-seo-growth/raw")
    args = parser.parse_args()
    indexation, backlinks = collect_audit()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "indexation-before.json").write_text(json.dumps(indexation, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "backlinks-before.json").write_text(json.dumps(backlinks, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "indexation-review.md").write_text(_review_markdown(indexation, backlinks), encoding="utf-8")
    print(json.dumps({"indexation_status": indexation["yandex"]["search_samples"]["status"],
                      "google_status": indexation["google"]["status"],
                      "backlinks_status": backlinks["yandex"]["external_samples"]["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
