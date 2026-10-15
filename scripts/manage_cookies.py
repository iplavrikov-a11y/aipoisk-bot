#!/usr/bin/env python3
"""
TenderLex: Cookie Manager CLI.
Usage:
  python3 scripts/manage_cookies.py set --domain etm.ru --cookies "session_id=123; qrator_msid=abc"
  python3 scripts/manage_cookies.py list
  python3 scripts/manage_cookies.py test --url "https://www.etm.ru/catalog"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, "/root/projects/tenderlex/backend")

import httpx
from app.price_monitoring.cookie_manager import cookie_manager


async def test_url(url: str):
    cookie = cookie_manager.get_cookie_for_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if cookie:
        headers["Cookie"] = cookie
        print(f"Applying cookie for {url}: {cookie[:40]}... (len={len(cookie)})")
    else:
        print(f"No custom cookie found for {url}. Sending without cookie.")

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers)
            print(f"Status: HTTP {resp.status_code}")
            print(f"Response size: {len(resp.text)} chars")
            if resp.status_code == 200:
                print("SUCCESS: Site accessible!")
            elif resp.status_code in (403, 444, 503):
                print(f"BLOCKED: Site returned HTTP {resp.status_code} (WAF / anti-bot challenge active).")
            else:
                print(f"HTTP Response code: {resp.status_code}")
        except Exception as e:
            print(f"Request error: {e}")


def main():
    parser = argparse.ArgumentParser(description="TenderLex Cookie Manager CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Set
    set_parser = subparsers.add_parser("set", help="Set cookie for a domain")
    set_parser.add_argument("--domain", required=True, help="Domain, e.g. etm.ru, chipdip.ru")
    set_parser.add_argument("--cookies", required=True, help="Cookie string (e.g. from DevTools or Cookie-Editor)")

    # List
    subparsers.add_parser("list", help="List configured domain cookies")

    # Test
    test_parser = subparsers.add_parser("test", help="Test fetching a URL with configured cookies")
    test_parser.add_argument("--url", required=True, help="URL to test")

    args = parser.parse_args()

    if args.command == "set":
        cookie_manager.set_cookie(args.domain, args.cookies)
        print(f"Saved cookies for domain '{args.domain}' ({len(args.cookies)} chars).")
    elif args.command == "list":
        domains = cookie_manager.list_domains()
        if not domains:
            print("No domain cookies configured yet.")
        else:
            print("Configured domain cookies:")
            for d, length in domains.items():
                print(f"  • {d}: {length} chars")
    elif args.command == "test":
        asyncio.run(test_url(args.url))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
