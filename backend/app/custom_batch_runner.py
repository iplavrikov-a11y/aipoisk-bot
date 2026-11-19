from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
import socket
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from .ai import _llm_limiter_held_var, _process_llm_limiter, call_llm, custom_provider_map, parse_json_object
from .config import config
from .custom_batch_insights import clean_kontur_url, enrich_batch_result_item
from .document_parser import (
    clean_surrogates,
    clean_xml_compatible,
    combined_document_context,
    extract_text,
    organize_procurement_documents,
    sanitize_filename,
)
from .models import SystemSettings, parse_json_dict
from .procurement_report import PROCUREMENT_LEGAL_BASELINE
from .procurement_sources import normalize_source_url, source_url_is_public
from .tenderplan import fetch_tenderplan_source_sync

logger = logging.getLogger(__name__)
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

CUSTOM_BATCH_SPEC_FILENAME = "custom_batch_spec.json"
CUSTOM_BATCH_RESULTS_FILENAME = "custom_batch_results.json"
VERTEX_REDIRECT_RE = re.compile(
    r"https://vertexaisearch\.cloud\.google\.com/grounding-api-redirect/[A-Za-z0-9_\-=]+"
)
INTERNAL_BRAND_RE = re.compile(r"\btenderplan(?:\.ru)?\b|тендерплан[а-я]*", re.IGNORECASE)

SMALL_TENDER_MATCH_PROMPT = """Ты сопоставляешь строку из реестра клиента с найденными карточками малых закупок.
Выбери ТОЛЬКО ту карточку, которая действительно относится к той же закупке (совпадает смысл предмета закупки и/или заказчик/ИНН/НМЦК/год).
ВАЖНО: у коротких номеров (6–8 цифр) часто встречаются совпадения номера у совершенно разных закупок других лет или регионов (например, в строке клиента — «Поставка бронеставни, 599 589 ₽», а в карточке — «Продукты питания, 18 088 ₽» 2023 года). Если предмет закупки, сумма, год или заказчик явно НЕ совпадают — ОБЯЗАТЕЛЬНО верни {"matched_id": null}!
Ответ строго JSON: {"matched_id": "строка id или null"}."""

DEFAULT_EXPRESS_ASSESSMENT_PROMPT = """# ИНСТРУКЦИЯ ДЛЯ ИИ-АНАЛИТИКА ЭКСПРЕСС-ОЦЕНКИ ЗАКУПОК

Роль: Ты — ведущий тендерный аналитик и специалист по закупкам/снабжению. Твоя задача — быстро и практично проанализировать документацию закупки (ТЗ / Описание объекта закупки / Извещение / Контракт), подобрать подходящий коммерческий товар, проверить соответствие ключевым требованиям, предложить реальных поставщиков/производителей и выдать ориентировочный финансово-логистический расчёт маржинальности.

---

### Алгоритм работы и структура ответа:

#### 1. Краткое резюме и условия закупки
* Наименование объекта закупки:
* Суть поставки: (в 2–3 предложениях, что именно требуется поставить)
* Место поставки: (адрес / регион / склад заказчика из документации)
* Срок поставки: (календарные/рабочие дни, график или крайняя дата)
* Срок оплаты: (условия и сроки оплаты по проекту контракта / извещению, если указаны)
* Ключевые «подводные камни» ТЗ: (сложные ГОСТы, лицензии, нацрежим / ПП РФ № 1875 / ГИСП, специфические требования к упаковке, приёмке или маркировке, особенности площадки).

#### 2. Подбор товара и Сравнительная Таблица Соответствия
Найди реальный коммерческий товар / модель / оборудование в продаже в РФ, полностью или максимально подходящий под ТЗ. Сформируй сравнительную таблицу и обязательно дай прямую кликабельную ссылку на найденный товар на сайте продавца:

| Характеристика / Параметр из ТЗ | Требование Заказчика (в ТЗ) | Значение предлагаемого товара/аналога | Статус соответствия (Соответствует / Условно соответствует / Отклонение) | Примечание / Риск отклонения заявки |
| :--- | :--- | :--- | :--- | :--- |

#### 3. Потенциальные поставщики и заводы-производители
Предложи 3–5 реальных производителей / оптовых дистрибьюторов / продавцов данной продукции в РФ:
* Название компании / завода и сайт (и город расположения).
* Почему подходят: что в ТЗ указывает на их продукцию или специализацию.
* Примерная закупочная оптовая цена за единицу и на весь объём.

#### 4. Оценка логистики и доставки
* Предполагаемое плечо логистики: (откуда везти — до места поставки заказчика).
* Оценка стоимости доставки: (ориентировочная стоимость ТК / фуры / контейнера / спецтехники на этот объём).
* Особые условия перевозки: (негабарит, температурный режим, манипулятор, жёсткая обрешётка и т.д.).

#### 5. Финансово-маржинальный расчёт и Вердикт
Составь предварительную экономику сделки:
* НМЦК (Цена заказчика): [Сумма]
* Ориентировочная себестоимость товара (Опт): [Сумма]
* Ориентировочная логистика: [Сумма]
* Прочие расходы (обеспечение заявки/исполнения, комиссия площадки, налоги): [Сумма]
* Расчётная Валовая Маржа: [Сумма и %]
* ИТОГОВЫЙ ВЕРДИКТ: (стоит ли выходить в закупку и почему — например, «Закупка демпинговая», «Рабочая маржа — стоит запросить КП», «Высокомаржинальный эксклюзив — рекомендуется детальный просчёт»).

В самом конце отчёта добавь короткую заметку:
*Примечание: это экспресс-оценка для быстрого отбора закупок; рыночные цены и маржа рассчитаны ориентировочно по открытым источникам. Перед подачей заявки рекомендуется проверить все позиции ТЗ, требования нацрежима и подготовить запрос КП в полном «Анализе документации».*"""


