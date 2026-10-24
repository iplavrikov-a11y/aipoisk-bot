#!/usr/bin/env python3
"""Verify the Home v3 walkthrough: actionable demo, honest feedback, motion and no mutations."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", default="http://127.0.0.1:3098")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
base = args.base.rstrip("/")
checks = []


def check(name, condition=True):
    assert condition, name
    checks.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    mutations = []

    def route(request_route):
        request = request_route.request
        if request.method not in ["GET", "HEAD"]:
            mutations.append(request.url)
            request_route.abort()
        elif urlparse(request.url).netloc != urlparse(base).netloc:
            request_route.abort()
        elif "/api/chat/" in request.url:
            request_route.fulfill(status=200, content_type="application/json", body='{"messages":[]}')
        else:
            request_route.continue_()

    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.route("**/*", route)
    context.add_init_script("localStorage.setItem('tenderlex_analytics_consent','denied');")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base, wait_until="networkidle")
    page.wait_for_timeout(700)

    check("home v3 wrapper", page.locator(".home-v3").count() == 1)
    check("one h1", page.locator("h1").count() == 1)
    check("existing header retained", page.locator(".tl-site-header").count() == 1)
    check("existing footer retained", page.locator(".tl-site-footer").count() == 1)
    demo = page.locator(".home-v3 .demo")
    check("learning goal visible", "после разбора вы сможете" in demo.inner_text().lower())
    check("five step tabs", demo.locator("[data-step]").count() == 5)

    demo.locator('[data-step="2"]').click()
    page.wait_for_timeout(350)
    check("step 2 title", page.locator("[data-step-title]").inner_text() == "Разбор")
    check("step 2 URL state", "step=2" in page.url)
    check("step 2 panel visible", page.locator('[data-step-view="2"]').is_visible())
    page.locator('[data-extract="6"]').click()
    check("missing field explains its source", "is-active" in (page.locator('[data-source-line="6"]').get_attribute("class") or ""))

    demo.locator('[data-step="3"]').click()
    page.wait_for_timeout(250)
    page.locator('[data-supplier-filter="manufacturer"]').click()
    check("candidate filter works", page.locator(".supplier-card:visible").count() == 1)
    check("filtered candidates are explained", "Почему в списке" in page.locator('[data-step-view="3"]').inner_text())

    demo.locator('[data-step="4"]').click()
    page.wait_for_timeout(250)
    page.locator("[data-diff-toggle]").click()
    check(
        "only-differences removes matching rows",
        page.locator('.diff-table tbody tr[data-diff="same"]').evaluate_all(
            "(rows) => rows.every((row) => getComputedStyle(row).display === 'none')"
        ),
    )

    demo.locator('[data-step="5"]').click()
    page.wait_for_timeout(250)
    page.locator('[data-quiz-option="quantity"]').click()
    check("wrong self-check is explained", "Количество уже есть" in page.locator("[data-quiz-feedback]").inner_text())
    check("wrong self-check is marked", "is-wrong" in (page.locator('[data-quiz-option="quantity"]').get_attribute("class") or ""))
    page.locator('[data-quiz-option="payment"]').click()
    check("correct self-check is explained", "Верно" in page.locator("[data-quiz-feedback]").inner_text())
    check("correct self-check is marked", "is-correct" in (page.locator('[data-quiz-option="payment"]').get_attribute("class") or ""))

    check("no task or payment mutations", not mutations)
    check("zero runtime errors", not errors)

    page.locator("#outcomes").scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    check("scroll reveal starts CSS animations", page.evaluate("document.getAnimations().filter(a=>a.playState==='running').length") > 0)
    check("heading stays visible", page.locator("h1").evaluate("(e)=>getComputedStyle(e).opacity") == "1")
    for width in [375, 430, 768, 1024, 1440]:
        page.set_viewport_size({"width": width, "height": 1000})
        check("no page overflow " + str(width), page.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
    page.screenshot(path=str(args.output.with_suffix(".png")))
    context.close()

    context = browser.new_context(viewport={"width": 375, "height": 900}, reduced_motion="reduce")
    context.route("**/*", route)
    context.add_init_script("localStorage.setItem('tenderlex_analytics_consent','denied');")
    page = context.new_page()
    page.goto(base, wait_until="networkidle")
    page.wait_for_timeout(1000)
    check("reduced-motion content readable", page.locator("h1").evaluate("(e)=>getComputedStyle(e).opacity") == "1")
    check("reduced-motion has no running animations", page.evaluate("document.getAnimations().filter(a=>a.playState==='running').length") == 0)
    check("autoplay is off", page.evaluate("window.__TENDERLEX_HOME_V3__?.autoplay === false"))
    context.close()

    context = browser.new_context(java_script_enabled=False, viewport={"width": 1440, "height": 1000})
    context.route("**/*", route)
    page = context.new_page()
    page.goto(base, wait_until="load")
    check("no-JS h1 visible", page.locator("h1").is_visible())
    check("no-JS first step visible", page.locator('[data-step-view="1"]').is_visible())
    check("no-JS footer retained", page.locator(".tl-site-footer").count() == 1)
    context.close()
    browser.close()

report = {"status": "passed", "checks": checks, "count": len(checks), "boundary": "No task, payment or external mutations allowed."}
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False))
