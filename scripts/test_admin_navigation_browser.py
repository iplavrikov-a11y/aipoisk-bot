"""Smoke every admin view with a fully intercepted API.

This intentionally never calls the production admin API.  It makes the
authenticated shell deterministic while exercising the deployed JavaScript,
navigation, and each view's loading/error boundary.
"""

import asyncio
import json
import os
from collections import Counter
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


BASE_URL = os.environ.get("ADMIN_QA_BASE_URL", "https://admin.tenderlex.ru/")
FAIL_DASHBOARD = os.environ.get("ADMIN_QA_DASHBOARD_500") == "1"

VIEWS = [
    "dashboard",
    "seo",
    "clients",
    "jobs",
    "outreach",
    "billing",
    "settings",
    "price_monitoring",
    "cookies",
    "ai",
    "mcp",
]


SETTINGS = {
    "public_base_url": "https://tenderlex.ru",
    "storage_retention_days": 30,
    "completed_job_retention_days": 30,
    "failed_job_retention_days": 30,
    "max_upload_mb": 30,
    "max_files_per_batch": 10,
    "default_supplier_target": 10,
    "allow_partial_supplier_reports": True,
    "logistics_enabled": False,
    "geo_radius_search_enabled_global": True,
    "trial_enabled": True,
    "trial_balance_rub": 1000,
    "primary_provider": "openai",
    "primary_model": "gpt-test",
    "light_provider": "openai",
    "light_model": "gpt-test-mini",
    "supplier_ai_provider": "openai",
    "supplier_ai_model": "gpt-test-mini",
    "custom_ai_providers_json": "[]",
    "saved_models_json": "[]",
    "ai_function_models_json": "{}",
    "ai_analysis_fallback_json": "[]",
    "ai_supplier_fallback_json": "[]",
    "supplier_search_provider_order": "yandex",
    "supplier_search_ui": {"has_active_source": False, "active_label": "", "active_note": "", "technical_sources": []},
    "bot_telegram": "@TenderLexBot",
    "contact_email": "info@example.test",
    "contact_telegram": "@TenderLexSupport",
    "contact_max": "",
    "contact_max_link": "",
    "contact_website": "https://tenderlex.ru",
    "payment_instructions": "Тестовые данные",
    "yandex_search_folder_id": "",
    "google_search_cse_id": "",
    "document_settings_json": "{}",
    "report_settings_json": "{}",
}


