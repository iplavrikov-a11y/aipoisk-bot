#!/usr/bin/env python3
"""
Comprehensive benchmark runner for TenderLex 7-mode matrix:
1. supplier_search (RU - Только Россия) - 15 real items
2. supplier_search (CIS - РФ и СНГ) - 15 real items
3. supplier_search (WORLD - Весь мир) - 15 real items
4. exact_product (Подбор товара и аналогов) - 15 real items
5. price_monitoring (RU - Только Россия) - 15 real items
6. price_monitoring (CIS - РФ и СНГ) - 15 real items
7. price_monitoring (WORLD - Весь мир) - 15 real items

Real items extracted directly from previous production customer jobs in data/aipoisk.db.
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import SessionLocal
from app.models import SystemSettings
from app.supplier_search import (
    _search_with_yandex,
    _exclude_candidates,
    is_domain_allowed_for_geo,
    Candidate,
    base_domain,
    CIS_CCTLDS,
    FOREIGN_NATIONAL_CCTLDS,
    FOREIGN_B2B_PORTALS,
)
from app.exact_product.pipeline import analyze_exact_product
from app.price_monitoring.extractor import is_valid_domain, is_foreign_source
from app.price_monitoring.pipeline import clean_nomenclature_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark")

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


async def run_benchmark():
    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).filter_by(id=1).first()
        if not settings:
            logger.error("No system settings found in DB!")
            return
    finally:
        db.close()

    results = {
        "supplier_search_ru": [],
        "supplier_search_cis": [],
        "supplier_search_world": [],
        "exact_product": [],
        "price_monitoring_ru": [],
        "price_monitoring_cis": [],
        "price_monitoring_world": [],
    }

    print("=====================================================================")
    print("STARTING 105-TASK BENCHMARK ACROSS 7 MODES ON REAL PRODUCTION GOODS")
    print("=====================================================================")

    # -------------------------------------------------------------
    # 1. SUPPLIER SEARCH - RU (15 tasks)
    # -------------------------------------------------------------
    print("\n--- [MODE 1/7] SUPPLIER SEARCH: RU (Только Россия) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, reqs = await _search_with_yandex(settings, [item], max_results=10, geo_scope="ru")
        filtered = _exclude_candidates(cands, set(), geo_scope="ru")
        elapsed = time.time() - t0

        domains = [c.domain for c in filtered]
        foreign_leaks = [d for d in domains if any(d.endswith(tld) for tld in FOREIGN_NATIONAL_CCTLDS)]

        status = "OK" if len(filtered) > 0 and len(foreign_leaks) == 0 else "FAIL"
        results["supplier_search_ru"].append({
            "item": item,
            "candidates_count": len(filtered),
            "foreign_leaks": foreign_leaks,
            "status": status,
            "time_sec": round(elapsed, 2),
            "sample_domains": domains[:3],
        })
        print(f"[{idx}/15] {item}: {len(filtered)} cands ({status}) in {elapsed:.2f}s | domains: {domains[:3]}")

    # -------------------------------------------------------------
    # 2. SUPPLIER SEARCH - CIS (15 tasks)
    # -------------------------------------------------------------
    print("\n--- [MODE 2/7] SUPPLIER SEARCH: CIS (РФ и СНГ) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, reqs = await _search_with_yandex(settings, [item], max_results=10, geo_scope="cis")
        filtered = _exclude_candidates(cands, set(), geo_scope="cis")
        elapsed = time.time() - t0

        domains = [c.domain for c in filtered]
        # Non-CIS foreign leaks:
        non_cis_foreign = [d for d in domains if any(d.endswith(tld) for tld in FOREIGN_NATIONAL_CCTLDS - CIS_CCTLDS)]
        cis_found = [d for d in domains if any(d.endswith(tld) for tld in CIS_CCTLDS)]

        status = "OK" if len(filtered) > 0 and len(non_cis_foreign) == 0 else "FAIL"
        results["supplier_search_cis"].append({
            "item": item,
            "candidates_count": len(filtered),
            "cis_domains": cis_found,
            "non_cis_leaks": non_cis_foreign,
            "status": status,
            "time_sec": round(elapsed, 2),
            "sample_domains": domains[:3],
        })
        print(f"[{idx}/15] {item}: {len(filtered)} cands (CIS: {len(cis_found)}, Non-CIS leaks: {len(non_cis_foreign)}) in {elapsed:.2f}s")

    # -------------------------------------------------------------
    # 3. SUPPLIER SEARCH - WORLD (15 tasks)
    # -------------------------------------------------------------
    print("\n--- [MODE 3/7] SUPPLIER SEARCH: WORLD (Весь мир) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, reqs = await _search_with_yandex(settings, [item], max_results=10, geo_scope="world")
        filtered = _exclude_candidates(cands, set(), geo_scope="world")
        elapsed = time.time() - t0

        domains = [c.domain for c in filtered]
        # Check aggregator block
        aggregator_leaks = [d for d in domains if any(d == p or d.endswith("." + p) for p in FOREIGN_B2B_PORTALS)]
        status = "OK" if len(filtered) > 0 and len(aggregator_leaks) == 0 else "FAIL"
        results["supplier_search_world"].append({
            "item": item,
            "candidates_count": len(filtered),
            "aggregator_leaks": aggregator_leaks,
            "status": status,
            "time_sec": round(elapsed, 2),
            "sample_domains": domains[:3],
        })
        print(f"[{idx}/15] {item}: {len(filtered)} cands (Aggregator leaks: {len(aggregator_leaks)}) in {elapsed:.2f}s | sample: {domains[:3]}")

    # -------------------------------------------------------------
    # 4. EXACT PRODUCT (15 tasks)
    # -------------------------------------------------------------
    print("\n--- [MODE 4/7] EXACT PRODUCT: Model Identification & Analogs ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        try:
            report = await analyze_exact_product(
                settings,
                f"Требуется поставка: {item}. Новое, заводское исполнение, ГОСТ/ТУ.",
                procurement_title=item,
                selected_positions=[{"name": item, "quantity": "1 шт"}],
            )
            elapsed = time.time() - t0
            pos = report.positions[0] if report.positions else None
            analogs_count = len(pos.alternative_brands) if pos and pos.alternative_brands else 0
            specs_count = len(pos.specs_breakdown) if pos and pos.specs_breakdown else 0
            status = "OK" if pos and (pos.identified_model or analogs_count > 0 or specs_count > 0) else "PARTIAL"
            results["exact_product"].append({
                "item": item,
                "identified_model": pos.identified_model if pos else "",
                "identified_brand": pos.identified_brand if pos else "",
                "analogs_count": analogs_count,
                "parameters_count": specs_count,
                "status": status,
                "time_sec": round(elapsed, 2),
            })
            print(f"[{idx}/15] {item}: Model='{pos.identified_model if pos else ''}' | Analogs={analogs_count} | Specs={specs_count} in {elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - t0
            results["exact_product"].append({
                "item": item,
                "status": "ERROR",
                "error": str(e),
                "time_sec": round(elapsed, 2),
            })
            print(f"[{idx}/15] {item}: ERROR: {e} in {elapsed:.2f}s")

    # -------------------------------------------------------------
    # 5. PRICE MONITORING - RU (15 tasks)
    # -------------------------------------------------------------
    print("\n--- [MODE 5/7] PRICE MONITORING: RU (Только Россия) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, reqs = await _search_with_yandex(settings, [f"{item} цена купить"], max_results=10, geo_scope="ru")
        valid_urls = [c.url for c in cands if is_valid_domain(c.url, target_item_name=item, geo_scope="ru")]
        foreign_in_valid = [u for u in valid_urls if is_foreign_source(u, geo_scope="ru")]
        elapsed = time.time() - t0

        status = "OK" if len(valid_urls) > 0 and len(foreign_in_valid) == 0 else "FAIL"
        results["price_monitoring_ru"].append({
            "item": item,
            "valid_urls_count": len(valid_urls),
            "foreign_violations": len(foreign_in_valid),
            "status": status,
            "time_sec": round(elapsed, 2),
        })
        print(f"[{idx}/15] {item}: {len(valid_urls)} valid domestic price URLs (0 foreign leaks) in {elapsed:.2f}s")

    # -------------------------------------------------------------
    # 6. PRICE MONITORING - CIS (15 tasks)
    # -------------------------------------------------------------
    print("\n--- [MODE 6/7] PRICE MONITORING: CIS (РФ и СНГ) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, reqs = await _search_with_yandex(settings, [f"{item} цена купить"], max_results=10, geo_scope="cis")
        valid_urls = [c.url for c in cands if is_valid_domain(c.url, target_item_name=item, geo_scope="cis")]
        non_cis_foreign = [u for u in valid_urls if is_foreign_source(u, geo_scope="cis")]
        elapsed = time.time() - t0

        status = "OK" if len(valid_urls) > 0 and len(non_cis_foreign) == 0 else "FAIL"
        results["price_monitoring_cis"].append({
            "item": item,
            "valid_urls_count": len(valid_urls),
            "non_cis_foreign_violations": len(non_cis_foreign),
            "status": status,
            "time_sec": round(elapsed, 2),
        })
        print(f"[{idx}/15] {item}: {len(valid_urls)} valid CIS/RU price URLs (0 non-CIS leaks) in {elapsed:.2f}s")

    # -------------------------------------------------------------
    # 7. PRICE MONITORING - WORLD (15 tasks)
    # -------------------------------------------------------------
    print("\n--- [MODE 7/7] PRICE MONITORING: WORLD (Весь мир) ---")
    for idx, item in enumerate(REAL_ITEMS, 1):
        t0 = time.time()
        cands, reqs = await _search_with_yandex(settings, [f"{item} price supplier"], max_results=10, geo_scope="world")
        valid_urls = [c.url for c in cands if is_valid_domain(c.url, target_item_name=item, filter_foreign=False, geo_scope="world")]
        aggregator_leaks = [u for u in valid_urls if any(p in u for p in FOREIGN_B2B_PORTALS)]
        elapsed = time.time() - t0

        status = "OK" if len(valid_urls) > 0 and len(aggregator_leaks) == 0 else "FAIL"
        results["price_monitoring_world"].append({
            "item": item,
            "valid_urls_count": len(valid_urls),
            "aggregator_violations": len(aggregator_leaks),
            "status": status,
            "time_sec": round(elapsed, 2),
        })
        print(f"[{idx}/15] {item}: {len(valid_urls)} valid World price URLs (Aggregator leaks: {len(aggregator_leaks)}) in {elapsed:.2f}s")

    # Save benchmark report to JSON
    out_path = Path("benchmark_results.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nBenchmark completed successfully! Results written to {out_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
