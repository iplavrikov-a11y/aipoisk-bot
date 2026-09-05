import asyncio
import os
import sys
import time
import json
import sqlite3
import psycopg2
from dataclasses import dataclass
from typing import Any

# Set paths
sys.path.insert(0, '/root/projects/aipoisk-bot/backend')
import dotenv
dotenv.load_dotenv('/root/projects/emailagent/.env')
sys.path.insert(0, '/root/projects/emailagent')

# Load modules
from app import supplier_search as ts
from backend.services import supplier_search_v2 as es
from backend.services.supplier_discovery import service as es_serv

# 30 Real procurement test dataset selected from TenderLex and EmailAgent DBs
BENCHMARK_ITEMS = [
    # 1-10: Industrial Equipment & Machinery
    {"id": 1, "title": "Бисерная мельница лабораторная и промышленная", "category": "мельницы", "okpd2": "28.92.12.110"},
    {"id": 2, "title": "Вакуумная насосная станция двухроторная", "category": "вакуумные насосы", "okpd2": "28.13.11.110"},
    {"id": 3, "title": "Установка ручной лазерной очистки металла 1500 Вт", "category": "лазерное оборудование", "okpd2": "28.41.33.190"},
    {"id": 4, "title": "Зачистная машина для обработки сварных швов", "category": "зачистные станки", "okpd2": "28.41.31.110"},
    {"id": 5, "title": "Таль электрическая канатная г/п 5 тонн", "category": "грузоподъемное оборудование", "okpd2": "28.22.11.110"},
    {"id": 6, "title": "Машина для ямочного ремонта дорог прицепная", "category": "дорожная техника", "okpd2": "28.92.21.110"},
    {"id": 7, "title": "Комплектная трансформаторная подстанция КТПН 630 кВА", "category": "трансформаторные подстанции", "okpd2": "27.11.41.000"},
    {"id": 8, "title": "Установка термокомпрессионной сварки микросхем", "category": "микроэлектронное оборудование", "okpd2": "28.99.39.190"},
    {"id": 9, "title": "Заглушенная камера со встроенным источником звука", "category": "испытательное оборудование", "okpd2": "26.51.66.190"},
    {"id": 10, "title": "Роботизированный вилочный погрузчик AGV", "category": "складская робототехника", "okpd2": "28.22.15.110"},
    
    # 11-20: Technical Products, Components & Consumables
    {"id": 11, "title": "Датчик электрической проводимости ДП-2С ВР30.02.000-01", "category": "КИПиА / датчики", "okpd2": "26.51.52.110"},
    {"id": 12, "title": "Канат стальной оцинкованный ГОСТ 3077-80 36.5 мм", "category": "стальные канаты", "okpd2": "25.93.11.110"},
    {"id": 13, "title": "Сильфонные компенсаторы КСО Ду 200 Ру 16", "category": "трубопроводная арматура", "okpd2": "25.99.29.190"},
    {"id": 14, "title": "Пластиковые щиты ЩМП-П со степенью защиты IP65", "category": "электротехнические шкафы", "okpd2": "27.12.31.000"},
    {"id": 15, "title": "Лента конвейерная резинотканевая 2М-1000-4-ТК-200-2", "category": "конвейерные ленты", "okpd2": "22.19.40.110"},
    {"id": 16, "title": "Цепь тяговая пластинчатая катковая М80С1-3-160", "category": "приводные и тяговые цепи", "okpd2": "25.93.15.110"},
    {"id": 17, "title": "Маслоуловитель промышленный вертикальный МО-25", "category": "фильтрационное оборудование", "okpd2": "28.29.12.110"},
    {"id": 18, "title": "Уплотнения гребного вала дейдвудного устройства судна", "category": "судовые уплотнения", "okpd2": "22.19.73.110"},
    {"id": 19, "title": "Кассеты для тангенциальной фильтрации ультрафильтрационные", "category": "биотехнологические мембраны", "okpd2": "28.29.12.110"},
    {"id": 20, "title": "Мягкие контейнеры Биг-Бэг 4-стропные 1 тонна", "category": "промышленная упаковка", "okpd2": "13.92.21.110"},
    
    # 21-30: Materials, Chemistry, Electrical & Specialized Goods
    {"id": 21, "title": "Панель поликарбонатная сотовая 16 мм прозрачная", "category": "полимерные материалы", "okpd2": "22.21.42.120"},
    {"id": 22, "title": "Техпластины ТМКЩ средней твердости 10 мм ГОСТ 7338-90", "category": "резинотехнические изделия", "okpd2": "22.19.20.110"},
    {"id": 23, "title": "Материалы верхнего строения пути: рельсы Р65, подкладки КД65", "category": "железнодорожные материалы", "okpd2": "24.10.71.110"},
    {"id": 24, "title": "Фильтры масляные тонкой очистки для газовой турбины GT13E2", "category": "турбинные фильтры", "okpd2": "28.29.12.110"},
    {"id": 25, "title": "Фильтры воздушные карманные ФВК G4/F7 для вентиляции", "category": "вентиляционные фильтры", "okpd2": "28.25.14.110"},
    {"id": 26, "title": "Оптический кабель в грозозащитном тросе ОКГТ 48 волокон", "category": "кабельная продукция", "okpd2": "27.31.12.000"},
    {"id": 27, "title": "Устройства пожаротушения самосрабатывающие порошковые ОСП-1", "category": "пожарное оборудование", "okpd2": "28.29.22.110"},
    {"id": 28, "title": "Фторопластовая прокладка Ф4 во вкладыш пятового устройства", "category": "фторопластовые изделия", "okpd2": "22.29.29.190"},
    {"id": 29, "title": "Система контроля бортовых и наземных радиостанций", "category": "радиоизмерительное оборудование", "okpd2": "26.51.44.000"},
    {"id": 30, "title": "Установка лазерного скрайбирования полупроводниковых пластин", "category": "лазерные микроустановки", "okpd2": "28.99.39.190"},
]

