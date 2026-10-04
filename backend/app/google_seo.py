"""Read-only Google Search Console analytics for the TenderLex SEO dashboard."""
import json
import logging
import os
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .seo_daily import source_date

logger = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_KEY_PATH = DATA_DIR / "google_service_account.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DEFAULT_SITE_URL = "sc-domain:tenderlex.ru"
GSC_TIMEZONE = "America/Los_Angeles"
DEFAULT_LAG_DAYS = 3
QUERY_PAGE_SIZE = 500


def get_gsc_service():
    """Build a Search Console client using existing read-only credentials."""
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not key_path or not Path(key_path).exists():
        key_path = str(DEFAULT_KEY_PATH)
    if Path(key_path).exists():
        creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    raw_json = os.environ.get("GOOGLE_GSC_KEY_JSON", "")
    if raw_json:
        creds = service_account.Credentials.from_service_account_info(json.loads(raw_json), scopes=SCOPES)
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    return None


def _closed_period(days: int, lag_days: int, now: datetime | None = None) -> dict:
    if days < 1:
        raise ValueError("days must be positive")
    if lag_days < 0:
        raise ValueError("lag_days cannot be negative")
    now_pt = now.astimezone(ZoneInfo(GSC_TIMEZONE)) if now else datetime.now(ZoneInfo(GSC_TIMEZONE))
    end_date = now_pt.date() - timedelta(days=lag_days)
    start_date = end_date - timedelta(days=days - 1)
    return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "period_days": days,
            "timezone": GSC_TIMEZONE, "data_state": "final", "lag_days": lag_days,
            "is_closed": True, "collected_at": now_pt.isoformat()}


def _metric_row(row: dict) -> dict:
    if not all(isinstance(row.get(key), (int, float)) and math.isfinite(row[key]) for key in ("impressions", "clicks")):
        raise ValueError("Search Analytics clicks or impressions are missing.")
    impressions = int(row["impressions"])
    clicks = int(row["clicks"])
    if impressions and (not isinstance(row.get("position"), (int, float)) or not math.isfinite(row["position"])):
        raise ValueError("Search Analytics position is missing.")
    return {"clicks": clicks, "impressions": impressions,
            "ctr_percent": round(clicks / impressions * 100, 2) if impressions else 0.0,
            "avg_position": round(float(row.get("position", 0.0)), 2) if impressions else None}


def _date_key(row: dict) -> str | None:
    keys = row.get("keys") if isinstance(row, dict) else None
    return source_date(keys[0]) if isinstance(keys, list) and keys else None


def _query_pages(service, site_url: str, body: dict, errors: list[str], metadata: dict | None = None) -> list[dict]:
    """Read every available page; privacy-suppressed query data remains suppressed."""
    rows: list[dict] = []
    start_row = 0
    try:
        while True:
            page = service.searchanalytics().query(
                siteUrl=site_url, body={**body, "rowLimit": QUERY_PAGE_SIZE, "startRow": start_row}
            ).execute()
            if metadata is not None:
                page_metadata = page.get("metadata") or {}
                marker = source_date(page_metadata.get("firstIncompleteDate") or page_metadata.get("first_incomplete_date"))
                if isinstance(marker, str) and (not metadata.get("first_incomplete_date") or marker < metadata["first_incomplete_date"]):
                    metadata["first_incomplete_date"] = marker
            batch = page.get("rows", [])
            if not isinstance(batch, list):
                raise ValueError("Search Analytics row list is unavailable.")
            rows.extend(batch)
            if len(batch) < QUERY_PAGE_SIZE:
                break
            start_row += QUERY_PAGE_SIZE
    except Exception as exc:
        errors.append(f"Search Analytics {body.get('dimensions', [])}: {exc}")
    return rows


def _query_with_fallback(service, site_url: str, body: dict, errors: list[str]) -> tuple[str, list[dict]]:
    before = len(errors)
    rows = _query_pages(service, site_url, body, errors)
    if rows or len(errors) == before:
        return site_url, rows
    fallback_url = "https://tenderlex.ru/"
    fallback_before = len(errors)
    fallback_rows = _query_pages(service, fallback_url, body, errors)
    if len(errors) == fallback_before:
        # The fallback property is usable; the domain-property error is diagnostic noise.
        del errors[before:fallback_before]
    return fallback_url, fallback_rows


