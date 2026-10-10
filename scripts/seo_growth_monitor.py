#!/usr/bin/env python3
"""Collect aggregate SEO evidence locally; never send messages or change a site."""
import argparse
from datetime import date, datetime
import fcntl
import json
import math
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "seo_growth"
PERIOD_FIELDS = ("start_date", "end_date", "timezone", "period_days", "is_closed", "data_state", "instrumented_from", "full_days_from")
SAMPLING_FIELDS = ("sampled", "sample_share", "sample_size", "sample_space")


def clean_period(value):
    return {key: value.get(key) for key in PERIOD_FIELDS if key in value} if isinstance(value, dict) else None


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def clean_sampling(value):
    return {key: value.get(key) for key in SAMPLING_FIELDS if key in value} if isinstance(value, dict) else None


def source(status, period, metrics, *, sampling=None, annotation=None, observed_at=None):
    available = status in {"available", "partial"}
    result = {"status": status if status in {"available", "partial", "not_ready"} else "unavailable",
              "period": clean_period(period),
              "metrics": {key: number(value) if available else None for key, value in metrics.items()}}
    if sampling is not None:
        result["sampling"] = clean_sampling(sampling)
    if annotation is not None:
        result["annotation"] = annotation
    if observed_at is not None:
        result["observed_at"] = observed_at
    return result


def registration(value):
    status = value.get("status")
    sampling = value.get("sampling")
    if status == "available" and isinstance(sampling, dict) and sampling.get("sampled") is True:
        status = "partial"
    return source(status, value.get("period"),
                  {key: value.get(key) for key in ("visits", "goal_visits", "rate_percent")}, sampling=sampling)


def collect_funnel(snapshot, tokens, http_json):
    """Observe goal visits separately; these counts do not prove an ordered cohort."""
    metrika = snapshot.get("metrika", {})
    period = metrika.get("primary_conversion", {}).get("period")
    unavailable = {"status": "unavailable", "period": clean_period(period),
                   "metrics": {"visits": None, "task_started_visits": None, "result_downloaded_visits": None},
                   "sequence_proven": False, "sampled": None}
    not_ready = {**unavailable, "status": "not_ready"}
    empty = {"all": dict(unavailable), "organic": dict(unavailable)}
    observed = datetime.fromisoformat(snapshot["updated_at"].replace("Z", "+00:00"))
    # First full instrumented Moscow day closes at midnight on October 2.
    if not period and observed.astimezone(ZoneInfo("Europe/Moscow")).date() < date(2026, 10, 2):
        return {"all": dict(not_ready), "organic": dict(not_ready)}
    if (not period or not period.get("is_closed") or period.get("start_date", "") < "2026-10-01"
            or period.get("full_days_from") != "2026-10-01" or not 1 <= (period.get("period_days") or 0) <= 28):
        return empty
    ids = {}
    for goal in metrika.get("goals", []):
        conditions = goal.get("conditions", [])
        if (goal.get("type") not in {"action", "javascript"} or len(conditions) != 1
                or conditions[0].get("type") != "exact" or not str(goal.get("id", "")).isdigit()):
            continue
        event = conditions[0].get("url")
        if event in {"task_started", "result_downloaded"}:
            if event in ids:
                return empty  # Ambiguous goal definitions must not silently change history.
            ids[event] = int(goal["id"])
    if len(ids) != 2 or not tokens.get("metrika") or not tokens.get("counter_id"):
        return empty
    params = {"ids": tokens["counter_id"], "date1": period["start_date"], "date2": period["end_date"],
              "accuracy": "full", "metrics": f"ym:s:visits,ym:s:goal{ids['task_started']}visits,ym:s:goal{ids['result_downloaded']}visits"}
    result = {}
    for segment in ("all", "organic"):
        query = dict(params)
        if segment == "organic":
            query["filters"] = "ym:s:lastSignTrafficSource=='organic'"
        response = http_json("https://api-metrika.yandex.net/stat/v1/data?" + urlencode(query),
                             headers={"Authorization": "OAuth " + tokens["metrika"]}, timeout=15)
        totals = response.get("totals") if isinstance(response, dict) else None
        valid = (isinstance(response, dict) and not response.get("error") and not response.get("errors") and isinstance(totals, list)
                 and len(totals) == 3 and all(number(value) is not None and value >= 0 for value in totals)
                 and all(value <= totals[0] for value in totals[1:]))
        if not valid:
            result[segment] = dict(unavailable)
        else:
            result[segment] = {"status": "available", "period": clean_period(period),
                               "metrics": dict(zip(unavailable["metrics"], totals)),
                               "sequence_proven": False, **clean_sampling(response)}
    return result


