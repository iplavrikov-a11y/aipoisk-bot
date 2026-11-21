from __future__ import annotations

import asyncio
import base64
import csv
import datetime as dt
import io
import logging
import re
import subprocess
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import ZoneInfo

import httpx
import openpyxl

from .ai import call_llm, custom_provider_map, parse_json_object
from .config import config
from .custom_batch_insights import clean_kontur_url
from .document_parser import clean_xml_compatible, extract_text, sanitize_filename
from .models import SystemSettings
from .procurement_sources import normalize_source_url, official_notice_number_from_url

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

logger = logging.getLogger(__name__)

IMAGE_REGISTRY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
TEXT_DOC_REGISTRY_EXTENSIONS = {".docx", ".doc", ".pdf", ".txt"}
ALLOWED_REGISTRY_EXTENSIONS = {".xlsx", ".xls", ".csv"} | TEXT_DOC_REGISTRY_EXTENSIONS | IMAGE_REGISTRY_EXTENSIONS
MAX_REGISTRY_BYTES = 15 * 1024 * 1024
MAX_ZIP_ENTRIES = 2500
MAX_ZIP_UNCOMPRESSED_BYTES = 80 * 1024 * 1024
MAX_REGISTRY_ITEMS = 200

COLUMN_MAPPING_SYSTEM_PROMPT = """Ты — ИИ-анализатор структуры закупочных таблиц.
Тебе переданы первые строки листа таблицы (индексы строк с 1, внутри каждой строки — массив ячеек с индексами колонок с 0).
Определи:
1) Является ли эта таблица перечнем/реестром тендеров (закупок), где у строк указаны номера извещений/закупок?
   ВАЖНО:
   - Обязателен ТОЛЬКО номер извещения/закупки (`notice_number`). Название закупки (`title`), НМЦК (`nmck`), даты и ссылки НЕ обязательны (например, в котировках НМЦК может отсутствовать, а в файле может быть вообще один столбец с номерами извещений).
   - Обычная товарная спецификация одного тендера (где колонки № п/п 1,2,3, Наименование товара, Кол-во, Ед.изм. без номеров извещений закупок) НЕ является реестром закупок (is_procurement_table = false).
2) С какой строки (data_start_row, нумерация с 1) начинаются сами строки закупок. Если заголовков нет и номера закупок идут прямо с 1-й строки — укажи `"data_start_row": 1`.
3) Индексы колонок (с 0, целое число или null, если такой колонки нет):
   - notice_number: номер извещения / реестровый номер / номер закупки (ОБЯЗАТЕЛЬНО)
   - title: название / наименование объекта закупки / предмет закупки (необязательно, null если нет)
   - nmck: НМЦ / НМЦК / начальная (максимальная) цена (необязательно, null если нет)
   - publication_date: дата публикации / размещения (необязательно)
   - deadline_date: дата и время окончания приема заявок / срок подачи заявок / подача заявок до (выбирай именно окончание приема заявок, НЕ путай с датой проведения отбора, аукциона или подведения итогов)
   - procurement_type: тип торгов / закон (44-ФЗ, 223-ФЗ, малые закупки и т.п., необязательно)
   - kontur_url: ссылка на Контур.Закупки (если вынесена в отдельный столбец, необязательно)
   - eis_url: ссылка на ЕИС (необязательно)
   - etp_url: ЭТП / ссылка на площадку (необязательно)
   - customer_inn: ИНН заказчика (необязательно)
   - customer_name: наименование заказчика (организатор / размещает закупку, необязательно)

Верни строго JSON без комментариев:
{
  "is_procurement_table": true,
  "data_start_row": 3,
  "columns": {
    "notice_number": 0,
    "title": 1,
    "nmck": 2,
    "publication_date": 7,
    "deadline_date": 8,
    "procurement_type": 11,
    "kontur_url": null,
    "eis_url": 12,
    "etp_url": 14,
    "customer_inn": 25,
    "customer_name": 24
  }
}"""

DOCX_REGISTRY_SYSTEM_PROMPT = """Ты — ИИ-анализатор закупочных документов.
Определи, является ли переданный документ списком/реестром тендеров (достаточно перечня номеров извещений; название закупки, НМЦК, даты и остальные поля НЕ обязательны и могут отсутствовать — например, в списке котировок или перечне из одних номеров), или это документация/ТЗ одной конкретной закупки.
Если это ТЗ/контракт/извещение ОДНОЙ закупки — верни {"is_procurement_table": false, "items": []}.
Если это список/таблица тендеров с номерами извещений — извлеки все закупки в JSON (отсутствующие необязательные поля оставляй пустыми / null):
{
  "is_procurement_table": true,
  "items": [
    {
      "notice_number": "строка номера извещения",
      "title": "наименование закупки или пусто",
      "nmck_value": null,
      "nmck_raw": "сумма или пусто",
      "publication_date": "ДД.ММ.ГГГГ или пусто",
      "deadline_date": "ДД.ММ.ГГГГ ЧЧ:ММ или пусто",
      "procurement_type": "44-ФЗ / 223-ФЗ / Малые закупки или пусто",
      "etp_url": "https://... или пусто",
      "customer_inn": "ИНН или пусто",
      "customer_name": "Заказчик или пусто"
    }
  ]
}"""


