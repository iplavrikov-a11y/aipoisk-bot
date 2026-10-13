from __future__ import annotations

import asyncio
from dataclasses import asdict
import io
import json
import logging
import os
import statistics
from typing import Any, Callable, List, Optional
from urllib.parse import urlparse

import httpx
import openpyxl

from ..exact_product.yandex_search import YandexSearchEngine, YandexSearchResult
from ..models import SystemSettings
from .cleaner import (
    build_commercial_search_queries,
    build_fallback_broad_queries,
    clean_nomenclature_name,
    normalize_unit,
)
from .excel_report import generate_price_monitoring_excel
from .extractor import extract_supplier_quote, fetch_page_content_and_meta, is_valid_domain
from .models import BatchMonitoringResult, ItemPriceResult, SupplierQuote

logger = logging.getLogger(__name__)

# Реестр федеральных ритейлеров с официальными юрлицами и ИНН для гарантированной точности реквизитов
KNOWN_MAJOR_RETAILERS: dict[str, dict[str, str]] = {
    "vseinstrumenti.ru": {
        "company_name": 'ООО "Всеинструменты.ру"',
        "inn": "7722753969",
        "contacts": "+7 (800) 550-37-70, г. Москва",
    },
    "etm.ru": {
        "company_name": 'ООО "ЭТМ"',
        "inn": "7804028214",
        "contacts": "+7 (800) 775-17-71, г. Санкт-Петербург",
    },
    "chipdip.ru": {
        "company_name": 'АО "Чип и Дип"',
        "inn": "7709022648",
        "contacts": "+7 (800) 555-62-70, г. Москва",
    },
    "rs24.ru": {
        "company_name": 'ООО "Русский Свет"',
        "inn": "6901032540",
        "contacts": "+7 (800) 777-70-04, г. Тверь",
    },
    "lemanapro.ru": {
        "company_name": 'ООО "Лемана ПРО"',
        "inn": "5029069967",
        "contacts": "+7 (800) 700-00-99, г. Мытищи",
    },
    "dns-shop.ru": {
        "company_name": 'ООО "ДНС Ритейл"',
        "inn": "2540167061",
        "contacts": "+7 (800) 770-79-99, г. Владивосток",
    },
    "komus.ru": {
        "company_name": 'ООО "Комус"',
        "inn": "7721793895",
        "contacts": "+7 (800) 200-33-83, г. Москва",
    },
}


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


