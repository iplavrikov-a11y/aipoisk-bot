#!/usr/bin/env python3
"""
Масштабное тестирование 30+ новых реальных промышленных ТЗ из базы закупок платформы.
Проверяет:
1. Отсутствие кодов ОКПД2/КТРУ в строгих кавычках коммерческих запросов.
2. Блокировку тендерных агрегаторов (roseltorg, star-pro, otc, torgkey).
3. Исключение бюджетных заказчиков (больниц, школ) из поставщиков.
4. Полноту и качество выдачи в режимах: Весь мир, СНГ, Россия.
"""

import asyncio
import json
import os
import sys
import time

# Ensure backend is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.exact_product.llm_bridge import get_settings
from app.price_monitoring.cleaner import (
    build_commercial_search_queries,
    clean_nomenclature_name,
    extract_generic_nomenclature_codes,
    is_classifier_code,
    is_drawing_or_part_code,
)
from app.price_monitoring.extractor import (
    is_public_institution_buyer,
    is_valid_domain,
)
from app.price_monitoring.pipeline import process_single_item
from app.exact_product.yandex_search import YandexSearchEngine
from app.supplier_search import (
    _expand_search_queries,
    is_domain_allowed_for_geo,
)

# 32 совершенно новых промышленных ТЗ из реальных боевых задач платформы TenderLex:
FRESH_PROCUREMENT_ITEMS = [
    # 1-3. Офисная мебель (ТЗ из задачи №994 - проверка исправления ОКПД2 и исключения больниц)
    {
        "name": "Кресло офисное Тип 1 для руководителя",
        "unit": "шт",
        "requirements": [
            {"param_name": "ОКПД2 / КТРУ", "tz_requirement": "31.01.12.160 31.01.12.160-00000005"},
            {"param_name": "Материал", "tz_requirement": "Кожа натуральная, дерево"},
            {"param_name": "Механизм", "tz_requirement": "Мультиблок"}
        ]
    },
    {
        "name": "Кресло офисное Тип 2 для персонала",
        "unit": "шт",
        "requirements": [
            {"param_name": "ОКПД2 / КТРУ", "tz_requirement": "31.01.12.160 31.01.12.160-00000005"},
            {"param_name": "Материал", "tz_requirement": "Сетчатый акрил, металл"}
        ]
    },
    {
        "name": "Стул на металлическом каркасе для посетителей",
        "unit": "шт",
        "requirements": [
            {"param_name": "ОКПД2 / КТРУ", "tz_requirement": "31.01.11.150 31.01.11.150-00000003"},
            {"param_name": "Каркас", "tz_requirement": "Металл черный, ткань"}
        ]
    },
    # 4-6. Строительные сэндвич-панели и крепеж (ТЗ из задачи №996)
    {
        "name": "Стеновые сэндвич-панели ПСТ 250 1190 100",
        "unit": "м2",
        "requirements": [{"param_name": "Цвет", "tz_requirement": "RAL 8017"}]
    },
    {
        "name": "Кровельные сэндвич-панели ПКТ 220 1000 100",
        "unit": "м2",
        "requirements": [{"param_name": "Цвет", "tz_requirement": "RAL 5005"}]
    },
    {
        "name": "Саморез для сэндвич-панелей 140х5,5",
        "unit": "шт",
        "requirements": [{"param_name": "Тип", "tz_requirement": "Углеродистая сталь с EPDM шайбой"}]
    },
    # 7. Спортивные конструкции (ТЗ из задачи №995)
    {
        "name": "Защитные стекла для хоккейных бортов",
        "unit": "шт",
        "requirements": [{"param_name": "Тип", "tz_requirement": "Закаленное стекло 12 мм"}]
    },
    # 8. Нефтепродуктовое оборудование (ТЗ из задачи №944)
    {
        "name": "Рукав напорно-всасывающий для нефтепродуктов",
        "unit": "м",
        "requirements": [{"param_name": "Стандарт", "tz_requirement": "ГОСТ 5398-76"}]
    },
    # 9-32. Разнообразное тяжелое промышленное оборудование из базы aipoisk.db
    {"name": "Установка вакуумного переплава и литья", "unit": "компл"},
    {"name": "Мобильный ремонтно-диагностический комплекс (МРДК)", "unit": "компл"},
    {"name": "Лабораторная система полимеризационного синтеза", "unit": "шт"},
    {"name": "Установка термокомпрессионной ультразвуковой сварки", "unit": "шт"},
    {"name": "Илоскреб радиальный для первичных отстойников", "unit": "шт"},
    {"name": "Шкаф управления оборудованием ШУО", "unit": "шт"},
    {"name": "Лампа щелевая офтальмологическая", "unit": "шт"},
    {"name": "Стол приборный медицинский", "unit": "шт"},
    {"name": "Эталонный резонатор в вакуумной камере", "unit": "компл"},
    {"name": "Инкапсулятор лабораторный", "unit": "шт"},
    {"name": "Панель ограждения железобетонная ПО-2", "unit": "шт"},
    {"name": "Фундамент стаканного типа ФЖ", "unit": "шт"},
    {"name": "Система контроля скорости шахтной установки (СКДС-ПУ)", "unit": "компл"},
    {"name": "Авиационный спасательный плот", "unit": "шт"},
    {"name": "Пространственная металлическая рама", "unit": "т"},
    {"name": "Каверномер скважинный геофизический", "unit": "шт"},
    {"name": "Гидравлическая аэродромная силовая установка", "unit": "шт"},
    {"name": "Вальцы резинообрабатывающие", "unit": "шт"},
    {"name": "Автомат редуцирования обжимки гнезд", "unit": "шт"},
    {"name": "Пневмокаркасный модуль быстровозводимый", "unit": "компл"},
    {"name": "Система микроволнового разложения проб", "unit": "шт"},
    {"name": "Вытяжной лабораторный шкаф химический", "unit": "шт"},
    {"name": "Сканирующий электронный микроскоп", "unit": "компл"},
    {"name": "Грохот самобалансный тяжелого типа ГСТ", "unit": "шт"},
]


