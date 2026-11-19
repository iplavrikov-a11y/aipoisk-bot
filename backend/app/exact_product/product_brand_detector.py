from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .llm_bridge import call_llm
from .minprom import (
    find_minprom_gisp_match as _find_minprom_sync,
    find_minprom_registry_matches_ai as _find_minprom_ai,
    is_gisp_product_compatible_ai,
)

logger = logging.getLogger(__name__)


def isolate_tz_table_content(raw_text: str) -> str:
    """
    Извлекает ИСКЛЮЧИТЕЛЬНО табличную часть технического задания.
    Полностью отсекает всё, что идет ниже таблицы (условия поставки, догадки ИИ).
    При этом сохраняет заголовок/преамбулу и саму таблицу, даже если в преамбуле
    присутствуют вводные пометки.
    """
    if not raw_text:
        return ""
    text = raw_text.strip()

    # 1. HTML-таблица (<table ...>...</table>)
    if "<table" in text.lower():
        end_idx = text.lower().rfind("</table>")
        if end_idx != -1:
            end_pos = end_idx + len("</table>")
            start_pos = text.lower().find("<table")
            m_title = re.search(
                r"(?i)(?:ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|#+\s*(?:4\.5\s*)?ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|##\s*Спецификация|##\s*Товары)",
                text[:start_pos],
            )
            preamble = text[m_title.start():start_pos].strip() if m_title else text[:min(start_pos, 300)].strip()
            return f"{preamble}\n\n{text[start_pos:end_pos]}".strip()

    # 2. Таблицы формата docx (=== TABLE) или Markdown/pipe (| ... | или col1 | col2)
    lines = text.splitlines()
    table_line_indices = []
    for i, line in enumerate(lines):
        l_str = line.strip()
        if re.match(r"^===\s*TABLE", l_str, re.IGNORECASE):
            table_line_indices.append(i)
        elif "|" in l_str and (l_str.startswith("|") or len(l_str.split("|")) >= 3):
            table_line_indices.append(i)

    if table_line_indices:
        first_tbl = table_line_indices[0]
        last_tbl = table_line_indices[-1]

        # Захватываем заголовок из преамбулы (строки до первой таблицы)
        preamble_lines = []
        for j in range(first_tbl):
            l = lines[j].strip()
            # Если в преамбуле пошли условия поставки или догадки ИИ — останавливаем преамбулу на этом месте
            if re.match(r"(?i)^(?:[-*•]\s*\*{0,2}(?:Для позиции|Точный товар|Аналог)|Для позиции|#+\s*Условия|Условия\s+поставки)", l):
                break
            preamble_lines.append(lines[j])

        # Ищем конец таблицы и отсекаем подтабличные блоки
        end_tbl = last_tbl
        for k in range(last_tbl + 1, len(lines)):
            l = lines[k].strip()
            if not l:
                continue
            if re.match(r"(?i)^(?:[-*•]\s*\*{0,2}(?:Для позиции|Точный товар|Аналог)|#+\s*Условия|Условия\s+поставки)", l):
                break
            if "|" in l or re.match(r"^===\s*TABLE", l):
                end_tbl = k
            elif k - end_tbl <= 2:
                # возможное продолжение ячейки таблицы
                end_tbl = k
            else:
                break

        preamble = "\n".join(preamble_lines).strip()
        table_part = "\n".join(lines[first_tbl : end_tbl + 1]).strip()
        if preamble:
            return f"{preamble}\n\n{table_part}"
        return table_part

    # 3. Документ без таблиц — обычный текст: отсекаем подтабличные блоки
    cutoff = re.search(
        r"(?im)^(?:\s*[-*•]\s*\*{0,2}(?:Для позиции|Точный товар|Аналог\s*\d*)|#+\s*Условия\s+поставки|###?\s*Условия|Условия\s+поставки\s*:)",
        text,
    )
    if cutoff:
        return text[: cutoff.start()].strip()

    return text

