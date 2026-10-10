#!/usr/bin/env python3
"""
TenderLex Autonomous Multi-Engine Indexing Pipeline.
Submits new and updated URLs to:
1. Yandex.Webmaster Recrawl Queue API (/recrawl/queue)
2. IndexNow API (Yandex, Bing, Seznam, Naver)
3. Google Search Console API (Sitemaps Submission)
4. Sitemaps HTTP Ping (Google & Yandex)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.yandex_seo import _load_env_tokens, _http_json
from app.google_seo import get_gsc_service, DEFAULT_SITE_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reindex_pipeline")

INDEXNOW_KEY = "8fa93cd04f90454a82f7ff7d4434a4c6"
KEY_LOCATION = "https://tenderlex.ru/8fa93cd04f90454a82f7ff7d4434a4c6.txt"
HOST = "tenderlex.ru"
SITEMAP_URL = "https://tenderlex.ru/sitemap.xml"

# High priority URLs to push directly into crawler queues
PRIORITY_URLS = [
    "https://tenderlex.ru/api-integracii",
    "https://tenderlex.ru/baza-znaniy/avtomatizaciya-zakupok-cherez-api-1c",
    "https://tenderlex.ru/",
    "https://tenderlex.ru/poisk-postavshchikov-po-tz",
    "https://tenderlex.ru/podbor-tovara-i-analogov-po-tz",
    "https://tenderlex.ru/analiz-zakupochnoi-dokumentacii",
    "https://tenderlex.ru/baza-znaniy",
    "https://tenderlex.ru/sitemap.xml",
]


def fetch_sitemap_urls() -> list[str]:
    try:
        req = urllib.request.Request(SITEMAP_URL, headers={"User-Agent": "TenderLex-Indexer/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read().decode("utf-8"))
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [elem.text.strip() for elem in root.findall(".//ns:loc", ns) if elem.text]
        logger.info("Parsed %d URLs from live sitemap.xml", len(urls))
        return urls
    except Exception as e:
        logger.warning("Failed to fetch live sitemap (%s), using priority fallback", e)
        return list(PRIORITY_URLS)


def submit_yandex_webmaster_recrawl(urls: list[str]) -> dict:
    tokens = _load_env_tokens()
    token = tokens.get("webmaster", "")
    if not token:
        return {"ok": False, "error": "YANDEX_WEBMASTER_TOKEN missing"}

    wm_headers = {
        "Authorization": f"OAuth {token}",
        "Content-Type": "application/json",
    }

    user_res = _http_json("https://api.webmaster.yandex.net/v4/user", headers=wm_headers)
    user_id = user_res.get("user_id")
    if not user_id:
        return {"ok": False, "error": "Failed to resolve Yandex Webmaster user_id", "details": user_res}

    host_id = tokens.get("host_id", "https:tenderlex.ru:443")
    quota_res = _http_json(f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/recrawl/quota", headers=wm_headers)
    daily_quota = quota_res.get("daily_quota", 0)
    quota_remainder = quota_res.get("quota_remainder", 0)
    logger.info("Yandex Webmaster recrawl quota: %d / %d remaining", quota_remainder, daily_quota)

    recrawl_url = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/recrawl/queue"
    results = []
    submitted_count = 0

    for u in urls:
        if quota_remainder <= 0:
            results.append({"url": u, "status": "SKIPPED_QUOTA_EXCEEDED"})
            continue

        try:
            req_data = json.dumps({"url": u}).encode("utf-8")
            req = urllib.request.Request(recrawl_url, data=req_data, headers=wm_headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 202):
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    task_id = resp_data.get("task_id", "")
                    quota_remainder = resp_data.get("quota_remainder", quota_remainder - 1)
                    submitted_count += 1
                    results.append({"url": u, "status": "SUBMITTED", "task_id": task_id})
                    logger.info("Yandex recrawl queued: %s (task: %s)", u, task_id)
                else:
                    results.append({"url": u, "status": f"HTTP_{resp.status}"})
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            results.append({"url": u, "status": f"HTTP_ERROR_{he.code}", "detail": err_body[:200]})
        except Exception as e:
            results.append({"url": u, "status": "ERROR", "detail": str(e)})

    return {
        "ok": True,
        "daily_quota": daily_quota,
        "quota_remainder": quota_remainder,
        "submitted_count": submitted_count,
        "tasks": results,
    }


def submit_indexnow(urls: list[str]) -> dict:
    payload = {
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }
    endpoints = [
        ("IndexNow Central", "https://api.indexnow.org/indexnow"),
        ("Yandex IndexNow", "https://yandex.com/indexnow"),
    ]
    results = {}
    for name, ep in endpoints:
        try:
            req = urllib.request.Request(
                ep,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                results[name] = {"status": resp.status, "ok": resp.status in (200, 202)}
                logger.info("%s submission: HTTP %d (%d URLs)", name, resp.status, len(urls))
        except urllib.error.HTTPError as he:
            results[name] = {"status": he.code, "ok": False, "error": str(he)}
            logger.warning("%s error: HTTP %d", name, he.code)
        except Exception as e:
            results[name] = {"status": None, "ok": False, "error": str(e)}
            logger.warning("%s exception: %s", name, e)

    return results


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


def ping_sitemaps() -> dict:
    pings = {
        "google": f"https://www.google.com/ping?sitemap={urllib.request.quote(SITEMAP_URL, safe=':/?=')}",
        "yandex": f"https://webmaster.yandex.ru/ping?sitemap={urllib.request.quote(SITEMAP_URL, safe=':/?=')}",
    }
    results = {}
    for engine, ping_url in pings.items():
        try:
            req = urllib.request.Request(ping_url, headers={"User-Agent": "TenderLex-Ping/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                results[engine] = {"status": resp.status, "ok": resp.status < 400}
                logger.info("Pinged %s sitemap: HTTP %d", engine, resp.status)
        except Exception as e:
            results[engine] = {"status": None, "ok": False, "error": str(e)}
    return results


def main():
    print("=" * 60)
    print("TenderLex Autonomous Multi-Engine Reindex Trigger")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    all_urls = fetch_sitemap_urls()
    print(f"Total sitemap URLs discovered: {len(all_urls)}")

    # 1. Yandex Webmaster Recrawl Queue (API)
    print("\n--- 1. Submitting Priority URLs to Yandex.Webmaster Recrawl Queue ---")
    yandex_res = submit_yandex_webmaster_recrawl(PRIORITY_URLS)
    print(f"Yandex Webmaster: submitted {yandex_res.get('submitted_count', 0)} URLs. Remaining quota: {yandex_res.get('quota_remainder', 0)}")
    for task in yandex_res.get("tasks", []):
        print(f"  • {task.get('status')}: {task.get('url')} (task_id: {task.get('task_id', '-')})")

    # 2. IndexNow Push (Yandex, Bing, etc.)
    print(f"\n--- 2. Submitting all {len(all_urls)} URLs to IndexNow (Yandex + Bing) ---")
    indexnow_res = submit_indexnow(all_urls)
    for name, res in indexnow_res.items():
        print(f"  • {name}: HTTP {res.get('status')} (ok: {res.get('ok')})")

    # 3. Google Search Console Sitemaps API
    print("\n--- 3. Submitting sitemap.xml to Google Search Console API ---")
    gsc_res = submit_google_search_console_sitemap()
    print(f"  • GSC: ok={gsc_res.get('ok')} (error={gsc_res.get('error', 'None')})")

    # 4. Sitemap Pings
    print("\n--- 4. Pinging Sitemap Endpoints ---")
    ping_res = ping_sitemaps()
    for engine, res in ping_res.items():
        print(f"  • {engine}: status={res.get('status')} ok={res.get('ok')}")

    # Output artifact summary
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sitemap_urls_count": len(all_urls),
        "yandex_webmaster": yandex_res,
        "indexnow": indexnow_res,
        "google_search_console": gsc_res,
        "sitemap_pings": ping_res,
    }
    out_file = ROOT_DIR / "data" / "reindex_execution_latest.json"
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nExecution saved to: {out_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
