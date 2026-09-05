import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import SystemSettings
from app.outreach_models import OutreachLead, OutreachSearchTask
from app.outreach_search import run_outreach_search_task
from app.supplier_search import discover_suppliers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("compare_search_engines")


async def run_comparison(test_name: str, query_context: str, target: int = 3):
    print(f"\n================================================================================")
    print(f"🔬 ЗАПУСК СРАВНИТЕЛЬНОГО ТЕСТА: {test_name}")
    print(f"📋 Предмет поиска: {query_context}")
    print(f"🎯 Целевое количество: {target}")
    print(f"================================================================================\n")

    with SessionLocal() as db:
        settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()

    # 1. TenderLex Client Engine
    print("▶️ [1/2] Запуск клиентского движка TenderLex...")
    t0_tl = time.time()

    async def tl_progress(pct: int, msg: str):
        print(f"   [TenderLex {pct}%] {msg}")

    try:
        tl_suppliers, tl_meta = await discover_suppliers(
            settings=settings,
            context=query_context,
            target=target,
            progress_callback=tl_progress,
        )
    except Exception as e:
        print(f"❌ Ошибка TenderLex: {e}")
        tl_suppliers, tl_meta = [], {"error": str(e)}

    tl_elapsed = round(time.time() - t0_tl, 2)
    print(f"✅ TenderLex завершил поиск за {tl_elapsed} сек. Найдено поставщиков: {len(tl_suppliers)}")

    # 2. Outreach Search Engine
    print("\n▶️ [2/2] Запуск модернизированного движка Outreach...")
    t0_out = time.time()
    out_task_id = f"test_cmp_{uuid4().hex[:8]}"

    try:
        await run_outreach_search_task(
            task_id=out_task_id,
            name=f"CmpTest: {test_name}",
            prompt=query_context,
            target_count=target,
            session_factory=SessionLocal,
            settings=settings,
        )
    except Exception as e:
        print(f"❌ Ошибка Outreach: {e}")

    out_elapsed = round(time.time() - t0_out, 2)

    with SessionLocal() as db:
        out_task = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == out_task_id).first()
        out_leads = db.query(OutreachLead).filter(OutreachLead.task_id == out_task_id).all()
        out_leads_data = [
            {
                "company_name": l.company_name,
                "website": l.website,
                "email": l.email,
                "phone": l.phone,
                "inn": l.inn,
                "activity_profile": l.activity_profile,
                "relevance_score": l.relevance_score,
                "mx_valid": l.mx_valid,
            }
            for l in out_leads
        ]

    print(f"✅ Outreach завершил поиск за {out_elapsed} сек. Собрано лидов: {len(out_leads_data)}")

    # 3. Side-by-side analysis
    print("\n" + "=" * 80)
    print(f"📊 СРАВНИТЕЛЬНЫЙ АНАЛИЗ ДЛЯ '{test_name}'")
    print("=" * 80)

    print("\n--- [TENDERLEX ПОСТАВЩИКИ] ---")
    for i, s in enumerate(tl_suppliers[:target], 1):
        site = s.get("site") or s.get("url") or ""
        name = s.get("name") or s.get("company_name") or ""
        inn = s.get("inn") or "н/д"
        email = s.get("email") or s.get("emails") or ""
        phone = s.get("phone") or s.get("phones") or ""
        comment = s.get("comments") or s.get("reason") or ""
        print(f"  {i}. {name} | ИНН: {inn} | Сайт: {site}")
        print(f"     Email: {email} | Тел: {phone}")
        print(f"     Вердикт ИИ: {comment[:120]}...")

    print("\n--- [OUTREACH ПОСТАВЩИКИ] ---")
    for i, s in enumerate(out_leads_data[:target], 1):
        site = s.get("website") or ""
        name = s.get("company_name") or ""
        inn = s.get("inn") or "н/д"
        email = s.get("email") or ""
        phone = s.get("phone") or ""
        prof = s.get("activity_profile") or ""
        score = s.get("relevance_score") or 0
        mx = "✓ MX OK" if s.get("mx_valid") else "✗ No MX"
        print(f"  {i}. {name} | ИНН: {inn} | Сайт: {site}")
        print(f"     Email: {email} ({mx}) | Тел: {phone}")
        print(f"     Балл релевантности: {score}/100 | Профиль: {prof[:120]}...")

    print("\n--- [СВОДНЫЕ МЕТРИКИ] ---")
    print(f"  Время выполнения:        TenderLex = {tl_elapsed}s | Outreach = {out_elapsed}s")
    print(f"  Количество кандидатов:   TenderLex = {len(tl_suppliers)} | Outreach = {len(out_leads_data)}")
    
    tl_inns = sum(1 for s in tl_suppliers if s.get("inn"))
    out_inns = sum(1 for s in out_leads_data if s.get("inn"))
    print(f"  Найдено ИНН:             TenderLex = {tl_inns}/{len(tl_suppliers)} | Outreach = {out_inns}/{len(out_leads_data)}")
    
    tl_phones = sum(1 for s in tl_suppliers if s.get("phone") or s.get("phones"))
    out_phones = sum(1 for s in out_leads_data if s.get("phone"))
    print(f"  Найдено телефонов:       TenderLex = {tl_phones}/{len(tl_suppliers)} | Outreach = {out_phones}/{len(out_leads_data)}")
    
    tl_emails = sum(1 for s in tl_suppliers if s.get("email") or s.get("emails"))
    out_emails = sum(1 for s in out_leads_data if s.get("email"))
    print(f"  Найдено Email:           TenderLex = {tl_emails}/{len(tl_suppliers)} | Outreach = {out_emails}/{len(out_leads_data)}")


async def main():
    await run_comparison(
        test_name="Трубопроводная арматура и задвижки",
        query_context="Трубопроводная арматура: задвижки стальные клиновые 30с41нж Ду50-Ду200, фланцы стальные ГОСТ 12820-80, отводы, дисковые затворы от производителей",
        target=3,
    )


if __name__ == "__main__":
    asyncio.run(main())
