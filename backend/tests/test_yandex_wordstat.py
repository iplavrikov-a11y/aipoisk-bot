import json
import time
import pytest
import app.yandex_wordstat as yws

_REAL_FETCH = yws._fetch_wordstat_from_api

@pytest.fixture(autouse=True)
def isolate_wordstat(tmp_path, monkeypatch):
    monkeypatch.setattr(yws, "DATA_DIR", tmp_path)
    monkeypatch.setattr(yws, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(yws, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(yws, "load_wordstat_credentials", lambda: {"client_id": "", "token": ""})
    monkeypatch.setattr(yws, "_fetch_wordstat_from_api", lambda *args: None)
    monkeypatch.setattr(yws.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("unexpected network request"))

def test_api_failure_never_fabricates_demand_or_click_forecast():
    result = yws.get_phrase_demand("поиск по ТЗ", fallback_shows=1000, avg_position=7)
    assert result["demand"] is None
    assert result["top3_potential_clicks"] is None
    assert result["source"] == "unavailable"
    assert not yws.CACHE_FILE.exists()

def test_api_real_zero_has_period_and_provenance(monkeypatch):
    monkeypatch.setattr(yws, "_fetch_wordstat_from_api", lambda *args: 0)
    result = yws.get_phrase_demand("редкий запрос")
    assert result["demand"] == 0
    assert result["source"] == "wordstat_api"
    assert result["period"]["period_days"] == 30
    assert result["period"]["kind"] == "provider_defined_rolling"
    assert result["regions"] == [225]
    assert result["top3_potential_clicks"] is None

def test_estimated_legacy_cache_ignored_without_failed_refresh_write():
    original = json.dumps({"phrases": {"запрос": {"demand": 900, "source": "estimated", "timestamp": int(time.time())}}})
    yws.CACHE_FILE.write_text(original)
    result = yws.get_phrase_demand("запрос")
    assert result["demand"] is None
    assert yws.CACHE_FILE.read_text() == original

def test_verified_cache_retains_source_period_volume(monkeypatch):
    monkeypatch.setattr(yws, "_fetch_wordstat_from_api", lambda *args: 123)
    first = yws.get_phrase_demand("запрос")
    monkeypatch.setattr(yws, "_fetch_wordstat_from_api", lambda *args: pytest.fail("cache avoids API"))
    second = yws.get_phrase_demand("запрос")
    assert second["source"] == "cache"
    assert second["origin_source"] == "wordstat_api"
    assert second["period"] == first["period"]
    assert second["demand"] == 123

def test_growth_priority_without_wordstat_uses_observed_shows_only():
    result = yws.enrich_growth_points([{"text": "редкий", "shows": 3}, {"text": "частый", "shows": 73}])
    assert result[0]["text"] == "частый"
    assert result[0]["priority"] == "high"
    assert result[1]["priority"] == "normal"
    assert all(item["wordstat_demand"] is None and item["top3_potential_clicks"] is None for item in result)

def test_api_does_not_substitute_other_phrase_and_checks_tls(monkeypatch):
    calls = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps({"topRequests": [{"phrase": "другой запрос", "count": 999}]}).encode()
    def fake_open(req, **kwargs):
        calls.append(kwargs)
        return Response()
    monkeypatch.setattr(yws.urllib.request, "urlopen", fake_open)
    assert _REAL_FETCH("нужный запрос", "test-token") is None
    assert "context" not in calls[0] or calls[0]["context"].check_hostname