@dataclass(frozen=True)
class CustomTenderBundle:
    ok: bool
    context: str = ""
    error: str = ""
    files_count: int = 0


@dataclass(frozen=True)
class CustomPromptRunResult:
    markdown: str
    model: str
    sources: list[dict[str, str]] = field(default_factory=list)


def _strip_internal_source_names(text: str) -> str:
    if not text:
        return ""
    return INTERNAL_BRAND_RE.sub("официальный источник закупки", text)


def _active_ru_socks_proxy() -> str | None:
    proxy_url = (
        str(config.tenderplan_download_proxy_url or "").strip()
        or "socks5://127.0.0.1:1080"
    )
    parsed = urlparse(proxy_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 1080
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return proxy_url.replace("socks5h://", "socks5://", 1)
    except OSError:
        return None


def _build_excel_row_header(item: dict[str, Any]) -> str:
    lines = ["=== ДАННЫЕ СТРОКИ ИЗ ВЫГРУЗКИ КЛИЕНТА ==="]
    if item.get("notice_number"):
        lines.append(f"Номер закупки/извещения: {item['notice_number']}")
    if item.get("title"):
        lines.append(f"Наименование закупки: {item['title']}")
    if item.get("nmck_raw"):
        lines.append(f"НМЦК: {item['nmck_raw']}")
    if item.get("procurement_type"):
        lines.append(f"Тип торгов: {item['procurement_type']}")
    if item.get("publication_date"):
        lines.append(f"Дата публикации: {item['publication_date']}")
    if item.get("deadline_date"):
        lines.append(f"Окончание приёма заявок: {item['deadline_date']}")
    if item.get("customer_name"):
        lines.append(f"Заказчик: {item['customer_name']}")
    if item.get("customer_inn"):
        lines.append(f"ИНН заказчика: {item['customer_inn']}")
    return "\n".join(lines)


_ATTACHMENT_HREF_RE = re.compile(
    r"(?:FileDownloadHandler|DownloadFile|/download/|attachment|\.(?:docx?|pdf|xlsx?|zip|rar|rtf)(?:[?#]|$))",
    re.IGNORECASE,
)


def _is_html_stub_response(resp: httpx.Response) -> bool:
    ct = str(resp.headers.get("content-type") or "").lower()
    if "text/html" in ct or "application/xhtml" in ct:
        return True
    head = (resp.content or b"")[:512].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html", b"<?xml")) and b"<html" in head


def _filename_from_response(resp: httpx.Response, fallback: str) -> str:
    cd = str(resp.headers.get("content-disposition") or "")
    m_utf = re.search(r"filename\*\s*=\s*(?:UTF-8|utf-8)''([^;\r\n]+)", cd)
    if m_utf:
        return sanitize_filename(unquote(m_utf.group(1).strip('"\' ')))
    m_std = re.search(r'filename\s*=\s*"?([^";\r\n]+)"?', cd)
    if m_std:
        return sanitize_filename(m_std.group(1).strip('"\' '))
    return sanitize_filename(fallback)


async def _fetch_public_etp_page(url: str) -> tuple[str, list[tuple[str, bytes]]]:
    clean_url = normalize_source_url(url)
    if not clean_url or not await asyncio.to_thread(source_url_is_public, clean_url):
        return "", []
    proxy = await asyncio.to_thread(_active_ru_socks_proxy)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    for transport_proxy in ([proxy, None] if proxy else [None]):
        try:
            async with httpx.AsyncClient(
                timeout=12.0,
                follow_redirects=True,
                headers=headers,
                proxy=transport_proxy,
            ) as client:
                resp = await client.get(clean_url)
                if resp.status_code >= 400 or not resp.text:
                    continue
                if not await asyncio.to_thread(source_url_is_public, str(resp.url)):
                    continue
                soup = BeautifulSoup(resp.text[:400_000], "html.parser")
                doc_links: list[tuple[str, str]] = []
                seen_links: set[str] = set()
                base_resp_url = str(resp.url)
                for a_tag in soup.find_all("a", href=True):
                    href = str(a_tag.get("href") or "").strip()
                    if not href or href.startswith(("#", "javascript:", "mailto:")):
                        continue
                    abs_url = normalize_source_url(urljoin(base_resp_url, href))
                    if not abs_url or abs_url in seen_links:
                        continue
                    link_text = a_tag.get_text(" ", strip=True)
                    low_combined = f"{abs_url} {link_text}".lower()
                    if any(
                        skip in low_combined
                        for skip in ("политика", "privacy", "согласие", "инструкция_площадк", "руководство_польз")
                    ):
                        continue
                    if _ATTACHMENT_HREF_RE.search(abs_url):
                        seen_links.add(abs_url)
                        doc_links.append((abs_url, link_text))

                for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
                    tag.decompose()
                text = "\n".join(
                    line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
                )
                blocked = ("Anti-DDoS защита", "Доступ ограничен", "Access Denied", "DDoS-Guard")
                if len(text) < 120 or any(marker in text for marker in blocked):
                    continue

                etp_files: list[tuple[str, bytes]] = []
                for idx, (file_url, link_label) in enumerate(doc_links[:8], start=1):
                    if not await asyncio.to_thread(source_url_is_public, file_url):
                        continue
                    try:
                        fresp = await client.get(file_url)
                        if (
                            fresp.status_code < 400
                            and fresp.content
                            and len(fresp.content) <= 25 * 1024 * 1024
                            and not _is_html_stub_response(fresp)
                        ):
                            fallback_name = Path(urlparse(file_url).path).name or f"etp_doc_{idx}"
                            if link_label and "." in link_label and len(link_label) < 120:
                                fallback_name = link_label
                            fname = _filename_from_response(fresp, fallback_name)
                            etp_files.append((fname, fresp.content))
                    except Exception:
                        continue
                return text[:80_000], etp_files
        except Exception:
            continue
    return "", []


async def _search_small_procurement_in_source_api(
    settings: SystemSettings,
    item: dict[str, Any],
    etp_page_text: str,
) -> tuple[str, list[tuple[str, bytes]]]:
    token = str(config.tenderplan_api_token or "").strip()
    if not token:
        return "", []
    base_url = str(config.tenderplan_base_url or "https://tenderplan.ru").rstrip("/")
    exact_num = str(item.get("notice_number") or "").strip()
    raw_num = re.sub(r"\D+", "", exact_num)
    candidate_numbers: list[str] = []
    if exact_num:
        candidate_numbers.append(exact_num)
    if raw_num and raw_num not in candidate_numbers:
        candidate_numbers.append(raw_num)
    if etp_page_text:
        for m in re.findall(r"(?<!\d)(\d{7,19})(?!\d)", etp_page_text[:8000]):
            if m not in candidate_numbers:
                candidate_numbers.append(m)
            if len(candidate_numbers) >= 5:
                break

    found_candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    auth_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=15.0, headers=auth_headers) as api_client:
        for num in candidate_numbers:
            try:
                resp = await api_client.get(f"{base_url}/api/search/tender", params={"number": num})
                if resp.status_code >= 400:
                    continue
                payload = resp.json()
            except Exception:
                continue

            def _collect(node: Any) -> None:
                if isinstance(node, dict):
                    tid = str(node.get("_id") or node.get("id") or "")
                    if tid and (node.get("orderName") or node.get("number")) and tid not in seen_ids:
                        seen_ids.add(tid)
                        pub_ms = node.get("publicationDateTime")
                        pub_str = ""
                        if isinstance(pub_ms, (int, float)) and pub_ms > 0:
                            try:
                                pub_str = dt.datetime.fromtimestamp(
                                    pub_ms / 1000.0, tz=MOSCOW_TZ
                                ).strftime("%d.%m.%Y")
                            except Exception:
                                pub_str = ""
                        found_candidates.append(
                            {
                                "id": tid,
                                "number": str(node.get("number") or ""),
                                "orderName": str(node.get("orderName") or "")[:300],
                                "maxPrice": node.get("maxPrice"),
                                "published_at": pub_str,
                                "organisationsSearch": str(node.get("organisationsSearch") or "")[:200],
                            }
                        )
                    for val in node.values():
                        _collect(val)
                elif isinstance(node, list):
                    for elem in node:
                        _collect(elem)

            _collect(payload)

        if not found_candidates:
            return "", []

        raw_title = str(item.get("title") or "").strip()
        clean_title = "" if raw_title == f"Закупка {item.get('notice_number')}" else raw_title
        has_identifying_meta = bool(
            clean_title
            or str(item.get("nmck_raw") or "").strip()
            or str(item.get("customer_inn") or "").strip()
            or str(item.get("customer_name") or "").strip()
            or etp_page_text.strip()
        )

        matched_id: str | None = None
        if len(found_candidates) == 1 and not has_identifying_meta:
            matched_id = found_candidates[0]["id"]
        else:
            match_raw = await call_llm(
                settings,
                json.dumps(
                    {
                        "target": {
                            "notice_number": item.get("notice_number"),
                            "title": clean_title,
                            "nmck_raw": item.get("nmck_raw"),
                            "publication_date": item.get("publication_date"),
                            "customer_inn": item.get("customer_inn"),
                            "customer_name": item.get("customer_name"),
                            "etp_snippet": (etp_page_text or "")[:1500],
                        },
                        "candidates": found_candidates[:10],
                    },
                    ensure_ascii=False,
                ),
                system_prompt=SMALL_TENDER_MATCH_PROMPT,
                tier="light",
                json_mode=True,
                timeout_seconds=20.0,
                temperature=0.0,
            )
            parsed_match = parse_json_object(match_raw)
            if isinstance(parsed_match, dict) and parsed_match.get("matched_id"):
                cand_id = str(parsed_match["matched_id"])
                if any(c["id"] == cand_id for c in found_candidates):
                    matched_id = cand_id

        if not matched_id:
            return "", []

        try:
            fi_resp = await api_client.get(f"{base_url}/api/tenders/v2/fullinfo", params={"id": matched_id})
            if fi_resp.status_code >= 400:
                return "", []
            fullinfo = fi_resp.json()
        except Exception:
            return "", []

    tender = fullinfo.get("tender") if isinstance(fullinfo, dict) else {}
    if not isinstance(tender, dict):
        return "", []

    card_lines = [
        "=== ОФИЦИАЛЬНАЯ КАРТОЧКА МАЛОЙ ЗАКУПКИ ===",
        f"Наименование: {tender.get('orderName') or item.get('title') or ''}",
        f"НМЦК: {tender.get('maxPrice') or item.get('nmck_raw') or ''}",
    ]
    if tender.get("tenderSearch"):
        card_lines.append(f"Позиции и описание: {tender.get('tenderSearch')}")
    if tender.get("json"):
        card_lines.append(f"Структурированные поля карточки:\n{str(tender.get('json'))[:40000]}")

    docs = tender.get("attachments") or tender.get("documents") or []
    downloaded: list[tuple[str, bytes]] = []
    skipped_gated_files: list[str] = []
    if isinstance(docs, list) and docs:
        proxy = await asyncio.to_thread(_active_ru_socks_proxy)
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, proxy=proxy) as dl_client:
            for idx, doc in enumerate(docs[:12], start=1):
                if not isinstance(doc, dict):
                    continue
                href = normalize_source_url(str(doc.get("href") or doc.get("url") or "").strip())
                if not href or not await asyncio.to_thread(source_url_is_public, href):
                    continue
                fname = sanitize_filename(
                    str(doc.get("realName") or doc.get("displayName") or doc.get("name") or f"doc_{idx}.docx")
                )
                try:
                    dresp = await dl_client.get(href)
                    if dresp.status_code < 400 and dresp.content and len(dresp.content) <= 25 * 1024 * 1024:
                        if _is_html_stub_response(dresp):
                            skipped_gated_files.append(fname)
                        else:
                            downloaded.append((fname, dresp.content))
                except Exception:
                    continue

    if skipped_gated_files and not downloaded:
        card_lines.append(
            "Примечание по вложениям: файлы ("
            + ", ".join(skipped_gated_files[:5])
            + ") на стороне площадки защищены от автоматической загрузки; анализ выполнен по структурированной карточке закупки."
        )

    return "\n".join(card_lines), downloaded


