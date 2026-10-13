#!/usr/bin/env python3
"""
TenderLex: Live Real-Web E2E Pipeline Runner & Architectural Diagnostic.
Runs the live price monitoring pipeline with real Yandex searches,
real HTTP website fetching, real LLM extraction, real DaData resolution,
and real Excel generation.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import openpyxl
from dotenv import load_dotenv

# Ensure backend and repo root in PYTHONPATH
sys.path.insert(0, "/root/projects/tenderlex")
sys.path.insert(0, "/root/projects/tenderlex/backend")
load_dotenv("/root/projects/tenderlex/.env")
load_dotenv()

from app.db import SessionLocal
from app.models import SystemSettings
from app.price_monitoring.pipeline import run_price_monitoring_pipeline
from scripts.benchmark_200_price_monitoring import BENCHMARK_220_ITEMS

# Set up logging to stdout and file
LOG_FILE = "/tmp/live_price_monitoring_e2e.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger("live_runner")


def build_input_excel(items: List[tuple[str, str]], target_path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Спецификация"
    ws.append(["№ п/п", "Наименование товара / номенклатура", "Ед. изм."])
    for idx, (name, unit) in enumerate(items, start=1):
        ws.append([idx, name, unit])
    wb.save(target_path)
    logger.info("Created input specification Excel with %d positions at %s", len(items), target_path)


async def main():
    start_ts = time.time()
    db = SessionLocal()
    settings = db.query(SystemSettings).first()
    if not settings:
        logger.error("SystemSettings not found in database!")
        return

    logger.info("=" * 70)
    logger.info("🚀 LAUNCHING LIVE WEB E2E PRICE MONITORING PIPELINE")
    logger.info("Yandex Folder ID configured: %s", bool(settings.yandex_search_folder_id))
    logger.info("Yandex API Key configured: %s", bool(settings.yandex_search_api_key))
    logger.info("DaData API Key configured: %s", bool(os.getenv("DADATA_API_KEY")))
    logger.info("=" * 70)

    # We take all items from the diverse benchmark dataset
    # You can configure item_count here. Let's take all items or pass via CLI
    count = int(sys.argv[1]) if len(sys.argv) > 1 else len(BENCHMARK_220_ITEMS)
    selected_items = [(nom, unit) for (cat, nom, unit) in BENCHMARK_220_ITEMS[:count]]

    input_excel_path = "/tmp/live_input_specification.xlsx"
    output_excel_path = "/tmp/live_price_monitoring_output.xlsx"
    build_input_excel(selected_items, input_excel_path)

    with open(input_excel_path, "rb") as f:
        file_bytes = f.read()

    logger.info("Running pipeline on %d items with controlled parallel workers...", len(selected_items))

    def on_progress(percent: int, msg: str):
        logger.info("[PROGRESS %3d%%] %s", percent, msg)

    # Run the real pipeline
    result = await run_price_monitoring_pipeline(
        file_bytes=file_bytes,
        settings=settings,
        output_excel_path=output_excel_path,
        price_per_position_rub=50.0,
        progress_callback=on_progress,
        max_suppliers=5,
        max_parallel_items=4,  # 4 parallel items to stay healthy with Yandex QPS
    )

    elapsed_s = time.time() - start_ts
    db.close()

    logger.info("=" * 70)
    logger.info("🏁 LIVE PIPELINE COMPLETED IN %.1f SECONDS (%.2f min)", elapsed_s, elapsed_s / 60.0)
    logger.info("Total positions: %d", result.total_positions)
    logger.info("Found positions: %d (%.1f%%)", result.found_positions, (result.found_positions / result.total_positions) * 100)
    logger.info("Not found positions: %d", result.not_found_positions)
    logger.info("Saved report: %s (%.1f KB)", output_excel_path, os.path.getsize(output_excel_path) / 1024)
    logger.info("=" * 70)

    # -------------------------------------------------------------
    # ARCHITECTURAL DIAGNOSTIC & QUALITY AUDIT
    # -------------------------------------------------------------
    logger.info("\n📊 DETAILED QUALITY AUDIT & ERROR DETECTION:")
    total_quotes = 0
    quotes_with_inn = 0
    quotes_with_contacts = 0
    quotes_with_reconcile = 0
    outliers_detected = 0
    empty_items = []

    for it in result.items:
        quotes = it.quotes
        valid_q = [q for q in quotes if q.price_rub > 0]
        total_quotes += len(valid_q)

        if not valid_q:
            empty_items.append((it.row_number, it.raw_name, it.clean_name))
            continue

        for q in valid_q:
            if q.inn:
                quotes_with_inn += 1
            if q.contacts:
                quotes_with_contacts += 1
            if q.conversion_comment:
                quotes_with_reconcile += 1
            if q.is_outlier:
                outliers_detected += 1

    logger.info("• Total valid quotes extracted: %d", total_quotes)
    if total_quotes > 0:
        logger.info("• INN extraction rate: %d/%d (%.1f%%)", quotes_with_inn, total_quotes, (quotes_with_inn / total_quotes) * 100)
        logger.info("• Contacts extraction rate: %d/%d (%.1f%%)", quotes_with_contacts, total_quotes, (quotes_with_contacts / total_quotes) * 100)
        logger.info("• Conversion/reconcile comments: %d (%.1f%%)", quotes_with_reconcile, total_quotes, (quotes_with_reconcile / total_quotes) * 100)
        logger.info("• Outliers flagged: %d", outliers_detected)

    if empty_items:
        logger.info("• Positions without quotes (%d):", len(empty_items))
        for r_num, raw, cln in empty_items[:15]:
            logger.info("   [Row %d] '%s' (cleaned: '%s')", r_num, raw, cln)

    # Save summary JSON for analysis
    summary = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": elapsed_s,
        "total_positions": result.total_positions,
        "found_positions": result.found_positions,
        "not_found_positions": result.not_found_positions,
        "total_quotes": total_quotes,
        "quotes_with_inn": quotes_with_inn,
        "quotes_with_contacts": quotes_with_contacts,
        "outliers_detected": outliers_detected,
        "empty_items_sample": empty_items[:10],
    }
    with open("/tmp/live_price_monitoring_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info("Summary saved to /tmp/live_price_monitoring_summary.json")


if __name__ == "__main__":
    asyncio.run(main())
