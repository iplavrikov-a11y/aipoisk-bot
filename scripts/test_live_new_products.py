import asyncio
import logging
import os
import sys

# Добавляем backend в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db import SessionLocal
from app.models import SystemSettings
from app.exact_product.yandex_search import YandexSearchEngine
from app.price_monitoring.pipeline import process_single_item
from app.price_monitoring.excel_report import generate_price_monitoring_excel
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_live_new_products")

TEST_ITEMS = [
    (1, "Манометр МП3-У 0-1.0 МПа", "ШТ"),
    (2, "Кран шаровой латунный 1/2 внутренняя-наружная резьба (бабочка)", "ШТ"),
    (3, "Автоматический выключатель ВА47-29 1П 16А С", "ШТ"),
    (4, "Перчатки х/б с ПВХ напылением 4 нити", "ПАР"),
]

async def main():
    db = SessionLocal()
    settings = db.query(SystemSettings).first()
    if not settings:
        print("ERROR: SystemSettings not found in DB")
        return

    logger.info("Yandex Folder: %s, Key: %s...", settings.yandex_search_folder_id, settings.yandex_search_api_key[:8] if settings.yandex_search_api_key else "NONE")

    engine = YandexSearchEngine(
        folder_id=settings.yandex_search_folder_id,
        api_key=settings.yandex_search_api_key,
    )
    search_sem = asyncio.Semaphore(2)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    timeout = httpx.Timeout(20.0, connect=10.0)

    results = []

    async with httpx.AsyncClient(headers=headers, limits=limits, timeout=timeout, follow_redirects=True, verify=False) as http_client:
        for it in TEST_ITEMS:
            logger.info("=== Processing Item %d: %s [%s] ===", it[0], it[1], it[2])
            res = await process_single_item(
                item_tuple=it,
                engine=engine,
                settings=settings,
                http_client=http_client,
                search_semaphore=search_sem,
                max_suppliers=3,
                min_target_suppliers=3,
                cluster_ratio=2.2,
                filter_marketplaces=True,
            )
            results.append(res)
            logger.info("Finished Item %d: status=%s, total quotes=%d, valid consensus quotes=%d",
                        it[0], res.status, len(res.quotes), len([q for q in res.quotes if q.price_rub > 0 and not q.is_outlier]))
            for q in res.quotes:
                logger.info("  Quote: %s | %s ₽ (raw: %s %s) | INN: %s | Outlier: %s | Comment: %s | URL: %s",
                            q.company_name, q.price_rub, q.raw_price_rub, q.site_unit, q.inn, q.is_outlier, q.comment, q.url)

    out_path = "/root/projects/tenderlex/storage/test_new_products_report.xlsx"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    generate_price_monitoring_excel(results, out_path, max_suppliers=3)
    logger.info("Generated Excel report at %s", out_path)

    print("\n" + "="*80)
    print("SUMMARY VERIFICATION OF NEW PRODUCTS:")
    print("="*80)
    for res in results:
        disp_quotes = [q for q in res.quotes if q.price_rub > 0 and not q.is_outlier]
        outliers = [q for q in res.quotes if q.is_outlier]
        prices = [q.price_rub for q in disp_quotes]
        ratio = (max(prices) / min(prices)) if (prices and min(prices) > 0) else 0.0

        print(f"\nItem #{res.row_number}: {res.clean_name} [{res.unit}]")
        print(f"  Status: {res.status}")
        print(f"  Total Quotes Found: {len(res.quotes)} (Consensus: {len(disp_quotes)}, Outliers: {len(outliers)})")
        print(f"  Displayed Consensus Prices: {prices}")
        print(f"  Price Ratio (Max/Min): {ratio:.2f}x (Threshold <= 2.2x)")
        if len(disp_quotes) >= 3:
            print("  [PASS] Target >= 3 suppliers achieved!")
        else:
            print(f"  [WARN] Achieved {len(disp_quotes)} suppliers (target: 3)")
        if ratio <= 2.2 and ratio > 0:
            print("  [PASS] Price consensus tight and within threshold!")
        elif ratio == 0:
            print("  [NOTE] Divergence or no consensus prices displayed.")
        else:
            print(f"  [FAIL] Price ratio {ratio:.2f}x exceeds threshold!")

        if outliers:
            print(f"  Pruned Outliers: {[q.price_rub for q in outliers]}")

    db.close()

if __name__ == "__main__":
    asyncio.run(main())
