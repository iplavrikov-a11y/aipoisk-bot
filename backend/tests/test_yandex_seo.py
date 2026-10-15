from datetime import datetime, timezone
import pytest

@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    import app.yandex_seo as seo
    def forbidden(*args, **kwargs):
        pytest.fail("unexpected network request")
    monkeypatch.setattr(seo, "_http_json", forbidden)
    monkeypatch.setattr(seo.urllib.request, "urlopen", forbidden)

from app.yandex_seo import (
    _metric_chunks,
    _metrika_closed_period,
    build_primary_conversion,
    generate_ai_recommendations,
)


def test_recommendations_without_a_ready_sample_are_measurement_tasks_not_uplift_claims():
    recommendations = generate_ai_recommendations(
        [{"text": "поиск поставщиков", "avg_position": 5.0, "shows": 40}],
        {"primary_conversion": {"status": "unavailable", "reason": "goal tracking is not configured"}},
        sample_size_ready=False,
    )

    assert len(recommendations) == 1
    assert recommendations[0]["id"] == "rec_measurement_baseline"
    assert "%" not in recommendations[0]["impact"]
    assert "гипотеза" in recommendations[0]["rationale"].lower()


def test_primary_conversion_uses_unique_goal_visits_only_for_registered_registration_action():
    goals = [{
        "id": 42,
        "name": "Registration success",
        "type": "action",
        "conditions": [{"type": "exact", "url": "registration_success"}],
    }]

    conversion = build_primary_conversion(goals, {42: 3}, visits=20, primary_goal_id="42")

    assert {key: conversion[key] for key in ("status", "goal_id", "goal_name", "goal_visits", "rate_percent", "reason")} == {
        "status": "available",
        "goal_id": 42,
        "goal_name": "Registration success",
        "goal_visits": 3,
        "rate_percent": 15.0,
        "reason": None,
    }


def test_primary_conversion_does_not_relabel_legacy_url_goal_as_registration():
    goals = [{"id": 42, "name": "Кабинет посещение страницы", "type": "url", "conditions": []}]

    conversion = build_primary_conversion(goals, {42: 3}, visits=20, primary_goal_id="42")

    assert conversion["status"] == "unavailable"
    assert "registration_success" in conversion["reason"]


def test_metrika_closed_period_has_28_complete_counter_days():
    period = _metrika_closed_period("Europe/Moscow", now=datetime(2026, 9, 30, 12, tzinfo=timezone.utc))

    assert period["start_date"] == "2026-09-02"
    assert period["end_date"] == "2026-09-29"
    assert period["period_days"] == 28
    assert period["timezone"] == "Europe/Moscow"


def test_metrika_goal_metrics_are_limited_to_twenty_per_request():
    chunks = _metric_chunks([f"ym:s:goal{index}reaches" for index in range(41)])

    assert [len(chunk) for chunk in chunks] == [20, 20, 1]


def test_primary_missing_metric_is_unavailable():
    goals = [{"id": 42, "type": "action", "conditions": [{"type": "exact", "url": "registration_success"}]}]
    result = build_primary_conversion(goals, {}, visits=20, primary_goal_id="42")
    assert result["status"] == "unavailable"
    assert result["rate_percent"] is None


def test_ready_all_traffic_does_not_enable_recommendations_with_invalid_primary_goal():
    recommendations = generate_ai_recommendations([], {"visits": 1000, "primary_conversion": {"status": "unavailable", "reason": "goal failed"}}, sample_size_ready=True)
    assert [item["id"] for item in recommendations] == ["rec_measurement_baseline"]


def test_env_file_primary_goal_and_environment_precedence(tmp_path, monkeypatch):
    import app.yandex_seo as seo
    env_path = tmp_path / ".env"
    env_path.write_text("YANDEX_METRIKA_TOKEN=file-token\nYANDEX_WEBMASTER_TOKEN=file-webmaster\nYANDEX_METRIKA_PRIMARY_GOAL_ID=42\nAIPOISK_OWNER_TELEGRAM_ID=99\n")
    monkeypatch.setattr(seo, "ENV_PATH", env_path)
    monkeypatch.setenv("YANDEX_METRIKA_TOKEN", "runtime-token")
    monkeypatch.setenv("YANDEX_WEBMASTER_TOKEN", "runtime-webmaster")
    monkeypatch.delenv("YANDEX_METRIKA_PRIMARY_GOAL_ID", raising=False)
    monkeypatch.delenv("AIPOISK_OWNER_TELEGRAM_ID", raising=False)
    result = seo._load_env_tokens()
    assert result["metrika"] == "runtime-token"
    assert result["webmaster"] == "runtime-webmaster"
    assert result["primary_goal_id"] == "42"
    assert result["owner_telegram_id"] == "99"


