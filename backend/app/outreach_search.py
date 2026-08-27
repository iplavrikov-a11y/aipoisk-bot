from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
import socket
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from .ai import call_llm, parse_json_object
from .config import config
from .dadata_client import enrich_company_by_inn
from .models import SystemSettings
from .outreach_models import OutreachLead, OutreachSearchTask, now_utc
from .supplier_search import (
    BLOCKED_DOMAINS,
    base_domain,
    contact_page_url,
    email_has_valid_mx,
    extract_company_name,
    extract_internal_links,
    fetch_page,
    fetch_page_with_browser,
    html_text_to_page,
    normalize_url,
    prioritize_emails,
    _browser_pool_session,
    _normalize_ru_phone,
    _verified_email,
    _verified_phone,
)

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+7|8)[\s\-(]?\d{3}[\s\-)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
INN_RE = re.compile(r"\b\d{10}\b|\b\d{12}\b")

# Generic blocked portal domains (aggregators, job boards, message boards, social media, banks, OFD, tender software)
EXTENDED_BLOCKED_DOMAINS = BLOCKED_DOMAINS | {
    "klerk.ru", "leboard.ru", "profi.ru", "kwork.ru", "youla.ru", "hh.ru", "superjob.ru",
    "zakon.guru", "garant.ru", "audit-it.ru", "vc.ru", "journal.tinkoff.ru",
    # Banks & Financial Brokers
    "sberbank.ru", "sber.ru", "vtb.ru", "alfabank.ru", "tbank.ru", "tinkoff.ru", "gazprombank.ru",
    "psbank.ru", "lockobank.ru", "open.ru", "sovcombank.ru", "raiffeisen.ru", "mkb.ru", "rshb.ru",
    "domrfbank.ru", "uralsib.ru", "zenit.ru", "absolutbank.ru", "metallinvestbank.ru", "bspb.ru",
    "sravni.ru", "banki.ru", "cifin.ru", "vsezaimy.ru", "vbr.ru", "fintender.ru", "tender-garant.ru",
    "finstar.ru", "expertcentre.org",
    # OFD, EDS, Reporting & Tax Software
    "1-ofd.ru", "astral.ru", "tensor.ru", "sbis.ru", "kontur.ru", "taxcom.ru", "platformaofd.ru",
    "taxnet.ru", "e-dis.ru", "ecplegko.ru", "ed-sro.ru",
    # Tender Aggregators, Consulting Brokers & Procurement Software
    "tenderplan.ru", "seldon-pro.ru", "seldon.ru", "b2b-center.ru", "bicotender.ru", "synapsenet.ru",
    "rostender.info", "zakupki.gov.ru", "sberbank-ast.ru", "rts-tender.ru", "roseltorg.ru", "etp-ets.ru",
    "tektorg.ru", "fabrikant.ru", "gz-spb.ru", "zakazrf.ru", "lot-online.ru", "etp-gpb.ru",
    "tendergo.pro", "izhtender.ru", "bidexpert.ru", "tenderopora.ru", "tendercorp.ru", "tendercapital.ru",
    "gos-44.ru", "tenderup.ru", "b2g-partner.ru", "torgi223.ru", "tender-life.ru",
    # Media Holdings, Libraries, Education & Research
    "znanium.ru", "shkulev.ru", "e-library.ru", "cyberleninka.ru", "consultant.ru", "garant.ru",
    "sudact.ru", "gosuslugi.ru", "nalog.gov.ru", "cbr.ru", "fas.gov.ru", "minfin.gov.ru",
}

IRRELEVANT_PATTERNS = [
    r"банковск(?:ая|ие|ую|их)\s+гаранти",
    r"открыти(?:е|я)\s+расчетн(?:ого|ых)\s+счет",
    r"кредитован(?:ие|ия)\s+бизнеса",
    r"сравнен(?:ие|ия)\s+кредит",
    r"онлайн[\s-]касс",
    r"электронн(?:ая|ой|ую|ые)\s+подпис",
    r"выпуск\s+эцп",
    r"оператор\s+фискальных\s+данных",
    r"курсы\s+повышения\s+квалификации",
    r"обучение\s+(?:44-фз|223-фз|госзакупк)",
    r"электронная\s+библиотечная\s+система",
    r"сетевое\s+издание",
    r"городской\s+портал",
    r"новости\s+городов",
    r"агрегатор\s+тендеров",
    r"поиск\s+тендеров\s+и\s+закупок",
    r"тендерное\s+сопровождение",
]
RE_IRRELEVANT = re.compile("|".join(IRRELEVANT_PATTERNS), re.IGNORECASE)


@dataclass
class OutreachCandidate:
    url: str
    domain: str
    title: str = ""
    snippet: str = ""
    source_query: str = ""
    ai_rank_confidence: int = 0
    ai_rank_reason: str = ""


FORBIDDEN_FILE_EXTENSIONS = (
    ".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".ico",
    ".map", ".min", ".woff", ".woff2", ".ttf", ".eot", ".json", ".xml", ".mp4",
    ".webm", ".gz", ".zip", ".tar", ".pdf", ".txt", ".0", ".1", ".2", ".3", ".4",
    ".5", ".6", ".7", ".8", ".9", ".ts", ".jsx", ".tsx", ".scss", ".less", ".apk"
)

FORBIDDEN_PLACEHOLDER_DOMAINS = {
    "example.com", "example.org", "example.net", "domain.com", "yoursite.com",
    "mail.com", "email.com", "site.ru", "site.com", "vashsait.ru", "mysite.ru",
    "test.ru", "sample.com", "tempmail.com", "sait.ru", "vash-sait.ru", "domain.ru",
    "test.com", "localhost", "localdomain", "mycompany.ru", "company.ru", "somedomain.com"
}

FORBIDDEN_PLACEHOLDER_USERS = {
    "name", "your", "test", "tests", "testing", "sample", "rating", "email",
    "user", "username", "someone", "mail", "post", "frunze", "ivanov", "petrov",
    "sidorov", "example", "demo", "test1", "test2", "no-reply", "noreply",
    "donotreply", "null", "undefined", "none", "admin@harant.ru"
}

FORBIDDEN_SUPPORT_PREFIXES = (
    "support@", "help@", "claim@", "abuse@", "postmaster@", "mailer-daemon@",
    "hostmaster@", "root@", "security@", "ebs_support@", "ticket@", "tickets@",
    "billing@", "compliance@", "otzyv@", "otzyvy@", "press@", "pressa@",
    "hr@", "job@", "rabota@", "career@", "resume@", "kadry@"
)


def _clean_email(email_str: str) -> str:
    if not email_str:
        return ""
    import urllib.parse
    email_str = urllib.parse.unquote(str(email_str or "")).strip().lower()
    email_str = email_str.strip(".,;:/()[]{}<>\"'\\_+-# \t\r\n")
    email_str = re.sub(r"^(?:20|3d|25|2f)+", "", email_str).strip()
    if not (5 <= len(email_str) <= 100):
        return ""
    if "@" not in email_str or email_str.count("@") != 1:
        return ""
    user, domain = email_str.split("@", 1)
    user = user.strip(".,;:/()[]{}<>\"'\\_+-#")
    domain = domain.strip(".,;:/()[]{}<>\"'\\_+-#")
    if not user or not domain or "." not in domain:
        return ""
    if any(domain.endswith(ext) for ext in FORBIDDEN_FILE_EXTENSIONS):
        return ""
    if any(domain.startswith(pref) for pref in ("0.", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
        return ""
    tld = domain.split(".")[-1]
    if tld.isdigit() or len(tld) < 2 or len(tld) > 24:
        return ""
    if any(user.startswith(bad) for bad in ("--", "..", "__", "intro.", "jquery", "bootstrap", "react", "vue", "angular", "browser")):
        return ""
    if domain in FORBIDDEN_PLACEHOLDER_DOMAINS:
        return ""
    if user in FORBIDDEN_PLACEHOLDER_USERS:
        return ""
    if user.startswith(("test-", "test.", "example", "sample")):
        return ""
    if any(email_str.startswith(pref) for pref in FORBIDDEN_SUPPORT_PREFIXES):
        return ""
    try:
        if any(ord(c) > 127 for c in domain):
            domain = domain.encode("idna").decode("ascii")
    except Exception:
        pass
    return f"{user}@{domain}"


# Active search background jobs {task_id: {"status": str, "target": int, "progress": int, "message": str, "cancel": bool}}
ACTIVE_SEARCH_TASKS: dict[str, dict[str, Any]] = {}


def get_fresh_system_settings(session_factory: Any = None) -> SystemSettings | None:
    """Safely retrieves expunged SystemSettings with all attributes loaded to prevent DetachedInstanceError."""
    from .db import SessionLocal
    factory = session_factory or SessionLocal
    with factory() as db:
        s = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
        if s:
            _ = s.custom_ai_providers_json
            _ = s.yandex_search_folder_id
            _ = s.yandex_search_api_key
            _ = s.yandex_search_price_per_request
            _ = s.primary_provider
            _ = s.primary_model
            _ = s.light_provider
            _ = s.light_model
            db.expunge(s)
            return s
    return None


async def generate_search_queries_matrix(
    prompt: str,
    count: int = 40,
    sys_settings: SystemSettings | None = None,
    is_extend: bool = False,
    wave_index: int = 1,
    existing_count: int = 0,
    executed_queries: set[str] | None = None,
) -> tuple[list[str], float]:
    """Generates an extensive matrix of targeted commercial B2B supplier search queries."""
    if count <= 120:
        target_q_count = min(70, max(35, count // 2))
    elif count <= 500:
        target_q_count = min(140, max(70, count // 4))
    elif count <= 1500:
        target_q_count = min(220, max(120, count // 7))
    else:
        target_q_count = min(280, max(180, count // 10))

    if is_extend or wave_index > 1:
        system_prompt = (
            f"Ты ведущий эксперт по поиску реальных B2B поставщиков, заводов и коммерческих организаций. "
            f"ЭТО РЕЖИМ ДОБОРА (ВОЛНА №{wave_index}). В базе уже собрано {existing_count}+ базовых федеральных организаций по этой теме. "
            "СТРОГИЕ ПРАВИЛА ДОБОРА: "
            "1) СТРОГО ЗАПРЕЩЕНО повторять общие шаблонные фразы (например: 'поставщики оптом', 'участники тендеров 44-фз'), так как они уже полностью исчерпаны. "
            "2) УЗКИЕ НОМЕНКЛАТУРНЫЕ ПОДКАТЕГОРИИ: разбей заданную тему на 6-10 конкретных товарных групп, видов сырья, комплектующих, оборудования или номенклатуры (с кодами ОКПД2, ГОСТ, ТУ, марками, специфическими отраслевыми терминами). "
            "3) РЕГИОНАЛЬНЫЕ КЛАСТЕРЫ И ЦЕНТРЫ СБЫТА: обязательно привязывай запросы к конкретным промышленным регионам и городам РФ (Урал: Екатеринбург, Челябинск, Пермь; Поволжье: Казань, Самара, Нижний Новгород, Уфа; Сибирь: Новосибирск, Красноярск, Омск; Юг: Ростов-на-Дону, Краснодар; СЗФО: СПб; ЦФО: Воронеж, Ярославль, Калуга; ДВФО: Хабаровск, Владивосток). "
            "4) СТАТУСНЫЕ ОПЕРАТОРЫ СНАБЖЕНИЯ: 'официальный дилер завода', 'торговый дом производителя', 'региональный распределительный склад', 'комплектация промышленных предприятий', 'реестр исполненных госконтрактов по профилю', 'складской комплекс опт'. "
            "5) ТЕНДЕРНЫЙ ОПЫТ: если в теме указаны закупки/тендеры — используй маркеры реальных исполнителей: 'поставки по 44-ФЗ', 'поставки по 223-ФЗ', 'реестр договоров', 'отдел корпоративных закупок'. "
            "6) ИСКЛЮЧЕНИЕ МУСОРА: используй отрицательные операторы: -'банковская гарантия' -'обучение' -'семинар' -'эцп' -'агрегатор' -'курсы'. "
            f"Сгенерируй от {target_q_count} разнообразных глубоких целевых поисковых запросов. "
            "Верни ТОЛЬКО валидный JSON массив строк, например: [\"запрос 1\", \"запрос 2\"]."
        )
        user_prompt = (
            f"Целевая отрасль / профиль поставщиков:\n{prompt}\n\n"
            f"Параметры добора: Волна #{wave_index}, требуется дополнительно контактов: {count}. "
            f"Сгенерируй {target_q_count} глубоких специализированных поисковых запросов в виде JSON массива:"
        )
    else:
        system_prompt = (
            "Ты ведущий эксперт по поиску реальных B2B поставщиков, заводов и коммерческих организаций. "
            "Твоя задача — составить глубокую и точную матрицу поисковых запросов для Яндекса и Google, "
            "которая найдет официальные сайты реальных поставщиков и производителей по заданной теме пользователя. "
            "СТРОГИЕ ПРАВИЛА СОСТАВЛЕНИЯ ЗАПРОСОВ: "
            "1) Фокусируйся на товарных и отраслевых коммерческих запросах: заводы, производители, оптовые поставщики, дистрибьюторы, склады, каталоги продукции, коммерческие отделы продаж. "
            "2) Добавляй коммерческие модификаторы: 'производитель', 'завод', 'оптом со склада', 'официальный дилер', 'дистрибьютор', 'прайс-лист', 'отдел продаж', 'каталог'. "
            "3) СПЕЦИАЛИЗАЦИЯ ПО ТЕНДЕРАМ / 44-ФЗ / 223-ФЗ: Если в запросе пользователя указаны участники тендеров, поставщики по 44-ФЗ/223-ФЗ или госконтрактам — ОБЯЗАТЕЛЬНО составляй специализированные запросы, находящие компании с подтвержденным опытом закупок: 'поставки по 44-ФЗ', 'поставки по 223-ФЗ', 'исполненные госконтракты', 'реестр контрактов', 'поставки для бюджетных учреждений', 'поставки для госучреждений', 'опыт работы по 44-ФЗ', 'тендерный отдел поставщика', 'государственные закупки поставщик'. "
            "4) Используй отрицательные операторы Яндекса для исключения мусора: -'банковская гарантия' -'обучение' -'семинар' -'эцп' -'агрегатор' -'курсы'. "
            "5) Включай географический охват: крупнейшие регионы РФ (Москва, Санкт-Петербург, Урал, Поволжье, Сибирь, Юг РФ, общероссийские формулировки). "
            "6) НЕ составляй запросы 'как выиграть тендер' или 'обучение госзакупкам'. Нужны только сайты реальных поставщиков товаров и услуг. "
            f"Сгенерируй от {target_q_count} разнообразных целевых поисковых запросов. "
            "Верни ТОЛЬКО валидный JSON массив строк, например: [\"запрос 1\", \"запрос 2\"]."
        )
        user_prompt = f"Целевая отрасль / профиль поставщиков:\n{prompt}\n\nКоличество контактов: {count}. Сгенерируй {target_q_count} поисковых запросов в виде JSON массива:"

    estimated_llm_cost = 0.02  # Gemini Flash-Lite query matrix generation

    try:
        settings = sys_settings or get_fresh_system_settings()
        if settings:
            resp = await call_llm(
                settings,
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
                raw_q = [str(q).strip() for q in data if str(q).strip()]
                if executed_queries:
                    raw_q = [q for q in raw_q if q.strip().lower() not in executed_queries]
                if raw_q:
                    return raw_q[:target_q_count], estimated_llm_cost
    except Exception as e:
        logger.warning(f"Error generating search queries with AI: {e}")

    # Fallback heuristic queries with commercial operators
    base = prompt.strip()
    words = [w for w in re.split(r"[,;\s]+", base) if len(w) > 2]
    keywords = " ".join(words[:4]) if words else base
    if is_extend or wave_index > 1:
        regions = ["Екатеринбург", "Казань", "Самара", "Новосибирск", "Нижний Новгород", "Ростов-на-Дону", "Краснодар", "Уфа", "Челябинск", "Пермь", "Красноярск", "Воронеж", "Владивосток", "Хабаровск", "СПб", "Ярославль"]
        types = [
            "официальный дилер завода склад",
            "торговый дом производитель оптом",
            "комплексное снабжение предприятий прайс",
            "отдел продаж производителя каталог",
            "региональный распределительный центр опт",
            "поставки для госучреждений опыт 44-фз",
            "реестр исполненных контрактов поставщик 223-фз",
        ]
    else:
        regions = ["Москва", "СПб", "Екатеринбург", "Новосибирск", "Казань", "Нижний Новгород", "Самара", "Краснодар", "Россия", "ЦФО", "Урал", "Поволжье"]
        types = [
            "завод производитель оптом",
            "официальный дистрибьютор склад",
            "торговый дом поставщик прайс",
            "каталог продукции отдел продаж",
            "оптовые поставки от производителя",
            "производство и поставка опт",
        ]

    fallback = []
    for reg in regions:
        for t in types:
            q_str = f"{keywords} {t} {reg} -\"банковская гарантия\" -\"обучение\""
            if not executed_queries or q_str.strip().lower() not in executed_queries:
                fallback.append(q_str)
    return fallback[:75], 0.0


async def fetch_yandex_search_candidates(
    query: str,
    folder_id: str,
    api_key: str,
    max_pages: int = 3,
    groups_on_page: int = 20,
) -> tuple[list[OutreachCandidate], int]:
    """Targeted Yandex Search v2 matching core TenderLex search economics."""
    if not folder_id or not api_key:
        return [], 0

    headers = {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}
    candidates: list[OutreachCandidate] = []
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
                            # Extract title
                            t_elem = doc.find("title")
                            title_text = "".join(t_elem.itertext()).strip() if t_elem is not None else ""
                            # Extract snippet / passages
                            passages = doc.findall(".//passage")
                            headline = doc.find(".//headline")
                            snippet_parts = []
                            if headline is not None:
                                snippet_parts.append("".join(headline.itertext()).strip())
                            for p in passages:
                                snippet_parts.append("".join(p.itertext()).strip())
                            snippet_text = " ".join(snippet_parts)[:400]

                            candidates.append(
                                OutreachCandidate(
                                    url=u,
                                    domain=dom,
                                    title=title_text,
                                    snippet=snippet_text,
                                    source_query=query,
                                )
                            )
            except Exception as e:
                logger.debug(f"Yandex page {page} error for query '{query}': {e}")
                break

    return candidates, requests_count


async def fetch_ddgs_search_candidates(query: str, max_results: int = 40) -> list[OutreachCandidate]:
    """Free fallback search via DuckDuckGo returning candidate objects."""
    candidates = []
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results, region="ru-ru")
        for r in results:
            if isinstance(r, dict) and "href" in r:
                u = normalize_url(r["href"])
                dom = base_domain(u)
                if dom and dom not in EXTENDED_BLOCKED_DOMAINS:
                    candidates.append(
                        OutreachCandidate(
                            url=u,
                            domain=dom,
                            title=str(r.get("title") or "").strip(),
                            snippet=str(r.get("body") or "").strip(),
                            source_query=query,
                        )
                    )
    except Exception as e:
        logger.debug(f"DDGS search error: {e}")
    return candidates


async def ai_rerank_outreach_candidates(
    candidates: list[OutreachCandidate],
    prompt: str,
    sys_settings: SystemSettings | None = None,
    batch_size: int = 25,
) -> tuple[list[OutreachCandidate], float]:
    """Pre-filters candidate search snippets in batches using LLM to eliminate irrelevant sites before crawling."""
    if not candidates:
        return [], 0.0

    settings = sys_settings or get_fresh_system_settings()
    if not settings or not settings.has_active_ai_provider:
        return candidates, 0.0

    approved_candidates: list[OutreachCandidate] = []
    total_cost = 0.0

    system_prompt = (
        "Ты профессиональный AI-аудитор B2B компаний, поставщиков и участников закупок. "
        "Твоя задача — отобрать из поисковой выдачи сайты организаций, строго соответствующих запросу пользователя "
        "(включая компании-посредники, операторов комплексного снабжения, торговые дома, дистрибьюторов, подрядчиков по закупкам, заводы и дилеров). "
        "СТРОГО ОТКЛОНЯЙ (is_supplier: false): "
        "- Банки, финансовые услуги, кредитование, лизинг, банковские гарантии. "
        "- Обучающие центры, курсы, семинары, учебные заведения, электронные библиотеки. "
        "- Сервисы электронной подписи (ЭЦП), онлайн-касс, ОФД, бухгалтерский софт. "
        "- Тендерные агрегаторы, юридические фирмы по спорам в ФАС, доски объявлений. "
        "- Новостные порталы, блоги, форумы, статьи, вакансии. "
        "ПРИНИМАЙ (is_supplier: true, confidence >= 40): "
        "- Компании, соответствующие профилю запроса пользователя (включая снабженцев, торговых посредников, участников торгов). "
        "Верни ТОЛЬКО JSON массив объектов:\n"
        "[{\"index\": 0, \"is_supplier\": true, \"confidence\": 85, \"reason\": \"Компания по профилю запроса\"}]"
    )

    for i in range(0, len(candidates), batch_size):
        chunk = candidates[i : i + batch_size]
        items_payload = []
        for idx, c in enumerate(chunk):
            items_payload.append({
                "index": idx,
                "domain": c.domain,
                "url": c.url,
                "title": c.title,
                "snippet": c.snippet,
            })

        user_prompt = (
            f"Тема поиска поставщиков:\n{prompt}\n\n"
            f"Список кандидатов из поисковой выдачи:\n{json.dumps(items_payload, ensure_ascii=False)}\n\n"
            "Оцени каждого кандидата и верни JSON массив:"
        )

        try:
            resp = await call_llm(
                sys_settings,
                user_prompt,
                system_prompt=system_prompt,
                tier="light",
                json_mode=True,
                timeout_seconds=40,
            )
            total_cost += 0.35  # ~0.35 RUB per chunk
            text = resp.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            evaluations = json.loads(text)
            if isinstance(evaluations, list):
                eval_map = {int(item.get("index", -1)): item for item in evaluations if isinstance(item, dict)}
                for idx, c in enumerate(chunk):
                    ev = eval_map.get(idx)
                    if ev and bool(ev.get("is_supplier")) and int(ev.get("confidence", 0) or 0) >= 50:
                        c.ai_rank_confidence = int(ev.get("confidence", 0) or 0)
                        c.ai_rank_reason = str(ev.get("reason") or "")
                        approved_candidates.append(c)
            else:
                approved_candidates.extend(chunk)
        except Exception as e:
            logger.warning(f"AI candidate rerank error for chunk {i}: {e}")
            approved_candidates.extend(chunk)

    return approved_candidates, total_cost


def extract_outreach_company_name(combined_text: str, candidate: OutreachCandidate) -> str:
    """Extracts a clean company name from candidate title or website text."""
    generic_lines = {"компания", "о компании", "производство", "о производстве", "главная", "контакты"}
    title = re.sub(r"\s+", " ", candidate.title or "").strip(" -|")
    if title:
        for separator in ("|", "—", "–", "-"):
            title = title.split(separator)[0].strip()
        if title and 4 <= len(title) <= 80 and title.lower() not in generic_lines:
            return title
    for line in combined_text.splitlines()[:25]:
        line = re.sub(r"\s+", " ", line).strip(" -|")
        if 4 <= len(line) <= 80 and line.lower() not in generic_lines:
            if any(marker in line.lower() for marker in ["ооо", "ао", "пао", "завод", "фабрика", "тд", "гк", "производственная компания"]):
                return line
    return candidate.domain


async def crawl_site_for_outreach_lead(
    candidate: OutreachCandidate,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Deep two-tier website crawling: multi-page HTTP + Playwright headless browser fallback."""
    origin_url = candidate.url
    root_dom = candidate.domain or base_domain(origin_url)
    if not root_dom or root_dom in EXTENDED_BLOCKED_DOMAINS:
        return None

    parsed = urlparse(origin_url)
    scheme = parsed.scheme or "https"
    base_origin = f"{scheme}://{parsed.netloc}"

    emails: set[str] = set()
    phones: set[str] = set()
    inns: set[str] = set()
    page_title = candidate.title or ""
    collected_text_parts: list[str] = []

    # 1. Fast HTTP Multi-page fetch
    async def _fetch_http(url_target: str) -> str:
        try:
            r = await client.get(
                url_target,
                timeout=httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=3.0),
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"},
            )
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                return (r.text or "")[:300000]
        except Exception:
            pass
        return ""

    main_html = await _fetch_http(base_origin)
    if main_html:
        soup = BeautifulSoup(main_html[:200000], "html.parser")
        if not page_title and soup.title and soup.title.string:
            page_title = soup.title.string.strip()

        for s in soup(["script", "style", "svg", "noscript"]):
            s.decompose()
        main_text = soup.get_text(" ", strip=True)[:100000]
        collected_text_parts.append(main_text)

        # Extract contacts from homepage HTML & tags
        for a in soup.find_all("a", href=True):
            href = str(a.get("href") or "").strip()
            if href.lower().startswith("mailto:"):
                clean_e = _clean_email(href.split(":", 1)[1].split("?")[0])
                if clean_e and not clean_e.endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
                    emails.add(clean_e)
            elif href.lower().startswith("tel:"):
                clean_p = _normalize_ru_phone(href.split(":", 1)[1].split("?")[0])
                if clean_p:
                    phones.add(clean_p)

        for raw_e in EMAIL_RE.findall(main_html[:250000]):
            clean_e = _clean_email(raw_e)
            if clean_e and not clean_e.endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
                emails.add(clean_e)

        for raw_p in PHONE_RE.findall(main_text):
            clean_p = _normalize_ru_phone(raw_p)
            if clean_p:
                phones.add(clean_p)

        for raw_inn in INN_RE.findall(main_text):
            if "инн" in main_text.lower() or "rekvizit" in base_origin.lower():
                inns.add(raw_inn)

        # Discover internal links to contacts, about, requisites, catalog
        internal_links = extract_internal_links(main_html, base_origin)
        if internal_links:
            subpage_htmls = await asyncio.gather(*[_fetch_http(l) for l in internal_links[:8]], return_exceptions=True)
            for sub_html in subpage_htmls:
                if isinstance(sub_html, str) and sub_html:
                    sub_soup = BeautifulSoup(sub_html[:200000], "html.parser")
                    for s in sub_soup(["script", "style", "svg", "noscript"]):
                        s.decompose()
                    sub_text = sub_soup.get_text(" ", strip=True)[:100000]
                    collected_text_parts.append(sub_text)

                    for a in sub_soup.find_all("a", href=True):
                        href = str(a.get("href") or "").strip()
                        if href.lower().startswith("mailto:"):
                            clean_e = _clean_email(href.split(":", 1)[1].split("?")[0])
                            if clean_e and not clean_e.endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
                                emails.add(clean_e)
                        elif href.lower().startswith("tel:"):
                            clean_p = _normalize_ru_phone(href.split(":", 1)[1].split("?")[0])
                            if clean_p:
                                phones.add(clean_p)

                    for raw_e in EMAIL_RE.findall(sub_html[:250000]):
                        clean_e = _clean_email(raw_e)
                        if clean_e and not clean_e.endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
                            emails.add(clean_e)

                    for raw_p in PHONE_RE.findall(sub_text):
                        clean_p = _normalize_ru_phone(raw_p)
                        if clean_p:
                            phones.add(clean_p)

                    for raw_inn in INN_RE.findall(sub_text):
                        inns.add(raw_inn)

    # 2. If no emails found or site is SPA/JS-based, fallback to Playwright Headless Browser
    if not emails or len(" ".join(collected_text_parts)) < 200:
        try:
            browser_page = await asyncio.wait_for(
                fetch_page_with_browser(base_origin, source="outreach_crawler"),
                timeout=18.0,
            )
            if browser_page and browser_page.get("html"):
                b_html = (browser_page.get("html") or "")[:250000]
                b_text = (browser_page.get("text") or "")[:100000]
                collected_text_parts.append(b_text)

                for raw_e in EMAIL_RE.findall(b_html):
                    clean_e = _clean_email(raw_e)
                    if clean_e and not clean_e.endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
                        emails.add(clean_e)

                for raw_p in PHONE_RE.findall(b_text):
                    clean_p = _normalize_ru_phone(raw_p)
                    if clean_p:
                        phones.add(clean_p)

                for raw_inn in INN_RE.findall(b_text):
                    inns.add(raw_inn)
        except Exception as e:
            logger.debug(f"Playwright fallback error for {base_origin}: {e}")

    if not emails:
        return None

    # Filter out state, municipal and educational domain suffixes
    lower_dom = root_dom.lower()
    if lower_dom.endswith((".gov.ru", ".edu.ru", ".mil.ru", ".adm.ru", "gosuslugi.ru", "nalog.ru")):
        return None

    combined_text = " ".join(collected_text_parts)[:15000]

    # Semantic pattern rejection
    if RE_IRRELEVANT.search(page_title) or (len(RE_IRRELEVANT.findall(combined_text)) >= 2 and not any(k in combined_text.lower() for k in ["производство", "завод", "поставка товара", "оптовые продажи", "дистрибьютор", "каталог продукции", "подрядные работы"])):
        logger.debug(f"Skipping irrelevant domain {root_dom} ({page_title})")
        return None

    # Company name extraction
    company_name = extract_outreach_company_name(combined_text, candidate)

    # Prioritize corporate emails
    valid_emails = prioritize_emails(list(emails), domain=root_dom)
    primary_email = valid_emails[0] if valid_emails else list(emails)[0]

    # Validate MX record
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
        "page_title": page_title,
        "plain_text": combined_text,
        "activity_profile": page_title[:140] if page_title else (company_name or root_dom),
        "mx_valid": has_mx,
    }


async def ai_review_outreach_lead(
    crawled_data: dict[str, Any],
    prompt: str,
    sys_settings: SystemSettings | None = None,
) -> tuple[dict[str, Any] | None, float]:
    """Full-text LLM verification of crawled vendor website to confirm match with target niche."""
    settings = sys_settings or get_fresh_system_settings()
    if not settings or not settings.has_active_ai_provider:
        return crawled_data, 0.0

    site_text = crawled_data.get("plain_text", "")[:4000]
    page_title = crawled_data.get("page_title", "")
    company_name = crawled_data.get("company_name", "")
    website = crawled_data.get("website", "")

    system_prompt = (
        "Ты строгий B2B аудитор коммерческих поставщиков и производителей. "
        "Твоя задача — проверить текст сайта компании и определить, является ли она реальным целевым поставщиком/производителем по запросу пользователя. "
        "КРИТЕРИИ ОТБОРА: "
        "1. ПРИНИМАЙ (is_relevant: true, score >= 60): "
        "   - Заводы, производственные предприятия, фабрики. "
        "   - Оптовые поставщики, дистрибьюторы, официальные дилеры, торговые дома, склады. "
        "   - Профильные коммерческие и строительные подрядчики. "
        "2. СПЕЦИАЛИЗАЦИЯ ПО ТЕНДЕРАМ / 44-ФЗ / 223-ФЗ: "
        "   - Если в запросе пользователя явно указаны участники тендеров, поставщики по 44-ФЗ/223-ФЗ или госконтрактам — отдавай приоритет и принимай компании, на сайтах которых есть подтверждения работы с закупками: разделы 'Госзакупки', 'Тендеры', 'Поставки по 44-ФЗ/223-ФЗ', поставки для госучреждений, школ, больниц, министерств, номера контрактов ЕИС. "
        "3. ОТКЛОНЯЙ (is_relevant: false, score < 40): "
        "   - Банки, финансовые сервисы, банковские гарантии, займы, лизинг. "
        "   - Обучающие центры, курсы 44-ФЗ/223-ФЗ, учебные заведения, электронные библиотеки. "
        "   - Продажа ЭЦП, онлайн-касс, ОФД, бухгалтерский и налоговый софт. "
        "   - Тендерные агрегаторы, юридические фирмы по сопровождению торгов, брокеры. "
        "   - Новостные издания, блоги, форумы, доски объявлений. "
        "Верни ТОЛЬКО JSON объект:\n"
        "{\n"
        "  \"is_relevant\": true/false,\n"
        "  \"score\": 0-100,\n"
        "  \"site_type\": \"manufacturer|dealer|distributor|supplier|contractor|unrelated\",\n"
        "  \"activity_profile\": \"Краткое описание деятельности компании (1-2 предложения)\",\n"
        "  \"reason\": \"краткое обоснование решения\"\n"
        "}"
    )

    user_prompt = (
        f"Целевой запрос пользователя:\n{prompt}\n\n"
        f"Данные о компании:\n"
        f"- Сайт: {website}\n"
        f"- Название: {company_name}\n"
        f"- Заголовок: {page_title}\n"
        f"- Текст сайта:\n{site_text}\n\n"
        "Оцени соответствие компании критериям и верни JSON:"
    )

    estimated_cost = 0.007  # Real Gemini Flash-Lite cost (~2K tokens)

    try:
        raw = await call_llm(
            sys_settings,
            user_prompt,
            system_prompt=system_prompt,
            tier="light",
            json_mode=True,
            timeout_seconds=30,
        )
        data = parse_json_object(raw)
        if isinstance(data, dict):
            is_rel = bool(data.get("is_relevant", False))
            score = int(data.get("score", 0) or 0)
            site_type = str(data.get("site_type") or "").lower()
            if is_rel and score >= 55 and site_type != "unrelated":
                crawled_data["relevance_score"] = score
                crawled_data["activity_profile"] = str(data.get("activity_profile") or crawled_data["activity_profile"])
                crawled_data["site_type"] = site_type
                return crawled_data, estimated_cost
            else:
                logger.debug(f"AI review rejected {website}: {data.get('reason')}")
                return None, estimated_cost
    except Exception as e:
        logger.warning(f"AI review error for {website}: {e}")

    return crawled_data, estimated_cost


async def enrich_lead_with_dadata(lead_data: dict[str, Any]) -> dict[str, Any] | None:
    """Enriches company via DaData EGRUL API, validates active legal status and filters out prohibited OKVEDs."""
    inn = str(lead_data.get("inn") or "").strip()
    if not inn or len(inn) not in (10, 12):
        return lead_data

    try:
        dadata_res = await enrich_company_by_inn(inn)
        if not dadata_res:
            return lead_data

        # 1. Check legal status: discard liquidated or bankrupt companies
        status = str(dadata_res.get("status") or "").upper()
        if status in {"LIQUIDATED", "LIQUIDATING", "BANKRUPT"}:
            logger.debug(f"Rejecting company {inn}: inactive EGRUL status '{status}'")
            return None

        # 2. Check OKVED: reject financial, educational, legal broker activities
        okved = str(dadata_res.get("okved") or "").strip()
        if okved.startswith(("64.", "65.", "66.", "85.", "69.", "64", "65", "66", "85", "69")):
            logger.debug(f"Rejecting company {inn}: non-target OKVED '{okved}'")
            return None

        # 3. Enrich verified company attributes
        if dadata_res.get("company_name"):
            lead_data["company_name"] = str(dadata_res["company_name"]).strip()
        if dadata_res.get("management_name"):
            lead_data["management_name"] = str(dadata_res["management_name"]).strip()
        if dadata_res.get("city") or dadata_res.get("region"):
            lead_data["region"] = str(dadata_res.get("city") or dadata_res.get("region") or "").strip()
        if dadata_res.get("legal_address"):
            lead_data["legal_address"] = str(dadata_res["legal_address"]).strip()

        return lead_data
    except Exception as e:
        logger.warning(f"DaData enrichment error for INN {inn}: {e}")
        return lead_data


async def run_outreach_search_task(
    task_id: str,
    name: str,
    prompt: str,
    target_count: int,
    session_factory: Any,
    settings: Any = None,
    is_extend: bool = False,
    extra_count: int = 0,
    additional_prompt: str = "",
    wave_index: int = 1,
    is_resume: bool = False,
) -> None:
    """Executes enterprise-grade B2B supplier search with Adaptive Multi-Pass loop, Playwright crawling & strict Yandex pricing."""
    sys_settings = get_fresh_system_settings(session_factory)
    yandex_unit_price = float(getattr(sys_settings, "yandex_search_price_per_request", 0.04) or 0.04)
    folder_id = getattr(sys_settings, "yandex_search_folder_id", "") or ""
    api_key = getattr(sys_settings, "yandex_search_api_key", "") or ""

    total_yandex_requests = 0
    total_llm_cost = 0.0
    initial_collected = 0
    initial_scanned = 0

    with session_factory() as db:
        task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
        if not task_rec:
            task_rec = OutreachSearchTask(
                id=task_id,
                name=name or prompt[:60],
                prompt=prompt,
                target_count=target_count,
                status="running",
                started_at=now_utc(),
                message="Анализирую задачу и составляю отраслевую матрицу запросов...",
            )
            db.add(task_rec)
            db.commit()
        else:
            task_rec.status = "running"
            task_rec.started_at = now_utc()
            task_rec.completed_at = None
            current_task_collected = task_rec.collected_count or 0
            if is_resume:
                total_yandex_requests = task_rec.yandex_requests or 0
                initial_scanned = task_rec.scanned_sites or 0
                try:
                    w_list = json.loads(task_rec.waves_json) if task_rec.waves_json else []
                    matched_w = next((w for w in w_list if w.get("wave") == wave_index), None)
                    if matched_w:
                        w_reqs = matched_w.get("yandex_requests", 0)
                        w_coll = matched_w.get("collected", 0)
                        initial_yandex_requests = max(0, total_yandex_requests - w_reqs)
                        initial_collected = max(0, current_task_collected - w_coll)
                        wave_target = matched_w.get("target") or (extra_count if is_extend else target_count)
                    else:
                        initial_yandex_requests = total_yandex_requests if is_extend else 0
                        initial_collected = current_task_collected
                        wave_target = extra_count if is_extend else target_count
                except Exception:
                    initial_yandex_requests = total_yandex_requests if is_extend else 0
                    initial_collected = current_task_collected
                    wave_target = extra_count if is_extend else target_count
                task_rec.message = f"Возобновление сбора контактов (цель: +{wave_target})..."
            elif is_extend:
                total_yandex_requests = task_rec.yandex_requests or 0
                initial_yandex_requests = total_yandex_requests
                total_llm_cost = 0.0
                initial_collected = current_task_collected
                initial_scanned = task_rec.scanned_sites or 0
                if target_count < initial_collected:
                    target_count = initial_collected + max(extra_count, 100)
                task_rec.target_count = target_count
                task_rec.message = f"Запуск добора (+{extra_count or (target_count - initial_collected)} контактов)..."
            else:
                initial_yandex_requests = 0
                task_rec.target_count = target_count
                task_rec.message = "Анализирую задачу и составляю отраслевую матрицу запросов..."
            db.commit()

    initial_yandex_cost = round(total_yandex_requests * yandex_unit_price, 2)
    wave_target = wave_target if is_resume else (extra_count if (is_extend and extra_count > 0) else target_count)
    wave_init_coll = max(0, current_task_collected - initial_collected) if is_resume else 0
    wave_init_reqs = max(0, total_yandex_requests - initial_yandex_requests) if is_resume else 0

    ACTIVE_SEARCH_TASKS[task_id] = {
        "status": "running",
        "name": name,
        "prompt": prompt,
        "target": target_count,
        "collected": current_task_collected,
        "scanned_sites": initial_scanned,
        "yandex_requests": total_yandex_requests,
        "yandex_cost_rub": initial_yandex_cost,
        "llm_cost_rub": 0.0,
        "total_cost_rub": initial_yandex_cost,
        "is_extend": is_extend,
        "wave_index": wave_index,
        "wave_target": wave_target,
        "wave_collected": wave_init_coll,
        "wave_yandex_requests": wave_init_reqs,
        "wave_cost_rub": round(wave_init_reqs * yandex_unit_price, 2),
        "message": f"Возобновление сбора контактов..." if is_resume else (f"Добор контактов: цель +{wave_target} контактов..." if is_extend else "Анализирую задачу и составляю отраслевую матрицу запросов..."),
    }

    async with _browser_pool_session():
        try:
            active_prompt = f"{prompt}. {additional_prompt}".strip() if additional_prompt else prompt
            queries_target_count = extra_count if (is_extend and extra_count > 0) else target_count

            # Preload ALL existing domains and emails to prevent duplicate crawls and searches
            seen_domains: set[str] = set()
            with session_factory() as db:
                existing_lead_rows = db.query(OutreachLead.email, OutreachLead.website).all()
                existing_emails = set()
                for em, web in existing_lead_rows:
                    if em:
                        em_clean = em.strip().lower()
                        existing_emails.add(em_clean)
                        if "@" in em_clean:
                            d_em = base_domain(em_clean.split("@")[-1])
                            if d_em:
                                seen_domains.add(d_em)
                    if web:
                        d_web = base_domain(web)
                        if d_web:
                            seen_domains.add(d_web)

            collected_count = initial_collected
            scanned_so_far = initial_scanned
            max_passes = 6
            current_pass = 1
            executed_queries: set[str] = set()

            sem = asyncio.Semaphore(4)
            queue_file = Path(f"data/outreach_queue_{task_id}.json")

            while collected_count < target_count and current_pass <= max_passes:
                remaining_needed = target_count - collected_count
                approved_candidates: list[OutreachCandidate] = []

                # 0. Check if candidate queue is already preserved on disk from pause/crash
                if is_resume and queue_file.exists():
                    try:
                        with open(queue_file, "r", encoding="utf-8") as f:
                            q_data = json.load(f)
                        saved_cands = q_data.get("candidates", [])
                        saved_idx = q_data.get("processed_idx", 0)
                        if saved_idx < len(saved_cands):
                            approved_candidates = [
                                OutreachCandidate(
                                    title=c.get("title", ""),
                                    url=c.get("url", ""),
                                    domain=c.get("domain", ""),
                                    snippet=c.get("snippet", ""),
                                    score=float(c.get("score", 1.0) or 1.0),
                                )
                                for c in saved_cands[saved_idx:]
                                if c.get("domain") and c.get("domain") not in seen_domains and c.get("domain") not in EXTENDED_BLOCKED_DOMAINS
                            ]
                            if approved_candidates:
                                ACTIVE_SEARCH_TASKS[task_id]["message"] = (
                                    f"Возобновление: обход {len(approved_candidates)} сохраненных сайтов (0 ₽ в Яндекс)..."
                                )
                    except Exception as e:
                        logger.warning(f"Failed to read queue_file: {e}")

                if not approved_candidates:
                    # 1. Generate / Expand Query Matrix with distinct strategy per pass
                    if current_pass == 1:
                        queries, _ = await generate_search_queries_matrix(
                            active_prompt,
                            count=queries_target_count,
                            sys_settings=sys_settings,
                            is_extend=is_extend,
                            wave_index=wave_index,
                            existing_count=initial_collected,
                            executed_queries=executed_queries,
                        )
                    elif current_pass == 2:
                        regions_str = "Москва, Санкт-Петербург, Урал, Екатеринбург, Поволжье, Казань, Самара, Нижний Новгород, Сибирь, Новосибирск, Краснодар, Ростов-на-Дону, Владивосток, Хабаровск, Пермь, Воронеж, Уфа, Челябинск, Красноярск"
                        pass_prompt = f"{active_prompt}. Региональные коммерческие поставщики и дистрибьюторы: {regions_str}. Официальные дилеры, складские комплексы, оптовые отделы продаж и снабжения."
                        queries, _ = await generate_search_queries_matrix(
                            pass_prompt,
                            count=max(remaining_needed * 3, 70),
                            sys_settings=sys_settings,
                            is_extend=True,
                            wave_index=max(wave_index, 2),
                            existing_count=collected_count,
                            executed_queries=executed_queries,
                        )
                    elif current_pass == 3:
                        pass_prompt = f"{active_prompt}. Отраслевая номенклатура, комплексное снабжение предприятий, поставка оборудования и материалов по ТЗ, тендерный отдел поставщика, торговые дома, реестр контрактов."
                        queries, _ = await generate_search_queries_matrix(
                            pass_prompt,
                            count=max(remaining_needed * 3, 70),
                            sys_settings=sys_settings,
                            is_extend=True,
                            wave_index=max(wave_index, 3),
                            existing_count=collected_count,
                            executed_queries=executed_queries,
                        )
                    elif current_pass == 4:
                        pass_prompt = f"{active_prompt}. Федеральные поставщики, оптовая дистрибуция со склада, оптовый прайс-лист, отдел сбыта, коммерческие контракты, поставки для бюджетных и коммерческих заказчиков."
                        queries, _ = await generate_search_queries_matrix(
                            pass_prompt,
                            count=max(remaining_needed * 2, 60),
                            sys_settings=sys_settings,
                            is_extend=True,
                            wave_index=max(wave_index, 4),
                            existing_count=collected_count,
                            executed_queries=executed_queries,
                        )
                    else:
                        pass_prompt = f"{active_prompt}. Оптовые склады, торгово-производственные компании, операторы материально-технического снабжения, каталоги b2b продукции (проход {current_pass})."
                        queries, _ = await generate_search_queries_matrix(
                            pass_prompt,
                            count=max(remaining_needed * 2, 50),
                            sys_settings=sys_settings,
                            is_extend=True,
                            wave_index=max(wave_index, current_pass),
                            existing_count=collected_count,
                            executed_queries=executed_queries,
                        )

                    # Filter out already executed queries in this task session
                    queries = [q for q in queries if q.strip().lower() not in executed_queries]

                    ACTIVE_SEARCH_TASKS[task_id]["message"] = f"Проход {current_pass}/{max_passes}: сгенерировано {len(queries)} B2B запросов (цель: +{remaining_needed} лидов)..."

                    with session_factory() as db:
                        task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                        if task_rec:
                            task_rec.queries_count = (task_rec.queries_count or 0) + len(queries)
                            task_rec.llm_cost_rub = 0.0
                            task_rec.yandex_cost_rub = round(total_yandex_requests * yandex_unit_price, 2)
                            task_rec.total_cost_rub = task_rec.yandex_cost_rub
                            task_rec.message = ACTIVE_SEARCH_TASKS[task_id]["message"]
                            db.commit()

                    # Dynamic parameters for this pass: focus on top 40-60 highest-density results
                    if remaining_needed <= 120:
                        dynamic_max_pages = 2
                        dynamic_groups_on_page = 20
                        candidates_multiplier = 3.0
                    elif remaining_needed <= 500:
                        dynamic_max_pages = 3
                        dynamic_groups_on_page = 20
                        candidates_multiplier = 3.0
                    elif remaining_needed <= 1500:
                        dynamic_max_pages = 4
                        dynamic_groups_on_page = 20
                        candidates_multiplier = 3.0
                    else:
                        dynamic_max_pages = 5
                        dynamic_groups_on_page = 20
                        candidates_multiplier = 3.0

                    async def _fetch_q_candidates(q_text: str) -> tuple[list[OutreachCandidate], int]:
                        async with sem:
                            c_res = []
                            req_c = 0
                            if folder_id and api_key:
                                c_res, req_c = await fetch_yandex_search_candidates(
                                    q_text,
                                    folder_id,
                                    api_key,
                                    max_pages=dynamic_max_pages,
                                    groups_on_page=dynamic_groups_on_page,
                                )
                            if not c_res:
                                c_res = await fetch_ddgs_search_candidates(q_text, max_results=dynamic_groups_on_page * 2)
                            return c_res, req_c

                    raw_candidates: list[OutreachCandidate] = []
                    q_chunk_size = 4

                    for q_i in range(0, len(queries), q_chunk_size):
                        chunk = queries[q_i : q_i + q_chunk_size]
                        for q in chunk:
                            executed_queries.add(q.strip().lower())
                        if ACTIVE_SEARCH_TASKS.get(task_id, {}).get("pause"):
                            ACTIVE_SEARCH_TASKS[task_id]["status"] = "paused"
                            with session_factory() as db:
                                task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                                if task_rec:
                                    task_rec.status = "paused"
                                    task_rec.message = f"На паузе (собрано {wave_collected} из +{wave_target} контактов). Нажмите «Продолжить»"
                                    db.commit()
                            return

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

                        if len(raw_candidates) >= max(int(remaining_needed * candidates_multiplier), 120):
                            break

                        chunk = queries[q_i : q_i + q_chunk_size]
                        results_chunk = await asyncio.gather(*[_fetch_q_candidates(q) for q in chunk], return_exceptions=True)
                        for item in results_chunk:
                            if isinstance(item, tuple):
                                res_cands, req_c = item
                                total_yandex_requests += req_c
                                for c in res_cands:
                                    if c.domain and c.domain not in seen_domains and c.domain not in EXTENDED_BLOCKED_DOMAINS:
                                        seen_domains.add(c.domain)
                                        raw_candidates.append(c)

                        current_yandex_cost = round(total_yandex_requests * yandex_unit_price, 2)
                        wave_yandex_requests = max(0, total_yandex_requests - initial_yandex_requests)
                        wave_yandex_cost = round(wave_yandex_requests * yandex_unit_price, 2)

                        ACTIVE_SEARCH_TASKS[task_id]["yandex_requests"] = total_yandex_requests
                        ACTIVE_SEARCH_TASKS[task_id]["yandex_cost_rub"] = current_yandex_cost
                        ACTIVE_SEARCH_TASKS[task_id]["llm_cost_rub"] = 0.0
                        ACTIVE_SEARCH_TASKS[task_id]["total_cost_rub"] = current_yandex_cost
                        ACTIVE_SEARCH_TASKS[task_id]["wave_yandex_requests"] = wave_yandex_requests
                        ACTIVE_SEARCH_TASKS[task_id]["wave_cost_rub"] = wave_yandex_cost
                        ACTIVE_SEARCH_TASKS[task_id]["message"] = (
                            f"Проход {current_pass}: найдено {len(raw_candidates)} сайтов (Яндекс: {wave_yandex_cost:.2f} ₽)..."
                            if is_extend
                            else f"Проход {current_pass}: найдено {len(raw_candidates)} сайтов (Яндекс: {current_yandex_cost:.2f} ₽)..."
                        )

                        with session_factory() as db:
                            t_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                            if t_rec:
                                t_rec.yandex_requests = total_yandex_requests
                                t_rec.yandex_cost_rub = current_yandex_cost
                                t_rec.total_cost_rub = current_yandex_cost
                                t_rec.message = ACTIVE_SEARCH_TASKS[task_id]["message"]
                                try:
                                    w_list = json.loads(t_rec.waves_json) if t_rec.waves_json else []
                                    for w in w_list:
                                        if w.get("wave") == wave_index:
                                            w["yandex_requests"] = wave_yandex_requests
                                            w["yandex_cost_rub"] = wave_yandex_cost
                                            w["cost_rub"] = wave_yandex_cost
                                    t_rec.waves_json = json.dumps(w_list, ensure_ascii=False)
                                except Exception:
                                    pass
                                db.commit()

                    # 2. AI Reranking
                    if raw_candidates:
                        approved_candidates, _ = await ai_rerank_outreach_candidates(raw_candidates, active_prompt, sys_settings)
                    else:
                        approved_candidates = []

                    if not approved_candidates:
                        current_pass += 1
                        continue

                    # Persist found candidate sites immediately to disk
                    try:
                        with open(queue_file, "w", encoding="utf-8") as f:
                            json.dump({
                                "task_id": task_id,
                                "wave_index": wave_index,
                                "processed_idx": 0,
                                "candidates": [
                                    {"title": c.title, "url": c.url, "domain": c.domain, "snippet": c.snippet, "score": getattr(c, "score", 1.0)}
                                    for c in approved_candidates
                                ],
                                "created_at": now_utc().isoformat(),
                            }, f, ensure_ascii=False)
                    except Exception as e:
                        logger.warning(f"Failed to persist candidate queue: {e}")

                # 3. Deep Crawling & Verification
                batch_size = 10
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=3.0),
                    verify=False,
                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=30),
                ) as http_client:
                    for i in range(0, len(approved_candidates), batch_size):
                        if ACTIVE_SEARCH_TASKS.get(task_id, {}).get("pause"):
                            ACTIVE_SEARCH_TASKS[task_id]["status"] = "paused"
                            try:
                                if queue_file.exists():
                                    with open(queue_file, "r", encoding="utf-8") as f:
                                        q_data = json.load(f)
                                    q_data["processed_idx"] = q_data.get("processed_idx", 0) + i
                                    with open(queue_file, "w", encoding="utf-8") as f:
                                        json.dump(q_data, f, ensure_ascii=False)
                            except Exception:
                                pass
                            with session_factory() as db:
                                task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                                if task_rec:
                                    task_rec.status = "paused"
                                    rem = max(0, len(approved_candidates) - i)
                                    task_rec.message = f"На паузе (собрано {wave_collected} из +{wave_target} контактов, в очереди еще {rem} сайтов). Нажмите «Продолжить»"
                                    try:
                                        waves_list = json.loads(task_rec.waves_json) if task_rec.waves_json else []
                                        for w in waves_list:
                                            if w.get("wave") == wave_index:
                                                w["status"] = "paused"
                                                w["collected"] = wave_collected
                                                w["cost_rub"] = wave_yandex_cost
                                        task_rec.waves_json = json.dumps(waves_list, ensure_ascii=False)
                                    except Exception:
                                        pass
                                    db.commit()
                            return

                        if ACTIVE_SEARCH_TASKS.get(task_id, {}).get("cancel"):
                            ACTIVE_SEARCH_TASKS[task_id]["status"] = "cancelled"
                            try:
                                if queue_file.exists():
                                    with open(queue_file, "r", encoding="utf-8") as f:
                                        q_data = json.load(f)
                                    q_data["processed_idx"] = q_data.get("processed_idx", 0) + i
                                    with open(queue_file, "w", encoding="utf-8") as f:
                                        json.dump(q_data, f, ensure_ascii=False)
                            except Exception:
                                pass
                            with session_factory() as db:
                                task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                                if task_rec:
                                    task_rec.status = "cancelled"
                                    task_rec.completed_at = now_utc()
                                    task_rec.message = f"Остановлено (собрано {wave_collected} из +{wave_target} контактов). Можно продолжить."
                                    try:
                                        waves_list = json.loads(task_rec.waves_json) if task_rec.waves_json else []
                                        for w in waves_list:
                                            if w.get("wave") == wave_index:
                                                w["status"] = "cancelled"
                                                w["collected"] = wave_collected
                                                w["cost_rub"] = wave_yandex_cost
                                        task_rec.waves_json = json.dumps(waves_list, ensure_ascii=False)
                                    except Exception:
                                        pass
                                    db.commit()
                            return

                        batch = approved_candidates[i : i + batch_size]
                        async def _safe_crawl(cand):
                            try:
                                return await asyncio.wait_for(crawl_site_for_outreach_lead(cand, http_client), timeout=30.0)
                            except Exception:
                                return None
                        crawl_tasks = [_safe_crawl(cand) for cand in batch]
                        crawled_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)

                        async def _evaluate_and_enrich(crawled_item):
                            if not isinstance(crawled_item, dict) or not crawled_item.get("email"):
                                return None, 0.0
                            em_val = crawled_item["email"].lower().strip()
                            if em_val in existing_emails:
                                return None, 0.0
                            reviewed_lead, rev_cost = await ai_review_outreach_lead(crawled_item, active_prompt, sys_settings)
                            if not reviewed_lead:
                                return None, rev_cost
                            verified_lead = await enrich_lead_with_dadata(reviewed_lead)
                            if not verified_lead:
                                return None, rev_cost
                            return verified_lead, rev_cost

                        eval_tasks = [_evaluate_and_enrich(c) for c in crawled_results if isinstance(c, dict) and c.get("email")]
                        eval_results = await asyncio.gather(*eval_tasks, return_exceptions=True)

                        for res in eval_results:
                            if isinstance(res, tuple):
                                verified_lead, _ = res
                                if verified_lead and verified_lead.get("email"):
                                    em = verified_lead["email"].lower().strip()
                                    if em not in existing_emails:
                                        existing_emails.add(em)
                                        with session_factory() as db:
                                            lead = OutreachLead(
                                                task_id=task_id,
                                                wave_index=wave_index,
                                                email=em,
                                                company_name=verified_lead.get("company_name", ""),
                                                phone=verified_lead.get("phone", ""),
                                                website=verified_lead.get("website", ""),
                                                inn=verified_lead.get("inn", ""),
                                                category=active_prompt[:80],
                                                activity_profile=verified_lead.get("activity_profile", ""),
                                                relevance_score=verified_lead.get("relevance_score", 100),
                                                source="search",
                                                status="new",
                                                mx_valid=bool(verified_lead.get("mx_valid", True)),
                                            )
                                            db.add(lead)
                                            db.commit()
                                        collected_count += 1

                        current_scanned = scanned_so_far + min(i + batch_size, len(approved_candidates))
                        current_yandex_cost = round(total_yandex_requests * yandex_unit_price, 2)
                        wave_yandex_requests = max(0, total_yandex_requests - initial_yandex_requests)
                        wave_yandex_cost = round(wave_yandex_requests * yandex_unit_price, 2)
                        wave_collected = max(0, collected_count - initial_collected)
                        wave_target = extra_count if is_extend else target_count

                        ACTIVE_SEARCH_TASKS[task_id]["collected"] = collected_count
                        ACTIVE_SEARCH_TASKS[task_id]["scanned_sites"] = current_scanned
                        ACTIVE_SEARCH_TASKS[task_id]["yandex_requests"] = total_yandex_requests
                        ACTIVE_SEARCH_TASKS[task_id]["yandex_cost_rub"] = current_yandex_cost
                        ACTIVE_SEARCH_TASKS[task_id]["llm_cost_rub"] = 0.0
                        ACTIVE_SEARCH_TASKS[task_id]["total_cost_rub"] = current_yandex_cost
                        ACTIVE_SEARCH_TASKS[task_id]["wave_yandex_requests"] = wave_yandex_requests
                        ACTIVE_SEARCH_TASKS[task_id]["wave_cost_rub"] = wave_yandex_cost
                        ACTIVE_SEARCH_TASKS[task_id]["wave_collected"] = wave_collected
                        ACTIVE_SEARCH_TASKS[task_id]["wave_target"] = wave_target

                        if is_extend:
                            ACTIVE_SEARCH_TASKS[task_id]["message"] = (
                                f"Собрано в доборе {wave_collected}/{wave_target} контактов (Яндекс: {wave_yandex_cost:.2f} ₽)..."
                            )
                        else:
                            ACTIVE_SEARCH_TASKS[task_id]["message"] = (
                                f"Собрано {collected_count}/{target_count} целевых контактов (Яндекс: {current_yandex_cost:.2f} ₽)..."
                            )

                        with session_factory() as db:
                            task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                            if task_rec:
                                task_rec.collected_count = collected_count
                                task_rec.scanned_sites = current_scanned
                                task_rec.yandex_requests = total_yandex_requests
                                task_rec.yandex_cost_rub = current_yandex_cost
                                task_rec.llm_cost_rub = 0.0
                                task_rec.total_cost_rub = current_yandex_cost
                                task_rec.message = ACTIVE_SEARCH_TASKS[task_id]["message"]
                                try:
                                    waves_list = json.loads(task_rec.waves_json) if task_rec.waves_json else []
                                    for w in waves_list:
                                        if w.get("wave") == wave_index:
                                            w["collected"] = wave_collected
                                            w["cost_rub"] = wave_yandex_cost
                                            w["yandex_cost_rub"] = wave_yandex_cost
                                            w["yandex_requests"] = wave_yandex_requests
                                    task_rec.waves_json = json.dumps(waves_list, ensure_ascii=False)
                                except Exception:
                                    pass
                                db.commit()

                        # Update persistent queue progress on disk
                        try:
                            if queue_file.exists():
                                with open(queue_file, "r", encoding="utf-8") as f:
                                    q_data = json.load(f)
                                q_data["processed_idx"] = min(q_data.get("processed_idx", 0) + batch_size, len(q_data.get("candidates", [])))
                                with open(queue_file, "w", encoding="utf-8") as f:
                                    json.dump(q_data, f, ensure_ascii=False)
                        except Exception:
                            pass

                        if collected_count >= target_count:
                            try:
                                queue_file.unlink(missing_ok=True)
                            except Exception:
                                pass
                            break

                scanned_so_far += len(approved_candidates)
                current_pass += 1

            final_yandex_cost = round(total_yandex_requests * yandex_unit_price, 2)
            final_total_cost = final_yandex_cost

            ACTIVE_SEARCH_TASKS[task_id]["status"] = "completed"
            ACTIVE_SEARCH_TASKS[task_id]["yandex_cost_rub"] = final_yandex_cost
            ACTIVE_SEARCH_TASKS[task_id]["total_cost_rub"] = final_yandex_cost
            ACTIVE_SEARCH_TASKS[task_id]["llm_cost_rub"] = 0.0

            with session_factory() as db:
                actual_count = db.query(OutreachLead).filter(OutreachLead.task_id == task_id).count()
                task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                if task_rec:
                    task_rec.status = "completed"
                    task_rec.collected_count = actual_count
                    task_rec.scanned_sites = initial_scanned + len(approved_candidates)
                    task_rec.yandex_requests = total_yandex_requests
                    task_rec.yandex_cost_rub = final_yandex_cost
                    task_rec.llm_cost_rub = 0.0
                    task_rec.total_cost_rub = final_yandex_cost
                    wave_added = actual_count - initial_collected
                    is_full_target_reached = (wave_added >= wave_target) if is_extend else (actual_count >= target_count)
                    if is_full_target_reached:
                        task_rec.message = f"Готово! Цель выполнена на 100%: собрано +{wave_added} целевых контактов. Расход Яндекса: {final_yandex_cost:.2f} ₽ ({total_yandex_requests} зап.)."
                    else:
                        task_rec.message = f"Собрано +{wave_added} из +{wave_target} контактов. Расход Яндекса: {final_yandex_cost:.2f} ₽ ({total_yandex_requests} зап.)."
                    ACTIVE_SEARCH_TASKS[task_id]["message"] = task_rec.message

                    # Update wave records in waves_json
                    try:
                        waves_list = json.loads(task_rec.waves_json) if task_rec.waves_json else []
                    except Exception:
                        waves_list = []
                    
                    wave_added = actual_count - initial_collected
                    wave_reqs = max(0, total_yandex_requests - int(initial_yandex_cost / yandex_unit_price if yandex_unit_price > 0 else 0))
                    for w in waves_list:
                        if w.get("wave") == wave_index:
                            w["collected"] = max(w.get("collected", 0), wave_added)
                            w["status"] = "completed"
                            w["yandex_requests"] = wave_reqs
                            w["yandex_cost_rub"] = round(final_yandex_cost - initial_yandex_cost, 2)
                            w["cost_rub"] = round(final_yandex_cost - initial_yandex_cost, 2)
                    if waves_list:
                        task_rec.waves_json = json.dumps(waves_list, ensure_ascii=False)

                    db.commit()

        except Exception as e:
            logger.error(f"Search task {task_id} failed: {e}", exc_info=True)
            ACTIVE_SEARCH_TASKS[task_id]["status"] = "paused"
            ACTIVE_SEARCH_TASKS[task_id]["message"] = f"Сбой сбора: {str(e)[:80]}. Сайты сохранены. Нажмите «Продолжить»."
            with session_factory() as db:
                task_rec = db.query(OutreachSearchTask).filter(OutreachSearchTask.id == task_id).first()
                if task_rec:
                    task_rec.status = "paused"
                    task_rec.message = ACTIVE_SEARCH_TASKS[task_id]["message"]
                    try:
                        waves_list = json.loads(task_rec.waves_json) if task_rec.waves_json else []
                        for w in waves_list:
                            if w.get("wave") == wave_index:
                                w["status"] = "paused"
                        task_rec.waves_json = json.dumps(waves_list, ensure_ascii=False)
                    except Exception:
                        pass
                    db.commit()