BRAND_DETECTION_PROMPT = """Ты — ведущий эксперт по государственным закупкам (44-ФЗ, 223-ФЗ) и промышленному оборудованию.
Твоя задача — внимательно изучить приложенный текст технического задания (ТЗ) или спецификации и определить ТОЧНЫЙ ТОВАР, конкретную МОДЕЛЬ и ПРОИЗВОДИТЕЛЯ, под характеристики которых заказчик составил техническое задание.

Текст технического задания:
{report_text}

Ответь СТРОГО в формате JSON списка объектов:
[
  {{
    "position_no": 1,
    "name_in_tz": "Наименование позиции из ТЗ",
    "identified_brand": "Торговая марка / Бренд",
    "identified_model": "Точная модель / артикул",
    "manufacturer": "Завод-изготовитель (юридическое лицо)",
    "confidence": 0.95,
    "reasoning": "Обоснование подбора по ключевым параметрам ТЗ",
    "source_url": "Официальный сайт или ссылка на каталог",
    "specs_breakdown": [
      {{
        "param_name": "Параметр",
        "tz_requirement": "Требование ТЗ",
        "product_fact": "Факт производителя",
        "status": "match",
        "comment": "Подтверждено документацией"
      }}
    ],
    "alternative_brands": []
  }}
]
"""


def extract_clean_spec_text(report_text: str) -> str:
    """
    В TenderLex клиенты загружают техническое задание целиком (DOCX, PDF, Excel, текст).
    Лишнего текста переписки нет — весь документ является техническим заданием.
    Изолируем секцию ТЗ только если передан внутренний мультисекционный отчет с блоками 4.5 / 4.6.
    """
    if not report_text:
        return ""
    text = report_text.strip()

    # Если передан внутренний структурированный отчет TenderLex с главами аналитики:
    m = re.search(
        r"(?i)(?:#+\s*4\.5\s*ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ)(.+?)(?=(?:#+\s*4\.[6-9]|#+\s*5\.|\Z))",
        text,
        re.DOTALL,
    )
    if m and len(m.group(0).strip()) > 40:
        return isolate_tz_table_content(m.group(0).strip())

    # Во всех остальных случаях ТЗ анализируется целиком
    return text


async def find_minprom_registry_matches_ai(
    brand: str = "",
    manufacturer: str = "",
    model: str = "",
    name_in_tz: str = "",
    okpd2: str = "",
    max_entries: int = 5,
    settings: Any = None,
) -> list[dict[str, Any]]:
    """Поиск в реестре Минпромторга (ГИСП) через ИИ."""
    if settings is None:
        from .llm_bridge import get_settings
        settings = get_settings()
    return await _find_minprom_ai(
        settings,
        brand=brand,
        manufacturer=manufacturer,
        model=model,
        name_in_tz=name_in_tz,
        okpd2=okpd2,
        max_entries=max_entries,
    )



def find_minprom_registry_matches(
    brand: str = "",
    manufacturer: str = "",
    model: str = "",
    name_in_tz: str = "",
    okpd2: str = "",
    max_entries: int = 5,
) -> list[dict[str, Any]]:
    """Синхронный поиск в реестре Минпромторга (ГИСП)."""
    match = _find_minprom_sync(
        brand=brand,
        manufacturer=manufacturer,
        model=model,
        name_in_tz=name_in_tz,
    )
    if not match:
        return []
    return [{
        "registry_number": match.registry_number,
        "manufacturer": match.manufacturer,
        "product": match.product,
        "inn": match.inn,
        "conclusion_number": match.conclusion_number,
        "valid_until": match.valid_until,
        "source_url": match.source_url,
    }][:max(1, int(max_entries or 5))]


