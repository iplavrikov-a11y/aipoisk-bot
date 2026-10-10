from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.google_seo import fetch_google_analytics
from app.yandex_seo import fetch_fresh_snapshot
from test_yandex_seo import _mock_snapshot


@pytest.fixture(autouse=True)
def fixed_google_calendar(monkeypatch):
    class Calendar(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    monkeypatch.setattr('app.google_seo.datetime', Calendar)


def test_yandex_daily_uses_all_queries_history_not_phrase_sample(tmp_path, monkeypatch):
    seo, requests = _mock_snapshot(tmp_path, monkeypatch)
    original = seo._http_json
    def http(url, **kwargs):
        if '/search-queries/all/history?' in url:
            requests.append(url)
            return {'indicators': {'TOTAL_SHOWS': [{'date':'2026-10-02T00:00:00+03:00','value':14}], 'TOTAL_CLICKS':[{'date':'2026-10-02T00:00:00+03:00','value':0}], 'AVG_SHOW_POSITION':[]}}
        return original(url, **kwargs)
    monkeypatch.setattr(seo, '_http_json', http)
    snapshot = seo.fetch_fresh_snapshot()
    assert any('/search-queries/all/history?' in u for u in requests)
    row = snapshot['webmaster']['daily_dynamics'][-1]
    assert row['date']=='2026-10-02' and row['shows']==14 and row['clicks']==0
    assert row['avg_position'] is None and row['queries_count'] is None
    assert snapshot['webmaster']['daily_scope']=='property_totals'


def test_google_fresh_daily_retains_camelcase_metadata_and_closed_summary():
    service = MagicMock()
    def execute():
        body=service.searchanalytics().query.call_args.kwargs['body']
        if body['dimensions']==[]:return {'rows':[{'clicks':2,'impressions':20,'position':8}]}
        if body['dimensions']==['query']:return {'rows':[]}
        if body.get('dataState')=='all':
            return {'metadata':{'firstIncompleteDate':'2026-10-01'},'rows':[{'keys':['2026-10-03'],'clicks':1,'impressions':10,'position':7}]}
        return {'rows':[]}
    service.searchanalytics().query.return_value.execute.side_effect=execute
    service.sitemaps().list().execute.return_value={'sitemap':[]}
    with patch('app.google_seo.get_gsc_service',return_value=service):data=fetch_google_analytics()
    assert data['period']['data_state']=='final' and data['total_clicks']==2
    assert data['daily_period']['data_state']=='all'
    assert data['first_incomplete_date']=='2026-10-01'
    assert data['daily_dynamics'][-1]['date']=='2026-10-03'
    assert data['daily_dynamics'][-1]['data_status']=='preliminary'


def test_yandex_indicators_publish_independently_and_keep_reported_zero():
    from app.seo_daily import yandex_daily
    rows = yandex_daily({'indicators': {
        'TOTAL_SHOWS': [{'date': '2026-10-03T00:00:00+03:00', 'value': 0}, {'date': '2026-10-04T00:00:00+03:00', 'value': 12}],
        'TOTAL_CLICKS': [{'date': '2026-10-03T00:00:00+03:00', 'value': 0}],
        'AVG_SHOW_POSITION': []}}, '2026-10-04')
    assert rows[0]['shows'] == 0 and rows[0]['clicks'] == 0 and rows[0]['avg_position'] is None
    assert rows[1]['clicks'] is None and rows[1]['data_status'] == 'preliminary'


def test_fresh_google_failure_keeps_final_daily_and_known_summary():
    service = MagicMock()
    def execute():
        body = service.searchanalytics().query.call_args.kwargs['body']
        if body.get('dataState') == 'all': raise RuntimeError('fresh daily unavailable')
        if body['dimensions'] == []: return {'rows': [{'clicks': 2, 'impressions': 20, 'position': 8}]}
        if body['dimensions'] == ['date']: return {'rows': [{'keys': ['2026-09-29'], 'clicks': 1, 'impressions': 10, 'position': 7}]}
        return {'rows': []}
    service.searchanalytics().query.return_value.execute.side_effect = execute
    service.sitemaps().list().execute.return_value = {'sitemap': []}
    with patch('app.google_seo.get_gsc_service', return_value=service): data = fetch_google_analytics()
    assert data['status'] == 'partial' and data['total_clicks'] == 2
    assert data['daily_dynamics'][0]['data_status'] == 'final'
    assert data['period']['end_date'] == '2026-09-29'
    assert data['period']['latest_observed_final_date'] == '2026-09-29'
    assert data['component_status']['daily_dynamics'] == 'error'


def test_missing_date_keys_do_not_crash_preflight_or_invent_a_day():
    service = MagicMock()
    def execute():
        body = service.searchanalytics().query.call_args.kwargs['body']
        if body['dimensions'] == ['date']:
            return {'rows': [{'keys': [], 'clicks': 0, 'impressions': 0, 'position': 0}]}
        return {'rows': []}
    service.searchanalytics().query.return_value.execute.side_effect = execute
    service.sitemaps().list().execute.return_value = {'sitemap': []}
    with patch('app.google_seo.get_gsc_service', return_value=service): data = fetch_google_analytics()
    assert data['daily_dynamics'] == []