def summarize(snapshot):
    """Allowlist numbers and periods; do not persist arbitrary API error text or URLs."""
    google = snapshot.get("google", {})
    totals = google.get("property_totals", {})
    webmaster = snapshot.get("webmaster", {})
    metrika = snapshot.get("metrika", {})
    primary = metrika.get("primary_conversion", {})
    organic = primary.get("organic", {})
    updated = datetime.fromisoformat(snapshot["updated_at"].replace("Z", "+00:00"))
    if updated.tzinfo is None:
        raise ValueError("Snapshot must have an explicit collection timezone")
    top_queries = webmaster.get("top_queries") if isinstance(webmaster.get("top_queries"), list) else []

    def summed_query_metric(name):
        values = [number(query.get(name)) for query in top_queries if isinstance(query, dict)]
        return sum(value for value in values if value is not None) if values else None

    popular_annotation = {
        "coverage": "Sum of visible provider-returned popular-query rows; not all site searches or property totals.",
        "visible_query_rows": len(top_queries),
    }
    sources = {
        "google": source("available" if google.get("totals_status") == "available" else "unavailable", google.get("period"),
                         {key: totals.get(key) for key in ("impressions", "clicks", "ctr_percent", "avg_position")}),
        "yandex_index": source("available" if not webmaster.get("error") and webmaster.get("searchable_pages") is not None else "unavailable",
                               None, {key: webmaster.get(key) for key in ("searchable_pages", "excluded_pages", "sqi")},
                               annotation="Point-in-time index observation; it has no traffic period.", observed_at=updated.isoformat()),
        "yandex_popular_query_sample": source("available" if not webmaster.get("error") and top_queries else "unavailable",
                                               webmaster.get("period"),
                                               {"impressions": summed_query_metric("shows"), "clicks": summed_query_metric("clicks"),
                                                "visible_query_rows": len(top_queries)}, annotation=popular_annotation),
        "metrika": source(("partial" if (metrika.get("sampling") or {}).get("sampled") is True else "available") if not metrika.get("error") and metrika.get("visits") is not None else "unavailable",
                          metrika.get("period"), {key: metrika.get(key) for key in ("visits", "users", "pageviews", "bounce_rate", "avg_duration_seconds")}, sampling=metrika.get("sampling")),
        "registration_all": registration(primary),
        "registration_organic": registration(organic),
    }
    sampled = organic.get("sampling", {}).get("sampled")
    organic_period = organic.get("period") or {}
    ready = (organic.get("status") == "available" and (number(organic.get("visits")) or 0) >= 300
             and organic_period.get("period_days") == 28 and sampled is False
             and organic_period.get("is_closed") is True)
    funnel = snapshot.get("funnel", {})
    for segment in ("all", "organic"):
        value = funnel.get(segment, {})
        funnel_status = value.get("status")
        if funnel_status == "available" and value.get("sampled") is True:
            funnel_status = "partial"
        sources[f"task_goals_{segment}"] = source(funnel_status, value.get("period"),
            {key: (value.get("metrics") or {}).get(key) for key in ("visits", "task_started_visits", "result_downloaded_visits")},
            sampling=clean_sampling(value) if value.get("sampled") is not None else None)
    base_sources_complete = all(sources[name]["status"] in {"available", "partial"} for name in ("google", "yandex_index", "metrika"))
    funnel_expected = any(sources[f"task_goals_{segment}"]["status"] != "not_ready" for segment in ("all", "organic"))
    funnel_complete = all(sources[f"task_goals_{segment}"]["status"] in {"available", "partial"} for segment in ("all", "organic"))
    registration_expected = updated.astimezone(ZoneInfo("Europe/Moscow")).date() >= date(2026, 10, 2)
    registration_complete = all(sources[name]["status"] in {"available", "partial"} for name in ("registration_all", "registration_organic"))
    collection_complete = (snapshot.get("collection_status") == "active" and base_sources_complete
                           and (not funnel_expected or funnel_complete)
                           and (not registration_expected or registration_complete))
    return {"schema_version": 1, "collected_at": updated.isoformat(),
            "collection_date": updated.astimezone(ZoneInfo("Europe/Moscow")).date().isoformat(),
            "sources": sources, "sample_ready": ready, "seo_uplift_proven": False,
            "collection_complete": collection_complete,
            "notes": ["Different engines and periods are never added together.",
                      "300 organic visits is an operational minimum, not proof of significance or uplift.",
                      "Consent, blockers and counter filters limit Metrika coverage.",
                      "Registration full-day measurement starts 2026-10-01.",
                      "Goal visits are independent observations, not an ordered cohort or sequential conversion rate.",
                      "Yandex popular-query values are an annotated provider-returned sample, not sitewide search totals."]}


