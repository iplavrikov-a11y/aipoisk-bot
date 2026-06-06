from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from .config import config
from .document_parser import sanitize_filename

MSK = ZoneInfo("Europe/Moscow")
TENDERPLAN_BASE_URL = "https://tenderplan.ru"
DOWNLOAD_ALLOWED_HOSTS = {"zakupki.gov.ru"}
DOWNLOAD_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DICTIONARY_CACHE_TTL_SECONDS = 6 * 60 * 60
TENDERPLAN_PLACING_WAY_LABELS = {
    "0": "Иной способ",
    "1": "Открытый конкурс",
    "2": "Открытый аукцион",
    "3": "Открытый аукцион в электронной форме",
    "4": "Запрос котировок",
    "5": "Предварительный отбор",
    "6": "Закупка у единственного поставщика",
    "7": "Конкурс с ограниченным участием",
    "8": "Двухэтапный конкурс",
    "9": "Закрытый конкурс",
    "10": "Закрытый конкурс с ограниченным участием",
    "11": "Закрытый двухэтапный конкурс",
    "12": "Закрытый аукцион",
    "13": "Запрос котировок без размещения извещения",
    "14": "Запрос предложений",
    "15": "Электронный аукцион",
    "16": "Иной многолотовый способ",
    "17": "Сообщение о заинтересованности в проведении открытого конкурса",
    "18": "Иной однолотовый способ",
    "19": "Редукцион",
    "20": "Переторжка",
    "21": "Конкурентные переговоры",
    "22": "Запрос котировок в электронной форме",
    "23": "Открытый конкурс в электронной форме",
    "24": "Запрос предложений в электронной форме",
    "25": "Конкурс с ограниченным участием в электронной форме",
    "26": "Двухэтапный конкурс в электронной форме",
    "27": "Запрос цен товаров, работ, услуг",
    "28": "Голландский аукцион",
    "29": "Публичное предложение",
    "30": "Закупки малого объема",
}
TENDERPLAN_STATUS_LABELS = {
    "0": "Неизвестно",
    "1": "Прием заявок",
    "2": "Работа комиссии",
    "3": "Размещение завершено",
    "4": "Размещение отменено",
    "5": "Размещение не состоялось",
    "6": "Исполнение завершено",
    "7": "Исполняется",
    "8": "Расторжение",
}
TENDERPLAN_TOOL_DICTIONARIES = {
    "placingways": ("/api/tools/placingways/list", TENDERPLAN_PLACING_WAY_LABELS),
    "statuses": ("/api/tools/statuses/list", TENDERPLAN_STATUS_LABELS),
}


@dataclass(frozen=True)
class TenderplanAttachment:
    name: str
    href: str
    category: str = "documentation"
    size: int | None = None
    publication_date_time: int | None = None


@dataclass(frozen=True)
class TenderplanDownloadedFile:
    filename: str
    content: bytes
    category: str
    source_url: str
    size: int
    document_type: str = "other"
    document_type_source: str = "unknown"
    document_type_confidence: float = 0.0
    content_document_types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TenderplanFetchResult:
    ok: bool
    status: str
    context: str = ""
    notice_number: str = ""
    tender_id: str = ""
    error: str = ""
    downloaded_files: list[TenderplanDownloadedFile] = field(default_factory=list)
    failed_downloads: list[dict] = field(default_factory=list)
    service_schema_version: str = ""
    warnings: list[str] = field(default_factory=list)
    document_hints: dict = field(default_factory=dict)


class TenderplanError(RuntimeError):
    pass


def fetch_tenderplan_source_sync(notice_number: str) -> TenderplanFetchResult:
    service_result = fetch_tender_source_service_sync(notice_number)
    if service_result is not None:
        if service_result.ok or service_result.status in {"invalid_number", "not_found"}:
            return service_result

    token = str(config.tenderplan_api_token or "").strip()
    if not token:
        if service_result is not None:
            return TenderplanFetchResult(
                ok=False,
                status=service_result.status or "failed",
                notice_number=notice_number,
                error=f"{service_result.error}; резервный локальный источник закупок не настроен".strip("; "),
            )
        return TenderplanFetchResult(
            ok=False,
            status="not_configured",
            notice_number=notice_number,
            error="Источник закупок по номеру извещения не настроен",
        )

    client = TenderplanClient(token=token, base_url=config.tenderplan_base_url or TENDERPLAN_BASE_URL)
    try:
        return client.fetch_procurement(notice_number)
    except TenderplanError as exc:
        return TenderplanFetchResult(ok=False, status="failed", notice_number=notice_number, error=str(exc))


def fetch_tender_source_service_sync(notice_number: str) -> TenderplanFetchResult | None:
    base_url = str(config.tender_source_service_url or "").strip().rstrip("/")
    if not base_url:
        return None
    try:
        timeout = float(config.tender_source_service_timeout_seconds or 60)
    except (TypeError, ValueError):
        timeout = 60.0
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.post(f"{base_url}/v1/procurements/{notice_number}/bundle", params={"download": "true"})
            response.raise_for_status()
            payload = response.json()
            files, file_errors = load_tender_source_service_files(client, base_url, payload.get("files") or [])
    except Exception as exc:
        return TenderplanFetchResult(
            ok=False,
            status="service_failed",
            notice_number=notice_number,
            error=f"Общий сервис источников закупок недоступен: {exc}",
        )

    failed = list(payload.get("download_errors") or [])
    failed.extend(file_errors)
    status = str(payload.get("status") or ("ok" if payload.get("success") else "failed"))
    if file_errors and status == "ok":
        status = "partial"
    error = str(payload.get("error") or "")
    warnings = [str(item) for item in payload.get("warnings") or [] if str(item).strip()]
    context = str(payload.get("context") or "")
    if warnings and "Предупреждения источника документации" not in context:
        warning_text = "\n".join(f"- {warning}" for warning in warnings[:20])
        context = f"Предупреждения источника документации:\n{warning_text}\n\n{context}".strip()
    if file_errors:
        file_error_text = f"Не получено файлов из общего сервиса: {len(file_errors)}"
        error = f"{error}; {file_error_text}" if error else file_error_text
    return TenderplanFetchResult(
        ok=bool(payload.get("success")) and not file_errors,
        status=status,
        context=context,
        notice_number=str(payload.get("notice_number") or notice_number),
        tender_id=str(payload.get("tender_id") or ""),
        error=error,
        downloaded_files=files,
        failed_downloads=failed,
        service_schema_version=str(payload.get("schema_version") or ""),
        warnings=warnings,
        document_hints=payload.get("document_hints") if isinstance(payload.get("document_hints"), dict) else {},
    )