IMAGE_REGISTRY_SYSTEM_PROMPT = """Ты — ИИ-анализатор скриншотов и фотографий закупочных таблиц/документов.
Посмотри на изображение и определи:
- Если это скриншот или фото списка/реестра закупок (таблица тендеров, выгрузка из поисковика закупок, перечень номеров извещений ЕИС/ЭТП) — верни `"is_procurement_table": true` и максимально точно извлеки все строки закупок (особенно внимательно переписывай цифры номеров извещений!).
- Если это фото/скриншот ТЗ, спецификации товаров, договора или карточки ОДНОЙ закупки без списка других тендеров — верни `{"is_procurement_table": false, "items": []}`.
Ответ строго JSON без комментариев:
{
  "is_procurement_table": true,
  "items": [
    {
      "notice_number": "строка номера извещения",
      "title": "наименование закупки или пусто",
      "nmck_value": null,
      "nmck_raw": "сумма или пусто",
      "publication_date": "ДД.ММ.ГГГГ или пусто",
      "deadline_date": "ДД.ММ.ГГГГ ЧЧ:ММ или пусто",
      "procurement_type": "44-ФЗ / 223-ФЗ / Малые закупки или пусто",
      "etp_url": "https://... или пусто",
      "customer_inn": "ИНН или пусто",
      "customer_name": "Заказчик или пусто"
    }
  ]
}"""


@dataclass(frozen=True)
class RegistryPreviewResult:
    is_registry: bool
    filename: str
    sheet_name: str
    sheet_names: list[str]
    items: list[dict[str, Any]]
    requires_sheet_selection: bool = False
    selected_sheets: list[str] = field(default_factory=list)


def _validate_zip_container(raw_bytes: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise ValueError("Слишком много объектов внутри архива документа.")
            total_uncompressed = sum(max(0, info.file_size) for info in infos)
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError("Превышен допустимый размер содержимого файла.")
    except zipfile.BadZipFile as exc:
        raise ValueError("Файл повреждён или имеет некорректный формат.") from exc


def _unwrap_redirect_url(raw_url: str) -> tuple[str, str]:
    """Decode Kontur/export redirect wrapper into (primary_url, etp_url) safely."""
    cleaned = str(raw_url or "").strip()
    if not cleaned:
        return "", ""
    primary = normalize_source_url(cleaned)
    etp_link = ""
    try:
        parsed = urlparse(cleaned)
        query = parse_qs(parsed.query)
        if "url" in query and query["url"]:
            candidate = normalize_source_url(unquote(str(query["url"][0])))
            if candidate:
                primary = candidate
        if "metrics.EtpLink" in query and query["metrics.EtpLink"]:
            etp_candidate = normalize_source_url(unquote(str(query["metrics.EtpLink"][0])))
            if etp_candidate:
                etp_link = etp_candidate
    except Exception:
        pass
    return primary, etp_link


def _format_cell_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, dt.datetime):
        if val.hour == 0 and val.minute == 0 and val.second == 0:
            return val.strftime("%d.%m.%Y")
        return val.strftime("%d.%m.%Y %H:%M")
    if isinstance(val, dt.date):
        return val.strftime("%d.%m.%Y")
    return clean_xml_compatible(str(val)).strip()


_RU_DEADLINE_RE = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?:[,\sT]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
)
_ISO_DEADLINE_RE = re.compile(
    r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[T\s]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
)


def _format_msk_datetime_from_epoch(value: Any, *, with_time: bool = True) -> tuple[str, int | None]:
    if value in (None, "", False):
        return "", None
    try:
        numeric = float(value)
        if numeric <= 0:
            return "", None
        if numeric > 10_000_000_000:
            ms = int(round(numeric))
            sec = numeric / 1000.0
        else:
            sec = numeric
            ms = int(round(numeric * 1000.0))
        parsed = dt.datetime.fromtimestamp(sec, dt.timezone.utc).astimezone(MOSCOW_TZ)
        if not with_time:
            return parsed.strftime("%d.%m.%Y"), ms
        if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
            return parsed.strftime("%d.%m.%Y"), ms
        return parsed.strftime("%d.%m.%Y %H:%M"), ms
    except (TypeError, ValueError, OSError):
        return "", None


def parse_deadline_timestamp_ms(value: Any) -> int | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, dt.datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=MOSCOW_TZ)
        return int(round(aware.timestamp() * 1000))
    if isinstance(value, dt.date):
        aware = dt.datetime(value.year, value.month, value.day, tzinfo=MOSCOW_TZ)
        return int(round(aware.timestamp() * 1000))
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric <= 0:
            return None
        return int(round(numeric if numeric > 10_000_000_000 else numeric * 1000.0))

    raw = clean_xml_compatible(str(value)).strip()
    if not raw:
        return None
    cleaned = re.sub(r"\(?\s*(?:МСК|MSK|UTC\+?3)\s*\)?", "", raw, flags=re.IGNORECASE).strip()

    m_ru = _RU_DEADLINE_RE.search(cleaned)
    if m_ru:
        day, month, year = int(m_ru.group(1)), int(m_ru.group(2)), int(m_ru.group(3))
        if year < 100:
            year += 2000
        hour = int(m_ru.group(4) or 0)
        minute = int(m_ru.group(5) or 0)
        second = int(m_ru.group(6) or 0)
        try:
            aware = dt.datetime(year, month, day, hour, minute, second, tzinfo=MOSCOW_TZ)
            return int(round(aware.timestamp() * 1000))
        except ValueError:
            return None

    m_iso = _ISO_DEADLINE_RE.search(cleaned)
    if m_iso:
        year, month, day = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        hour = int(m_iso.group(4) or 0)
        minute = int(m_iso.group(5) or 0)
        second = int(m_iso.group(6) or 0)
        try:
            aware = dt.datetime(year, month, day, hour, minute, second, tzinfo=MOSCOW_TZ)
            return int(round(aware.timestamp() * 1000))
        except ValueError:
            return None

    try:
        iso_dt = dt.datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if iso_dt.tzinfo is None:
            iso_dt = iso_dt.replace(tzinfo=MOSCOW_TZ)
        return int(round(iso_dt.timestamp() * 1000))
    except ValueError:
        return None


