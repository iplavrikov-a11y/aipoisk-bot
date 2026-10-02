"""Wordstat observations with provenance; unavailable API data remains unknown."""
import os
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
CACHE_FILE = DATA_DIR / "yandex_wordstat_cache.json"
ENV_PATH = ROOT_DIR / ".env"
CACHE_TTL_SECONDS = 7 * 86400
WORDSTAT_PERIOD = {"period_days": 30, "kind": "provider_defined_rolling", "start_date": None, "end_date": None}


def load_wordstat_credentials() -> Dict[str, str]:
    """Read configured credentials without overwriting runtime environment values."""
    env_values = {}
    if ENV_PATH.exists():
        try:
            for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                name, separator, value = line.strip().partition("=")
                if separator and name in {"YANDEX_WORDSTAT_CLIENT_ID", "YANDEX_WORDSTAT_TOKEN"}:
                    env_values[name] = value.strip().strip("\"'")
        except OSError:
            pass
    return {"client_id": os.environ.get("YANDEX_WORDSTAT_CLIENT_ID", env_values.get("YANDEX_WORDSTAT_CLIENT_ID", "")),
            "token": os.environ.get("YANDEX_WORDSTAT_TOKEN", env_values.get("YANDEX_WORDSTAT_TOKEN", ""))}


def _load_cache() -> Dict[str, Any]:
    """Ignore unverifiable legacy rows in memory; do not rewrite on a read."""
    try:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        verified = {key: value for key, value in cache.get("phrases", {}).items()
                    if isinstance(value, dict) and value.get("source") == "wordstat_api"
                    and value.get("period", {}).get("period_days") == 30
                    and isinstance(value.get("demand"), int) and value["demand"] >= 0}
        return {"phrases": verified}
    except (OSError, ValueError, AttributeError):
        return {"phrases": {}}


def _save_cache(cache_data: Dict[str, Any]) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = CACHE_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_file.replace(CACHE_FILE)
    except OSError:
        pass


def _fetch_wordstat_from_api(phrase: str, token: str) -> Optional[int]:
    """Return the matching phrase count for the provider's last 30 days."""
    if not token or not phrase:
        return None
    payload = {"phrase": phrase, "regions": [225], "devices": ["all"]}
    req = urllib.request.Request(
        "https://api.wordstat.yandex.net/v1/topRequests",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        # urllib's default TLS context verifies certificates and hostnames.
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
        for item in result.get("topRequests", []):
            if item.get("phrase", "").strip().casefold() == phrase.strip().casefold():
                count = item.get("count")
                if count is not None and int(count) >= 0:
                    return int(count)
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None


def get_phrase_demand(phrase: str, fallback_shows: int = 0, avg_position: float = 0.0, force_refresh: bool = False) -> Dict[str, Any]:
    """Return verified Wordstat data; observed site impressions cannot estimate market demand."""
    phrase_key = phrase.strip().casefold()
    now_ts = int(time.time())
    now_iso = datetime.now(timezone.utc).isoformat()
    cache = _load_cache()
    cached_entry = cache["phrases"].get(phrase_key)
    if not force_refresh and cached_entry and 0 <= now_ts - cached_entry.get("timestamp", 0) < CACHE_TTL_SECONDS:
        return {**cached_entry, "phrase": phrase, "source": "cache", "origin_source": "wordstat_api", "top3_potential_clicks": None}
    api_demand = _fetch_wordstat_from_api(phrase, load_wordstat_credentials()["token"])
    result = {"phrase": phrase, "demand": api_demand, "top3_potential_clicks": None,
              "source": "wordstat_api" if api_demand is not None else "unavailable",
              "period": dict(WORDSTAT_PERIOD), "regions": [225], "devices": ["all"],
              "cached_at": now_iso if api_demand is not None else None, "timestamp": now_ts,
              "reason": None if api_demand is not None else "No verified matching-phrase Wordstat API response; search demand is unknown."}
    if api_demand is not None:
        cache["phrases"][phrase_key] = result
        _save_cache(cache)
    return result


def enrich_growth_points(growth_points: List[Dict[str, Any]], force_refresh: bool = False) -> List[Dict[str, Any]]:
    enriched = []
    for item in growth_points:
        info = get_phrase_demand(item.get("text", ""), force_refresh=force_refresh)
        demand = info["demand"]
        shows = item.get("shows") or 0
        priority = "high" if (demand is not None and demand >= 80) or shows >= 20 else "medium" if (demand is not None and demand >= 30) or shows >= 5 else "normal"
        enriched.append({**item, "wordstat_demand": demand, "top3_potential_clicks": None,
                         "demand_source": info["source"], "demand_origin_source": info.get("origin_source", info["source"]),
                         "demand_period": info["period"], "demand_collected_at": info["cached_at"],
                         "demand_regions": info["regions"], "priority": priority})
    enriched.sort(key=lambda item: (item.get("wordstat_demand") is not None, item.get("wordstat_demand") or 0, item.get("shows") or 0), reverse=True)
    return enriched
