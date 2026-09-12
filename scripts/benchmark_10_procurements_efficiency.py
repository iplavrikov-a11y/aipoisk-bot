"""Benchmark 10 diverse procurements to measure supplier discovery quality and Yandex Search API cost efficiency."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db import SessionLocal
from app.repository import get_or_create_settings
from app.supplier_search import (
    discover_suppliers,
    SUPPLIER_POLICY_NORMAL,
    SUPPLIER_POLICY_MINPROM_PRIORITY,
)

BENCHMARK_TASKS = [
    {"id": 1, "industry": "Лабораторная мебель", "query": "Шкаф вытяжной химический лабораторный", "target": 10, "policy": SUPPLIER_POLICY_NORMAL},
    {"id": 2, "industry": "Светотехника", "query": "Светильники светодиодные уличные консольные ДКУ IP66", "target": 10, "policy": SUPPLIER_POLICY_MINPROM_PRIORITY},
    {"id": 3, "industry": "Кабельная продукция", "query": "Кабель силовой ВВГнг(А)-FRLS 3х2.5 ГОСТ 31996-2012", "target": 10, "policy": SUPPLIER_POLICY_MINPROM_PRIORITY},
    {"id": 4, "industry": "Полимерные трубы", "query": "Трубы напорные из полиэтилена ПЭ 100 для водоснабжения", "target": 10, "policy": SUPPLIER_POLICY_NORMAL},
    {"id": 5, "industry": "Запорная арматура", "query": "Клапаны запорные фланцевые стальные 15с65нж Ду50 Ру16", "target": 10, "policy": SUPPLIER_POLICY_MINPROM_PRIORITY},
    {"id": 6, "industry": "Трансформаторы", "query": "Трансформаторы силовые масляные герметичные ТМГ 1000/10/0.4", "target": 10, "policy": SUPPLIER_POLICY_NORMAL},
    {"id": 7, "industry": "Медоборудование", "query": "Кровати медицинские функциональные трехсекционные с электроприводом", "target": 10, "policy": SUPPLIER_POLICY_MINPROM_PRIORITY},
    {"id": 8, "industry": "Фасовочное оборудование", "query": "Автоматическая машина для фасовки сыпучих продуктов", "target": 10, "policy": SUPPLIER_POLICY_NORMAL},
    {"id": 9, "industry": "Спецодежда / СИЗ", "query": "Костюмы мужские для защиты от общих производственных загрязнений", "target": 10, "policy": SUPPLIER_POLICY_NORMAL},
    {"id": 10, "industry": "Промышленные АКБ", "query": "Аккумуляторная батарея стационарная свинцово-кислотная с жидким электролитом", "target": 10, "policy": SUPPLIER_POLICY_NORMAL},
]

async def run_benchmark():
    with SessionLocal() as db:
        settings = get_or_create_settings(db)

    print("=" * 95)
    print("STARTING 10-PROCUREMENT SEARCH QUALITY & COST EFFICIENCY BENCHMARK")
    print("=" * 95)

    results = []
    total_yandex_reqs = 0
    total_yandex_cost = 0.0

    for task in BENCHMARK_TASKS:
        tid = task["id"]
        ind = task["industry"]
        query = task["query"]
        target = task["target"]
        policy = task["policy"]

        print(f"\n[{tid}/10] {ind}: '{query}' (target={target})")
        t0 = time.time()

        try:
            accepted, evidence = await discover_suppliers(
                settings,
                query,
                target=target,
                supplier_search_policy=policy,
            )
            elapsed = round(time.time() - t0, 1)

            # Search API metrics
            search_meta = evidence.get("search", {})
            yandex_reqs = search_meta.get("yandex_requests_count", 0)
            yandex_cost = search_meta.get("yandex_cost_rub", 0.0)

            # Check recovery rounds if any
            rec_rounds = evidence.get("recovery_rounds", [])
            for r in rec_rounds:
                r_search = r.get("search", {})
                yandex_reqs += r_search.get("yandex_requests_count", 0)
                yandex_cost += r_search.get("yandex_cost_rub", 0.0)

            total_yandex_reqs += yandex_reqs
            total_yandex_cost += yandex_cost

            verified_count = len(accepted)
            plants_count = sum(1 for s in accepted if s.get("site_type") == "manufacturer" or s.get("status") == "завод")
            has_contacts = sum(1 for s in accepted if s.get("phone") or s.get("email"))
            reg_matches = sum(1 for s in accepted if (s.get("minprom_registry_match") or {}).get("matched"))

            status = "PASS" if verified_count >= min(target, 5) else "WARN"

            res = {
                "id": tid,
                "industry": ind,
                "query": query,
                "status": status,
                "found_count": verified_count,
                "plants_count": plants_count,
                "has_contacts": has_contacts,
                "reg_matches": reg_matches,
                "yandex_reqs": yandex_reqs,
                "yandex_cost_rub": round(yandex_cost, 2),
                "recovery_rounds": len(rec_rounds),
                "elapsed_sec": elapsed,
                "sample_suppliers": [
                    {
                        "name": s.get("company_name", ""),
                        "site": s.get("site", ""),
                        "phone": s.get("phone", ""),
                        "email": s.get("email", ""),
                    }
                    for s in accepted[:3]
                ],
            }
            results.append(res)
            print(f"  -> {status}: Найдено {verified_count} поставщиков ({plants_count} заводов, {has_contacts} с контактами) | Яндекс: {yandex_reqs} запр. ({yandex_cost:.2f} ₽) | {elapsed}с")
            for i, s in enumerate(accepted[:3], 1):
                print(f"     {i}. {s.get('company_name')} ({s.get('site')}) - {s.get('phone') or s.get('email') or 'контакты на сайте'}")

        except Exception as exc:
            elapsed = round(time.time() - t0, 1)
            print(f"  -> FAIL in {ind}: {exc}")
            results.append({
                "id": tid,
                "industry": ind,
                "status": "FAIL",
                "error": str(exc),
                "elapsed_sec": elapsed,
            })

    out_file = Path(__file__).resolve().parent / "benchmark_10_procurements_efficiency_results.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 95)
    print("BENCHMARK SUMMARY REPORT (10 Procurements)")
    print("=" * 95)
    print(f"{'#':<3} | {'Отрасль':<24} | {'Статус':<6} | {'Поставщ.':<8} | {'Заводы':<6} | {'Контакты':<8} | {'Яндекс запр.':<12} | {'Цена (₽)':<8} | {'Время':<6}")
    print("-" * 95)
    for r in results:
        if r.get("status") != "FAIL":
            print(f"{r['id']:<3} | {r['industry']:<24} | {r['status']:<6} | {r['found_count']:<8} | {r['plants_count']:<6} | {r['has_contacts']:<8} | {r['yandex_reqs']:<12} | {r['yandex_cost_rub']:<8.2f} | {r['elapsed_sec']:<6}s")
        else:
            print(f"{r['id']:<3} | {r['industry']:<24} | FAIL   | -        | -      | -        | -            | -        | {r['elapsed_sec']}s")
    print("-" * 95)
    avg_cost = total_yandex_cost / max(1, len(results))
    avg_reqs = total_yandex_reqs / max(1, len(results))
    print(f"ИТОГО ПО 10 ЗАКУПКАМ: {total_yandex_reqs} запросов Яндекс API | Общая стоимость: {total_yandex_cost:.2f} ₽")
    print(f"СРЕДНЕЕ НА ОДНУ ЗАКУПКУ: {avg_reqs:.1f} запросов | СРЕДНЯЯ СТОИМОСТЬ: {avg_cost:.2f} ₽ (было 5.50+ ₽!)")
    print("=" * 95)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