def _parse_nmck(val: Any) -> tuple[float | None, str]:
    if val is None or val == "":
        return None, ""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        num = float(val)
        formatted = f"{num:,.2f}".replace(",", " ").replace(".", ",")
        if formatted.endswith(",00"):
            formatted = formatted[:-3]
        return num, f"{formatted} ₽"
    raw = _format_cell_value(val)
    if not raw:
        return None, ""
    cleaned_digits = (
        raw.replace("\xa0", "")
        .replace(" ", "")
        .replace("₽", "")
        .replace("руб.", "")
        .replace("руб", "")
        .replace("RUB", "")
        .replace(",", ".")
    )
    try:
        num = float(cleaned_digits)
        formatted = f"{num:,.2f}".replace(",", " ").replace(".", ",")
        if formatted.endswith(",00"):
            formatted = formatted[:-3]
        return num, f"{formatted} ₽"
    except ValueError:
        return None, raw


def _convert_xls_to_xlsx_bytes(raw_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="tlx_xls_") as tmpdir:
        tmp_path = Path(tmpdir)
        in_file = tmp_path / "input.xls"
        in_file.write_bytes(raw_bytes)
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(tmp_path),
                str(in_file),
            ],
            check=True,
            timeout=25,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        out_file = tmp_path / "input.xlsx"
        if not out_file.is_file():
            raise ValueError("Не удалось прочитать файл .xls. Сохраните таблицу в формате .xlsx.")
        return out_file.read_bytes()


def _col_int(cols: dict[str, Any], key: str, max_cols: int) -> int | None:
    val = cols.get(key)
    if isinstance(val, int) and not isinstance(val, bool) and 0 <= val < max_cols:
        return val
    return None


async def parse_procurement_registry_file(
    settings: SystemSettings,
    *,
    filename: str,
    content: bytes,
    requested_sheet: str = "",
    requested_sheets: list[str] | None = None,
) -> RegistryPreviewResult:
    safe_name = sanitize_filename(filename or "registry.xlsx")
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_REGISTRY_EXTENSIONS:
        return RegistryPreviewResult(False, safe_name, "", [], [])
    if not content or len(content) > MAX_REGISTRY_BYTES:
        raise ValueError("Файл пуст или превышает допустимый размер (15 МБ).")

    if suffix in IMAGE_REGISTRY_EXTENSIONS:
        return await _parse_image_registry(settings, safe_name, content)

    if suffix == ".docx":
        _validate_zip_container(content)
        return await _parse_text_document_registry(settings, safe_name, content, sheet_label="Документ")

    if suffix in TEXT_DOC_REGISTRY_EXTENSIONS:
        label = "PDF" if suffix == ".pdf" else ("Текст" if suffix == ".txt" else "Документ")
        return await _parse_text_document_registry(settings, safe_name, content, sheet_label=label)

    if suffix == ".csv":
        return await _parse_csv_registry(settings, safe_name, content)

    xlsx_bytes = _convert_xls_to_xlsx_bytes(content) if suffix == ".xls" else content
    _validate_zip_container(xlsx_bytes)
    return await _parse_xlsx_registry(
        settings,
        safe_name,
        xlsx_bytes,
        requested_sheet=requested_sheet,
        requested_sheets=requested_sheets,
    )


