import asyncio
import os
import re
import sys
from typing import Any, List, Dict
import httpx
from bs4 import BeautifulSoup

from app.db import SessionLocal
from app.models import SystemSettings
from app.ai import call_llm, parse_json_object
from app.exact_product.yandex_search import YandexSearchEngine

def clean_spec_name(name: str) -> str:
    cleaned = re.sub(r'/(НЕ\s*ИСП|не\s*исп)', '', name, flags=re.IGNORECASE)
    cleaned = re.sub(r'\((кг|м3|шт|т)\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

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
    clean = clean_spec_name(item_name)
    query = f"{clean} купить цена руб"
    print(f"\n[SEARCH] {clean} (unit: {unit}) -> query: {query}")
    try:
        # Search Yandex
        results = await engine.search(query, max_results=6, enrich_query=False)
    except Exception as e:
        print(f"Search error for {clean}: {e}")
        return []

    quotes = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    for r in results:
        if len(quotes) >= 5:
            break
        url = r.url
        print(f"  Fetching: {url}")
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200 or not resp.text:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')
            for s in soup(['script', 'style', 'nav', 'header', 'footer']):
                s.decompose()
            text = ' '.join(soup.stripped_strings)[:3500]
            if not text or len(text) < 50:
                continue
            
            prompt = f'''Найди точную цену товара, название компании, ИНН и контакты на странице поставщика:
Товар из заявки: {clean} (ед. изм.: {unit})
URL страницы: {url}
Текст со страницы товара:
{text}

Правила:
1. Если на странице указана точная числовая цена (в рублях) за товар или единицу — укажи price_rub (число) и is_price_found: true.
2. Если цена "по запросу", "уточняйте", 0 или не найдена — укажи price_rub: null, is_price_found: false.
3. company_name: краткое название компании/магазина (например, "ВсеИнструменты", "ООО Металлсервис", "ЭТМ").
4. inn: ИНН компании, если есть на странице, иначе null.
5. contacts: телефон или email компании.

Ответь строго JSON:
{{
  "company_name": "...",
  "inn": "...",
  "contacts": "...",
  "price_rub": 1234.5,
  "unit": "{unit}",
  "is_price_found": true
}}
'''
            ai_raw = await call_llm(settings, prompt, tier='light')
            parsed = parse_json_object(ai_raw)
            if parsed and parsed.get("is_price_found") and parsed.get("price_rub"):
                try:
                    price = float(parsed["price_rub"])
                    if price > 0:
                        quotes.append({
                            "company_name": parsed.get("company_name") or r.domain,
                            "inn": parsed.get("inn"),
                            "contacts": parsed.get("contacts"),
                            "price_rub": price,
                            "unit": parsed.get("unit") or unit,
                            "url": url,
                        })
                        print(f"    --> FOUND: {parsed.get('company_name')} | {price} руб | {url}")
                except (ValueError, TypeError):
                    pass
        except Exception as exc:
            pass

    return quotes

async def main():
    db = SessionLocal()
    settings = db.query(SystemSettings).first()
    engine = YandexSearchEngine(folder_id=settings.yandex_search_folder_id, api_key=settings.yandex_search_api_key)
    
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        # Test first 4 items for quick proof
        for item_name, unit in test_items[:5]:
            quotes = await search_and_extract(item_name, unit, engine, settings, client)
            print(f"TOTAL QUOTES FOR '{item_name}': {len(quotes)}")
            for q in quotes:
                print(f"  * {q['company_name']}: {q['price_rub']} руб/{q['unit']} (ИНН: {q['inn']}, Тел: {q['contacts']}) -> {q['url']}")

    await engine.close()
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
