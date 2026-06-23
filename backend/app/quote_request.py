from __future__ import annotations

import re
from typing import Any

from .ai import call_llm, parse_json_object
from .report_builder import QUOTE_REQUEST_INTRO


QUOTE_REQUEST_TITLE = "ЗАПРОС КП"
MISSING_VALUE = "Просим указать в КП"

BASE_CONDITIONS = [
    "Срок поставки",
    "Город поставки",
    "Условия оплаты",
    "Документы качества",
    "Упаковка/тара",
]
OPTIONAL_CONDITIONS = [
    "Срок получения предложений",
    "Гарантия",
    "Срок изготовления",
    "Нормативное соответствие",
    "Реестровая запись Минпромторга",
]


async def build_quote_request_markdown_with_ai(
    settings: Any,
    source_text: str,
    *,
    subject: str = "",
    procurement_profile: dict | None = None,
) -> str:
    """Build supplier-facing quote request text, using AI only when tables are not recoverable."""
    if _extract_table_from_text(source_text):
        return build_quote_request_markdown(
            source_text,
            subject=subject,
            procurement_profile=procurement_profile,
        )

    if getattr(settings, "has_active_ai_provider", False):
        try:
            ai_markdown = await _build_quote_request_with_ai(
                settings,
                source_text,
                subject=subject,
            )
            if _extract_table_from_text(ai_markdown):
                return ai_markdown
        except Exception:
            pass

    return build_quote_request_markdown(
        source_text,
        subject=subject,
        procurement_profile=procurement_profile,
    )


def build_quote_request_markdown(
    source_text: str,
    *,
    subject: str = "",
    procurement_profile: dict | None = None,
) -> str:
    title = _quote_subject(source_text, subject=subject, procurement_profile=procurement_profile)
    table = _extract_table_from_text(source_text) or _table_from_profile(procurement_profile, title)
    conditions = _extract_conditions(source_text)
    return _compose_quote_request(title, table, conditions)


async def _build_quote_request_with_ai(settings: Any, source_text: str, *, subject: str = "") -> str:
    prompt = f"""Извлеки из ТЗ данные для supplier-facing документа "Запрос КП".

Нужно сохранить все товарные позиции, характеристики, единицы измерения, количества и важные условия поставки.
Не добавляй ОКПД2, КТРУ, внутренние комментарии анализа, ссылки на исходные файлы и служебные предупреждения.
Не придумывай значения. Если срока, города, количества, единицы измерения или документа качества нет, используй строку "{MISSING_VALUE}".

Ответ строго JSON:
{{
  "title": "краткое название предмета закупки",
  "items": [
    {{
      "name": "наименование",
      "characteristics": "характеристики, ГОСТ, размеры, марка",
      "unit": "единица измерения",
      "quantity": "количество"
    }}
  ],
  "conditions": {{
    "delivery_term": "срок поставки",
    "delivery_city": "город или место поставки",
    "payment_terms": "условия оплаты",
    "quality_documents": "документы качества",
    "packaging": "упаковка/тара",
    "proposal_deadline": "срок получения предложений",
    "warranty": "гарантия",
    "manufacturing_term": "срок изготовления",
    "normative_compliance": "нормативное соответствие",
    "minprom_registry": "реестровая запись Минпромторга"
  }}
}}

Предмет закупки: {subject or MISSING_VALUE}

ТЗ/отчёт:
{str(source_text or "")[:120000]}"""
    raw = await call_llm(
        settings,
        prompt,
        system_prompt="Ты закупочный аналитик. Готовишь точный Запрос КП для поставщика без выдуманных данных.",
        tier="primary",
        routing_key="supplier_tz_context_extraction",
        json_mode=True,
        timeout_seconds=180,
    )
    payload = parse_json_object(raw)
    title = _clean_cell(payload.get("title")) or subject or "Техническое задание"
    table = _table_from_ai_items(payload.get("items"), fallback_title=title)
    conditions = _conditions_from_ai_payload(payload.get("conditions"))
    return _compose_quote_request(title, table, conditions)


def _compose_quote_request(title: str, table: str, conditions: dict[str, str]) -> str:
    parts = [
        QUOTE_REQUEST_TITLE,
        "",
        QUOTE_REQUEST_INTRO,
        "",
        f"**{title or 'Техническое задание'}**",
        "",
        table.strip(),
        "",
        "### Условия поставки",
        "",
    ]
    for label in BASE_CONDITIONS:
        parts.append(f"- **{label}:** {_condition_value(conditions.get(label))}")
    for label in OPTIONAL_CONDITIONS:
        value = _condition_value(conditions.get(label), require_known=True)
        if value:
            parts.append(f"- **{label}:** {value}")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip()