def load_tender_source_service_files(
    client: httpx.Client,
    base_url: str,
    file_items: list[dict],
) -> tuple[list[TenderplanDownloadedFile], list[dict]]:
    files: list[TenderplanDownloadedFile] = []
    errors: list[dict] = []
    for item in file_items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        filename = str(item.get("filename") or "document")
        try:
            response = client.get(urljoin(f"{base_url}/", url.lstrip("/")))
            response.raise_for_status()
            content = response.content
            if not content:
                raise TenderplanError("empty file from tender source service")
            files.append(
                TenderplanDownloadedFile(
                    filename=filename,
                    content=content,
                    category=str(item.get("category") or "documentation"),
                    source_url=str(item.get("source_url") or ""),
                    size=len(content),
                    document_type=str(item.get("document_type") or "other"),
                    document_type_source=str(item.get("document_type_source") or "unknown"),
                    document_type_confidence=float(item.get("document_type_confidence") or 0.0),
                    content_document_types=[
                        str(value)
                        for value in item.get("content_document_types") or []
                        if str(value).strip()
                    ],
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "name": filename,
                    "href": str(item.get("url") or item.get("source_url") or ""),
                    "category": str(item.get("category") or "documentation"),
                    "error": f"service_file_fetch_failed: {exc}",
                }
            )
    return files, errors


