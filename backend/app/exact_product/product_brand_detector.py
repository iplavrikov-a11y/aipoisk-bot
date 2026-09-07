from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .llm_bridge import call_llm
from .minprom import (
    find_minprom_gisp_match as _find_minprom_sync,
    find_minprom_registry_matches_ai as _find_minprom_ai,
)

logger = logging.getLogger(__name__)


def isolate_tz_table_content(raw_text: str) -> str:
    """
    Извлекает ИСКЛЮЧИТЕЛЬНО табличную часть технического задания.
    Полностью отсекает всё, что идет ниже таблицы.
    """
    if not raw_text:
        return ""
    text = raw_text.strip()

    # 1. Жесткая отсечка на первом маркере подтабличной части
    cutoff = re.search(
        r"(?im)^(?:\s*[-*•]\s*\*{0,2}(?:Для позиции|Точный товар|Аналог\s*\d*)|#+\s*Условия\s+поставки|###?\s*Условия|Условия\s+поставки\s*:)",
        text,
    )
    if cutoff:
        text = text[: cutoff.start()].strip()

    # 2. HTML-таблица (<table ...>...</table>)
    if "<table" in text.lower():
        end_idx = text.lower().rfind("</table>")
        if end_idx != -1:
            end_pos = end_idx + len("</table>")
            start_idx = 0
            m_title = re.search(
                r"(?i)(?:ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|#+\s*(?:4\.5\s*)?ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|##\s*Спецификация|##\s*Товары)",
                text[:end_pos],
            )
            if m_title:
                start_idx = m_title.start()
            return text[start_idx:end_pos].strip()

    # 3. Markdown-таблица (| ... |)
    lines = text.splitlines()
    table_line_indices = [
        i for i, line in enumerate(lines)
        if line.strip().startswith("|") and line.strip().endswith("|")
    ]
    if table_line_indices:
        first_tbl = table_line_indices[0]
        last_tbl = first_tbl
        for idx in table_line_indices[1:]:
            if idx - last_tbl <= 3:
                last_tbl = idx
            else:
                break

        start_idx = first_tbl
        for j in range(first_tbl - 1, max(-1, first_tbl - 6), -1):
            l = lines[j].strip()
            if not l:
                continue
            if any(h in l.lower() for h in ("техническое задание", "спецификация", "товары")) or l.startswith("#") or l.startswith("**"):
                start_idx = j
            elif start_idx == first_tbl:
                start_idx = j

        return "\n".join(lines[start_idx : last_tbl + 1]).strip()

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
    """Извлекает чистую техническую спецификацию или таблицу ТЗ, отсекая общую информацию отчета и любые приписки под таблицей."""
    if not report_text:
        return ""
    text = report_text.strip()

    # Если это полный аналитический отчет, сначала находим блок ТЗ
    m = re.search(
        r"(?i)(?:#+\s*(?:4\.5\s*)?ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|##\s*Спецификация|##\s*Товары)(.+?)(?=(?:#+\s*4\.[6-9]|#+\s*5\.|#+\s*Предварительная\s+аналитика|#+\s*Конфликты|\Z))",
        text,
        re.DOTALL,
    )
    section_text = m.group(0).strip() if m and len(m.group(0).strip()) > 40 else text

    # Изолируем только таблицу ТЗ (отсекая блоки «Для позиции», «Точный товар», «Условия поставки» под таблицей)
    return isolate_tz_table_content(section_text)


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
    return _find_minprom_sync(
        brand=brand,
        manufacturer=manufacturer,
        model=model,
        name_in_tz=name_in_tz,
        okpd2=okpd2,
        max_entries=max_entries,
    )


async def enrich_positions_with_minprom_registry_ai(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Асинхронное обогащение выявленных позиций записями ГИСП.
    """
    if not positions:
        return []

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
            max_entries=3,
        )

        valid_matches = raw_matches[:3]
        pos["minprom_matches"] = valid_matches

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
