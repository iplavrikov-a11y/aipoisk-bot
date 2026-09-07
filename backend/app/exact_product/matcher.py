"""
Характеристики ТЗ -> Поиск товара по характеристикам -> Факты из документов -> Детерминированная матрица -> Решение.
Многодокументное слияние (Multi-Doc Fusion) и консенсус независимых источников.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin

from ..ai import call_llm
from ..models import SystemSettings, parse_json_dict, parse_json_list
from ..supplier_search import _search_with_yandex
from .fetcher import EXCLUDED_DOMAINS, fetch_batch_web_documents
from .minprom import (
    detect_minprom_registry_requirement,
    find_minprom_registry_matches_ai,
)
from .validation import (
    _compact,
    compute_spec_compliance,
    spec_status_key,
)

logger = logging.getLogger(__name__)

ProgressCallback = Any
_MAX_CANDIDATE_DOCS = 12
MAX_EXACT_POSITIONS_PER_JOB = 5
_MAX_FACTS_PER_DOC = 40
_CITY_SUFFIX_RE = re.compile(r"\s*[-–—]\s*[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s*$")
_LISTING_URL_HINT_RE = re.compile(r"(?i)(category|catalog|katalog|section|rubric|kollektsiya|kollektsii|tovary|shop|search|tag|brands?|producers?)")

_DOC_EXTRACT_PROMPT = """Ты — дословный экстрактор технических характеристик товара.
Документ (карточка товара / паспорт / каталог): «{title}»

Текст документа (паспорт / карточка товара / каталог):
{text}

Параметры технического задания:
{tz_params}

ЗАДАЧИ:
1. Выпиши из текста документа ЗНАЧЕНИЯ тех параметров ТЗ, которые прямо присутствуют в документе.
   - В качестве ключей JSON ("facts") используй ТОЧНЫЕ названия параметров из списка ТЗ.
   - Габариты сопоставляй по смыслу (высота, ширина, глубина).
   - Если в документе единица измерения отличается от ТЗ, укажи значение дословно с единицей из документа ('556 мм', '1.4 кВт'), но ключ сохрани ровно как в ТЗ!
   - Значение переноси ДОСЛОВНО, без "не менее/не более".
   - Если значения параметра в документе нет — параметр в facts не включай. НЕ ВЫДУМЫВАЙ.
2. Определи товар: бренд (марку изделия), точную модель, производителя — строго из заголовка/текста документа.
   - В качестве бренда и производителя указывай ТОЛЬКО марку самого изделия или завод-изготовитель. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО указывать названия интернет-магазинов или маркетплейсов. Если бренд или модель не названы, пиши пустую строку "".
3. Для описательных параметров ТЗ (состав, материал, свойства): переноси подтверждающие технологические свойства из текста.

Ответь СТРОГО в формате JSON:
{{
  "product_brand": "бренд изделия или пусто",
  "product_model": "модель изделия или пусто",
  "manufacturer": "завод-изготовитель или пусто",
  "is_relevant": true,
  "facts": {{"Параметр ТЗ": "дословное значение из документа"}}
}}
Если документ не про такой товар — верни {{"is_relevant": false, "facts": {{}}}}.
"""

_TZ_REQUIREMENTS_LLM_PROMPT = """Ты — извлекатель требований из технического задания.
Твоя задача — ТОЛЬКО ПЕРЕПИСАТЬ ХАРАКТЕРИСТИКИ ИЗ ТЕКСТА ТЗ.
КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО угадывать или определять товар по характеристикам.
Из текста спецификации выпиши ВСЕ проверяемые характеристики в виде "Параметр: требование".
Требование переноси дословно (диапазоны, значения, маркировки, перечисления через "или").
Не выдумывай параметры, которых нет в тексте.

Текст спецификации:
{spec}

Ответь СТРОГО JSON-списком:
[{{"param_name": "...", "tz_requirement": "..."}}]
"""

TZ_STRUCTURE_PROMPT = """Ты — аналитик технических заданий по государственным закупкам (44-ФЗ/223-ФЗ).
Твоя задача — ТОЛЬКО ПЕРЕПИСАТЬ ХАРАКТЕРИСТИКИ ИЗ ТЕКСТА ТЗ.
КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО пытаться угадать или понять, какой товар заложен в характеристиках!

Текст технического задания:
{spec}

ЗАДАЧИ:
1. "item_name" — общий предмет закупки в именительном падеже из текста ТЗ, БЕЗ городов/адресов/заказчиков.
2. "city" — населённый пункт/адрес из ТЗ, если указан (иначе "").
3. "positions" — РАЗБИЕНИЕ ТЗ НА ПОЗИЦИИ (товары). Каждый РАЗНЫЙ товар — отдельная позиция:
   - "name" — наименование позиции прямо из текста ТЗ;
   - "brand_hint" — бренд/марка, ТОЛЬКО если прямо написана словами в тексте ТЗ. Если нет — "";
   - "model_hint" — модель/артикул, ТОЛЬКО если прямо написана словами в тексте ТЗ. Если нет — "";
   - "manufacturer_hint" — завод-изготовитель, ТОЛЬКО если прямо назван словами в тексте ТЗ. Если нет — "";
   - "analogs" — список аналогов, ТОЛЬКО если в тексте ТЗ прямо перечислены конкретные аналоги: [{{"brand": "...", "model": "...", "manufacturer": "..."}}], иначе [];
   - "requirements" — ПОЛНЫЙ СПИСОК СВОИХ ХАРАКТЕРИСТИК позиции: [{{"param_name": "...", "tz_requirement": "..."}}]. Переноси дословно;
   - "search_queries" — 3-4 РЕАЛИСТИЧНЫХ поисковых запроса для Яндекса/Google, составленных специально под эту позицию с учётом ключевых характеристик и стандартов.

Ответь СТРОГО в формате JSON:
{{
  "item_name": "...",
  "city": "...",
  "positions": [
    {{
      "name": "...",
      "brand_hint": "",
      "model_hint": "",
      "manufacturer_hint": "",
      "analogs": [],
      "requirements": [{{"param_name": "...", "tz_requirement": "..."}}],
      "search_queries": ["запрос 1", "запрос 2", "запрос 3"]
    }}
  ]
}}
"""

_CHARACTERISTIC_QUERIES_LLM_PROMPT = """Ты — ведущий инженер по государственным закупкам (44-ФЗ/223-ФЗ).
Твоя задача — составить 4-6 высокоточных поисковых запросов для Яндекса, чтобы найти официальный паспорт изделия, карточку производителя или заводской каталог оборудования, удовлетворяющего техническому заданию.

Предмет закупки: «{item_name}»
Характеристики ТЗ:
{specs_text}
Подсказки ТЗ (если есть):
- Бренд: {brand_hint}
- Модель: {model_hint}
- Производитель: {manufacturer_hint}
- Возможные аналоги: {analogs_hint}

ТРЕБОВАНИЯ К СОСТАВЛЕНИЮ ЗАПРОСОВ:
1. Длина запроса от 3 до 7 слов. БЕЗ стоп-слов ('не менее', 'не более', 'в соответствии с').
2. Выдели ключевые дискриминаторы: тип, технологию, размеры, ГОСТ, ТУ, мощность.
3. Обязательно включи запрос на поиск первоисточника/паспорта: «[предмет] [тип] паспорт PDF» или «[предмет] [марка] завод производитель».
4. Ответ СТРОГО JSON-списком из 4-6 строк:
["запрос 1", "запрос 2", "запрос 3", "запрос 4"]"""

_AI_MATRIX_EVAL_PROMPT = """Ты — объективный инженер-эксперт по закупкам (44-ФЗ, 223-ФЗ).
Твоя задача — объективно оценить соответствие фактических характеристик найденного товара требованиям технического задания (ТЗ).

Товар: «{item_name}»
Модель: «{brand} {model}»

Требования ТЗ и факты, извлеченные из документации товара:
{specs_table}

ИНСТРУКЦИЯ ПО ОЦЕНКЕ:
1. "pass" (соответствует):
   - Фактическое значение удовлетворяет требованию ТЗ (с учетом размерностей и единиц: 25 мкм = 0.025 мм; 690 мм = 69 см; 1.9 кВт = 1900 Вт).
   - Заводской диапазон нарезки/выпуска перекрывает требование ТЗ.
   - Качественные параметры совпадают по смыслу и технологии (бесконтактный = сенсорный).
   - Улучшенные характеристики по ч. 2 ст. 33 44-ФЗ (степень защиты, надежность) без нарушения посадочных мест заказчика ("pass" с пометкой "Улучшенные характеристики").
2. "fail" (не соответствует):
   - Фактическое значение явно выходит за пределы допустимого диапазона ТЗ или прямо противоречит требованию.
3. "unknown" (не указано):
   - Если факт пустой или в тексте нет данных для проверки.

Формат ответа — строго JSON:
{{
  "evaluations": [
    {{
      "param_name": "...",
      "verdict": "pass" | "fail" | "unknown",
      "note": "Краткое инженерное пояснение (1 предложение)"
    }}
  ]
}}
"""

_MULTI_SOURCE_CONSENSUS_PROMPT = """Ты — эксперт по анализу оборудования и закупкам по 44-ФЗ.
Для товара «{item_name}» модели «{brand} {model}» собраны данные из НЕСКОЛЬКИХ независимых источников (дилеры, официальный сайт, PDF-паспорт):

