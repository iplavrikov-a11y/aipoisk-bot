#!/usr/bin/env python3
"""
TenderLex Yandex SEO & Analytics Manager
Handles automated Yandex Webmaster indexing and Yandex Metrika insights.
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# Load env variables from root .env if present
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

def load_env():
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"'")
            if k not in os.environ:
                os.environ[k] = v

load_env()

WEBMASTER_TOKEN = os.environ.get("YANDEX_WEBMASTER_TOKEN", "")
METRIKA_TOKEN = os.environ.get("YANDEX_METRIKA_TOKEN", "")
METRIKA_COUNTER_ID = os.environ.get("YANDEX_METRIKA_COUNTER_ID", "109753178")
HOST_ID = "https:tenderlex.ru:443"

def http_json(url, headers=None, data=None, method="GET"):
    hdrs = headers or {}
    post_bytes = None
    if data is not None:
        post_bytes = json.dumps(data).encode("utf-8")
        hdrs["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=post_bytes, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return {"error": f"HTTP {e.code}: {e.reason}", "details": err_body}
    except Exception as e:
        return {"error": str(e)}

def get_webmaster_user_id():
    res = http_json("https://api.webmaster.yandex.net/v4/user", headers={"Authorization": f"OAuth {WEBMASTER_TOKEN}"})
    if "user_id" in res:
        return res["user_id"]
    raise RuntimeError(f"Failed to get Webmaster user_id: {res}")

def get_webmaster_summary():
    user_id = get_webmaster_user_id()
    headers = {"Authorization": f"OAuth {WEBMASTER_TOKEN}"}
    
    summary = http_json(f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{HOST_ID}/summary", headers=headers)
    queries = http_json(
        f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{HOST_ID}/search-queries/popular?order_by=TOTAL_SHOWS&query_indicator=TOTAL_SHOWS",
        headers=headers
    )
    sitemaps = http_json(f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{HOST_ID}/sitemaps", headers=headers)
    quota = http_json(f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{HOST_ID}/recrawl/quota", headers=headers)
    
    return {
        "summary": summary,
        "queries": queries,
        "sitemaps": sitemaps,
        "quota": quota
    }

def get_metrika_summary(days=30):
    headers = {"Authorization": f"OAuth {METRIKA_TOKEN}"}
    
    def query(params):
        url = f"https://api-metrika.yandex.net/stat/v1/data?ids={METRIKA_COUNTER_ID}&date1={days}daysAgo&date2=today&" + params
        return http_json(url, headers=headers)
    
    # 1. Total overview
    totals = query("metrics=ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate,ym:s:avgVisitDurationSeconds")
    
    # 2. Top traffic sources
    sources = query("metrics=ym:s:visits,ym:s:users&dimensions=ym:s:lastSignTrafficSource&sort=-ym:s:visits")
    
    # 3. Top visited pages
    pages = query("metrics=ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds&dimensions=ym:s:startURLPath&sort=-ym:s:visits&limit=15")
    
    return {
        "totals": totals,
        "sources": sources,
        "pages": pages
    }

def run_report():
    print("==================================================")
    print("📊 TENDERLEX INTEGRATED SEO & METRIKA REPORT")
    print("==================================================")
    
    # 1. Webmaster
    print("\n🔍 --- 1. YANDEX WEBMASTER STATUS ---")
    try:
        wm = get_webmaster_summary()
        sqi = wm["summary"].get("sqi", "N/A")
        searchable = wm["summary"].get("searchable_pages_count", "N/A")
        excluded = wm["summary"].get("excluded_pages_count", "N/A")
        quota = wm["quota"].get("quota_remainder", "N/A")
        
        print(f"• ИКС сайта: {sqi}")
        print(f"• Страниц в поиске Яндекса: {searchable}")
        print(f"• Исключенных страниц: {excluded}")
        print(f"• Доступная квота на переобход: {quota} страниц")
        
        print("\n🔥 Реальные поисковые запросы из Яндекса:")
        queries_list = wm["queries"].get("queries", [])
        for q in queries_list[:10]:
            text = q.get("query_text", "")
            shows = q.get("indicators", {}).get("TOTAL_SHOWS", 0)
            print(f"  - [{shows:.0f} показ(ов)] {text}")
    except Exception as e:
        print(f"Webmaster error: {e}")
        
    # 2. Metrika
    print("\n📈 --- 2. YANDEX METRIKA INSIGHTS (Last 30 Days) ---")
    try:
        m = get_metrika_summary(days=30)
        tot_data = m["totals"].get("totals", [])
        if tot_data and len(tot_data) >= 5:
            visits = int(tot_data[0])
            users = int(tot_data[1])
            pageviews = int(tot_data[2])
            bounce = round(float(tot_data[3]), 1)
            duration_s = int(tot_data[4])
            min_s = f"{duration_s // 60}m {duration_s % 60}s"
            
            print(f"• Посетители: {users} чел. | Визиты: {visits} | Просмотры: {pageviews}")
            print(f"• Среднее время на сайте: {min_s}")
            print(f"• Отказы: {bounce}%")
            
        print("\n📌 Источники трафика:")
        for r in m["sources"].get("data", []):
            src_name = r["dimensions"][0]["name"]
            v = int(r["metrics"][0])
            print(f"  • {src_name:25s}: {v:3d} визитов")
            
        print("\n📄 Топ страниц по посещаемости:")
        for r in m["pages"].get("data", []):
            path = r["dimensions"][0]["name"]
            v = int(r["metrics"][0])
            u = int(r["metrics"][1])
            b = round(r["metrics"][2], 1)
            d = int(r["metrics"][3])
            print(f"  • {path:40s} | {v:3d} виз. | {u:2d} польз. | отказ: {b:4.1f}% | {d}s")
    except Exception as e:
        print(f"Metrika error: {e}")
        
    print("\n==================================================")

def main():
    parser = argparse.ArgumentParser(description="TenderLex Yandex SEO & Analytics Manager")
    parser.add_argument("--recrawl", action="store_true", help="Queue explicitly changed public URLs")
    parser.add_argument("--changed-url", action="append", default=[], metavar="URL")
    parser.add_argument("--report", action="store_true", help="Display combined SEO + Metrika report")
    parser.add_argument("--json", action="store_true", help="Output raw data in JSON format")
    
    args = parser.parse_args()
    
    if args.recrawl:
        if not args.changed_url:
            parser.error("--recrawl requires at least one --changed-url")
        sys.path.insert(0, str(ROOT_DIR / "backend"))
        from app.yandex_seo import submit_sitemap_recrawl
        response = submit_sitemap_recrawl(args.changed_url)
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0 if response.get("ok") else 1
    elif args.changed_url:
        parser.error("--changed-url requires --recrawl")
    elif args.json:
        wm = get_webmaster_summary()
        m = get_metrika_summary()
        print(json.dumps({"webmaster": wm, "metrika": m}, indent=2, ensure_ascii=False))
    else:
        run_report()

if __name__ == "__main__":
    raise SystemExit(main())