def _extract_table_from_text(text: str) -> str:
    value = str(text or "")
    if not value.strip():
        return ""
    starts = []
    for pattern in (
        r"(?:#{2,5}\s*)?Товары и требования[^\n]*\n",
        r"(?:#{2,5}\s*)?Техническое задание[^\n]*\n",
        r"(?:#{2,5}\s*)?Спецификация[^\n]*\n",
        r"(?:#{2,5}\s*)?Описание объекта закупки[^\n]*\n",
    ):
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            starts.append(match.end())
    first_table = re.search(r"(?m)^\s*\|[^\n]*(?:Наименование|Товар|Позиция)[^\n]*\|\s*$", value)
    if first_table:
        starts.append(first_table.start())
    for start in starts or [0]:
        table = _collect_markdown_table(value[start:])
        if table:
            return table
    return ""


def _collect_markdown_table(text: str) -> str:
    lines = str(text or "").splitlines()
    table_lines: list[str] = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:-1]:
            in_table = True
            table_lines.append(stripped)
            continue
        if in_table:
            break
    if len(table_lines) < 3:
        return ""
    return _normalize_table(table_lines)


def _normalize_table(lines: list[str]) -> str:
    rows = [_parse_table_row(line) for line in lines]
    if len(rows) < 3:
        return ""
    header = [_normalize_header(cell) for cell in rows[0]]
    indexes = {
        "num": _find_header(header, ("№", "номер", "n")),
        "name": _find_header(header, ("наименование", "товар", "позиция", "предмет")),
        "characteristics": _find_header(header, ("характерист", "описание", "требован")),
        "unit": _find_header(header, ("ед.изм", "единица", "ед изм")),
        "quantity": _find_header(header, ("кол-во", "количество", "объем")),
    }
    if indexes["name"] is None:
        return _clean_classifier_text("\n".join(lines))

    result = [
        "| № | Наименование | Характеристики | Ед.изм. | Кол-во |",
        "|---|---|---|---|---|",
    ]
    for row_index, row in enumerate(rows[2:], start=1):
        name = _cell_at(row, indexes["name"])
        if not name or _looks_like_separator(name):
            continue
        num = _cell_at(row, indexes["num"]) or str(row_index)
        characteristics = _cell_at(row, indexes["characteristics"]) or MISSING_VALUE
        unit = _cell_at(row, indexes["unit"]) or MISSING_VALUE
        quantity = _cell_at(row, indexes["quantity"]) or MISSING_VALUE
        result.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in [num, name, characteristics, unit, quantity]
            )
            + " |"
        )
    if len(result) == 2:
        return ""
    return "\n".join(result)


def _table_from_ai_items(items: Any, *, fallback_title: str) -> str:
    rows = []
    if isinstance(items, list):
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            name = _clean_cell(item.get("name") or item.get("title"))
            if not name:
                continue
            rows.append(
                [
                    str(index),
                    name,
                    _clean_cell(item.get("characteristics") or item.get("description")) or MISSING_VALUE,
                    _clean_cell(item.get("unit")) or MISSING_VALUE,
                    _clean_cell(item.get("quantity") or item.get("count")) or MISSING_VALUE,
                ]
            )
    if not rows:
        rows = [["1", fallback_title or "Товар по ТЗ", MISSING_VALUE, MISSING_VALUE, MISSING_VALUE]]
    return _format_table(rows)


def _table_from_profile(procurement_profile: dict | None, title: str) -> str:
    rows = []
    profile = procurement_profile if isinstance(procurement_profile, dict) else {}
    items = profile.get("items") if isinstance(profile, dict) else []
    if isinstance(items, list):
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            name = _clean_cell(item.get("name") or item.get("title"))
            if not name:
                continue
            terms = _join_terms(item.get("exact_terms"), item.get("required_terms"))
            rows.append([str(index), name, terms or MISSING_VALUE, MISSING_VALUE, MISSING_VALUE])
    if not rows:
        rows = [["1", title or "Товар по ТЗ", _fallback_characteristics(title), MISSING_VALUE, MISSING_VALUE]]
    return _format_table(rows)