async def fetch_custom_tender_bundle(
    settings: SystemSettings,
    item: dict[str, Any],
) -> CustomTenderBundle:
    raw_num = str(item.get("notice_number") or "").strip()
    digits = re.sub(r"\D+", "", raw_num)
    doc_options = parse_json_dict(settings.document_settings_json)
    row_header = _build_excel_row_header(item)

    if len(digits) in {11, 19}:
        tp_res = await asyncio.to_thread(fetch_tenderplan_source_sync, digits)
        parsed_docs: list[tuple[str, str]] = []
        if tp_res.downloaded_files:
            with tempfile.TemporaryDirectory(prefix="tlx_cb_") as tmpdir:
                for idx, f in enumerate(tp_res.downloaded_files[:25], start=1):
                    safe_name = sanitize_filename(f.filename or f"doc_{idx}")
                    fpath = Path(tmpdir) / f"{idx:02d}_{safe_name}"
                    fpath.write_bytes(f.content)
                    txt, _ = await asyncio.to_thread(extract_text, fpath, doc_options)
                    if txt and txt.strip():
                        parsed_docs.append((safe_name, txt))
        if len(parsed_docs) > 1:
            parsed_docs, _ = await asyncio.to_thread(organize_procurement_documents, parsed_docs)
        docs_ctx = combined_document_context(parsed_docs) if parsed_docs else ""
        combined = "\n\n".join(
            part for part in (row_header, _strip_internal_source_names(tp_res.context), docs_ctx) if part.strip()
        )
        if not tp_res.ok and not docs_ctx:
            return CustomTenderBundle(
                ok=False,
                error=tp_res.error or f"Не удалось выгрузить документацию по извещению {digits}",
            )
        return CustomTenderBundle(ok=True, context=combined[:160_000], files_count=len(parsed_docs))

    # Малые закупки / короткие номера / ссылки ЭТП
    etp_url = str(item.get("etp_url") or item.get("eis_url") or "").strip()
    etp_text, etp_files = await _fetch_public_etp_page(etp_url) if etp_url else ("", [])
    api_card_text, api_files = await _search_small_procurement_in_source_api(settings, item, etp_text)

    combined_raw_files: list[tuple[str, bytes]] = [*api_files, *etp_files]
    dedup_files: list[tuple[str, bytes]] = []
    seen_file_sigs: set[tuple[str, int]] = set()
    for fname, fbytes in combined_raw_files:
        sig = (fname.lower(), len(fbytes))
        if sig not in seen_file_sigs:
            seen_file_sigs.add(sig)
            dedup_files.append((fname, fbytes))

    parsed_small: list[tuple[str, str]] = []
    if dedup_files:
        with tempfile.TemporaryDirectory(prefix="tlx_cbs_") as tmpdir:
            for idx, (fname, fbytes) in enumerate(dedup_files[:20], start=1):
                fpath = Path(tmpdir) / f"{idx:02d}_{fname}"
                fpath.write_bytes(fbytes)
                txt, _ = await asyncio.to_thread(extract_text, fpath, doc_options)
                if txt and txt.strip():
                    parsed_small.append((fname, txt))
    if len(parsed_small) > 1:
        parsed_small, _ = await asyncio.to_thread(organize_procurement_documents, parsed_small)
    small_docs_ctx = combined_document_context(parsed_small) if parsed_small else ""
    etp_block = f"=== СТРАНИЦА ПЛОЩАДКИ ЗАКУПКИ ({etp_url}) ===\n{etp_text}" if etp_text else ""

    if not etp_text and not api_card_text and not small_docs_ctx:
        return CustomTenderBundle(
            ok=False,
            error=(
                f"По малой закупке № {raw_num} площадка закрыта от автоматической выгрузки и нет "
                "документов в базе ЕИС (плата за эту позицию не списана)."
            ),
        )

    combined_small = "\n\n".join(
        part
        for part in (row_header, _strip_internal_source_names(api_card_text), etp_block, small_docs_ctx)
        if part.strip()
    )
    return CustomTenderBundle(ok=True, context=combined_small[:160_000], files_count=len(parsed_small))


