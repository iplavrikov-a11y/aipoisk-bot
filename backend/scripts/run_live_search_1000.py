import asyncio
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("outreach_runner")

from app.db import SessionLocal
from app.models import SystemSettings
from app.outreach_models import OutreachLead
from app.outreach_search import (
    generate_search_queries_matrix,
    fetch_yandex_search_pages,
    fetch_ddgs_search_pages,
    crawl_site_for_contact,
    base_domain,
    BLOCKED_DOMAINS,
    ACTIVE_SEARCH_TASKS,
    run_outreach_search_task,
)
import httpx

async def run_search_benchmark():
    prompt = "сопровождение тендеров, компании занимающиеся участием в тендерах и исполнением госконтрактов, тендерные отделы"
    target_count = 1000
    task_id = "task-benchmark-1000"

    print("=" * 70, flush=True)
    print("ЗАПУСК ТЕСТА СБОРА КОНТАКТОВ (Outreach Lead Generation)", flush=True)
    print(f"Промпт: {prompt}", flush=True)
    print(f"Целевое количество: {target_count}", flush=True)
    print("=" * 70, flush=True)

    db = SessionLocal()
    sys_settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not sys_settings:
        sys_settings = SystemSettings(id=1)
    
    initial_leads = db.query(OutreachLead).count()
    print(f"База до запуска: {initial_leads} контактов", flush=True)
    db.close()

    t_start = time.time()

    # Step 1: AI Query Matrix Generation
    print("\n[ШАГ 1] Генерация матрицы поисковых запросов через LLM...", flush=True)
    queries = await generate_search_queries_matrix(prompt, count=target_count)
    print(f"-> Сгенерировано {len(queries)} целевых запросов:", flush=True)
    for idx, q in enumerate(queries[:12], 1):
        print(f"   {idx}. {q}", flush=True)
    if len(queries) > 12:
        print(f"   ... и еще {len(queries) - 12} запросов", flush=True)

    # Step 2: Search Engine Crawling (Yandex API + Fallback)
    print("\n[ШАГ 2] Поиск сайтов в поисковых системах...", flush=True)
    folder_id = sys_settings.yandex_search_folder_id
    api_key = sys_settings.yandex_search_api_key
    print(f"-> Yandex API настроен: folder_id={'ДА' if folder_id else 'НЕТ'}, api_key={'ДА' if api_key else 'НЕТ'}", flush=True)

    seen_domains = set()
    candidate_urls = []

    sem = asyncio.Semaphore(4)

    async def _fetch_q_urls(q_text: str) -> list[str]:
        async with sem:
            u_res = []
            if folder_id and api_key:
                try:
                    u_res = await fetch_yandex_search_pages(q_text, folder_id, api_key, max_pages=6, groups_on_page=20)
                except Exception as e:
                    logger.debug(f"Yandex query error '{q_text}': {e}")
            if not u_res:
                try:
                    u_res = await fetch_ddgs_search_pages(q_text, max_results=35)
                except Exception as e:
                    logger.debug(f"DDGS error '{q_text}': {e}")
            return u_res

    q_chunk_size = 6
    for q_i in range(0, len(queries), q_chunk_size):
        chunk = queries[q_i : q_i + q_chunk_size]
        results_chunk = await asyncio.gather(*[_fetch_q_urls(q) for q in chunk], return_exceptions=True)
        for res_urls in results_chunk:
            if isinstance(res_urls, list):
                for u in res_urls:
                    dom = base_domain(u)
                    if dom and dom not in seen_domains and dom not in BLOCKED_DOMAINS:
                        seen_domains.add(dom)
                        candidate_urls.append(u)

        print(f"   Обработано запросов: {min(q_i + q_chunk_size, len(queries))}/{len(queries)} | Найдено уникальных сайтов: {len(candidate_urls)}", flush=True)
        if len(candidate_urls) >= target_count * 2.2:
            break

    print(f"-> Всего найдено уникальных релевантных сайтов компаний: {len(candidate_urls)}", flush=True)

    # Step 3: Deep Contact Crawling & Extraction
    print("\n[ШАГ 3] Глубокий парсинг сайтов, извлечение контактов (Email, Телефон, ИНН, Название) и MX-проверка...", flush=True)

    with SessionLocal() as db:
        existing_emails = {r[0].lower() for r in db.query(OutreachLead.email).all()}

    collected_count = 0
    batch_size = 20
    scanned_sites = 0
    errors_count = 0

    async with httpx.AsyncClient(timeout=10.0, verify=False, limits=httpx.Limits(max_connections=35, max_keepalive_connections=20)) as client:
        for i in range(0, len(candidate_urls), batch_size):
            batch = candidate_urls[i : i + batch_size]
            tasks = [crawl_site_for_contact(u, client) for u in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            scanned_sites += len(batch)
            new_batch_leads = []

            for res in results:
                if isinstance(res, Exception):
                    errors_count += 1
                    continue
                if isinstance(res, dict) and res.get("email"):
                    em = res["email"].lower()
                    if em not in existing_emails:
                        existing_emails.add(em)
                        lead = OutreachLead(
                            email=em,
                            company_name=res.get("company_name", "") or res.get("website", ""),
                            phone=res.get("phone", ""),
                            website=res.get("website", ""),
                            inn=res.get("inn", ""),
                            city="РФ",
                            category=prompt[:80],
                            source="search",
                            status="new",
                            mx_valid=bool(res.get("mx_valid", True)),
                        )
                        new_batch_leads.append(lead)

            if new_batch_leads:
                with SessionLocal() as db:
                    for l in new_batch_leads:
                        db.add(l)
                    db.commit()
                collected_count += len(new_batch_leads)

            if scanned_sites % 60 == 0 or collected_count >= target_count or scanned_sites >= len(candidate_urls):
                print(f"   Просканировано сайтов: {scanned_sites}/{len(candidate_urls)} | Собрано валидных контактов: {collected_count}", flush=True)

            if collected_count >= target_count:
                break

    t_end = time.time()
    duration = t_end - t_start

    print("\n" + "=" * 70, flush=True)
    print("РЕЗУЛЬТАТЫ СБОРА И ТЕСТИРОВАНИЯ", flush=True)
    print("=" * 70, flush=True)
    print(f"Время работы: {duration:.1f} сек ({duration/60:.1f} мин)", flush=True)
    print(f"Найдено сайтов компаний: {len(candidate_urls)}", flush=True)
    print(f"Просканировано сайтов: {scanned_sites}", flush=True)
    print(f"Собрано и сохранено новых лидов: {collected_count}", flush=True)
    print(f"Ошибок парсинга/таймаутов сайтов: {errors_count}", flush=True)
    
    # Check sample leads from DB
    with SessionLocal() as db:
        sample_leads = db.query(OutreachLead).filter(OutreachLead.category.like("%сопровождение%")).order_by(OutreachLead.id.desc()).limit(10).all()
        print("\nПримеры извлеченных компаний и контактов:", flush=True)
        for idx, l in enumerate(sample_leads, 1):
            print(f"{idx}. {l.company_name[:35]:35} | {l.email:30} | {l.phone:18} | {l.website:25} | MX={l.mx_valid}", flush=True)

if __name__ == "__main__":
    asyncio.run(run_search_benchmark())
