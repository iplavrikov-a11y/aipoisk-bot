"""The background collector is analytics-only and does not dispatch actions."""
import importlib.util
from pathlib import Path


def test_background_collector_only_reads_the_snapshot(monkeypatch, capsys):
    path = Path(__file__).resolve().parents[2] / 'scripts/refresh_seo_snapshot.py'
    spec = importlib.util.spec_from_file_location('seo_admin_collector', path)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    calls = []
    monkeypatch.setattr(collector, 'get_cached_or_fresh_analytics', lambda: calls.append('analytics') or {'collection_status': 'active', 'updated_at': '2026-10-04'})
    assert collector.main() == 0
    assert calls == ['analytics']
    assert 'status=active' in capsys.readouterr().out


def test_failed_collection_is_visible_to_the_service(monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts/refresh_seo_snapshot.py'
    spec = importlib.util.spec_from_file_location('seo_admin_collector', path)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    monkeypatch.setattr(collector, 'get_cached_or_fresh_analytics', lambda: {'collection_status': 'error'})
    assert collector.main() == 1
