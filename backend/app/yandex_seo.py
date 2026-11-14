"""
TenderLex SEO & Analytics Autonomous Pipeline
Gathers analytics snapshots from Yandex.Webmaster, Yandex.Metrika, Yandex.Wordstat, and Google Search Console API.
Tracks conversion goals, detects striking-distance queries in both search engines, and sends Telegram digests.
"""
import os
import json
import time
import asyncio
import urllib.request
import urllib.error
import logging
import re
import math
import tempfile
from email.utils import parsedate_to_datetime
from threading import Lock
import fcntl
from html import escape
from urllib.parse import quote, unquote, urlencode, urlsplit
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from aiogram import Bot
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
SNAPSHOT_PATH = DATA_DIR / "yandex_analytics_snapshot.json"
RECS_STATE_PATH = DATA_DIR / "seo_recommendations_state.json"
HISTORY_PATH = DATA_DIR / "seo_daily_history.json"
ENV_PATH = ROOT_DIR / ".env"
PRIMARY_CONVERSION_CUTOFF = "2026-10-01"
METRIKA_RESTORED_FROM = "2026-11-08"
METRIKA_OPT_IN_CUTOVER = "2026-11-14"
METRIKA_EXPLICIT_OPT_IN_FROM = "2026-11-15"
WEBMASTER_FRESHNESS_DAYS = 14
_ANALYTICS_LOCK = Lock()


def _load_env_tokens():
    fields = {"webmaster": "YANDEX_WEBMASTER_TOKEN", "metrika": "YANDEX_METRIKA_TOKEN",
              "counter_id": "YANDEX_METRIKA_COUNTER_ID", "bot_token": "AIPOISK_BOT_TOKEN",
              "owner_telegram_id": "AIPOISK_OWNER_TELEGRAM_ID", "primary_goal_id": "YANDEX_METRIKA_PRIMARY_GOAL_ID",
              "user_id": "YANDEX_WEBMASTER_USER_ID"}
    file_values = {}
    if ENV_PATH.exists():
        try:
            for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                name, separator, value = line.strip().partition("=")
                if separator and name in fields.values():
                    file_values[name] = value.strip().strip("\"'")
        except OSError:
            pass
    tokens = {field: os.environ.get(name, file_values.get(name, "")) for field, name in fields.items()}
    tokens["host_id"] = os.environ.get("YANDEX_WEBMASTER_HOST_ID", "https:tenderlex.ru:443")
    return tokens


def _get_webmaster_user_id(tokens: dict, wm_headers: dict) -> str | None:
    configured = str(tokens.get("user_id") or "").strip()
    if configured:
        return configured

    try:
        user_res = _http_json("https://api.webmaster.yandex.net/v4/user", headers=wm_headers, timeout=5)
        if isinstance(user_res, dict) and user_res.get("user_id"):
            return str(user_res["user_id"])
    except Exception:
        pass

    try:
        oauth_res = _http_json("https://login.yandex.ru/info", headers=wm_headers, timeout=5)
        if isinstance(oauth_res, dict) and oauth_res.get("id"):
            return str(oauth_res["id"])
    except Exception:
        pass

    return "137212208" if tokens.get("webmaster") else None


def _retry_delay(value: str | None) -> float:
    if not value:
        return 0.5
    try:
        return max(0.5, float(value))
    except ValueError:
        try:
            return max(0.5, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 0.5


def _http_json(url: str, headers: dict = None, timeout: int = 15, retry_transient: bool = False) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    for attempt in range(2 if retry_transient else 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else {"error": "Unexpected API response."}
        except Exception as error:
            if retry_transient and attempt == 0:
                if isinstance(error, urllib.error.HTTPError) and error.code in {429, 502, 503, 504}:
                    delay = _retry_delay(error.headers.get("Retry-After") if error.headers else None)
                    if delay <= 3:
                        error.close()
                        time.sleep(delay)
                        continue
                elif isinstance(error, TimeoutError) or (isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError)):
                    time.sleep(0.5)
                    continue
            # Keep provider errors useful without leaking credentials in request URLs or headers.
            safe_error = re.sub(r"(?:OAuth\s+|Bearer\s+|y0__)[^\s,'\"]+", "[redacted]", str(error))
            return {"error": safe_error}


def _metrika_closed_period(counter_timezone: str | None, now: datetime | None = None, days: int = 28) -> dict:
    """Return explicit inclusive counter-local dates, ending with the last complete day."""
    timezone_error = None
    try:
        if not counter_timezone:
            raise ValueError("Counter timezone is missing.")
        zone = ZoneInfo(counter_timezone)
    except Exception:
        zone = timezone.utc
        timezone_error = "Counter timezone is missing or invalid; UTC is diagnostic fallback only."
    local_now = now.astimezone(zone) if now else datetime.now(zone)
    end_date = local_now.date() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "period_days": days,
            "timezone": counter_timezone if timezone_error is None else "UTC", "timezone_valid": timezone_error is None,
            "error": timezone_error, "is_closed": True, **_metrika_regime(start_date.isoformat(), end_date.isoformat())}


def _metrika_regime(start_date: str, end_date: str) -> dict:
    if start_date >= METRIKA_EXPLICIT_OPT_IN_FROM:
        return {"measurement_regime": "explicit_opt_in", "is_comparable": True}
    if start_date >= METRIKA_RESTORED_FROM and end_date < METRIKA_OPT_IN_CUTOVER:
        return {"measurement_regime": "prior_tracking", "is_comparable": False}
    return {"measurement_regime": "mixed_or_interrupted" if end_date >= METRIKA_RESTORED_FROM else "before_tracking_recovery", "is_comparable": False}


def _metric_chunks(metrics: list[str], size: int = 20) -> list[list[str]]:
    return [metrics[index:index + size] for index in range(0, len(metrics), size)]


def _action_values(value) -> set[str]:
    if isinstance(value, dict):
        values = set()
        if str(value.get("type", "")).lower() == "exact" and isinstance(value.get("url"), str):
            values.add(value["url"])
        if str(value.get("type", "")).lower() in {"action", "javascript"} and isinstance(value.get("value"), str):
            values.add(value["value"])
        for child in value.values():
            values.update(_action_values(child))
        return values
    if isinstance(value, list):
        values = set()
        for child in value:
            values.update(_action_values(child))
        return values
    return set()


def _is_registration_goal(goal: dict) -> bool:
    conditions = goal.get("conditions", [])
    return (str(goal.get("type", "")).lower() in {"action", "javascript"}
            and isinstance(conditions, list) and len(conditions) == 1
            and _action_values(conditions) == {"registration_success"})


def _primary_measurement_period(closed_period: dict) -> dict | None:
    end_date = closed_period["end_date"]
    start_date = max(closed_period["start_date"], PRIMARY_CONVERSION_CUTOFF)
    if end_date < start_date:
        return None
    days = (datetime.fromisoformat(end_date) - datetime.fromisoformat(start_date)).days + 1
    return {**closed_period, "start_date": start_date, "period_days": days, "instrumented_from": "2026-09-30",
            "full_days_from": PRIMARY_CONVERSION_CUTOFF, **_metrika_regime(start_date, end_date)}


def _response_error(response: dict, *, totals_count: int | None = None, data_required: bool = False) -> str | None:
    if response.get("error") or response.get("errors") or response.get("error_code"):
        return str(response.get("error") or response.get("errors") or response["error_code"])
    if totals_count is not None:
        totals = response.get("totals")
        if not isinstance(totals, list) or len(totals) != totals_count:
            return "Expected metric totals are missing from the API response."
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in totals):
            return "Metric totals contain unavailable values."
    if data_required and not isinstance(response.get("data"), list):
        return "Expected report data is missing from the API response."
    return None


