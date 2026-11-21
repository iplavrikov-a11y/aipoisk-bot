#!/usr/bin/env python3
"""
Price monitoring benchmark for 15 real items across RU, CIS, WORLD scopes.
Total 45 tasks.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import SessionLocal
from app.models import SystemSettings
from app.supplier_search import _search_with_yandex, FOREIGN_NATIONAL_CCTLDS, CIS_CCTLDS, FOREIGN_B2B_PORTALS
from app.price_monitoring.extractor import is_valid_domain, is_foreign_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REAL_ITEMS = [
    "Таль электрическая канатная",
    "Теплообменник пластинчатый",
    "Шнековый транспортер",
    "Барабан конвейерный",
    "Подшипниковый узел в сборе",
    "Станок для финишной абразивной обработки лопаток",
    "Приспособление для промежуточного подсоединения пожарных рукавов к трубопроводу",
    "Зачистная машина",
    "Станция просеивания металлического порошка",
    "Тепловизор общепромышленный",
    "Насос-регулятор НР-3ВМ-Т",
    "Мягкий контейнер (биг-бэг) 95х95х130",
    "Лист стальной рифленый",
    "Регулятор температуры прямого действия",
    "Лебедка лифтовая редукторная",
]


async def run():
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).filter_by(id=1).first()
    finally:
        db.close()

    results = {
        "price_monitoring_ru": [],
        "price_monitoring_cis": [],
        "price_monitoring_world": [],
    }

    print("=== STARTING PRICE MONITORING BENCHMARK (45 TASKS) ===")

    # 1. RU MODE (15 tasks)
    print("\n--- PRICE MONITORING: RU (15 tasks) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, _ = await _search_with_yandex(settings, [f"{item} цена прайс"], max_results=12, geo_scope="ru")
        valid = [c for c in cands if is_valid_domain(c.url, target_item_name=item, geo_scope="ru")]
        foreign_leaks = [c.url for c in valid if is_foreign_source(c.url, geo_scope="ru")]
        elapsed = time.time() - t0
        status = "OK" if len(valid) > 0 and len(foreign_leaks) == 0 else "FAIL"
        results["price_monitoring_ru"].append({
            "item": item,
            "total_candidates": len(cands),
            "valid_domestic_urls": len(valid),
            "foreign_leaks": foreign_leaks,
            "sample_domains": [c.domain for c in valid[:3]],
            "status": status,
            "time_sec": round(elapsed, 2),
        })
        print(f"[{idx}/15] {item}: {len(valid)} valid domestic URLs ({status}) in {elapsed:.2f}s | sample: {[c.domain for c in valid[:3]]}")

    # 2. CIS MODE (15 tasks)
    print("\n--- PRICE MONITORING: CIS (15 tasks) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, _ = await _search_with_yandex(settings, [f"{item} цена прайс"], max_results=12, geo_scope="cis")
        valid = [c for c in cands if is_valid_domain(c.url, target_item_name=item, geo_scope="cis")]
        non_cis_leaks = [c.url for c in valid if is_foreign_source(c.url, geo_scope="cis")]
        cis_sources = [c.domain for c in valid if any(c.domain.endswith(t) for t in CIS_CCTLDS)]
        elapsed = time.time() - t0
        status = "OK" if len(valid) > 0 and len(non_cis_leaks) == 0 else "FAIL"
        results["price_monitoring_cis"].append({
            "item": item,
            "total_candidates": len(cands),
            "valid_urls": len(valid),
            "cis_domains": cis_sources,
            "non_cis_leaks": non_cis_leaks,
            "sample_domains": [c.domain for c in valid[:3]],
            "status": status,
            "time_sec": round(elapsed, 2),
        })
        print(f"[{idx}/15] {item}: {len(valid)} valid URLs (CIS found: {len(cis_sources)}, Non-CIS leaks: {len(non_cis_leaks)}) in {elapsed:.2f}s")

    # 3. WORLD MODE (15 tasks)
    print("\n--- PRICE MONITORING: WORLD (15 tasks) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, _ = await _search_with_yandex(settings, [f"{item} price catalog"], max_results=12, geo_scope="world")
        valid = [c for c in cands if is_valid_domain(c.url, target_item_name=item, filter_foreign=False, geo_scope="world")]
        agg_leaks = [c.url for c in valid if any(p in c.domain for p in FOREIGN_B2B_PORTALS)]
        foreign_sources = [c.domain for c in valid if any(c.domain.endswith(t) for t in FOREIGN_NATIONAL_CCTLDS)]
        elapsed = time.time() - t0
        status = "OK" if len(valid) > 0 and len(agg_leaks) == 0 else "FAIL"
        results["price_monitoring_world"].append({
            "item": item,
            "total_candidates": len(cands),
            "valid_urls": len(valid),
            "foreign_domains": foreign_sources,
            "aggregator_leaks": agg_leaks,
            "sample_domains": [c.domain for c in valid[:3]],
            "status": status,
            "time_sec": round(elapsed, 2),
        })
        print(f"[{idx}/15] {item}: {len(valid)} valid World URLs (Foreign TLDs: {len(foreign_sources)}, Aggregator leaks: {len(agg_leaks)}) in {elapsed:.2f}s | sample: {[c.domain for c in valid[:3]]}")

    out_file = Path("price_monitoring_benchmark.json")
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nPrice monitoring benchmark completed! Written to {out_file.resolve()}")


if __name__ == "__main__":
    asyncio.run(run())