{sources_block}

ТРЕБОВАНИЯ ТЗ И ПРЕДВАРИТЕЛЬНЫЕ ФАКТЫ:
{specs_table}

ЗАДАЧА (КРОСС-СВЕРКА И КОНСЕНСУС):
1. Объедини характеристики из разных источников в полную картину.
2. Сверь значения между источниками (консенсус):
   - Если источники называют одно значение — подтверди его, статус "pass" или "fail". В note укажи: "Подтверждено [источники]: [значение]".
   - Если на одном сайте опечатка, а паспорт завода говорит иное — зафиксируй консенсус по паспорту завода.
   - Данные официального PDF-паспорта завода всегда имеют наивысший приоритет.
3. Оценка вердикта: "pass", "fail", "unknown".

Формат ответа — строго валидный JSON:
{{
  "evaluations": [
    {{
      "param_name": "...",
      "consensus_fact": "...",
      "verdict": "pass" | "fail" | "unknown",
      "note": "Пояснение консенсуса и подтвердивших источников"
    }}
  ]
}}
"""

_ROUND2_QUERIES_LLM_PROMPT = """Ты — специалист по техническому подбору номенклатуры в закупках.
Предыдущий поиск по позиции «{item_name}» выявил следующие результаты:
{candidate_info}

Требования ТЗ к позиции:
{specs_text}

Твоя задача — составить 3-5 точных поисковых запросов для Яндекса (длиной 3-7 слов):
1. Если текущий кандидат имеет расхождения с ТЗ — сформируй запросы для поиска АЛЬТЕРНАТИВНОГО оборудования/производителя без расхождений.
2. Если текущий кандидат подходит — сформируй запросы для нахождения официального паспорта изделия, руководства по эксплуатации завода-изготовителя (паспорт PDF, руководство характеристики).