async def run_benchmark():
    print("=" * 80)
    print("STARTING 30-PROCUREMENT REAL-WORLD SEARCH ENGINE BENCHMARK")
    print("Comparing: TenderLex (aipoisk-bot) vs EmailAgent (emailagent)")
    print("=" * 80)
    
    results = []
    
    for item in BENCHMARK_ITEMS:
        item_id = item["id"]
        title = item["title"]
        cat = item["category"]
        okpd2 = item["okpd2"]
        
        print(f"\n[{item_id}/30] Evaluating: {title} (Категория: {cat}, ОКПД2: {okpd2})")
        
        # 1. TenderLex Minprom GISP Search
        t0 = time.perf_counter()
        tl_queries = [title, cat, okpd2]
        tl_gisp_entries = await ts.search_minprom_registry_entries(tl_queries, max_results=20)
        tl_gisp_time = (time.perf_counter() - t0) * 1000
        
        # 2. EmailAgent Minprom GISP Search
        t0 = time.perf_counter()
        ea_queries = [title, cat, okpd2]
        ea_gisp_entries = await es.search_gisp_product_registry_entries(ea_queries, max_entries=20)
        ea_gisp_time = (time.perf_counter() - t0) * 1000
        
        # 3. DNS Fast pre-check benchmark on candidate domains
        sample_domains = [
            "yandex.ru", "rosneft.ru", "severstal.com", "tmk-group.ru", "sibur.ru",
            "nonexistent-supplier-bogus-domain-999.ru", "fake-pipe-factory-xyz.com"
        ]
        
        t0 = time.perf_counter()
        tl_dns_checks = []
        for d in sample_domains:
            tl_dns_checks.append(await ts.candidate_domain_resolves_fast(d))
        tl_dns_time = (time.perf_counter() - t0) * 1000
        
        t0 = time.perf_counter()
        ea_svc = es_serv.SupplierDiscoveryService(browser=es_serv.AgentBrowserClient())
        ea_dns_checks = []
        for d in sample_domains:
            cand = es_serv.SupplierSearchCandidate(url=f"https://{d}", domain=d)
            ea_dns_checks.append(await ea_svc._candidate_domain_resolves(cand))
        ea_dns_time = (time.perf_counter() - t0) * 1000
        
        # 4. MX Record Verification check
        sample_emails = [
            "sales@yandex.ru", "info@rosneft.ru", "order@nonexistent-fake-domain-12345.ru"
        ]
        t0 = time.perf_counter()
        tl_mx_checks = []
        for em in sample_emails:
            tl_mx_checks.append(await ts.email_has_valid_mx(em))
        tl_mx_time = (time.perf_counter() - t0) * 1000
        
        res = {
            "id": item_id,
            "title": title,
            "category": cat,
            "okpd2": okpd2,
            "tl_gisp_count": len(tl_gisp_entries),
            "tl_gisp_time_ms": round(tl_gisp_time, 2),
            "ea_gisp_count": len(ea_gisp_entries),
            "ea_gisp_time_ms": round(ea_gisp_time, 2),
            "tl_dns_time_ms": round(tl_dns_time, 2),
            "ea_dns_time_ms": round(ea_dns_time, 2),
            "tl_mx_time_ms": round(tl_mx_time, 2),
            "tl_gisp_manufacturers": list({e.get("manufacturer") for e in tl_gisp_entries if e.get("manufacturer")})[:3],
            "ea_gisp_manufacturers": list({e.manufacturer for e in ea_gisp_entries if e.manufacturer})[:3],
        }
        results.append(res)
        print(f"  -> GISP: TL={len(tl_gisp_entries)} entries ({tl_gisp_time:.1f}ms) | EA={len(ea_gisp_entries)} entries ({ea_gisp_time:.1f}ms)")
        print(f"  -> DNS Precheck: TL={tl_dns_time:.1f}ms | EA={ea_dns_time:.1f}ms | MX Check: {tl_mx_time:.1f}ms")

    # Output aggregate metrics
    print("\n" + "=" * 80)
    print("AGGREGATE BENCHMARK RESULTS (30 Real Procurements)")
    print("=" * 80)
    
    total_tl_gisp = sum(r["tl_gisp_count"] for r in results)
    total_ea_gisp = sum(r["ea_gisp_count"] for r in results)
    avg_tl_gisp_time = sum(r["tl_gisp_time_ms"] for r in results) / len(results)
    avg_ea_gisp_time = sum(r["ea_gisp_time_ms"] for r in results) / len(results)
    avg_tl_dns_time = sum(r["tl_dns_time_ms"] for r in results) / len(results)
    avg_ea_dns_time = sum(r["ea_dns_time_ms"] for r in results) / len(results)
    avg_tl_mx_time = sum(r["tl_mx_time_ms"] for r in results) / len(results)
    
    print(f"Total GISP registry items found across 30 queries: TenderLex = {total_tl_gisp} | EmailAgent = {total_ea_gisp}")
    print(f"Avg GISP search speed: TenderLex = {avg_tl_gisp_time:.2f} ms | EmailAgent = {avg_ea_gisp_time:.2f} ms")
    print(f"Avg DNS Precheck speed (7 domains): TenderLex = {avg_tl_dns_time:.2f} ms | EmailAgent = {avg_ea_dns_time:.2f} ms")
    print(f"Avg MX Validation speed (3 emails): TenderLex = {avg_tl_mx_time:.2f} ms")
    
    with open('/root/projects/aipoisk-bot/scripts/benchmark_comparison_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "total_items": len(results),
                "total_tl_gisp_found": total_tl_gisp,
                "total_ea_gisp_found": total_ea_gisp,
                "avg_tl_gisp_time_ms": round(avg_tl_gisp_time, 2),
                "avg_ea_gisp_time_ms": round(avg_ea_gisp_time, 2),
                "avg_tl_dns_time_ms": round(avg_tl_dns_time, 2),
                "avg_ea_dns_time_ms": round(avg_ea_dns_time, 2),
                "avg_tl_mx_time_ms": round(avg_tl_mx_time, 2),
            },
            "cases": results
        }, f, ensure_ascii=False, indent=2)
    print("Benchmark data saved to /root/projects/aipoisk-bot/scripts/benchmark_comparison_results.json")

if __name__ == '__main__':
    asyncio.run(run_benchmark())
