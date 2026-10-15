#!/usr/bin/env python3
"""
TenderLex: 150-Item Multi-Industry Domain Discovery & WAF Diagnostic.
Runs searches for 150 diverse procurement positions across 10 industries,
analyzes which supplier domains and marketplaces appear most frequently,
tests their live HTTP response, and identifies which sites need cookies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections import Counter
from typing import Dict, List, Tuple
from urllib.parse import urlparse

# Add paths
sys.path.insert(0, "/root/projects/tenderlex")
sys.path.insert(0, "/root/projects/tenderlex/backend")

from dotenv import load_dotenv
load_dotenv("/root/projects/tenderlex/.env")

from app.db import SessionLocal
from app.models import SystemSettings
from app.exact_product.yandex_search import YandexSearchEngine, NON_COMMERCIAL_DOMAINS
from app.price_monitoring.cleaner import clean_nomenclature_name, build_commercial_search_queries
from app.price_monitoring.cookie_manager import cookie_manager
from scripts.benchmark_200_price_monitoring import BENCHMARK_220_ITEMS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("domain_diagnostics")


def select_150_diverse_items() -> List[Tuple[str, str, str]]:
    """Selects exactly 150 diverse positions balanced across all categories."""
    by_category: Dict[str, List[Tuple[str, str, str]]] = {}
    for cat, name, unit in BENCHMARK_220_ITEMS:
        by_category.setdefault(cat, []).append((cat, name, unit))

    selected = []
    # Take up to 15 items per category across 10-12 categories
    for cat, items in by_category.items():
        take = min(15, len(items))
        selected.extend(items[:take])
        if len(selected) >= 150:
            break

    if len(selected) < 150:
        for cat, items in by_category.items():
            for it in items[15:]:
                selected.append(it)
                if len(selected) >= 150:
                    break
            if len(selected) >= 150:
                break

    return selected[:150]


async def main():
    items = select_150_diverse_items()
    logger.info("Selected %d diverse positions across %d industries for domain discovery.", len(items), len(set(x[0] for x in items)))

    db = SessionLocal()
    settings = db.query(SystemSettings).first()
    if not settings:
        logger.error("No system settings found in DB.")
        db.close()
        return

    engine = YandexSearchEngine(
        folder_id=settings.yandex_search_folder_id,
        api_key=settings.yandex_search_api_key,
    )

    domain_counter = Counter()
    domain_to_categories = {}
    domain_to_sample_urls = {}
    processed_items = 0

    sem = asyncio.Semaphore(6)

    async def _search_item(idx: int, cat: str, raw_name: str, unit: str):
        nonlocal processed_items
        clean = clean_nomenclature_name(raw_name)
        queries = build_commercial_search_queries(clean, unit)[:2] # Top 2 commercial queries per item

        async with sem:
            for q in queries:
                try:
                    res = await engine.search(q, max_results=20, enrich_query=False, filter_marketplaces=False)
                    for r in res:
                        if not r.url:
                            continue
                        try:
                            netloc = urlparse(r.url).netloc.lower()
                            if netloc.startswith("www."):
                                netloc = netloc[4:]
                            # Ignore non-commercial search engines/gov
                            if any(netloc == bd or netloc.endswith("." + bd) for bd in NON_COMMERCIAL_DOMAINS):
                                continue
                            if any(netloc.endswith(ext) for ext in (".gov.ru", ".mil.ru", ".edu.ru")):
                                continue
                            domain_counter[netloc] += 1
                            domain_to_categories.setdefault(netloc, set()).add(cat)
                            if netloc not in domain_to_sample_urls:
                                domain_to_sample_urls[netloc] = r.url
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug("Query '%s' failed: %s", q, e)

        processed_items += 1
        if processed_items % 25 == 0 or processed_items == len(items):
            logger.info("Searched %d / %d positions. Unique commercial domains found so far: %d", processed_items, len(items), len(domain_counter))

    tasks = [_search_item(idx, cat, name, unit) for idx, (cat, name, unit) in enumerate(items, start=1)]
    await asyncio.gather(*tasks)
    await engine.close()
    db.close()

    logger.info("Search phase complete. Total unique domains: %d", len(domain_counter))
    top_domains = domain_counter.most_common(50)

    # Now test live connectivity for Top 30 domains
    logger.info("Testing live HTTP connectivity from server for Top 30 domains...")
    test_results = []
    for domain, freq in top_domains[:30]:
        has_cookie = bool(cookie_manager.get_cookie(domain))
        test_res = await cookie_manager.test_domain(domain)
        test_results.append({
            "domain": domain,
            "frequency": freq,
            "categories": list(domain_to_categories.get(domain, [])),
            "sample_url": domain_to_sample_urls.get(domain, ""),
            "has_cookie": has_cookie,
            "cookie_length": test_res.get("cookie_length", 0),
            "status_code": test_res.get("status_code", 0),
            "status_text": test_res.get("status_text", ""),
            "accessible": test_res.get("accessible", False),
            "duration_ms": test_res.get("duration_ms", 0),
            "title": test_res.get("title", ""),
        })

    # Save summary artifact
    out_json = "/root/projects/tenderlex/storage/domain_diagnostics_150_items.json"
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "total_positions_tested": len(items),
            "unique_domains_found": len(domain_counter),
            "top_domains": test_results,
        }, f, ensure_ascii=False, indent=2)

    print("\n" + "="*90)
    print("TOP DOMAINS DISCOVERED ACROSS 150 POSITIONS (BY FREQUENCY):")
    print("="*90)
    print(f"{'#':<3} {'Домен':<24} {'Встречаемость':<14} {'Куки':<12} {'HTTP':<8} {'Статус':<25}")
    print("-" * 90)
    for idx, d in enumerate(test_results, start=1):
        cookie_str = f"Есть ({d['cookie_length']}зн)" if d['has_cookie'] else "Нет"
        http_str = f"{d['status_code']}"
        acc_str = "OK (доступен)" if d['accessible'] else "WAF / Блокировка"
        print(f"{idx:<3} {d['domain']:<24} {d['frequency']:<14} {cookie_str:<12} {http_str:<8} {acc_str:<25}")
    print("="*90)


if __name__ == "__main__":
    asyncio.run(main())