def payload(path: str):
    """Return safe minimal data matching the read shape of each view."""
    if path.startswith("/api/auth/session"):
        return {"ok": True}
    if path.startswith("/api/dashboard"):
        return {"total_clients": 0, "total_jobs": 0, "running_jobs": 0, "failed_jobs": 0}
    if path.startswith("/api/ops/system-status"):
        return {
            "server": {"cpu_percent": 1, "ram_percent": 1, "ram_used_gb": 1, "ram_total_gb": 8, "disk_free_gb": 100},
            "services": [], "warnings": [], "status": "ok", "queue": {"pending": 0, "running": 0, "failed": 0},
        }
    if path.startswith("/api/ops/minprom-registry"):
        return {"status": "ok", "configured": True}
    if path.startswith("/api/settings/keys"):
        return {}
    if path.startswith("/api/settings"):
        return SETTINGS
    if path.startswith("/api/clients/sync-check"):
        return {"version_key": "fixture", "clients_count": 0, "latest_client": None}
    if path.startswith("/api/clients"):
        return []
    if path.startswith("/api/jobs"):
        return []
    if path.startswith("/api/tariffs"):
        return [
            {"id": 1, "name": "Старт", "units": 10, "price_kopeks": 100000, "bonus_kopeks": 0, "badge": "Хит", "sort_order": 1, "is_active": True, "kind": "deposit"},
            {"id": 2, "name": "Оптимальный", "units": 35, "price_kopeks": 300000, "bonus_kopeks": 50000, "badge": "Хит", "sort_order": 2, "is_active": True, "kind": "deposit"},
            {"id": 3, "name": "Про", "units": 65, "price_kopeks": 500000, "bonus_kopeks": 150000, "badge": "Хит", "sort_order": 3, "is_active": True, "kind": "deposit"},
            {"id": 4, "name": "Бизнес", "units": 140, "price_kopeks": 1000000, "bonus_kopeks": 400000, "badge": "Хит", "sort_order": 4, "is_active": True, "kind": "deposit"},
            {"id": 5, "name": "Корпоративный", "units": 375, "price_kopeks": 2500000, "bonus_kopeks": 1250000, "badge": "Максимум", "sort_order": 5, "is_active": True, "kind": "deposit"},
            {"id": 6, "name": "1 запрос контактов поставщиков", "units": 1, "price_kopeks": 9900, "bonus_kopeks": 0, "badge": "", "sort_order": 10, "is_active": True, "kind": "supplier_search"},
            {"id": 7, "name": "5 запросов контактов поставщиков", "units": 5, "price_kopeks": 49000, "bonus_kopeks": 0, "badge": "", "sort_order": 11, "is_active": True, "kind": "supplier_search"},
            {"id": 8, "name": "1 запрос подбора аналогов", "units": 1, "price_kopeks": 9900, "bonus_kopeks": 0, "badge": "", "sort_order": 20, "is_active": True, "kind": "exact_product"},
            {"id": 9, "name": "1 анализ документации закупки", "units": 1, "price_kopeks": 9900, "bonus_kopeks": 0, "badge": "", "sort_order": 30, "is_active": True, "kind": "procurement_report"},
            {"id": 10, "name": "1 добор поставщиков", "units": 1, "price_kopeks": 4900, "bonus_kopeks": 0, "badge": "", "sort_order": 40, "is_active": True, "kind": "supplier_search_extra"},
        ]
    if path.startswith("/api/web-password-resets"):
        return []
    if path.startswith("/api/analytics/bot"):
        return {
            "period_days": 30,
            "summary": {},
            "funnel": {},
            "jobs": {"daily": [], "by_mode": [], "by_status": []},
            "top_clients": [],
        }
    if path.startswith("/api/seo-analytics"):
        return {"yandex": {"status": "unavailable"}, "google": {"status": "unavailable"}}
    if path.startswith("/api/price-monitoring/settings"):
        return {"default_price_rub": 50, "max_suppliers_per_item": 5, "max_positions": 1000, "concurrency": 4, "cluster_ratio": 1.4}
    if path.startswith("/api/price-monitoring/clients"):
        return {"clients": []}
    if path.startswith("/api/price-monitoring/jobs"):
        return {"jobs": []}
    if path.startswith("/api/cookies"):
        return {"catalog": []}
    if path.startswith("/api/admin/api-keys"):
        return [] if not path.startswith("/api/admin/api-keys/master") else {"item": None, "raw_api_key": None}
    if path.startswith("/api/outreach/"):
        if path.startswith("/api/outreach/stats"):
            return {"total_leads": 0, "sent": 0, "replied": 0}
        if path.startswith("/api/outreach/settings"):
            return {}
        return []
    return {}