async def _map_sheet_columns_with_ai(
    settings: SystemSettings,
    sample_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = (
        "Определи структуру таблицы закупок по первым непустым строкам:\n"
        f"{sample_rows}"
    )
    raw = await call_llm(
        settings,
        prompt,
        system_prompt=COLUMN_MAPPING_SYSTEM_PROMPT,
        tier="light",
        json_mode=True,
        timeout_seconds=25.0,
        temperature=0.0,
    )
    parsed = parse_json_object(raw)
    return parsed if isinstance(parsed, dict) else {}


def _sheet_has_content(ws: Any) -> bool:
    max_r = min(ws.max_row or 0, 20)
    max_c = min(ws.max_column or 0, 25)
    for r in range(1, max_r + 1):
        for c in range(1, max_c + 1):
            if _format_cell_value(ws.cell(r, c).value):
                return True
    return False


async def _parse_xlsx_registry(
    settings: SystemSettings,
    safe_name: str,
    xlsx_bytes: bytes,
    *,
    requested_sheet: str = "",
    requested_sheets: list[str] | None = None,
) -> RegistryPreviewResult:
    wb_val = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=False)
    wb_link = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=False, read_only=False)
    all_sheets = list(wb_val.sheetnames)
    if not all_sheets:
        return RegistryPreviewResult(False, safe_name, "", [], [])

    non_empty_sheets = [name for name in all_sheets if _sheet_has_content(wb_val[name])]
    sheet_names = non_empty_sheets or all_sheets

    explicit_sheets: list[str] = []
    normalized_sheet_lookup: dict[str, str] = {}
    for actual_name in all_sheets:
        norm_key = " ".join(str(actual_name).split())
        if norm_key and norm_key not in normalized_sheet_lookup:
            normalized_sheet_lookup[norm_key] = actual_name

    def _resolve_sheet_name(candidate: str) -> str | None:
        raw_c = str(candidate or "")
        if raw_c in all_sheets:
            return raw_c
        stripped_c = raw_c.strip()
        if stripped_c in all_sheets:
            return stripped_c
        return normalized_sheet_lookup.get(" ".join(raw_c.split()))

    had_explicit_request = bool(requested_sheets or str(requested_sheet or "").strip())
    if requested_sheets:
        seen_s: set[str] = set()
        for name in requested_sheets:
            matched_s = _resolve_sheet_name(str(name or ""))
            if matched_s and matched_s not in seen_s:
                seen_s.add(matched_s)
                explicit_sheets.append(matched_s)
    elif requested_sheet:
        matched_single = _resolve_sheet_name(requested_sheet)
        if matched_single:
            explicit_sheets = [matched_single]

    if had_explicit_request and not explicit_sheets:
        return RegistryPreviewResult(
            is_registry=False,
            filename=safe_name,
            sheet_name="",
            sheet_names=sheet_names,
            items=[],
            requires_sheet_selection=False,
            selected_sheets=[],
        )

    if not explicit_sheets and len(sheet_names) > 1:
        return RegistryPreviewResult(
            is_registry=True,
            filename=safe_name,
            sheet_name="",
            sheet_names=sheet_names,
            items=[],
            requires_sheet_selection=True,
            selected_sheets=[],
        )

    sheets_to_parse = explicit_sheets or [sheet_names[0]]
    items: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for chosen_sheet in sheets_to_parse:
        if len(items) >= MAX_REGISTRY_ITEMS:
            break
        ws_val = wb_val[chosen_sheet]
        ws_link = wb_link[chosen_sheet]
        max_row = min(ws_val.max_row or 0, 1000)
        max_col = min(ws_val.max_column or 0, 60)
        if max_row < 1 or max_col < 1:
            continue

        sample_rows: list[dict[str, Any]] = []
        for r in range(1, min(max_row + 1, 12)):
            vals = [_format_cell_value(ws_val.cell(r, c).value)[:120] for c in range(1, max_col + 1)]
            if any(vals):
                sample_rows.append({"row": r, "cells": vals})
            if len(sample_rows) >= 6:
                break

        if not sample_rows:
            continue

        mapping = await _map_sheet_columns_with_ai(settings, sample_rows)
        if not mapping.get("is_procurement_table"):
            continue

        cols = mapping.get("columns") if isinstance(mapping.get("columns"), dict) else {}
        col_num = _col_int(cols, "notice_number", max_col)
        if col_num is None:
            continue

        col_title = _col_int(cols, "title", max_col)
        col_nmck = _col_int(cols, "nmck", max_col)
        col_pub = _col_int(cols, "publication_date", max_col)
        col_dead = _col_int(cols, "deadline_date", max_col)
        col_type = _col_int(cols, "procurement_type", max_col)
        col_kontur = _col_int(cols, "kontur_url", max_col)
        col_eis = _col_int(cols, "eis_url", max_col)
        col_etp = _col_int(cols, "etp_url", max_col)
        col_inn = _col_int(cols, "customer_inn", max_col)
        col_cust = _col_int(cols, "customer_name", max_col)
        default_start = 1 if max_row == 1 else 2
        start_row = max(1, int(mapping.get("data_start_row") or default_start))

        for r in range(start_row, max_row + 1):
            raw_num = _format_cell_value(ws_val.cell(r, col_num + 1).value)
            if not raw_num:
                continue
            title = _format_cell_value(ws_val.cell(r, col_title + 1).value) if col_title is not None else ""
            nmck_val, nmck_raw = (
                _parse_nmck(ws_val.cell(r, col_nmck + 1).value) if col_nmck is not None else (None, "")
            )
            pub_date = _format_cell_value(ws_val.cell(r, col_pub + 1).value) if col_pub is not None else ""
            dead_date = _format_cell_value(ws_val.cell(r, col_dead + 1).value) if col_dead is not None else ""
            proc_type = _format_cell_value(ws_val.cell(r, col_type + 1).value) if col_type is not None else ""
            cust_inn = _format_cell_value(ws_val.cell(r, col_inn + 1).value) if col_inn is not None else ""
            cust_name = _format_cell_value(ws_val.cell(r, col_cust + 1).value) if col_cust is not None else ""

            kontur_url = ""
            eis_url = ""
            etp_url = ""
            checked_cols: set[int] = set()
            for idx_col in (col_num, col_kontur, col_title, col_eis, col_etp):
                if idx_col is None or idx_col in checked_cols:
                    continue
                checked_cols.add(idx_col)
                lcell = ws_link.cell(r, idx_col + 1)
                target = str(lcell.hyperlink.target or "").strip() if lcell.hyperlink else ""
                if not target and isinstance(lcell.value, str) and "http" in lcell.value:
                    target = lcell.value
                if target:
                    primary_u, etp_u = _unwrap_redirect_url(target)
                    if "kontur.ru" in primary_u.lower() and not kontur_url:
                        kontur_url = clean_kontur_url(primary_u)
                    elif "zakupki.gov.ru" in primary_u and not eis_url:
                        eis_url = primary_u
                    elif primary_u and "kontur.ru" not in primary_u.lower() and not etp_url:
                        etp_url = primary_u
                    if etp_u and not etp_url:
                        etp_url = etp_u

            # Fallback scan: if Kontur link lives in another column's hyperlink or text, capture it too.
            if not kontur_url:
                for c_idx in range(max_col):
                    if c_idx in checked_cols:
                        continue
                    lcell = ws_link.cell(r, c_idx + 1)
                    target = str(lcell.hyperlink.target or "").strip() if lcell.hyperlink else ""
                    if not target and isinstance(lcell.value, str) and "kontur.ru" in lcell.value.lower():
                        target = lcell.value
                    if target and "kontur.ru" in target.lower():
                        primary_u, _ = _unwrap_redirect_url(target)
                        if "kontur.ru" in primary_u.lower():
                            kontur_url = clean_kontur_url(primary_u)
                            if kontur_url:
                                break

            dedup_key = f"{raw_num}::{title[:60]}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            items.append(
                {
                    "id": uuid.uuid4().hex[:12],
                    "row_no": len(items) + 1,
                    "sheet_name": chosen_sheet,
                    "notice_number": raw_num[:80],
                    "title": (title or f"Закупка {raw_num}")[:500],
                    "nmck_value": nmck_val,
                    "nmck_raw": nmck_raw[:80],
                    "publication_date": pub_date[:60],
                    "deadline_date": dead_date[:60],
                    "deadline_ts": parse_deadline_timestamp_ms(dead_date),
                    "procurement_type": proc_type[:80],
                    "kontur_url": kontur_url[:1000],
                    "eis_url": eis_url[:1000],
                    "etp_url": etp_url[:1000],
                    "customer_inn": cust_inn[:40],
                    "customer_name": cust_name[:300],
                }
            )
            if len(items) >= MAX_REGISTRY_ITEMS:
                break

    display_sheet = sheets_to_parse[0] if len(sheets_to_parse) == 1 else ", ".join(sheets_to_parse)
    return RegistryPreviewResult(
        is_registry=bool(items),
        filename=safe_name,
        sheet_name=display_sheet,
        sheet_names=sheet_names,
        items=items,
        requires_sheet_selection=False,
        selected_sheets=sheets_to_parse,
    )


