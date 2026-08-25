import pytest
from unittest.mock import MagicMock, patch
from app.google_seo import fetch_google_analytics, get_gsc_service


def test_fetch_google_analytics_no_creds(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/non_existent_path.json")
    with patch("app.google_seo.DEFAULT_KEY_PATH", "/tmp/non_existent_path.json"):
        res = fetch_google_analytics(days=30)
        assert res["status"] in ["unavailable", "error"]
        assert "error" in res


def test_fetch_google_analytics_with_mock_service():
    mock_service = MagicMock()
    mock_searchanalytics = MagicMock()
    mock_query_cmd = MagicMock()
    
    mock_rows = [
        {"keys": ["анализ рисков закупок"], "clicks": 5, "impressions": 50, "ctr": 0.1, "position": 5.2},
        {"keys": ["поиск поставщиков"], "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 12.0},
        {"keys": ["тендеры 44 фз"], "clicks": 0, "impressions": 2, "ctr": 0.0, "position": 45.0},
    ]
    mock_query_cmd.execute.return_value = {"rows": mock_rows}
    mock_searchanalytics.query.return_value = mock_query_cmd
    mock_service.searchanalytics.return_value = mock_searchanalytics
    
    mock_sitemaps = MagicMock()
    mock_sitemaps_cmd = MagicMock()
    mock_sitemaps_cmd.execute.return_value = {
        "sitemap": [
            {"path": "https://tenderlex.ru/sitemap.xml", "lastSubmitted": "2026-08-20T10:00:00Z", "isPending": False}
        ]
    }
    mock_sitemaps.list.return_value = mock_sitemaps_cmd
    mock_service.sitemaps.return_value = mock_sitemaps

    with patch("app.google_seo.get_gsc_service", return_value=mock_service):
        res = fetch_google_analytics(days=30, site_url="sc-domain:tenderlex.ru")
        assert res["status"] == "active"
        assert res["total_impressions"] == 62
        assert res["total_clicks"] == 6
        assert len(res["top_queries"]) == 3
        assert len(res["growth_points"]) >= 1
        assert len(res["sitemaps"]) == 1
        assert res["sitemaps"][0]["path"] == "https://tenderlex.ru/sitemap.xml"


def test_combined_queries_in_snapshot(tmp_path, monkeypatch):
    import app.yandex_seo as yseo
    test_snapshot = tmp_path / "test_snapshot.json"
    monkeypatch.setattr(yseo, "SNAPSHOT_PATH", test_snapshot)
    monkeypatch.setattr(yseo, "DATA_DIR", tmp_path)

    with patch("app.yandex_seo._http_json") as mock_http, \
         patch("app.google_seo.fetch_google_analytics") as mock_google:
        
        mock_http.return_value = {}
        mock_google.return_value = {
            "status": "active",
            "total_impressions": 10,
            "total_clicks": 1,
            "avg_position": 8.0,
            "top_queries": [
                {"text": "номенклатура закупок", "shows": 10, "clicks": 1, "avg_position": 8.0, "ctr_percent": 10.0}
            ],
            "growth_points": []
        }
        
        snap = yseo.fetch_fresh_snapshot()
        assert "google" in snap
        assert "combined_queries" in snap
        assert snap["google"]["status"] == "active"
        assert len(snap["combined_queries"]) >= 1
        assert snap["combined_queries"][0]["text"] == "номенклатура закупок"
        assert snap["combined_queries"][0]["in_google"] is True

