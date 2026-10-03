"""Snapshot freshness follows collection time, never edits to the file."""
import json
from datetime import datetime, timedelta, timezone

import pytest
import app.yandex_seo as seo

@pytest.mark.parametrize('age', [7, -1])
def test_old_or_future_collection_is_not_fresh_after_a_file_edit(tmp_path, monkeypatch, age):
    path = tmp_path / 'snapshot.json'
    path.write_text(json.dumps({'schema_version': 2, 'updated_at': (datetime.now(timezone.utc)-timedelta(hours=age)).isoformat()}))
    monkeypatch.setattr(seo, 'SNAPSHOT_PATH', path)
    monkeypatch.setattr(seo, 'fetch_fresh_snapshot', lambda: {'fresh': True})
    assert seo.get_cached_or_fresh_analytics() == {'fresh': True}


def test_recent_collection_is_reused_without_network(tmp_path, monkeypatch):
    path = tmp_path / 'snapshot.json'
    data = {'schema_version': 2, 'updated_at': datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(data)); monkeypatch.setattr(seo, 'SNAPSHOT_PATH', path)
    monkeypatch.setattr(seo, 'fetch_fresh_snapshot', lambda: pytest.fail('unexpected collection'))
    assert seo.get_cached_or_fresh_analytics() == data


def test_simultaneous_expired_reads_collect_once(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    path = tmp_path / 'snapshot.json'
    monkeypatch.setattr(seo, 'SNAPSHOT_PATH', path)
    started, release, duplicate = Event(), Event(), Event()
    calls = []
    def collect():
        calls.append(1)
        if len(calls) > 1: duplicate.set()
        started.set()
        assert release.wait(5)
        data = {'schema_version': 2, 'updated_at': datetime.now(timezone.utc).isoformat()}
        path.write_text(json.dumps(data))
        return data
    monkeypatch.setattr(seo, 'fetch_fresh_snapshot', collect)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(seo.get_cached_or_fresh_analytics)
        assert started.wait(5)
        second = pool.submit(seo.get_cached_or_fresh_analytics)
        duplicate.wait(0.2)
        release.set()
        assert first.result() == second.result()
    assert len(calls) == 1