async def _parse_csv_registry(
    settings: SystemSettings,
    safe_name: str,
    raw_bytes: bytes,
) -> RegistryPreviewResult:
    decoded = ""
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            decoded = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not decoded.strip():
        return RegistryPreviewResult(False, safe_name, "CSV", ["CSV"], [])
    sample = decoded[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(decoded), dialect))[:500]
    if len(rows) < 1:
        return RegistryPreviewResult(False, safe_name, "CSV", ["CSV"], [])
    max_col = max((len(r) for r in rows), default=0)
    sample_rows = [
        {"row": idx + 1, "cells": [clean_xml_compatible(c).strip()[:120] for c in r[:50]]}
        for idx, r in enumerate(rows[:8])
        if any(str(c).strip() for c in r)
    ][:6]
    mapping = await _map_sheet_columns_with_ai(settings, sample_rows)
    if not mapping.get("is_procurement_table"):
        return RegistryPreviewResult(False, safe_name, "CSV", ["CSV"], [])
    cols = mapping.get("columns") if isinstance(mapping.get("columns"), dict) else {}
    col_num = _col_int(cols, "notice_number", max_col)
    if col_num is None:
        return RegistryPreviewResult(False, safe_name, "CSV", ["CSV"], [])
    col_title = _col_int(cols, "title", max_col)
    col_nmck = _col_int(cols, "nmck", max_col)
    col_pub = _col_int(cols, "publication_date", max_col)
    col_dead = _col_int(cols, "deadline_date", max_col)
    col_type = _col_int(cols, "procurement_type", max_col)
    col_kontur = _col_int(cols, "kontur_url", max_col)
    default_csv_start = 1 if len(rows) == 1 else 2
    start_idx = max(0, int(mapping.get("data_start_row") or default_csv_start) - 1)
    items: list[dict[str, Any]] = []
    for r in rows[start_idx:]:
        raw_num = clean_xml_compatible(r[col_num]).strip() if col_num < len(r) else ""
        if not raw_num:
            continue
        title = clean_xml_compatible(r[col_title]).strip() if col_title is not None and col_title < len(r) else ""
        nmck_val, nmck_raw = _parse_nmck(r[col_nmck]) if col_nmck is not None and col_nmck < len(r) else (None, "")
        pub_date = clean_xml_compatible(r[col_pub]).strip() if col_pub is not None and col_pub < len(r) else ""
        dead_date = clean_xml_compatible(r[col_dead]).strip() if col_dead is not None and col_dead < len(r) else ""
        proc_type = clean_xml_compatible(r[col_type]).strip() if col_type is not None and col_type < len(r) else ""
        kontur_url = ""
        if col_kontur is not None and col_kontur < len(r):
            raw_k = clean_xml_compatible(r[col_kontur]).strip()
            if raw_k and "kontur.ru" in raw_k.lower():
                primary_k, _ = _unwrap_redirect_url(raw_k)
                kontur_url = clean_kontur_url(primary_k)
        if not kontur_url:
            for cell_val in r:
                s_val = clean_xml_compatible(cell_val).strip()
                if s_val and "kontur.ru" in s_val.lower() and "http" in s_val.lower():
                    primary_k, _ = _unwrap_redirect_url(s_val)
                    kontur_url = clean_kontur_url(primary_k)
                    if kontur_url:
                        break
        items.append(
            {
                "id": uuid.uuid4().hex[:12],
                "row_no": len(items) + 1,
                "notice_number": raw_num[:80],
                "title": (title or f"Закупка {raw_num}")[:500],
                "nmck_value": nmck_val,
                "nmck_raw": nmck_raw[:80],
                "publication_date": pub_date[:60],
                "deadline_date": dead_date[:60],
                "deadline_ts": parse_deadline_timestamp_ms(dead_date),
                "procurement_type": proc_type[:80],
                "kontur_url": kontur_url[:1000],
                "eis_url": "",
                "etp_url": "",
                "customer_inn": "",
                "customer_name": "",
            }
        )
        if len(items) >= MAX_REGISTRY_ITEMS:
            break
    return RegistryPreviewResult(bool(items), safe_name, "CSV", ["CSV"], items)