async def _resolve_single_vertex_redirect(client: httpx.AsyncClient, redirect_url: str) -> str:
    try:
        resp = await client.get(redirect_url, follow_redirects=False)
        if resp.status_code in {301, 302, 303, 307, 308}:
            loc = normalize_source_url(str(resp.headers.get("location") or "").strip())
            if loc and await asyncio.to_thread(source_url_is_public, loc):
                return loc
    except Exception:
        pass
    return redirect_url


async def _unwrap_grounding_urls(
    markdown: str,
    grounding_chunks: list[dict[str, Any]],
) -> tuple[str, list[dict[str, str]]]:
    inline_redirects = list(dict.fromkeys(VERTEX_REDIRECT_RE.findall(markdown or "")))
    chunk_items: list[tuple[str, str]] = []
    for ch in grounding_chunks[:50]:
        web = ch.get("web") if isinstance(ch, dict) else None
        if isinstance(web, dict) and web.get("uri"):
            chunk_items.append((str(web.get("title") or "Источник"), str(web["uri"])))

    all_to_resolve = list(
        dict.fromkeys(
            [*inline_redirects, *(uri for _, uri in chunk_items if uri.startswith("https://vertexaisearch."))]
        )
    )
    resolved_map: dict[str, str] = {}
    if all_to_resolve:
        async with httpx.AsyncClient(timeout=4.5) as client:
            tasks = [_resolve_single_vertex_redirect(client, u) for u in all_to_resolve[:50]]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for orig, res in zip(all_to_resolve[:50], results):
                if isinstance(res, str) and res:
                    resolved_map[orig] = res

    updated_md = markdown
    for orig, real_u in resolved_map.items():
        updated_md = updated_md.replace(orig, real_u)

    non_seller_domains = (
        "zakupki.gov.ru",
        "kontur.ru",
        "tenderplan.ru",
        "consultant.ru",
        "garant.ru",
        "zakon.guru",
        "moy-zakupki.ru",
        "sprosradar.ru",
        "synapsenet.ru",
        "rusprofile.ru",
        "sudact.ru",
        "zakupki44fz.ru",
        "tzfz.ru",
        "rostender.info",
        "gkgz.ru",
        "tendergo.pro",
        "spark-interfax.ru",
        "rostrud.gov.ru",
    )
    sources: list[dict[str, str]] = []
    seen_uris: set[str] = set()
    for title, uri in chunk_items:
        final_u = resolved_map.get(uri, uri)
        if not final_u or final_u in seen_uris or "vertexaisearch.cloud.google.com" in final_u:
            continue
        if any(skip in final_u.lower() for skip in non_seller_domains):
            continue
        seen_uris.add(final_u)
        sources.append({"title": title, "url": final_u})

    return updated_md, sources[:10]


