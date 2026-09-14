from __future__ import annotations

import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..ai import call_llm
from ..models import SystemSettings, parse_json_dict
from ..supplier_search import _minprom_registry_sqlite_path
from .models import GISP_PRODUCT_REGISTRY_URL, GispRegistryMatch

logger = logging.getLogger(__name__)


def _get_call_llm():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "call_llm"):
        return getattr(mod, "call_llm")
    from ..ai import call_llm
    return call_llm

GENERIC_GISP_TERMS = {
    "россия", "рф", "гост", "модель", "стандарт", "серия", "марка", "универсальный",
    "тип", "версия", "комплект", "устройство", "изделие", "оборудование", "материал", "состав",
}

_GISP_COMPAT_CACHE: dict[str, bool] = {}


def detect_minprom_registry_requirement(report_text: str) -> Optional[bool]:
    """
    Определяет, требуется ли в закупке включение продукции в Реестр промышленной продукции РФ (ГИСП).
    Возвращает True только при наличии требований нацрежима (запрет по ПП 616, ограничение по ПП 878, 102 и т.д.).
    """
    if not report_text:
        return None
    text_low = report_text.lower()
    minprom_triggers = (
        "реестр российской промышленной продукции",
        "реестровая запись",
        "выписка из реестра",
        "постановление № 616",
        "постановление правительства № 616",
        "пп рф 616",
        "пп 616",
        "постановление № 878",
        "пп рф 878",
        "пп 878",
        "национальный режим",
        "нацрежим",
        "запрет на допуск",
        "ограничение допуска",
        "1875",
        "719",
    )
    return any(trig in text_low for trig in minprom_triggers)


def _is_generic_gisp_term(s: str) -> bool:
    if not s:
        return True
    cleaned = re.sub(r'(?i)\b(ооо|ао|пао|зао|нпк|нпо|пк|тд|ип|гк|оао|рф|«|»|\"|\')\b', ' ', s.lower())
    cleaned = re.sub(r'[^а-яa-z0-9]', ' ', cleaned).strip()
    return cleaned in GENERIC_GISP_TERMS or len(cleaned) < 3


def _extract_word_stems(text: str) -> set[str]:
    stop_words = {
        "комплект", "система", "устройство", "изделие", "оборудование", "аппарат",
        "прибор", "средство", "комплекс", "блок", "модуль", "установка", "материал",
        "станция", "позиция", "наименование", "закупка", "поставка", "продукция",
        "для", "при", "или", "под", "над", "все", "всех", "типа", "вида", "типов",
        "номер", "часть", "элемент", "серия", "марка", "модель", "стандарт", "состав",
    }
    words = re.findall(r"[а-яёa-z0-9]{4,}", text.lower())
    stems = set()
    for w in words:
        if w in stop_words or w.isdigit():
            continue
        stem = re.sub(r'(?:овая|евая|иная|ный|ная|ное|ные|ого|его|ому|ему|ыми|ими|ом|ем|ах|ях|ам|ям|ов|ев|ей|ая|яя|ое|ее|ые|ие|ый|ий|ой|ей|у|ю|а|я|о|е|ы|и)$', '', w)
        if len(stem) >= 3:
            stems.add(stem)
        else:
            stems.add(w[:4])
    return stems


def _is_gisp_product_compatible(
    gisp_product: str,
    name_in_tz: str,
    brand: str = "",
    model: str = "",
) -> bool:
    if not gisp_product or not name_in_tz:
        return False

    p_lower = str(gisp_product or "").lower().strip()
    tz_lower = str(name_in_tz or "").lower().strip()
    model_lower = str(model or "").lower().strip()
    brand_lower = str(brand or "").lower().strip()

    tz_stems = _extract_word_stems(tz_lower)
    prod_stems = _extract_word_stems(p_lower)
    has_term_overlap = bool(tz_stems & prod_stems) if (tz_stems and prod_stems) else False

    if model_lower and not _is_generic_gisp_term(model_lower) and len(model_lower) >= 3:
        if bool(re.search(rf'\b{re.escape(model_lower)}\b', p_lower)):
            if has_term_overlap or not tz_stems:
                return True

    if brand_lower and not _is_generic_gisp_term(brand_lower) and len(brand_lower) >= 4:
        if bool(re.search(rf'\b{re.escape(brand_lower)}\b', p_lower)):
            if has_term_overlap or not tz_stems:
                return True

    return has_term_overlap


