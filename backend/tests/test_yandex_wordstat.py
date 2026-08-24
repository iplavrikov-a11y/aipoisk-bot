import os
import json
import time
import pytest
from pathlib import Path
from app.yandex_wordstat import (
    load_wordstat_credentials,
    get_phrase_demand,
    enrich_growth_points,
    _estimate_demand,
    CTR_TOP3,
    CACHE_TTL_SECONDS
)


def test_load_wordstat_credentials():
    creds = load_wordstat_credentials()
    assert "client_id" in creds
    assert "token" in creds
    assert creds["client_id"] == "a84a7a825d3c4cbb9b2ff237ad38e425"
    assert creds["token"] == "y0__wgBELDitkEY0YBIII2s4uIYMM7MspMISpwm_Kxd3r0y_5uOlklAlmAEnic"


def test_top3_potential_calculation():
    assert CTR_TOP3 == 0.35
    
    demand = 100
    expected_top3 = int(round(demand * 0.35))
    assert expected_top3 == 35

    res = get_phrase_demand("поиск товаров по тз", fallback_shows=10, avg_position=7.5)
    assert res["demand"] > 0
    assert res["top3_potential_clicks"] == int(round(res["demand"] * 0.35))
    assert res["phrase"] == "поиск товаров по тз"


def test_estimate_demand():
    est1 = _estimate_demand("подбор аналогов по тз", shows=29, avg_position=7.0)
    assert est1 > 100

    est2 = _estimate_demand("редкий запрос", shows=0, avg_position=0.0)
    assert est2 >= 15


def test_wordstat_caching(tmp_path, monkeypatch):
    test_cache_file = tmp_path / "test_wordstat_cache.json"
    import app.yandex_wordstat as yws
    monkeypatch.setattr(yws, "CACHE_FILE", test_cache_file)
    monkeypatch.setattr(yws, "DATA_DIR", tmp_path)

    res1 = yws.get_phrase_demand("тендерный поиск тестовый", fallback_shows=5, avg_position=6.0)
    assert test_cache_file.exists()

    with open(test_cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)
    assert "тендерный поиск тестовый" in cache_data["phrases"]
    assert cache_data["phrases"]["тендерный поиск тестовый"]["demand"] == res1["demand"]

    # Second call should read from cache
    res2 = yws.get_phrase_demand("тендерный поиск тестовый")
    assert res2["source"] == "cache"
    assert res2["demand"] == res1["demand"]
    assert res2["top3_potential_clicks"] == res1["top3_potential_clicks"]


def test_enrich_growth_points():
    raw_points = [
        {
            "text": "мало показов",
            "shows": 3,
            "avg_position": 9.0,
            "clicks": 0
        },
        {
            "text": "поиск товаров по тз",
            "shows": 73,
            "avg_position": 8.3,
            "clicks": 0
        },
        {
            "text": "подбор аналогов по тз",
            "shows": 29,
            "avg_position": 7.0,
            "clicks": 0
        }
    ]

    enriched = enrich_growth_points(raw_points)
    assert len(enriched) == 3

    # Check that it's sorted descending by wordstat_demand
    assert enriched[0]["wordstat_demand"] >= enriched[1]["wordstat_demand"]
    assert enriched[1]["wordstat_demand"] >= enriched[2]["wordstat_demand"]

    # Check enriched fields
    top_item = enriched[0]
    assert top_item["priority"] == "high"
    assert "wordstat_demand" in top_item
    assert "top3_potential_clicks" in top_item
    assert top_item["top3_potential_clicks"] == int(round(top_item["wordstat_demand"] * 0.35))