def compare_source(current, previous):
    invalid = {"status": "not_comparable", "changes": {},
               "reason": "Require adjacent, complete, equally long periods with identical timezone and coverage."}
    if (current.get("status") != "available" or previous.get("status") != "available"
            or set(current.get("metrics", {})) != set(previous.get("metrics", {}))
            or any((current.get("sampling") or {}).get(key) != (previous.get("sampling") or {}).get(key)
                   for key in ("sampled", "sample_share"))):
        return invalid
    a, b = current.get("period") or {}, previous.get("period") or {}
    try:
        a_start, a_end = date.fromisoformat(a["start_date"]), date.fromisoformat(a["end_date"])
        b_start, b_end = date.fromisoformat(b["start_date"]), date.fromisoformat(b["end_date"])
        a_days, b_days = (a_end - a_start).days + 1, (b_end - b_start).days + 1
        valid = (a.get("is_closed") is True and b.get("is_closed") is True
                 and bool(a.get("timezone")) and a.get("timezone") == b.get("timezone")
                 and a.get("data_state") == b.get("data_state")
                 and a.get("instrumented_from") == b.get("instrumented_from")
                 and a.get("full_days_from") == b.get("full_days_from")
                 and a_days > 0 and a_days == b_days == a.get("period_days") == b.get("period_days")
                 and (a_start - b_end).days == 1)
    except (KeyError, TypeError, ValueError):
        return invalid
    if not valid:
        return invalid
    changes = {}
    for key, value in current.get("metrics", {}).items():
        old = previous.get("metrics", {}).get(key)
        if number(value) is not None and number(old) is not None:
            changes[key] = {"previous": old, "current": value, "delta": round(value - old, 4)}
    return {"status": "comparable", "changes": changes, "previous_period": b,
            "reason": "Observed difference; it does not prove causality or statistical significance."}


def compare_history(summary, history):
    results = {}
    for name, current in summary["sources"].items():
        result = {"status": "not_comparable", "changes": {}, "reason": "No adjacent comparable historical period yet."}
        # Index counts are point-in-time states, not period totals.
        if name == "yandex_index":
            results[name] = {**result, "reason": "Index counts are point-in-time observations, not period traffic totals."}
            continue
        for item in reversed(history):
            result = compare_source(current, item.get("sources", {}).get(name, {}))
            if result["status"] == "comparable":
                break
        results[name] = result
    return results


