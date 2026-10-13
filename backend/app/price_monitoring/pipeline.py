from __future__ import annotations

import asyncio
import io
import logging
import os
import statistics
from typing import Any, Callable, List, Optional
from urllib.parse import urlparse

import httpx
import openpyxl

from ..exact_product.yandex_search import YandexSearchEngine
from ..models import SystemSettings
from .cleaner import build_commercial_search_queries, clean_nomenclature_name, normalize_unit
from .excel_report import generate_price_monitoring_excel
from .extractor import extract_supplier_quote, fetch_page_content_and_meta, is_valid_domain
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


def validate_and_reconcile_item_quotes(item_res: ItemPriceResult) -> None:
    """
    Кросс-валидация котировок по одной позиции:
    1. Обнаружение расхождений в кратности (баллоны, тонны/кг, упаковки/штуки).
    2. Авто-приведение к единице заказчика, если какой-то поставщик указал цену за всю тару.
    3. Выявление и маркировка экстремальных статистических выбросов.
    """
    valid_quotes = [q for q in item_res.quotes if q.price_rub > 0]
    if len(valid_quotes) < 2:
        return

    prices = [q.price_rub for q in valid_quotes]
    min_p = min(prices)
    max_p = max(prices)
    ratio = max_p / min_p if min_p > 0 else 1.0

    # Если цены разнятся более чем в 3 раза, проверяем типовые кратности фасовок
    if ratio >= 3.0:
        item_lower = item_res.clean_name.lower()
        norm_u = normalize_unit(item_res.unit)

        for q in valid_quotes:
            q_ratio = q.price_rub / min_p

            # 1. Пропан (баллон 50л vs кг, коэффициент 21)
            if "пропан" in item_lower and norm_u in ("кг", "к-г"):
                if 14.0 <= q_ratio <= 35.0:
                    converted = round(q.price_rub / 21.0, 2)
                    q.price_rub = converted
                    q.conversion_comment = f"Авто-пересчет кратности: {q.raw_price_rub:,.0f} ₽ за баллон 50л -> {converted:,.2f} ₽/кг"

            # 2. Кислород (баллон 40л vs м3, коэффициент 6.3)
            elif "кислород" in item_lower and norm_u in ("м3", "куб"):
                if 4.5 <= q_ratio <= 14.0:
                    converted = round(q.price_rub / 6.3, 2)
                    q.price_rub = converted
                    q.conversion_comment = f"Авто-пересчет кратности: {q.raw_price_rub:,.0f} ₽ за баллон 40л -> {converted:,.2f} ₽/м³"

            # 3. Вес и сыпучие: Тонна <-> Килограмм
            if norm_u in ("кг", "к-г") and q_ratio >= 400.0 and q.price_rub > 20000:
                converted = round(q.price_rub / 1000.0, 2)
                q.price_rub = converted
                q.conversion_comment = f"Авто-пересчет кратности: {q.raw_price_rub:,.0f} ₽ за тонну -> {converted:,.2f} ₽/кг"
            elif norm_u in ("т", "тонна") and (max_p / q.price_rub) >= 300.0 and q.price_rub < 3000:
                converted = round(q.price_rub * 1000.0, 2)
                q.price_rub = converted
                q.conversion_comment = f"Авто-пересчет кратности: {q.raw_price_rub:,.2f} ₽/кг -> {converted:,.0f} ₽/т"

            # 4. Цемент в мешках: 50 кг vs тонна (20 мешков в тонне)
            elif norm_u in ("т", "тонна") and "цемент" in item_lower and (max_p / q.price_rub) >= 15.0 and q.price_rub < 1500:
                converted = round(q.price_rub * 20.0, 2)
                q.price_rub = converted
                q.conversion_comment = f"Авто-пересчет кратности: {q.raw_price_rub:,.0f} ₽ за мешок 50 кг -> {converted:,.0f} ₽/т"

            # 5. ГСМ и жидкости: Бочка 200л vs Литр
            elif norm_u in ("л", "литр") and (q_ratio >= 100.0 or (max_p / q.price_rub) >= 100.0) and q.price_rub > 15000:
                converted = round(q.price_rub / 200.0, 2)
                q.price_rub = converted
                q.conversion_comment = f"Авто-пересчет кратности: {q.raw_price_rub:,.0f} ₽ за бочку 200л -> {converted:,.2f} ₽/л"

            # 6. Пиломатериалы: штука vs м³
            elif norm_u in ("м3", "куб") and any(w in item_lower for w in ("доск", "брус", "пиломатериал")) and (max_p / q.price_rub) >= 10.0 and q.price_rub < 3000:
                q.is_outlier = True
                q.comment = f"⚠️ Цена {q.price_rub:,.0f} ₽ указана за штуку (хлыст), а не за м³. Рекомендуется проверить кубатуру."

            # 7. Упаковки по 100 шт vs штука
            elif norm_u == "шт" and 70.0 <= q_ratio <= 130.0 and "100" in item_lower:
                converted = round(q.price_rub / 100.0, 2)
                q.price_rub = converted
                q.conversion_comment = f"Авто-пересчет кратности: {q.raw_price_rub:,.0f} ₽ за уп (100 шт) -> {converted:,.2f} ₽/шт"

        # Проверка статистических выбросов по медиане после пересчета
        updated_prices = [q.price_rub for q in valid_quotes]
        med_p = statistics.median(updated_prices)
        for q in valid_quotes:
            if q.price_rub > med_p * 3.5 or (med_p > 0 and q.price_rub < med_p / 3.5):
                q.is_outlier = True
                warning_note = f"⚠️ Цена {q.price_rub:,.2f} ₽ существенно отличается от среднерыночной ({med_p:,.2f} ₽). Рекомендуется проверить фасовку."
                q.comment = f"{q.comment} | {warning_note}".strip(" |")

    # Сортируем: сначала подтвержденные цены без статуса выброса
    item_res.quotes.sort(key=lambda q: (q.is_outlier, q.price_rub if q.price_rub > 0 else 999_999_999))


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
        for q in queries[:4]:
            try:
                results = await engine.search(q, max_results=8, enrich_query=False, filter_marketplaces=False)
                for r in results:
                    if r.url and is_valid_domain(r.url) and r.url not in candidate_urls:
                        candidate_urls.append(r.url)
            except Exception as e:
                logger.warning("Search query error for %s: %s", q, e)
            if len(candidate_urls) >= 15:
                break

    # Сбор и извлечение цен с найденных страниц
    seen_domains: set[str] = set()
    for url in candidate_urls:
        if len(item_res.quotes) >= max_suppliers:
            break
        try:
            domain = urlparse(url).netloc.lower()
            if domain in seen_domains:
                continue

            page_text, inn, kpp, contacts = await fetch_page_content_and_meta(http_client, url)
            if not page_text or len(page_text) < 60:
                continue

            quote = await extract_supplier_quote(
                settings=settings,
                target_item_name=clean,
                target_unit=unit,
                url=url,
                page_text=page_text,
                pre_inn=inn,
                pre_kpp=kpp,
                pre_contacts=contacts,
            )
            if quote and quote.is_price_found and quote.price_rub > 0:
                seen_domains.add(domain)
                item_res.quotes.append(quote)
        except Exception as exc:
            logger.debug("Error processing url %s: %s", url, exc)

    # Кросс-проверка и устранение аномалий между поставщиками
    validate_and_reconcile_item_quotes(item_res)

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
