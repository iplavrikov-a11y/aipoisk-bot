"""Benchmark 10 diverse industries for Minpromtorg & supplier discovery."""
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
    SUPPLIER_POLICY_MINPROM_ONLY,
    SUPPLIER_POLICY_MINPROM_PRIORITY,
    SUPPLIER_POLICY_NORMAL,
)

BENCHMARK_TASKS = [
    {
        "id": 1,
        "industry": "Лабораторная мебель",
        "query": "Шкаф вытяжной химический (кислотостойкий) и лабораторная мебель",
        "policy": SUPPLIER_POLICY_MINPROM_ONLY,
        "target": 10,
    },
    {
        "id": 2,
        "industry": "Светотехника",
        "query": "Светильники светодиодные уличные консольные ДКУ IP66",
        "policy": SUPPLIER_POLICY_MINPROM_PRIORITY,
        "target": 8,
    },
    {
        "id": 3,
        "industry": "Кабельная продукция",
        "query": "Кабель силовой ВВГнг(А)-FRLS 3х2.5 ГОСТ 31996-2012",
        "policy": SUPPLIER_POLICY_MINPROM_PRIORITY,
        "target": 8,
    },
    {
        "id": 4,
        "industry": "Полимерные трубы",
        "query": "Трубы напорные из полиэтилена ПЭ 100 ГОСТ 18599-2001 для питьевого водоснабжения",
        "policy": SUPPLIER_POLICY_MINPROM_PRIORITY,
        "target": 8,
    },
    {
        "id": 5,
        "industry": "КИПиА / Датчики",
        "query": "Датчики давления микропроцессорные Метран 150 с токовым выходом 4-20 мА",
        "policy": SUPPLIER_POLICY_MINPROM_PRIORITY,
        "target": 8,
    },
    {
        "id": 6,
        "industry": "Запорная арматура",
        "query": "Клапаны запорные фланцевые стальные 15с65нж Ду50 Ру16",
        "policy": SUPPLIER_POLICY_MINPROM_PRIORITY,
        "target": 8,
    },
    {
        "id": 7,
        "industry": "Энергетика / Трансформаторы",
        "query": "Трансформаторы силовые масляные герметичные ТМГ 1000/10/0.4",
        "policy": SUPPLIER_POLICY_MINPROM_PRIORITY,
        "target": 8,
    },
    {
        "id": 8,
        "industry": "Медоборудование",
        "query": "Кровати медицинские функциональные трехсекционные с электроприводом",
        "policy": SUPPLIER_POLICY_MINPROM_PRIORITY,
        "target": 8,
    },
    {
        "id": 9,
        "industry": "Фасовочное оборудование",
        "query": "Автоматическая машина для фасовки и упаковки сыпучих продуктов",
        "policy": SUPPLIER_POLICY_NORMAL,
        "target": 8,
    },
    {
        "id": 10,
        "industry": "Спецодежда / СИЗ",
        "query": "Костюмы мужские для защиты от общих производственных загрязнений и механических воздействий ГОСТ 12.4.280-2014",
        "policy": SUPPLIER_POLICY_MINPROM_PRIORITY,
        "target": 8,
    },
]

async def run_benchmark():
    with SessionLocal() as db:
        settings = get_or_create_settings(db)
    
    print("=" * 80)
    print(f"BENCHMARK START: 10 Diverse Industry Tasks")
    print(f"Server: 202.71.13.57 | Python {sys.version.split()[0]}")
    print("=" * 80)
    
    results = []
    
    for task in BENCHMARK_TASKS:
        idx = task["id"]
        industry = task["industry"]
        query = task["query"]
        policy = task["policy"]
        target = task["target"]
        
        print(f"\n[{idx}/10] Testing: {industry}")
        print(f"  Query: \"{query}\" (policy={policy}, target={target})")
        t0 = time.time()
        
        try:
            accepted, evidence = await discover_suppliers(
                settings,
                query,
                target=target,
                supplier_search_policy=policy,
            )
            elapsed = round(time.time() - t0, 1)
            verified_count = len(accepted)
            reg_matches = sum(1 for s in accepted if (s.get("minprom_registry_match") or {}).get("matched"))
            plants_count = sum(1 for s in accepted if s.get("site_type") == "manufacturer" or s.get("status") == "завод")
            has_contacts = sum(1 for s in accepted if s.get("phone") or s.get("email"))
            
            status = "PASS" if verified_count >= min(target, 5) else "WARN"
            
            res_item = {
                "id": idx,
                "industry": industry,
                "query": query,
                "policy": policy,
                "status": status,
                "found_count": verified_count,
                "registry_count": reg_matches,
                "plants_count": plants_count,
                "has_contacts_count": has_contacts,
                "elapsed_sec": elapsed,
                "top_suppliers": [
                    {
                        "name": s.get("company_name", ""),
                        "site": s.get("site", ""),
                        "phone": s.get("phone", ""),
                        "email": s.get("email", ""),
                        "registry_number": (s.get("minprom_registry_match") or {}).get("registry_number", ""),
                        "fit": s.get("product_fit", ""),
                    }
                    for s in accepted[:5]
                ],
            }
            results.append(res_item)
            
            print(f"  -> Result: {status} | Found: {verified_count} suppliers ({reg_matches} in Minpromtorg, {plants_count} plants) in {elapsed}s")
            for i, s in enumerate(accepted[:3], 1):
                reg = (s.get("minprom_registry_match") or {}).get("registry_number", "")
                reg_str = f" [Реестр: {reg}]" if reg else ""
                print(f"     {i}. {s.get('company_name')} | {s.get('site')} | {s.get('phone') or s.get('email') or 'нет контакта'}{reg_str}")
                
        except Exception as e:
            elapsed = round(time.time() - t0, 1)
            print(f"  -> ERROR in {industry}: {e}")
            results.append({
                "id": idx,
                "industry": industry,
                "query": query,
                "policy": policy,
                "status": "FAIL",
                "error": str(e),
                "elapsed_sec": elapsed,
            })
            
    out_file = Path(__file__).resolve().parent / "benchmark_10_minprom_results.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print("\n" + "=" * 80)
    print("FINAL BENCHMARK SUMMARY (10 Industries)")
    print("=" * 80)
    print(f"{'#':<3} | {'Отрасль':<25} | {'Статус':<6} | {'Всего':<6} | {'Реестр':<6} | {'Заводы':<6} | {'Время':<6}")
    print("-" * 80)
    for r in results:
        print(f"{r['id']:<3} | {r['industry']:<25} | {r['status']:<6} | {r.get('found_count', 0):<6} | {r.get('registry_count', 0):<6} | {r.get('plants_count', 0):<6} | {r.get('elapsed_sec', 0)}s")
    print("=" * 80)
    print(f"Results saved to: {out_file}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
