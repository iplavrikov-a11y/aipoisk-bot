"""Regression coverage for the read-only SEO indexation audit CLI."""
import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seo_indexation_audit.py"
spec = importlib.util.spec_from_file_location("seo_indexation_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_normalize_public_url_matches_root_and_trailing_slash_redirects():
    assert audit.normalize_public_url("https://TENDERLEX.ru") == "https://tenderlex.ru/"
    assert audit.normalize_public_url("https://tenderlex.ru/#fragment") == "https://tenderlex.ru/"
    assert audit.normalize_public_url("https://tenderlex.ru/guide/?utm_source=test") == "https://tenderlex.ru/guide"


def test_match_urls_uses_redirect_target_and_does_not_treat_root_slashes_as_different():
    result = audit.match_sitemap_urls(
        ["https://tenderlex.ru/", "https://tenderlex.ru/guide"],
        [{"url": "https://tenderlex.ru", "searchable": True},
         {"url": "https://tenderlex.ru/guide/", "searchable": False,
          "target_url": "https://tenderlex.ru/guide"}],
    )

    assert result["sitemap_urls"] == 2
    assert result["observed_urls"] == 2
    assert result["matched_urls"] == 2
    assert result["searchable_matches"] == 1
    assert result["not_searchable_matches"] == 1


def test_paginated_yandex_samples_uses_offset_until_reported_count():
    calls = []

    def get_page(offset, limit):
        calls.append((offset, limit))
        if offset == 0:
            return {"count": 205, "samples": [{"url": "https://tenderlex.ru/a"}] * 100}
        if offset == 100:
            return {"count": 205, "samples": [{"url": "https://tenderlex.ru/b"}] * 100}
        return {"count": 205, "samples": [{"url": "https://tenderlex.ru/c"}] * 5}

    result = audit.collect_paginated_samples(get_page, page_size=100)

    assert calls == [(0, 100), (100, 100), (200, 100)]
    assert result["status"] == "available"
    assert result["api_count"] == 205
    assert result["returned_count"] == 205


def test_missing_or_permission_error_remains_unknown_not_zero():
    result = audit.collect_paginated_samples(
        lambda offset, limit: {"error_code": "HOST_NOT_VERIFIED", "error": "OAuth top-secret"}
    )

    assert result["status"] == "unavailable"
    assert result["api_count"] is None
    assert result["returned_count"] is None
    assert "top-secret" not in result["error"]


def test_events_are_historical_and_do_not_create_current_exclusion_count():
    result = audit.build_event_history(
        {"status": "available", "api_count": 1, "items": [
            {"url": "https://tenderlex.ru/old", "event": "REMOVED_FROM_SEARCH", "excluded_url_status": "LOW_QUALITY"}
        ]}
    )

    assert result["scope"] == "historical_search_events"
    assert result["current_exclusion_count"] is None
    assert result["removed_event_count"] == 1


def test_google_inspection_failure_is_unknown_and_does_not_leak_credentials():
    result = audit.inspect_google_urls(
        ["https://tenderlex.ru/"],
        service_factory=lambda: (_ for _ in ()).throw(RuntimeError("service-account super-secret")),
        max_workers=2,
    )

    assert result["status"] == "unavailable"
    assert result["inspected_count"] is None
    assert result["unknown_count"] == 1
    assert "super-secret" not in result["error"]


def test_one_redirect_observation_does_not_prove_two_indexed_pages():
    result = audit.match_sitemap_urls(
        ["https://tenderlex.ru/old", "https://tenderlex.ru/new"],
        [{"url": "https://tenderlex.ru/old", "searchable": True, "target_url": "https://tenderlex.ru/new"}],
    )
    assert result["matched_urls"] == 1
    assert result["searchable_matches"] == 1


def test_conflicting_current_observations_remain_unknown_in_any_order():
    observations = [{'url':'https://tenderlex.ru/guide','searchable':True}, {'url':'https://tenderlex.ru/guide','searchable':False,'excluded_url_status':'LOW_QUALITY'}]
    for items in (observations, list(reversed(observations)), observations + observations[:1]):
        result = audit.match_sitemap_urls(['https://tenderlex.ru/guide'],items)
        assert result['searchable_matches'] == 0
        assert result['not_searchable_matches'] == 0
        assert result['unknown_matches'] == 1
        assert result['conflicting_matches'] == 1