async def is_gisp_product_compatible_ai(
    settings: SystemSettings,
    gisp_product: str,
    name_in_tz: str,
    brand: str = "",
    model: str = "",
) -> bool:
    if not gisp_product or not name_in_tz:
        return False

    if not _is_gisp_product_compatible(gisp_product, name_in_tz, brand, model):
        return False

    if not getattr(settings, "has_active_ai_provider", False):
        return True

    prompt = f"""Определи, относятся ли два наименования товара к одной категории/типу продукции:
Товар из Реестра Минпромторга РФ: "{gisp_product}"
Товар/оборудование из ТЗ закупки: "{name_in_tz}"
Бренд/модель: {brand} {model}

Критерии:
- true: если оба товара относятся к одному функциональному виду продукции.
- false: если это случайный омоним или товар совершенно другой сферы.

Ответь строго JSON: {{"compatible": true}} или {{"compatible": false}}"""

    try:
        raw = await _get_call_llm()(
            settings,
            prompt,
            system_prompt="Ты эксперт по товарной классификации. Отвечай только валидным JSON.",
            tier="light",
            routing_key="procurement_brand_detection",
            json_mode=True,
            timeout_seconds=20.0,
        )
        parsed = parse_json_dict(raw)
        if isinstance(parsed, dict) and "compatible" in parsed:
            return bool(parsed["compatible"])
    except Exception as exc:
        logger.debug("is_gisp_product_compatible_ai_failed: %s", exc)

    return _is_gisp_product_compatible(gisp_product, name_in_tz, brand, model)


def _extract_conclusion_info(evidence: str) -> tuple[str, str]:
    conclusion_number = ""
    valid_until = ""
    if not evidence:
        return conclusion_number, valid_until
    m_conc = re.search(r'(?:заключение|срок действия\/заключение|заключение минпромторга)[\s:]*([^\;\,\n]+)', evidence, re.IGNORECASE)
    if m_conc:
        val = m_conc.group(1).strip()
        date_match = re.search(r'(\d{2}[.\/]\d{2}[.\/]\d{4}|\d{4}-\d{2}-\d{2})', val)
        if date_match:
            valid_until = date_match.group(1)
        num_clean = re.sub(r'(\d{2}[.\/]\d{2}[.\/]\d{4}|\d{4}-\d{2}-\d{2})', '', val).strip(" №/-,.")
        if num_clean:
            conclusion_number = num_clean
    return conclusion_number, valid_until


def _build_gisp_fts_query_grid(
    brand: str,
    manufacturer: str,
    model: str = "",
    name_in_tz: str = "",
) -> list[str]:
    queries: list[str] = []

    clean_manuf = ""
    if manufacturer and len(manufacturer.strip()) > 3:
        clean_manuf = re.sub(r'(?i)\b(ООО|АО|ПАО|ЗАО|НПК|НПО|ПК|ТД|ИП|ГК|ОАО|РФ|«|»|"|\')\b', '', manufacturer).strip()
        clean_manuf = re.sub(r'[^а-яА-Яa-zA-Z0-9\s-]', ' ', clean_manuf).strip()
        if _is_generic_gisp_term(clean_manuf) or len(clean_manuf) < 3:
            clean_manuf = ""

    clean_brand = ""
    if brand and len(brand.strip()) > 2 and not _is_generic_gisp_term(brand):
        clean_brand = brand.strip()

    clean_model = ""
    if model and len(model.strip()) > 2 and not _is_generic_gisp_term(model):
        clean_model = model.strip()

    clean_tz_terms: list[str] = []
    if name_in_tz and len(name_in_tz.strip()) > 4:
        clean_tz_terms = [
            w for w in re.sub(r'[^а-яА-Яa-zA-Z0-9\s]', ' ', name_in_tz).split()
            if len(w) >= 3 and not _is_generic_gisp_term(w)
        ]

    if clean_manuf and clean_model:
        queries.append(f"{clean_manuf} {clean_model}")
    if clean_brand and clean_model and clean_brand != clean_manuf:
        queries.append(f"{clean_brand} {clean_model}")
    if clean_manuf and clean_tz_terms:
        queries.append(f"{clean_manuf} {' '.join(clean_tz_terms[:2])}")
    if clean_brand and clean_tz_terms and clean_brand != clean_manuf:
        queries.append(f"{clean_brand} {' '.join(clean_tz_terms[:2])}")
    if clean_manuf and clean_manuf not in queries:
        queries.append(clean_manuf)
    if clean_brand and clean_brand not in queries:
        queries.append(clean_brand)
    if clean_model and clean_model not in queries:
        queries.append(clean_model)
    if clean_tz_terms and len(clean_tz_terms) >= 2:
        queries.append(" ".join(clean_tz_terms[:3]))

    return queries