def fetch_google_analytics(days: int = 28, site_url: str = DEFAULT_SITE_URL, lag_days: int = DEFAULT_LAG_DAYS) -> Dict[str, Any]:
    """Read a closed final GSC period without treating query rows as site totals."""
    period = _closed_period(days, lag_days)
    zero_metrics = {"clicks": 0, "impressions": 0, "ctr_percent": 0.0, "avg_position": None}
    unknown_metrics = {key: None for key in zero_metrics}
    result: Dict[str, Any] = {
        "status": "unavailable", "site_url": site_url, "period_days": days, "period": period,
        "property_totals": unknown_metrics.copy(), "totals_status": "unavailable",
        "query_sample": {"status": "unavailable", "row_count": None, **unknown_metrics, "impression_coverage_percent": None},
        "component_status": {"credentials": "unavailable", "property_totals": "unavailable", "query_sample": "unavailable", "daily_dynamics": "unavailable", "sitemaps": "unavailable"},
        # Backwards-compatible aliases that always reference property totals.
        "total_impressions": None, "total_clicks": None, "avg_position": None, "avg_ctr_percent": None,
        "top_queries": [], "growth_points": [], "daily_dynamics": [], "phrase_dynamics": [],
        "sitemaps": [], "errors": [],
    }
    errors: list[str] = result["errors"]
    try:
        service = get_gsc_service()
    except Exception:
        errors.append("Google Service Account credentials could not be parsed or initialized.")
        result["component_status"]["credentials"] = "error"
        result["status"] = "error"
        return result
    if not service:
        errors.append("Google Service Account credentials not found")
        return result
    result["component_status"]["credentials"] = "available"
    # A fixed lag is a request bound, not proof that all dates are finalized.
    # Anchor the summary to the latest observed final date before requesting totals.
    preflight_errors: list[str] = []
    preflight_site, final_rows = _query_with_fallback(service, site_url, {
        "startDate": (datetime.fromisoformat(period["start_date"]) - timedelta(days=35)).date().isoformat(),
        "endDate": period["end_date"], "dimensions": ["date"], "dataState": "final",
    }, preflight_errors)
    final_dates = {_date_key(row) for row in final_rows}
    available_final = max((day for day in final_dates if day and day <= period["end_date"]), default=None)
    if available_final:
        period["end_date"] = available_final
        period["start_date"] = (datetime.fromisoformat(available_final) - timedelta(days=days - 1)).date().isoformat()
    period["latest_observed_final_date"] = available_final
    site_url = preflight_site
    base = {"startDate": period["start_date"], "endDate": period["end_date"], "dataState": "final"}
    try:
        active_site, property_rows = _query_with_fallback(service, site_url, {**base, "dimensions": []}, errors)
        result["site_url"] = active_site
        if errors:
            result["component_status"]["property_totals"] = "error"
            result["status"] = "error"
            return result
        try:
            property_metrics = _metric_row(property_rows[0]) if property_rows else zero_metrics.copy()
        except (TypeError, ValueError) as property_error:
            errors.append(f"Search Analytics property metrics: {property_error}")
            result["totals_status"] = "error"
            result["component_status"]["property_totals"] = "error"
            result["status"] = "error"
            return result
        result["totals_status"] = "available"
        result["component_status"]["property_totals"] = "available"
        result["property_totals"] = property_metrics
        result.update({"total_impressions": property_metrics["impressions"], "total_clicks": property_metrics["clicks"],
                       "avg_position": property_metrics["avg_position"], "avg_ctr_percent": property_metrics["ctr_percent"]})

        query_error_count = len(errors)
        query_rows = _query_pages(service, active_site, {**base, "dimensions": ["query"]}, errors)
        if len(errors) == query_error_count:
            try:
                queries: List[dict] = []
                sample_impressions = sample_clicks = 0
                weighted_position = 0.0
                for row in query_rows:
                    metrics = _metric_row(row)
                    sample_impressions += metrics["impressions"]
                    sample_clicks += metrics["clicks"]
                    weighted_position += (metrics["avg_position"] or 0.0) * metrics["impressions"]
                    queries.append({"text": row.get("keys", [""])[0], "shows": metrics["impressions"], "clicks": metrics["clicks"],
                                    "avg_position": metrics["avg_position"], "ctr_percent": metrics["ctr_percent"]})
                result["query_sample"] = {
                    "status": "available", "row_count": len(query_rows), "clicks": sample_clicks, "impressions": sample_impressions,
                    "ctr_percent": round(sample_clicks / sample_impressions * 100, 2) if sample_impressions else 0.0,
                    "avg_position": round(weighted_position / sample_impressions, 2) if sample_impressions else None,
                    "impression_coverage_percent": round(sample_impressions / property_metrics["impressions"] * 100, 2) if property_metrics["impressions"] else None,
                }
                result["component_status"]["query_sample"] = "available"
                queries.sort(key=lambda item: (item["shows"], item["clicks"]), reverse=True)
                result["top_queries"] = queries
                result["growth_points"] = [
                    {**item, "potential": "Гипотеза: близко к первой странице Google", "action": "Проверить интент, посадочную страницу и CTR на достаточной выборке"}
                    for item in queries if item["avg_position"] is not None and 3.5 <= item["avg_position"] <= 20 and item["shows"] >= 20
                ]
            except (TypeError, ValueError, KeyError, IndexError) as query_error:
                errors.append(f"Search Analytics query metrics: {query_error}")
        if len(errors) != query_error_count:
            result["query_sample"]["status"] = "error"
            result["component_status"]["query_sample"] = "error"

        daily_error_count = len(errors)
        errors.extend(preflight_errors)
        daily_period = {**_closed_period(30, 0), "data_state": "all", "is_closed": False}
        metadata = {}
        fresh_rows = _query_pages(service, active_site, {"startDate": daily_period["start_date"], "endDate": daily_period["end_date"], "dataState": "all", "dimensions": ["date"]}, errors, metadata)
        final_dates = {_date_key(row) for row in final_rows}
        by_date = {_date_key(row): row for row in final_rows}
        by_date.update({_date_key(row): row for row in fresh_rows})
        by_date = {day: row for day, row in by_date.items() if isinstance(day, str) and daily_period["start_date"] <= day <= daily_period["end_date"] and source_date(day)}
        marker = metadata.get("first_incomplete_date")
        for day, row in sorted(by_date.items()):
            if not source_date(day): continue
            try:
                metrics = _metric_row(row)
                data_status = "preliminary" if marker and day >= marker else "final" if day in final_dates or (marker and day < marker) else "preliminary"
                result["daily_dynamics"].append({"date": day, "clicks": metrics["clicks"], "shows": metrics["impressions"], "avg_position": metrics["avg_position"], "ctr_percent": metrics["ctr_percent"], "data_status": data_status})
            except (TypeError, ValueError) as exc:
                errors.append(f"Search Analytics daily metrics: {exc}")
        result["daily_period"] = {**daily_period, "available_start_date": min(by_date, default=None), "available_end_date": max(by_date, default=None)}
        result["first_incomplete_date"] = marker
        result["component_status"]["daily_dynamics"] = "available" if len(errors) == daily_error_count else "error"
        try:
            sitemaps = service.sitemaps().list(siteUrl=active_site).execute().get("sitemap", [])
            result["sitemaps"] = [{"path": item.get("path", ""), "last_submitted": item.get("lastSubmitted", ""),
                "last_downloaded": item.get("lastDownloaded", ""), "is_pending": item.get("isPending", False),
                "warnings": item.get("warnings", 0), "errors": item.get("errors", 0)} for item in sitemaps]
            result["component_status"]["sitemaps"] = "available"
        except Exception as exc:
            result["component_status"]["sitemaps"] = "error"
            errors.append(f"Sitemaps: {exc}")
        result["status"] = "active" if not errors else "partial"
    except Exception as exc:
        logger.exception("Error fetching Google Search Console analytics")
        errors.append(str(exc))
        result["status"] = "error"
    return result