def cluster_and_reconcile_item_quotes(item_res: ItemPriceResult, cluster_ratio: float = 2.2) -> None:
    """
    1. Авто-приведение кратностей (баллоны 50л -> кг, м3 -> штуки, мешки 50кг -> т, упаковки 100 шт).
    2. Кластеризация цен (Price Clustering):
       Находит наибольший согласованный кластер близких цен (где max_p / min_p <= cluster_ratio).
    3. Жесткая отсечка выбросов:
       Все цены вне согласованного кластера маркируются is_outlier = True и исключаются из клиентского отчета.
    4. Если согласованного кластера нет (все цены разрознены и отличаются более чем в cluster_ratio раз):
       маркировать котировки как несогласованные выбросы, не выводить в отчет сомнительные цены.
    """
    valid_quotes = [q for q in item_res.quotes if q.price_rub > 0]
    if not valid_quotes:
        return

    # 1. Приведение кратностей фасовок
    if len(valid_quotes) >= 2:
        prices = [q.price_rub for q in valid_quotes]
        min_p = min(prices)
        max_p = max(prices)
        ratio = max_p / min_p if min_p > 0 else 1.0

        if ratio >= 2.5:
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
                    q.comment = f"⚠️ Цена {q.price_rub:,.0f} ₽ указана за штуку, а не за м³."

                # 7. Упаковки по 100 шт vs штука
                elif norm_u == "шт" and 70.0 <= q_ratio <= 130.0 and "100" in item_lower:
                    converted = round(q.price_rub / 100.0, 2)
                    q.price_rub = converted
                    q.conversion_comment = f"Авто-пересчет кратности: {q.raw_price_rub:,.0f} ₽ за уп (100 шт) -> {converted:,.2f} ₽/шт"

    # 2. Кластеризация цен (Price Clustering)
    valid_quotes = [q for q in item_res.quotes if q.price_rub > 0 and not q.is_outlier]
    if len(valid_quotes) <= 1:
        return

    valid_quotes.sort(key=lambda q: q.price_rub)
    k = len(valid_quotes)

    # Ищем все возможные непрерывные кластеры цен, где p_max / p_min <= cluster_ratio
    clusters: list[list[SupplierQuote]] = []
    for i in range(k):
        for j in range(i, k):
            p_min = valid_quotes[i].price_rub
            p_max = valid_quotes[j].price_rub
            if p_min > 0 and (p_max / p_min) <= cluster_ratio:
                clusters.append(valid_quotes[i : j + 1])

    if not clusters:
        return

    max_size = max(len(c) for c in clusters)
    candidate_clusters = [c for c in clusters if len(c) == max_size]

    best_cluster = candidate_clusters[0]
    if len(candidate_clusters) > 1:
        def _rel_spread(cl: list[SupplierQuote]) -> float:
            p_vals = [q.price_rub for q in cl]
            return (max(p_vals) - min(p_vals)) / (statistics.mean(p_vals) or 1.0)
        best_cluster = min(candidate_clusters, key=_rel_spread)

    best_ids = {id(q) for q in best_cluster}

    if max_size >= 2:
        # Сформирован согласованный кластер из >= 2 источников
        min_cp = min(q.price_rub for q in best_cluster)
        max_cp = max(q.price_rub for q in best_cluster)
        for q in item_res.quotes:
            if id(q) not in best_ids:
                q.is_outlier = True
                q.comment = f"⚠️ Исключена: цена {q.price_rub:,.2f} ₽ вне согласованного кластера ({min_cp:,.2f} - {max_cp:,.2f} ₽)"
    else:
        # max_size == 1: все цены разрознены более чем в cluster_ratio раз
        # Пользовательское правило: если сильно разнятся, источники в отчет не выводить
        for q in item_res.quotes:
            q.is_outlier = True
            q.comment = f"⚠️ Цены поставщиков имеют сильный разброс (>{cluster_ratio}x). Единый ценовой кластер не сформирован."

    # Сортируем: сначала подтвержденный кластер по возрастанию цены, затем исключенные
    item_res.quotes.sort(key=lambda q: (q.is_outlier, q.price_rub if q.price_rub > 0 else 999_999_999))


# Псевдоним для обратной совместимости
validate_and_reconcile_item_quotes = cluster_and_reconcile_item_quotes


def _save_checkpoint(checkpoint_path: str, results: list[ItemPriceResult], total: int) -> None:
    """Атомарно сохраняет промежуточный прогресс для защиты от сбоев и перезапусков."""
    try:
        tmp_path = checkpoint_path + ".tmp"
        payload = {
            "total": total,
            "completed": len(results),
            "items": [
                {
                    "row_number": r.row_number,
                    "raw_name": r.raw_name,
                    "clean_name": r.clean_name,
                    "unit": r.unit,
                    "status": r.status,
                    "quotes": [asdict(q) for q in r.quotes],
                }
                for r in results
            ],
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, checkpoint_path)
    except Exception as exc:
        logger.warning("Checkpoint save error: %s", exc)


def _load_checkpoint(checkpoint_path: str) -> list[ItemPriceResult]:
    """Загружает сохраненные результаты, если задача была прервана."""
    results: list[ItemPriceResult] = []
    if not os.path.exists(checkpoint_path):
        return results
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for it in data.get("items", []):
                quotes = [SupplierQuote(**q) for q in it.get("quotes", [])]
                item_obj = ItemPriceResult(
                    row_number=it["row_number"],
                    raw_name=it["raw_name"],
                    clean_name=it["clean_name"],
                    unit=it["unit"],
                    quotes=quotes,
                    status=it.get("status", "found"),
                )
                results.append(item_obj)
        logger.info("Loaded %d completed items from checkpoint %s", len(results), checkpoint_path)
    except Exception as exc:
        logger.warning("Checkpoint load error %s: %s", checkpoint_path, exc)
    return results


