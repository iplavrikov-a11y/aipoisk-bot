from unittest.mock import MagicMock, patch
import pytest

from app.google_seo import fetch_google_analytics
from app.yandex_seo import fetch_fresh_snapshot


def test_fetch_google_analytics_success():
    mock_service = MagicMock()
    mock_searchanalytics = MagicMock()
    mock_query = MagicMock()
    def response_for(body):
        if body["dimensions"] == []:
            return {"rows": [{"clicks": 25, "impressions": 300, "ctr": 0.083, "position": 2.8}]}
        if body["dimensions"] == ["query"]:
            return {"rows": [
                {"keys": ["оценка рисков закупок"], "clicks": 5, "impressions": 100, "ctr": 0.05, "position": 4.5},
                {"keys": ["поиск поставщиков по тз"], "clicks": 20, "impressions": 200, "ctr": 0.10, "position": 2.0},
            ]}
        return {"rows": []}
    mock_query.execute.side_effect = lambda: response_for(mock_searchanalytics.query.call_args.kwargs["body"])
    mock_searchanalytics.query.return_value = mock_query
    mock_service.searchanalytics.return_value = mock_searchanalytics

    mock_sitemaps = MagicMock()
    mock_sitemaps_list = MagicMock()
    mock_sitemaps_list.execute.return_value = {
        "sitemap": [
            {
                "path": "https://tenderlex.ru/sitemap.xml",
                "lastSubmitted": "2026-08-25T00:00:00Z",
                "lastDownloaded": "2026-08-25T00:00:00Z",
                "isPending": False,
                "warnings": 0,
                "errors": 0,
            }
        ]
    }
    mock_sitemaps.list.return_value = mock_sitemaps_list
    mock_service.sitemaps.return_value = mock_sitemaps

    with patch("app.google_seo.get_gsc_service", return_value=mock_service):
        data = fetch_google_analytics(days=30)
        assert data["status"] == "active"
        assert data["total_impressions"] == 300
        assert data["total_clicks"] == 25
        assert len(data["top_queries"]) == 2
        assert len(data["growth_points"]) >= 1
        assert data["growth_points"][0]["text"] == "оценка рисков закупок"
        assert len(data["sitemaps"]) == 1


def test_google_analytics_uses_closed_property_total_and_labels_query_coverage():
    """Property totals remain canonical when anonymized queries are omitted."""
    service = MagicMock()

    def response_for(body):
        dimensions = body.get("dimensions", [])
        if dimensions == []:
            return {"rows": [{"clicks": 13, "impressions": 961, "ctr": 13 / 961, "position": 24.33}]}
        if dimensions == ["query"]:
            return {"rows": [{"keys": ["visible query"], "clicks": 0, "impressions": 234, "ctr": 0, "position": 20.0}]}
        if dimensions == ["date"]:
            return {"rows": []}
        if dimensions == ["date", "query"]:
            return {"rows": []}
        raise AssertionError(dimensions)

    query = MagicMock()
    query.execute.side_effect = lambda: response_for(service.searchanalytics().query.call_args.kwargs["body"])
    service.searchanalytics().query.return_value = query
    service.sitemaps().list().execute.return_value = {"sitemap": []}

    with patch("app.google_seo.get_gsc_service", return_value=service):
        data = fetch_google_analytics(days=28, lag_days=3)

    assert data["property_totals"]["clicks"] == 13
    assert data["total_clicks"] == 13
    assert data["query_sample"]["clicks"] == 0
    assert data["query_sample"]["impression_coverage_percent"] == 24.35
    assert data["period"]["data_state"] == "final"
    assert data["period"]["lag_days"] == 3
    for call in service.searchanalytics().query.call_args_list:
        assert call.kwargs["body"]["dataState"] == "final"


def test_google_analytics_paginates_visible_query_rows():
    service = MagicMock()
    calls = []

    def execute_query():
        body = service.searchanalytics().query.call_args.kwargs["body"]
        calls.append(body.copy())
        dimensions = body.get("dimensions", [])
        if dimensions == []:
            return {"rows": [{"clicks": 2, "impressions": 20, "ctr": 0.1, "position": 4.0}]}
        if dimensions == ["query"]:
            if body.get("startRow", 0) == 0:
                return {"rows": [
                    {"keys": [f"query-{index}"], "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 3.0}
                    for index in range(500)
                ]}
            return {"rows": []}
        return {"rows": []}

    query = MagicMock()
    query.execute.side_effect = execute_query
    service.searchanalytics().query.return_value = query
    service.sitemaps().list().execute.return_value = {"sitemap": []}

    with patch("app.google_seo.get_gsc_service", return_value=service):
        fetch_google_analytics(days=28)

    query_calls = [body for body in calls if body.get("dimensions") == ["query"]]
    assert [body.get("startRow", 0) for body in query_calls] == [0, 500]


def _gsc_fixture(query_error=False):
    service = MagicMock()
    def execute():
        body = service.searchanalytics().query.call_args.kwargs["body"]
        if body["dimensions"] == []:
            return {"rows": [{"clicks": 5, "impressions": 100, "position": 4.0}]}
        if body["dimensions"] == ["query"] and query_error:
            raise RuntimeError("query scope unavailable")
        return {"rows": []}
    service.searchanalytics().query.return_value.execute.side_effect = execute
    service.sitemaps().list().execute.return_value = {"sitemap": []}
    return service


def test_missing_credentials_leave_query_sample_unknown():
    with patch("app.google_seo.get_gsc_service", return_value=None):
        data = fetch_google_analytics()
    assert data["query_sample"]["status"] == "unavailable"
    assert data["query_sample"]["clicks"] is None
    assert data["query_sample"]["impression_coverage_percent"] is None
    assert data["query_sample"]["row_count"] is None


def test_service_credential_parse_error_is_reported_without_crashing():
    with patch("app.google_seo.get_gsc_service", side_effect=ValueError("malformed credentials")):
        data = fetch_google_analytics()
    assert data["status"] == "error"
    assert data["property_totals"]["impressions"] is None
    assert data["query_sample"]["status"] == "unavailable"


def test_query_api_failure_preserves_property_totals_but_query_sample_unknown():
    with patch("app.google_seo.get_gsc_service", return_value=_gsc_fixture(query_error=True)):
        data = fetch_google_analytics()
    assert data["total_clicks"] == 5
    assert data["totals_status"] == "available"
    assert data["query_sample"]["status"] == "error"
    assert data["query_sample"]["clicks"] is None
    assert data["query_sample"]["impression_coverage_percent"] is None
    assert data["top_queries"] == []


def test_valid_empty_query_response_is_real_zero_with_available_status():
    with patch("app.google_seo.get_gsc_service", return_value=_gsc_fixture()):
        data = fetch_google_analytics()
    assert data["query_sample"]["status"] == "available"
    assert data["query_sample"]["clicks"] == 0
    assert data["query_sample"]["row_count"] == 0


def test_incomplete_property_row_is_error_not_available_with_zero_totals():
    service = _gsc_fixture()
    service.searchanalytics().query.return_value.execute.side_effect = None
    service.searchanalytics().query.return_value.execute.return_value = {"rows": [{"position": 5.0}]}
    with patch("app.google_seo.get_gsc_service", return_value=service):
        data = fetch_google_analytics()
    assert data["status"] == "error"
    assert data["totals_status"] == "error"
    assert data["total_clicks"] is None
    assert data["component_status"]["property_totals"] == "error"
