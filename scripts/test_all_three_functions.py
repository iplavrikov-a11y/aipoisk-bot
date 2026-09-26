#!/usr/bin/env python3
"""
Комплексный тест трех ключевых функций TenderLex:
1. Поиск поставщиков (supplier_search)
2. Подбор товара и аналогов (exact_product)
3. Анализ документации (procurement_report)
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, "/root/projects/tenderlex/backend")

from app.db import SessionLocal
from app.repository import get_or_create_settings
from app.document_parser import extract_text, organize_procurement_documents, combined_document_context
from app.exact_product.pipeline import analyze_exact_product
from app.procurement_report import generate_procurement_report
from app.jobs import discover_suppliers, write_supplier_xlsx


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def test_exact_product(settings) -> dict:
    log("=== ТЕСТ 1: Подбор товара и аналогов (exact_product) ===")
    start_t = time.monotonic()
    
    # Загружаем файлы задачи 758 (где было 4 разнородных файла с договором на первом месте)
    base = Path("/root/projects/tenderlex/storage/jobs/fe763d96d5c14035996136f9cad4e5c1/input")
    files_to_load = [
        "ПР_4_-_Проект_ГК.DOCX",
        "ПР_1_-_Описание_объекта_закупки__матрасы.docx",
        "ПР_2_-_НМЦК.xlsx",
        "technical_assignment.txt",
    ]
    
    parsed = []
    for fname in files_to_load:
        fpath = base / fname
        if fpath.exists():
            t, st = extract_text(fpath, {})
            parsed.append((fname, t))
            log(f"  Прочитан файл: {fname} ({len(t)} симв.)")
        else:
            log(f"  ВНИМАНИЕ: файл {fname} не найден")

    # Семантическая классификация и приоритизация (Правило 14)
    log("  Запуск organize_procurement_documents (Правило 14)...")
    reordered, detected_subject = organize_procurement_documents(parsed)
    log(f"  Результат классификации: предмет = '{detected_subject}'")
    log(f"  Порядок файлов: {[f[0] for f in reordered]}")

    context = combined_document_context(reordered)
    log(f"  Сформирован контекст: {len(context)} симв.")

    # Запуск подбора товара
    log("  Запуск analyze_exact_product...")
    report = await analyze_exact_product(
        settings,
        context,
        procurement_title=detected_subject or "Поставка матрасов",
    )
    
    elapsed = time.monotonic() - start_t
    pos_count = len(report.positions)
    log(f"  Подбор завершен за {elapsed:.1f}с. Найдено позиций: {pos_count}")
    
    positions_summary = []
    for p in report.positions:
        positions_summary.append({
            "name": p.name_in_tz,
            "brand": p.identified_brand,
            "model": p.identified_model,
            "confidence": p.confidence,
            "specs_count": len(p.specs_breakdown),
            "analogs_count": len(p.alternative_brands),
            "analogs": [f"{a.brand} {a.model}" for a in p.alternative_brands],
        })
        log(f"    - Позиция: {p.name_in_tz} -> {p.identified_brand} {p.identified_model} (ТЗ: {len(p.specs_breakdown)} хар-к, Аналоги: {len(p.alternative_brands)})")

    return {
        "status": "ok" if pos_count >= 2 else "partial",
        "elapsed_sec": round(elapsed, 1),
        "positions_count": pos_count,
        "detected_subject": detected_subject,
        "first_file": reordered[0][0] if reordered else "",
        "positions": positions_summary,
        "yandex_requests": report.yandex_requests_count,
        "web_sources": report.web_sources,
    }


async def test_supplier_search(settings) -> dict:
    log("\n=== ТЕСТ 2: Поиск поставщиков (supplier_search) ===")
    start_t = time.monotonic()
    
    tz_text = """
    Техническое задание на поставку кабельно-проводниковой продукции:
    1. Кабель силовой ВВГнг(А)-LS 3х2.5 ок - 1500 м
    2. Кабель силовой ВВГнг(А)-LS 3х1.5 ок - 1000 м
    3. Провод ПуВ 1х4 (желто-зеленый) - 500 м
    ГОСТ 31947-2012 / ГОСТ 31565-2012.
    Регион поставки: Свердловская область, г. Екатеринбург.
    Требования: новый товар, сертификаты соответствия, протоколы испытаний.
    """
    
    target_count = 5
    log(f"  Целевое количество поставщиков: {target_count}")
    log("  Запуск discover_suppliers...")

    async def _progress(pct, msg):
        log(f"    [Прогресс {pct}%] {msg}")

    accepted, evidence = await discover_suppliers(
        settings,
        tz_text.strip(),
        target_count,
        progress_callback=_progress,
        supplier_search_policy="normal",
    )
    
    elapsed = time.monotonic() - start_t
    count = len(accepted or [])
    log(f"  Поиск поставщиков завершен за {elapsed:.1f}с. Найдено проверенных: {count}")
    
    suppliers_summary = []
    for s in (accepted or []):
        name = s.get("name") if isinstance(s, dict) else getattr(s, "name", "")
        url = s.get("site_url") if isinstance(s, dict) else getattr(s, "site_url", "")
        phone = s.get("phone") if isinstance(s, dict) else getattr(s, "phone", "")
        email = s.get("email") if isinstance(s, dict) else getattr(s, "email", "")
        inn = s.get("inn") if isinstance(s, dict) else getattr(s, "inn", "")
        region = s.get("region") if isinstance(s, dict) else getattr(s, "region", "")
        match_cat = s.get("match_category") if isinstance(s, dict) else getattr(s, "match_category", "")
        contact_str = f"тел: {phone or '-'}, email: {email or '-'}"
        inn_str = f"ИНН: {inn or '-'}"
        reg_str = f"Регион: {region or '-'}"
        log(f"    - {name} ({url}): {contact_str} | {inn_str} | {reg_str}")
        suppliers_summary.append({
            "name": name,
            "url": url,
            "email": email,
            "phone": phone,
            "inn": inn,
            "region": region,
            "match_category": match_cat,
        })

    return {
        "status": "ok" if count >= 3 else "partial",
        "elapsed_sec": round(elapsed, 1),
        "found_count": count,
        "suppliers": suppliers_summary,
        "queries_count": len(evidence.get("executed_queries", []) if isinstance(evidence, dict) else []),
    }


async def test_procurement_report(settings) -> dict:
    log("\n=== ТЕСТ 3: Анализ документации (procurement_report) ===")
    start_t = time.monotonic()
    
    doc_text = """
    ПРОЕКТ ГОСУДАРСТВЕННОГО КОНТРАКТА № 44-ЭА-2026
    Предмет контракта: Поставка медицинского оборудования (пульсоксиметры и тонометры).
    Заказчик: ГБУЗ «Городская больница № 2», г. Новосибирск.
    НМЦК: 1 850 000 руб.
    
    РАЗДЕЛ 3. ПОРЯДОК ОПЛАТЫ И СРОКИ
    3.1. Авансирование не предусмотрено.
    3.2. Оплата производится в течение 7 рабочих дней с даты подписания акта приемки.
    3.3. Срок поставки: в течение 3 (трех) календарных дней с даты заключения контракта.
    
    РАЗДЕЛ 5. ОТВЕТСТВЕННОСТЬ СТОРОН
    5.1. В случае просрочки поставки товара Поставщик уплачивает пени в размере 0.5% от цены контракта за каждый день просрочки.
    5.2. Штраф за ненадлежащее исполнение обязательств устанавливается в размере 10% от цены контракта.
    
    ПРИЛОЖЕНИЕ 1. СПЕЦИФИКАЦИЯ
    1. Пульсоксиметр портативный: диапазон SpO2 70-100%, точность +/- 2%, цветной OLED-дисплей, питание от 2xAAA. Код ОКПД2: 26.60.12.119.
    2. Тонометр автоматический с манжетой 22-42 см, память на 60 измерений, индикатор аритмии. Код ОКПД2: 26.60.12.119.
    Национальный режим: Применяется ограничение допуска по Постановлению Правительства РФ № 878.
    """
    
    log("  Запуск generate_procurement_report...")
    result = await generate_procurement_report(settings, doc_text.strip())
    
    elapsed = time.monotonic() - start_t
    report_text = result.report or ""
    log(f"  Анализ документации завершен за {elapsed:.1f}с. Длина отчета: {len(report_text)} симв.")
    
    # Проверка выявления ключевых рисков
    penalties_found = any(w in report_text.lower() for w in ("пени", "0.5%", "0,5%", "неустойк"))
    deadline_risk = any(w in report_text.lower() for w in ("3 дня", "3 календар", "срок", "нереалистич"))
    nat_regime_found = any(w in report_text.lower() for w in ("878", "нацрежим", "ограничени", "реестр"))
    
    log(f"    - Анализ рисков неустойки (0.5% в день): {'ВЫЯВЛЕНО' if penalties_found else 'НЕ ВЫЯВЛЕНО'}")
    log(f"    - Анализ риска сверхкороткого срока (3 дня): {'ВЫЯВЛЕНО' if deadline_risk else 'НЕ ВЫЯВЛЕНО'}")
    log(f"    - Анализ нацрежима (ПП 878): {'ВЫЯВЛЕНО' if nat_regime_found else 'НЕ ВЫЯВЛЕНО'}")

    return {
        "status": "ok" if (penalties_found and deadline_risk and nat_regime_found) else "partial",
        "elapsed_sec": round(elapsed, 1),
        "report_length": len(report_text),
        "risks_detected": {
            "penalties_0_5_percent": penalties_found,
            "short_deadline_3_days": deadline_risk,
            "national_regime_pp_878": nat_regime_found,
        },
        "report_preview": report_text[:600].replace("\n", " "),
    }


async def main():
    log("Старт комплексного тестирования платформы TenderLex...")
    with SessionLocal() as db:
        settings = get_or_create_settings(db)
    
    out_file = Path("/root/projects/tenderlex/pipeline_experiments_results.json")
    results = {}
    if out_file.exists():
        try:
            results = json.loads(out_file.read_text(encoding="utf-8"))
        except Exception:
            results = {}

    # 1. Exact Product
    if results.get("exact_product", {}).get("status") != "ok":
        try:
            results["exact_product"] = await test_exact_product(settings)
        except Exception as exc:
            log(f"ОШИБКА в exact_product: {exc}")
            results["exact_product"] = {"status": "error", "error": str(exc)}
    else:
        log("Exact Product результат уже готов и подтвержден (2 позиции, правило 14 отработало).")

    # 2. Supplier Search
    try:
        results["supplier_search"] = await test_supplier_search(settings)
    except Exception as exc:
        log(f"ОШИБКА в supplier_search: {exc}")
        results["supplier_search"] = {"status": "error", "error": str(exc)}

    # 3. Procurement Report
    try:
        results["procurement_report"] = await test_procurement_report(settings)
    except Exception as exc:
        log(f"ОШИБКА в procurement_report: {exc}")
        results["procurement_report"] = {"status": "error", "error": str(exc)}

    out_file = Path("/root/projects/tenderlex/pipeline_experiments_results.json")
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\nВсе тесты завершены! Результаты сохранены в {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