def render_report(summary, comparisons):
    labels = {"google": "Google: весь ресурс", "yandex_index": "Яндекс: состояние индекса",
              "yandex_popular_query_sample": "Яндекс: выборка популярных запросов",
              "metrika": "Метрика: измеренные посещения", "registration_all": "Регистрации: весь измеренный трафик",
              "registration_organic": "Регистрации: органический трафик",
              "task_goals_all": "Запуски и скачивания: весь измеренный трафик",
              "task_goals_organic": "Запуски и скачивания: органический трафик"}
    metric_labels = {"impressions": "показы", "clicks": "клики", "ctr_percent": "CTR, %", "avg_position": "средняя позиция",
                     "searchable_pages": "страницы в поиске", "excluded_pages": "исключённые страницы", "sqi": "ИКС",
                     "visible_query_rows": "видимые строки запросов",
                     "visits": "визиты", "users": "посетители", "pageviews": "просмотры", "bounce_rate": "отказы, %",
                     "avg_duration_seconds": "среднее время, с", "goal_visits": "визиты с регистрацией", "rate_percent": "конверсия, %",
                     "task_started_visits": "визиты с запуском", "result_downloaded_visits": "визиты со скачиванием"}
    lines = [f"# TenderLex — наблюдение {summary['collection_date']}", "",
             "Рост SEO после изменений: **Не доказано**. Ниже фактические наблюдения, а не прогноз.", "",
             "| Источник | Период и часовой пояс | Измерения |", "|---|---|---|"]
    for name, item in summary["sources"].items():
        p = item.get("period") or {}
        window = (f"наблюдение {item['observed_at']}" if item.get("observed_at") else
                  f"{p.get('start_date', '—')} — {p.get('end_date', '—')}; {p.get('timezone', '—')}")
        measurements = "; ".join(f"{metric_labels.get(key, key)}: {value if value is not None else 'нет данных'}" for key, value in item["metrics"].items())
        status_label = "есть данные" if item["status"] == "available" else "частичная выборка" if item["status"] == "partial" else "нет данных"
        suffix = "; выборка неполная" if (item.get("sampling") or {}).get("sampled") is True else ""
        lines.append(f"| {labels[name]} ({status_label}) | {window} | {measurements}{suffix} |")
    lines.extend(["", "## Сопоставимые периоды", ""])
    for name, result in comparisons.items():
        if result["status"] != "comparable":
            lines.append(f"- {labels[name]}: сопоставимого периода пока нет; рост не вычислен.")
        else:
            lines.append(f"- {labels[name]}: " + "; ".join(f"{key} {value['previous']} → {value['current']} (изменение {value['delta']:+})"
                                                               for key, value in result["changes"].items()))
    lines.extend(["", "## Ограничения", "", "- Согласие на аналитику, блокировщики и фильтры счётчика ограничивают полноту Метрики.",
                  "- Первый полный день новых регистрационных целей — 1 октября 2026 года.",
                  "- Небольшая выборка не позволяет уверенно выбирать победителя по конверсии.",
                  "- Визиты с регистрацией, запуском и скачиванием считаются отдельно; это не подтверждение последовательности действий одного посетителя.",
                  "- 300 органических визитов — рабочий ориентир, не доказательство значимости.",
                  "- Сборщик не меняет сайт, не отправляет URL на переобход и не рассылает сообщения.", ""])
    return "\n".join(lines)


def atomic_write(path, content):
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def persist(summary, output):
    output = Path(output)
    history_dir = output / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    # A collector rerun replaces only this collection day, never other evidence.
    day = date.fromisoformat(summary["collection_date"]).isoformat()
    history = []
    for path in sorted(history_dir.glob("*.json")):
        if path.stem == day:
            continue
        history.append(json.loads(path.read_text(encoding="utf-8")))
    comparisons = compare_history(summary, history)
    content = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    atomic_write(history_dir / f"{day}.json", content)
    atomic_write(output / "latest.json", content)
    atomic_write(output / "comparisons.json", json.dumps(comparisons, ensure_ascii=False, indent=2) + "\n")
    atomic_write(output / "latest.md", render_report(summary, comparisons))
    if date.fromisoformat(day).weekday() == 0:
        weekly = output / "weekly"
        weekly.mkdir(exist_ok=True)
        atomic_write(weekly / f"{day}.md", render_report(summary, comparisons))


def configure_readonly_collector_paths(output):
    """Keep legacy snapshot writes inside the collector state directory when sandboxed."""
    from app import yandex_seo
    state = Path(output)
    yandex_seo.DATA_DIR = state
    yandex_seo.SNAPSHOT_PATH = state / "yandex_analytics_snapshot.json"
    yandex_seo.HISTORY_PATH = state / "seo_daily_history.json"
    yandex_seo.RECS_STATE_PATH = state / "seo_recommendations_state.json"
    credential_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if credential_dir:
        yandex_seo.ENV_PATH = Path(credential_dir) / "seo-monitor.env"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Use an existing snapshot; do not query APIs")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / ".collector.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.snapshot:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        else:
            sys.path.insert(0, str(ROOT / "backend"))
            configure_readonly_collector_paths(args.output)
            from app.yandex_seo import fetch_fresh_snapshot
            snapshot = fetch_fresh_snapshot()
            from app.yandex_seo import _load_env_tokens, _http_json
            snapshot["funnel"] = collect_funnel(snapshot, _load_env_tokens(), _http_json)
        summary = summarize(snapshot)
        persist(summary, args.output)
        print(json.dumps({"collection_date": summary["collection_date"], "collection_complete": summary["collection_complete"],
                          "sample_ready": summary["sample_ready"], "report": str(args.output / "latest.md")}, ensure_ascii=False))
        return 0 if summary["collection_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