def _build_registry_result_from_llm_payload(
    parsed: Any,
    safe_name: str,
    sheet_label: str,
) -> RegistryPreviewResult:
    if not isinstance(parsed, dict) or not parsed.get("is_procurement_table"):
        return RegistryPreviewResult(False, safe_name, sheet_label, [sheet_label], [])
    raw_items = parsed.get("items") if isinstance(parsed.get("items"), list) else []
    items: list[dict[str, Any]] = []
    seen_nums: set[str] = set()
    for item in raw_items[:MAX_REGISTRY_ITEMS]:
        if not isinstance(item, dict):
            continue
        num = clean_xml_compatible(str(item.get("notice_number") or "")).strip()
        if not num:
            continue
        dedupe_key = num.lower()
        if dedupe_key in seen_nums:
            continue
        seen_nums.add(dedupe_key)
        nmck_val, nmck_raw = _parse_nmck(item.get("nmck_value") or item.get("nmck_raw"))
        if item.get("nmck_raw") and not nmck_raw:
            nmck_raw = clean_xml_compatible(str(item.get("nmck_raw"))).strip()
        etp_u = normalize_source_url(str(item.get("etp_url") or "").strip())
        eis_u = normalize_source_url(str(item.get("eis_url") or "").strip())
        kontur_u = clean_kontur_url(str(item.get("kontur_url") or "").strip())
        if not kontur_u and "kontur.ru" in etp_u.lower():
            kontur_u = clean_kontur_url(etp_u)
            etp_u = ""
        items.append(
            {
                "id": uuid.uuid4().hex[:12],
                "row_no": len(items) + 1,
                "notice_number": num[:80],
                "title": (clean_xml_compatible(str(item.get("title") or "")).strip() or f"Закупка {num}")[:500],
                "nmck_value": nmck_val,
                "nmck_raw": nmck_raw[:80],
                "publication_date": clean_xml_compatible(str(item.get("publication_date") or "")).strip()[:60],
                "deadline_date": clean_xml_compatible(str(item.get("deadline_date") or "")).strip()[:60],
                "deadline_ts": parse_deadline_timestamp_ms(item.get("deadline_date")),
                "procurement_type": clean_xml_compatible(str(item.get("procurement_type") or "")).strip()[:80],
                "kontur_url": kontur_u[:1000],
                "eis_url": eis_u[:1000],
                "etp_url": etp_u[:1000],
                "customer_inn": clean_xml_compatible(str(item.get("customer_inn") or "")).strip()[:40],
                "customer_name": clean_xml_compatible(str(item.get("customer_name") or "")).strip()[:300],
            }
        )
    return RegistryPreviewResult(bool(items), safe_name, sheet_label, [sheet_label], items)


async def _parse_text_document_registry(
    settings: SystemSettings,
    safe_name: str,
    raw_bytes: bytes,
    *,
    sheet_label: str = "Документ",
) -> RegistryPreviewResult:
    with tempfile.TemporaryDirectory(prefix="tlx_doc_") as tmpdir:
        doc_path = Path(tmpdir) / safe_name
        doc_path.write_bytes(raw_bytes)
        extracted, _ = extract_text(doc_path)
    if not extracted or len(extracted.strip()) < 7:
        return RegistryPreviewResult(False, safe_name, sheet_label, [sheet_label], [])
    raw = await call_llm(
        settings,
        f"Извлеки реестр закупок из документа:\n\n{extracted[:60000]}",
        system_prompt=DOCX_REGISTRY_SYSTEM_PROMPT,
        tier="light",
        json_mode=True,
        timeout_seconds=40.0,
        temperature=0.0,
    )
    parsed = parse_json_object(raw)
    return _build_registry_result_from_llm_payload(parsed, safe_name, sheet_label)


async def _parse_docx_registry(
    settings: SystemSettings,
    safe_name: str,
    raw_bytes: bytes,
) -> RegistryPreviewResult:
    return await _parse_text_document_registry(settings, safe_name, raw_bytes, sheet_label="Документ")


