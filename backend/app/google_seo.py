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

        # 2. Query Search Analytics by date for daily dynamics
        daily_req = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date"],
            "rowLimit": 100,
            "dataState": "all"
        }
        daily_rows = []
        try:
            d_resp = service.searchanalytics().query(siteUrl=site_url, body=daily_req).execute()
            daily_rows = d_resp.get("rows", [])
        except Exception as d_err:
            logger.warning("Could not fetch Google daily analytics: %s", d_err)

        # 3. Query Search Analytics by date and query for unique queries count and phrase changes
        q_daily_req = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date", "query"],
            "rowLimit": 1000,
            "dataState": "all"
        }
        date_to_queries = {}
        query_date_positions = {}
        try:
            q_d_resp = service.searchanalytics().query(siteUrl=site_url, body=q_daily_req).execute()
            for row in q_d_resp.get("rows", []):
                d_key = row["keys"][0]
                q_key = row["keys"][1]
                q_pos = round(float(row.get("position", 0.0)), 1)
                date_to_queries.setdefault(d_key, set()).add(q_key)
                query_date_positions.setdefault(q_key, {})[d_key] = q_pos
        except Exception as qd_err:
            logger.warning("Could not fetch Google date+query analytics: %s", qd_err)

        daily_dynamics = []
        prev_pos = None
        prev_clicks = None
        prev_shows = None

        daily_rows.sort(key=lambda x: x.get("keys", [""])[0])
        for r in daily_rows:
            d_str = r.get("keys", [""])[0]
            d_clicks = int(r.get("clicks", 0))
            d_shows = int(r.get("impressions", 0))
            d_pos = round(float(r.get("position", 0.0)), 1)
            d_ctr = round(float(r.get("ctr", 0.0)) * 100, 1)
            q_count = len(date_to_queries.get(d_str, []))

            # In SEO, smaller position number means higher/better ranking
            pos_delta = round(prev_pos - d_pos, 1) if prev_pos is not None else 0.0
            clicks_delta = d_clicks - prev_clicks if prev_clicks is not None else 0
            shows_delta = d_shows - prev_shows if prev_shows is not None else 0
            trend = "up" if pos_delta > 0 else ("down" if pos_delta < 0 else "stable")

            daily_dynamics.append({
                "date": d_str,
                "clicks": d_clicks,
                "shows": d_shows,
                "avg_position": d_pos,
                "ctr_percent": d_ctr,
                "queries_count": q_count,
                "clicks_delta": clicks_delta,
                "shows_delta": shows_delta,
                "pos_delta": pos_delta,
                "trend": trend
            })
            prev_pos = d_pos
            prev_clicks = d_clicks
            prev_shows = d_shows

        phrase_dynamics = []
        for q_text, d_map in query_date_positions.items():
            sorted_dates = sorted(d_map.keys())
            if len(sorted_dates) >= 2:
                last_d = sorted_dates[-1]
                prev_d = sorted_dates[-2]
                pos_latest = d_map[last_d]
                pos_prev = d_map[prev_d]
                change = round(pos_prev - pos_latest, 1)
                phrase_dynamics.append({
                    "text": q_text,
                    "engine": "google",
                    "current_pos": pos_latest,
                    "prev_pos": pos_prev,
                    "delta": change,
                    "trend": "up" if change > 0 else ("down" if change < 0 else "stable")
                })
        phrase_dynamics.sort(key=lambda x: abs(x["delta"]), reverse=True)

        # 4. Check Sitemaps status
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
            "sitemaps": sitemaps_clean,
            "daily_dynamics": daily_dynamics,
            "phrase_dynamics": phrase_dynamics[:25]
        })

    except Exception as e:
        logger.error("Error fetching Google Search Console analytics: %s", e)
        result["status"] = "error"
        result["error"] = str(e)

    return result