async def find_minprom_gisp_match_ai(
    settings: SystemSettings,
    brand: str,
    manufacturer: str,
    model: str = "",
    name_in_tz: str = "",
) -> Optional[GispRegistryMatch]:
    sqlite_path = _minprom_registry_sqlite_path()
    if not sqlite_path or not sqlite_path.is_file():
        shared_path = Path("/root/projects/emailagent/storage/minprom_registry/minprom_registry.sqlite")
        if shared_path.is_file():
            sqlite_path = shared_path
        else:
            return None

    queries = _build_gisp_fts_query_grid(brand, manufacturer, model, name_in_tz)
    if not queries:
        return None

    try:
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        try:
            for q in queries:
                terms = [t for t in re.findall(r"[\w]{2,}", q) if len(t) > 1]
                if not terms:
                    continue
                match_expression = " AND ".join([f'"{t}"*' for t in terms[:4]])
                try:
                    cursor = conn.execute(
                        """
                        SELECT e.registry_number, e.manufacturer, e.product, e.inn, e.source_url, e.evidence
                        FROM entries_fts
                        JOIN entries e ON e.id = entries_fts.rowid
                        WHERE entries_fts MATCH ?
                        LIMIT 8
                        """,
                        (match_expression,),
                    )
                    rows = cursor.fetchall()
                    for reg_num, manuf, prod, inn, src_url, evidence in rows:
                        if _is_gisp_product_compatible(prod, name_in_tz, brand, model):
                            if await is_gisp_product_compatible_ai(settings, prod, name_in_tz, brand, model):
                                conc_num, v_until = _extract_conclusion_info(str(evidence or ""))
                                return GispRegistryMatch(
                                    registry_number=str(reg_num or "").strip(),
                                    manufacturer=str(manuf or "").strip(),
                                    product=str(prod or "").strip(),
                                    inn=str(inn or "").strip(),
                                    conclusion_number=conc_num,
                                    valid_until=v_until,
                                    source_url=str(src_url or GISP_PRODUCT_REGISTRY_URL),
                                    matched=True,
                                )
                except sqlite3.Error:
                    pass
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("find_minprom_gisp_match_ai_failed: %s", exc)

    return None


