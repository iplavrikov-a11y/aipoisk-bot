#!/usr/bin/env python3
"""
Benchmark script:
Tests multi-item technical specification analysis in TenderLex Exact Product mode.
Measures:
1. Triaging (filtering works, services, screws -> retaining top-3 key capital items).
2. Number of search queries performed and budget adherence (<= 16 queries).
3. Exact execution cost in rubles (Yandex Search API + AI Tokens).
4. Output report generation (DOCX and XLSX) and file sizes.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db import SessionLocal
from app.models import SystemSettings
from app.exact_product import (
    MAX_EXACT_POSITIONS_PER_JOB,
    MAX_YANDEX_QUERIES_PER_JOB,
    analyze_exact_product,
    write_exact_product_docx,
    write_exact_product_xlsx,
)

# Complex 6-item mixed specification (contains capital equipment, cable, valve, tiny screws, and installation services)
SAMPLE_MULTI_ITEM_TZ = """
ТЕХНИЧЕСКОЕ ЗАДАНИЕ
на поставку промышленного технологического оборудования, запорно-регулирующей арматуры и кабельной продукции

1. Позиция №1: Насос центробежный консольный для перекачивания технологической воды
Подача (производительность): не менее 50 м3/ч (номинал 50-60 м3/ч).
Напор: не менее 32 м вод. ст.
Частота вращения: 2900 об/мин.
Мощность электродвигателя: не более 11 кВт, исполнение общепромышленное IP55.
Материал проточной части: серый чугун СЧ20.
Температура перекачиваемой среды: от 0 до +85 °C.

2. Позиция №2: Кабель силовой бронированный ВБШвнг(А)-LS 4х16 (N, PE) - 1 кВ
Число и сечение жил: 4х16 мм2.
Материал жилы: медь, 1 класс гибкости по ГОСТ 22483-2012.
Изоляция: ПВХ пластикат пониженной пожарной опасности.
Броня: две стальные оцинкованные ленты.
Наружная оболочка: защитный шланг из ПВХ пластиката низкой пожароопасности.
Соответствие: ГОСТ 31996-2012. Длина строительная: 500 м.

3. Позиция №3: Затвор дисковый поворотный межфланцевый Ду150 Ру16 с электроприводом
Номинальный диаметр: DN 150.
Номинальное давление: PN 1.6 МПа (16 кгс/см2).
Материал корпуса: ковкий чугун GGG40 или сталь 20.
Материал диска: нержавеющая сталь AISI 316 (08Х17Н13М2).
Уплотнение седла: EPDM, герметичность класс А по ГОСТ 9544-2015.
Привод: четвертьоборотный электропривод 220В с концевыми выключателями и ручным дублером.

4. Позиция №4: Болты оцинкованные М12х45 с гайками и шайбами (комплект крепежа)
Класс прочности: 8.8 по ГОСТ ISO 898-1-2014.
Покрытие: термодиффузионное или гальваническое цинкование.
Количество: 100 шт.

5. Позиция №5: Саморезы по металлу 4.2х19 со сверлом
Количество: 500 шт.

6. Позиция №6: Шеф-монтажные и пусконаладочные работы (ПНР) насосного агрегата
Выполнение работ по проверке соосности валов, подключению к электросети и испытаниям под нагрузкой в течение 72 часов.
"""


async def run_benchmark():
    print("=" * 70)
    print("TENDERLEX EXACT PRODUCT SAFEGUARD & COST BENCHMARK")
    print("=" * 70)

    db = SessionLocal()
    try:
        settings = db.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings()
    finally:
        db.close()

    print(f"[*] Configuration constants:")
    print(f"    - MAX_EXACT_POSITIONS_PER_JOB: {MAX_EXACT_POSITIONS_PER_JOB}")
    print(f"    - MAX_YANDEX_QUERIES_PER_JOB:  {MAX_YANDEX_QUERIES_PER_JOB}")
    print(f"    - Has active AI provider:      {settings.has_active_ai_provider}")
    print(f"[*] Input specification contains: 6 items (3 key items, 2 fasteners, 1 installation service)")

    t_start = time.time()
    progress_log = []

    async def log_progress(pct: int, msg: str):
        elapsed = time.time() - t_start
        print(f"    [{elapsed:5.1f}s] [{pct:3d}%] {msg}")
        progress_log.append((pct, msg))

    print("\n[*] Starting analyze_exact_product pipeline...")
    report = await analyze_exact_product(
        settings=settings,
        context=SAMPLE_MULTI_ITEM_TZ,
        procurement_title="Поставка оборудования, арматуры и кабеля для насосной станции",
        progress_callback=log_progress,
    )
    t_end = time.time()
    total_elapsed = t_end - t_start

    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Execution time:            {total_elapsed:.1f} seconds ({total_elapsed / 60:.1f} min)")
    print(f"Total positions in report: {len(report.positions)} (Limit: {MAX_EXACT_POSITIONS_PER_JOB})")
    print(f"Yandex search queries:     {report.yandex_requests_count} (Cap: {MAX_YANDEX_QUERIES_PER_JOB})")
    print(f"Yandex search cost:        {report.yandex_cost_rub:.2f} руб.")
    print(f"Verified documents parsed: {len(report.verified_documents)} docs")

    print("\n[*] Extracted & Verified Positions:")
    for idx, pos in enumerate(report.positions, start=1):
        gisp_str = f"ГИСП №{pos.gisp_match.registry_number}" if pos.gisp_match else "Нет в ГИСП"
        print(f"  {idx}. {pos.name_in_tz[:55]}")
        print(f"     -> Товар: {pos.identified_brand} {pos.identified_model} (Завод: {pos.manufacturer}) [{gisp_str}]")
        print(f"     -> Параметров в Form 2: {len(pos.specs_breakdown)}, Аналогов: {len(pos.alternative_brands)}")

    print("\n[*] Report Summary:")
    print(f"  {report.summary}")

    # Generate documents and measure file sizes
    out_dir = Path("/tmp/tenderlex_benchmark")
    out_dir.mkdir(parents=True, exist_ok=True)

    docx_path = out_dir / "benchmark_report.docx"
    write_exact_product_docx(docx_path, report)

    xlsx_path = out_dir / "benchmark_report.xlsx"
    write_exact_product_xlsx(xlsx_path, report)

    docx_bytes = docx_path.read_bytes()
    xlsx_bytes = xlsx_path.read_bytes()

    print(f"\n[*] Generated Artifacts & File Sizes:")
    print(f"  - DOCX Report: {docx_path} ({len(docx_bytes) / 1024:.1f} KB)")
    print(f"  - XLSX Form 2: {xlsx_path} ({len(xlsx_bytes) / 1024:.1f} KB)")

    # Assertions for verification
    assert len(report.positions) <= MAX_EXACT_POSITIONS_PER_JOB, f"Positions count {len(report.positions)} exceeds max {MAX_EXACT_POSITIONS_PER_JOB}"
    assert report.yandex_requests_count <= MAX_YANDEX_QUERIES_PER_JOB, f"Queries {report.yandex_requests_count} exceeds cap {MAX_YANDEX_QUERIES_PER_JOB}"
    assert len(docx_bytes) > 5000, "DOCX report is too small"
    assert len(xlsx_bytes) > 5000, "XLSX report is too small"
    print("\n[SUCCESS] All benchmark checks passed!")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