def _dimension_report(rows: list, metric_count: int) -> list:
    """Validate dimension rows before converting them into presentation fields."""
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("dimensions"), list) or not row["dimensions"]:
            raise ValueError("Report dimension is unavailable.")
        if not isinstance(row["dimensions"][0], dict) or "name" not in row["dimensions"][0]:
            raise ValueError("Report dimension name is unavailable.")
        error = _response_error({"totals": row.get("metrics")}, totals_count=metric_count)
        if error:
            raise ValueError(error)
    return rows


def build_primary_conversion(goals: list, goal_visits: dict[int, int], visits: int | None, primary_goal_id: str | None, *, period: dict | None = None, error: str | None = None, source: str = "all traffic") -> dict:
    """Use one registered success action and matching unique-visit denominator."""
    base = {"status": "unavailable", "goal_id": None, "goal_name": None, "goal_visits": None,
            "rate_percent": None, "visits": visits, "period": period, "source": source, "reason": None}
    if not primary_goal_id:
        return {**base, "reason": "YANDEX_METRIKA_PRIMARY_GOAL_ID is not configured; registration_success instrumentation starts 2026-09-30; comparable full days start 2026-10-01."}
    try:
        goal_id = int(primary_goal_id)
    except (TypeError, ValueError):
        return {**base, "reason": "Primary goal ID must be a numeric registered JavaScript goal."}
    goal = next((item for item in goals if str(item.get("id")) == str(goal_id)), None)
    if not goal:
        return {**base, "reason": error or "Configured primary goal is missing in Yandex Metrika."}
    base.update(goal_id=goal_id, goal_name=goal.get("name", "Registration success"))
    if not _is_registration_goal(goal):
        return {**base, "reason": "Primary goal must be a JavaScript action with exact registration_success condition."}
    if error or goal_id not in goal_visits or visits is None:
        return {**base, "reason": error or "Unique goal visits or the matching denominator are unavailable."}
    unique_visits = goal_visits[goal_id]
    if unique_visits is None or unique_visits < 0 or visits < 0 or unique_visits > visits:
        return {**base, "reason": "Unique goal visits are inconsistent with the matching denominator."}
    return {**base, "status": "available", "goal_visits": unique_visits,
            "rate_percent": round(unique_visits / visits * 100, 2) if visits else None,
            "reason": None if visits else "No visits in the measured registration period."}