async def find_minprom_registry_matches_ai(
    settings: Any = None,
    brand: str = "",
    manufacturer: str = "",
    model: str = "",
    name_in_tz: str = "",
    okpd2: str = "",
    max_entries: int = 6,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Поиск кандидатов в реестре Минпромторга для начального наполнения (Minprom-First)."""
    if isinstance(settings, str):
        # Called positionally without settings: find_minprom_registry_matches_ai(brand, manufacturer, ...)
        brand, manufacturer, model, name_in_tz, okpd2 = settings, brand, manufacturer, model, name_in_tz
        settings = None

    if settings is None or not hasattr(settings, "has_active_ai_provider"):
        from .llm_bridge import get_settings
        settings = get_settings()

    sqlite_path = _minprom_registry_sqlite_path()
    if not sqlite_path or not sqlite_path.is_file():
        shared_path = Path("/root/projects/emailagent/storage/minprom_registry/minprom_registry.sqlite")
        if shared_path.is_file():
            sqlite_path = shared_path
        else:
            return []


    queries = _build_gisp_fts_query_grid(brand, manufacturer, model, name_in_tz)
    results: List[Dict[str, Any]] = []
    seen = set()

    try:
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        try:
            for q in queries[:4]:
                terms = [t for t in re.findall(r"[\w]{2,}", q) if len(t) > 1]
                if not terms:
                    continue
                match_expression = " AND ".join([f'"{t}"*' for t in terms[:3]])
                try:
                    cursor = conn.execute(
                        """
                        SELECT e.registry_number, e.manufacturer, e.product, e.inn, e.source_url, e.evidence
                        FROM entries_fts
                        JOIN entries e ON e.id = entries_fts.rowid
                        WHERE entries_fts MATCH ?
                        LIMIT ?
                        """,
                        (match_expression, max_entries),
                    )
                    for reg_num, manuf, prod, inn, src_url, evidence in cursor.fetchall():
                        key = f"{manuf}_{prod}"
                        if key not in seen:
                            seen.add(key)
                            conc_num, v_until = _extract_conclusion_info(str(evidence or ""))
                            results.append({
                                "registry_number": str(reg_num or "").strip(),
                                "manufacturer": str(manuf or "").strip(),
                                "product": str(prod or "").strip(),
                                "inn": str(inn or "").strip(),
                                "conclusion_number": conc_num,
                                "valid_until": v_until,
                                "source_url": str(src_url or GISP_PRODUCT_REGISTRY_URL),
                            })
                            if len(results) >= max_entries:
                                return results
                except sqlite3.Error:
                    pass
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("find_minprom_registry_matches_ai_failed: %s", exc)

    return results


def find_minprom_gisp_match(
    brand: str,
    manufacturer: str,
    model: str = "",
    name_in_tz: str = "",
) -> Optional[GispRegistryMatch]:
    """Синхронный поиск записи в Реестре Минпромторга (ГИСП) с базовой эвристикой."""
    sqlite_path = _minprom_registry_sqlite_path()
    if not sqlite_path or not sqlite_path.is_file():
        shared_path = Path("/root/projects/emailagent/storage/minprom_registry/minprom_registry.sqlite")
        if shared_path.is_file():
            sqlite_path = shared_path
        else:
            return None

    queries = _build_gisp_fts_query_grid(brand, manufacturer, model, name_in_tz)
    if not queries:
        return None

    try:
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        try:
            for q in queries:
                terms = [t for t in re.findall(r"[\w]{2,}", q) if len(t) > 1]
                if not terms:
                    continue
                match_expression = " AND ".join([f'"{t}"*' for t in terms[:4]])
                try:
                    cursor = conn.execute(
                        """
                        SELECT e.registry_number, e.manufacturer, e.product, e.inn, e.source_url, e.evidence
                        FROM entries_fts
                        JOIN entries e ON e.id = entries_fts.rowid
                        WHERE entries_fts MATCH ?
                        LIMIT 8
                        """,
                        (match_expression,),
                    )
                    rows = cursor.fetchall()
                    for reg_num, manuf, prod, inn, src_url, evidence in rows:
                        if _is_gisp_product_compatible(prod, name_in_tz, brand, model):
                            conc_num, v_until = _extract_conclusion_info(str(evidence or ""))
                            return GispRegistryMatch(
                                registry_number=str(reg_num or "").strip(),
                                manufacturer=str(manuf or "").strip(),
                                product=str(prod or "").strip(),
                                inn=str(inn or "").strip(),
                                conclusion_number=conc_num,
                                valid_until=v_until,
                                source_url=str(src_url or GISP_PRODUCT_REGISTRY_URL),
                                matched=True,
                            )
                except sqlite3.Error:
                    pass
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("find_minprom_gisp_match_failed: %s", exc)

    return None


def extract_conclusion_number(evidence: str) -> str:
    num, _ = _extract_conclusion_info(evidence)
    return num


def check_model_in_gisp_text(model: str, gisp_entry: dict) -> bool:
    if not model or not gisp_entry:
        return False
    text = f"{gisp_entry.get('product', '')} {gisp_entry.get('evidence', '')}".lower()
    return model.lower() in text


def match_brand_in_gisp(brand: str, okpd2: str = "") -> list[dict]:
    sqlite_path = _minprom_registry_sqlite_path()
    if not sqlite_path or not sqlite_path.is_file():
        shared_path = Path("/root/projects/emailagent/storage/minprom_registry/minprom_registry.sqlite")
        if shared_path.is_file():
            sqlite_path = shared_path
        else:
            return []
    terms = [t for t in re.findall(r"[\w]{2,}", brand) if len(t) > 1]
    if not terms:
        return []
    match_expr = " AND ".join([f'"{t}"*' for t in terms[:3]])
    try:
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        cursor = conn.execute(
            """
            SELECT e.registry_number, e.manufacturer, e.product, e.inn, e.source_url, e.evidence
            FROM entries_fts
            JOIN entries e ON e.id = entries_fts.rowid
            WHERE entries_fts MATCH ?
            LIMIT 10
            """,
            (match_expr,),
        )
        res = []
        for reg_num, manuf, prod, inn, src_url, evidence in cursor.fetchall():
            conc_num, v_until = _extract_conclusion_info(str(evidence or ""))
            res.append({
                "registry_number": str(reg_num or "").strip(),
                "manufacturer": str(manuf or "").strip(),
                "product": str(prod or "").strip(),
                "inn": str(inn or "").strip(),
                "conclusion_number": conc_num,
                "valid_until": v_until,
                "source_url": str(src_url or GISP_PRODUCT_REGISTRY_URL),
            })
        conn.close()
        return res
    except Exception:
        return []

