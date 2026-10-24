#!/usr/bin/env python3
"""Regression coverage for admin refreshes using only mocked API responses."""

import json
from datetime import datetime, timezone
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from test_admin_navigation_browser import payload as shell_payload


ROOT = Path(__file__).resolve().parent.parent
DIST = Path(os.environ.get("ADMIN_QA_DIST", ROOT / "frontend" / "dist"))
BASE_URL = os.environ.get("ADMIN_QA_BASE_URL", "http://admin.test/")

SNAPSHOT = {
    "schema_version": 2,
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "collection_status": "active",
    "metrika": {"period": {"start_date": "2026-10-01", "end_date": "2026-10-18", "timezone": "Europe/Moscow"}, "users": 15, "visits": 26, "pageviews": 33, "bounce_rate": 23.1, "avg_duration_seconds": 145, "sources": [], "top_pages": [], "goals": [], "primary_conversion": {}},
    "webmaster": {"status": "active", "period": {"start_date": "2026-10-01", "end_date": "2026-10-18"}, "top_queries": [], "daily_dynamics": []},
    "google": {"status": "active", "period": {"start_date": "2026-10-01", "end_date": "2026-10-18"}, "property_totals": {}, "top_queries": [], "daily_dynamics": []},
}
CLIENTS = {
    "clients": [
        {"id": "client-a", "name": "Клиент А", "email": "a@example.test", "telegram_id": "", "balance_rub": 1000, "allowed": True, "custom_price_rub": None, "effective_price_rub": 50, "has_override": False},
        {"id": "client-b", "name": "Клиент Б", "email": "b@example.test", "telegram_id": "", "balance_rub": 1000, "allowed": True, "custom_price_rub": None, "effective_price_rub": 50, "has_override": False},
    ]
}
SETTINGS = {"default_price_rub": 50, "max_suppliers_per_item": 5, "max_positions": 1000, "concurrency": 4, "cluster_ratio": 1.4, "filter_marketplaces": True, "filter_foreign_sources": True, "max_variation_pct": 33}


def asset_response(path: str) -> tuple[str, bytes]:
    file_path = DIST / (path.lstrip("/") if path.startswith("/assets/") else "index.html")
    return mimetypes.guess_type(str(file_path))[0] or "application/octet-stream", file_path.read_bytes()


def main() -> int:
    checks: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        context.add_init_script(
            """
            (() => {
              const setIntervalNative = window.setInterval.bind(window);
              window.setInterval = (callback, delay, ...args) =>
                setIntervalNative(callback, delay === 120000 ? 20 : delay, ...args);
              const fetchNative = window.fetch.bind(window);
              let seoRequests = 0;
              window.fetch = (input, init) => {
                const url = input instanceof Request ? input.url : String(input);
                if (new URL(url, location.href).pathname === '/api/seo-analytics' && ++seoRequests === 2) {
                  window.__seoAnalyticsCalls = seoRequests;
                  return new Promise((resolve) => {
                    window.__releaseSeoPoll = () => {
                      window.__releaseSeoPoll = null;
                      return fetchNative(input, init).then(resolve);
                    };
                  });
                }
                if (new URL(url, location.href).pathname === '/api/seo-analytics') {
                  window.__seoAnalyticsCalls = seoRequests;
                }
                return fetchNative(input, init);
              };
            })();
            """
        )
        page = context.new_page()
        page.set_default_timeout(5_000)
        errors: list[str] = []
        seo_calls = 0
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(f"console: {message.text}") if message.type == "error" else None)

        def intercept(route):
            nonlocal seo_calls
            request = route.request
            path = urlparse(request.url).path
            if not path.startswith("/api/"):
                if not request.url.startswith("http://admin.test/"):
                    return route.continue_()
                content_type, body = asset_response(path)
                return route.fulfill(status=200, content_type=content_type, body=body)
            if path == "/api/auth/session":
                body = {"ok": True}
            elif path == "/api/seo-analytics":
                seo_calls += 1
                body = SNAPSHOT
            elif path == "/api/price-monitoring/settings":
                body = SETTINGS
            elif path == "/api/price-monitoring/clients":
                body = CLIENTS
            elif path == "/api/price-monitoring/jobs":
                body = {"jobs": []}
            elif path == "/api/price-monitoring/clients/client-a" and request.method == "POST":
                body = {"ok": True}
            elif path == "/api/dashboard":
                body = {"total_clients": 0, "total_jobs": 0, "running_jobs": 0, "failed_jobs": 0}
            elif path == "/api/settings":
                body = {}
            else:
                body = shell_payload(path)
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

        context.route("**/*", intercept)
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_selector(".app-shell")
        page.wait_for_timeout(150)
        print(json.dumps({"before_price_navigation": page.locator("body").inner_text()[:500], "runtime_errors": errors}, ensure_ascii=False), flush=True)
        page.locator('a[href="#price_monitoring"]').click()
        page.get_by_text("Клиент А", exact=True).wait_for()
        client_b = page.get_by_text("Клиент Б", exact=True).locator("xpath=ancestor::tr")
        price_input_b = client_b.locator('input[type="number"]')
        price_input_b.fill("222")
        client_a = page.get_by_text("Клиент А", exact=True).locator("xpath=ancestor::tr")
        client_a.get_by_role("button", name="Сохранить", exact=True).click()
        page.wait_for_timeout(250)
        assert price_input_b.input_value() == "222", "Refreshing one saved client discarded a different unsaved edit"
        checks.append("client-dirty-edit-survives-other-client-save")

        page.locator('a[href="#seo"]').click()
        page.get_by_text("Данные загружены", exact=True).wait_for()
        page.wait_for_function("window.__seoAnalyticsCalls >= 2")
        assert page.get_by_text("Данные загружены", exact=True).count() == 1, "Background SEO refresh replaced loaded status with a blocking checking badge"
        assert page.get_by_text("Проверяем обновления…", exact=True).count() == 1, "Background SEO refresh must have a scoped indicator"
        page.evaluate("window.__releaseSeoPoll()")
        page.wait_for_function("window.__seoAnalyticsCalls >= 2 && !window.__releaseSeoPoll")
        assert seo_calls >= 2, "SEO polling fixture did not execute"
        checks.append("seo-background-refresh-keeps-loaded-status")

        assert not errors, errors
        context.close()
        browser.close()
    print(json.dumps({"checks": checks, "dist": str(DIST)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