async def main() -> int:
    errors: list[str] = []
    requests: Counter[str] = Counter()
    full_job_polls = 0
    nested_actions: list[str] = []
    slow_resume = False
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        def record_console_error(msg):
            # A deliberately intercepted HTTP 500 is rendered by the app and
            # Chrome reports it as a resource error. It is not a JavaScript
            # runtime failure for this negative test.
            if msg.type == "error" and not (FAIL_DASHBOARD and "500" in msg.text and "Failed to load resource" in msg.text):
                errors.append(f"console: {msg.text}")

        page.on("console", record_console_error)

        async def intercept(route):
            nonlocal full_job_polls
            request = route.request
            parsed = urlsplit(request.url)
            path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            if not path.startswith("/api/"):
                if request.method not in ("GET", "HEAD") or parsed.netloc != urlsplit(BASE_URL).netloc:
                    await route.abort()
                else:
                    await route.continue_()
                return
            requests[path.split("?", 1)[0]] += 1
            if FAIL_DASHBOARD and path.startswith("/api/dashboard"):
                await route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "fixture failure"}))
                return
            if path.startswith("/api/jobs?") and "limit=2000" in path:
                full_job_polls += 1
            if slow_resume and path.startswith(("/api/jobs", "/api/dashboard", "/api/clients/sync-check")):
                await asyncio.sleep(0.2)
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(payload(path)))

        await page.route("**/*", intercept)
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_selector(".app-shell", timeout=10000)
        if FAIL_DASHBOARD:
            await page.wait_for_timeout(300)
            visible_errors = await page.locator(".alert.error").count()
            print(json.dumps({"negative_case": "dashboard_500", "visible_error_banners": visible_errors, "runtime_errors": errors}, ensure_ascii=False))
            await browser.close()
            return 0 if visible_errors >= 1 and not errors else 2

        async def click_if_present(name: str) -> bool:
            button = page.get_by_role("button", name=name, exact=True)
            if await button.count():
                await button.first.click()
                await page.wait_for_timeout(80)
                nested_actions.append(name)
                return True
            return False

        async def exercise_nested(view: str) -> None:
            # Only non-mutating tab switches and opening/closing forms are covered.
            if view == "outreach":
                for name in ("Задачи поиска (0)", "Входящие ответы", "Настройки почты"):
                    await click_if_present(name)
                if await click_if_present("+ Запустить новый поиск"):
                    close = page.get_by_role("button", name="✕ Закрыть", exact=True)
                    if await close.count():
                        await close.click()
                        nested_actions.append("outreach-form-close")
            elif view == "mcp":
                for name in ("🍏 Claude Desktop", "⚡ Cursor", "🤖 ChatGPT", "🐍 Python"):
                    await click_if_present(name)
                if await click_if_present("Создать API-ключ"):
                    close = page.locator(".server-modal-close")
                    if await close.count():
                        await close.first.click()
                        nested_actions.append("mcp-key-dialog-close")

        checked = []
        current_view = "dashboard"
        try:
            for view in VIEWS:
                current_view = view
                await page.locator(f'a[href="#{view}"]').click()
                await page.wait_for_timeout(250)
                await page.wait_for_selector("main.main", timeout=3000)
                checked.append(view)
                if view == "billing" and os.environ.get("ADMIN_QA_SCREENSHOT_BILLING") == "1":
                    screenshot_path = os.environ.get("ADMIN_QA_SCREENSHOT_PATH", "/root/.gemini/antigravity-ide/brain/a2fbabe8-62e1-4c95-a8b8-d5467e74a391/scratch/tariffs_preview.png")
                    await page.screenshot(path=screenshot_path, full_page=True)
                await exercise_nested(view)
        except Exception as exc:
            print(json.dumps({"views_checked": checked, "failed_view": current_view, "api_calls": dict(requests), "runtime_errors": errors, "exception": str(exc)}, ensure_ascii=False))
            await browser.close()
            return 3

        # A full history load is required after opening Jobs, but must not be
        # repeated while another view is selected.
        await page.locator('a[href="#jobs"]').click()
        await page.wait_for_timeout(350)
        slow_resume = True
        before_resume = {"jobs": full_job_polls, "dashboard": requests["/api/dashboard"], "sync": requests["/api/clients/sync-check"]}
        await page.evaluate("""() => {
            window.dispatchEvent(new Event('focus'));
            document.dispatchEvent(new Event('visibilitychange'));
            window.dispatchEvent(new Event('focus'));
        }""")
        await page.wait_for_timeout(350)
        resume_counts = {"jobs": full_job_polls-before_resume["jobs"], "dashboard": requests["/api/dashboard"]-before_resume["dashboard"], "sync": requests["/api/clients/sync-check"]-before_resume["sync"]}
        resume_deduplicated = all(count == 1 for count in resume_counts.values())
        slow_resume = False
        full_job_polls_on_jobs = full_job_polls
        await page.locator('a[href="#dashboard"]').click()
        await page.wait_for_timeout(6500)
        overfetches = full_job_polls - full_job_polls_on_jobs
        expected_nested = {"Задачи поиска (0)", "Входящие ответы", "Настройки почты", "🍏 Claude Desktop", "⚡ Cursor", "🤖 ChatGPT", "🐍 Python", "Создать API-ключ", "mcp-key-dialog-close"}
        nested_present = expected_nested.issubset(nested_actions)
        print(json.dumps({"views_checked": checked, "api_calls": dict(requests), "runtime_errors": errors, "full_job_polls_on_jobs": full_job_polls_on_jobs, "full_job_polls_outside_jobs": overfetches, "nested_actions": nested_actions, "required_nested_actions_present": nested_present, "resume_request_counts": resume_counts, "resume_deduplicated": resume_deduplicated}, ensure_ascii=False))
        await browser.close()
    if errors:
        return 2
    return 0 if full_job_polls_on_jobs >= 1 and overfetches == 0 and nested_present and resume_deduplicated else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
