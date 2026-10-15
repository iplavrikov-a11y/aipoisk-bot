import asyncio
import os
import re
import sys
from typing import Any, List, Dict
import httpx

from app.db import SessionLocal
from app.models import SystemSettings
from app.exact_product.yandex_search import YandexSearchEngine
from app.price_monitoring.cleaner import clean_nomenclature_name, build_commercial_search_queries
from app.price_monitoring.extractor import fetch_page_content_and_meta, extract_supplier_quote, is_valid_domain
from app.price_monitoring.pipeline import validate_and_reconcile_item_quotes
from app.price_monitoring.models import ItemPriceResult, SupplierQuote

test_items = [
    ("Лента диаграммная 0-100 120мм Р1763", "М2"),
    ("Пружина пластик.19мм 100шт/НЕ ИСП", "УП"),
    ("Било Л-04.524", "ШТ"),
    ("Билодержатель К4-15-01", "ШТ"),
    ("Палец К4-79", "ШТ"),
    ("Набивка ВАТИ-202 22х22мм", "КГ"),
    ("Ветошь х/б", "КГ"),
    ("Кислород газ.ГОСТ 5583(м3)", "М3"),
    ("Пропан сжиженный бал.50л ТУ 51-882", "КГ"),
    ("Электрод ОЗС-12 4мм", "КГ"),
    ("Броня радиальная верхняя К4-52", "ШТ"),
    ("Лист 10 ВСт3сп ГОСТ 19903/НЕ ИСП", "Т"),
    ("Полоса 4х20 Ст0 ГОСТ 103/НЕ ИСП", "Т"),
    ("Круг шлиф.ПП 80х20х20", "ШТ"),
    ("Подшипник 13630 ГОСТ 8545", "ШТ"),
    ("Смазка 1-13 ТУ 38.401-58-142 (кг)", "КГ"),
]

async def search_and_extract(item_name: str, unit: str, engine, settings, client):
    clean = clean_nomenclature_name(item_name)
    queries = build_commercial_search_queries(clean, unit)
    candidate_urls = []

    for q in queries[:2]:
        try:
            results = await engine.search(q, max_results=6, enrich_query=False)
            for r in results:
                if r.url and is_valid_domain(r.url) and r.url not in candidate_urls:
                    candidate_urls.append(r.url)
        except Exception as e:
            print(f"Search error for {clean}: {e}")

    item_res = ItemPriceResult(row_number=1, raw_name=item_name, clean_name=clean, unit=unit)

    for url in candidate_urls[:6]:
        try:
            page_text, inn, kpp, contacts = await fetch_page_content_and_meta(client, url)
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
                item_res.quotes.append(quote)
                print(f"    --> FOUND: {quote.company_name} | {quote.price_rub} руб/{quote.unit} (ИНН: {quote.inn}) | {quote.conversion_comment}")
        except Exception:
            pass

    validate_and_reconcile_item_quotes(item_res)
    return item_res.quotes

async def main():
    db = SessionLocal()
    settings = db.query(SystemSettings).first()
    engine = YandexSearchEngine(folder_id=settings.yandex_search_folder_id, api_key=settings.yandex_search_api_key)

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        # Test Propane & Oxygen specifically
        for item_name, unit in [("Пропан сжиженный бал.50л ТУ 51-882", "КГ"), ("Кислород газ.ГОСТ 5583(м3)", "М3")]:
            print(f"\n[TESTING] {item_name} ({unit})")
            quotes = await search_and_extract(item_name, unit, engine, settings, client)
            print(f"TOTAL QUOTES FOR '{item_name}': {len(quotes)}")
            for q in quotes:
                print(f"  * {q.company_name}: {q.price_rub} руб/{q.unit} (ИНН: {q.inn}, Тел: {q.contacts}) -> {q.url} [{q.conversion_comment}]")

    await engine.close()
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