async def process_single_item(
    item_tuple: tuple[int, str, str],
    engine: YandexSearchEngine,
    settings: SystemSettings,
    http_client: httpx.AsyncClient,
    search_semaphore: asyncio.Semaphore,
    max_suppliers: int = 3,
    min_target_suppliers: int = 3,
    cluster_ratio: float = 2.2,
    filter_marketplaces: bool = True,
) -> ItemPriceResult:
    row_idx, raw_name, unit = item_tuple
    clean = clean_nomenclature_name(raw_name)
    item_res = ItemPriceResult(
        row_number=row_idx,
        raw_name=raw_name,
        clean_name=clean,
        unit=unit,
    )

    candidate_urls: list[str] = []
    url_to_meta: dict[str, YandexSearchResult] = {}

    # ВОЛНА 1: Первичные коммерческие запросы (розница, опт, склады, каталоги)
    queries = build_commercial_search_queries(clean, unit)
    async with search_semaphore:
        for q in queries[:4]:
            try:
                results = await engine.search(
                    q, max_results=20, enrich_query=False, filter_marketplaces=filter_marketplaces
                )
                for r in results:
                    if r.url and is_valid_domain(r.url, target_item_name=clean, filter_marketplaces=filter_marketplaces):
                        url_to_meta[r.url] = r
                        if r.url not in candidate_urls:
                            candidate_urls.append(r.url)
            except Exception as e:
                logger.warning("Search query error for %s: %s", q, e)
            if len(candidate_urls) >= 30:
                break

    # Сбор и извлечение цен с найденных страниц
    seen_domains: set[str] = set()

    # Оцениваем до (max_suppliers + 2) котировок, чтобы алгоритм кластеризации имел запас для отсева выбросов
    target_eval_quotes = max(4, max_suppliers + 2)

    async def _evaluate_candidates(urls: list[str]) -> None:
        for url in urls:
            valid_found = len([q for q in item_res.quotes if q.is_price_found and q.price_rub > 0])
            if valid_found >= target_eval_quotes:
                break
            try:
                domain = urlparse(url).netloc.lower().replace("www.", "")
                if domain in seen_domains:
                    continue

                page_text, inn, kpp, contacts = await fetch_page_content_and_meta(http_client, url)
                meta = url_to_meta.get(url)

                # Объединяем сниппет поисковой выдачи со страницей (критично при WAF, динамическом JS или капче)
                snippet_block = ""
                if meta and (meta.snippet or meta.title):
                    snippet_block = f"[ПОИСКОВЫЙ СНИППЕТ ЯНДЕКСА]: {meta.title} | {meta.snippet}\n\n"

                if not page_text or len(page_text) < 60:
                    if snippet_block:
                        page_text = snippet_block + f"Источник: {url}"
                    else:
                        continue
                else:
                    page_text = snippet_block + page_text

                if not page_text or len(page_text) < 30:
                    continue

                # Реестр федеральных сетей
                for kd, kdata in KNOWN_MAJOR_RETAILERS.items():
                    if kd in domain:
                        if not inn:
                            inn = kdata["inn"]
                        if not contacts:
                            contacts = kdata["contacts"]
                        break

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
                    for kd, kdata in KNOWN_MAJOR_RETAILERS.items():
                        if kd in domain:
                            quote.company_name = kdata["company_name"]
                            quote.inn = kdata["inn"]
                            if not quote.contacts:
                                quote.contacts = kdata["contacts"]
                            break
                    seen_domains.add(domain)
                    item_res.quotes.append(quote)
            except Exception as exc:
                logger.debug("Error processing url %s: %s", url, exc)

    await _evaluate_candidates(candidate_urls)

    # ВОЛНА 2 (АДАПТИВНЫЙ ПОИСК ДЛЯ ДОСТИЖЕНИЯ КВОРУМА):
    # Если найдено менее min_target_suppliers подтвержденных цен,
    # запускаем расширенные запросы без жестких ограничений и с отраслевым контекстом
    valid_count = len([q for q in item_res.quotes if q.is_price_found and q.price_rub > 0])
    if valid_count < min_target_suppliers:
        fallback_queries = build_fallback_broad_queries(clean, unit)
        wave2_urls: list[str] = []
        async with search_semaphore:
            for bq in fallback_queries[:4]:
                try:
                    b_results = await engine.search(
                        bq, max_results=20, enrich_query=False, filter_marketplaces=filter_marketplaces
                    )
                    for r in b_results:
                        if r.url and is_valid_domain(r.url, target_item_name=clean, filter_marketplaces=filter_marketplaces):
                            url_to_meta[r.url] = r
                            if r.url not in candidate_urls and r.url not in wave2_urls:
                                wave2_urls.append(r.url)
                except Exception as b_exc:
                    logger.warning("Broad search query error for %s: %s", bq, b_exc)
                if len(candidate_urls) + len(wave2_urls) >= 45:
                    break

        if wave2_urls:
            await _evaluate_candidates(wave2_urls)

    # Кластеризация цен и жесткая отсечка выбросов
    cluster_and_reconcile_item_quotes(item_res, cluster_ratio=cluster_ratio)

    item_res.status = "found" if item_res.has_prices else ("divergent" if any(q.price_rub > 0 for q in item_res.quotes) else "not_found")
    return item_res