class TenderplanClient:
    def __init__(self, *, token: str, base_url: str = TENDERPLAN_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout = float(config.tenderplan_timeout_seconds or 20)
        self._tool_dictionary_cache: dict[str, tuple[float, dict[str, str], str]] = {}

    def fetch_procurement(self, notice_number: str) -> TenderplanFetchResult:
        number = normalize_notice_number(notice_number)
        if not number:
            return TenderplanFetchResult(ok=False, status="invalid_number", notice_number=notice_number, error="Некорректный номер извещения")

        search_payload = self._get_json("/api/search/tender", params={"number": number})
        matches = find_tender_matches(search_payload, number)
        if not matches:
            return TenderplanFetchResult(ok=False, status="not_found", notice_number=number, error="Закупка не найдена по номеру извещения")
        tender_id = str(matches[0].get("_id") or matches[0].get("id") or "").strip()
        if not tender_id:
            return TenderplanFetchResult(ok=False, status="not_found", notice_number=number, error="Источник закупки не вернул ID карточки")

        fullinfo_by_id: dict[str, dict] = {}
        related_tenders: list[dict] = []
        related_ids: list[str] = []
        if len(matches) > 1:
            ids = [str(item.get("_id") or item.get("id") or "").strip() for item in matches if item.get("_id") or item.get("id")]
            ids = list(dict.fromkeys(item for item in ids if item))
            if len(ids) > 1:
                related_ids = ids[:20]
                for item_id in related_ids:
                    item_fullinfo = self._get_json("/api/tenders/v2/fullinfo", params={"id": item_id})
                    if isinstance(item_fullinfo, dict):
                        fullinfo_by_id[item_id] = item_fullinfo
                tenders = [
                    item.get("tender")
                    for item in fullinfo_by_id.values()
                    if isinstance(item, dict) and isinstance(item.get("tender"), dict)
                ]
                hrefs = {str(item.get("href") or "").strip() for item in tenders if item.get("href")}
                numbers = {str(item.get("number") or "").strip() for item in tenders if item.get("number")}
                if any(item and item != number for item in numbers):
                    return TenderplanFetchResult(ok=False, status="ambiguous", notice_number=number, error="Источник закупки вернул несколько карточек по номеру")
                selected_id = preferred_tender_id(fullinfo_by_id, fallback_id=tender_id)
                if len(hrefs) > 1 and not selected_id:
                    return TenderplanFetchResult(ok=False, status="ambiguous", notice_number=number, error="Источник закупки вернул несколько карточек по номеру")
                if selected_id:
                    tender_id = selected_id
                related_ids = related_tender_ids(fullinfo_by_id, selected_id=tender_id)
                related_tenders = [
                    fullinfo_by_id[item_id].get("tender")
                    for item_id in related_ids
                    if isinstance(fullinfo_by_id.get(item_id), dict) and isinstance(fullinfo_by_id[item_id].get("tender"), dict)
                ]

        fullinfo = fullinfo_by_id.get(tender_id) or self._get_json("/api/tenders/v2/fullinfo", params={"id": tender_id})
        attachments = self._get_json("/api/tenders/attachments", params={"id": tender_id}, default=[])
        explanations = self._get_json("/api/tenders/explanations", params={"id": tender_id}, default=[])
        explanation_attachments = self._get_json("/api/tenders/explanations/attachments", params={"id": tender_id}, default=[])
        for related_id in related_ids:
            if related_id == tender_id:
                continue
            attachments = merge_tenderplan_payloads(
                attachments,
                self._get_json("/api/tenders/attachments", params={"id": related_id}, default=[]),
            )
            explanations = merge_tenderplan_payloads(
                explanations,
                self._get_json("/api/tenders/explanations", params={"id": related_id}, default=[]),
            )
            explanation_attachments = merge_tenderplan_payloads(
                explanation_attachments,
                self._get_json("/api/tenders/explanations/attachments", params={"id": related_id}, default=[]),
            )

        tender = fullinfo.get("tender") if isinstance(fullinfo, dict) else {}
        placing_way_names, placing_way_source = self.tool_dictionary("placingways")
        status_names, status_source = self.tool_dictionary("statuses")
        if is_unknown_dictionary_code((tender or {}).get("placingWay"), placing_way_names):
            placing_way_names, placing_way_source = self.tool_dictionary("placingways", force=True)
        if is_unknown_dictionary_code((tender or {}).get("status"), status_names):
            status_names, status_source = self.tool_dictionary("statuses", force=True)
        context = build_tenderplan_context(
            notice_number=number,
            tender_id=tender_id,
            fullinfo=fullinfo if isinstance(fullinfo, dict) else {},
            attachments=attachments,
            explanations=explanations,
            explanation_attachments=explanation_attachments,
            placing_way_names=placing_way_names,
            placing_way_source=placing_way_source,
            status_names=status_names,
            status_source=status_source,
            related_tenders=related_tenders,
        )
        download_items = [
            *attachment_items(attachments, "documentation"),
            *attachment_items(explanation_attachments, "explanation"),
        ]
        fallback_urls = resolve_223_filestore_fallbacks(str(tender.get("href") or ""), download_items)
        files, failed = download_tenderplan_attachments(download_items, fallback_urls=fallback_urls)
        context = f"{context}\n{build_tenderplan_download_context(files, failed)}"
        status = "ok" if not failed else "partial"
        return TenderplanFetchResult(
            ok=True,
            status=status,
            context=context,
            notice_number=str(tender.get("number") or number),
            tender_id=tender_id,
            downloaded_files=files,
            failed_downloads=failed,
            error=f"Не скачано файлов: {len(failed)}" if failed else "",
        )

    def _get_json(self, path: str, *, params: dict | None = None, default=None):
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
                response = client.get(url, params=params or {})
        except httpx.HTTPError as exc:
            if default is not None:
                return default
            raise TenderplanError(f"Запрос к источнику закупок не выполнен: {path}: {exc}") from exc
        if response.status_code >= 400:
            if default is not None:
                return default
            raise TenderplanError(f"Запрос к источнику закупок не выполнен: {path}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            if default is not None:
                return default
            raise TenderplanError(f"Источник закупок вернул некорректный JSON: {path}") from exc

    def tool_dictionary(self, name: str, *, force: bool = False) -> tuple[dict[str, str], str]:
        path, fallback = TENDERPLAN_TOOL_DICTIONARIES[name]
        now = time.monotonic()
        cached = self._tool_dictionary_cache.get(name)
        if cached and not force and now - cached[0] < DICTIONARY_CACHE_TTL_SECONDS:
            return cached[1], cached[2]
        payload = self._get_json(path, default=[])
        api_labels = parse_tool_dictionary(payload)
        if api_labels:
            labels = {**fallback, **api_labels}
            source = f"Tenderplan {path}"
        else:
            labels = dict(fallback)
            source = "локальный fallback справочника Tenderplan"
        self._tool_dictionary_cache[name] = (now, labels, source)
        return labels, source


def normalize_notice_number(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) == 36:
        return ""
    if len(digits) in {11, 19}:
        return digits
    return ""


def find_tender_matches(payload, notice_number: str) -> list[dict]:
    candidates: list[dict] = []

    def walk(value) -> None:
        if isinstance(value, dict):
            number = str(value.get("number") or value.get("relationNumber") or "")
            if number == notice_number and (value.get("_id") or value.get("id")):
                candidates.append(value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    result: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item.get("_id") or item.get("id") or item.get("number") or "")
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def build_tenderplan_context(
    *,
    notice_number: str,
    tender_id: str,
    fullinfo: dict,
    attachments,
    explanations,
    explanation_attachments,
    placing_way_names: dict[str, str] | None = None,
    placing_way_source: str = "",
    status_names: dict[str, str] | None = None,
    status_source: str = "",
    related_tenders: list[dict] | None = None,
) -> str:
    tender = fullinfo.get("tender") if isinstance(fullinfo, dict) else {}
    tender = tender if isinstance(tender, dict) else {}
    tender_json = parse_tender_json(tender.get("json"))
    objects = extract_object_rows(tender_json)
    dates = tender_dates(tender, tender_json)
    national_regime = extract_national_regime(objects, tender_json)
    customers = [str(item.get("name") or "") for item in tender.get("customers") or [] if isinstance(item, dict) and item.get("name")]
    platform = tender.get("platform") if isinstance(tender.get("platform"), dict) else {}
    placing_way_lines = format_placing_way_lines(
        tender.get("placingWay"),
        global_search=tender.get("globalSearch"),
        placing_way_names=placing_way_names,
        dictionary_source=placing_way_source,
    )

    lines = [
        f"=== ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ ПО НОМЕРУ ИЗВЕЩЕНИЯ ({notice_number}) ===",
        (
            "Это структурированные данные из ЕИС по номеру извещения. "
            "Используй их как основной источник критичных полей: номер извещения, "
            "заказчик, НМЦК, сроки подачи заявок, дата аукциона, дата итогов, площадка, способ закупки, "
            "национальный режим и карточка закупки. Даты ниже нормализованы в московское время, если поле "
            "является timestamp источника. Разъяснения и ответы заказчика имеют приоритет над исходным ТЗ, "
            "если уточняют характеристики, сроки, оплату или иные условия."
        ),
        "",
        "Карточка закупки:",
        f"- Номер извещения: {tender.get('number') or notice_number}",
        f"- ID источника: {tender_id}",
        f"- Источник ЕИС: {tender.get('href') or ''}",
        f"- Наименование: {tender.get('orderName') or ''}",
        f"- Закон: {law_label(tender.get('href'))}",
        *placing_way_lines,
        format_status_line(tender.get("status"), status_names=status_names, dictionary_source=status_source),
        f"- НМЦК/цена: {format_price(tender.get('maxPrice'))}",
        f"- Заказчики: {'; '.join(customers)}",
        f"- Площадка: {platform.get('name') or ''} {platform.get('href') or ''}".strip(),
        f"- Обеспечение заявки: {format_price(tender.get('guaranteeApp'))}",
        f"- Обеспечение контракта: {format_price(tender.get('guaranteeContract'))}",
        f"- СМП/СОНО: {bool(tender.get('smp'))}",
        "",
        "Сроки закупки (МСК):",
        f"- Размещено: {dates.get('publication') or ''}",
        f"- Начало подачи заявок: {dates.get('submission_start') or ''}",
        f"- Дата и время окончания срока подачи заявок (МСК): {dates.get('submission_close') or ''}",
        f"- Аукцион/подача цены: {dates.get('bidding') or ''}",
        f"- Дата подведения итогов (МСК): {dates.get('summing_up') or ''}",
        "",
        "Национальный режим и преимущества:",
        *[f"- {item}" for item in national_regime],
        "",
        "Объект закупки / позиции:",
    ]
    related_lines = format_related_tenders(related_tenders or [], selected_tender_id=tender_id)
    if related_lines:
        lines.extend(["", "Несколько карточек/лотов по этому извещению:", *related_lines, ""])
    for row in objects[:80]:
        lines.append(format_object_row(row))
    if len(objects) > 80:
        lines.append(f"- ... еще позиций: {len(objects) - 80}")
    lines.extend(
        [
            "",
            "Документы и служебные материалы:",
            f"- Документация: {len(attachment_items(attachments, 'documentation'))} файлов",
            f"- Разъяснения/ответы заказчика: {count_items(explanations)} записей, {len(attachment_items(explanation_attachments, 'explanation'))} файлов",
        ]
    )
    for title, items in (
        ("Файлы документации", attachment_items(attachments, "documentation")),
        ("Файлы разъяснений", attachment_items(explanation_attachments, "explanation")),
    ):
        if not items:
            continue
        lines.extend(["", f"{title}:"])
        for item in items[:60]:
            lines.append(f"- {item.name} ({format_size(item.size)})")
    return "\n".join(line for line in lines if line is not None)[:500000] + "\n"


def build_tenderplan_download_context(files: list[TenderplanDownloadedFile], failed: list[dict]) -> str:
    lines = [
        "Скачивание документации:",
        f"- Скачано файлов для последующего анализа: {len(files)}",
        f"- Не скачано файлов: {len(failed)}",
    ]
    if failed:
        lines.append("Неполученные файлы:")
        for item in failed[:30]:
            name = str(item.get("name") or "").strip() or "без имени"
            error = str(item.get("error") or "").strip() or "unknown"
            lines.append(f"- {name}: {error}")
        if len(failed) > 30:
            lines.append(f"- ... еще файлов: {len(failed) - 30}")
    return "\n".join(lines) + "\n"


def parse_tender_json(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def tender_dates(tender: dict, tender_json: dict) -> dict[str, str]:
    publication = publication_date_from_feed(tender) or format_msk(tender.get("publicationDateTime"), with_time=False)
    return {
        "publication": publication,
        "submission_start": format_msk(tender.get("submissionStartDateTime") or find_tender_json_datetime(tender_json, "RequestStartDateTime")),
        "submission_close": format_msk(tender.get("submissionCloseDateTime") or find_tender_json_datetime(tender_json, "RequestEndDateTime")),
        "bidding": format_msk(tender.get("biddingDateTime") or find_tender_json_datetime(tender_json, "BiddingDateTime")),
        "summing_up": format_msk(tender.get("summingUpDateTime") or find_tender_json_datetime(tender_json, "SummingUpDateTime")),
    }


def publication_date_from_feed(tender: dict) -> str:
    for event in tender.get("feed") or []:
        if not isinstance(event, dict):
            continue
        text = str(event.get("event") or "")
        if "Размещен документ" in text or "Размещено" in text:
            value = format_msk(event.get("eventDateTime"), with_time=False)
            if value:
                return value
    return ""


def find_tender_json_datetime(tender_json: dict, fn: str):
    result = None

    def walk(value) -> None:
        nonlocal result
        if result is not None:
            return
        if isinstance(value, dict):
            if value.get("fn") == fn and value.get("fv"):
                result = value.get("fv")
                return
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(tender_json)
    return result


def format_msk(value, *, with_time: bool = True) -> str:
    if not value:
        return ""
    try:
        numeric = float(value)
        if numeric > 10_000_000_000:
            numeric = numeric / 1000
        dt = datetime.fromtimestamp(numeric, timezone.utc).astimezone(MSK)
    except (TypeError, ValueError, OSError):
        return ""
    return dt.strftime("%d.%m.%Y %H:%M МСК" if with_time else "%d.%m.%Y")


def format_price(value) -> str:
    if value in (None, ""):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:,.2f} руб.".replace(",", " ")


def format_size(value: int | None) -> str:
    if not value:
        return "размер не указан"
    if value < 1024 * 1024:
        return f"{round(value / 1024, 1)} КБ"
    return f"{round(value / 1024 / 1024, 1)} МБ"


def law_label(href: object) -> str:
    text = str(href or "")
    if "notice223" in text:
        return "223-ФЗ"
    if "/44fz/" in text or "/ea" in text or "/zk" in text or "/notice/" in text:
        return "44-ФЗ"
    return ""


def count_items(value) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(len(item) for item in value.values() if isinstance(item, list))
    return 0


def attachment_items(value, category: str) -> list[TenderplanAttachment]:
    result: list[TenderplanAttachment] = []

    def add(item) -> None:
        if not isinstance(item, dict):
            return
        href = str(item.get("href") or "").strip()
        if not href:
            return
        name = str(item.get("realName") or item.get("displayName") or Path(urlparse(href).path).name or "document").strip()
        size = item.get("size")
        result.append(
            TenderplanAttachment(
                name=name,
                href=href,
                category=category,
                size=int(size) if isinstance(size, (int, float)) else None,
                publication_date_time=item.get("publicationDateTime") if isinstance(item.get("publicationDateTime"), int) else None,
            )
        )

    if isinstance(value, list):
        for item in value:
            add(item)
    elif isinstance(value, dict):
        for item in value.values():
            if isinstance(item, list):
                for nested in item:
                    add(nested)
            else:
                add(item)
    return result


def merge_tenderplan_payloads(*payloads):
    result: list[dict] = []
    seen: set[str] = set()
    for payload in payloads:
        for item in flatten_tenderplan_payload(payload):
            key = tenderplan_payload_key(item)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


def flatten_tenderplan_payload(value) -> list[dict]:
    result: list[dict] = []

    def add(item) -> None:
        if isinstance(item, dict):
            result.append(item)

    if isinstance(value, list):
        for item in value:
            add(item)
    elif isinstance(value, dict):
        for item in value.values():
            if isinstance(item, list):
                for nested in item:
                    add(nested)
            else:
                add(item)
    return result


def tenderplan_payload_key(item: dict) -> str:
    for field in ("href", "_id", "id", "uid", "guid"):
        value = str(item.get(field) or "").strip()
        if value:
            return f"{field}:{value}"
    return json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)


def extract_object_rows(tender_json: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def walk(value) -> None:
        if isinstance(value, dict):
            if value.get("ft") == "Table" and isinstance(value.get("fv"), dict):
                table = value["fv"]
                headers = {
                    str(col): str((header or {}).get("fv") or (header or {}).get("fn") or "")
                    for col, header in (table.get("th") or {}).items()
                    if isinstance(header, dict)
                }
                for raw_row in (table.get("tb") or {}).values():
                    if not isinstance(raw_row, dict):
                        continue
                    row: dict[str, str] = {}
                    for col, cell in raw_row.items():
                        if not isinstance(cell, dict):
                            continue
                        label = headers.get(str(col)) or str(cell.get("fdn") or cell.get("fn") or col)
                        row[label] = str(cell.get("fv") if cell.get("fv") is not None else "").strip()
                    if row:
                        rows.append(row)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(tender_json)
    return rows


def extract_national_regime(objects: list[dict[str, str]], tender_json: dict) -> list[str]:
    result: list[str] = []
    for row in objects:
        for key, value in row.items():
            if "нацрежим" in key.lower() or "nationalregime" in key.lower():
                if value:
                    name = row.get("Наименования товара, работы, услуги") or row.get("Наименование товара, работы, услуги") or row.get("Name") or ""
                    result.append(f"{name}: {value}".strip(": "))
    general = tender_json.get("general") if isinstance(tender_json, dict) else {}
    if isinstance(general, dict):
        for key in ("requirements", "restrictInfo", "preference"):
            value = find_general_field(general, key)
            if value is not None:
                label = {"requirements": "Требования", "restrictInfo": "Ограничения", "preference": "Преимущества"}[key]
                result.append(f"{label}: {bool(value)}")
    return result or ["Нет структурированных данных о нацрежиме в карточке источника"]


def find_general_field(general: dict, fn: str):
    for item in general.values():
        if isinstance(item, dict) and item.get("fn") == fn:
            return item.get("fv")
    return None


def format_object_row(row: dict[str, str]) -> str:
    preferred = [
        "Наименования товара, работы, услуги",
        "Наименование товара, работы, услуги",
        "Описание",
        "Нацрежим",
        "КТРУ",
        "ОКПД2",
        "Количество",
        "Цена",
        "Стоимость",
    ]
    parts: list[str] = []
    used: set[str] = set()
    for key in preferred:
        if row.get(key):
            parts.append(f"{key}: {row[key]}")
            used.add(key)
    for key, value in row.items():
        if key not in used and value:
            parts.append(f"{key}: {value}")
    return "- " + "; ".join(parts)


PROCUREMENT_METHOD_PATTERNS = (
    "Запрос котировок в электронной форме",
    "Запрос предложений в электронной форме",
    "Открытый конкурс в электронной форме",
    "Запрос цен товаров, работ, услуг",
    "Конкурс в электронной форме",
    "Аукцион в электронной форме",
    "Электронный аукцион",
    "Закупка у единственного поставщика",
    "Запрос котировок",
    "Запрос предложений",
    "Открытый конкурс",
    "Иной способ",
    "Аукцион",
    "Конкурс",
)


def parse_tool_dictionary(payload) -> dict[str, str]:
    if not isinstance(payload, list):
        return {}
    labels: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = item.get("_id")
        name = str(item.get("name") or "").strip()
        if code is None or not name:
            continue
        labels[str(code)] = " ".join(name.split())
    return labels


def is_unknown_dictionary_code(value, labels: dict[str, str]) -> bool:
    text = " ".join(("" if value is None else str(value)).split())
    return bool(re.fullmatch(r"\d{1,4}", text) and text not in labels)


def format_placing_way_lines(
    value,
    *,
    global_search=None,
    placing_way_names: dict[str, str] | None = None,
    dictionary_source: str = "",
) -> list[str]:
    text = " ".join(("" if value is None else str(value)).split())
    if text and re.fullmatch(r"\d{1,4}", text):
        label = (placing_way_names or {}).get(text, "")
        if label:
            lines = [
                f"- Способ осуществления закупки: {label}",
                f"- Код способа закупки источника: {text}",
                f"- Источник расшифровки способа: {_public_dictionary_source(dictionary_source)}",
            ]
            if text == "0":
                lines.append(
                    "- Детализация способа: источник передал обобщенный код 0 «Иной способ»; "
                    "подвид нужно брать из извещения, документации или площадки, если он там указан."
                )
            return lines
    inferred = extract_procurement_method_from_text(global_search)
    if inferred and (not text or re.fullmatch(r"\d{1,4}", text)):
        lines = [f"- Способ осуществления закупки: {inferred}"]
        if text:
            lines.append(f"- Код способа закупки источника: {text}")
        lines.append("- Источник расшифровки способа: текст карточки закупки")
        return lines
    if not text:
        return ["- Способ осуществления закупки: "]
    if re.fullmatch(r"\d{1,4}", text):
        return [
            f"- Код способа закупки источника: {text}",
            "- Человекочитаемый способ закупки: код не найден в справочнике; см. формулировку в извещении/документации",
        ]
    return [f"- Способ осуществления закупки: {text}"]


def extract_procurement_method_from_text(value) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    for method in PROCUREMENT_METHOD_PATTERNS:
        if re.search(rf"(?<![А-Яа-яЁёA-Za-z]){re.escape(method)}(?![А-Яа-яЁёA-Za-z])", text, flags=re.IGNORECASE):
            return method
    return ""


def format_status_line(value, *, status_names: dict[str, str] | None = None, dictionary_source: str = "") -> str:
    text = " ".join(("" if value is None else str(value)).split())
    if not text:
        return "- Статус: "
    if re.fullmatch(r"\d{1,4}", text):
        label = (status_names or {}).get(text, "")
        if label:
            return f"- Статус: {label} (код источника: {text}; источник: {_public_dictionary_source(dictionary_source)})"
        return f"- Статус/код источника: {text}"
    return f"- Статус: {text}"


def _public_dictionary_source(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "официальный справочник"
    if "/placingways/" in raw:
        return "официальный справочник способов закупки"
    if "/statuses/" in raw:
        return "официальный справочник статусов"
    if "fallback" in raw.lower():
        return "локальный справочник"
    return "официальный справочник"


def format_related_tenders(tenders: list[dict], *, selected_tender_id: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for index, tender in enumerate(tenders[:30], start=1):
        if not isinstance(tender, dict):
            continue
        tender_id = str(tender.get("_id") or tender.get("id") or "").strip()
        name = str(tender.get("orderName") or "").strip()
        if not name and not tender_id:
            continue
        key = tender_id or name
        if key in seen:
            continue
        seen.add(key)
        marker = "основная карточка" if tender_id and tender_id == selected_tender_id else f"карточка {index}"
        parts = [marker]
        if name:
            parts.append(name)
        price = format_price(tender.get("maxPrice"))
        if price:
            parts.append(f"НМЦК: {price}")
        close = format_msk(tender.get("submissionCloseDateTime"))
        if close:
            parts.append(f"окончание подачи: {close}")
        result.append("- " + "; ".join(parts))
    if len(tenders) > 30:
        result.append(f"- ... еще карточек/лотов: {len(tenders) - 30}")
    return result


def preferred_tender_id(fullinfo_by_id: dict[str, dict], *, fallback_id: str) -> str:
    entries = tender_entries(fullinfo_by_id)
    notice_entries = [(item_id, tender) for item_id, tender in entries if is_primary_notice_href(str(tender.get("href") or ""))]
    if len(notice_entries) == 1:
        return notice_entries[0][0]
    non_price_request_entries = [(item_id, tender) for item_id, tender in entries if not is_price_request_href(str(tender.get("href") or ""))]
    if len(non_price_request_entries) == 1:
        return non_price_request_entries[0][0]
    if fallback_id in fullinfo_by_id:
        fallback_tender = fullinfo_by_id.get(fallback_id, {}).get("tender")
        fallback_href = str(fallback_tender.get("href") or "") if isinstance(fallback_tender, dict) else ""
        if fallback_href and all(str(tender.get("href") or "") == fallback_href for _, tender in entries):
            return fallback_id
    return ""


def related_tender_ids(fullinfo_by_id: dict[str, dict], *, selected_id: str) -> list[str]:
    selected = fullinfo_by_id.get(selected_id, {}).get("tender")
    selected_href = str(selected.get("href") or "") if isinstance(selected, dict) else ""
    if not selected_href:
        return [selected_id] if selected_id in fullinfo_by_id else []
    result = [
        item_id
        for item_id, tender in tender_entries(fullinfo_by_id)
        if str(tender.get("href") or "") == selected_href
    ]
    return result or [selected_id]


def tender_entries(fullinfo_by_id: dict[str, dict]) -> list[tuple[str, dict]]:
    result: list[tuple[str, dict]] = []
    for item_id, fullinfo in fullinfo_by_id.items():
        tender = fullinfo.get("tender") if isinstance(fullinfo, dict) else None
        if isinstance(tender, dict):
            result.append((item_id, tender))
    return result


def is_primary_notice_href(href: str) -> bool:
    text = str(href or "")
    return "/epz/order/notice/" in text or "notice223" in text


def is_price_request_href(href: str) -> bool:
    return "/epz/pricereq/" in str(href or "")


def download_tenderplan_attachments(
    attachments: list[TenderplanAttachment],
    *,
    fallback_urls: dict[str, str] | None = None,
) -> tuple[list[TenderplanDownloadedFile], list[dict]]:
    files: list[TenderplanDownloadedFile] = []
    failures: list[dict] = []
    seen: set[str] = set()
    fallback_urls = fallback_urls or {}
    max_files = max(0, int(config.tenderplan_max_documents or 0))
    max_bytes = max(1, int(config.tenderplan_max_document_mb or 1)) * 1024 * 1024
    for attachment in attachments:
        if len(files) >= max_files:
            failures.append({"name": attachment.name, "href": attachment.href, "error": "document_limit"})
            continue
        effective_href = fallback_urls.get(attachment.href, attachment.href)
        if effective_href in seen:
            continue
        seen.add(effective_href)
        if not is_allowed_download_url(effective_href):
            failures.append({"name": attachment.name, "href": attachment.href, "effective_href": effective_href, "error": "host_not_allowed"})
            continue
        if attachment.size and attachment.size > max_bytes:
            failures.append({"name": attachment.name, "href": attachment.href, "error": "file_too_large"})
            continue
        effective_attachment = attachment
        if effective_href != attachment.href:
            effective_attachment = TenderplanAttachment(
                name=attachment.name,
                href=effective_href,
                category=attachment.category,
                size=attachment.size,
                publication_date_time=attachment.publication_date_time,
            )
        downloaded = download_attachment(effective_attachment, max_bytes=max_bytes)
        if isinstance(downloaded, TenderplanDownloadedFile):
            files.append(downloaded)
        else:
            if effective_href != attachment.href:
                downloaded["effective_href"] = effective_href
            failures.append(downloaded)
    return files, failures


def resolve_223_filestore_fallbacks(tender_href: str, attachments: list[TenderplanAttachment]) -> dict[str, str]:
    if "notice223" not in str(tender_href or ""):
        return {}
    old_downloads = [
        item
        for item in attachments
        if item.category == "documentation" and "/223/purchase/public/download/download.html" in item.href
    ]
    if not old_downloads:
        return {}

    status, common_html = run_curl_fetch_text(tender_href)
    if not status.startswith("2") or not common_html:
        return {}
    documents_url = notice223_documents_url(tender_href, common_html)
    if not documents_url:
        return {}
    status, documents_html = run_curl_fetch_text(documents_url, referer=tender_href)
    if not status.startswith("2") or not documents_html:
        return {}

    by_name = filestore_fallbacks_from_documents_html(documents_html, base_url=documents_url)
    result: dict[str, str] = {}
    for attachment in old_downloads:
        fallback = best_filestore_fallback_url(attachment.name, by_name)
        if fallback:
            result[attachment.href] = fallback
    return result


def notice223_documents_url(tender_href: str, html: str) -> str:
    parsed = urlparse(str(tender_href or ""))
    query = parse_qs(parsed.query)
    number = (query.get("regNumber") or query.get("purchaseNoticeNumber") or [""])[0]
    if not number:
        match = re.search(r"purchaseNoticeNumber=(\d+)", html)
        number = match.group(1) if match else ""
    guid = ""
    for pattern in (
        r"noticeGuid=([0-9a-fA-F-]{36})",
        r"purchaseNoticeGuid=([0-9a-fA-F-]{36})",
    ):
        match = re.search(pattern, html)
        if match:
            guid = match.group(1)
            break
    if not number or not guid:
        return ""
    return f"https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber={number}&noticeGuid={guid}"


def filestore_fallbacks_from_documents_html(html: str, *, base_url: str) -> dict[str, str]:
    soup = BeautifulSoup(str(html or ""), "html.parser")
    result: dict[str, str] = {}
    for anchor in soup.find_all("a"):
        href = str(anchor.get("href") or "")
        if "/223/filestore/public/1.0/download/fz223/file.html" not in href:
            continue
        name = " ".join(anchor.get_text(" ", strip=True).split())
        key = normalize_document_name(name)
        if key and key not in result:
            result[key] = urljoin(base_url, href)
    return result


def normalize_document_name(value: str) -> str:
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"\.(docx?|xlsx?|pdf|zip|rar|7z|rtf|odt|txt|xml|html?)$", "", text)
    text = re.sub(r"[^0-9a-zа-я]+", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def best_filestore_fallback_url(attachment_name: str, by_name: dict[str, str]) -> str:
    key = normalize_document_name(attachment_name)
    if not key:
        return ""
    if key in by_name:
        return by_name[key]

    tokens = document_name_tokens(key)
    scored: list[tuple[float, str]] = []
    for candidate_key, url in by_name.items():
        candidate_key = normalize_document_name(candidate_key)
        if not candidate_key or not url:
            continue
        candidate_tokens = document_name_tokens(candidate_key)
        common = tokens & candidate_tokens
        if not common:
            continue
        overlap = len(common) / max(len(tokens), len(candidate_tokens), 1)
        ratio = SequenceMatcher(None, key, candidate_key).ratio()
        score = max(overlap, ratio)
        if score >= 0.82 or (len(common) >= 3 and score >= 0.58):
            scored.append((score, url))

    if not scored:
        return ""
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.05:
        return scored[0][1]
    return ""


def document_name_tokens(value: str) -> set[str]:
    tokens = set(normalize_document_name(value).split())
    if "тз" in tokens:
        tokens.update({"техническое", "задание"})
    if {"техническое", "задание"}.issubset(tokens):
        tokens.add("тз")
    return tokens


def is_allowed_download_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in DOWNLOAD_ALLOWED_HOSTS or any(host.endswith(f".{allowed}") for allowed in DOWNLOAD_ALLOWED_HOSTS)


def download_attachment(attachment: TenderplanAttachment, *, max_bytes: int):
    filename = safe_attachment_filename(attachment.name, attachment.href, attachment.category)
    with tempfile.TemporaryDirectory(prefix="aipoisk-tenderplan-") as tmp:
        output = Path(tmp) / filename
        status, error = run_curl_download(attachment.href, output)
        if not status.startswith("2") or not output.exists():
            return {"name": attachment.name, "href": attachment.href, "error": error or f"http_{status}"}
        size = output.stat().st_size
        if size <= 0:
            return {"name": attachment.name, "href": attachment.href, "error": "empty_file"}
        if size > max_bytes:
            return {"name": attachment.name, "href": attachment.href, "error": "file_too_large"}
        return TenderplanDownloadedFile(
            filename=filename,
            content=output.read_bytes(),
            category=attachment.category,
            source_url=attachment.href,
            size=size,
        )


def safe_attachment_filename(name: str, href: str, category: str) -> str:
    raw = str(name or Path(urlparse(href).path).name or "document").strip()
    suffix = safe_suffix(Path(raw).suffix) or safe_suffix(Path(urlparse(href).path).suffix)
    stem = raw[: -len(Path(raw).suffix)] if suffix and Path(raw).suffix else raw
    filename = sanitize_filename(stem)
    prefix = {"documentation": "Документация", "explanation": "Разъяснение"}.get(category, "Документ")
    return filename_with_suffix(f"{prefix} - {filename}", suffix)


def safe_suffix(value: str) -> str:
    suffix = str(value or "").strip().lower()
    if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
        return suffix
    return ""


def filename_with_suffix(stem: str, suffix: str, *, max_bytes: int = 180) -> str:
    clean_stem = sanitize_filename(stem)
    suffix = safe_suffix(suffix)
    if not suffix:
        return clean_stem
    candidate = f"{clean_stem}{suffix}"
    if len(candidate.encode("utf-8")) <= max_bytes:
        return candidate
    available = max(1, max_bytes - len(suffix.encode("utf-8")))
    truncated = clean_stem.encode("utf-8")[:available].decode("utf-8", errors="ignore").rstrip(" ._-")
    return f"{truncated or 'document'}{suffix}"


def run_curl_download(url: str, output: Path) -> tuple[str, str]:
    args = curl_base_args(output=output, referer="https://zakupki.gov.ru/")
    args.append(url)
    attempts = curl_retry_attempts()
    last_status = "000"
    last_error = ""
    for attempt in range(attempts):
        if output.exists() and attempt > 0:
            output.unlink()
        try:
            result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=max(10, int(config.tenderplan_download_timeout_seconds or 30)) + 5)
        except (OSError, subprocess.SubprocessError) as exc:
            last_status, last_error = "000", str(exc)
        else:
            last_status = (result.stdout or "").strip()[-3:] or "000"
            last_error = (result.stderr or "").strip()[:500]
        if last_status.startswith("2") or not is_retryable_curl_status(last_status) or attempt + 1 >= attempts:
            return last_status, last_error
    return last_status, last_error


def run_curl_fetch_text(url: str, *, referer: str = "https://zakupki.gov.ru/") -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="aipoisk-eis-html-") as tmp:
        output = Path(tmp) / "page.html"
        args = curl_base_args(output=output, referer=referer)
        args.append(url)
        attempts = curl_retry_attempts()
        last_status = "000"
        last_error = ""
        last_text = ""
        for attempt in range(attempts):
            if output.exists() and attempt > 0:
                output.unlink()
            try:
                result = subprocess.run(
                    args,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=max(10, int(config.tenderplan_download_timeout_seconds or 30)) + 5,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                last_status, last_error, last_text = "000", str(exc), ""
            else:
                last_status = (result.stdout or "").strip()[-3:] or "000"
                last_error = (result.stderr or "").strip()[:500]
                last_text = output.read_text(encoding="utf-8", errors="ignore") if output.exists() else ""
            if last_status.startswith("2") or not is_retryable_curl_status(last_status) or attempt + 1 >= attempts:
                return last_status, last_text or last_error
        return last_status, last_text or last_error


def curl_base_args(*, output: Path, referer: str) -> list[str]:
    args = [
        "curl",
        "-L",
        "--max-time",
        str(max(5, int(config.tenderplan_download_timeout_seconds or 30))),
        "--connect-timeout",
        "10",
        "-A",
        DOWNLOAD_USER_AGENT,
        "-e",
        referer,
        "-sS",
        "-o",
        str(output),
        "-w",
        "%{http_code}",
    ]
    proxy_url = download_proxy_url()
    if proxy_url:
        parsed = urlparse(proxy_url)
        if parsed.scheme.startswith("socks"):
            host = parsed.hostname or ""
            port = parsed.port or 1080
            args.extend(["--socks5-hostname", f"{host}:{port}"])
        else:
            args.extend(["--proxy", proxy_url])
    return args


def curl_retry_attempts() -> int:
    try:
        retries = int(config.tenderplan_download_retries or 0)
    except (TypeError, ValueError):
        retries = 0
    return max(1, retries + 1)


def is_retryable_curl_status(status: str) -> bool:
    try:
        code = int(str(status or "").strip())
    except ValueError:
        return False
    return code == 0 or code in {408, 425, 429} or 500 <= code <= 599


def download_proxy_url() -> str:
    return str(
        config.tenderplan_download_proxy_url
        or os.getenv("AIPOISK_PROXY_URL")
        or os.getenv("PROXY_URL")
        or ""
    ).strip()