def test_primary_period_excludes_preinstrumentation_dates():
    from app.yandex_seo import _primary_measurement_period
    assert _primary_measurement_period({"start_date": "2026-09-02", "end_date": "2026-09-29", "timezone": "Europe/Moscow"}) is None
    result = _primary_measurement_period({"start_date": "2026-09-04", "end_date": "2026-10-01", "timezone": "Europe/Moscow"})
    assert result["start_date"] == "2026-10-01"
    assert result["end_date"] == "2026-10-01"
    assert result["period_days"] == 1


def _mock_snapshot(tmp_path, monkeypatch, fail_primary=False):
    import json
    from urllib.parse import parse_qs, urlparse
    import app.yandex_seo as seo
    import app.google_seo as google
    import app.yandex_wordstat as wordstat
    requests = []
    goals = [{"id": index, "name": f"goal {index}", "type": "action", "conditions": [{"type": "exact", "url": "registration_success" if index == 42 else f"event_{index}"}]} for index in range(1, 44)]
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 2, 12, tzinfo=timezone.utc).astimezone(tz or timezone.utc)
    class QueryResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps({"text_indicator_to_statistics": []}).encode()
    def fake_http(url, **kwargs):
        requests.append(url)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/v4/user"): return {"user_id": 1}
        if parsed.path.endswith("/summary"): return {"sqi": 10, "searchable_pages_count": 57, "excluded_pages_count": 3}
        if parsed.path.endswith("/all/history"): return {"indicators": {}}
        if parsed.path.endswith("/popular"): return {"queries": [], "date_from": "2026-09-21", "date_to": "2026-09-27"}
        if parsed.path.endswith("/goals"): return {"goals": goals}
        if "/management/" in parsed.path: return {"counter": {"time_zone_name": "Europe/Moscow", "time_zone_offset": 180, "filter_robots": 1}}
        metrics = query.get("metrics", [""])[0].split(",")
        if "ym:s:goal42visits" in metrics: return {"error": "goal unavailable"} if fail_primary else {"totals": [20, 3], "sampled": False}
        if "dimensions" in query: return {"data": []}
        if metrics == ["ym:s:visits", "ym:s:users", "ym:s:pageviews", "ym:s:bounceRate", "ym:s:avgVisitDurationSeconds"]: return {"totals": [500, 100, 600, 20, 60], "sampled": False}
        return {"totals": [1] * len(metrics)}
    monkeypatch.setattr(seo, "datetime", FrozenDatetime)
    monkeypatch.setattr(seo, "_load_env_tokens", lambda: {"metrika": "test", "webmaster": "test", "counter_id": "123", "host_id": "https:test:443", "primary_goal_id": "42"})
    monkeypatch.setattr(seo, "_http_json", fake_http)
    monkeypatch.setattr(seo.urllib.request, "urlopen", lambda *args, **kwargs: QueryResponse())
    monkeypatch.setattr(google, "fetch_google_analytics", lambda **kwargs: {"status": "active", "errors": [], "top_queries": [], "daily_dynamics": [], "phrase_dynamics": []})
    monkeypatch.setattr(wordstat, "enrich_growth_points", lambda points: points)
    monkeypatch.setattr(seo, "DATA_DIR", tmp_path)
    monkeypatch.setattr(seo, "SNAPSHOT_PATH", tmp_path / "snapshot.json")
    monkeypatch.setattr(seo, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(seo, "RECS_STATE_PATH", tmp_path / "recs.json")
    return seo, requests


def test_snapshot_explicit_dates_chunks_and_primary_denominator(tmp_path, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    seo, requests = _mock_snapshot(tmp_path, monkeypatch)
    snapshot = seo.fetch_fresh_snapshot()
    period = snapshot["metrika"]["period"]
    assert (period["start_date"], period["end_date"]) == ("2026-09-04", "2026-10-01")
    assert snapshot["schema_version"] == 2
    assert snapshot["metrika"]["total_goal_reaches"] == 43
    queries = [parse_qs(urlparse(url).query) for url in requests if "/stat/" in url]
    assert all(len(item["metrics"][0].split(",")) <= 20 for item in queries)
    assert not any("daysAgo" in item["date1"][0] for item in queries)
    primary = snapshot["metrika"]["primary_conversion"]
    assert primary["status"] == "available"
    assert primary["visits"] == 20
    assert primary["rate_percent"] == 15.0
    assert primary["period"]["start_date"] == "2026-10-01"
    assert not snapshot["sample_size_ready"]
    assert snapshot["webmaster"]["period"]["start_date"] == "2026-09-21"


def test_primary_api_failure_collection_partial(tmp_path, monkeypatch):
    seo, requests = _mock_snapshot(tmp_path, monkeypatch, fail_primary=True)
    snapshot = seo.fetch_fresh_snapshot()
    assert snapshot["metrika"]["primary_conversion"]["status"] == "unavailable"
    assert snapshot["metrika"]["primary_conversion"]["rate_percent"] is None
    assert snapshot["collection_status"] == "partial"


def test_legacy_snapshot_rejected_inside_ttl(tmp_path, monkeypatch):
    import app.yandex_seo as seo
    path = tmp_path / "snapshot.json"
    path.write_text('{"metrika":{"total_conversion_rate":26.83}}')
    monkeypatch.setattr(seo, "SNAPSHOT_PATH", path)
    monkeypatch.setattr(seo, "fetch_fresh_snapshot", lambda: {"schema_version": 2})
    assert seo.get_cached_or_fresh_analytics() == {"schema_version": 2}


def test_digest_missing_metrics_and_estimated_wordstat_stay_unknown():
    from app.yandex_seo import build_seo_digest
    message = build_seo_digest({"collection_status": "partial", "metrika": {"avg_duration_seconds": None, "total_goal_reaches": None, "goals": [{"reaches": None}]}, "webmaster": {"growth_points": [{"text": "<query>", "shows": 12, "avg_position": 7, "wordstat_demand": 900, "demand_source": "estimated"}]}})
    assert "Wordstat API" not in message
    assert "потенциал в ТОП-3" not in message
    assert "Сбор частичный" in message
    assert "&lt;query&gt;" in message


def test_primary_extra_action_is_not_registration_only():
    goals = [{"id": 42, "type": "action", "conditions": [{"type": "exact", "url": "registration_success"}, {"type": "action", "value": "contact_click"}]}]
    result = build_primary_conversion(goals, {42: 5}, visits=20, primary_goal_id="42")
    assert result["status"] == "unavailable"


def test_missing_source_metrics_report_error_without_crashing_snapshot(tmp_path, monkeypatch):
    seo, requests = _mock_snapshot(tmp_path, monkeypatch)
    fake_http = seo._http_json
    def malformed_sources(url, **kwargs):
        if "dimensions=ym:s:lastSignTrafficSource" in url:
            return {"data": [{"dimensions": [{"name": "organic"}], "metrics": [None, 4]}]}
        return fake_http(url, **kwargs)
    monkeypatch.setattr(seo, "_http_json", malformed_sources)
    snapshot = seo.fetch_fresh_snapshot()
    assert snapshot["collection_status"] == "partial"
    assert snapshot["metrika"]["sources"] == []
    assert "sources" in snapshot["metrika"]["errors"]


def test_missing_aggregate_totals_remain_null(tmp_path, monkeypatch):
    seo, requests = _mock_snapshot(tmp_path, monkeypatch)
    fake_http = seo._http_json
    def missing_totals(url, **kwargs):
        if "metrics=ym:s:visits,ym:s:users,ym:s:pageviews" in url:
            return {}
        return fake_http(url, **kwargs)
    monkeypatch.setattr(seo, "_http_json", missing_totals)
    snapshot = seo.fetch_fresh_snapshot()
    assert snapshot["metrika"]["visits"] is None
    assert snapshot["metrika"]["bounce_rate"] is None
    assert snapshot["collection_status"] == "partial"


def test_wordstat_forecast_cannot_leak_into_new_digest():
    from app.yandex_seo import build_seo_digest
    message = build_seo_digest({"webmaster": {"growth_points": [{"text": "query", "wordstat_demand": 10, "demand_source": "cache", "demand_origin_source": "wordstat_api", "demand_period": {"period_days": 30}, "demand_collected_at": "2026-09-30", "top3_potential_clicks": 3}]}})
    assert "Wordstat API: 10" in message
    assert "+3" not in message
    assert "/мес" not in message


def test_primary_zero_unique_visits_does_not_mean_missing_metric():
    goals = [{"id": 42, "type": "action", "conditions": [{"type": "exact", "url": "registration_success"}]}]
    result = build_primary_conversion(goals, {42: 0}, visits=20, primary_goal_id="42")
    assert result["status"] == "available"
    assert result["rate_percent"] == 0.0


def test_invalid_timezone_is_marked_error_and_fallback_label_is_utc():
    result = _metrika_closed_period("Definitely/Invalid", now=datetime(2026, 9, 30, 12, tzinfo=timezone.utc))
    assert result["timezone"] == "UTC"
    assert result["timezone_valid"] is False
    assert result["error"]


def test_missing_yandex_indicators_remain_null(tmp_path, monkeypatch):
    seo, requests = _mock_snapshot(tmp_path, monkeypatch)
    fake_http = seo._http_json
    def partial_queries(url, **kwargs):
        if "/popular?" in url:
            return {"queries": [{"query_text": "unknown metrics", "indicators": {"TOTAL_SHOWS": 40}}], "date_from": "2026-09-21", "date_to": "2026-09-27"}
        return fake_http(url, **kwargs)
    monkeypatch.setattr(seo, "_http_json", partial_queries)
    snapshot = seo.fetch_fresh_snapshot()
    query = snapshot["webmaster"]["top_queries"][0]
    assert query["shows"] == 40
    assert query["clicks"] is None
    assert query["avg_position"] is None
    assert query["ctr_percent"] is None


def test_combined_queries_do_not_sum_different_engine_periods(tmp_path, monkeypatch):
    import app.google_seo as google
    seo, requests = _mock_snapshot(tmp_path, monkeypatch)
    fake_http = seo._http_json
    def query_data(url, **kwargs):
        if "/popular?" in url:
            return {"queries": [{"query_text": "same phrase", "indicators": {"TOTAL_SHOWS": 40, "TOTAL_CLICKS": 3, "AVG_SHOW_POSITION": 2}}], "date_from": "2026-09-21", "date_to": "2026-09-27"}
        return fake_http(url, **kwargs)
    monkeypatch.setattr(seo, "_http_json", query_data)
    monkeypatch.setattr(google, "fetch_google_analytics", lambda **kwargs: {"status": "active", "errors": [], "period": {"start_date": "2026-09-02", "end_date": "2026-09-29"}, "top_queries": [{"text": "same phrase", "shows": 100, "clicks": 5}], "daily_dynamics": []})
    snapshot = seo.fetch_fresh_snapshot()
    query = snapshot["combined_queries"][0]
    assert query["yandex_shows"] == 40
    assert query["google_shows"] == 100
    assert query["total_shows"] is None
    assert query["total_clicks"] is None
    assert query["totals_comparable"] is False
    assert query["yandex_period"]["start_date"] == "2026-09-21"
    assert query["google_period"]["start_date"] == "2026-09-02"


def test_unhealthy_search_sources_gate_even_large_organic_registration_sample(tmp_path, monkeypatch):
    import app.google_seo as google
    seo, requests = _mock_snapshot(tmp_path, monkeypatch)
    fake_http = seo._http_json
    def large_primary(url, **kwargs):
        if "ym:s:goal42visits" in url:
            return {"totals": [1000, 100], "sampled": False}
        return fake_http(url, **kwargs)
    monkeypatch.setattr(seo, "_http_json", large_primary)
    monkeypatch.setattr(seo, "_primary_measurement_period", lambda period: {**period, "period_days": 28})
    monkeypatch.setattr(google, "fetch_google_analytics", lambda **kwargs: {"status": "partial", "errors": ["queries unavailable"], "top_queries": []})
    snapshot = seo.fetch_fresh_snapshot()
    assert snapshot["sample_visits"] == 1000
    assert not snapshot["sample_size_ready"]
    assert snapshot["recommendations"][0]["id"] == "rec_measurement_baseline"


def test_registration_period_excludes_partial_setup_day_september_30():
    from app.yandex_seo import _primary_measurement_period
    assert _primary_measurement_period({"start_date": "2026-09-03", "end_date": "2026-09-30", "timezone": "Europe/Moscow"}) is None
    result = _primary_measurement_period({"start_date": "2026-09-04", "end_date": "2026-10-01", "timezone": "Europe/Moscow"})
    assert result["start_date"] == "2026-10-01"
    assert result["period_days"] == 1
    assert result["instrumented_from"] == "2026-09-30"
    assert result["full_days_from"] == "2026-10-01"
