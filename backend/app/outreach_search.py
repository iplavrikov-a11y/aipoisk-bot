from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import socket
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from .ai import call_llm
from .config import config
from .models import SystemSettings
from .outreach_models import OutreachLead, OutreachSearchTask, now_utc
from .supplier_search import (
    BLOCKED_DOMAINS,
    base_domain,
    contact_page_url,
    email_has_valid_mx,
    extract_company_name,
    normalize_url,
    prioritize_emails,
    _normalize_ru_phone,
    _verified_email,
    _verified_phone,
)

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.I)
PHONE_RE = re.compile(r"(?:\+7|8)[\s\-(]?\d{3}[\s\-)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
INN_RE = re.compile(r"\b\d{10}\b|\b\d{12}\b")

# Generic blocked portal domains (aggregators, job boards, message boards, social media)
EXTENDED_BLOCKED_DOMAINS = BLOCKED_DOMAINS | {
    "klerk.ru",
    "leboard.ru",
    "profi.ru",
    "kwork.ru",
    "youla.ru",
    "hh.ru",
    "superjob.ru",
    "zakon.guru",
    "garant.ru",
    "audit-it.ru",
    "vc.ru",
    "journal.tinkoff.ru",
}


def _clean_email(email_str: str) -> str:
    email_str = email_str.strip().lower().rstrip(".,;:/)")
    if not (4 <= len(email_str) <= 100):
        return ""
    if "@" not in email_str or "." not in email_str.split("@")[-1]:
        return ""
    return email_str


# Active search background jobs {task_id: {"status": str, "target": int, "progress": int, "message": str, "cancel": bool}}
ACTIVE_SEARCH_TASKS: dict[str, dict[str, Any]] = {}


async def generate_search_queries_matrix(prompt: str, count: int = 40) -> tuple[list[str], float]:
    """Generates an extensive matrix of search queries targeting companies for any user-specified prompt."""
    target_q_count = min(75, max(30, count // 15))
    system_prompt = (
        "Ты эксперт по B2B поиску и лидогенерации организаций, компаний и коммерческих сайтов в интернете. "
        "Твоя задача — составить глубокую и разнообразную матрицу поисковых запросов для Яндекса и Google, "
        "которая найдет официальные сайты целевых компаний и организаций, точно соответствующих заданному описанию пользователя. "
        "Правила формирования запросов: "
        "1) Региональные привязки (крупные города РФ, регионы, федеральные округа, общероссийские формулировки). "
        "2) Профессиональные термины, формулировки коммерческих предложений, ключевые слова из контактов, каталогов, услуг и специфики ниши. "
        "3) Точное следование всем исключениям и критериям, указанным пользователем в его описании. "
        f"Сгенерируй от {target_q_count} разнообразных целевых поисковых запросов. "
        "Верни ТОЛЬКО валидный JSON массив строк, например: [\"запрос 1\", \"запрос 2\"]."
    )
    user_prompt = f"Целевой сегмент и критерии:\n{prompt}\n\nКоличество контактов: {count}. Сгенерируй {target_q_count} поисковых запросов в виде JSON массива:"

    estimated_llm_cost = 0.40  # ~0.40 RUB for prompt generation

    try:
        from .db import SessionLocal
        db = SessionLocal()
        sys_settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        db.close()
        if sys_settings:
            resp = await call_llm(
                sys_settings,
                user_prompt,
                system_prompt=system_prompt,
                tier="light",
                json_mode=True,
            )
            text = resp.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            data = json.loads(text)
            if isinstance(data, list):
                queries = [str(q).strip() for q in data if str(q).strip()]
                if queries:
                    return queries[:80], estimated_llm_cost
    except Exception as e:
        logger.warning(f"Error generating search queries with AI: {e}")

    # Fallback heuristic queries
    base = prompt.strip()
    words = [w for w in re.split(r"[,;\s]+", base) if len(w) > 2]
    keywords = " ".join(words[:4]) if words else base
    regions = ["Москва", "СПб", "Екатеринбург", "Новосибирск", "Казань", "Нижний Новгород", "Самара", "Краснодар", "Россия", "ЦФО", "Урал", "Поволжье"]
    types = ["поставки по 44-фз", "комплексное снабжение госконтракты", "торговый дом дилер", "поставщик оборудования торги", "исполнение контрактов опт", "официальный поставщик"]

    fallback = []
    for reg in regions:
        for t in types:
            fallback.append(f"{keywords} {t} {reg}")
    return fallback[:75], 0.0


async def fetch_yandex_search_pages(
    query: str,
    folder_id: str,
    api_key: str,
    max_pages: int = 8,
    groups_on_page: int = 20,
) -> tuple[list[str], int]:
    """Deep Yandex Search v2 with tracking of executed API requests."""
    if not folder_id or not api_key:
        return [], 0
    
    headers = {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}
    found_urls: list[str] = []
    requests_count = 0
    
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        for page in range(max_pages):
            body = {
                "query": {"searchType": "SEARCH_TYPE_RU", "queryText": query, "page": str(page)},
                "folderId": folder_id,
                "responseFormat": "FORMAT_XML",
                "groupBy": {"groupsOnPage": groups_on_page, "docsInGroup": 1},
            }
            try:
                res = await client.post("https://searchapi.api.cloud.yandex.net/v2/web/searchAsync", headers=headers, json=body)
                requests_count += 1
                if res.status_code != 200:
                    break
                op_id = str(res.json().get("id") or "")
                if not op_id:
                    break

                # Poll operation
                raw_xml = ""
                for _ in range(12):
                    await asyncio.sleep(1.2)
                    op_res = await client.get(f"https://operation.api.cloud.yandex.net/operations/{op_id}", headers=headers)
                    if op_res.status_code == 200:
                        op_data = op_res.json()
                        if op_data.get("done"):
                            raw_xml = str(op_data.get("response", {}).get("rawData") or "")
                            break

                if not raw_xml:
                    break

                # Parse XML
                if not raw_xml.startswith("<"):
                    try:
                        raw_xml = base64.b64decode(raw_xml).decode("utf-8")
                    except Exception:
                        pass
                
                root = ET.fromstring(raw_xml)
                docs = root.findall(".//doc")
                if not docs:
                    break

                for doc in docs:
                    u_elem = doc.find("url")
                    if u_elem is not None and u_elem.text:
                        u = normalize_url(u_elem.text)
                        dom = base_domain(u)
                        if dom and dom not in EXTENDED_BLOCKED_DOMAINS:
                            found_urls.append(u)
            except Exception as e:
                logger.debug(f"Yandex page {page} error for query '{query}': {e}")
                break

    return found_urls, requests_count


async def fetch_ddgs_search_pages(query: str, max_results: int = 40) -> list[str]:
    """Free fallback search via DuckDuckGo."""
    urls = []
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results, region="ru-ru")
        for r in results:
            if isinstance(r, dict) and "href" in r:
                u = normalize_url(r["href"])
                dom = base_domain(u)
                if dom and dom not in EXTENDED_BLOCKED_DOMAINS:
                    urls.append(u)
    except Exception as e:
        logger.debug(f"DDGS search error: {e}")
    return urls


async def crawl_site_for_contact(origin_url: str, client: httpx.AsyncClient | None = None) -> dict[str, Any] | None:
    """Accurate contact extraction with strict ICP relevance filtering."""
    if client is None:
        async with httpx.AsyncClient(timeout=12.0, verify=False) as local_client:
            return await crawl_site_for_contact(origin_url, client=local_client)

    parsed = urlparse(origin_url)
    root_dom = base_domain(origin_url)
    if not root_dom or root_dom in EXTENDED_BLOCKED_DOMAINS:
        return None

    scheme = parsed.scheme or "https"
    base_origin = f"{scheme}://{parsed.netloc}"

    emails: set[str] = set()
    phones: set[str] = set()
    inns: set[str] = set()
    company_name = ""
    page_title = ""
    combined_text = ""

    contact_paths = [
        "",
        "/contacts",
        "/kontakty",
    ]

    async def _fetch(path: str):
        nonlocal company_name, page_title, combined_text
        target = f"{base_origin.rstrip('/')}{path}"
        try:
            r = await client.get(
                target,
                timeout=httpx.Timeout(connect=2.0, read=2.5, write=2.0, pool=2.0),
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"},
            )
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                text = r.text
                soup = BeautifulSoup(text, "html.parser")

                if not page_title and soup.title and soup.title.string:
                    page_title = soup.title.string.strip()

                # Remove noise
                for s in soup(["script", "style", "svg", "noscript"]):
                    s.decompose()

                plain_text = soup.get_text(" ", strip=True)
                combined_text += " " + plain_text

                # Extract emails
                for raw_e in EMAIL_RE.findall(text):
                    clean_e = _clean_email(raw_e)
                    if clean_e and not clean_e.endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
                        emails.add(clean_e)

                # Extract phones
                for raw_p in PHONE_RE.findall(plain_text):
                    clean_p = _normalize_ru_phone(raw_p)
                    if clean_p:
                        phones.add(clean_p)

                # Extract INN
                for raw_inn in INN_RE.findall(plain_text):
                    if "инн" in plain_text.lower() or "rekvizit" in target.lower():
                        inns.add(raw_inn)

                # Company name
                if not company_name:
                    company_name = extract_company_name(plain_text, domain=root_dom)
        except Exception:
            pass

    # 1. Fetch main page
    try:
        await asyncio.wait_for(_fetch(""), timeout=3.0)
    except Exception:
        pass

    # 2. If no emails on homepage, fetch /contacts, /kontakty in parallel
    if not emails:
        tasks = [_fetch(p) for p in contact_paths[1:]]
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=3.5)
        except Exception:
            pass

    if not emails:
        return None

    # Activity profile
    activity_profile = page_title[:120] if page_title else (company_name or root_dom)

    # Filter emails through supplier_search rules
    valid_emails = prioritize_emails(list(emails), domain=root_dom)
    primary_email = valid_emails[0] if valid_emails else list(emails)[0]

    # MX check
    try:
        has_mx = await asyncio.wait_for(email_has_valid_mx(primary_email), timeout=1.5)
    except Exception:
        has_mx = True

    return {
        "email": primary_email,
        "company_name": company_name or root_dom,
        "phone": list(phones)[0] if phones else "",
        "website": base_origin,
        "inn": list(inns)[0] if inns else "",
        "activity_profile": activity_profile,
        "relevance_score": 100,
        "mx_valid": has_mx,
    }


async def _safe_crawl(url: str, client: httpx.AsyncClient) -> dict[str, Any] | None:
    try:
        return await asyncio.wait_for(crawl_site_for_contact(url, client), timeout=4.0)
    except Exception:
        return None


async def run_outreach_search_task(
    task_id: str,
    name: str,
    prompt: str,
    target_count: int,
    session_factory: Any,
    settings: Any = None,
) -> None:
    """Executes mass lead harvesting task with full cost tracking and multi-task DB persistence."""
    total_yandex_requests = 0
    total_llm_cost = 0.0

    ACTIVE_SEARCH_TASKS[task_id] = {
        "status": "running",
        "name": name,
        "prompt": prompt,
        "target": target_count,
        "collected": 0,
        "scanned_sites": 0,
        "yandex_requests": 0,
        "yandex_cost_rub": 0.0,
        "total_cost_rub": 0.0,
        "message": "Генерация расширенной матрицы запросов...",
    }

    # Ensure task record exists and extract settings
    with session_factory() as db:
        sys_settings = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        yandex_unit_price = float(getattr(sys_settings, "yandex_search_price_per_request", 0.04) or 0.04)
        folder_id = getattr(sys_settings, "yandex_search_folder_id", "") or ""
        api_key = getattr(sys_settings, "yandex_search_api_key", "") or ""

        task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
        if not task_rec:
            task_rec = OutreachSearchTask(
                id=task_id,
                name=name or prompt[:60],
                prompt=prompt,
                target_count=target_count,
                status="running",
                started_at=now_utc(),
                message="Генерация матрицы целевых запросов...",
            )
            db.add(task_rec)
            db.commit()

    try:
        queries, llm_cost = await generate_search_queries_matrix(prompt, count=target_count)
        total_llm_cost += llm_cost

        ACTIVE_SEARCH_TASKS[task_id]["message"] = f"Сгенерировано {len(queries)} целевых запросов. Поиск сайтов в Яндексе..."

        with session_factory() as db:
            task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
            if task_rec:
                task_rec.queries_count = len(queries)
                task_rec.llm_cost_rub = total_llm_cost
                task_rec.total_cost_rub = total_llm_cost
                task_rec.message = f"Сгенерировано {len(queries)} запросов..."
                db.commit()

        seen_domains: set[str] = set()
        candidate_urls: list[str] = []

        # 1. Search phase
        sem = asyncio.Semaphore(4)

        async def _fetch_q_urls(q_text: str) -> tuple[list[str], int]:
            async with sem:
                u_res = []
                req_c = 0
                if folder_id and api_key:
                    u_res, req_c = await fetch_yandex_search_pages(q_text, folder_id, api_key, max_pages=8, groups_on_page=20)
                if not u_res:
                    u_res = await fetch_ddgs_search_pages(q_text, max_results=35)
                return u_res, req_c

        q_chunk_size = 6
        for q_i in range(0, len(queries), q_chunk_size):
            if ACTIVE_SEARCH_TASKS.get(task_id, {}).get("cancel"):
                ACTIVE_SEARCH_TASKS[task_id]["status"] = "cancelled"
                with session_factory() as db:
                    task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                    if task_rec:
                        task_rec.status = "cancelled"
                        task_rec.completed_at = now_utc()
                        task_rec.message = "Задача остановлена пользователем"
                        db.commit()
                return

            if len(candidate_urls) >= target_count * 2.5:
                break

            chunk = queries[q_i : q_i + q_chunk_size]
            results_chunk = await asyncio.gather(*[_fetch_q_urls(q) for q in chunk], return_exceptions=True)
            for item in results_chunk:
                if isinstance(item, tuple):
                    res_urls, req_c = item
                    total_yandex_requests += req_c
                    for u in res_urls:
                        dom = base_domain(u)
                        if dom and dom not in seen_domains and dom not in EXTENDED_BLOCKED_DOMAINS:
                            seen_domains.add(dom)
                            candidate_urls.append(u)

            # Update cost
            current_yandex_cost = round(total_yandex_requests * yandex_unit_price, 2)
            current_total_cost = round(current_yandex_cost + total_llm_cost, 2)

            ACTIVE_SEARCH_TASKS[task_id]["yandex_requests"] = total_yandex_requests
            ACTIVE_SEARCH_TASKS[task_id]["yandex_cost_rub"] = current_yandex_cost
            ACTIVE_SEARCH_TASKS[task_id]["total_cost_rub"] = current_total_cost
            ACTIVE_SEARCH_TASKS[task_id]["message"] = f"Найдено {len(candidate_urls)} сайтов. Выполнено {total_yandex_requests} запросов ({current_total_cost:.2f} ₽)..."

            with session_factory() as db:
                task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                if task_rec:
                    task_rec.yandex_requests = total_yandex_requests
                    task_rec.yandex_cost_rub = current_yandex_cost
                    task_rec.total_cost_rub = current_total_cost
                    task_rec.message = ACTIVE_SEARCH_TASKS[task_id]["message"]
                    db.commit()

        # 2. Verification phase
        ACTIVE_SEARCH_TASKS[task_id]["message"] = f"Верификация {len(candidate_urls)} сайтов и сбор контактов..."

        collected_count = 0
        batch_size = 20

        with session_factory() as db:
            existing_emails = {r[0].lower() for r in db.query(OutreachLead.email).all()}

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=2.5, write=2.0, pool=2.0),
            verify=False,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=30),
        ) as client:
            for i in range(0, len(candidate_urls), batch_size):
                if ACTIVE_SEARCH_TASKS.get(task_id, {}).get("cancel"):
                    ACTIVE_SEARCH_TASKS[task_id]["status"] = "cancelled"
                    with session_factory() as db:
                        task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                        if task_rec:
                            task_rec.status = "cancelled"
                            task_rec.completed_at = now_utc()
                            task_rec.collected_count = collected_count
                            task_rec.scanned_sites = i
                            task_rec.message = "Задача остановлена пользователем"
                            db.commit()
                    return

                batch = candidate_urls[i : i + batch_size]
                tasks = [_safe_crawl(u, client) for u in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                with session_factory() as db:
                    for res in results:
                        if isinstance(res, dict) and res.get("email"):
                            em = res["email"].lower()
                            if em not in existing_emails:
                                existing_emails.add(em)
                                lead = OutreachLead(
                                    task_id=task_id,
                                    email=em,
                                    company_name=res.get("company_name", ""),
                                    phone=res.get("phone", ""),
                                    website=res.get("website", ""),
                                    inn=res.get("inn", ""),
                                    category=prompt[:80],
                                    activity_profile=res.get("activity_profile", ""),
                                    relevance_score=res.get("relevance_score", 100),
                                    source="search",
                                    status="new",
                                    mx_valid=bool(res.get("mx_valid", True)),
                                )
                                db.add(lead)
                                collected_count += 1
                    db.commit()

                current_scanned = min(i + batch_size, len(candidate_urls))
                ACTIVE_SEARCH_TASKS[task_id]["collected"] = collected_count
                ACTIVE_SEARCH_TASKS[task_id]["scanned_sites"] = current_scanned
                ACTIVE_SEARCH_TASKS[task_id]["message"] = f"Собрано {collected_count} целевых контактов из {len(candidate_urls)} сайтов ({current_total_cost:.2f} ₽)..."

                with session_factory() as db:
                    task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                    if task_rec:
                        task_rec.collected_count = collected_count
                        task_rec.scanned_sites = current_scanned
                        task_rec.message = ACTIVE_SEARCH_TASKS[task_id]["message"]
                        db.commit()

                if collected_count >= target_count:
                    break

        final_yandex_cost = round(total_yandex_requests * yandex_unit_price, 2)
        final_total_cost = round(final_yandex_cost + total_llm_cost, 2)

        ACTIVE_SEARCH_TASKS[task_id]["status"] = "completed"

        with session_factory() as db:
            actual_count = db.query(OutreachLead).filter(OutreachLead.task_id == task_id).count()
            task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
            if task_rec:
                task_rec.status = "completed"
                task_rec.collected_count = actual_count
                task_rec.scanned_sites = len(candidate_urls)
                task_rec.yandex_requests = total_yandex_requests
                task_rec.yandex_cost_rub = final_yandex_cost
                task_rec.llm_cost_rub = total_llm_cost
                task_rec.total_cost_rub = final_total_cost
                task_rec.completed_at = now_utc()
                task_rec.message = f"Готово! Собрано {actual_count} проверенных контактов. Стоимость: {final_total_cost:.2f} ₽."
                ACTIVE_SEARCH_TASKS[task_id]["message"] = task_rec.message
                db.commit()

    except Exception as e:
        logger.error(f"Search task {task_id} failed: {e}", exc_info=True)
        ACTIVE_SEARCH_TASKS[task_id]["status"] = "error"
        ACTIVE_SEARCH_TASKS[task_id]["message"] = f"Ошибка: {str(e)}"
        with session_factory() as db:
            task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
            if task_rec:
                task_rec.status = "error"
                task_rec.message = f"Ошибка: {str(e)}"
                task_rec.completed_at = now_utc()
                db.commit()
