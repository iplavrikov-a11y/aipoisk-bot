"""Regression test for Outreach background polling.

Every request is intercepted.  The fixture holds the first inbox reply while a
newer filtered request completes, proving that stale polling cannot replace a
user's current inbox view.  It also checks that background task polling does
not put the mail-settings save button into its unrelated "saving" state.
"""

import asyncio
import json
import os
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from test_admin_navigation_browser import payload as admin_payload


BASE_URL = os.environ.get("ADMIN_QA_BASE_URL", "https://admin.tenderlex.ru/")


def task(status: str = "running") -> dict:
    return {
        "id": "task-1", "name": "Fixture task", "prompt": "Initial prompt",
        "target_count": 50, "collected_count": 1, "scanned_sites": 1,
        "queries_count": 1, "status": status, "message": "", "yandex_requests": 0,
        "yandex_cost_rub": 0, "llm_cost_rub": 0, "total_cost_rub": 0,
        "cost_label": "0 ₽", "started_at": None, "completed_at": None,
        "created_at": "2026-01-01T00:00:00Z",
    }


async def main() -> int:
    errors: list[str] = []
    fixture_mutations: list[str] = []
    escaped_mutations: list[str] = []
    inbox_requests = 0
    lead_requests = 0
    held_inbox: asyncio.Future | None = None
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        await page.add_init_script("""
          localStorage.setItem('tenderlex_outreach_selected_task_id', 'task-1');
          localStorage.setItem('tenderlex_outreach_maintab', 'tasks');
        """)

        async def intercept(route):
            nonlocal inbox_requests, lead_requests, held_inbox
            request = route.request
            parsed = urlsplit(request.url)
            path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            if not path.startswith("/api/"):
                if request.method not in ("GET", "HEAD") or parsed.netloc != urlsplit(BASE_URL).netloc:
                    await route.abort()
                else:
                    await route.continue_()
                return
            if request.method not in ("GET", "HEAD"):
                if path.startswith("/api/outreach/campaigns"):
                    fixture_mutations.append(path)
                    await asyncio.sleep(1.2)
                    await route.fulfill(status=200, content_type="application/json", body=json.dumps({"id": "campaign-1"}))
                    return
                if path.startswith("/api/outreach/search/start"):
                    fixture_mutations.append(path)
                    await asyncio.sleep(1.2)
                    await route.fulfill(status=200, content_type="application/json", body=json.dumps({"task_id": "task-2"}))
                    return
                escaped_mutations.append(path)
                await route.abort()
                return
            if path.startswith("/api/auth/session"):
                body = {"ok": True}
            elif path.startswith("/api/outreach/tasks/") and path.endswith("/stats"):
                body = {"task": task(), "total_leads": 1, "new_leads": 1, "sent_leads": 0, "replied_leads": 0, "mx_valid_leads": 1}
            elif path.startswith("/api/outreach/tasks"):
                body = {"items": [task()]}
            elif path.startswith("/api/outreach/search/status/"):
                body = task("completed")
            elif path.startswith("/api/outreach/leads"):
                lead_requests += 1
                if lead_requests > 1:
                    await asyncio.sleep(1.5)
                body = {"items": [], "total": 0, "page": 1}
            elif path.startswith("/api/outreach/campaigns"):
                body = {"items": []}
            elif path.startswith("/api/outreach/settings"):
                body = {}
            elif path.startswith("/api/outreach/inbox"):
                inbox_requests += 1
                # The delayed first request models a slow background poll. The
                # second request is the user's newer filter change.
                if "category=replies" not in path:
                    body = {"items": [], "total": 0}
                elif held_inbox is None:
                    held_inbox = asyncio.get_running_loop().create_future()
                    await held_inbox
                    body = {"items": [{"id": "old", "sender_email": "old@example.test", "subject": "old", "body_text": "old", "body_html": "", "date_received": "2026-01-01", "is_read": False}], "total": 1}
                else:
                    body = {"items": [{"id": "new", "sender_email": "new@example.test", "subject": "new", "body_text": "new", "body_html": "", "date_received": "2026-01-01", "is_read": False}], "total": 1}
            else:
                body = admin_payload(path)
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

        await page.route("**/*", intercept)
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_selector('.app-shell', timeout=10000)
        await page.locator('a[href="#outreach"]').click()
        await page.wait_for_selector('.outreach-container', timeout=10000)
        prompt = page.locator('textarea[placeholder^="Промпт поиска"]')
        lead_filter = page.locator('input[placeholder^="Поиск по компании"]')
        await prompt.fill("Пользовательский критерий")
        await lead_filter.fill("пользовательский фильтр")
        await page.get_by_role("button", name="Настройки почты").click()
        await page.wait_for_timeout(2200)
        save_button = page.get_by_role("button", name="Сохранить настройки")
        settings_not_polling = await save_button.count() == 1 and await save_button.is_enabled()

        await page.get_by_role("button", name="Задачи поиска (1)").click()
        await page.wait_for_timeout(50)
        workspace_not_reset = await prompt.input_value() == "Пользовательский критерий" and await lead_filter.input_value() == "пользовательский фильтр"

        await page.get_by_role("button", name="Email-рассылка").click()
        await page.get_by_role("button", name="Запустить рассылку").click()
        await page.wait_for_timeout(80)
        await page.get_by_role("button", name="Настройки почты").click()
        campaign_does_not_disable_settings = await save_button.is_enabled()

        await page.get_by_role("button", name="Задачи поиска (1)").click()
        await page.get_by_role("button", name="Все задачи").click()
        await page.get_by_role("button", name="+ Запустить новый поиск").click()
        await page.get_by_placeholder("Например: Поставщики оборудования и исполнители госконтрактов 44-ФЗ").fill("Fixture search")
        await page.get_by_placeholder("Например: компании занимающиеся участием в тендерах, поставщики промышленного оборудования, торговые дома и снабжение по 44-ФЗ и 223-ФЗ").fill("Fixture criteria")
        await page.get_by_role("button", name="Запустить сбор контактов").click()
        await page.wait_for_timeout(80)
        await page.get_by_role("button", name="Настройки почты").click()
        search_does_not_disable_settings = await save_button.is_enabled()

        await page.get_by_role("button", name="Входящие ответы").click()
        await page.wait_for_timeout(100)
        await page.get_by_role("button", name="🟢 Живые ответы (0)").click()
        await page.wait_for_timeout(100)
        await page.get_by_role("button", name="🟢 Живые ответы (0)").click()
        await page.wait_for_timeout(100)
        if held_inbox and not held_inbox.done():
            held_inbox.set_result(None)
        await page.wait_for_timeout(250)
        inbox_not_overwritten = await page.get_by_text("new@example.test").count() > 0 and await page.get_by_text("old@example.test").count() == 0
        checks = {
            "background_task_poll_does_not_disable_settings_save": settings_not_polling,
            "background_task_refresh_preserves_workspace_inputs": workspace_not_reset,
            "campaign_creation_does_not_disable_settings_save": campaign_does_not_disable_settings,
            "search_start_does_not_disable_settings_save": search_does_not_disable_settings,
            "stale_inbox_response_does_not_replace_newer_filter": inbox_not_overwritten,
            "only_expected_fixture_mutations": len(fixture_mutations) == 2,
            "no_escaped_mutations": not escaped_mutations,
            "no_runtime_errors": not errors,
        }
        print(json.dumps({"status": "passed" if all(checks.values()) else "failed", "checks": checks, "inbox_requests": inbox_requests, "fixture_mutations": fixture_mutations, "escaped_mutations": escaped_mutations, "runtime_errors": errors}, ensure_ascii=False))
        await browser.close()
        return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
