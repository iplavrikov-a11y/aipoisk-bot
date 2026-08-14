#!/usr/bin/env python3
import os
import sys
import xml.etree.ElementTree as ET
import requests

INDEXNOW_KEY = "8fa93cd04f90454a82f7ff7d4434a4c6"
KEY_LOCATION = "https://tenderlex.ru/8fa93cd04f90454a82f7ff7d4434a4c6.txt"
HOST = "tenderlex.ru"
SITEMAP_URL = "https://tenderlex.ru/sitemap.xml"

def get_sitemap_urls():
    resp = requests.get(SITEMAP_URL, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = []
    for loc in root.findall('.//ns:loc', namespace):
        if loc.text:
            urls.append(loc.text.strip())
    return urls

def main():
    print(f"Fetching sitemap from {SITEMAP_URL}...")
    try:
        urls = get_sitemap_urls()
    except Exception as e:
        print(f"Error fetching sitemap: {e}")
        urls = [
            "https://tenderlex.ru/",
            "https://tenderlex.ru/poisk-postavshchikov-po-tz",
            "https://tenderlex.ru/poisk-postavshchikov-dlya-tendera",
            "https://tenderlex.ru/poisk-proizvoditeley-po-tz",
            "https://tenderlex.ru/postavshchiki-dlya-zaprosa-kp",
            "https://tenderlex.ru/zapros-kp-po-tz",
            "https://tenderlex.ru/analiz-zakupochnoi-dokumentacii",
            "https://tenderlex.ru/ocenka-riskov-zakupki",
            "https://tenderlex.ru/analiz-rynka-44-fz",
            "https://tenderlex.ru/reestr-minpromtorga-v-zakupkah"
        ]

    print(f"Found {len(urls)} URLs to submit to IndexNow:")
    for u in urls:
        print(f" - {u}")

    payload = {
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls
    }

    print("\nSubmitting to IndexNow (Yandex/Bing)...")
    endpoint = "https://api.indexnow.org/indexnow"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    res = requests.post(endpoint, json=payload, headers=headers, timeout=15)
    print(f"IndexNow response HTTP status: {res.status_code}")
    if res.status_code in (200, 202):
        print("SUCCESS: URLs submitted to IndexNow for Yandex/Bing indexing!")
    else:
        print(f"Notice: IndexNow returned status {res.status_code}: {res.text}")

if __name__ == "__main__":
    main()
