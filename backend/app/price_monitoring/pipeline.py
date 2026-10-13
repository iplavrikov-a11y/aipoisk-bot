from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Any, Callable, List, Optional
import httpx
import openpyxl

from ..exact_product.yandex_search import YandexSearchEngine
from ..models import SystemSettings
from .cleaner import build_commercial_search_queries, clean_nomenclature_name
from .excel_report import generate_price_monitoring_excel
from .extractor import extract_supplier_quote, fetch_page_content, is_valid_domain
from .models import BatchMonitoringResult, ItemPriceResult, SupplierQuote

logger = logging.getLogger(__name__)


def parse_input_excel(file_bytes: bytes) -> List[tuple[str, str]]:
    """Читает загруженный Excel-файл и извлекает кортежи (номенклатура, единица_измерения)."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    items: List[tuple[str, str]] = []

    # Определяем индексы колонок
    nom_col = 1
    unit_col = 2
    start_row = 1

    # Ищем заголовки в первых 10 строках
    for r in range(1, min(15, ws.max_row + 1)):
        for c in range(1, min(10, ws.max_column + 1)):
            val = str(ws.cell(row=r, column=c).value or "").strip().lower()
            if "номенклатур" in val or "наименован" in val or "товар" in val:
                nom_col = c
                start_row = r + 1
            elif "ед." in val or "ед.изм" in val or "единиц" in val:
                unit_col = c

    # Считываем строки данных
    for r in range(start_row, ws.max_row + 1):
        nom_val = str(ws.cell(row=r, column=nom_col).value or "").strip()
        unit_val = str(ws.cell(row=r, column=unit_col).value or "").strip()
        if not nom_val:
            continue
        # Пропускаем повторные заголовки
        if nom_val.lower().startswith("номенклатур") or nom_val.lower().startswith("наименован"):
            continue
        items.append((nom_val, unit_val or "шт"))

    return items


async def process_single_item(
    item_tuple: tuple[int, str, str],
    engine: YandexSearchEngine,
    settings: SystemSettings,
    http_client: httpx.AsyncClient,
    search_semaphore: asyncio.Semaphore,
    max_suppliers: int = 5,
) -> ItemPriceResult:
    row_idx, raw_name, unit = item_tuple
    clean = clean_nomenclature_name(raw_name)
    item_res = ItemPriceResult(
        row_number=row_idx,
        raw_name=raw_name,
        clean_name=clean,
        unit=unit,
    )

    queries = build_commercial_search_queries(clean, unit)
    candidate_urls: list[str] = []

    async with search_semaphore:
        for q in queries[:2]:
            try:
                results = await engine.search(q, max_results=8, enrich_query=False)
                for r in results:
                    if r.url and is_valid_domain(r.url) and r.url not in candidate_urls:
                        candidate_urls.append(r.url)
            except Exception as e:
                logger.warning("Search query error for %s: %s", q, e)
            if len(candidate_urls) >= 12:
                break

    # Сбор и извлечение цен с найденных страниц
    seen_domains: set[str] = set()
    for url in candidate_urls:
        if len(item_res.quotes) >= max_suppliers:
            break
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            if domain in seen_domains:
                continue

            page_text = await fetch_page_content(http_client, url)
            if not page_text or len(page_text) < 60:
                continue

            quote = await extract_supplier_quote(
                settings=settings,
                target_item_name=clean,
                target_unit=unit,
                url=url,
                page_text=page_text,
            )
            if quote and quote.is_price_found and quote.price_rub > 0:
                seen_domains.add(domain)
                item_res.quotes.append(quote)
        except Exception as exc:
            logger.debug("Error processing url %s: %s", url, exc)

    item_res.status = "found" if item_res.has_prices else "not_found"
    return item_res


async def run_price_monitoring_pipeline(
    file_bytes: bytes,
    settings: SystemSettings,
    output_excel_path: str,
    price_per_position_rub: float = 50.0,
    progress_callback: Optional[Callable[[int, str], Any]] = None,
    max_suppliers: int = 5,
    max_parallel_items: int = 5,
) -> BatchMonitoringResult:
    """Полный пайплайн мониторинга цен по загруженному Excel-файлу."""
    parsed_items = parse_input_excel(file_bytes)
    total = len(parsed_items)
    if total == 0:
        raise ValueError("В загруженном файле не найдено строк с номенклатурой.")

    if progress_callback:
        progress_callback(5, f"Загружено {total} позиций из файла")

    engine = YandexSearchEngine(
        folder_id=settings.yandex_search_folder_id,
        api_key=settings.yandex_search_api_key,
    )
    search_sem = asyncio.Semaphore(3)  # ограничиваем частоту к Yandex API

    results: List[ItemPriceResult] = []
    completed = 0

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http_client:
        # Обрабатываем пакетами с контролируемым параллелизмом
        batch_size = max_parallel_items
        for i in range(0, total, batch_size):
            chunk = [(idx + 1, nom, unit) for idx, (nom, unit) in enumerate(parsed_items[i : i + batch_size], start=i)]
            tasks = [
                process_single_item(item, engine, settings, http_client, search_sem, max_suppliers=max_suppliers)
                for item in chunk
            ]
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in chunk_results:
                if isinstance(r, ItemPriceResult):
                    results.append(r)
                else:
                    logger.error("Item processing exception: %s", r)

            completed += len(chunk)
            pct = 10 + int((completed / total) * 80)
            if progress_callback:
                progress_callback(pct, f"Обработано {completed} из {total} позиций...")

    await engine.close()

    # Генерация результирующего Excel-файла
    generate_price_monitoring_excel(results, output_excel_path, max_suppliers=max_suppliers)

    found_count = sum(1 for it in results if it.has_prices)
    not_found_count = total - found_count
    total_charged_rub = round(found_count * price_per_position_rub, 2)

    if progress_callback:
        progress_callback(100, f"Готово! Найдено цен для {found_count} из {total} позиций")

    return BatchMonitoringResult(
        job_id="",
        total_positions=total,
        found_positions=found_count,
        not_found_positions=not_found_count,
        price_per_position_rub=price_per_position_rub,
        total_charged_rub=total_charged_rub,
        items=results,
        output_excel_path=output_excel_path,
    )
