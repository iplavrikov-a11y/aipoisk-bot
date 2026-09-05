import asyncio
import json
import time
import sys
import sqlite3
import re
from pathlib import Path

# Add backend paths
sys.path.insert(0, '/root/projects/aipoisk-bot/backend')

from app.ai import call_llm
from app.repository import get_or_create_settings
from app.db import SessionLocal

db = SessionLocal()
settings = get_or_create_settings(db)
db.close()

# 15 procurements for AI morphological and query variant generation
TEST_ITEMS = [
    {"id": 1, "title": "Поставка тали электрической канатной г/п 5т", "raw": "таль электрическая канатная 5т"},
    {"id": 2, "title": "Цепь тяговая пластинчатая катковая М80С1-3-160", "raw": "цепь тяговая пластинчатая катковая"},
    {"id": 3, "title": "Комплекты уплотнений гребного вала дейдвудного устройства", "raw": "уплотнение гребного вала дейдвудного устройства"},
    {"id": 4, "title": "Вклейка фторопластовой прокладки во вкладыш пятового устройства", "raw": "прокладка фторопластовая пятовое устройство"},
    {"id": 5, "title": "Стальной канат ГОСТ 3077-80 оцинкованный", "raw": "канат стальной ГОСТ 3077"},
    {"id": 6, "title": "Лента конвейерная резинотканевая 2М-1000-4-ТК-200-2", "raw": "лента конвейерная резинотканевая ТК-200"},
    {"id": 7, "title": "Пластиковые щиты ЩМП-П IP65 навесные", "raw": "щит пластиковый ЩМП-П навесной IP65"},
    {"id": 8, "title": "Техпластины ТМКЩ средней твердости ГОСТ 7338-90", "raw": "техпластина ТМКЩ ГОСТ 7338-90"},
    {"id": 9, "title": "Сильфонные компенсаторы осевые фланцевые Ру16 Ду200", "raw": "сильфонный компенсатор осевой фланцевый"},
    {"id": 10, "title": "Материалы верхнего строения пути рельсы Р65 накладки 1Р65", "raw": "рельсы Р65 накладки 1Р65 ВСП"},
    {"id": 11, "title": "Кассеты для тангенциальной ультрафильтрации", "raw": "кассеты тангенциальной фильтрации ультрафильтрационные"},
    {"id": 12, "title": "Фильтры воздушные карманные ФВК G4/F7", "raw": "фильтры воздушные карманные ФВК вентиляция"},
    {"id": 13, "title": "Фильтры масляные тонкой очистки для газовой турбины", "raw": "фильтр масляный тонкой очистки газовая турбина"},
    {"id": 14, "title": "Устройства порошкового пожаротушения самосрабатывающие ОСП-1", "raw": "устройства пожаротушения самосрабатывающие порошковые ОСП"},
    {"id": 15, "title": "Трансформатор силовой трехфазный масляный ТМГ 1000 кВА", "raw": "трансформатор силовой трехфазный масляный ТМГ"}
]

SQLITE_PATH = Path("/root/projects/aipoisk-bot/data/minprom_registry.sqlite")

def search_registry(term: str):
    words = [w for w in re.split(r'\W+', term) if len(w) >= 3]
    if not words:
        return []
    fts_query = " ".join(f'"{w}"*' for w in words[:3])
    try:
        conn = sqlite3.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.manufacturer, e.product, e.inn
            FROM entries_fts f
            JOIN entries e ON f.rowid = e.id
            WHERE entries_fts MATCH ? 
            LIMIT 10
        """, (fts_query,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        return []

async def test_item(item):
    prompt = f"""Сформируй для поиска в реестре Минпромторга и в поиске B2B-поставщиков список синонимов, различных словоформ (включая единственное/множественное число, синонимы категорий и профессиональные термины).

Товар: "{item['title']}"

Верни строго JSON:
{{
  "search_queries": ["запрос 1", "запрос 2", "запрос 3", "запрос 4"]
}}"""
    try:
        t0 = time.perf_counter()
        raw = await call_llm(
            settings,
            prompt,
            system_prompt="Ты закупочный аналитик.",
            tier="light",
            json_mode=True,
            timeout_seconds=20
        )
        ai_time = (time.perf_counter() - t0) * 1000
        parsed = json.loads(raw)
        queries = parsed.get("search_queries", [])
        
        # Test each query against registry
        total_found = 0
        found_manufacturers = set()
        for q in queries:
            rows = search_registry(q)
            total_found += len(rows)
            for r in rows:
                found_manufacturers.add(r[0])
                
        return {
            "id": item["id"],
            "title": item["title"],
            "ai_time_ms": round(ai_time, 1),
            "ai_queries": queries,
            "total_found": total_found,
            "unique_manufacturers": list(found_manufacturers)[:3]
        }
    except Exception as e:
        return {
            "id": item["id"],
            "title": item["title"],
            "error": str(e)
        }

async def main():
    print("="*95)
    print("ТЕСТ ИИ-ГЕНЕРАЦИИ СЛОВОФОРМ И СЕМАНТИЧЕСКОГО ПОИСКА ДЛЯ 15 ЗАКУПОК")
    print("="*95)
    
    # Run in parallel batches of 5
    for batch_start in range(0, len(TEST_ITEMS), 5):
        batch = TEST_ITEMS[batch_start:batch_start+5]
        results = await asyncio.gather(*(test_item(item) for item in batch))
        for res in results:
            if "error" in res:
                print(f"[{res['id']:02d}] {res['title'][:40]:<40} | ОШИБКА: {res['error']}")
            else:
                mfg_str = ", ".join(res["unique_manufacturers"]) if res["unique_manufacturers"] else "Поиск через Web Search"
                print(f"[{res['id']:02d}] {res['title'][:40]:<40} | ИИ: {res['ai_time_ms']}мс | Запросов: {len(res['ai_queries'])} | Найдено: {res['total_found']} | {mfg_str[:40]}")
                print(f"     Запросы ИИ: {', '.join(res['ai_queries'][:3])}")

asyncio.run(main())