Ответь СТРОГО в формате JSON — список из 3-5 строк:
["запрос 1", "запрос 2", "запрос 3"]"""


def _clean_str(s: str) -> str:
    return re.sub(r"[^\w\s.-]", " ", str(s or "")).strip()


def _clean_org_name(name: str) -> str:
    return re.sub(r'(?i)\b(ооо|ао|пао|зао|гк|нпк|нпо|тд|«|»|")', "", str(name or "")).strip()


def _normalize_param_name(param: str) -> str:
    p = str(param or "").lower()
    p = re.sub(r"\s*\(.*?\)", "", p)
    p = re.sub(r"\s*,\s*[\w²³./%]+$", "", p)
    p = re.sub(r"[^\w\s]", " ", p)
    return re.sub(r"\s+", " ", p).strip()


def _compact_requirement(req: str, param: str = "") -> Optional[str]:
    s = re.sub(r"(?i)\b(не менее|не более|от|до|в пределах|должен быть|должна быть|согласно|по гост)\b", "", req)
    s = re.sub(r"[^\w\s.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s or len(s) < 2 or len(s) > 40:
        return None
    return s


def normalize_spec_text(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def normalize_model_label(brand: str, model: str) -> Tuple[str, str]:
    b = str(brand or "").strip()
    m = str(model or "").strip()
    if not b and m:
        parts = m.split()
        if len(parts) >= 2 and len(parts[0]) >= 2:
            b = parts[0]
            m = " ".join(parts[1:])
    return b, m


def _is_clean_maker_or_brand(val: Any) -> bool:
    s = str(val or "").strip().lower()
    if not s or len(s) < 2:
        return False
    if any(w in s for w in ("не указан", "пусто", "по документу", "none", "null", "товар", "россия", "китай", "импорт")):
        return False
    if any(shop in s for shop in ("всеинструменты", "твспб", "озон", "днс", "комус", "леруа")):
        return False
    return True


def _has_real_maker(c: Dict[str, Any], pos_hint: Optional[Dict[str, Any]] = None) -> bool:
    b = str(c.get("brand") or "").strip()
    mfr = str(c.get("manufacturer") or "").strip()
    if _is_clean_maker_or_brand(b) or _is_clean_maker_or_brand(mfr):
        return True
    if pos_hint and (_is_clean_maker_or_brand(pos_hint.get("brand")) or _is_clean_maker_or_brand(pos_hint.get("manufacturer"))):
        return True
    return False


def _resolve_real_maker_and_model(
    brand: str,
    manufacturer: str,
    model: str,
    doc: Optional[Dict[str, Any]] = None,
    fused_docs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, str, str]:
    b = str(brand or "").strip()
    mfr = str(manufacturer or "").strip()
    m = str(model or "").strip()

    if not b and mfr:
        b = mfr
    if not mfr and b:
        mfr = b

    # Очистка названий магазинов
    for shop in ("всеинструменты", "твспб", "dns", "ozon", "санова", "климбит"):
        if shop in b.lower():
            b = ""
        if shop in mfr.lower():
            mfr = ""

    return b, mfr, m


def _is_model_grounded_in_doc(model: str, title: str, text: str) -> bool:
    m_str = str(model or "").strip()
    if not m_str or len(_compact(m_str)) < 2:
        return False

    hay = _compact(f"{title} {text[:20000]}")
    m_comp = _compact(m_str)
    if m_comp in hay:
        return True

    clean_m = "".join(c if c.isalnum() else " " for c in m_str).split()
    meaningful = [w for w in clean_m if len(w) >= 2 and _compact(w) not in ("для", "рук", "гост", "товар", "шт")]
    if meaningful:
        matched = sum(1 for w in meaningful if _compact(w) in hay)
        if matched == len(meaningful) or (len(meaningful) >= 2 and matched / len(meaningful) >= 0.5):
            return True

    return False


def _is_brand_grounded_in_doc(brand: str, title: str, text: str) -> bool:
    b_str = str(brand or "").strip()
    if not b_str or len(_compact(b_str)) < 3:
        return True
    hay = _compact(f"{title} {text[:20000]}")
    if _compact(b_str) in hay:
        return True

    clean_words = "".join(c if c.isalnum() else " " for c in b_str).split()
    org_prefixes = {"ооо", "ао", "пао", "зао", "гк", "нпк", "нпо", "тд", "завод", "фабрика"}
    words = [w for w in clean_words if len(w) >= 3 and w.lower() not in org_prefixes]
    if words and any(_compact(w) in hay for w in words):
        return True
    return False


def _rank_search_candidates(
    candidates: list[Any],
    target_keywords: list[str],
    negative_keywords: list[str],
) -> list[str]:
    scored: list[tuple[float, str]] = []
    for c in candidates:
        url = getattr(c, "url", "") or (c.get("url") if isinstance(c, dict) else "") or ""
        if not url or not url.startswith("http"):
            continue
        title = getattr(c, "title", "") or (c.get("title") if isinstance(c, dict) else "") or ""
        snippet = getattr(c, "snippet", "") or (c.get("snippet") if isinstance(c, dict) else "") or ""
        text = f"{title} {snippet} {url}".lower()

        score = 0.0
        for kw in target_keywords:
            kw_clean = kw.lower().strip()
            if kw_clean and len(kw_clean) >= 3 and kw_clean in text:
                score += 3.0

        for nkw in negative_keywords:
            nkw_clean = nkw.lower().strip()
            if nkw_clean and len(nkw_clean) >= 3 and nkw_clean in text:
                score -= 15.0

        if ".pdf" in url.lower() or "pasport" in text or "паспорт" in text or "руководство" in text:
            score += 4.0

        if any(bad in url.lower() for bad in ["zakupki.gov.ru", "synapsenet.ru", "tenderplan.ru", "rostender.info", "bicotender.ru"]):
            score -= 5.0

        scored.append((score, url))

    scored.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    ordered_urls: list[str] = []
    for _, u in scored:
        if u not in seen:
            seen.add(u)
            ordered_urls.append(u)
    return ordered_urls


async def _fetch_search_results_for_specs(
    settings: SystemSettings,
    query: str | list,
    max_results: int = 6,
) -> list:
    if isinstance(query, (list, tuple)):
        query = " ".join(str(q).strip() for q in query if str(q).strip())
    query = str(query or "").strip()
    if not query:
        return []
    try:
        candidates, _ = await _search_with_yandex(
            settings,
            [query],
            max_results=max_results,
            expand_queries=False,
            max_pages_per_query=1,
        )
        return candidates
    except Exception as exc:
        logger.debug("search_specs_failed: %s", exc)
        return []


async def parse_tz_structure(
    settings: SystemSettings,
    spec_text: str,
) -> Optional[Dict[str, Any]]:
    if not spec_text or len(spec_text.strip()) < 30:
        return None
    try:
        raw = await call_llm(
            settings,
            prompt=TZ_STRUCTURE_PROMPT.format(spec=str(spec_text)[:16000]),
            system_prompt=(
                "Ты — аккуратный аналитик технических заданий. Твоя задача — ТОЛЬКО переписать характеристики из ТЗ. "
                "Строго запрещено угадывать товар или марку по характеристикам. "
                "Если точный бренд или завод прямо словами не написан в строке таблицы ТЗ заказчиком — оставляй поля пустыми. "
                "Отвечай только валидным JSON."
            ),
            json_mode=True,
            tier="primary",
            routing_key="procurement_brand_detection",
        )
    except Exception as exc:
        logger.debug("tz_structure_llm_failed: %s", exc)
        return None

    data = parse_json_dict(raw)
    if not isinstance(data, dict):
        return None

    spec_compact = _compact(spec_text)

    def _is_grounded_text(val: str) -> bool:
        if not val or len(val.strip()) < 2:
            return False
        return _compact(val) in spec_compact

    positions: List[Dict[str, Any]] = []
    for pos in data.get("positions") or []:
        if not isinstance(pos, dict):
            continue
        name = str(pos.get("name") or "").strip()[:120]
        reqs: List[Dict[str, str]] = []
        seen = set()
        for item in pos.get("requirements") or []:
            if not isinstance(item, dict):
                continue
            p = str(item.get("param_name") or "").strip()
            t = str(item.get("tz_requirement") or "").strip()
            if not p or not t or len(p) > 120 or len(t) > 1000:
                continue
            p_key = p.lower()
            if p_key in seen:
                continue
            seen.add(p_key)
            reqs.append({"param_name": p, "tz_requirement": t})

        brand_h = str(pos.get("brand_hint") or "").strip()
        model_h = str(pos.get("model_hint") or "").strip()
        mfr_h = str(pos.get("manufacturer_hint") or "").strip()

        if brand_h and not _is_grounded_text(brand_h):
            brand_h = ""
        if model_h and not _is_grounded_text(model_h):
            model_h = ""
        if mfr_h and not _is_grounded_text(mfr_h):
            mfr_h = ""

        analogs_raw = pos.get("analogs") or []
        grounded_analogs: List[Dict[str, str]] = []
        if isinstance(analogs_raw, list):
            for a in analogs_raw:
                if isinstance(a, dict):
                    ab = str(a.get("brand") or "").strip()
                    am = str(a.get("model") or "").strip()
                    af = str(a.get("manufacturer") or "").strip()
                    if (ab and _is_grounded_text(ab)) or (am and _is_grounded_text(am)) or (af and _is_grounded_text(af)):
                        grounded_analogs.append({"brand": ab, "model": am, "manufacturer": af})

        queries = [str(q).strip() for q in (pos.get("search_queries") or []) if isinstance(q, str) and len(str(q).strip()) >= 4]

        if name and reqs:
            positions.append({
                "name": name,
                "requirements": reqs,
                "brand_hint": brand_h,
                "model_hint": model_h,
                "manufacturer_hint": mfr_h,
                "analogs": grounded_analogs,
                "search_queries": queries,
            })

    if not positions:
        return None

    return {
        "item_name": str(data.get("item_name") or "").strip(),
        "city": str(data.get("city") or "").strip(),
        "positions": positions[:MAX_EXACT_POSITIONS_PER_JOB],
    }


def extract_tz_requirements_regex(spec_text: str) -> List[Dict[str, str]]:
    if not spec_text:
        return []
    reqs: List[Dict[str, str]] = []
    seen = set()

    def add_pair(param: str, req: str) -> None:
        param = param.strip(" \t-–—•")
        req = req.strip()
        param_l = param.lower()
        if not param or not req or len(param_l) < 3 or len(req) < 2:
            return
        if param_l in seen:
            return
        seen.add(param_l)
        reqs.append({"param_name": param, "tz_requirement": req})

    colon_pattern = re.compile(
        r"(?:^|[;\n\r]|(?<=\.)\s)\s*([A-Za-zА-ЯЁа-яё0-9][^:;.\n\r]{2,70}?)\s*:\s*([^:;\n\r]{2,200}?)(?=[;\n\r]|$)",
        re.MULTILINE,
    )
    for m in colon_pattern.finditer(spec_text):
        add_pair(m.group(1), m.group(2))
        if len(reqs) >= 25:
            break

    if len(reqs) < 25:
        dash_pattern = re.compile(
            r"(?:^|[;\n\r]|(?<=\.)\s)\s*([A-Za-zА-ЯЁа-яё][\wа-яё \t]{4,60}?)\s*[–—-]\s*((?=[^;\n\r]*\d)[^;\n\r]{2,120}?)(?=[;\n\r]|$)",
            re.MULTILINE,
        )
        for m in dash_pattern.finditer(spec_text):
            add_pair(m.group(1), m.group(2))
            if len(reqs) >= 25:
                break

    return reqs


async def extract_tz_requirements(
    settings: SystemSettings,
    spec_text: str,
) -> List[Dict[str, str]]:
    if not spec_text:
        return []

    try:
        tz_struct = await parse_tz_structure(settings, spec_text)
        if tz_struct and tz_struct.get("positions"):
            all_reqs = []
            seen = set()
            for pos in tz_struct["positions"]:
                for r in pos.get("requirements") or []:
                    pk = str(r.get("param_name") or "").strip().lower()
                    if pk and pk not in seen:
                        seen.add(pk)
                        all_reqs.append(r)
            if all_reqs:
                return all_reqs
    except Exception as exc:
        logger.debug("extract_tz_via_struct_failed: %s", exc)

    try:
        raw = await call_llm(
            settings,
            prompt=_TZ_REQUIREMENTS_LLM_PROMPT.format(spec=str(spec_text or "")[:12000]),
            system_prompt="Ты извлекаешь требования ТЗ дословно, без выдумывания. Отвечай только валидным JSON-списком.",
            json_mode=True,
            tier="light",
            routing_key="procurement_brand_detection",
        )
        if raw:
            data = parse_json_list(raw)
            if isinstance(data, list) and data:
                reqs = []
                seen = set()
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    p = str(item.get("param_name") or "").strip()
                    t = str(item.get("tz_requirement") or "").strip()
                    if p and t and p.lower() not in seen:
                        seen.add(p.lower())
                        reqs.append({"param_name": p, "tz_requirement": t})
                if reqs:
                    return reqs
    except Exception as exc:
        logger.debug("tz_requirements_llm_failed: %s", exc)

    return extract_tz_requirements_regex(spec_text)


def extract_existing_tz_brand_hints(text: str, parse_under_table_blocks: bool = True) -> Dict[str, Dict[str, Any]]:
    t = str(text or "").strip()
    if not t:
        return {}

    hints: Dict[str, Dict[str, Any]] = {}
    if parse_under_table_blocks:
        pos_blocks = re.split(r'(?:^|\n)[ \t]*(?:[-*•]\s*)?(?:\*\*)?Для позиции\s+[«"\'`]([^»"\'`\n]+)[»"\'`]:?(?:\*\*)?', t)
        if len(pos_blocks) > 1:
            for i in range(1, len(pos_blocks), 2):
                pos_name = pos_blocks[i].strip()
                block_body = pos_blocks[i + 1] if i + 1 < len(pos_blocks) else ""

                main_m = re.search(r'(?:[-*•]\s*)?(?:\*\*)?Точный товар:?(?:\*\*)?\s*([^\n]+)', block_body)
                main_desc = main_m.group(1).strip() if main_m else ""

                brand, model, mfr = "", "", ""
                if main_desc:
                    mod_m = re.search(r'модель\s+\*\*([^*]+)\*\*|модель\s+([^,]+)', main_desc, re.IGNORECASE)
                    if mod_m:
                        model = (mod_m.group(1) or mod_m.group(2) or "").strip()
                    mfr_m = re.search(r'производитель\s+\*\*([^*]+)\*\*|производитель\s+([^,]+)', main_desc, re.IGNORECASE)
                    if mfr_m:
                        mfr = (mfr_m.group(1) or mfr_m.group(2) or "").strip()
                    b_m = re.search(r'^\s*\*\*([^*]+)\*\*', main_desc)
                    if b_m:
                        brand = b_m.group(1).strip()
                    elif not brand:
                        first_part = re.split(r',|\bмодель\b|\bпроизводитель\b', main_desc)[0].strip(' *')
                        if first_part and len(first_part) > 1:
                            brand = first_part

                brand, mfr, model = _resolve_real_maker_and_model(brand, mfr, model)

                analogs = []
                for alt_m in re.finditer(r'(?:[-*•]\s*)?(?:\*\*)?Аналог\s*\d*:?(?:\*\*)?\s*([^\n]+)', block_body):
                    alt_desc = alt_m.group(1).strip()
                    a_brand, a_model, a_mfr = "", "", ""
                    a_mod_m = re.search(r'модель\s+\*\*([^*]+)\*\*|модель\s+([^,]+)', alt_desc, re.IGNORECASE)
                    if a_mod_m:
                        a_model = (a_mod_m.group(1) or a_mod_m.group(2) or "").strip()
                    a_mfr_m = re.search(r'производитель\s+\*\*([^*]+)\*\*|производитель\s+([^,]+)', alt_desc, re.IGNORECASE)
                    if a_mfr_m:
                        a_mfr = (a_mfr_m.group(1) or a_mfr_m.group(2) or "").strip()
                    a_b_m = re.search(r'^\s*\*\*([^*]+)\*\*', alt_desc)
                    if a_b_m:
                        a_brand = a_b_m.group(1).strip()
                    else:
                        a_first = re.split(r',|\bмодель\b|\bпроизводитель\b', alt_desc)[0].strip(' *')
                        if a_first and len(a_first) > 1:
                            a_brand = a_first

                    a_brand, a_mfr, a_model = _resolve_real_maker_and_model(a_brand, a_mfr, a_model)
                    if a_brand and a_model:
                        analogs.append({"brand": a_brand, "model": a_model, "manufacturer": a_mfr or a_brand})

                if brand or model or mfr or analogs:
                    hints[pos_name.lower()] = {
                        "pos_name": pos_name,
                        "brand": brand,
                        "model": model,
                        "manufacturer": mfr,
                        "analogs": analogs,
                    }

    return hints


def find_hint_for_position(hints: Dict[str, Dict[str, Any]], pos_name: str) -> Optional[Dict[str, Any]]:
    if not hints:
        return None
    pos_lower = str(pos_name or "").lower().strip()
    if pos_lower in hints:
        return hints[pos_lower]
    for k, v in hints.items():
        if k != "default" and (k in pos_lower or pos_lower in k):
            return v
    if len(hints) == 1 and "default" not in hints:
        return next(iter(hints.values()))
    return hints.get("default")


async def extract_doc_facts(
    settings: SystemSettings,
    doc: Dict[str, Any],
    requirements: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    text = str(doc.get("text") or "")
    title = str(doc.get("title") or "")
    if len(text.strip()) < 40:
        return None

    tz_params = "\n".join(f"- {r['param_name']}: {r['tz_requirement']}" for r in requirements)
    try:
        raw = await call_llm(
            settings,
            prompt=_DOC_EXTRACT_PROMPT.format(
                title=title[:200],
                text=text[:25000],
                tz_params=tz_params[:8000],
            ),
            system_prompt="Ты — дословный экстрактор характеристик. Категорически запрещено выдумывать значения. Отвечай только валидным JSON.",
            json_mode=True,
            tier="light",
            routing_key="procurement_brand_detection",
        )
    except Exception as exc:
        logger.debug("doc_fact_extract_failed: %s", exc)
        return None

    data = parse_json_dict(raw)
    if not isinstance(data, dict) or data.get("is_relevant") is False:
        return None

    raw_facts = data.get("facts")
    if not isinstance(raw_facts, dict):
        return None

    facts: Dict[str, str] = {}
    exact_map = {r["param_name"].strip().lower(): r["param_name"] for r in requirements}
    norm_map = {_normalize_param_name(r["param_name"]): r["param_name"] for r in requirements}

    for key, value in list(raw_facts.items())[:_MAX_FACTS_PER_DOC]:
        p_name = str(key or "").strip()
        val = str(value or "").strip()
        if not p_name or not val or len(val) > 120:
            continue
        canonical_param = exact_map.get(p_name.lower())
        if not canonical_param:
            norm_key = _normalize_param_name(p_name)
            canonical_param = norm_map.get(norm_key)
        if not canonical_param:
            continue
        facts[canonical_param] = val

    brand = str(data.get("product_brand") or "").strip()
    model = str(data.get("product_model") or "").strip()
    manufacturer = str(data.get("manufacturer") or "").strip()

    brand, manufacturer, model = _resolve_real_maker_and_model(brand, manufacturer, model, doc=doc)
    if not brand and manufacturer:
        brand = manufacturer
    if not manufacturer and brand:
        manufacturer = brand

    if not _is_model_grounded_in_doc(model, title, text):
        return None
    if brand and not _is_brand_grounded_in_doc(brand, title, text):
        return None
    if not facts:
        return None

    return {
        "brand": brand,
        "model": model,
        "manufacturer": manufacturer or brand,
        "facts": facts,
    }


def _find_fact_for_param(facts: Dict[str, str], param_name: str) -> str:
    if not facts or not param_name:
        return ""
    if param_name in facts:
        return str(facts[param_name] or "")
    p_clean = param_name.strip().lower()
    for k, v in facts.items():
        if k.strip().lower() == p_clean:
            return str(v or "")
    p_simple = p_clean.replace("²", "2").replace("³", "3")
    for k, v in facts.items():
        k_clean = k.strip().lower().replace("²", "2").replace("³", "3")
        if k_clean == p_simple:
            return str(v or "")
    p_alnum = "".join(c for c in p_simple if c.isalnum() or c.isspace()).strip()
    for k, v in facts.items():
        k_alnum = "".join(c for c in k.strip().lower().replace("²", "2").replace("³", "3") if c.isalnum() or c.isspace()).strip()
        if p_alnum and k_alnum and (p_alnum == k_alnum or p_alnum in k_alnum or k_alnum in p_alnum):
            return str(v or "")
    return ""


def build_candidate_matrix(
    candidate: Dict[str, Any],
    requirements: List[Dict[str, str]],
) -> Dict[str, Any]:
    facts = candidate.get("facts") or {}
    rows = []
    passes = 0
    fails = 0
    unknowns = 0

    for req in requirements:
        p_name = req["param_name"]
        tz_val = req["tz_requirement"]
        fact_val = _find_fact_for_param(facts, p_name)

        if not fact_val or "не указано" in fact_val.lower():
            verdict = "unknown"
            note = "В открытой документации не указано"
            unknowns += 1
        else:
            verdict = "unknown"
            note = "Требуется семантическая сверка"
            unknowns += 1

        rows.append({
            "param_name": p_name,
            "tz_requirement": tz_val,
            "fact": fact_val,
            "verdict": verdict,
            "note": note,
        })

    total = len(requirements) or 1
    return {
        "rows": rows,
        "passes": passes,
        "fails": fails,
        "unknowns": unknowns,
        "coverage": round(passes / total, 2),
        "coverage_with_unknowns": round((passes + 0.5 * unknowns) / total, 2),
    }


async def enrich_matrix_with_ai(
    settings: SystemSettings,
    matrix: Dict[str, Any],
    requirements: List[Dict[str, str]],
    brand: str = "",
    model: str = "",
    item_name: str = "",
) -> Dict[str, Any]:
    rows = matrix.get("rows") or []
    needs_ai = []
    is_tender_ev = bool(matrix.get("is_tender_evidence"))
    for r in rows:
        f = str(r.get("fact") or "").strip()
        if (f and "не указано" not in f.lower()) or is_tender_ev:
            if r.get("verdict") in ("unknown", "fail"):
                needs_ai.append(r)

    if not needs_ai:
        return matrix

    specs_lines = []
    for r in needs_ai:
        fact_display = r["fact"] if r["fact"] else "По тексту закупочной документации"
        specs_lines.append(f"- Параметр: «{r['param_name']}» | Требование ТЗ: «{r['tz_requirement']}» | Факт из документа: «{fact_display}»")
    specs_table = "\n".join(specs_lines)[:6000]

    try:
        raw = await call_llm(
            settings,
            prompt=_AI_MATRIX_EVAL_PROMPT.format(
                item_name=item_name or "Товар",
                brand=brand or "Производитель",
                model=model or "",
                specs_table=specs_table,
            ),
            system_prompt="Ты — объективный инженер-эксперт по закупкам. Оценивай техническое соответствие строго по смыслу и ГОСТам. Отвечай только валидным JSON.",
            json_mode=True,
            tier="light",
            routing_key="procurement_brand_detection",
        )
        data = parse_json_dict(raw)
        evals = (data or {}).get("evaluations") or [] if isinstance(data, dict) else []
        eval_map = {str(e.get("param_name") or "").strip().lower(): e for e in evals if isinstance(e, dict)}

        passes = matrix.get("passes", 0)
        fails = matrix.get("fails", 0)
        unknowns = matrix.get("unknowns", 0)

        for r in rows:
            pk = str(r.get("param_name") or "").strip().lower()
            ev = eval_map.get(pk)
            if not ev:
                for k, v in eval_map.items():
                    if k in pk or pk in k:
                        ev = v
                        break
            if ev:
                new_v = str(ev.get("verdict") or "").strip().lower()
                new_note = str(ev.get("note") or "").strip()
                old_v = r.get("verdict")
                if new_v in ("pass", "fail") and new_v != old_v:
                    if old_v == "pass": passes -= 1
                    elif old_v == "fail": fails -= 1
                    elif old_v == "unknown": unknowns -= 1

                    if new_v == "pass": passes += 1
                    elif new_v == "fail": fails += 1
                    else: unknowns += 1

                    r["verdict"] = new_v
                    if new_note:
                        r["note"] = new_note

        total = len(requirements) or 1
        matrix["passes"] = max(0, passes)
        matrix["fails"] = max(0, fails)
        matrix["unknowns"] = max(0, unknowns)
        matrix["coverage"] = round(matrix["passes"] / total, 2)
        matrix["coverage_with_unknowns"] = round((matrix["passes"] + 0.5 * matrix["unknowns"]) / total, 2)
    except Exception as exc:
        logger.debug("enrich_matrix_with_ai_failed: %s", exc)

    return matrix


async def expand_candidate_sources_ai(
    settings: SystemSettings,
    candidate: Dict[str, Any],
    pos_name: str,
    seen_urls: set,
    requirements: List[Dict[str, str]],
    max_sources: int = 4,
) -> Dict[str, Any]:
    brand = str(candidate.get("brand") or candidate.get("manufacturer") or "").strip()
    manufacturer = str(candidate.get("manufacturer") or brand).strip()
    model = str(candidate.get("model") or "").strip()
    bm_lower = (brand + " " + model + " " + manufacturer).lower()

    if not brand or not model or len(brand) < 2 or len(model) < 2:
        return candidate
    if any(w in bm_lower for w in ("не указан", "по документу", "пусто", "none", "null", "товар", "россия", "китай")):
        return candidate

    fused_docs = candidate.setdefault("fused_docs", [candidate["doc"]])
    existing_domains = {str(d.get("domain") or "").lower() for d in fused_docs if d.get("domain")}
    if len(existing_domains) >= max_sources:
        return candidate

    q_specs = f"{brand} {model} характеристики"
    q_passport = f"{brand} {model} паспорт PDF"

    raw_results = []
    for q in (q_specs, q_passport):
        try:
            r = await _fetch_search_results_for_specs(settings, q, max_results=6)
            raw_results.extend(r or [])
        except Exception:
            pass

    new_urls = []
    for res in raw_results:
        u = getattr(res, "url", "") or (res.get("url") if isinstance(res, dict) else "")
        if u and u.startswith("http") and u not in seen_urls:
            dom = getattr(res, "domain", "") or ""
            if dom and dom.lower() not in existing_domains and dom.lower() not in EXCLUDED_DOMAINS:
                new_urls.append(u)
                seen_urls.add(u)
                existing_domains.add(dom.lower())

    if new_urls:
        new_docs = await fetch_batch_web_documents(new_urls[:max_sources], max_docs=max_sources)
        for nd in new_docs:
            if isinstance(nd, dict) and nd.get("text"):
                fused_docs.append(nd)
                ext = await extract_doc_facts(settings, nd, requirements)
                if ext and ext.get("facts"):
                    for p_name, p_val in ext["facts"].items():
                        if p_val and p_name not in candidate.setdefault("facts", {}):
                            candidate["facts"][p_name] = p_val
                            candidate.setdefault("fact_sources", {})[p_name] = nd

    return candidate


async def enrich_candidate_multi_source_consensus_ai(
    settings: SystemSettings,
    candidate: Dict[str, Any],
    requirements: List[Dict[str, str]],
    item_name: str,
) -> Dict[str, Any]:
    fused_docs = candidate.get("fused_docs") or [candidate.get("doc")]
    if len(fused_docs) < 2:
        return candidate.get("matrix", {})

    brand = candidate.get("brand") or ""
    model = candidate.get("model") or ""
    matrix = candidate.get("matrix") or {}
    rows = matrix.get("rows") or []

    sources_lines = []
    for idx, d in enumerate(fused_docs[:4], 1):
        dom = d.get("domain") or d.get("url") or f"Источник {idx}"
        dt = d.get("type") or "веб-страница"
        txt_snippet = str(d.get("text") or "")[:2500]
        sources_lines.append(f"=== ИСТОЧНИК #{idx} [{dom}, тип: {dt}] ===\n{txt_snippet}\n")
    sources_block = "\n".join(sources_lines)

    specs_lines = []
    for r in rows:
        specs_lines.append(f"- «{r['param_name']}» | Требование ТЗ: «{r['tz_requirement']}» | Текущий факт: «{r.get('fact') or 'не найден'}»")
    specs_table = "\n".join(specs_lines)

    try:
        raw = await call_llm(
            settings,
            prompt=_MULTI_SOURCE_CONSENSUS_PROMPT.format(
                item_name=item_name,
                brand=brand,
                model=model,
                sources_block=sources_block,
                specs_table=specs_table,
            ),
            system_prompt="Ты эксперт по анализу промышленного оборудования. Проверяй консенсус по первоисточникам завода. Отвечай только валидным JSON.",
            json_mode=True,
            tier="light",
            routing_key="procurement_brand_detection",
        )
        data = parse_json_dict(raw)
        evals = (data or {}).get("evaluations") or [] if isinstance(data, dict) else []
        eval_map = {str(e.get("param_name") or "").strip().lower(): e for e in evals if isinstance(e, dict)}

        passes = matrix.get("passes", 0)
        fails = matrix.get("fails", 0)
        unknowns = matrix.get("unknowns", 0)

        for r in rows:
            pk = str(r.get("param_name") or "").strip().lower()
            ev = eval_map.get(pk)
            if ev:
                new_v = str(ev.get("verdict") or "").strip().lower()
                c_fact = str(ev.get("consensus_fact") or "").strip()
                note = str(ev.get("note") or "").strip()
                if c_fact and ("не указано" not in c_fact.lower()):
                    r["fact"] = c_fact

                old_v = r.get("verdict")
                if new_v in ("pass", "fail") and new_v != old_v:
                    if old_v == "pass": passes -= 1
                    elif old_v == "fail": fails -= 1
                    elif old_v == "unknown": unknowns -= 1

                    if new_v == "pass": passes += 1
                    elif new_v == "fail": fails += 1
                    else: unknowns += 1

                    r["verdict"] = new_v
                if note:
                    r["consensus_note"] = note

        total = len(requirements) or 1
        matrix["passes"] = max(0, passes)
        matrix["fails"] = max(0, fails)
        matrix["unknowns"] = max(0, unknowns)
        matrix["coverage"] = round(matrix["passes"] / total, 2)
        matrix["coverage_with_unknowns"] = round((matrix["passes"] + 0.5 * matrix["unknowns"]) / total, 2)
    except Exception as exc:
        logger.debug("multi_source_consensus_ai_failed: %s", exc)

    return matrix


def _normalize_model_for_exact_match(m: str) -> str:
    m_clean = str(m or "").lower()
    for w in ("silver", "white", "black", "белый", "серебристый", "черный", "матовый", "глянцевый"):
        m_clean = m_clean.replace(w, "")
    return _compact(m_clean)


def _is_concrete_specific_model(m_raw: str, generic_words: Set[str]) -> bool:
    m_comp = _compact(m_raw).lower()
    if not m_comp or len(m_comp) < 3 or m_comp in generic_words:
        return False
    m_clean = str(m_raw or "").lower()
    has_digits = any(c.isdigit() for c in m_clean)
    has_model_code = any(sep in m_clean for sep in ("-", "/", "_", "\\"))
    has_dimensions = any(sep in m_clean for sep in ("x", "х", "*", "×")) and has_digits
    return has_digits or has_model_code or has_dimensions


def fuse_candidates_by_model(
    candidates: List[Dict[str, Any]],
    requirements: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    generic_words = {
        "неуказан", "россия", "рф", "гост", "товар", "подокументу", "модельподокументу",
        "бумага", "канат", "паспорт", "сертификат", "каталог"
    }

    domain_clusters: Dict[str, List[Dict[str, Any]]] = {}
    pdf_candidates: List[Dict[str, Any]] = []

    for idx, c in enumerate(candidates):
        d = c.get("doc") or {}
        d_type = str(d.get("type") or "").lower()
        d_url = str(d.get("url") or "").lower()
        is_pdf = (d_type == "pdf") or d_url.endswith(".pdf")
        domain = str(d.get("domain") or "").strip().lower()

        b = _compact(c.get("brand") or "").lower()
        m = _compact(c.get("model") or "").lower()

        is_specific_brand = bool(b and len(b) >= 3 and b not in generic_words)
        is_specific_model = bool(m and len(m) >= 3 and m not in generic_words)

        if is_pdf:
            pdf_candidates.append(c)
        else:
            if domain:
                if is_specific_brand and is_specific_model:
                    key = f"{domain}_{b}_{m}"
                else:
                    key = f"{domain}_{idx}"
            else:
                key = f"raw_{idx}"
            domain_clusters.setdefault(key, []).append(c)

    web_fused: List[Dict[str, Any]] = []
    for key, group in domain_clusters.items():
        if len(group) == 1:
            c = dict(group[0])
            c["fused_docs"] = [c["doc"]]
            c["fact_sources"] = {k: c["doc"] for k in (c.get("facts") or {})}
            web_fused.append(c)
        else:
            merged_facts: Dict[str, str] = {}
            fact_sources: Dict[str, Dict[str, Any]] = {}
            all_docs: List[Dict[str, Any]] = []
            seen_urls = set()

            sorted_group = sorted(group, key=lambda item: -len(item.get("facts") or {}))
            for c in sorted_group:
                d = c.get("doc") or {}
                d_url = d.get("url")
                if d_url and d_url not in seen_urls:
                    seen_urls.add(d_url)
                    all_docs.append(d)
                for p_name, p_val in (c.get("facts") or {}).items():
                    if not p_val or "не указано" in p_val.lower():
                        continue
                    if p_name not in merged_facts:
                        merged_facts[p_name] = p_val
                        fact_sources[p_name] = d

            primary = sorted_group[0]
            fused = {
                "doc": primary["doc"],
                "fused_docs": all_docs,
                "brand": primary.get("brand"),
                "model": primary.get("model"),
                "manufacturer": primary.get("manufacturer") or primary.get("brand"),
                "facts": merged_facts,
                "fact_sources": fact_sources,
                "is_tender_evidence": any(item.get("is_tender_evidence") for item in sorted_group),
                "supplier": next((item.get("supplier") for item in sorted_group if item.get("supplier")), None),
                "supplier_inn": next((item.get("supplier_inn") for item in sorted_group if item.get("supplier_inn")), None),
                "reasoning": next((item.get("reasoning") for item in sorted_group if item.get("reasoning")), None),
            }
            web_fused.append(fused)

    cross_dealer_fused: List[Dict[str, Any]] = []
    for c in web_fused:
        c_b_norm = _compact(c.get("brand") or "").lower()
        c_m_norm = _normalize_model_for_exact_match(c.get("model") or "")
        c_m_raw = str(c.get("model") or "")

        is_specific_b = bool(c_b_norm and len(c_b_norm) >= 3 and c_b_norm not in generic_words)
        is_concrete_m = _is_concrete_specific_model(c_m_raw, generic_words)

        matched_dealer_target = None
        if is_specific_b and is_concrete_m:
            for target in cross_dealer_fused:
                t_b_norm = _compact(target.get("brand") or "").lower()
                t_m_norm = _normalize_model_for_exact_match(target.get("model") or "")
                if t_b_norm == c_b_norm and t_m_norm == c_m_norm:
                    matched_dealer_target = target
                    break

        if matched_dealer_target is not None:
            for d in c.get("fused_docs") or []:
                if d.get("url") and d["url"] not in {doc.get("url") for doc in matched_dealer_target["fused_docs"]}:
                    matched_dealer_target["fused_docs"].append(d)
            for p_name, p_val in (c.get("facts") or {}).items():
                if not p_val or "не указано" in p_val.lower():
                    continue
                curr_val = str(matched_dealer_target["facts"].get(p_name) or "").strip().lower()
                if p_name not in matched_dealer_target["facts"] or not curr_val or "не указано" in curr_val:
                    matched_dealer_target["facts"][p_name] = p_val
                    src_doc = c.get("fact_sources", {}).get(p_name) or c.get("doc")
                    matched_dealer_target["fact_sources"][p_name] = src_doc
        else:
            cross_dealer_fused.append(c)

    return cross_dealer_fused


def rank_candidates(
    candidates: List[Dict[str, Any]],
    hint_brand: str = "",
    hint_model: str = "",
    minprom_required: bool = False,
    minprom_manufacturers: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    clean_hint_b = _clean_org_name(str(hint_brand or "")).lower()
    clean_hint_mod = str(hint_model or "").strip().lower()

    def sort_key(c: Dict[str, Any]):
        m = c["matrix"]
        b = str(c.get("brand") or "").strip().lower()
        mod = str(c.get("model") or "").strip().lower()
        mfr = str(c.get("manufacturer") or "").strip().lower()
        doc_text = str(c.get("doc", {}).get("text") or "").lower()
        doc_url = str(c.get("doc", {}).get("url") or "").lower()

        def _clean_field(val: Any) -> str:
            s = str(val or "").strip().lower()
            if not s or any(w in s for w in ("пусто", "не указан", "по документу", "none", "null", "товар")):
                return ""
            return s

        clean_b = _clean_field(b)
        clean_mfr = _clean_field(mfr)
        effective_b = clean_b or clean_mfr or clean_hint_b
        clean_mod = _clean_field(mod)
        is_garbage_maker = (
            not effective_b or not clean_mod
            or len(effective_b) < 2 or len(clean_mod) < 2
        )
        has_maker = 1 if is_garbage_maker else 0

        total_reqs = len(m.get("rows", [])) or 14
        passes = m["passes"]
        fails = m["fails"]
        coverage = m["coverage"]

        min_clean_passes = min(total_reqs, max(1, int(total_reqs * 0.35))) if total_reqs else 1
        is_clean_conforming = 0 if (fails == 0 and passes >= min_clean_passes and not is_garbage_maker) else 1

        matches_model = 1
        if clean_hint_mod and len(clean_hint_mod) >= 2:
            if _compact(clean_hint_mod) in _compact(mod) or _compact(mod) in _compact(clean_hint_mod):
                matches_model = 0

        is_tender_ev = 0 if c.get("is_tender_evidence") else 1

        in_minprom = 1
        if minprom_required:
            reg_num = c.get("minprom_registry_number")
            m_matches = c.get("minprom_matches")
            if reg_num or m_matches:
                in_minprom = 0
            elif minprom_manufacturers:
                if any(mm.lower() in b or mm.lower() in mfr or mm.lower() in doc_text[:2000] for mm in minprom_manufacturers):
                    in_minprom = 0

        net_score = (passes * 3) - (fails * 5)

        matches_hint = 1
        if clean_hint_b and len(clean_hint_b) >= 3:
            hint_words = [w for w in "".join(c if c.isalnum() else " " for c in clean_hint_b).split() if len(w) >= 4]
            if hint_words and any(w in b or w in mfr or w in doc_url or w in doc_text[:1500] for w in hint_words):
                matches_hint = 0

        return (
            has_maker,
            is_clean_conforming,
            matches_model,
            is_tender_ev,
            in_minprom,
            -net_score,
            -passes,
            fails,
            -coverage,
            matches_hint,
        )

    return sorted(candidates, key=sort_key)


def _spec_row(row: Dict[str, Any], source_no: Optional[int], source_url: str) -> Dict[str, str]:
    verdict = row["verdict"]
    fact = row["fact"]
    consensus_note = row.get("consensus_note")
    clean_note = str(row.get("note") or "").strip()

    if verdict == "pass":
        status = "match"
        if consensus_note:
            comment = consensus_note
        elif clean_note:
            src_lbl = f" [ИСТОЧНИК #{source_no}]" if source_no else ""
            comment = f"Подтверждено документом производителя{src_lbl}: {clean_note}."
        else:
            comment = f"Подтверждено документацией [ИСТОЧНИК #{source_no}]" if source_no else "Подтверждено документацией производителя"
    elif verdict == "fail":
        status = "mismatch"
        src_lbl = f" [ИСТОЧНИК #{source_no}]" if source_no else ""
        comment = f"Отклонение от требований ТЗ{src_lbl}: {clean_note}." if clean_note else "Отклонение от требований ТЗ."
    else:
        status = "clarify"
        fact = "В открытой документации не указано (требуется официальный паспорт завода)"
        comment = "Параметр отсутствует в открытых источниках — требуется уточнить по паспорту завода."

    return {
        "param_name": row["param_name"],
        "tz_requirement": row["tz_requirement"],
        "product_fact": fact,
        "status": status,
        "comment": comment,
        "source_url": source_url or "",
    }


def build_positions_from_ranked(
    ranked: List[Dict[str, Any]],
    requirements: List[Dict[str, str]],
    item_name: str,
    max_analogs: int = 2,
    pos_hint: Optional[Dict[str, Any]] = None,
) -> Optional[List[Dict[str, Any]]]:
    if not ranked:
        return None

    min_clean_passes = min(len(requirements), max(1, int(len(requirements) * 0.35))) if requirements else 1
    qualified = [
        c for c in ranked
        if c["matrix"]["fails"] == 0
        and c["matrix"]["passes"] >= min_clean_passes
        and _has_real_maker(c, pos_hint)
    ]

    valid_ranked = [c for c in ranked if _has_real_maker(c, pos_hint)]
    if not valid_ranked:
        return None

    winner = qualified[0] if qualified else valid_ranked[0]

    winner_b = str(winner.get("brand") or winner.get("manufacturer") or "").strip().lower()
    winner_m = str(winner.get("model") or "").strip().lower()
    winner_key = f"{winner_b} {winner_m}".strip()

    seen_alt_keys = {winner_key}
    analogs_pool = []
    clean_analogs = [c for c in ranked if c["matrix"]["fails"] == 0 and _has_real_maker(c, pos_hint)]
    for c in clean_analogs:
        c_b = str(c.get("brand") or c.get("manufacturer") or "").strip().lower()
        c_m = str(c.get("model") or "").strip().lower()
        c_key = f"{c_b} {c_m}".strip()
        if c_key and c_key not in seen_alt_keys:
            seen_alt_keys.add(c_key)
            analogs_pool.append(c)
            if len(analogs_pool) >= max_analogs:
                break

    ordered = [winner] + analogs_pool[:max_analogs]
    main = ordered[0]
    m = main["matrix"]

    fused_docs = list(main.get("fused_docs") or [main["doc"]])
    fact_sources = main.get("fact_sources") or {}

    raw_b, raw_mfr, raw_mod = _resolve_real_maker_and_model(
        main.get("brand") or "",
        main.get("manufacturer") or "",
        main.get("model") or "",
        doc=main.get("doc"),
        fused_docs=fused_docs,
    )
    brand, model = normalize_model_label(raw_b, raw_mod)
    manufacturer = raw_mfr or brand or "Производитель по документу"

    doc_index_map: Dict[str, int] = {}
    for idx, d in enumerate(fused_docs, 1):
        u = d.get("url")
        if u and u not in doc_index_map:
            doc_index_map[u] = idx

    specs_breakdown = []
    for row in m.get("rows") or []:
        p_name = row["param_name"]
        src_doc = fact_sources.get(p_name) or main.get("doc") or {}
        src_url = str(src_doc.get("url") or "").strip()
        src_no = doc_index_map.get(src_url)
        specs_breakdown.append(_spec_row(row, src_no, src_url))

    conf = compute_spec_compliance(specs_breakdown)
    reasoning = (
        f"Модель {brand} {model} подобрана по результатам сопоставления характеристик ТЗ с открытыми техническими данными производителя. "
        f"Подтверждено соответствие {m['passes']} параметров из {len(requirements)}."
    )

    alts: List[Dict[str, Any]] = []
    for a in ordered[1:]:
        a_b, a_mfr, a_mod = _resolve_real_maker_and_model(
            a.get("brand") or "",
            a.get("manufacturer") or "",
            a.get("model") or "",
            doc=a.get("doc"),
        )
        a_b, a_mod = normalize_model_label(a_b, a_mod)
        a_matrix = a.get("matrix") or {}
        a_specs = [_spec_row(r, None, str(a.get("doc", {}).get("url") or "")) for r in a_matrix.get("rows") or []]
        a_conf = compute_spec_compliance(a_specs)

        alts.append({
            "brand": a_b or "Аналог",
            "model": a_mod or "",
            "manufacturer": a_mfr or a_b,
            "confidence": a_conf,
            "notes": f"Отечественный аналог по 44-ФЗ. Подтверждено {a_matrix.get('passes', 0)} параметров.",
            "source_url": str(a.get("doc", {}).get("url") or ""),
            "specs_breakdown": a_specs,
        })

    if pos_hint and pos_hint.get("analogs"):
        existing_alt_names = {
            f"{(a.get('brand') or '').lower()} {(a.get('model') or '').lower()}".strip()
            for a in alts
        }
        w_b = (brand or "").lower().strip()
        w_mfr = (manufacturer or "").lower().strip()
        for ea in pos_hint["analogs"]:
            if isinstance(ea, dict):
                ea_brand = str(ea.get("brand") or "").strip()
                ea_model = str(ea.get("model") or "").strip()
                ea_mfr = str(ea.get("manufacturer") or ea_brand).strip()
                ea_key = f"{ea_brand.lower()} {ea_model.lower()}".strip()
                if (
                    ea_brand
                    and ea_key not in existing_alt_names
                    and ea_brand.lower() not in (w_b, w_mfr)
                    and (ea_mfr or "").lower() not in (w_b, w_mfr)
                ):
                    alts.append({
                        "brand": ea_brand,
                        "model": ea_model,
                        "manufacturer": ea_mfr or ea_brand,
                        "confidence": 0.85,
                        "notes": ea.get("notes") or f"Взаимозаменяемый промышленный аналог ({ea_brand} {ea_model}), указанный в закупочной документации.",
                        "source_url": "",
                        "specs_breakdown": [],
                    })
                    existing_alt_names.add(ea_key)

    primary_url = ""
    for d in fused_docs:
        u = str(d.get("url") or "").strip()
        if u.startswith("http"):
            primary_url = u
            break

    verified_docs_out = []
    seen_urls = set()
    for d in fused_docs:
        u = str(d.get("url") or "").strip()
        if u and u not in seen_urls:
            seen_urls.add(u)
            verified_docs_out.append({
                "url": u,
                "domain": d.get("domain") or "",
                "type": d.get("type") or "html",
                "title": d.get("title") or "",
                "text": str(d.get("text") or "")[:20000],
            })

    return [{
        "position_no": 1,
        "name_in_tz": item_name,
        "identified_brand": brand,
        "identified_model": model,
        "manufacturer": manufacturer,
        "confidence": conf,
        "reasoning": reasoning,
        "source_url": primary_url,
        "specs_breakdown": specs_breakdown,
        "alternative_brands": alts,
        "verified_documents": verified_docs_out,
    }]


async def _fetch_product_links_from_listings(
    listing_urls: List[str],
    item_name: str,
    limit: int = 8,
) -> List[str]:
    import httpx
    item_words = [w for w in re.findall(r"[а-яa-z]{4,}", str(item_name or "").lower())][:3]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    links: List[str] = []
    seen = set()
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
        for listing_url in listing_urls[:4]:
            if not listing_url or not listing_url.startswith("http"):
                continue
            try:
                resp = await client.get(listing_url)
                if resp.status_code >= 400:
                    continue
                html = resp.text
            except Exception:
                continue
            for m in re.finditer(r"href=[\"']([^\"'#]+)[\"']", html):
                href = m.group(1)
                full = urljoin(listing_url, href).split("?")[0].rstrip("/")
                if not full.startswith("http") or full in seen or full == listing_url:
                    continue
                low = full.lower()
                if not _LISTING_URL_HINT_RE.search(low):
                    continue
                if any(bad in low for bad in ("otzyv", "blog", "news", "article", "uslugi", "dostavka", "kontakt", "o-kompanii", "comparison")):
                    continue
                if item_words and not any(w in low for w in item_words) and not re.search(r"[/-]\d{3,}[/\-]|-\d{3,}$", low):
                    continue
                seen.add(full)
                links.append(full)
                if len(links) >= limit:
                    return links
    return links


async def _second_round_queries_ai(
    settings: SystemSettings,
    best: Optional[Dict[str, Any]],
    requirements: List[Dict[str, str]],
    item_name: str,
) -> List[str]:
    clean_name = str(item_name or "").strip()
    brand = str((best or {}).get("brand") or "").strip()
    model = str((best or {}).get("model") or "").strip()
    if brand.lower() in ("не указан", "unknown", "none", "производитель"):
        brand = ""
    if model.lower() in ("не указан", "unknown", "none"):
        model = ""

    rows = (best.get("matrix") or {}).get("rows") if best else None
    fails = [r for r in rows if r.get("verdict") == "fail"] if rows else []
    passes = [r for r in rows if r.get("verdict") == "pass"] if rows else []

    if fails:
        cand_info = f"Кандидат: {brand} {model}\nОтклонения от ТЗ: " + "; ".join(
            f"{f.get('param_name')} (факт: {f.get('fact')}, ТЗ: {f.get('tz_requirement')})" for f in fails[:5]
        )
    elif model:
        cand_info = f"Кандидат: {brand} {model}\nСовпали характеристики: {len(passes)} шт."
    else:
        cand_info = "Кандидат пока не найден или не имеет точной модели."

    specs_lines = [f"- {r.get('param_name')}: {r.get('tz_requirement')}" for r in requirements if r.get("param_name")]
    specs_text = "\n".join(specs_lines)[:8000]

    try:
        raw = await call_llm(
            settings,
            prompt=_ROUND2_QUERIES_LLM_PROMPT.format(
                item_name=clean_name,
                candidate_info=cand_info,
                specs_text=specs_text,
            ),
            system_prompt="Ты эксперт по техническому поиску оборудования. Отвечай только валидным JSON-списком строк.",
            json_mode=True,
            tier="light",
            routing_key="procurement_brand_detection",
            timeout_seconds=20.0,
        )
        data = parse_json_list(raw)
        if isinstance(data, list) and data:
            queries = [str(q).strip() for q in data if isinstance(q, str) and len(str(q).strip()) >= 4]
            if queries:
                return queries
    except Exception as exc:
        logger.debug("_second_round_queries_ai_failed: %s", exc)

    # Резервные запросы
    queries = []
    if brand and model and not fails:
        queries.append(f'"{brand}" "{model}" паспорт инструкция PDF')
        queries.append(f'{clean_name} "{model}" характеристики')
    elif clean_name:
        queries.append(f"{clean_name} характеристики паспорт")
        queries.append(f"{clean_name} паспорт PDF")
    return queries[:5]


async def detect_exact_products_characteristic_first(
    settings: SystemSettings,
    spec_text: str,
    procurement_title: str = "",
    progress_callback: Optional[ProgressCallback] = None,
    full_context: Optional[str] = None,
    evidence_data: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
    """
    Характеристики ТЗ -> Поиск товара по характеристикам -> Факты из документов -> Матрица -> Решение.
    """
    if not spec_text or len(spec_text.strip()) < 30:
        return None

    if progress_callback:
        await progress_callback(15, "ИИ-разбор структуры ТЗ: предмет, позиции, характеристики...")

    spec_norm = normalize_spec_text(spec_text)
    item_name = ""
    tz_positions: List[Dict[str, Any]] = []

    tz_structure = await parse_tz_structure(settings, spec_norm)
    if tz_structure:
        item_name = tz_structure.get("item_name") or ""
        tz_positions = tz_structure.get("positions") or []

    if not tz_positions:
        requirements = await extract_tz_requirements(settings, spec_norm)
        if len(requirements) < 2:
            return None
        base_name = item_name or procurement_title or "Оборудование по ТЗ"
        tz_positions = [{"name": base_name, "requirements": requirements}]

    if not item_name:
        item_name = procurement_title or "Оборудование по ТЗ"

    tz_brand_hints = extract_existing_tz_brand_hints(full_context or spec_text, parse_under_table_blocks=True)

    all_found_positions: List[Dict[str, Any]] = []
    all_found_docs: List[Dict[str, Any]] = []

    for pos_idx, p_tz in enumerate(tz_positions[:MAX_EXACT_POSITIONS_PER_JOB], 1):
        pos_name = p_tz.get("name") or item_name
        pos_reqs = p_tz.get("requirements") or []
        if not pos_reqs:
            continue

        pos_hint = find_hint_for_position(tz_brand_hints, pos_name)
        hint_b = p_tz.get("brand_hint") or (pos_hint.get("brand") if pos_hint else "") or ""
        hint_mod = p_tz.get("model_hint") or (pos_hint.get("model") if pos_hint else "") or ""
        hint_mfr = p_tz.get("manufacturer_hint") or (pos_hint.get("manufacturer") if pos_hint else "") or ""
        hint_analogs = p_tz.get("analogs") or (pos_hint.get("analogs") if pos_hint else []) or []

        eff_pos_hint = dict(p_tz)
        if pos_hint:
            if not eff_pos_hint.get("brand_hint") and pos_hint.get("brand"):
                eff_pos_hint["brand_hint"] = pos_hint["brand"]
            if not eff_pos_hint.get("model_hint") and pos_hint.get("model"):
                eff_pos_hint["model_hint"] = pos_hint["model"]
            if not eff_pos_hint.get("manufacturer_hint") and pos_hint.get("manufacturer"):
                eff_pos_hint["manufacturer_hint"] = pos_hint["manufacturer"]
            if not eff_pos_hint.get("analogs") and pos_hint.get("analogs"):
                eff_pos_hint["analogs"] = pos_hint["analogs"]

        analogs_str = ", ".join(
            f"{a.get('brand', '')} {a.get('model', '')}".strip()
            for a in hint_analogs
            if isinstance(a, dict)
        )

        # 1. Поисковые запросы через ИИ
        queries = []
        try:
            specs_lines = [f"- {r['param_name']}: {r['tz_requirement']}" for r in pos_reqs]
            raw_q = await call_llm(
                settings,
                prompt=_CHARACTERISTIC_QUERIES_LLM_PROMPT.format(
                    item_name=pos_name,
                    specs_text="\n".join(specs_lines)[:10000],
                    brand_hint=hint_b,
                    model_hint=hint_mod,
                    manufacturer_hint=hint_mfr,
                    analogs_hint=analogs_str,
                ),
                system_prompt="Ты инженер-эксперт по закупкам. Отвечай только валидным JSON-списком строк.",
                json_mode=True,
                tier="light",
                routing_key="procurement_brand_detection",
                timeout_seconds=25.0,
            )
            parsed_q = parse_json_list(raw_q)
            if isinstance(parsed_q, list):
                queries = [str(q).strip() for q in parsed_q if isinstance(q, str) and len(str(q).strip()) >= 4]
        except Exception:
            pass

        if not queries:
            queries = p_tz.get("search_queries") or [
                f"{pos_name} характеристики паспорт",
                f"{pos_name} паспорт PDF",
            ]

        # Прямые запросы по марке/модели и официальному сайту
        if hint_mod and len(hint_mod) >= 2:
            clean_item_short = pos_name.split("(")[0].strip()
            q_mfr = f'"{clean_item_short}" "{hint_mod}" завод производитель'
            if q_mfr.lower() not in {q.lower() for q in queries}:
                queries.append(q_mfr)
            q_site = f'"{clean_item_short}" "{hint_mod}" официальный сайт'
            if q_site.lower() not in {q.lower() for q in queries}:
                queries.append(q_site)

        # 2. Выполнение поиска в сети
        raw_candidates: List[Any] = []
        for q in queries[:6]:
            res = await _fetch_search_results_for_specs(settings, q, max_results=6)
            raw_candidates.extend(res)

        target_kws = [pos_name] + [
            c for c in (_compact_requirement(r["tz_requirement"], r["param_name"]) or "" for r in pos_reqs) if c
        ]
        if hint_b: target_kws.append(hint_b)
        if hint_mod: target_kws.append(hint_mod)

        urls = _rank_search_candidates(raw_candidates, target_kws, ["б/у", "аренда"])[:_MAX_CANDIDATE_DOCS]
        docs: List[Dict[str, Any]] = []
        seen_urls = set(urls)
        if urls:
            docs = await fetch_batch_web_documents(urls, max_docs=_MAX_CANDIDATE_DOCS)

        # 3. Извлечение фактов из документов (параллельно через Semaphore)
        candidates: List[Dict[str, Any]] = []
        if docs:
            sem = asyncio.Semaphore(4)
            async def _extract_single(d: Dict[str, Any]) -> Any:
                async with sem:
                    return await extract_doc_facts(settings, d, pos_reqs)

            extracted = await asyncio.gather(*(_extract_single(d) for d in docs), return_exceptions=True)
            for d, ext in zip(docs, extracted):
                if isinstance(ext, Exception) or not ext or not ext.get("facts"):
                    continue
                candidates.append({
                    "doc": d,
                    "brand": ext.get("brand"),
                    "model": ext.get("model"),
                    "manufacturer": ext.get("manufacturer"),
                    "facts": ext.get("facts") or {},
                })

        # Инъекция улик из документации закупки (Tier 0 Evidence)
        if evidence_data and evidence_data.get("evidence_products"):
            for ev_p in evidence_data["evidence_products"]:
                ev_b = ev_p.get("brand") or ""
                ev_mod = ev_p.get("model") or ""
                ev_mfr = ev_p.get("manufacturer") or ev_b
                ev_facts = ev_p.get("facts") or {}
                if ev_b or ev_mod:
                    ev_doc = {
                        "url": "документация_закупки_нмцк",
                        "title": f"Официальная документация закупки ({ev_p.get('reasoning', 'улики')})",
                        "text": f"Документ закупки: {ev_b} {ev_mod}. Производитель: {ev_mfr}",
                        "domain": "документы_закупки",
                        "type": "official_tender_document",
                    }
                    candidates.append({
                        "doc": ev_doc,
                        "brand": ev_b,
                        "model": ev_mod,
                        "manufacturer": ev_mfr,
                        "facts": ev_facts,
                        "is_tender_evidence": True,
                        "reasoning": ev_p.get("reasoning", "Официальная документация закупки"),
                    })

        ranked: List[Dict[str, Any]] = []
        if candidates:
            candidates = fuse_candidates_by_model(candidates, pos_reqs)
            for c in candidates:
                c["matrix"] = build_candidate_matrix(c, pos_reqs)
                c["matrix"] = await enrich_matrix_with_ai(
                    settings, c["matrix"], pos_reqs,
                    brand=c.get("brand") or "",
                    model=c.get("model") or "",
                    item_name=pos_name,
                )
            ranked = rank_candidates(candidates, hint_brand=hint_b, hint_model=hint_mod)

        best = ranked[0] if ranked else None

        # Раунд 2 (добор при браке лидера или слабом покрытии)
        need_round2 = (best is None) or (best["matrix"]["fails"] > 0) or (best["matrix"]["coverage"] < 0.5)
        if need_round2:
            if progress_callback:
                await progress_callback(60, f"Позиция {pos_idx}: дополнительный поиск паспортов и каталогов заводов...")
            round2_queries = await _second_round_queries_ai(settings, best, pos_reqs, pos_name)
            docs2_raw: List[Any] = []
            for q2 in round2_queries[:4]:
                r2 = await _fetch_search_results_for_specs(settings, q2, max_results=6)
                docs2_raw.extend(r2)

            urls2 = _rank_search_candidates(docs2_raw, target_kws, ["б/у", "аренда"])[:6]
            urls2 = [u for u in urls2 if u not in seen_urls]
            for u in urls2: seen_urls.add(u)

            if urls2:
                docs2 = await fetch_batch_web_documents(urls2, max_docs=6)
                sem2 = asyncio.Semaphore(4)
                async def _extract_single2(d: Dict[str, Any]) -> Any:
                    async with sem2:
                        return await extract_doc_facts(settings, d, pos_reqs)

                extracted2 = await asyncio.gather(*(_extract_single2(d) for d in docs2), return_exceptions=True)
                for d2, ext2 in zip(docs2, extracted2):
                    docs.append(d2)
                    if isinstance(ext2, Exception) or not ext2 or not ext2.get("facts"):
                        continue
                    candidates.append({
                        "doc": d2,
                        "brand": ext2.get("brand"),
                        "model": ext2.get("model"),
                        "manufacturer": ext2.get("manufacturer"),
                        "facts": ext2.get("facts") or {},
                    })

                if candidates:
                    candidates = fuse_candidates_by_model(candidates, pos_reqs)
                    for c in candidates:
                        c["matrix"] = build_candidate_matrix(c, pos_reqs)
                        c["matrix"] = await enrich_matrix_with_ai(
                            settings, c["matrix"], pos_reqs,
                            brand=c.get("brand") or "",
                            model=c.get("model") or "",
                            item_name=pos_name,
                        )
                    ranked = rank_candidates(candidates, hint_brand=hint_b, hint_model=hint_mod)
                    best = ranked[0] if ranked else None

        # 3. Многоисточниковый консенсус для лидеров
        if ranked:
            if progress_callback:
                await progress_callback(80, f"Позиция {pos_idx}: кросс-сверка консенсуса независимых источников...")
            for top_c in ranked[:2]:
                if not top_c.get("is_tender_evidence"):
                    await expand_candidate_sources_ai(settings, top_c, pos_name, seen_urls, pos_reqs, max_sources=4)
                    if len(top_c.get("fused_docs", [])) >= 2:
                        top_c["matrix"] = await enrich_candidate_multi_source_consensus_ai(settings, top_c, pos_reqs, pos_name)

            ranked = rank_candidates(candidates, hint_brand=hint_b, hint_model=hint_mod)
            best = ranked[0] if ranked else None

        if best is not None:
            built = build_positions_from_ranked(ranked, pos_reqs, pos_name, pos_hint=eff_pos_hint)
            if built:
                built[0]["position_no"] = pos_idx
                all_found_positions.extend(built)
                all_found_docs.extend(docs)

    return all_found_positions, all_found_docs


find_candidate_models_characteristic_first = detect_exact_products_characteristic_first