async def _extract_registry_json_with_vision(
    settings: SystemSettings,
    image_bytes: bytes,
    mime_type: str,
) -> dict[str, Any] | None:
    providers = custom_provider_map(settings)
    gemini_prov = providers.get("gemini")
    if not gemini_prov:
        return None
    raw_base = str(gemini_prov.get("baseUrl") or "http://127.0.0.1:8318/v1").strip().rstrip("/")
    if raw_base.endswith("/v1"):
        raw_base = raw_base[:-3]
    api_key = str(gemini_prov.get("apiKey") or "").strip()
    if not api_key:
        return None
    light_model = str(getattr(settings, "light_model", "") or "").strip()
    candidates = list(
        dict.fromkeys(
            m
            for m in [light_model, "gemini-3.8-flash-high", "gemini-3-flash", "gemini-2.5-flash"]
            if m and "gemini" in m.lower()
        )
    )
    if not candidates:
        candidates = ["gemini-3.8-flash-high", "gemini-3-flash"]

    b64_data = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "systemInstruction": {"parts": [{"text": IMAGE_REGISTRY_SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": "Проанализируй изображение и верни строго JSON."},
                    {"inlineData": {"mimeType": mime_type, "data": b64_data}},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            for model_id in candidates[:3]:
                resp = await client.post(
                    f"{raw_base}/v1beta/models/{model_id}:generateContent",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code >= 400:
                    continue
                data = resp.json()
                cands = data.get("candidates") if isinstance(data, dict) else None
                if not isinstance(cands, list) or not cands:
                    continue
                parts = ((cands[0].get("content") or {}).get("parts") or [])
                raw_text = "\n".join(str(p.get("text") or "") for p in parts if isinstance(p, dict)).strip()
                parsed = parse_json_object(raw_text)
                if isinstance(parsed, dict):
                    return parsed
    except Exception as exc:
        logger.debug("Vision registry extraction fallback to OCR: %s", exc)
    return None


async def _parse_image_registry(
    settings: SystemSettings,
    safe_name: str,
    raw_bytes: bytes,
) -> RegistryPreviewResult:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 45_000_000
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            normalized = ImageOps.exif_transpose(img)
            if normalized.mode not in ("RGB", "L"):
                normalized = normalized.convert("RGB")
            w, h = normalized.size
            if max(w, h) > 2048:
                ratio = 2048.0 / float(max(w, h))
                normalized = normalized.resize(
                    (max(1, int(w * ratio)), max(1, int(h * ratio))),
                    Image.Resampling.LANCZOS,
                )
            buf = io.BytesIO()
            normalized.save(buf, format="JPEG", quality=90, optimize=True)
            prepared_jpeg = buf.getvalue()
    except Exception as exc:
        raise ValueError("Не удалось прочитать изображение. Проверьте, что файл не повреждён.") from exc

    vision_parsed = await _extract_registry_json_with_vision(settings, prepared_jpeg, "image/jpeg")
    if isinstance(vision_parsed, dict):
        return _build_registry_result_from_llm_payload(vision_parsed, safe_name, "Изображение")

    # Fallback: OCR via document_parser + standard LLM extraction
    return await _parse_text_document_registry(settings, safe_name, raw_bytes, sheet_label="Изображение")


_ALPHA_NOTICE_RE = re.compile(r"^[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9\-_/]{4,40}$")


def parse_procurement_text_list(raw_text: str) -> RegistryPreviewResult:
    """Parse notice numbers and/or URLs separated by commas, semicolons, newlines, or whitespace."""
    cleaned = clean_xml_compatible(str(raw_text or "")).strip()
    if not cleaned:
        return RegistryPreviewResult(False, "Список извещений", "Текстовый ввод", ["Текстовый ввод"], [])

    tokens = [
        tok.strip(" \t\r\n,;\"'«»()[]")
        for tok in re.split(r"[\r\n,;|\t ]+", cleaned)
    ]
    items: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for tok in tokens:
        if not tok:
            continue
        if tok.lower() in {"№", "n", "извещение", "закупка", "номер"}:
            continue
        tok = re.sub(r"^(?:№|#)+", "", tok).strip()
        if not tok:
            continue

        notice_number = ""
        kontur_url = ""
        eis_url = ""
        etp_url = ""
        proc_type = ""

        if tok.lower().startswith(("http://", "https://")):
            primary_u, extra_etp = _unwrap_redirect_url(tok)
            if not primary_u:
                continue
            if "kontur.ru" in primary_u.lower():
                kontur_url = clean_kontur_url(primary_u)
            elif "zakupki.gov.ru" in primary_u:
                eis_url = primary_u
                notice_number = official_notice_number_from_url(primary_u)
                proc_type = "ЕИС"
            else:
                etp_url = primary_u
            if extra_etp and not etp_url:
                etp_url = extra_etp
            if not notice_number:
                m_urls = re.findall(r"(?:[?&](?:id|regNumber)=|/need/|/)([A-Za-z0-9\-]*\d[A-Za-z0-9\-]{3,24})(?=[/?#]|$)", primary_u)
                if m_urls:
                    notice_number = m_urls[-1]
            if not notice_number:
                notice_number = primary_u[:80]
        else:
            digits = re.sub(r"\D+", "", tok)
            if not digits or len(digits) < 5 or not _ALPHA_NOTICE_RE.match(tok):
                continue
            notice_number = tok[:80]
            if digits == notice_number:
                if len(digits) == 19:
                    proc_type = "44-ФЗ"
                elif len(digits) == 11:
                    proc_type = "223-ФЗ"
                elif 6 <= len(digits) <= 9:
                    proc_type = "Малая закупка"

        dedup_key = f"{notice_number}::{kontur_url or eis_url or etp_url}".lower()
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        items.append(
            {
                "id": uuid.uuid4().hex[:12],
                "row_no": len(items) + 1,
                "notice_number": notice_number,
                "title": f"Закупка {notice_number}",
                "nmck_value": None,
                "nmck_raw": "",
                "publication_date": "",
                "deadline_date": "",
                "deadline_ts": None,
                "procurement_type": proc_type,
                "kontur_url": kontur_url[:1000],
                "eis_url": eis_url[:1000],
                "etp_url": etp_url[:1000],
                "customer_inn": "",
                "customer_name": "",
            }
        )
        if len(items) >= MAX_REGISTRY_ITEMS:
            break

    return RegistryPreviewResult(bool(items), "Список извещений", "Текстовый ввод", ["Текстовый ввод"], items)


def _extract_search_candidates(payload: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            tid = str(node.get("_id") or node.get("id") or "").strip()
            if tid and (node.get("number") or node.get("orderName")) and tid not in seen_ids:
                seen_ids.add(tid)
                candidates.append(node)
            for val in node.values():
                _walk(val)
        elif isinstance(node, list):
            for elem in node:
                _walk(elem)

    _walk(payload)
    return candidates


def _pick_best_search_match(candidates: list[dict[str, Any]], notice_number: str) -> dict[str, Any] | None:
    if not candidates:
        return None
    exact = str(notice_number or "").strip()
    digits = re.sub(r"\D+", "", exact)
    exact_matches = [c for c in candidates if str(c.get("number") or "").strip() == exact]
    if not exact_matches and digits:
        exact_matches = [
            c
            for c in candidates
            if re.sub(r"\D+", "", str(c.get("number") or "").strip()) == digits
        ]
    pool = exact_matches or (candidates if len(candidates) == 1 else [])
    if not pool:
        return None
    pool.sort(
        key=lambda c: (
            1 if c.get("submissionCloseDateTime") else 0,
            1 if c.get("status") == 1 else 0,
            1 if c.get("maxPrice") is not None else 0,
            1 if c.get("orderName") else 0,
        ),
        reverse=True,
    )
    return pool[0]


async def enrich_registry_preview_items(
    items: list[dict[str, Any]],
    *,
    max_items: int = 60,
    total_timeout_seconds: float = 8.0,
) -> list[dict[str, Any]]:
    """Enrich parsed registry preview rows with live source metadata (deadline_date, price, title) when missing.

    Never reads/writes a cache: every preview enrichment runs live against the source API.
    """
    if not items:
        return items

    needs_enrichment: list[dict[str, Any]] = []
    for it in items:
        if it.get("deadline_ts") is None and it.get("deadline_date"):
            it["deadline_ts"] = parse_deadline_timestamp_ms(it.get("deadline_date"))
        notice_num = str(it.get("notice_number") or "").strip()
        raw_title = str(it.get("title") or "").strip()
        missing_deadline = not str(it.get("deadline_date") or "").strip()
        missing_title = not raw_title or raw_title == f"Закупка {notice_num}"
        missing_price = it.get("nmck_value") is None and not str(it.get("nmck_raw") or "").strip()
        if notice_num and (missing_deadline or missing_title or missing_price):
            needs_enrichment.append(it)

    token = str(config.tenderplan_api_token or "").strip()
    if not token or not needs_enrichment:
        return items

    base_url = str(config.tenderplan_base_url or "https://tenderplan.ru").rstrip("/")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    sem = asyncio.Semaphore(6)

    async def _enrich_one(client: httpx.AsyncClient, item: dict[str, Any]) -> None:
        exact_num = str(item.get("notice_number") or "").strip()
        digits = re.sub(r"\D+", "", exact_num)
        if not digits or len(digits) < 6:
            return
        queries = [exact_num]
        if digits != exact_num:
            queries.append(digits)

        matched: dict[str, Any] | None = None
        async with sem:
            for q_num in queries:
                try:
                    resp = await client.get(f"{base_url}/api/search/tender", params={"number": q_num})
                    if resp.status_code >= 400:
                        continue
                    cands = _extract_search_candidates(resp.json())
                    matched = _pick_best_search_match(cands, exact_num)
                    if matched is not None:
                        break
                except Exception:
                    continue

        if not matched:
            return

        if not str(item.get("deadline_date") or "").strip():
            dead_str, dead_ms = _format_msk_datetime_from_epoch(
                matched.get("submissionCloseDateTime"), with_time=True
            )
            if dead_str:
                item["deadline_date"] = dead_str[:60]
                item["deadline_ts"] = dead_ms

        if not str(item.get("publication_date") or "").strip():
            pub_str, _ = _format_msk_datetime_from_epoch(
                matched.get("publicationDateTime"), with_time=False
            )
            if pub_str:
                item["publication_date"] = pub_str[:60]

        cur_title = str(item.get("title") or "").strip()
        order_name = clean_xml_compatible(str(matched.get("orderName") or "")).strip()
        if order_name and (not cur_title or cur_title == f"Закупка {exact_num}"):
            item["title"] = order_name[:500]

        if item.get("nmck_value") is None and not str(item.get("nmck_raw") or "").strip():
            max_price = matched.get("maxPrice")
            if max_price not in (None, ""):
                nmck_val, nmck_raw = _parse_nmck(max_price)
                if nmck_val is not None:
                    item["nmck_value"] = nmck_val
                    item["nmck_raw"] = nmck_raw[:80]

        if not str(item.get("customer_name") or "").strip():
            customers = matched.get("customers")
            if isinstance(customers, list):
                names = [
                    clean_xml_compatible(str(c.get("name") or "")).strip()
                    for c in customers
                    if isinstance(c, dict) and str(c.get("name") or "").strip()
                ]
                if names:
                    item["customer_name"] = "; ".join(names)[:300]

        if not str(item.get("eis_url") or "").strip():
            href = normalize_source_url(str(matched.get("href") or "").strip())
            if href and "zakupki.gov.ru" in href:
                item["eis_url"] = href[:1000]

    try:
        async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
            tasks = [_enrich_one(client, it) for it in needs_enrichment[:max_items]]
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=total_timeout_seconds)
    except Exception:
        pass

    return items
