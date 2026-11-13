#!/usr/bin/env python3
"""Regression tests for the public support-chat polling contract.

Every API is intercepted.  The delayed replies deliberately race opening,
closing and a failed send so the test proves UI state is not based on a stale
polling closure.  No real chat session, Telegram notification or customer
message is created.
"""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", default="http://127.0.0.1:3098")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
BASE = args.base.rstrip("/")


def message(message_id: str, text: str, sender: str = "admin") -> dict:
    return {
        "id": message_id,
        "sender": sender,
        "text": text,
        "timestamp": "2026-10-19T08:00:00.000Z",
    }


async def main() -> None:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    mutations: list[str] = []
    message_requests = 0
    send_requests = 0
    first_poll_started = asyncio.Event()
    release_first_poll = asyncio.Event()
    third_poll_started = asyncio.Event()
    release_third_poll = asyncio.Event()
    fourth_poll_started = asyncio.Event()
    release_fourth_poll = asyncio.Event()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        await context.add_init_script(
            """localStorage.clear();
            localStorage.setItem('tenderlex_analytics_consent', 'denied');
            const shorten = (delay) => delay === 4000 || delay === 25000 ? 180 : delay;
            const originalSetTimeout = window.setTimeout;
            const originalSetInterval = window.setInterval;
            window.setTimeout = (fn, delay, ...rest) => originalSetTimeout(fn, shorten(delay), ...rest);
            window.setInterval = (fn, delay, ...rest) => originalSetInterval(fn, shorten(delay), ...rest);"""
        )
        page = await context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def intercept(route):
            nonlocal message_requests, send_requests
            request = route.request
            url = urlparse(request.url)
            if url.netloc != urlparse(BASE).netloc:
                await route.abort()
                return
            if not url.path.startswith("/api/"):
                await route.continue_()
                return
            if url.path == "/api/chat/messages" and request.method == "GET":
                message_requests += 1
                if message_requests == 1:
                    first_poll_started.set()
                    await release_first_poll.wait()
                    payload = {"messages": [*[message(f"history-{i}", f"Архивное сообщение {i}: условия поставки и уточнения по спецификации") for i in range(20)], message("admin-open", "Ответ во время открытия")]}
                elif message_requests == 2:
                    payload = {"messages": [*[message(f"history-{i}", f"Архивное сообщение {i}: условия поставки и уточнения по спецификации") for i in range(20)], message("admin-open", "Ответ во время открытия")]}
                elif message_requests == 3:
                    third_poll_started.set()
                    await release_third_poll.wait()
                    payload = {
                        "messages": [
                            message("admin-open", "Ответ во время открытия"),
                            message("admin-closed", "Ответ после закрытия"),
                        ]
                    }
                else:
                    fourth_poll_started.set()
                    await release_fourth_poll.wait()
                    payload = {
                        "messages": [
                            message("admin-open", "Ответ во время открытия"),
                            message("admin-closed", "Ответ после закрытия"),
                            message("repeat-one", "Повторяющийся текст"),
                            message("repeat-two", "Повторяющийся текст"),
                            message("admin-during-send", "Ответ одновременно с ошибкой отправки"),
                        ]
                    }
                await route.fulfill(status=200, content_type="application/json", body=json.dumps(payload, ensure_ascii=False))
                return
            if url.path == "/api/chat/send" and request.method == "POST":
                send_requests += 1
                if send_requests == 1:
                    await route.fulfill(status=500, content_type="application/json", body='{"error":"synthetic"}')
                else:
                    await route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps({"success": True, "message": message("server-echo", "Подтверждённое сообщение", "user")}, ensure_ascii=False),
                    )
                return
            if request.method != "GET":
                mutations.append(url.path)
                await route.abort()
                return
            await route.fulfill(status=200, content_type="application/json", body="{}")

        await context.route("**/*", intercept)
        await page.goto(BASE + "/", wait_until="domcontentloaded")
        launcher = page.get_by_role("button", name="Чат с поддержкой TenderLex")
        await launcher.wait_for()
        checks["idle_launcher_does_not_ping"] = await page.locator(".animate-ping").count() == 0
        await page.emulate_media(reduced_motion="reduce")
        checks["reduced_motion_has_no_idle_ping"] = await page.locator(".animate-ping").count() == 0

        await asyncio.wait_for(first_poll_started.wait(), timeout=5)
        await launcher.click()
        release_first_poll.set()
        await page.get_by_text("Ответ во время открытия", exact=True).wait_for()
        await page.get_by_label("Закрыть чат").click()
        await asyncio.wait_for(third_poll_started.wait(), timeout=5)
        checks["open_before_response_does_not_create_stale_unread"] = await launcher.get_by_text("1", exact=True).count() == 0

        release_third_poll.set()
        await launcher.get_by_text("1", exact=True).wait_for(timeout=5000)
        checks["close_before_response_marks_unread"] = await launcher.get_by_text("1", exact=True).count() == 1
        await launcher.click()
        await page.get_by_text("Ответ после закрытия", exact=True).wait_for()
        await asyncio.wait_for(fourth_poll_started.wait(), timeout=5)
        feed = page.locator(".overflow-y-auto").filter(has=page.locator("text=Ответ во время открытия"))
        await feed.evaluate("node => { node.scrollTop = 0; }")
        before_scroll = await feed.evaluate("node => node.scrollTop")
        await page.get_by_placeholder("Напишите сообщение администратору...").fill("Моё сообщение")
        await page.get_by_role("button", name="Отправить сообщение").click()
        await page.get_by_role("alert").wait_for()
        # Sending intentionally scrolls to the end. The reader then returns to
        # older messages before the held incoming reply arrives.
        await feed.evaluate("node => { node.scrollTop = 0; }")
        before_scroll = await feed.evaluate("node => node.scrollTop")
        release_fourth_poll.set()
        await page.get_by_text("Ответ одновременно с ошибкой отправки", exact=True).wait_for()
        await page.wait_for_timeout(100)
        after_scroll = await feed.evaluate("node => node.scrollTop")
        checks["incoming_message_does_not_yank_reader"] = before_scroll == after_scroll
        assert await feed.evaluate("node => node.scrollHeight > node.clientHeight + 48"), "Fixture must have scrollable message history"

        await page.wait_for_timeout(100)
        checks["same_text_messages_with_distinct_ids_are_preserved"] = await page.get_by_text("Повторяющийся текст", exact=True).count() == 2
        checks["failed_send_keeps_concurrent_admin_message"] = await page.get_by_text("Ответ одновременно с ошибкой отправки", exact=True).count() == 1
        checks["failed_optimistic_message_is_removed"] = await page.get_by_text("Моё сообщение", exact=True).count() == 0
        await page.get_by_placeholder("Напишите сообщение администратору...").fill("Подтверждённое сообщение")
        await page.get_by_role("button", name="Отправить сообщение").click()
        await page.get_by_text("Подтверждённое сообщение", exact=True).wait_for()
        checks["successful_optimistic_echo_reconciles_once"] = await page.get_by_text("Подтверждённое сообщение", exact=True).count() == 1
        checks["no_unexpected_mutations"] = not mutations
        checks["no_runtime_errors"] = not errors
        await browser.close()

    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "messageRequests": message_requests,
        "sendRequests": send_requests,
        "runtimeErrors": errors,
        "boundary": "All chat APIs are intercepted; no real chat, Telegram delivery or customer mutation.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    assert all(checks.values()), "Chat polling regression"


asyncio.run(main())