async def run_price_monitoring_pipeline(
    file_bytes: bytes,
    settings: SystemSettings,
    output_excel_path: str,
    price_per_position_rub: float = 50.0,
    progress_callback: Optional[Callable[[int, str], Any]] = None,
    max_suppliers: int = 3,
    max_parallel_items: int = 4,
    checkpoint_path: Optional[str] = None,
    cluster_ratio: float = 2.2,
    filter_marketplaces: bool = True,
) -> BatchMonitoringResult:
    """Полный пайплайн мониторинга цен с защитой от сбоев (чекпоинты) и кластеризацией цен."""
    parsed_items = parse_input_excel(file_bytes)
    total = len(parsed_items)
    if total == 0:
        raise ValueError("В загруженном файле не найдено строк с номенклатурой.")

    # Проверка лимита строк из настроек
    max_positions_limit = int(getattr(settings, "price_monitoring_max_positions", 1000) or 1000)
    if total > max_positions_limit:
        raise ValueError(f"В файле {total} позиций. Лимит в настройках системы — {max_positions_limit} строк. Разбейте файл на части.")

    if progress_callback:
        progress_callback(5, f"Загружено {total} позиций из файла")

    engine = YandexSearchEngine(
        folder_id=settings.yandex_search_folder_id,
        api_key=settings.yandex_search_api_key,
    )
    search_sem = asyncio.Semaphore(3)

    results: List[ItemPriceResult] = []
    completed_rows: set[int] = set()

    # Восстановление из чекпоинта при наличии
    if checkpoint_path and os.path.exists(checkpoint_path):
        results = _load_checkpoint(checkpoint_path)
        completed_rows = {r.row_number for r in results}
        if completed_rows and progress_callback:
            progress_callback(
                int((len(completed_rows) / total) * 80) + 10,
                f"Возобновлено из контрольной точки: {len(completed_rows)}/{total} позиций уже готовы",
            )

    proxy_url = os.getenv("PRICE_MONITORING_PROXY") or os.getenv("HTTPS_PROXY")
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, proxy=proxy_url) as http_client:
        batch_size = max_parallel_items
        for i in range(0, total, batch_size):
            chunk = [(idx + 1, nom, unit) for idx, (nom, unit) in enumerate(parsed_items[i : i + batch_size], start=i)]
            chunk_to_process = [it for it in chunk if it[0] not in completed_rows]

            if chunk_to_process:
                tasks = [
                    process_single_item(
                        item,
                        engine,
                        settings,
                        http_client,
                        search_sem,
                        max_suppliers=max_suppliers,
                        min_target_suppliers=min(3, max_suppliers),
                        cluster_ratio=cluster_ratio,
                        filter_marketplaces=filter_marketplaces,
                    )
                    for item in chunk_to_process
                ]
                chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in chunk_results:
                    if isinstance(r, ItemPriceResult):
                        results.append(r)
                        completed_rows.add(r.row_number)
                    else:
                        logger.error("Item processing exception: %s", r)

                # Сохраняем промежуточный чекпоинт каждые batch_size строк
                if checkpoint_path:
                    _save_checkpoint(checkpoint_path, results, total)

            pct = 10 + int((len(completed_rows) / total) * 80)
            if progress_callback:
                progress_callback(pct, f"Обработано {len(completed_rows)} из {total} позиций...")

    await engine.close()

    # Сортируем результаты строго по порядку строк входного файла
    results.sort(key=lambda it: it.row_number)

    # Генерация результирующего Excel-файла
    generate_price_monitoring_excel(results, output_excel_path, max_suppliers=max_suppliers)

    # Очистка файла чекпоинта после успешного завершения
    if checkpoint_path and os.path.exists(checkpoint_path):
        try:
            os.remove(checkpoint_path)
        except Exception:
            pass

    found_count = sum(1 for it in results if it.has_prices)
    not_found_count = total - found_count
    total_charged_rub = round(found_count * price_per_position_rub, 2)

    if progress_callback:
        progress_callback(100, f"Готово! Найдено подтвержденных цен для {found_count} из {total} позиций")

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

