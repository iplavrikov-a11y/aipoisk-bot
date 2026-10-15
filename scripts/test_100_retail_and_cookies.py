#!/usr/bin/env python3
"""
TenderLex: 100 Diverse Commodity Test with Cookie & Retail Search Verification.
Tests 100 real procurement positions across retail, wholesale, electrical, tools,
electronics, construction, IT, stationery, and industrial sectors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import openpyxl
from dotenv import load_dotenv

sys.path.insert(0, "/root/projects/tenderlex")
sys.path.insert(0, "/root/projects/tenderlex/backend")
load_dotenv("/root/projects/tenderlex/.env")
load_dotenv()

from app.db import SessionLocal
from app.models import SystemSettings
from app.price_monitoring.pipeline import run_price_monitoring_pipeline
from app.price_monitoring.cookie_manager import cookie_manager
from scripts.benchmark_200_price_monitoring import BENCHMARK_220_ITEMS

# Set up logging
LOG_FILE = "/tmp/test_100_price_monitoring.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger("test_100")


# 100 precisely picked diverse positions from all 12 industries
SELECTED_100_ITEMS: List[Tuple[str, str, str]] = [
    # 1. Электротехника и кабель (15) - ETM, RS24, Минимакс
    ("Электротехника", "Кабель силовой ВВГнг(А)-LS 3х2.5 ГОСТ 31996", "м"),
    ("Электротехника", "Кабель силовой ВВГнг(А)-LS 5х16 ГОСТ 31996", "м"),
    ("Электротехника", "Кабель силовой бронированный ВБШвнг(А) 4х50", "м"),
    ("Электротехника", "Кабель контрольный КВВГнг(А) 7х1.5 ГОСТ 1508", "м"),
    ("Электротехника", "Провод установочный ПуВ 1х4 (ПВ-1)", "м"),
    ("Электротехника", "Провод соединительный ПВС 3х1.5 ГОСТ 7399", "м"),
    ("Электротехника", "Кабель огнестойкий FRLS КПСнг(А)-FRLS 1х2х0.75", "м"),
    ("Электротехника", "Автоматический выключатель ВА47-29 3Р 25А характеристика С IEK", "шт"),
    ("Электротехника", "Автоматический выключатель ВА47-100 3Р 80А характеристика D", "шт"),
    ("Электротехника", "Устройство защитного отключения УЗО ВД1-63 2Р 25А 30мА", "шт"),
    ("Электротехника", "Дифференциальный автомат АВДТ32 2Р 16А 30мА", "шт"),
    ("Электротехника", "Контактор электромагнитный КМИ-22510 25А 220В", "шт"),
    ("Электротехника", "Счетчик электрической энергии трехфазный Меркурий 230 АМ-01", "шт"),
    ("Электротехника", "Светильник светодиодный промышленный купольный 100 Вт IP65", "шт"),
    ("Электротехника", "Кабельный лоток перфорированный 100х50х3000 мм оцинкованный", "м"),

    # 2. Инструмент, метизы и СИЗ (15) - ВсеИнструменты, Лемана Про, 220 Вольт
    ("Инструмент и СИЗ", "Набор инструмента S04H624101S Jonnesway", "шт"),
    ("Инструмент и СИЗ", "Круг отрезной по металлу 125х1.2х22.2 Луга Абразив", "шт"),
    ("Инструмент и СИЗ", "Круг зачистной по металлу 125х6.0х22.2", "шт"),
    ("Инструмент и СИЗ", "Сверло по металлу спиральное 10.0 мм Р6М5 ГОСТ 10902", "шт"),
    ("Инструмент и СИЗ", "Ключ гаечный комбинированный 24 мм Cr-V ГОСТ 16983", "шт"),
    ("Инструмент и СИЗ", "Молоток слесарный 500 г с фибергласовой рукояткой", "шт"),
    ("Инструмент и СИЗ", "Диск алмазный отрезной сегментный 230 мм по бетону", "шт"),
    ("Инструмент и СИЗ", "Набор бит отверточных 32 предмета Bosch", "шт"),
    ("Инструмент и СИЗ", "Рулетка измерительная 5 м х 19 мм с фиксатором", "шт"),
    ("Инструмент и СИЗ", "Перчатки хлопчатобумажные трикотажные 4 нити с точечным ПВХ", "пар"),
    ("Инструмент и СИЗ", "Респиратор противоаэрозольный Алина-210 FFP2", "шт"),
    ("Инструмент и СИЗ", "Очки защитные закрытые с непрямой вентиляцией", "шт"),
    ("Инструмент и СИЗ", "Болт М16х60 ГОСТ 7798-70 оцинкованный", "кг"),
    ("Инструмент и СИЗ", "Шпилька резьбовая М12х1000 мм DIN 975 оцинк.", "шт"),
    ("Инструмент и СИЗ", "Анкер клиновой 12х100 мм оцинкованный", "шт"),

    # 3. Электроника, датчики и КИПиА (10) - ЧИП и ДИП, Метран, Данфосс
    ("КИПиА и IT", "Преобразователь давления измерительный Метран-150", "шт"),
    ("КИПиА и IT", "Датчик давления Danfoss MBS 3000 0-10 бар G1/4", "шт"),
    ("КИПиА и IT", "Термопреобразователь сопротивления ТСП 0196 Pt100", "шт"),
    ("КИПиА и IT", "Манометр технический МТП-100/1-ВУ 0-1.6 МПа М20х1.5", "шт"),
    ("КИПиА и IT", "Манометр электроконтактный ЭКМ-1У 0-1.0 МПа", "шт"),
    ("КИПиА и IT", "Термометр биметаллический ТБ-3 0-120 С", "шт"),
    ("КИПиА и IT", "Мультиметр цифровой Fluke 179", "шт"),
    ("КИПиА и IT", "Токовые клещи электроизмерительные Mastech MS2008B", "шт"),
    ("КИПиА и IT", "Припой ПОС-61 проволока 2.0 мм ГОСТ 21930", "кг"),
    ("КИПиА и IT", "Реле промежуточное РЭП-26 24В DC", "шт"),

    # 4. IT, серверы и оргтехника (8) - ДНС, Ситилинк, Регард
    ("КИПиА и IT", "Проц.IntelCore i5-9400F 2900 LGA1151v2", "шт"),
    ("КИПиА и IT", "Процессор серверный Intel Xeon Silver 4310 LGA4189 OEM", "шт"),
    ("КИПиА и IT", "Твердотельный накопитель SSD 1TB Kingston KC600 SATA3", "шт"),
    ("КИПиА и IT", "Модуль оперативной памяти DDR4 16GB Kingston Fury 3200MHz", "шт"),
    ("КИПиА и IT", "Источник бесперебойного питания ИБП APC Smart-UPS 1500VA", "шт"),
    ("КИПиА и IT", "Коммутатор сетевой управляемый 24 порта Gigabit Ethernet", "шт"),
    ("КИПиА и IT", "Светильник светодиодный офисный Армстронг 36 Вт 595х595", "шт"),
    ("КИПиА и IT", "Лампа светодиодная LED Е27 15 Вт 4000К", "шт"),

    # 5. Канцелярия, бумага и офис (6) - Комус, Офисмаг, ForOffice
    ("Канцелярия", "Бумага офисная А4 белая 80 г/м2 500 листов SvetoCopy", "уп"),
    ("Канцелярия", "Пружина пластик.19мм 100шт/НЕ ИСП", "уп"),
    ("Канцелярия", "Лента диаграммная 0-100 120мм Р1763", "м2"),
    ("Канцелярия", "Ветошь х/б", "кг"),
    ("Канцелярия", "Мягкий контейнер Биг-бэг МКР 4-стропный 95х95х130 см", "шт"),
    ("Канцелярия", "Пленка полиэтиленовая техническая 200 мкм рукав", "м2"),

    # 6. Стройматериалы и отделка (12) - Лемана Про, Петрович, Сатурн
    ("Стройматериалы", "Цемент ПЦ 500 Д20 мешок 50 кг ГОСТ 31108", "т"),
    ("Стройматериалы", "Гипсокартон ГКЛВ влагостойкий 12.5 мм 2500х1200", "м2"),
    ("Стройматериалы", "Фанера ФК 1520х1520х15 мм сорт 4/4", "шт"),
    ("Стройматериалы", "Плита OSB-3 влагостойкая 2500х1250х12 мм", "лист"),
    ("Стройматериалы", "Доска обрезная хвойная 50х150х6000 мм 1 сорт ГОСТ 8486", "м3"),
    ("Стройматериалы", "Грунтовка глубокого проникновения Ceresit CT 17 10л", "л"),
    ("Стройматериалы", "Клей для плитки Ceresit CM 11 Plus мешок 25 кг", "кг"),
    ("Стройматериалы", "Штукатурка гипсовая Ротбанд мешок 30 кг Knauf", "кг"),
    ("Стройматериалы", "Шпаклевка финишная Vetonit LR+ мешок 20 кг", "кг"),
    ("Стройматериалы", "Пена монтажная полиуретановая всесезонная 750 мл", "шт"),
    ("Стройматериалы", "Герметик силиконовый нейтральный картридж 310 мл", "шт"),
    ("Стройматериалы", "Керамогранит серый матовый 600х600 мм", "м2"),

    # 7. Теплоизоляция и гидроизоляция (8) - Технониколь, Изоспан
    ("Изоляция", "Теплоизоляция из экструзионного пенополистирола (XPS) 50 мм", "м3"),
    ("Изоляция", "Минераловатные плиты Техновент Стандарт 100 мм", "м3"),
    ("Изоляция", "Утеплитель минераловатный Роклайт 50 мм 8.64 м2", "уп"),
    ("Изоляция", "Праймер битумный Технониколь №01 ведро 20л", "л"),
    ("Изоляция", "Гидроизоляция Техноэласт ЭПП рулон 10 м2", "м2"),
    ("Изоляция", "Мембрана супердиффузионная ветро-влагозащитная Изоспан АМ", "м2"),
    ("Изоляция", "Трубки теплоизоляционные из вспененного полиэтилена 28/9 мм", "м"),
    ("Изоляция", "Асбестовый картон КАОН-1 толщина 4 мм лист", "кг"),

    # 8. Металлопрокат и трубы (10) - Металлсервис, СПК
    ("Металлопрокат", "Лист 10 ВСт3сп ГОСТ 19903/НЕ ИСП", "т"),
    ("Металлопрокат", "Полоса 4х20 Ст0 ГОСТ 103/НЕ ИСП", "т"),
    ("Металлопрокат", "Круг стальной 40 мм ст45 ГОСТ 2590-2006", "кг"),
    ("Металлопрокат", "Арматура А500С ф12 мм ГОСТ 34028-2016", "т"),
    ("Металлопрокат", "Труба профильная 40х40х2.0 ГОСТ 8639-82", "м"),
    ("Металлопрокат", "Труба электросварная 108х4.0 ГОСТ 10704-91", "м"),
    ("Металлопрокат", "Уголок равнополочный 50х50х5 ГОСТ 8509-93", "т"),
    ("Металлопрокат", "Швеллер 10П ГОСТ 8240-97", "т"),
    ("Металлопрокат", "Лист оцинкованный 0.55 мм ГОСТ 14918-80", "т"),
    ("Металлопрокат", "Лист нержавеющий AISI 304 2.0 мм", "кг"),

    # 9. Сварочные газы и смеси (6) - Евробаллон, Лидергаз, Уралтехгаз
    ("Газы и сварка", "Кислород газ.ГОСТ 5583(м3)", "м3"),
    ("Газы и сварка", "Пропан сжиженный бал.50л ТУ 51-882", "кг"),
    ("Газы и сварка", "Азот газообразный особой чистоты бал.40л ГОСТ 9293", "м3"),
    ("Газы и сварка", "Аргон газообразный высший сорт бал.40л ГОСТ 10157", "м3"),
    ("Газы и сварка", "Углекислота жидкая бал.40л ГОСТ 8050-85", "кг"),
    ("Газы и сварка", "Электрод ОЗС-12 4мм (кг)", "кг"),

    # 10. ГСМ и технические масла (6) - Синтек, Лукойл, Газпромнефть
    ("ГСМ и масла", "Смазка Литол-24 ГОСТ 21150 ведро 18 кг", "кг"),
    ("ГСМ и масла", "Масло индустриальное И-20А ГОСТ 20799 бочка 200л", "л"),
    ("ГСМ и масла", "Масло моторное М-10Г2к ГОСТ 8581 бочка 200л", "л"),
    ("ГСМ и масла", "Масло гидравлическое ВМГЗ ТУ 38.101479-00 бочка 200л", "л"),
    ("ГСМ и масла", "Тосол А-40М бочка 200 кг", "кг"),
    ("ГСМ и масла", "Тормозная жидкость ДОТ-4 флакон 910 г", "шт"),

    # 11. Трубопроводная арматура (4) - Гремир, ЛД, Армагус
    ("Арматура", "Задвижка чугунная фланцевая 30ч6бр Ду100 Ру10", "шт"),
    ("Арматура", "Кран шаровый фланцевый стальной 11с67п Ду80 Ру16", "шт"),
    ("Арматура", "Отвод стальной 90 градусов 89х3.5 ст20 ГОСТ 17375-2001", "шт"),
    ("Арматура", "Набивка ВАТИ-202 22х22мм", "кг"),

    # 12. Механика и дробильное оборудование (4) - Проммаш, Автопитер
    ("Дробильное и механика", "Било Л-04.524", "шт"),
    ("Дробильное и механика", "Палец К4-79", "шт"),
    ("Дробильное и механика", "Подшипник 13630 ГОСТ 8545", "шт"),
    ("Дробильное и механика", "Ремень клиновой приводной профиль В-2500 ГОСТ 1284", "шт"),
]

SELECTED_100_ITEMS = SELECTED_100_ITEMS[:100]
assert len(SELECTED_100_ITEMS) == 100, f"Expected 100 items, got {len(SELECTED_100_ITEMS)}"


def build_input_excel(target_path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Спецификация"
    ws.append(["№ п/п", "Отрасль / Категория", "Наименование номенклатуры", "Ед. изм."])
    for idx, (cat, name, unit) in enumerate(SELECTED_100_ITEMS, start=1):
        ws.append([idx, cat, name, unit])
    wb.save(target_path)
    logger.info("Created 100-position test specification Excel at %s", target_path)


async def main():
    start_ts = time.time()
    db = SessionLocal()
    settings = db.query(SystemSettings).first()
    if not settings:
        logger.error("SystemSettings not found in database!")
        return

    logger.info("=" * 80)
    logger.info("🚀 STARTING 100-POSITION LIVE PRICE MONITORING TEST (COOKIES & RETAIL)")
    logger.info("Yandex Search API: %s", bool(settings.yandex_search_api_key))
    logger.info("DaData API Key: %s", bool(os.getenv("DADATA_API_KEY")))
    logger.info("Configured Domain Cookies: %s", list(cookie_manager.list_domains().keys()))
    logger.info("=" * 80)

    input_path = "/tmp/test_100_input_spec.xlsx"
    output_path = "/tmp/test_100_price_monitoring_report.xlsx"
    build_input_excel(input_path)

    with open(input_path, "rb") as f:
        file_bytes = f.read()

    def progress(pct: int, msg: str):
        logger.info("[PROGRESS %3d%%] %s", pct, msg)

    # Execute the full real pipeline
    result = await run_price_monitoring_pipeline(
        file_bytes=file_bytes,
        settings=settings,
        output_excel_path=output_path,
        price_per_position_rub=50.0,
        progress_callback=progress,
        max_suppliers=5,
        max_parallel_items=5,
    )

    elapsed_sec = time.time() - start_ts

    # Deep diagnostic analysis of results
    total_items = len(result.items)
    found_items = sum(1 for it in result.items if it.has_prices)
    all_quotes = [q for it in result.items for q in it.quotes if q.price_rub > 0]
    quotes_count = len(all_quotes)
    avg_quotes_per_item = round(quotes_count / max(1, total_items), 2)
    avg_quotes_per_found = round(quotes_count / max(1, found_items), 2)

    # Domain distribution
    from urllib.parse import urlparse
    domain_counts: dict[str, int] = {}
    cookie_domain_quotes: dict[str, int] = {d: 0 for d in cookie_manager.list_domains()}
    
    inn_resolved_count = 0
    unit_converted_count = 0
    official_opf_count = 0

    for q in all_quotes:
        dom = urlparse(q.url).netloc.lower()
        if dom.startswith("www."):
            dom = dom[4:]
        domain_counts[dom] = domain_counts.get(dom, 0) + 1

        for cd in cookie_domain_quotes:
            if dom == cd or dom.endswith("." + cd):
                cookie_domain_quotes[cd] += 1

        if q.inn and len(q.inn) in (10, 12):
            inn_resolved_count += 1
        if q.conversion_comment:
            unit_converted_count += 1
        if any(q.company_name.startswith(p) for p in ("ООО", "АО", "ЗАО", "ПАО", "ИП", "Общество")):
            official_opf_count += 1

    # Excel Report Inspection
    wb_out = openpyxl.load_workbook(output_path, data_only=False)
    sheet1_valid = "Пример отчета" in wb_out.sheetnames
    sheet2_valid = "Детализированный реестр" in wb_out.sheetnames
    ws1 = wb_out["Пример отчета"]
    formulas_min_count = sum(1 for r in range(5, ws1.max_row + 1) if str(ws1.cell(row=r, column=13).value or "").startswith("=MIN"))
    formulas_avg_count = sum(1 for r in range(5, ws1.max_row + 1) if str(ws1.cell(row=r, column=14).value or "").startswith("=AVERAGE"))
    row_height_sample = ws1.row_dimensions[5].height

    metrics = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_sec": round(elapsed_sec, 1),
        "total_positions": total_items,
        "found_positions": found_items,
        "coverage_pct": round((found_items / total_items) * 100, 1),
        "total_quotes": quotes_count,
        "avg_quotes_per_item": avg_quotes_per_item,
        "avg_quotes_per_found": avg_quotes_per_found,
        "inn_resolved_count": inn_resolved_count,
        "inn_resolution_pct": round((inn_resolved_count / max(1, quotes_count)) * 100, 1),
        "official_opf_pct": round((official_opf_count / max(1, quotes_count)) * 100, 1),
        "unit_conversions_count": unit_converted_count,
        "cookie_domains_activity": cookie_domain_quotes,
        "unique_domains_count": len(domain_counts),
        "top_10_domains": sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        "excel_verification": {
            "sheet1_title": ws1.title,
            "row_height": row_height_sample,
            "formulas_min_count": formulas_min_count,
            "formulas_avg_count": formulas_avg_count,
        },
        "output_excel_path": output_path,
    }

    metrics_path = "/tmp/test_100_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    logger.info("=" * 80)
    logger.info("🏁 100-POSITION TEST COMPLETED IN %.1f MIN (%.1fs)", elapsed_sec / 60, elapsed_sec)
    logger.info("Found: %d / %d (%.1f%%)", found_items, total_items, metrics["coverage_pct"])
    logger.info("Quotes collected: %d (avg %.2f per found item)", quotes_count, avg_quotes_per_found)
    logger.info("INNs verified via DaData: %d (%.1f%%)", inn_resolved_count, metrics["inn_resolution_pct"])
    logger.info("Unit conversions applied: %d", unit_converted_count)
    logger.info("Saved metrics to %s", metrics_path)
    logger.info("Saved final report to %s", output_path)
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