def _format_table(rows: list[list[str]]) -> str:
    lines = [
        "| № | Наименование | Характеристики | Ед.изм. | Кол-во |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        normalized_row = (row + [""] * 5)[:5]
        lines.append("| " + " | ".join(_markdown_cell(value) for value in normalized_row) + " |")
    return "\n".join(lines)


def _extract_conditions(text: str) -> dict[str, str]:
    source = _clean_classifier_text(text)
    return {
        "Срок поставки": _extract_condition(source, ("Срок поставки", "Срок исполнения", "Срок выполнения", "Период поставки")),
        "Город поставки": _extract_condition(source, ("Город поставки", "Место поставки", "Адрес поставки")),
        "Условия оплаты": _extract_condition(source, ("Условия оплаты", "Оплата", "Порядок оплаты")),
        "Документы качества": _extract_condition(source, ("Документы качества", "Сертификаты", "Паспорт качества")),
        "Упаковка/тара": _extract_condition(source, ("Упаковка/тара", "Упаковка", "Тара", "Маркировка")),
        "Срок получения предложений": _extract_condition(source, ("Срок получения предложений", "Срок предоставления КП", "КП до")),
        "Гарантия": _extract_condition(source, ("Гарантия", "Гарантийный срок")),
        "Срок изготовления": _extract_condition(source, ("Срок изготовления",)),
        "Нормативное соответствие": _extract_condition(source, ("Нормативное соответствие",)),
        "Реестровая запись Минпромторга": _extract_condition(source, ("Реестровая запись Минпромторга", "Минпромторг", "ГИСП")),
    }


def _conditions_from_ai_payload(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    mapping = {
        "Срок поставки": ("delivery_term", "delivery_terms", "supply_term"),
        "Город поставки": ("delivery_city", "delivery_place", "delivery_location"),
        "Условия оплаты": ("payment_terms", "payment"),
        "Документы качества": ("quality_documents", "quality_docs"),
        "Упаковка/тара": ("packaging", "package"),
        "Срок получения предложений": ("proposal_deadline", "kp_deadline", "quote_deadline"),
        "Гарантия": ("warranty",),
        "Срок изготовления": ("manufacturing_term",),
        "Нормативное соответствие": ("normative_compliance",),
        "Реестровая запись Минпромторга": ("minprom_registry", "gisp"),
    }
    result: dict[str, str] = {}
    for label, keys in mapping.items():
        for key in keys:
            value = _clean_cell(payload.get(key))
            if value:
                result[label] = value
                break
    return result


def _extract_condition(source: str, aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        pattern = rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?{re.escape(alias)}(?:\*\*)?\s*[:\-]\s*(.+?)\s*$"
        match = re.search(pattern, source)
        if not match:
            continue
        value = _clean_condition(match.group(1))
        if value and not _looks_like_separator(value):
            return value
    return ""


def _quote_subject(source_text: str, *, subject: str, procurement_profile: dict | None) -> str:
    explicit = _clean_cell(subject)
    if explicit:
        return explicit
    profile = procurement_profile if isinstance(procurement_profile, dict) else {}
    profile_summary = _clean_cell(profile.get("summary")) if isinstance(profile, dict) else ""
    if profile_summary:
        return profile_summary
    for pattern in (
        r"(?im)^\s*#\s+(.+?)\s*$",
        r"(?im)(?:предмет|объект)\s+закупк[ии]\s*[:\-]\s*(.+?)\s*$",
        r"(?im)(?:наименование\s+товара|номенклатура)\s*[:\-]\s*(.+?)\s*$",
    ):
        match = re.search(pattern, str(source_text or ""))
        if match:
            value = _clean_cell(match.group(1))
            if value:
                return value
    return "Техническое задание"


def _parse_table_row(line: str) -> list[str]:
    return [_clean_cell(cell) for cell in line.strip().strip("|").split("|")]


def _cell_at(row: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    return _clean_cell(row[index])


def _find_header(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    for index, header in enumerate(headers):
        if any(alias in header for alias in aliases):
            return index
    return None


def _normalize_header(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    normalized = normalized.replace("ед. изм.", "ед.изм").replace("ед.изм.", "ед.изм").replace("ед изм", "ед.изм")
    normalized = normalized.replace("количество", "кол-во")
    return normalized


def _join_terms(*values: Any) -> str:
    terms: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, list):
            candidates = [str(item) for item in value]
        else:
            candidates = []
        for candidate in candidates:
            cleaned = _clean_cell(candidate)
            if cleaned and cleaned.lower() not in [item.lower() for item in terms]:
                terms.append(cleaned)
    return "; ".join(terms)


def _fallback_characteristics(title: str) -> str:
    return f"Требования по загруженному ТЗ: {title}" if title else MISSING_VALUE


def _condition_value(value: str | None, *, require_known: bool = False) -> str:
    cleaned = _clean_condition(value)
    if cleaned and cleaned != MISSING_VALUE:
        return cleaned
    return "" if require_known else MISSING_VALUE


def _clean_condition(value: Any) -> str:
    cleaned = _clean_cell(value)
    if not cleaned:
        return ""
    cleaned = re.split(r"\s{2,}|\s+\|\s+", cleaned, maxsplit=1)[0].strip()
    return cleaned[:500].rstrip(" .,:;")


def _clean_cell(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`]+", "", text)
    text = _clean_classifier_text(text)
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip(" .,:;")
    return text


def _markdown_cell(value: str) -> str:
    cleaned = _clean_cell(value).replace("|", "/")
    return cleaned or ""


def _clean_classifier_text(text: Any) -> str:
    value = str(text or "")
    classifier = r"(?:ОКПД\s*2?|OKPD\s*2?|КТРУ|KTRU|Код\s+КТРУ)"
    value = re.sub(
        rf"\s*[\(\[]\s*(?:код\s+)?{classifier}\s*[:№#Nn\-–—]?\s*[\wА-Яа-яЁё.\s/-]+[\)\]]",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        rf"(?:код\s+)?{classifier}\s*[:№#Nn\-–—]?\s*[\wА-Яа-яЁё.\s/-]+(?=$|[\n;,.|])",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b\d{2}\.\d{2}\.\d{2}(?:\.\d{1,3}){0,3}\b", "", value)
    return value


def _looks_like_separator(value: str) -> bool:
    return bool(re.fullmatch(r"[:\-\s|]+", str(value or "")))