def _gemini_gateway_config(settings: SystemSettings) -> tuple[str, str, list[str]]:
    providers = custom_provider_map(settings)
    gemini_prov = providers.get("gemini")
    if not gemini_prov:
        raise RuntimeError("Провайдер Gemini не настроен в системе.")
    raw_base = str(gemini_prov.get("baseUrl") or "http://127.0.0.1:8318/v1").strip().rstrip("/")
    if raw_base.endswith("/v1"):
        raw_base = raw_base[:-3]
    api_key = str(gemini_prov.get("apiKey") or "").strip()
    if not api_key:
        raise RuntimeError("Ключ локального шлюза Gemini не задан.")
    primary = str(settings.primary_model or "gemini-4-hydrogen-xhigh").strip()
    candidates = list(
        dict.fromkeys(
            m
            for m in [primary, "gemini-4-argon-high", "gemini-3.8-flash-high", "gemini-3-flash"]
            if m
        )
    )
    return raw_base, api_key, candidates


async def run_custom_prompt_with_gemini_search(
    settings: SystemSettings,
    *,
    custom_prompt: str,
    document_context: str,
    procurement_label: str = "",
) -> CustomPromptRunResult:
    base_url, api_key, model_candidates = _gemini_gateway_config(settings)
    today_str = dt.datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y")
    effective_prompt = str(custom_prompt or "").strip() or DEFAULT_EXPRESS_ASSESSMENT_PROMPT
    system_text = (
        f"{effective_prompt}\n\n"
        f"Дополнительные системные правила выполнения (актуальная дата: {today_str}):\n"
        "1. Обязательно используй встроенный поиск Google (google_search), чтобы найти реальный "
        "коммерческий товар/модель в продаже в РФ с актуальной ценой и обязательно вставь прямую "
        "кликабельную ссылку [Название товара / Магазин](https://...) на страницу конкретного товара "
        "у продавца в разделе подбора товара, а также сайты поставщиков/производителей в разделе поставщиков.\n"
        "2. Строго соблюдай порядок и структуру разделов, а также все условные правила из инструкции выше (не переставляй разделы местами).\n"
        "3. Никогда не упоминай в тексте технические названия агрегаторов данных (например, Tenderplan).\n"
        "4. Визуальное оформление и читаемость (никакого «сплошного полотна текста»):\n"
        "   - Каждый крупный блок оформляй нумерованным заголовком `### 1. ...`, `### 2. ...` строго в порядке инструкции выше.\n"
        "   - Для ключевых параметров закупки и финансово-маржинального расчёта оформляй наглядную двухколоночную Markdown-таблицу `| Показатель | Значение |`, а перед таблицей финансово-маржинального расчёта выделяй короткий абзац `**ИТОГОВЫЙ ВЕРДИКТ:** ...` с главным выводом. В строке расчётной маржи указывай конкретную сумму в рублях и процент, например: `| **Расчётная Валовая Маржа** | **75 000 ₽ (22,5%)** |` (или со знаком `−` при убыточности).\n"
        "   - В сравнительной таблице соответствия позиций в колонке статуса пиши чёткий статус в начале ячейки (`Соответствует`, `Условно соответствует` или `Отклонение`).\n"
        "   - Избегай длинных простыней текста: разбивай детали на короткие списки `* **Параметр:** значение` и нумерованные карточки `1. **...**` с вложенными подпунктами.\n"
        "5. Справочная правовая памятка ниже предназначена только для внутренних расчётов и проверки фактов — НЕ переписывай её как шаблонные абзацы в текст отчёта и строго соблюдай любые запреты/исключения из инструкции клиента выше.\n\n"
        f"{PROCUREMENT_LEGAL_BASELINE}"
    )
    user_text = (
        f"Проанализируй закупочную документацию{f' ({procurement_label})' if procurement_label else ''}:\n\n"
        f"{clean_surrogates(document_context)[:140_000]}"
    )

    last_err = "Не удалось получить ответ модели Gemini"
    for model_id in model_candidates:
        payload = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.2},
        }
        already_held = _llm_limiter_held_var.get()
        if not already_held:
            await _process_llm_limiter.acquire(timeout=180.0)
            token = _llm_limiter_held_var.set(True)
        else:
            token = None
        try:
            async with httpx.AsyncClient(timeout=150.0) as client:
                resp = await client.post(
                    f"{base_url}/v1beta/models/{model_id}:generateContent",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
        except Exception as exc:
            last_err = str(exc)
            continue
        finally:
            if token is not None:
                _llm_limiter_held_var.reset(token)
                _process_llm_limiter.release()

        if resp.status_code >= 400:
            last_err = f"HTTP {resp.status_code} ({model_id})"
            continue

        data = resp.json()
        cand = (data.get("candidates") or [{}])[0]
        parts = cand.get("content", {}).get("parts") or []
        raw_md = "\n".join(str(p.get("text") or "") for p in parts if isinstance(p, dict) and p.get("text")).strip()
        if not raw_md:
            last_err = f"Пустой ответ модели ({model_id})"
            continue

        grounding_meta = cand.get("groundingMetadata") or {}
        chunks = grounding_meta.get("groundingChunks") or []
        clean_md = _strip_internal_source_names(raw_md)
        clean_md, resolved_sources = await _unwrap_grounding_urls(clean_md, chunks)

        if resolved_sources and "http" not in clean_md:
            links_block = "\n".join(f"* [{s['title']}]({s['url']})" for s in resolved_sources[:5])
            clean_md = f"{clean_md}\n\n---\n#### Найденные ссылки на товар и продавцов:\n{links_block}"

        return CustomPromptRunResult(markdown=clean_md, model=model_id, sources=resolved_sources)

    raise RuntimeError(last_err)


def _extract_subject_fallback(markdown: str, context: str) -> str:
    for text in (markdown, context):
        for pat in (
            r"\*{0,2}Наименование объекта закупки\*{0,2}\s*[:\-]\s*(.+)",
            r"\*{0,2}(?:Предмет|Объект|Наименование)\s+закупк[ии]\*{0,2}\s*[:\-]\s*(.+)",
        ):
            m = re.search(pat, str(text or ""), flags=re.IGNORECASE)
            if m:
                cleaned = re.sub(r"[*_`]+", "", m.group(1)).strip(" .:—-")
                if cleaned and len(cleaned) >= 4:
                    return cleaned[:300]
    return ""


async def execute_custom_batch_items(
    settings: SystemSettings,
    *,
    custom_prompt: str,
    items: list[dict[str, Any]],
    on_item_done: Callable[[int, dict[str, Any], list[dict[str, Any]]], None] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = [
        {
            "index": idx,
            "id": str(it.get("id") or f"item-{idx}"),
            "notice_number": str(it.get("notice_number") or ""),
            "title": str(it.get("title") or ""),
            "nmck_raw": str(it.get("nmck_raw") or ""),
            "publication_date": str(it.get("publication_date") or ""),
            "deadline_date": str(it.get("deadline_date") or ""),
            "procurement_type": str(it.get("procurement_type") or ""),
            "kontur_url": clean_kontur_url(str(it.get("kontur_url") or "")),
            "eis_url": normalize_source_url(str(it.get("eis_url") or "")),
            "etp_url": normalize_source_url(str(it.get("etp_url") or "")),
            "status": "pending",
            "report_markdown": "",
            "ai_model": "",
            "sources": [],
            "error": "",
            "docx_filename": "",
        }
        for idx, it in enumerate(items)
    ]

    sem = asyncio.Semaphore(3)

    async def _run_one(idx: int, raw_item: dict[str, Any]) -> None:
        async with sem:
            if check_cancelled:
                await asyncio.to_thread(check_cancelled)
            results[idx]["status"] = "running"
            bundle = await fetch_custom_tender_bundle(settings, raw_item)
            if not bundle.ok:
                results[idx]["status"] = "failed"
                results[idx]["error"] = bundle.error
                if on_item_done:
                    await asyncio.to_thread(on_item_done, idx, results[idx], results)
                return
            if check_cancelled:
                await asyncio.to_thread(check_cancelled)
            try:
                notice_no = str(raw_item.get("notice_number") or "").strip()
                raw_title = str(raw_item.get("title") or "").strip()
                is_placeholder_title = not raw_title or raw_title == f"Закупка {notice_no}"
                label = (
                    f"№ {notice_no}"
                    if is_placeholder_title
                    else f"№ {notice_no} — {raw_title[:80]}"
                ).strip(" —")
                ai_res = await run_custom_prompt_with_gemini_search(
                    settings,
                    custom_prompt=custom_prompt,
                    document_context=bundle.context,
                    procurement_label=label,
                )
                if is_placeholder_title:
                    discovered = _extract_subject_fallback(ai_res.markdown, bundle.context)
                    if discovered:
                        results[idx]["title"] = discovered
                results[idx]["status"] = "completed"
                results[idx]["report_markdown"] = ai_res.markdown
                results[idx]["ai_model"] = ai_res.model
                results[idx]["sources"] = ai_res.sources
                results[idx] = enrich_batch_result_item(results[idx], spec_item=raw_item)
            except Exception as exc:
                logger.warning("Custom batch item %s failed: %s", raw_item.get("notice_number"), exc)
                results[idx]["status"] = "failed"
                results[idx]["error"] = "Не удалось сформировать ответ ИИ по закупке."
            if on_item_done:
                await asyncio.to_thread(on_item_done, idx, results[idx], results)

    await asyncio.gather(*(_run_one(i, it) for i, it in enumerate(items)))
    return results