def load_recommendation_states() -> dict:
    if RECS_STATE_PATH.exists():
        try:
            with open(RECS_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_recommendation_states(states: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(RECS_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(states, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def handle_recommendation_action(rec_id: str, action: str) -> dict:
    if action not in ["applied", "rejected", "pending"]:
        return {"ok": False, "error": "Invalid action. Must be applied, rejected, or pending"}
    states = load_recommendation_states()
    states[rec_id] = action
    save_recommendation_states(states)
    
    # Update current cached snapshot if exists
    if SNAPSHOT_PATH.exists():
        try:
            with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                snap = json.load(f)
            for r in snap.get("recommendations", []):
                if r.get("id") == rec_id:
                    r["status"] = action
            with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
    return {"ok": True, "rec_id": rec_id, "status": action}


WEBMASTER_GROWTH_MIN_SHOWS = 3


def generate_ai_recommendations(growth_points: list, metrika: dict, sample_size_ready: bool, google_data: dict = None) -> list:
    states = load_recommendation_states()
    if not sample_size_ready or metrika.get("primary_conversion", {}).get("status") != "available":
        reason = metrika.get("primary_conversion", {}).get("reason") or "недостаточно сопоставимых органических визитов с настроенной первичной целью"
        return [{
            "id": "rec_measurement_baseline",
            "category": "Качество измерений",
            "target": "SEO-аналитика",
            "title": "Сначала накопить валидную выборку",
            "current_text": "Решения по оптимизации требуют достаточного объема сопоставимых данных.",
            "proposed_text": "Собрать закрытый период и проверить настройку первичной цели до изменения страниц.",
            "rationale": f"Это гипотеза, а не прогноз эффекта: {reason}.",
            "impact": "Решение после подтверждения достаточной выборки.",
            "status": states.get("rec_measurement_baseline", "pending"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }]
    recs = []
    
    top_phrase = growth_points[0].get("text") if growth_points else None
    top_pos = growth_points[0].get("avg_position") if growth_points else None
    query_evidence = f"Запрос «{top_phrase}» виден около позиции {top_pos}. " if top_phrase and top_pos is not None else "Нет подтвержденного запроса и позиции для этой гипотезы. "
    
    recs.append({
        "id": "rec_h1_seo_boost_hypothesis_v2",
        "category": "Заголовок первого экрана (H1)",
        "target": "Главная страница tenderlex.ru",
        "title": "Оптимизация H1 под растущие поисковые фразы Яндекса и Google",
        "current_text": "Требует проверки текущего H1 посадочной страницы",
        "proposed_text": "Поиск поставщиков и производителей по техническому заданию | TenderLex",
        "rationale": query_evidence + "Это гипотеза для проверки соответствия H1 и интента на посадочной странице.",
        "impact": "Проверить изменение CTR и целевых визитов на закрытом периоде.",
        "status": states.get("rec_h1_seo_boost_hypothesis_v2", "pending"),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    recs.append({
        "id": "rec_meta_description_boost_hypothesis_v2",
        "category": "Мета-теги (Description)",
        "target": "Главная и посадочные страницы /poisk-postavshchikov-po-tz",
        "title": "Усиление коммерческого сниппета в поисковой выдаче",
        "current_text": "Требует проверки текущего description посадочной страницы",
        "proposed_text": "Поиск поставщиков и производителей по техническому заданию. Контакты организаций и сведения для проверки результатов перед запросом предложения.",
        "rationale": "Фраза является гипотезой для проверки релевантности сниппета. Перед изменением нужно подтвердить достаточные показы и привязку к странице.",
        "impact": "Проверить CTR по тем же запросам и страницам после переобхода.",
        "status": states.get("rec_meta_description_boost_hypothesis_v2", "pending"),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    cr = metrika.get("primary_conversion", {}).get("rate_percent")
    br = metrika.get("bounce_rate", 0.0)
    recs.append({
        "id": "rec_cta_cabinet_boost_hypothesis_v2",
        "category": "Конверсионная кнопка (CTA)",
        "target": "Шапка сайта и карточки сценариев",
        "title": "Оптимизация первого целевого действия на основе конверсий",
        "current_text": "Требует проверки текущего призыва к действию",
        "proposed_text": "Попробовать поиск поставщиков",
        "rationale": f"Первичная конверсия: {cr if cr is not None else 'не измеряется'}%; отказы {br}%. Это гипотеза, требующая валидной цели кабинета и сопоставимого периода.",
        "impact": "Проверить визиты с первичной целью после исправления измерения.",
        "status": states.get("rec_cta_cabinet_boost_hypothesis_v2", "pending"),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return recs


def changed_public_urls(urls: list[str] | None) -> list[str]:
    """Validate explicitly changed public URLs, including removed pages."""
    result = []
    for url in urls or []:
        if not isinstance(url, str):
            raise ValueError("Expected a list of URL strings.")
        parsed = urlsplit(url)
        path = unquote(parsed.path)
        if (parsed.scheme != "https" or parsed.netloc != "tenderlex.ru"
                or parsed.query or parsed.fragment or "?" in url or "#" in url
                or any(char.isspace() or ord(char) < 32 for char in url + path)
                or "\\" in path or any(part in {"..", "."} for part in path.split("/"))
                or path.removeprefix("/").split("/", 1)[0] in {"api", "cabinet", "_next"}):
            raise ValueError("Expected canonical public HTTPS URLs on tenderlex.ru without query strings or fragments.")
        result.append(url if parsed.path else url + "/")
    return list(dict.fromkeys(result))


def submit_sitemap_recrawl(urls: list[str] | None = None) -> dict:
    """Queue explicitly supplied changed public URLs at Yandex and IndexNow."""
    try:
        urls = changed_public_urls(urls)
    except (TypeError, ValueError) as error:
        return {"ok": False, "error": str(error)}
    if not urls:
        return {"ok": True, "status": "skipped", "submitted_count": 0, "total_urls": 0}
    tokens = _load_env_tokens()
    wm_headers = {
        "Authorization": f"OAuth {tokens['webmaster']}",
        "Content-Type": "application/json",
    }
    user_id = _get_webmaster_user_id(tokens, wm_headers)
    if not user_id:
        return {"ok": False, "error": "Yandex Webmaster user identity is unavailable.",
                "submitted_count": 0, "total_urls": len(urls), "indexnow": submit_indexnow(urls)}
    host_id = tokens["host_id"]
    quota_res = _http_json(f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/recrawl/quota", headers=wm_headers, timeout=10)
    daily_quota = quota_res.get("daily_quota") or 0
    remainder = quota_res.get("quota_remainder") or 0

    recrawl_url = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/recrawl/queue"
    submitted = 0
    results = []

    for u in urls:
        if remainder <= 0:
            results.append({"url": u, "status": "SKIPPED_QUOTA_EXCEEDED"})
            continue
        try:
            req_data = json.dumps({"url": u}).encode("utf-8")
            req = urllib.request.Request(recrawl_url, data=req_data, headers=wm_headers, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in [200, 202]:
                    data = json.loads(resp.read().decode("utf-8"))
                    task_id = data.get("task_id", "")
                    remainder = data.get("quota_remainder", remainder - 1)
                    submitted += 1
                    results.append({"url": u, "status": "SUBMITTED", "task_id": task_id})
                else:
                    results.append({"url": u, "status": f"HTTP_{resp.status}"})
        except Exception as e:
            # An independent IndexNow notification is still useful when the priority queue fails.
            results.append({"url": u, "status": "DEFERRED", "error": str(e)})

    indexnow_res = submit_indexnow(urls)

    return {
        "ok": submitted == len(urls) and indexnow_res["ok"],
        "submitted_count": submitted,
        "total_urls": len(urls),
        "daily_quota": daily_quota,
        "quota_remainder": remainder,
        "details": results,
        "indexnow": indexnow_res,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def submit_indexnow(urls: list[str] | None = None) -> dict:
    """Notify IndexNow only about explicit new, changed or removed URLs."""
    try:
        urls = changed_public_urls(urls)
    except (TypeError, ValueError) as error:
        return {"ok": False, "error": str(error)}
    if not urls:
        return {"ok": True, "status": "skipped", "submitted_count": 0}
    payload = {
        "host": "tenderlex.ru",
        "key": "8fa93cd04f90454a82f7ff7d4434a4c6",
        "keyLocation": "https://tenderlex.ru/8fa93cd04f90454a82f7ff7d4434a4c6.txt",
        "urlList": urls
    }
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            accepted = resp.status in {200, 202}
            return {"ok": accepted, "status": resp.status, "submitted_count": len(urls) if accepted else 0}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _webmaster_freshness(base: str, headers: dict, now: datetime, period: dict, previous: dict) -> dict:
    from .seo_daily import source_date, yandex_daily

    today = now.astimezone(ZoneInfo("Europe/Moscow")).date()
    window = urlencode({"date_from": (today - timedelta(days=89)).isoformat(), "date_to": today.isoformat()})
    history = _http_json(f"{base}/search-urls/in-search/history?{window}", headers=headers, timeout=4)
    sitemaps = _http_json(f"{base}/sitemaps?limit=100", headers=headers, timeout=4)
    activity_window = window + "&query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS&device_type_indicator=ALL"
    activity = _http_json(f"{base}/search-queries/all/history?{activity_window}", headers=headers, timeout=4)

    index_rows = history.get("history") or []
    index_date = max((row["date"] for row in index_rows if isinstance(row, dict) and source_date(row.get("date"))), default=None)
    sitemap = next((row for row in sitemaps.get("sitemaps") or [] if isinstance(row, dict)
                    and row.get("sitemap_url") == "https://tenderlex.ru/sitemap.xml"), {})
    sitemap_date = sitemap.get("last_access_date")
    try:
        activity_date = max((day["date"] for day in yandex_daily(activity, today.isoformat())
                             if (day.get("shows") or 0) > 0 or (day.get("clicks") or 0) > 0), default=None)
    except (TypeError, ValueError):
        activity_date = None

    observations = {
        "index_observed_at": index_date,
        "sitemap_downloaded_at": sitemap_date if source_date(sitemap_date) else None,
        "popular_queries_through": period["end_date"],
        "query_activity_through": activity_date,
    }
    # No new records may mean a rolling history window moved past the last observation.
    observations = {key: value or previous.get(key) for key, value in observations.items()}
    dates = [source_date(value) for value in observations.values()]
    threshold = (today - timedelta(days=WEBMASTER_FRESHNESS_DAYS)).isoformat()
    status = "stale" if any(day is not None and day < threshold for day in dates) else (
        "available" if all(dates) else "unavailable"
    )
    return {**observations, "status": status, "checked_at": now.isoformat(),
            "sitemap_urls": sitemap.get("urls_count", previous.get("sitemap_urls")),
            "sitemap_errors": sitemap.get("errors_count", previous.get("sitemap_errors"))}


METRIKA_COMPONENT_FIELDS = {
    "totals": ("visits", "users", "pageviews", "bounce_rate", "avg_duration_seconds", "sampling", "api_query_timezone"),
    "sources": ("sources",),
    "pages": ("top_pages",),
    "goals": ("goals", "total_goal_reaches"),
    "registration_all": ("primary_conversion", "total_conversion_rate"),
    "registration_organic": (),
}


def _usable_metrika_components(metrika: dict) -> dict:
    errors = metrika.get("errors") or {}
    primary = metrika.get("primary_conversion") or {}
    return {
        "totals": metrika.get("visits") is not None and "totals" not in errors,
        "sources": "sources" in metrika and "sources" not in errors,
        "pages": "top_pages" in metrika and "pages" not in errors,
        "goals": metrika.get("total_goal_reaches") is not None and not {"goals", "goal_reaches"} & errors.keys(),
        "registration_all": primary.get("status") == "available",
        "registration_organic": (primary.get("organic") or {}).get("status") == "available",
    }


def _retain_metrika_components(metrika: dict, previous_snapshot: dict, now_iso: str) -> None:
    previous = previous_snapshot.get("metrika") or {}
    if previous.get("counter_id", metrika["counter_id"]) != metrika["counter_id"]:
        previous = {}
    current_ok = _usable_metrika_components(metrika)
    previous_ok = _usable_metrika_components(previous)
    # An unknown timezone makes metrics unsuitable for reuse as observations of a closed local period.
    current_period_ok = (metrika.get("period") or {}).get("timezone_valid") is True
    previous_period_ok = (previous.get("period") or {}).get("timezone_valid") is True
    freshness = {}
    for key, fields in METRIKA_COMPONENT_FIELDS.items():
        old_freshness = (previous.get("component_freshness") or {}).get(key) or {}
        primary = metrika["primary_conversion"]
        old_primary = previous.get("primary_conversion") or {}
        period = metrika["period"]
        old_period = previous.get("period")
        if key == "registration_all":
            period = primary.get("period")
            old_period = old_primary.get("period")
        elif key == "registration_organic":
            period = (primary.get("organic") or {}).get("period")
            old_period = (old_primary.get("organic") or {}).get("period")
        if current_ok[key] and current_period_ok:
            freshness[key] = {"status": "available", "collected_at": now_iso, "period": period}
            continue
        if not old_freshness and previous_ok[key] and previous_period_ok:
            old_freshness = {"status": "available", "collected_at": previous_snapshot.get("updated_at"), "period": old_period}
        if old_freshness.get("status") not in {"available", "stale"}:
            freshness[key] = {"status": "unavailable", "collected_at": None, "period": period}
            continue

        freshness[key] = {**old_freshness, "status": "stale"}
        if key == "registration_all":
            metrika["primary_conversion"] = {**old_primary, "organic": primary.get("organic"), "status": "stale", "reason": primary.get("reason")}
            metrika["total_conversion_rate"] = previous.get("total_conversion_rate")
        elif key == "registration_organic":
            metrika["primary_conversion"]["organic"] = {
                **(old_primary.get("organic") or {}), "status": "stale", "reason": (primary.get("organic") or {}).get("reason"),
            }
        else:
            metrika.update({field: previous.get(field) for field in fields})
    metrika["component_freshness"] = freshness


def _write_snapshot(path: Path, value: dict) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def fetch_fresh_snapshot() -> dict:
    tokens = _load_env_tokens()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    # Load previous snapshot to preserve valid metrics during transient provider downtime
    prev_snap = {}
    if SNAPSHOT_PATH.exists():
        try:
            with open(SNAPSHOT_PATH, "r", encoding="utf-8") as sf:
                parsed = json.load(sf)
                if isinstance(parsed, dict):
                    prev_snap = parsed
        except Exception:
            pass

    prev_wm = prev_snap.get("webmaster") or {}

    # 1. Fetch Webmaster Summary & Popular Queries
    wm_headers = {"Authorization": f"OAuth {tokens['webmaster']}"}
    user_id = _get_webmaster_user_id(tokens, wm_headers)
    host_id = tokens["host_id"]
    wm_base = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}"
    if user_id:
        wm_summary = _http_json(f"{wm_base}/summary", headers=wm_headers, timeout=5)
        if "searchable_pages_count" not in wm_summary:
            wm_summary["error"] = wm_summary.get("error") or "Webmaster indexed-page count is unavailable."
        wm_queries = {"queries": []}
        query_offset = 0
        while True:
            response = _http_json(f"{wm_base}/search-queries/popular?order_by=TOTAL_SHOWS&query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS&query_indicator=AVG_SHOW_POSITION&limit=500&offset={query_offset}", headers=wm_headers, timeout=5)
            if response.get("error"):
                wm_queries["error"] = response["error"]
                break
            if not isinstance(response.get("queries"), list):
                wm_queries["error"] = "Popular-query list is missing from the API response."
                break
            for key in ("date_from", "date_to", "count"):
                if key in response:
                    wm_queries[key] = response[key]
            batch = response["queries"]
            wm_queries["queries"].extend(batch)
            if len(batch) < 500:
                break
            query_offset += len(batch)
            if isinstance(wm_queries.get("count"), int) and query_offset >= wm_queries["count"]:
                break
    else:
        wm_summary = {"error": "Yandex Webmaster user identity is unavailable."}
        wm_queries = {"error": wm_summary["error"], "queries": []}
    webmaster_period = {"start_date": wm_queries.get("date_from"), "end_date": wm_queries.get("date_to"),
                        "kind": "provider_defined_popular_queries", "timezone": "provider-defined"}
    if wm_queries.get("error") and prev_wm.get("period"):
        webmaster_period = prev_wm["period"]
    previous_freshness = prev_wm.get("freshness") or {}
    wm_freshness = (_webmaster_freshness(wm_base, wm_headers, now, webmaster_period, previous_freshness)
                    if user_id else {**previous_freshness, "status": "unavailable", "checked_at": now_iso})

    # 1.1 Fetch Webmaster Query Analytics (Daily breakdown by query and dates)
    wm_analytics_url = f"{wm_base}/query-analytics/list"
    wm_analytics_error = None
    wm_daily_raw = {}
    yandex_phrase_history = {}
    try:
        if not user_id:
            raise ValueError("Yandex Webmaster user identity is unavailable.")
        query_page_size = 300
        query_offset = 0
        while True:
            req_qa = urllib.request.Request(
                wm_analytics_url,
                data=json.dumps({"offset": query_offset, "limit": query_page_size}).encode("utf-8"),
                headers={**wm_headers, "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req_qa, timeout=12) as resp:
                qa_data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(qa_data.get("text_indicator_to_statistics"), list):
                raise ValueError("Webmaster query-analytics report is missing or unavailable.")
            query_batch = qa_data["text_indicator_to_statistics"]
            for it in query_batch:
                q_text = it.get("text_indicator", {}).get("value", "")
                for s in it.get("statistics", []):
                    dt = s.get("date")
                    field = s.get("field")
                    val = float(s.get("value", 0.0))
                    if dt not in wm_daily_raw:
                        wm_daily_raw[dt] = {"clicks": 0, "shows": 0, "query_metrics": {}}
                    query_metrics = wm_daily_raw[dt]["query_metrics"].setdefault(q_text, {})
                    if field == "CLICKS":
                        wm_daily_raw[dt]["clicks"] += int(val)
                        query_metrics["clicks"] = int(val)
                    elif field == "IMPRESSIONS":
                        wm_daily_raw[dt]["shows"] += int(val)
                        query_metrics["impressions"] = int(val)
                    elif field == "POSITION":
                        query_metrics["position"] = val
                        yandex_phrase_history.setdefault(q_text, {})[dt] = round(val, 1)
            if len(query_batch) < query_page_size:
                break
            query_offset += query_page_size
    except Exception as qa_err:
        wm_analytics_error = str(qa_err)
        logger.warning("Error fetching Yandex query-analytics: %s", qa_err)
    
    # Site-level daily totals have a wider/fresher window than the phrase sample.
    from .seo_daily import yandex_daily
    daily_today = datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat()
    daily_start = (datetime.now(ZoneInfo("Europe/Moscow")).date() - timedelta(days=29)).isoformat()
    daily_response = _http_json(f"{wm_base}/search-queries/all/history?query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS&query_indicator=AVG_SHOW_POSITION&device_type_indicator=ALL&date_from={daily_start}&date_to={daily_today}", headers=wm_headers, timeout=5) if user_id else {"error": "Webmaster identity unavailable"}
    daily_error = daily_response.get("error")
    full_yandex_daily = []
    try:
        full_yandex_daily = yandex_daily(daily_response, daily_today)
    except (TypeError, ValueError) as exc:
        daily_error = daily_error or str(exc)

    if not full_yandex_daily and HISTORY_PATH.exists():
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as h_f:
                hist_data = json.load(h_f)
            recovered = []
            cur_date = datetime.now(ZoneInfo("Europe/Moscow")).date()
            for i in range(29, 0, -1):
                d_str = (cur_date - timedelta(days=i)).isoformat()
                hist_item = hist_data.get(d_str, {})
                y_item = hist_item.get("yandex")
                if y_item and isinstance(y_item, dict) and y_item.get("date") == d_str:
                    recovered.append(y_item)
                else:
                    recovered.append({
                        "date": d_str,
                        "shows": None,
                        "clicks": None,
                        "avg_position": None,
                        "queries_count": None,
                        "coverage": "All queries reported by Webmaster; not a phrase sample.",
                        "data_status": "reported",
                        "ctr_percent": None,
                    })
            recovered.append({
                "date": daily_today,
                "shows": None,
                "clicks": None,
                "avg_position": None,
                "queries_count": None,
                "coverage": "All queries reported by Webmaster; not a phrase sample.",
                "data_status": "preliminary",
                "ctr_percent": None,
                "state": "Источник временно недоступен",
            })
            full_yandex_daily = recovered
        except Exception as h_exc:
            logger.warning("Could not recover Yandex daily from history: %s", h_exc)

    # 2. Fetch Metrika Core Metrics
    m_headers = {"Authorization": f"OAuth {tokens['metrika']}"}
    counter_id = tokens["counter_id"]
    counter_info = _http_json(
        f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}", headers=m_headers, timeout=6,
        retry_transient=True,
    )
    counter_timezone = counter_info.get("counter", {}).get("time_zone_name") or counter_info.get("counter", {}).get("timezone_name") or counter_info.get("counter", {}).get("timezone")
    metrika_period = _metrika_closed_period(counter_timezone)

    def m_query(params, period=None, *, retry=False):
        query_period = period or metrika_period
        url = f"https://api-metrika.yandex.net/stat/v1/data?ids={counter_id}&date1={query_period['start_date']}&date2={query_period['end_date']}&accuracy=full&" + params
        return _http_json(url, headers=m_headers, timeout=6, retry_transient=retry)

    m_totals = m_query("metrics=ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate,ym:s:avgVisitDurationSeconds", retry=True)
    m_sources = m_query("metrics=ym:s:visits,ym:s:users&dimensions=ym:s:lastSignTrafficSource&sort=-ym:s:visits", retry=True)
    m_pages = m_query("metrics=ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds&dimensions=ym:s:startURLPath&sort=-ym:s:visits&limit=10", retry=True)
    metrika_errors = {}
    for key, response, count in (("totals", m_totals, 5), ("sources", m_sources, None), ("pages", m_pages, None)):
        error = _response_error(response, totals_count=count, data_required=count is None)
        if error:
            metrika_errors[key] = error
    if counter_info.get("error") or metrika_period.get("error"):
        metrika_errors["counter"] = counter_info.get("error") or metrika_period["error"]

    goals_res = _http_json(f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}/goals", headers=m_headers,
                           timeout=6, retry_transient=True)
    raw_goals = goals_res.get("goals", [])
    goals_error = goals_res.get("error")
    if not isinstance(raw_goals, list) or "goals" not in goals_res:
        raw_goals = []
        goals_error = goals_error or "Registered goal list is unavailable."
    if goals_error:
        metrika_errors["goals"] = goals_error
    valid_goals = [goal for goal in raw_goals if str(goal.get("id", "")).isdigit()]
    reaches_by_id = {}
    metrics_list = [f"ym:s:goal{goal['id']}reaches" for goal in valid_goals]
    for metric_chunk in _metric_chunks(metrics_list):
        response = m_query(f"metrics={','.join(metric_chunk)}")
        error = _response_error(response, totals_count=len(metric_chunk))
        if error:
            metrika_errors["goal_reaches"] = error
            continue
        for metric, value in zip(metric_chunk, response["totals"]):
            goal_id = int(metric.removeprefix("ym:s:goal").removesuffix("reaches"))
            reaches_by_id[goal_id] = int(value)
    goals_clean = [{"id": goal["id"], "name": goal.get("name", "Цель"), "type": goal.get("type"),
                    "reaches": reaches_by_id.get(int(goal["id"])), "conditions": goal.get("conditions", [])} for goal in valid_goals]
    total_reaches = sum(reaches_by_id.values()) if not goals_error and "goal_reaches" not in metrika_errors else None

    primary_goal_id = tokens.get("primary_goal_id")
    primary_period = _primary_measurement_period(metrika_period)
    primary_error = goals_error or metrika_errors.get("counter")
    if primary_period is None:
        primary_error = "Registration instrumentation starts 2026-09-30; comparable completed full days start 2026-10-01 and none is available yet."
    primary_visits = None
    primary_goal_visits = {}
    organic_visits = None
    organic_goal_visits = {}
    organic_error = primary_error
    primary_samples = {}
    primary_goal = next((goal for goal in raw_goals if str(goal.get("id")) == str(primary_goal_id)), None)
    valid_primary_goal = primary_goal and _is_registration_goal(primary_goal)
    if not valid_primary_goal:
        metrika_errors["primary_goal"] = "The configured primary goal must be one exact registration_success JavaScript action."
    if primary_period and valid_primary_goal and not primary_error:
        params = f"metrics=ym:s:visits,ym:s:goal{primary_goal_id}visits"
        primary_response = m_query(params, primary_period)
        primary_error = _response_error(primary_response, totals_count=2)
        primary_samples["all_traffic"] = {key: primary_response.get(key) for key in ("sampled", "sample_share", "sample_size", "sample_space")}
        if primary_error is None:
            primary_visits = int(primary_response["totals"][0])
            primary_goal_visits[int(primary_goal_id)] = int(primary_response["totals"][1])
        organic_response = m_query(params + "&filters=" + quote("ym:s:lastSignTrafficSource=='organic'", safe=""), primary_period)
        organic_error = _response_error(organic_response, totals_count=2)
        primary_samples["organic"] = {key: organic_response.get(key) for key in ("sampled", "sample_share", "sample_size", "sample_space")}
        if organic_error is None:
            organic_visits = int(organic_response["totals"][0])
            organic_goal_visits[int(primary_goal_id)] = int(organic_response["totals"][1])
        if primary_error:
            metrika_errors["primary_conversion"] = primary_error
        if organic_error:
            metrika_errors["organic_conversion"] = organic_error
    primary_conversion = build_primary_conversion(raw_goals, primary_goal_visits, primary_visits, primary_goal_id, period=primary_period, error=primary_error)
    primary_conversion["sampling"] = primary_samples.get("all_traffic", {})
    primary_conversion["organic"] = build_primary_conversion(raw_goals, organic_goal_visits, organic_visits, primary_goal_id, period=primary_period, error=organic_error, source="organic traffic")
    primary_conversion["organic"]["sampling"] = primary_samples.get("organic", {})

    google_data = {"status": "unavailable", "site_url": "sc-domain:tenderlex.ru", "period_days": 28,
                   "total_impressions": None, "total_clicks": None, "avg_position": None, "avg_ctr_percent": None,
                   "top_queries": [], "growth_points": [], "sitemaps": []}
    try:
        from app.google_seo import fetch_google_analytics
        google_data = fetch_google_analytics(days=28)
    except Exception as google_error:
        google_data["error"] = str(google_error)
        logger.warning("Google Search Console analytics unavailable: %s", google_error)

    totals_arr = m_totals.get("totals", []) if "totals" not in metrika_errors else []
    visits = int(totals_arr[0]) if totals_arr else None
    users = int(totals_arr[1]) if totals_arr else None
    pageviews = int(totals_arr[2]) if totals_arr else None
    bounce_rate = round(float(totals_arr[3]), 1) if totals_arr else None
    duration_s = int(totals_arr[4]) if totals_arr else None

    queries_clean = []
    growth_points = []
    
    for q in wm_queries.get("queries", []):
        text = q.get("query_text", "")
        indicators = q.get("indicators", {})
        def indicator_value(name, digits=None):
            raw_value = indicators.get(name)
            try:
                number = float(raw_value)
                if math.isfinite(number) and number >= 0:
                    return round(number, digits) if digits is not None else int(number)
            except (TypeError, ValueError):
                pass
            return None
        shows = indicator_value("TOTAL_SHOWS")
        clicks = indicator_value("TOTAL_CLICKS")
        avg_pos = indicator_value("AVG_SHOW_POSITION", 1)
        ctr = round(clicks / shows * 100, 1) if shows and clicks is not None else 0.0 if shows == 0 and clicks == 0 else None
        
        item = {
            "text": text,
            "shows": shows,
            "clicks": clicks,
            "avg_position": avg_pos,
            "ctr_percent": ctr
        }
        queries_clean.append(item)
        
        # Webmaster popular queries cover a 7-day window (top query ~10 shows), so a
        # 20-show floor left Yandex growth points permanently empty.
        if avg_pos is not None and shows is not None and 3.0 <= avg_pos <= 20.0 and shows >= WEBMASTER_GROWTH_MIN_SHOWS:
            growth_points.append({
                **item,
                "potential": "Гипотеза: запрос близок к первой странице Яндекса",
                "action": "Проверить интент, посадочную страницу и CTR на закрытом периоде"
            })
            
    growth_points = sorted(growth_points, key=lambda g: g.get("shows") or 0, reverse=True)[:15]
    # Enrich growth points with Yandex Wordstat monthly demand & TOP-3 click potential
    try:
        from app.yandex_wordstat import enrich_growth_points
        growth_points = enrich_growth_points(growth_points)
    except Exception:
        pass
            
    sources_clean = []
    try:
        source_rows = _dimension_report(m_sources.get("data", []), 2)
    except ValueError as source_error:
        source_rows = []
        metrika_errors["sources"] = str(source_error)
    for s in source_rows:
        sources_clean.append({
            "name": s["dimensions"][0]["name"],
            "visits": int(s["metrics"][0]),
            "users": int(s["metrics"][1]) if len(s["metrics"]) > 1 else 0
        })
        
    pages_clean = []
    try:
        page_rows = _dimension_report(m_pages.get("data", []), 4)
    except ValueError as page_error:
        page_rows = []
        metrika_errors["pages"] = str(page_error)
    for p in page_rows:
        pages_clean.append({
            "path": p["dimensions"][0]["name"],
            "visits": int(p["metrics"][0]),
            "users": int(p["metrics"][1]),
            "bounce_rate": round(float(p["metrics"][2]), 1),
            "avg_duration_seconds": int(p["metrics"][3])
        })
        
    organic_conversion = primary_conversion["organic"]
    sample_ready = (organic_conversion["status"] == "available" and (organic_conversion["visits"] or 0) >= 300
                    and (primary_period or {}).get("period_days", 0) >= 28 and not metrika_errors
                    and (primary_period or {}).get("is_comparable") is True and wm_freshness["status"] == "available"
                    and organic_conversion.get("sampling", {}).get("sampled") is False
                    and not wm_summary.get("error") and not wm_queries.get("error") and not wm_analytics_error
                    and google_data.get("status") == "active" and not google_data.get("error") and not google_data.get("errors"))
    recommendations = generate_ai_recommendations(
        growth_points,
        {"visits": visits, "primary_conversion": primary_conversion, "bounce_rate": bounce_rate},
        sample_ready,
        google_data=google_data
    )

    # 5. Build Combined Unified Queries (Yandex + Google)
    combined_dict = {}
    for q in queries_clean:
        txt = q["text"].strip().lower()
        combined_dict[txt] = {
            "text": q["text"],
            "yandex_pos": q.get("avg_position", 0.0),
            "yandex_shows": q.get("shows", 0),
            "yandex_clicks": q.get("clicks", 0),
            "google_pos": None,
            "google_shows": 0,
            "google_clicks": 0,
            "total_shows": q.get("shows", 0),
            "total_clicks": q.get("clicks", 0),
            "in_yandex": True,
            "in_google": False,
        }

    for gq in google_data.get("top_queries", []):
        txt = gq["text"].strip().lower()
        if txt in combined_dict:
            combined_dict[txt]["google_pos"] = gq.get("avg_position", 0.0)
            combined_dict[txt]["google_shows"] = gq.get("shows", 0)
            combined_dict[txt]["google_clicks"] = gq.get("clicks", 0)
            combined_dict[txt]["total_shows"] = None
            combined_dict[txt]["total_clicks"] = None
            combined_dict[txt]["in_google"] = True
        else:
            combined_dict[txt] = {
                "text": gq["text"],
                "yandex_pos": None,
                "yandex_shows": 0,
                "yandex_clicks": 0,
                "google_pos": gq.get("avg_position", 0.0),
                "google_shows": gq.get("shows", 0),
                "google_clicks": gq.get("clicks", 0),
                "total_shows": gq.get("shows", 0),
                "total_clicks": gq.get("clicks", 0),
                "in_yandex": False,
                "in_google": True,
            }

    combined_queries = list(combined_dict.values())
    google_period = google_data.get("period", {})
    for query in combined_queries:
        query.update(yandex_period=webmaster_period, google_period=google_period, totals_comparable=False,
                     coverage="Visible query rows from separate engines and periods; compare sources separately.")
        query["total_shows"] = None
        query["total_clicks"] = None
    combined_queries.sort(key=lambda query: max(query.get("yandex_shows") or 0, query.get("google_shows") or 0), reverse=True)

    # 6. Calculate Yandex Daily Dynamics and Phrase Movements
    yandex_daily_dynamics = []
    prev_y_pos = None
    prev_y_clicks = None
    prev_y_shows = None
    for dt in sorted(wm_daily_raw.keys()):
        d_val = wm_daily_raw[dt]
        d_clicks = d_val["clicks"]
        d_shows = d_val["shows"]
        query_metrics = d_val["query_metrics"]
        position_weight = sum(item.get("position", 0.0) * item.get("impressions", 0) for item in query_metrics.values())
        position_impressions = sum(item.get("impressions", 0) for item in query_metrics.values() if "position" in item)
        d_avg_pos = round(position_weight / position_impressions, 1) if position_impressions else None
        q_count = sum(1 for item in query_metrics.values() if "position" in item)
        pos_delta = round(prev_y_pos - d_avg_pos, 1) if prev_y_pos is not None and d_avg_pos is not None else None
        clicks_delta = d_clicks - prev_y_clicks if prev_y_clicks is not None else 0
        shows_delta = d_shows - prev_y_shows if prev_y_shows is not None else 0
        trend = "up" if pos_delta and pos_delta > 0 else ("down" if pos_delta and pos_delta < 0 else "stable")
        yandex_daily_dynamics.append({
            "date": dt,
            "clicks": d_clicks,
            "shows": d_shows,
            "avg_position": d_avg_pos,
            "queries_count": q_count,
            "coverage": "Visible query rows only; not property totals.",
            "clicks_delta": clicks_delta,
            "shows_delta": shows_delta,
            "pos_delta": pos_delta,
            "trend": trend
        })
        prev_y_pos = d_avg_pos
        prev_y_clicks = d_clicks
        prev_y_shows = d_shows

    yandex_query_daily_dynamics = yandex_daily_dynamics
    yandex_daily_dynamics = full_yandex_daily

    yandex_phrase_dynamics = []
    for q_text, d_map in yandex_phrase_history.items():
        sorted_dates = sorted(d_map.keys())
        if len(sorted_dates) >= 2:
            last_d = sorted_dates[-1]
            prev_d = sorted_dates[-2]
            pos_latest = d_map[last_d]
            pos_prev = d_map[prev_d]
            change = round(pos_prev - pos_latest, 1)
            yandex_phrase_dynamics.append({
                "text": q_text,
                "engine": "yandex",
                "current_pos": pos_latest,
                "prev_pos": pos_prev,
                "delta": change,
                "trend": "up" if change > 0 else ("down" if change < 0 else "stable")
            })
    yandex_phrase_dynamics.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # Do not mix incomplete Metrika today traffic with delayed search-console days.
    google_dynamics = google_data.get("daily_dynamics", [])
    today_progress = {
        "status": "unavailable",
        "reason": "Today values are intentionally omitted: Metrika and search consoles have different completion times.",
        "date": None,
    }

    # 8. Build Combined Daily Dynamics (All Dates)
    all_dates = sorted(list(set([d["date"] for d in yandex_daily_dynamics] + [d["date"] for d in google_dynamics])))
    y_by_date = {d["date"]: d for d in yandex_daily_dynamics}
    g_by_date = {d["date"]: d for d in google_dynamics}

    combined_daily_dynamics = []
    for dt in all_dates:
        yd = y_by_date.get(dt, {})
        gd = g_by_date.get(dt, {})
        y_p = yd.get("avg_position")
        g_p = gd.get("avg_position")
        y_trend = yd.get("trend", "stable")
        g_trend = gd.get("trend", "stable")

        combined_daily_dynamics.append({
            "date": dt,
            "total_clicks": None,
            "total_shows": None,
            "totals_comparable": False,
            "coverage": "Resource totals with independent source timezones and publication states; compare engines separately.",
            "total_queries": None,
            "yandex": yd,
            "google": gd,
            "yandex_pos": y_p,
            "google_pos": g_p,
            "yandex_trend": y_trend,
            "google_trend": g_trend
        })

    all_phrase_dynamics = yandex_phrase_dynamics + google_data.get("phrase_dynamics", [])
    all_phrase_dynamics.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # Persist daily history
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        existing_history = {}
        if HISTORY_PATH.exists():
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                existing_history = json.load(f)
        for item in combined_daily_dynamics:
            previous = existing_history.get(item["date"], {})
            saved = {**item, "collected_at": now_iso}
            for engine in ("yandex", "google"):
                if (not item.get(engine) or (engine == "yandex" and daily_error)) and previous.get(engine):
                    saved[engine] = previous[engine]
                    saved[engine + "_collected_at"] = previous.get(engine + "_collected_at", previous.get("collected_at"))
                elif item.get(engine) and (engine != "yandex" or not daily_error):
                    saved[engine + "_collected_at"] = now_iso
            existing_history[item["date"]] = saved
        _write_snapshot(HISTORY_PATH, existing_history)
    except Exception as h_err:
        logger.warning("Could not persist SEO daily history: %s", h_err)
    
    collection_errors = {**{f"metrika_{key}": value for key, value in metrika_errors.items()},
                         **({"webmaster": wm_summary.get("error") or wm_queries.get("error")} if wm_summary.get("error") or wm_queries.get("error") else {}),
                         **({"webmaster_query_analytics": wm_analytics_error} if wm_analytics_error else {}),
                         **({"webmaster_daily": daily_error} if daily_error else {})}
    if google_data.get("status") != "active" or google_data.get("errors") or google_data.get("error"):
        collection_errors["google"] = google_data.get("errors") or google_data.get("error") or "Google analytics is unavailable."
    # Preserve summary metrics from previous snapshot when provider API is down
    sqi_val = wm_summary.get("sqi")
    searchable_pages_val = wm_summary.get("searchable_pages_count")
    excluded_pages_val = wm_summary.get("excluded_pages_count")
    summary_failed = bool(wm_summary.get("error"))
    summary_stale = summary_failed and prev_wm.get("component_status", {}).get("summary") in {"available", "stale"}
    if summary_stale:
        sqi_val = prev_wm.get("sqi")
        searchable_pages_val = prev_wm.get("searchable_pages")
        excluded_pages_val = prev_wm.get("excluded_pages")

    if wm_queries.get("error") and not queries_clean and prev_wm.get("top_queries"):
        queries_clean = prev_wm.get("top_queries", [])
    if wm_queries.get("error") and not growth_points and prev_wm.get("growth_points"):
        growth_points = prev_wm.get("growth_points", [])
    if wm_analytics_error and not yandex_phrase_dynamics and prev_wm.get("phrase_dynamics"):
        yandex_phrase_dynamics = prev_wm.get("phrase_dynamics", [])

    snapshot = {
        "schema_version": 2,
        "daily_schema_version": 1,
        "updated_at": now_iso,
        "collection_status": "partial" if collection_errors else "active",
        "collection_errors": collection_errors,
        "data_freshness": {
            "collected_at": now_iso,
            "webmaster": {"status": wm_freshness["status"],
                          "period": f"{webmaster_period['start_date']} — {webmaster_period['end_date']}" if webmaster_period["start_date"] and webmaster_period["end_date"] else "provider-defined; dates unavailable", "popular_queries_period": webmaster_period},
            "metrika": {"status": "error" if metrika_errors else "available", "period": metrika_period, "source": "all measured traffic", "timezone": metrika_period["timezone"]},
            "google": google_data.get("period", {}),
        },
        "sample_size_ready": sample_ready,
        "sample_visits": organic_conversion["visits"],
        "sample_source": "organic visits during the instrumented registration period",
        "sample_note": "300 organic visits over 28 completed instrumented days is an operational minimum, not proof of significance or uplift.",
        "sample_target": 300,
        "today_progress": today_progress,
        "daily_dynamics": combined_daily_dynamics[-30:],
        "phrase_dynamics": all_phrase_dynamics[:30],
        "webmaster": {
            "sqi": sqi_val,
            "searchable_pages": searchable_pages_val,
            "excluded_pages": excluded_pages_val,
            "error": wm_summary.get("error") or wm_queries.get("error") or wm_analytics_error or daily_error,
            "status": "partial" if (wm_summary.get("error") or wm_queries.get("error") or wm_analytics_error or daily_error) else "available",
            "freshness": wm_freshness,
            "component_status": {
                "summary": "stale" if summary_stale else "error" if summary_failed else "available",
                "query_sample": ("stale" if queries_clean else "error") if wm_queries.get("error") else "available",
                "daily_dynamics": ("stale" if full_yandex_daily else "error") if daily_error else "available",
                "phrase_dynamics": ("stale" if yandex_phrase_dynamics else "error") if wm_analytics_error else "available",
            },
            "daily_scope": "property_totals",
            "daily_period": {"start_date": daily_start, "end_date": daily_today, "timezone": "Europe/Moscow", "available_start_date": min((row["date"] for row in full_yandex_daily), default=None), "available_end_date": max((row["date"] for row in full_yandex_daily), default=None)},
            "period": webmaster_period,
            "query_coverage": "All returned popular queries after pagination; not all site searches.",
            "daily_coverage": "All-query resource totals; missing metrics remain unknown.",
            "top_queries": queries_clean[:50],
            "growth_points": growth_points[:15],
            "daily_dynamics": yandex_daily_dynamics,
            "query_daily_dynamics": yandex_query_daily_dynamics,
            "phrase_dynamics": yandex_phrase_dynamics[:25]
        },
        "google": google_data,
        "combined_queries": combined_queries[:100],
        "metrika": {
            "period_days": 28,
            "counter_id": counter_id,
            "period": metrika_period,
            "sampling": {key: m_totals.get(key) for key in ("sampled", "sample_share", "sample_size", "sample_space")},
            "api_query_timezone": m_totals.get("query", {}).get("timezone"),
            "counter_filter_robots": counter_info.get("counter", {}).get("filter_robots"),
            "source": "All measured traffic; consent and blockers limit coverage. Counter robot settings apply; explicit internal exclusions are not configured in this report.",
            "measurement_notes": [
                "Registration instrumentation starts 2026-09-30; conversion reports exclude that partial setup day and use completed full days from 2026-10-01.",
                "Tracking recovered on 2026-11-08. The first full explicit opt-in baseline day is 2026-11-15.",
                "Total goal reaches are event volume and must not be treated as a conversion rate.",
            ],
            "error": "; ".join(f"{key}: {value}" for key, value in metrika_errors.items()) or None,
            "errors": metrika_errors,
            "visits": visits,
            "users": users,
            "pageviews": pageviews,
            "bounce_rate": bounce_rate,
            "avg_duration_seconds": duration_s,
            "sources": sources_clean,
            "top_pages": pages_clean,
            "goals": goals_clean,
            "total_goal_reaches": total_reaches,
            "primary_conversion": primary_conversion,
            "total_conversion_rate": primary_conversion["rate_percent"],
        },
        "recommendations": recommendations
    }
    _retain_metrika_components(snapshot["metrika"], prev_snap, now_iso)
    
    # Save snapshot locally
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _write_snapshot(SNAPSHOT_PATH, snapshot)
    except (OSError, TypeError, ValueError) as error:
        logger.warning("Could not persist SEO snapshot: %s", error)
        
    return snapshot


def get_cached_or_fresh_analytics(force_refresh: bool = False) -> dict:
    # Recheck freshness inside the lock so concurrent admin reads collect once.
    with _ANALYTICS_LOCK:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SNAPSHOT_PATH.with_suffix(".collection.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return _cached_or_collect(force_refresh)


def _cached_or_collect(force_refresh: bool) -> dict:
    if not force_refresh and SNAPSHOT_PATH.exists():
        try:
            with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
            collected_at = datetime.fromisoformat(snapshot["updated_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - collected_at).total_seconds()
            if snapshot.get("schema_version", 0) >= 2 and snapshot.get("daily_schema_version") == 1 and 0 <= age < 3600:
                return snapshot
        except Exception:
            pass

    return fetch_fresh_snapshot()


def build_seo_digest(data: dict) -> str:
    """Render observed metrics and unknown states without promises or fake defaults."""
    def shown(value):
        return "—" if value is None else escape(str(value))

    metrika = data.get("metrika", {})
    webmaster = data.get("webmaster", {})
    google = data.get("google", {})
    period = metrika.get("period", {})
    primary = metrika.get("primary_conversion", {})
    duration = metrika.get("avg_duration_seconds")
    duration_text = f"{duration // 60} мин {duration % 60} сек" if duration is not None else "—"
    primary_rate = primary.get("rate_percent") if primary.get("status") == "available" else None
    primary_text = f"{primary_rate}% ({shown(primary.get('goal_visits'))} из {shown(primary.get('visits'))} визитов)" if primary_rate is not None else escape(primary.get("reason") or "нет валидной цели или периода")
    growth_lines = []
    for item in webmaster.get("growth_points", [])[:4]:
        line = f"  • «{escape(str(item.get('text', '')))}» (Яндекс) — {shown(item.get('shows'))} показов (поз. {shown(item.get('avg_position'))})"
        if item.get("wordstat_demand") is not None and item.get("demand_origin_source", item.get("demand_source")) == "wordstat_api" and item.get("demand_period", {}).get("period_days") == 30:
            line += f"\n    └ Wordstat API: {shown(item['wordstat_demand'])} запросов за последние 30 дней провайдера; Россия; сбор {shown(item.get('demand_collected_at'))}"
        growth_lines.append(line)
    for item in google.get("growth_points", [])[:3]:
        growth_lines.append(f"  • «{escape(str(item.get('text', '')))}» (Google) — {shown(item.get('shows'))} показов (поз. {shown(item.get('avg_position'))})")
    goals_lines = [f"  • {escape(str(goal.get('name', 'Цель')))}: {shown(goal.get('reaches'))} достижений" for goal in metrika.get("goals", []) if (goal.get("reaches") or 0) > 0]
    queries_lines = []
    for engine, queries in (("Яндекс", webmaster.get("top_queries", [])[:4]), ("Google", google.get("top_queries", [])[:3])):
        for item in queries:
            queries_lines.append(f"  • {engine}: {escape(str(item.get('text', '')))} — {shown(item.get('shows'))} показов (поз. {shown(item.get('avg_position'))})")
    google_available = google.get("status") == "active" and not google.get("error") and not google.get("errors")
    google_line = (f"Google: {shown(google.get('total_impressions'))} показов, {shown(google.get('total_clicks'))} кликов; позиция {shown(google.get('avg_position'))}" if google_available else "Google: данные недоступны или неполны")
    status = "Данные собраны" if data.get("collection_status") == "active" else "Сбор частичный: проверьте ошибки источников в панели"
    return (f"📊 <b>SEO-Дайджест TenderLex</b>\n{status}\n"
            f"Метрика: {shown(period.get('start_date'))} — {shown(period.get('end_date'))}, {shown(period.get('timezone'))}\n"
            f"Посетители: {shown(metrika.get('users'))}; визиты: {shown(metrika.get('visits'))}\n"
            f"Время на сайте: {duration_text}; отказы: {shown(metrika.get('bounce_rate'))}%\n"
            f"Достижения всех целей (объем событий): {shown(metrika.get('total_goal_reaches'))}\n"
            f"Регистрации, конверсия визитов: {primary_text}\n"
            f"Период регистрации: {shown((primary.get('period') or {}).get('start_date'))} — {shown((primary.get('period') or {}).get('end_date'))}\n"
            f"Яндекс: {shown(webmaster.get('searchable_pages'))} страниц в поиске; ИКС {shown(webmaster.get('sqi'))}\n"
            f"{google_line}\n\n"
            f"<b>События целей:</b>\n" + ("\n".join(goals_lines) or "Нет подтвержденных достижений") + "\n\n"
            + "<b>Гипотезы для проверки:</b>\n" + ("\n".join(growth_lines) or "Недостаточно подтвержденных данных") + "\n\n"
            + "<b>Запросы по источникам:</b>\n" + ("\n".join(queries_lines) or "Нет подтвержденных запросов"))


async def send_seo_telegram_digest() -> dict:
    tokens = _load_env_tokens()
    bot_token = tokens["bot_token"]
    owner_id = tokens["owner_telegram_id"]
    if not bot_token or not owner_id:
        return {"ok": False, "error": "Bot token or owner Telegram ID not configured"}
    message = build_seo_digest(get_cached_or_fresh_analytics())
    bot = Bot(token=bot_token)
    try:
        await bot.send_message(chat_id=int(owner_id), text=message, parse_mode=ParseMode.HTML)
        return {"ok": True, "sent_to": owner_id}
    except Exception as error:
        return {"ok": False, "error": str(error)}
    finally:
        await bot.session.close()