async def filter_minprom_candidates_ai(
    candidates: list[dict[str, Any]],
    name_in_tz: str,
    brand: str = "",
    model: str = "",
    settings: Any = None,
) -> list[dict[str, Any]]:
    """
    Пакетная семантическая фильтрация кандидатов из реестра Минпромторга (ГИСП)
    за один быстрый вызов ИИ (без кеширования между клиентскими задачами).
    """
    if not candidates or not name_in_tz:
        return candidates

    clean_tz = name_in_tz.strip()
    m_lower = (model or "").strip().lower()
    direct_matches: list[dict[str, Any]] = []
    to_eval_indices: list[int] = []

    for idx, c in enumerate(candidates):
        prod = str(c.get("product") or "").strip()
        if not prod:
            continue
        if m_lower and len(m_lower) >= 3 and m_lower in prod.lower():
            direct_matches.append(c)
            continue
        to_eval_indices.append(idx)

    if not to_eval_indices:
        return direct_matches

    batch_to_eval = to_eval_indices[:10]
    cand_lines: list[str] = []
    for line_num, idx in enumerate(batch_to_eval, start=1):
        c = candidates[idx]
        p_name = str(c.get("product") or "").strip()
        p_mfg = str(c.get("manufacturer") or "").strip()
        cand_lines.append(f"{line_num}. Товар: «{p_name}» | Производитель: «{p_mfg}»")

    prompt = f"""Ты — старший эксперт по товарной классификации промышленной продукции.
Задача: сопоставить позицию закупки из Технического задания (ТЗ) со списком товаров из официального Реестра Минпромторга РФ (ГИСП).

Позиция в ТЗ закупки: «{clean_tz}»
{f'Указанный бренд/модель: «{brand}» «{model}»' if (brand or model) else ''}

Кандидаты из Реестра Минпромторга:
{chr(10).join(cand_lines)}

ПРАВИЛО СЕМАНТИЧЕСКОГО СООТВЕТСТВИЯ:
- Кандидат ПОДХОДИТ, если он относится к тому же функциональному виду, типу или назначению продукции.
- Кандидат НЕ ПОДХОДИТ, если это товар другого назначения из другой сферы или случайный омоним.

Верни строго JSON со списком номеров подходящих товаров:
{{"compatible_indexes": [1, 2]}}
Если ни один кандидат не подходит, верни:
{{"compatible_indexes": []}}"""

    filtered_results = list(direct_matches)
    try:
        raw = await call_llm(
            prompt=prompt,
            system_prompt="Ты эксперт по классификации промышленной продукции. Отвечай строго валидным JSON.",
            model_tier="light",
            routing_key="procurement_brand_detection",
            json_mode=True,
            timeout_seconds=15.0,
        )
        cleaned = str(raw or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        data = json.loads(cleaned.strip())
        compat_set: set[int] = set()
        if isinstance(data, dict):
            compat_indexes = data.get("compatible_indexes") or []
            if isinstance(compat_indexes, list):
                compat_set = {int(x) for x in compat_indexes if str(x).isdigit()}
        elif isinstance(data, list):
            compat_set = {int(x) for x in data if str(x).isdigit()}

        for line_num, idx in enumerate(batch_to_eval, start=1):
            if line_num in compat_set:
                c = candidates[idx]
                if c not in filtered_results:
                    filtered_results.append(c)
        return filtered_results
    except Exception as exc:
        logger.debug("filter_minprom_candidates_ai_failed: %s", exc)
        # Fallback на поэлементную проверку при сбое пакетного вызова
        for idx in batch_to_eval:
            c = candidates[idx]
            prod = str(c.get("product") or "").strip()
            if prod and await is_gisp_product_compatible_ai(settings, prod, clean_tz, brand, model):
                if c not in filtered_results:
                    filtered_results.append(c)
        return filtered_results


async def enrich_positions_with_minprom_registry_ai(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Асинхронное обогащение выявленных позиций и их аналогов записями ГИСП (пакетная ИИ-фильтрация).
    """
    if not positions:
        return []

    from .llm_bridge import get_settings
    settings = get_settings()

    for pos in positions:
        if not isinstance(pos, dict):
            continue
        brand = str(pos.get("identified_brand") or "").strip()
        manuf = str(pos.get("manufacturer") or "").strip()
        model = str(pos.get("identified_model") or "").strip()
        name_tz = str(pos.get("name_in_tz") or "").strip()

        existing_reg = str(pos.get("minprom_registry_number") or "").strip()
        raw_matches = await find_minprom_registry_matches_ai(
            brand=brand,
            manufacturer=manuf,
            model=model,
            name_in_tz=name_tz,
            max_entries=5,
            settings=settings,
        )

        valid_matches = await filter_minprom_candidates_ai(
            raw_matches[:5],
            name_in_tz=name_tz,
            brand=brand,
            model=model,
            settings=settings,
        )
        pos["minprom_matches"] = valid_matches[:3]

        if existing_reg:
            pos["minprom_registry_number"] = existing_reg
            pos["minprom_manufacturer"] = pos.get("minprom_manufacturer") or manuf
            pos["minprom_product"] = pos.get("minprom_product") or model or name_tz
            pos["minprom_source_url"] = pos.get("minprom_source_url") or "https://gisp.gov.ru/pp719v2/pub/prod/"
            if valid_matches:
                pos["minprom_conclusion_number"] = valid_matches[0].get("conclusion_number", "")
        elif valid_matches:
            best = valid_matches[0]
            pos["minprom_registry_number"] = best.get("registry_number", "")
            pos["minprom_manufacturer"] = best.get("manufacturer", "")
            pos["minprom_product"] = best.get("product", "")
            pos["minprom_conclusion_number"] = best.get("conclusion_number", "")
            pos["minprom_source_url"] = best.get("source_url") or "https://gisp.gov.ru/pp719v2/pub/prod/"

        # Также подтягиваем ГИСП для взаимозаменяемых аналогов (если еще не заполнено)
        for alt in (pos.get("alternative_brands") or [])[:4]:
            if not isinstance(alt, dict) or alt.get("minprom_registry_number") or alt.get("gisp_match"):
                continue
            alt_b = str(alt.get("brand") or "").strip()
            alt_mfr = str(alt.get("manufacturer") or alt_b).strip()
            alt_m = str(alt.get("model") or "").strip()
            if not (alt_b or alt_mfr):
                continue
            alt_raw = await find_minprom_registry_matches_ai(
                brand=alt_b,
                manufacturer=alt_mfr,
                model=alt_m,
                name_in_tz=name_tz,
                max_entries=3,
                settings=settings,
            )
            if not alt_raw:
                continue
            alt_valid = await filter_minprom_candidates_ai(
                alt_raw[:3],
                name_in_tz=name_tz,
                brand=alt_b,
                model=alt_m,
                settings=settings,
            )
            if alt_valid:
                best_alt = alt_valid[0]
                alt["minprom_registry_number"] = best_alt.get("registry_number", "")
                alt["minprom_manufacturer"] = best_alt.get("manufacturer", "")
                alt["minprom_product"] = best_alt.get("product", "")
                alt["gisp_match"] = {
                    "registry_number": best_alt.get("registry_number", ""),
                    "manufacturer": best_alt.get("manufacturer", ""),
                    "product": best_alt.get("product", ""),
                    "inn": best_alt.get("inn", ""),
                    "conclusion_number": best_alt.get("conclusion_number", ""),
                    "valid_until": best_alt.get("valid_until", ""),
                    "source_url": best_alt.get("source_url") or "https://gisp.gov.ru/pp719v2/pub/prod/",
                }

    return positions


async def detect_brands_in_report(report_text: str, procurement_title: str = "") -> List[Dict[str, Any]]:
    """
    Анализирует текст ТЗ и выявляет скрытые бренды/модели.
    """
    if not report_text or len(report_text.strip()) < 30:
        return []

    spec_text = extract_clean_spec_text(report_text)
    trimmed_report = spec_text.strip()
    if len(trimmed_report) > 30000:
        trimmed_report = trimmed_report[:30000]

    if procurement_title and procurement_title.strip() and procurement_title.strip() not in trimmed_report:
        trimmed_report = f"Наименование закупки: {procurement_title.strip()}\n\n" + trimmed_report

    try:
        raw_response = await call_llm(
            prompt=BRAND_DETECTION_PROMPT.format(report_text=trimmed_report),
            system_prompt="Ты эксперт по B2B закупкам и промышленному оборудованию. Отвечай только валидным JSON.",
            json_mode=True,
            model_tier="primary",
            routing_key="procurement_brand_detection",
        )
        if not raw_response:
            return []

        cleaned = str(raw_response).strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        data = json.loads(cleaned.strip())
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("detect_brands_in_report_failed: %s", exc)
        return []
