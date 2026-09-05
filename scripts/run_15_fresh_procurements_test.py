import asyncio
import time
import json
import sqlite3
import re
from pathlib import Path

TEST_PROCUREMENTS = [
    {
        "id": 1,
        "title": "Поставка тали электрической канатной г/п 5т",
        "category": "Подъемно-транспортное оборудование",
        "search_term": "таль электрическая канатная",
        "okpd2": "28.22.11.110"
    },
    {
        "id": 2,
        "title": "Цепь тяговая пластинчатая катковая М80С1-3-160",
        "category": "Конвейерные комплектующие",
        "search_term": "цепь тяговая пластинчатая",
        "okpd2": "25.93.15.110"
    },
    {
        "id": 3,
        "title": "Комплекты уплотнений гребного вала дейдвудного устройства",
        "category": "Судостроение и судоремонт",
        "search_term": "дейдвудное уплотнение",
        "okpd2": "22.19.73.110"
    },
    {
        "id": 4,
        "title": "Вклейка фторопластовой прокладки во вкладыш пятового устройства",
        "category": "Гидротехнические сооружения / РТИ",
        "search_term": "фторопласт прокладка",
        "okpd2": "22.29.29.190"
    },
    {
        "id": 5,
        "title": "Стальной канат ГОСТ 3077-80 оцинкованный",
        "category": "Метизы и канатная продукция",
        "search_term": "канат стальной",
        "okpd2": "25.93.11.110"
    },
    {
        "id": 6,
        "title": "Лента конвейерная резинотканевая 2М-1000-4-ТК-200-2",
        "category": "РТИ и конвейеры",
        "search_term": "лента конвейерная резинотканевая",
        "okpd2": "22.19.40.110"
    },
    {
        "id": 7,
        "title": "Пластиковые щиты ЩМП-П IP65 навесные",
        "category": "Электротехнические корпуса",
        "search_term": "щит навесной IP65",
        "okpd2": "27.12.31.000"
    },
    {
        "id": 8,
        "title": "Техпластины ТМКЩ средней твердости ГОСТ 7338-90",
        "category": "РТИ промышленного назначения",
        "search_term": "техпластина ТМКЩ",
        "okpd2": "22.19.20.110"
    },
    {
        "id": 9,
        "title": "Сильфонные компенсаторы осевые фланцевые Ру16 Ду200",
        "category": "Трубопроводная арматура",
        "search_term": "компенсатор сильфонный",
        "okpd2": "25.99.29.190"
    },
    {
        "id": 10,
        "title": "Материалы верхнего строения пути рельсы Р65 накладки 1Р65",
        "category": "Железнодорожное оборудование",
        "search_term": "рельсы Р65",
        "okpd2": "24.10.71.110"
    },
    {
        "id": 11,
        "title": "Кассеты для тангенциальной ультрафильтрации",
        "category": "Фильтрационное оборудование",
        "search_term": "ультрафильтрация",
        "okpd2": "28.29.12.110"
    },
    {
        "id": 12,
        "title": "Фильтры воздушные карманные ФВК G4/F7",
        "category": "Системы вентиляции и очистки воздуха",
        "search_term": "фильтр воздушный карманный",
        "okpd2": "28.25.14.110"
    },
    {
        "id": 13,
        "title": "Фильтры масляные тонкой очистки для газовой турбины",
        "category": "Турбинное оборудование",
        "search_term": "фильтр масляный",
        "okpd2": "28.29.12.110"
    },
    {
        "id": 14,
        "title": "Устройства порошкового пожаротушения самосрабатывающие ОСП-1",
        "category": "Пожарная безопасность",
        "search_term": "порошковое пожаротушение",
        "okpd2": "28.29.22.110"
    },
    {
        "id": 15,
        "title": "Трансформатор силовой трехфазный масляный ТМГ 1000 кВА",
        "category": "Высоковольтное электрооборудование",
        "search_term": "трансформатор силовой ТМГ",
        "okpd2": "27.11.41.000"
    }
]

TL_SQLITE = Path("/root/projects/aipoisk-bot/data/minprom_registry.sqlite")
EA_SQLITE = Path("/root/projects/emailagent/storage/minprom_registry/current.sqlite")

def search_fts(db_path: Path, term: str):
    if not db_path.exists():
        return [], 0.0
    
    words = [w for w in re.split(r'\W+', term) if len(w) >= 3]
    if not words:
        words = [term]
    
    fts_query = " ".join(f'"{w}"*' for w in words[:3])
    
    t0 = time.perf_counter()
    results = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT e.registry_number, e.manufacturer, e.product, e.inn, e.source_url
            FROM entries_fts f
            JOIN entries e ON f.rowid = e.id
            WHERE entries_fts MATCH ? 
            LIMIT 20
        """, (fts_query,))
        
        for row in cursor.fetchall():
            results.append({
                "registry_number": row[0],
                "manufacturer": row[1],
                "product": row[2],
                "inn": row[3],
                "source_url": row[4]
            })
        conn.close()
    except Exception as e:
        print(f"Error querying {db_path}: {e}")
    
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return results, elapsed_ms

# Run benchmark
results = []
total_tl_ms = 0
total_ea_ms = 0
total_tl_count = 0
total_ea_count = 0

print("="*95)
print(f"{'№':<3} | {'Закупка':<45} | {'TL (найдено / время)':<20} | {'EA (найдено / время)':<20}")
print("="*95)

for item in TEST_PROCUREMENTS:
    tl_res, tl_ms = search_fts(TL_SQLITE, item["search_term"])
    ea_res, ea_ms = search_fts(EA_SQLITE, item["search_term"])
    
    total_tl_ms += tl_ms
    total_ea_ms += ea_ms
    total_tl_count += len(tl_res)
    total_ea_count += len(ea_res)
    
    results.append({
        "id": item["id"],
        "title": item["title"],
        "category": item["category"],
        "term": item["search_term"],
        "tl_count": len(tl_res),
        "tl_ms": round(tl_ms, 2),
        "ea_count": len(ea_res),
        "ea_ms": round(ea_ms, 2),
        "sample_mfg": [r["manufacturer"] for r in tl_res[:2]] if tl_res else []
    })
    
    mfg_str = f"({tl_res[0]['manufacturer'][:20]}...)" if tl_res else "(нет)"
    print(f"[{item['id']:02d}] | {item['title'][:45]:<45} | {len(tl_res):2d} шт ({tl_ms:6.2f} мс)  | {len(ea_res):2d} шт ({ea_ms:6.2f} мс)  | {mfg_str}")

print("="*95)
print(f"ИТОГИ:")
print(f"TenderLex  : Всего найдено: {total_tl_count} записей, Среднее время: {total_tl_ms/len(TEST_PROCUREMENTS):.2f} мс")
print(f"EmailAgent : Всего найдено: {total_ea_count} записей, Среднее время: {total_ea_ms/len(TEST_PROCUREMENTS):.2f} мс")
print("="*95)

out_file = Path("/root/projects/aipoisk-bot/scripts/test_15_fresh_results.json")
out_file.write_text(json.dumps({
    "summary": {
        "total_cases": len(TEST_PROCUREMENTS),
        "total_tl_found": total_tl_count,
        "total_ea_found": total_ea_count,
        "avg_tl_ms": round(total_tl_ms / len(TEST_PROCUREMENTS), 2),
        "avg_ea_ms": round(total_ea_ms / len(TEST_PROCUREMENTS), 2)
    },
    "cases": results
}, indent=2, ensure_ascii=False))
