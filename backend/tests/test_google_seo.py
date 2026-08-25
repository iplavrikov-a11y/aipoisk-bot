from unittest.mock import MagicMock, patch
import pytest

from app.google_seo import fetch_google_analytics
from app.yandex_seo import fetch_fresh_snapshot


def test_fetch_google_analytics_success():
    mock_service = MagicMock()
    mock_searchanalytics = MagicMock()
    mock_query = MagicMock()
    mock_query.execute.return_value = {
        "rows": [
            {
                "keys": ["оценка рисков закупок"],
                "clicks": 5,
                "impressions": 100,
                "ctr": 0.05,
                "position": 4.5,
            },
            {
                "keys": ["поиск поставщиков по тз"],
                "clicks": 20,
                "impressions": 200,
                "ctr": 0.10,
                "position": 2.0,
            }
        ]
    }
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
