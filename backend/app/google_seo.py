"""
TenderLex Google Search Console API Integration Module
Fetches organic search analytics (queries, impressions, clicks, CTR, position),
detects striking-distance growth points in Google, and checks sitemap status.
"""
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_KEY_PATH = DATA_DIR / "google_service_account.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DEFAULT_SITE_URL = "sc-domain:tenderlex.ru"


def get_gsc_service():
    """Builds and returns the Google Search Console API client."""
    key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not key_path or not Path(key_path).exists():
        key_path = str(DEFAULT_KEY_PATH)

    if not Path(key_path).exists():
        # Check if JSON content is in env
        raw_json = os.environ.get("GOOGLE_GSC_KEY_JSON", "")
        if raw_json:
            creds_info = json.loads(raw_json)
            creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            return build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        return None

    creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def fetch_google_analytics(days: int = 30, site_url: str = DEFAULT_SITE_URL) -> Dict[str, Any]:
    """
    Queries Google Search Console API for the specified number of days.
    Returns structured stats, top queries, and growth points.
    """
    now = datetime.now(timezone.utc)
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    result: Dict[str, Any] = {
        "status": "unavailable",
        "site_url": site_url,
        "period_days": days,
        "total_impressions": 0,
        "total_clicks": 0,
        "avg_position": 0.0,
        "avg_ctr_percent": 0.0,
        "top_queries": [],
        "growth_points": [],
        "sitemaps": []
    }

    try:
        service = get_gsc_service()
        if not service:
            result["error"] = "Google Service Account credentials not found"
            return result

        # 1. Query Search Analytics by query
        req_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "rowLimit": 500,
            "dataState": "all"
        }

        try:
            resp = service.searchanalytics().query(siteUrl=site_url, body=req_body).execute()
        except Exception as e:
            # If domain property fails, try https URL fallback
            fallback_url = "https://tenderlex.ru/"
            try:
                resp = service.searchanalytics().query(siteUrl=fallback_url, body=req_body).execute()
                site_url = fallback_url
                result["site_url"] = fallback_url
            except Exception:
                raise e

        rows = resp.get("rows", [])
        total_impressions = 0
        total_clicks = 0
        sum_pos_weighted = 0.0
        queries_clean = []
        growth_points = []

        for r in rows:
            query_text = r.get("keys", [""])[0]
            clicks = int(r.get("clicks", 0))
            impressions = int(r.get("impressions", 0))
            ctr = round(float(r.get("ctr", 0.0)) * 100, 1)
            avg_pos = round(float(r.get("position", 0.0)), 1)

            total_impressions += impressions
            total_clicks += clicks
            sum_pos_weighted += avg_pos * impressions

            item = {
                "text": query_text,
                "shows": impressions,
                "clicks": clicks,
                "avg_position": avg_pos,
                "ctr_percent": ctr
            }
            queries_clean.append(item)

            # Detect striking distance growth points in Google (positions 4 to 20)
            if 3.5 <= avg_pos <= 20.0 and impressions >= 1:
                growth_points.append({
                    **item,
                    "potential": f"Высокий (позиция {avg_pos} в Google)",
                    "action": "Дожать в ТОП-3 Google"
                })

        # Enrich growth points with Wordstat demand if available
        try:
            from app.yandex_wordstat import enrich_growth_points
            growth_points = enrich_growth_points(growth_points)
        except Exception:
            pass

        avg_pos_final = round(sum_pos_weighted / total_impressions, 1) if total_impressions > 0 else 0.0
        avg_ctr_final = round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0.0

        # Sort top queries by impressions descending
        queries_clean.sort(key=lambda x: (x["shows"], x["clicks"]), reverse=True)

        # 2. Check Sitemaps status
        sitemaps_clean = []
        try:
            sitemaps_resp = service.sitemaps().list(siteUrl=site_url).execute()
            for sm in sitemaps_resp.get("sitemap", []):
                sitemaps_clean.append({
                    "path": sm.get("path", ""),
                    "last_submitted": sm.get("lastSubmitted", ""),
                    "last_downloaded": sm.get("lastDownloaded", ""),
                    "is_pending": sm.get("isPending", False),
                    "warnings": sm.get("warnings", 0),
                    "errors": sm.get("errors", 0),
                })
        except Exception as sm_err:
            logger.warning("Could not fetch Google sitemaps: %s", sm_err)

        result.update({
            "status": "active",
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "avg_position": avg_pos_final,
            "avg_ctr_percent": avg_ctr_final,
            "top_queries": queries_clean,
            "growth_points": growth_points,
            "sitemaps": sitemaps_clean
        })

    except Exception as e:
        logger.error("Error fetching Google Search Console analytics: %s", e)
        result["status"] = "error"
        result["error"] = str(e)

    return result
