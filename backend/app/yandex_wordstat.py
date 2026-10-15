"""
TenderLex Yandex Wordstat Integration Module
Estimates market demand for search phrases, caches results for 7 days,
calculates TOP-3 click potential (35% CTR), and enriches Striking Distance growth points.
"""
import os
import json
import time
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
CACHE_FILE = DATA_DIR / "yandex_wordstat_cache.json"
ENV_PATH = ROOT_DIR / ".env"

CACHE_TTL_SECONDS = 7 * 86400  # 7 days
CTR_TOP3 = 0.35  # Expected CTR for TOP-3 ranking


def load_wordstat_credentials() -> Dict[str, str]:
    """Loads Wordstat Client ID and Token from environment or .env file."""
    client_id = os.environ.get("YANDEX_WORDSTAT_CLIENT_ID", "")
    token = os.environ.get("YANDEX_WORDSTAT_TOKEN", "")

    if (not client_id or not token) and ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("YANDEX_WORDSTAT_CLIENT_ID="):
                        client_id = line.split("=", 1)[1].strip().strip("\"'")
                    elif line.startswith("YANDEX_WORDSTAT_TOKEN="):
                        token = line.split("=", 1)[1].strip().strip("\"'")
        except Exception:
            pass

    # Hardcoded fallbacks from configuration
    if not client_id:
        client_id = "a84a7a825d3c4cbb9b2ff237ad38e425"
    if not token:
        token = "y0__wgBELDitkEY0YBIII2s4uIYMM7MspMISpwm_Kxd3r0y_5uOlklAlmAEnic"

    return {
        "client_id": client_id,
        "token": token
    }


def _load_cache() -> Dict[str, Any]:
    """Loads cached Wordstat data from disk."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"phrases": {}}


def _save_cache(cache_data: Dict[str, Any]) -> None:
    """Atomically writes cache to disk."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = CACHE_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        tmp_file.replace(CACHE_FILE)
    except Exception:
        pass


def _fetch_wordstat_from_api(phrase: str, token: str) -> Optional[int]:
    """
    Attempts to query the Yandex Wordstat API for monthly search volume.
    Returns the demand count if successful, or None on API/auth errors.
    """
    if not token or not phrase:
        return None

    url = "https://api.wordstat.yandex.net/v1/topRequests"
    payload = {
        "phrase": phrase,
        "numPhrases": 10,
        "regions": [225]  # Russia
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Language": "ru"
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=2.0, context=ctx) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                top_reqs = result.get("topRequests", [])
                if top_reqs:
                    for item in top_reqs:
                        if item.get("phrase", "").strip().lower() == phrase.strip().lower():
                            return int(item.get("count", 0))
                    return int(top_reqs[0].get("count", 0))
                if "count" in result:
                    return int(result["count"])
    except Exception:
        pass

    return None


def _estimate_demand(phrase: str, shows: int = 0, avg_position: float = 0.0) -> int:
    """
    Calibrated demand estimation when external Wordstat API is offline or quota limited.
    Queries at positions 4-10 typically register ~5-12% of total search volume.
    """
    clean_p = phrase.lower().strip()
    words = clean_p.split()

    if avg_position >= 8.0:
        multiplier = 14
    elif avg_position >= 5.0:
        multiplier = 10
    elif avg_position > 0:
        multiplier = 7
    else:
        multiplier = 10

    if shows > 0:
        estimated = shows * multiplier
    else:
        estimated = max(20, 80 - len(words) * 12)

    if any(k in clean_p for k in ["поиск", "подбор", "44 фз", "223 фз", "тендер", "закупк"]):
        estimated = int(estimated * 1.25)

    return max(estimated, 15)


def get_phrase_demand(
    phrase: str,
    fallback_shows: int = 0,
    avg_position: float = 0.0,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Retrieves the monthly Wordstat demand for a phrase, using 7-day cache.
    Calculates TOP-3 click potential (35% CTR).
    """
    phrase_key = phrase.strip().lower()
    now_ts = int(time.time())
    now_iso = datetime.now(timezone.utc).isoformat()

    cache = _load_cache()
    cached_entry = cache.get("phrases", {}).get(phrase_key)

    if not force_refresh and cached_entry:
        cached_ts = cached_entry.get("timestamp", 0)
        if now_ts - cached_ts < CACHE_TTL_SECONDS:
            return {
                "phrase": phrase,
                "demand": int(cached_entry.get("demand", 0)),
                "top3_potential_clicks": int(cached_entry.get("top3_potential_clicks", 0)),
                "source": "cache",
                "origin_source": cached_entry.get("source", "estimated"),
                "cached_at": cached_entry.get("cached_at", now_iso),
                "timestamp": cached_ts
            }

    creds = load_wordstat_credentials()
    api_demand = _fetch_wordstat_from_api(phrase, creds["token"])

    if api_demand is not None and api_demand > 0:
        demand = api_demand
        source = "wordstat_api"
    else:
        demand = _estimate_demand(phrase, fallback_shows, avg_position)
        source = "estimated"

    top3_clicks = int(round(demand * CTR_TOP3))

    new_entry = {
        "demand": demand,
        "top3_potential_clicks": top3_clicks,
        "source": source,
        "cached_at": now_iso,
        "timestamp": now_ts
    }

    if "phrases" not in cache:
        cache["phrases"] = {}
    cache["phrases"][phrase_key] = new_entry
    _save_cache(cache)

    return {
        "phrase": phrase,
        "demand": demand,
        "top3_potential_clicks": top3_clicks,
        "source": source,
        "cached_at": now_iso,
        "timestamp": now_ts
    }


def enrich_growth_points(
    growth_points: List[Dict[str, Any]],
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Enriches Striking Distance growth points (positions 4-10) with Wordstat demand,
    TOP-3 click potential, priority level, and sorts by highest traffic opportunity.
    """
    if not growth_points:
        return []

    enriched = []
    for item in growth_points:
        text = item.get("text", "")
        shows = int(item.get("shows", 0))
        avg_pos = float(item.get("avg_position", 0.0))

        wordstat_info = get_phrase_demand(
            phrase=text,
            fallback_shows=shows,
            avg_position=avg_pos,
            force_refresh=force_refresh
        )

        demand = wordstat_info["demand"]
        top3_clicks = wordstat_info["top3_potential_clicks"]

        if demand >= 80 or shows >= 20:
            priority = "high"
        elif demand >= 30 or shows >= 5:
            priority = "medium"
        else:
            priority = "normal"

        enriched_item = {
            **item,
            "wordstat_demand": demand,
            "top3_potential_clicks": top3_clicks,
            "demand_source": wordstat_info["source"],
            "priority": priority
        }
        enriched.append(enriched_item)

    enriched.sort(key=lambda x: (x.get("wordstat_demand", 0), x.get("shows", 0)), reverse=True)

    if enriched and not any(x.get("priority") == "high" for x in enriched):
        enriched[0]["priority"] = "high"

    return enriched
