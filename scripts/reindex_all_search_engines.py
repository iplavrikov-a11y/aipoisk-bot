#!/usr/bin/env python3
"""Notify search engines about explicit changed TenderLex URLs."""
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.google_seo import DEFAULT_SITE_URL
from app.yandex_seo import changed_public_urls, submit_sitemap_recrawl

logger = logging.getLogger(__name__)
SITEMAP_URL = "https://tenderlex.ru/sitemap.xml"


def submit_google_search_console_sitemap() -> dict:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        key_path = ROOT_DIR / "data" / "google_service_account.json"
        if not key_path.exists():
            return {"ok": False, "error": "data/google_service_account.json not found"}

        creds = service_account.Credentials.from_service_account_file(
            str(key_path), scopes=["https://www.googleapis.com/auth/webmasters"]
        )
        svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        svc.sitemaps().submit(siteUrl=DEFAULT_SITE_URL, feedpath=SITEMAP_URL).execute()
        logger.info("Google Search Console sitemap submission successful")
        return {"ok": True, "sitemap": SITEMAP_URL, "site_url": DEFAULT_SITE_URL}
    except Exception as e:
        logger.warning("GSC sitemap submission failed: %s", e)
        return {"ok": False, "error": str(e)}



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-url", action="append", default=[], metavar="URL",
                        help="New, changed or removed canonical public URL. Repeat for each URL.")
    parser.add_argument("--submit-sitemap", action="store_true", help="Submit the sitemap to Google Search Console.")
    args = parser.parse_args()
    if not args.changed_url and not args.submit_sitemap:
        parser.error("provide --changed-url or --submit-sitemap")
    try:
        urls = changed_public_urls(args.changed_url)
    except (TypeError, ValueError) as error:
        parser.error(str(error))

    summary = {"timestamp": datetime.now(timezone.utc).isoformat(), "changed_urls_count": len(urls)}
    if urls:
        summary["submissions"] = submit_sitemap_recrawl(urls)
    if args.submit_sitemap:
        summary["google_search_console"] = submit_google_search_console_sitemap()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if all(summary.get(key, {}).get("ok", True) for key in ("submissions", "google_search_console")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