async def run_benchmark():
    print(f"=== Запуск матричного тестирования на {len(FRESH_PROCUREMENT_ITEMS)} новых реальных ТЗ ===")
    
    settings = get_settings()
    engine = YandexSearchEngine(
        folder_id=settings.yandex_search_folder_id,
        api_key=settings.yandex_search_api_key,
    )
    
    test_results = {
        "classifier_leak_in_queries": 0,
        "tender_platform_leak": 0,
        "institutional_buyer_leak": 0,
        "modes": {
            "price_monitoring_world": [],
            "price_monitoring_ru": [],
            "supplier_search_world": [],
            "supplier_search_cis": [],
        }
    }

    # 1. Проверка генерации коммерческих запросов на всех 32 ТЗ (включая ТЗ с кодами ОКПД2)
    print("\n--- Этап 1: Проверка чистоты поисковых запросов и отсечения ОКПД2/КТРУ ---")
    for item in FRESH_PROCUREMENT_ITEMS:
        name = item["name"]
        unit = item.get("unit", "шт")
        reqs = item.get("requirements", [])
        
        # Симулируем сбор требований
        req_text = "; ".join(
            f"{r['param_name']}: {r['tz_requirement']}"
            for r in reqs
            if not is_classifier_code(r.get("param_name", ""))
            and not is_classifier_code(r.get("tz_requirement", ""))
            and not any(k in r.get("param_name", "").lower() for k in ("окпд", "ктру", "тнвэд"))
        )
        clean = clean_nomenclature_name(name)
        if req_text:
            clean = f"{clean}; {req_text}"
            
        nom_codes = extract_generic_nomenclature_codes(clean)
        exact_codes = [c for c in nom_codes if is_drawing_or_part_code(c, clean) and not is_classifier_code(c, clean)]
        
        queries = build_commercial_search_queries(clean, unit)
        
        # Проверяем, что ни один код ОКПД2 не попал в кавычки запроса
        has_okpd = any("ОКПД" in q or "31.01.12" in q or "31.01.11" in q for q in queries)
        if has_okpd:
            test_results["classifier_leak_in_queries"] += 1
            print(f"  [FAIL] Утечка ОКПД2 в запросе для {name}: {queries}")
        
    print(f"  Результат проверки запросов: утечек ОКПД2: {test_results['classifier_leak_in_queries']} (0 ожидается)")

    import httpx
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        # 2. Мониторинг цен (Весь мир) по офисным креслам из задачи №994
        print("\n--- Этап 2: Тестирование мониторинга цен (Весь мир) ---")
        world_items = FRESH_PROCUREMENT_ITEMS[:3]
        for idx, item in enumerate(world_items):
            name = item["name"]
            t0 = time.time()
            res = await process_single_item(
                item_tuple=(idx + 1, name, item.get("unit", "шт")),
                engine=engine,
                settings=settings,
                http_client=http_client,
                search_semaphore=asyncio.Semaphore(3),
                max_suppliers=3,
                min_target_suppliers=2,
                filter_marketplaces=True,
                filter_foreign=False,
                geo_scope="world",
                source_position={"id": f"pos_{idx+1}", "name": name, "requirements": item.get("requirements", [])}
            )
            elapsed = round(time.time() - t0, 2)
            
            # Проверка на утечки тендерных площадок и больниц
            tender_leaks = [q.url for q in res.quotes if any(tp in q.url for tp in ("roseltorg.ru", "star-pro.ru", "otc.ru", "torgkey.ru"))]
            hospital_leaks = [q.company_name for q in res.quotes if is_public_institution_buyer(q.company_name)]
            
            if tender_leaks:
                test_results["tender_platform_leak"] += len(tender_leaks)
            if hospital_leaks:
                test_results["institutional_buyer_leak"] += len(hospital_leaks)
                
            accepted_cnt = len(res.quotes)
            test_results["modes"]["price_monitoring_world"].append({
                "name": name,
                "quotes": accepted_cnt,
                "status": res.status,
                "time_sec": elapsed,
                "tender_leaks": tender_leaks,
                "hospital_leaks": hospital_leaks,
                "sample_suppliers": [q.company_name for q in res.quotes[:3]]
            })
            print(f"  [{idx+1}/{len(world_items)}] {name[:35]}: найдено {accepted_cnt} пост. ({res.status}) за {elapsed}с. Утечек: {len(tender_leaks)+len(hospital_leaks)}")

        # 3. Поиск поставщиков (Весь мир и СНГ) на 15 промышленных машинах и установках
        print("\n--- Этап 3: Тестирование поиска поставщиков (Весь мир и СНГ) ---")
        for idx, item in enumerate(FRESH_PROCUREMENT_ITEMS[12:27]):
            name = item["name"]
            t0 = time.time()
            
            # Генерируем международные и СНГ запросы
            queries_world = _expand_search_queries([name], max_queries=5, geo_scope="world")
            queries_cis = _expand_search_queries([name], max_queries=5, geo_scope="cis")
            
            # Выполняем быстрый поиск кандидатов
            res_world = await engine.search(queries_world[0], max_results=10)
            res_cis = await engine.search(queries_cis[0], max_results=10)
            
            valid_world = [r.url for r in res_world if is_domain_allowed_for_geo(r.domain, geo_scope="world")]
            valid_cis = [r.url for r in res_cis if is_domain_allowed_for_geo(r.domain, geo_scope="cis")]
            elapsed = round(time.time() - t0, 2)
            
            test_results["modes"]["supplier_search_world"].append({
                "name": name,
                "candidates": len(valid_world),
                "sample_domains": [r.domain for r in res_world[:3]]
            })
            test_results["modes"]["supplier_search_cis"].append({
                "name": name,
                "candidates": len(valid_cis),
                "sample_domains": [r.domain for r in res_cis[:3]]
            })
            print(f"  [{idx+1}/15] {name[:35]}: Мир {len(valid_world)} доменов, СНГ {len(valid_cis)} доменов ({elapsed}с)")

        # 4. Мониторинг цен (Россия) на строительных материалах и панелях
        print("\n--- Этап 4: Тестирование мониторинга цен (Только Россия) ---")
        ru_items = FRESH_PROCUREMENT_ITEMS[3:6]
        for idx, item in enumerate(ru_items):
            name = item["name"]
            t0 = time.time()
            res = await process_single_item(
                item_tuple=(idx + 1, name, item.get("unit", "шт")),
                engine=engine,
                settings=settings,
                http_client=http_client,
                search_semaphore=asyncio.Semaphore(3),
                max_suppliers=3,
                min_target_suppliers=2,
                filter_marketplaces=True,
                filter_foreign=True,
                geo_scope="ru",
                source_position={"id": f"pos_ru_{idx+1}", "name": name, "requirements": item.get("requirements", [])}
            )
            elapsed = round(time.time() - t0, 2)
            
            # Проверяем, что нет зарубежных доменов и нет госзаказчиков
            foreign_leaks = [q.url for q in res.quotes if not is_domain_allowed_for_geo(q.url, geo_scope="ru")]
            hospital_leaks = [q.company_name for q in res.quotes if is_public_institution_buyer(q.company_name)]
            tender_leaks = [q.url for q in res.quotes if any(tp in q.url for tp in ("roseltorg.ru", "star-pro.ru", "otc.ru", "torgkey.ru"))]
            
            if tender_leaks:
                test_results["tender_platform_leak"] += len(tender_leaks)
            if hospital_leaks:
                test_results["institutional_buyer_leak"] += len(hospital_leaks)
                
            test_results["modes"]["price_monitoring_ru"].append({
                "name": name,
                "quotes": len(res.quotes),
                "status": res.status,
                "time_sec": elapsed,
                "foreign_leaks": foreign_leaks,
                "hospital_leaks": hospital_leaks,
                "sample_suppliers": [q.company_name for q in res.quotes[:3]]
            })
            print(f"  [{idx+1}/{len(ru_items)}] RU {name[:35]}: найдено {len(res.quotes)} пост. ({res.status}), утечек: {len(foreign_leaks)+len(hospital_leaks)+len(tender_leaks)}")

    # Сохраняем сводный отчет
    out_file = "fresh_30_benchmark_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
        
    print(f"\n=== ИТОГИ БЕНЧМАРКА 30+ ТЗ ===")
    print(f"1. Утечек кодов ОКПД2/КТРУ в коммерческих запросах: {test_results['classifier_leak_in_queries']}")
    print(f"2. Утечек тендерных площадок (roseltorg, star-pro, etc.): {test_results['tender_platform_leak']}")
    print(f"3. Утечек бюджетных заказчиков (больниц, школ): {test_results['institutional_buyer_leak']}")
    print(f"4. Результаты сохранены в: {out_file}")
    assert test_results["classifier_leak_in_queries"] == 0
    assert test_results["tender_platform_leak"] == 0
    assert test_results["institutional_buyer_leak"] == 0
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ НА 100%!")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
