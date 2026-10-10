"""Prevent misleading SEO comparisons and unsafe persisted diagnostics."""
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seo_growth_monitor.py"
spec = importlib.util.spec_from_file_location("seo_growth_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def period(start="2026-09-01", end="2026-09-28", timezone="Europe/Moscow"):
    return {"start_date": start, "end_date": end, "timezone": timezone,
            "period_days": 28, "is_closed": True}


def instrumented_period():
    return {**period("2026-10-01", "2026-10-28"), "instrumented_from": "2026-09-30", "full_days_from": "2026-10-01"}


def snapshot():
    return {
        "updated_at": "2026-10-01T05:00:00+00:00",
        "collection_status": "active",
        "google": {"status": "active", "totals_status": "available",
                   "period": period(timezone="America/Los_Angeles"),
                   "property_totals": {"impressions": 895, "clicks": 9, "avg_position": 24.98, "ctr_percent": 1.01}},
        "webmaster": {"error": None, "period": period(), "searchable_pages": 57,
                      "excluded_pages": 3, "sqi": 10},
        "metrika": {"error": None, "period": period(), "visits": 31, "users": 17,
                    "primary_conversion": {"status": "unavailable", "period": None,
                                           "organic": {"status": "unavailable", "period": None}}},
    }


def test_separate_periods_and_no_invented_registration_zero():
    data = monitor.summarize(snapshot())
    assert data["sources"]["google"]["metrics"]["clicks"] == 9
    assert data["sources"]["metrika"]["metrics"]["visits"] == 31
    assert data["sources"]["google"]["period"]["timezone"] != data["sources"]["metrika"]["period"]["timezone"]
    assert data["sources"]["registration_organic"]["metrics"]["goal_visits"] is None
    assert data["sample_ready"] is False


def test_unavailable_totals_are_not_zero_or_success():
    data = snapshot()
    data["google"].update(totals_status="error", property_totals={"impressions": 0, "clicks": 0})
    result = monitor.summarize(data)
    assert result["sources"]["google"]["status"] == "unavailable"
    assert result["sources"]["google"]["metrics"]["clicks"] is None


def test_real_zero_is_preserved():
    data = snapshot()
    data["google"]["property_totals"]["clicks"] = 0
    assert monitor.summarize(data)["sources"]["google"]["metrics"]["clicks"] == 0


def test_overlapping_periods_cannot_be_reported_as_growth():
    previous = {"status": "available", "period": period(), "metrics": {"clicks": 3}}
    current = {"status": "available", "period": period("2026-09-02", "2026-09-29"), "metrics": {"clicks": 9}}
    assert monitor.compare_source(current, previous)["status"] == "not_comparable"


def test_adjacent_equal_closed_periods_can_be_compared():
    previous = {"status": "available", "period": period(), "metrics": {"clicks": 3}}
    current = {"status": "available", "period": period("2026-09-29", "2026-10-26"), "metrics": {"clicks": 9}}
    result = monitor.compare_source(current, previous)
    assert result["status"] == "comparable"
    assert result["changes"]["clicks"] == {"previous": 3, "current": 9, "delta": 6}


@pytest.mark.parametrize("change", [{"is_closed": False}, {"timezone": "UTC"}, {"end_date": "2026-10-25"}])
def test_mismatched_periods_are_refused(change):
    previous = {"status": "available", "period": period(), "metrics": {"clicks": 3}}
    new_period = {**period("2026-09-29", "2026-10-26"), **change}
    current = {"status": "available", "period": new_period, "metrics": {"clicks": 9}}
    assert monitor.compare_source(current, previous)["status"] == "not_comparable"


def test_daily_history_is_idempotent_and_diagnostics_are_allowlisted(tmp_path):
    data = snapshot()
    data["private"] = "SECRET-CUSTOMER-CONTENT"
    data["collection_errors"] = {"google": "OAuth SECRET-CREDENTIAL"}
    first = monitor.summarize(data)
    monitor.persist(first, tmp_path)
    data["google"]["property_totals"]["clicks"] = 10
    second = monitor.summarize(data)
    monitor.persist(second, tmp_path)
    assert len(list((tmp_path / "history").glob("*.json"))) == 1
    assert json.loads((tmp_path / "latest.json").read_text())["sources"]["google"]["metrics"]["clicks"] == 10
    combined = "".join(p.read_text() for p in tmp_path.rglob("*") if p.is_file())
    assert "SECRET" not in combined
    assert "Не доказано" in (tmp_path / "latest.md").read_text()


def test_sampling_or_incomplete_instrumentation_never_unlocks_uplift_claim():
    data = snapshot()
    goal = {"status": "available", "period": period(), "visits": 500, "goal_visits": 20,
            "rate_percent": 4, "sampling": {"sampled": True}}
    data["metrika"]["primary_conversion"] = {**goal, "organic": goal}
    assert monitor.summarize(data)["sample_ready"] is False


def test_funnel_never_queries_before_a_full_instrumented_day():
    calls = []
    result = monitor.collect_funnel(snapshot(), {}, lambda *a, **k: calls.append(a))
    assert calls == []
    assert result["all"]["status"] == "not_ready"


def test_funnel_uses_exact_js_goals_unique_visits_and_matching_organic_filter():
    from urllib.parse import parse_qs, urlparse
    data = snapshot()
    data["metrika"]["primary_conversion"]["period"] = instrumented_period()
    data["metrika"]["goals"] = [
        {"id": 10, "type": "action", "conditions": [{"type": "exact", "url": "task_started"}]},
        {"id": 11, "type": "action", "conditions": [{"type": "exact", "url": "result_downloaded"}]},
    ]
    calls = []
    def query(url, **kwargs):
        calls.append(parse_qs(urlparse(url).query))
        return {"totals": [20, 7, 3], "sampled": False}
    result = monitor.collect_funnel(data, {"metrika": "NEVER-PERSIST", "counter_id": "1"}, query)
    assert len(calls) == 2
    assert calls[0]["metrics"] == ["ym:s:visits,ym:s:goal10visits,ym:s:goal11visits"]
    assert calls[1]["filters"] == ["ym:s:lastSignTrafficSource=='organic'"]
    assert result["organic"]["metrics"]["result_downloaded_visits"] == 3
    assert result["organic"]["sequence_proven"] is False


def test_funnel_rejects_legacy_goal_and_missing_provider_totals():
    data = snapshot()
    data["metrika"]["primary_conversion"]["period"] = instrumented_period()
    data["metrika"]["goals"] = [{"id": 10, "type": "url", "conditions": [{"type": "exact", "url": "task_started"}]}]
    calls = []
    result = monitor.collect_funnel(data, {"metrika": "PRIVATE", "counter_id": "1"}, lambda *a, **k: calls.append(a))
    assert not calls
    assert result["all"]["status"] == "unavailable"


def test_active_snapshot_fails_success_gate_when_required_funnel_is_unavailable():
    data = snapshot()
    data["metrika"]["primary_conversion"]["period"] = instrumented_period()
    data["funnel"] = {"all": {"status": "unavailable", "period": instrumented_period(), "metrics": {}},
                      "organic": {"status": "unavailable", "period": instrumented_period(), "metrics": {}}}
    summary = monitor.summarize(data)
    assert summary["collection_complete"] is False


def test_cli_returns_nonzero_for_required_funnel_failure(tmp_path, monkeypatch):
    data = snapshot()
    data["metrika"]["primary_conversion"]["period"] = instrumented_period()
    data["funnel"] = {"all": {"status": "unavailable", "period": instrumented_period(), "metrics": {}},
                      "organic": {"status": "unavailable", "period": instrumented_period(), "metrics": {}}}
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(monitor.sys, "argv", ["seo_growth_monitor.py", "--snapshot", str(snapshot_path), "--output", str(tmp_path / "out")])
    assert monitor.main() == 1


def test_not_ready_funnel_before_first_full_day_is_not_a_collection_error():
    data = snapshot()
    data["funnel"] = monitor.collect_funnel(data, {}, lambda *args, **kwargs: None)
    summary = monitor.summarize(data)
    assert summary["sources"]["task_goals_all"]["status"] == "not_ready"
    assert summary["collection_complete"] is True


def test_funnel_non_object_response_is_unavailable_without_traceback():
    data = snapshot()
    data["metrika"]["primary_conversion"]["period"] = instrumented_period()
    data["metrika"]["goals"] = [
        {"id": 10, "type": "action", "conditions": [{"type": "exact", "url": "task_started"}]},
        {"id": 11, "type": "action", "conditions": [{"type": "exact", "url": "result_downloaded"}]},
    ]
    result = monitor.collect_funnel(data, {"metrika": "TOKEN", "counter_id": "1"}, lambda *args, **kwargs: [])
    assert result["all"]["status"] == "unavailable"
    assert result["organic"]["status"] == "unavailable"


def test_coverage_marker_mismatch_refuses_comparison():
    previous = {"status": "available", "period": {**period(), "full_days_from": "2026-10-01"}, "metrics": {"clicks": 3}}
    current = {"status": "available", "period": {**period("2026-09-29", "2026-10-26"), "full_days_from": "2026-10-02"}, "metrics": {"clicks": 9}}
    assert monitor.compare_source(current, previous)["status"] == "not_comparable"


def test_yandex_popular_sample_is_annotated_and_index_has_observed_at():
    data = snapshot()
    data["webmaster"]["top_queries"] = [{"shows": 10, "clicks": 2}, {"shows": 5, "clicks": 1}]
    summary = monitor.summarize(data)
    sample = summary["sources"]["yandex_popular_query_sample"]
    assert sample["metrics"] == {"impressions": 15, "clicks": 3, "visible_query_rows": 2}
    assert "not all site searches" in sample["annotation"]["coverage"]
    assert summary["sources"]["yandex_index"]["period"] is None
    assert summary["sources"]["yandex_index"]["observed_at"].endswith("+00:00")


def test_sampled_funnel_is_explicitly_partial_and_keeps_sampling_marker():
    data = snapshot()
    data["funnel"] = {"all": {"status": "available", "period": instrumented_period(),
                               "metrics": {"visits": 10, "task_started_visits": 2, "result_downloaded_visits": 1}, "sampled": True},
                      "organic": {"status": "available", "period": instrumented_period(),
                                  "metrics": {"visits": 5, "task_started_visits": 1, "result_downloaded_visits": 1}, "sampled": True}}
    summary = monitor.summarize(data)
    assert summary["sources"]["task_goals_all"]["status"] == "partial"
    assert summary["sources"]["task_goals_all"]["sampling"] == {"sampled": True}


def test_first_closed_instrumented_day_requires_funnel_goals():
    data = snapshot()
    data['updated_at'] = '2026-10-02T05:00:00+00:00'
    data['metrika']['primary_conversion']['period'] = {**instrumented_period(), 'end_date':'2026-10-01','period_days':1}
    data['funnel'] = monitor.collect_funnel(data, {}, lambda *args, **kwargs: None)
    assert data['funnel']['all']['status'] == 'unavailable'
    assert monitor.summarize(data)['collection_complete'] is False


def test_missing_primary_period_after_cutoff_is_not_not_ready_success():
    data = snapshot()
    data['updated_at'] = '2026-10-02T05:00:00+00:00'
    data['funnel'] = monitor.collect_funnel(data, {}, lambda *args, **kwargs: None)
    assert data['funnel']['all']['status'] == 'unavailable'
    assert monitor.summarize(data)['collection_complete'] is False


def test_different_metric_sets_are_not_comparable():
    previous = {'status':'available','period':period(),'metrics':{'clicks':3}}
    current = {'status':'available','period':period('2026-09-29','2026-10-26'),'metrics':{'clicks':9,'impressions':30}}
    assert monitor.compare_source(current,previous)['status'] == 'not_comparable'


def test_metrika_sampling_is_preserved_and_never_compared_as_exact():
    data = snapshot()
    data['metrika']['sampling'] = {'sampled':True,'sample_share':0.5,'sample_size':15,'sample_space':30}
    result = monitor.summarize(data)['sources']['metrika']
    assert result['status'] == 'partial'
    assert result['sampling']['sample_share'] == 0.5


def test_missing_registration_after_first_full_day_prevents_complete():
    data = snapshot()
    data['updated_at'] = '2026-10-02T05:00:00+00:00'
    data['funnel'] = {s:{'status':'available','period':instrumented_period(),'metrics':{'visits':1,'task_started_visits':0,'result_downloaded_visits':0}} for s in ('all','organic')}
    assert monitor.summarize(data)['collection_complete'] is False


def test_full_unsampled_periods_compare_despite_different_sample_population():
    previous = {'status':'available','period':period(),'metrics':{'visits':31},'sampling':{'sampled':False,'sample_share':1,'sample_size':31,'sample_space':31}}
    current = {'status':'available','period':period('2026-09-29','2026-10-26'),'metrics':{'visits':50},'sampling':{'sampled':False,'sample_share':1,'sample_size':50,'sample_space':50}}
    assert monitor.compare_source(current,previous)['status'] == 'comparable'
