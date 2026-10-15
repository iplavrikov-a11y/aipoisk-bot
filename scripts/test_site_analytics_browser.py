#!/usr/bin/env python3
"""Browser regression checks. All customer APIs and Metrika traffic are mocked."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", default="http://127.0.0.1:3093")
parser.add_argument("--evidence-dir", type=Path)
args = parser.parse_args()
base = args.base.rstrip("/")
sdk = """window.__analyticsTestCalls = [...(window.ym && window.ym.a || [])];
window.ym = function(){ window.__analyticsTestCalls.push(Array.from(arguments)); };"""
results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    def make_context(consent=None, ua=None, authenticated=False, viewport=None):
        kwargs = {"viewport": viewport or {"width": 1280, "height": 900}}
        if ua: kwargs["user_agent"] = ua
        context = browser.new_context(**kwargs)
        if consent:
            context.add_init_script("localStorage.setItem('tenderlex_analytics_consent', " + json.dumps(consent) + ");")
        state = {"authenticated": authenticated, "sdk_requests": 0, "register_requests": 0, "job_requests": 0}
        def route(request):
            url = request.request.url
            if "mc.yandex.ru" in url:
                if "/metrika/tag.js" in url:
                    state["sdk_requests"] += 1
                    request.fulfill(status=200, content_type="application/javascript", body=sdk)
                else: request.abort()
                return
            path = url.split("?", 1)[0]
            if "/api/chat/" in path:
                request.fulfill(status=500 if request.request.method == "POST" else 200, content_type="application/json", body=json.dumps({"messages": []}))
            elif "/api/customer/" in path:
                if path.endswith("/auth/register"):
                    state["authenticated"] = True
                    state["register_requests"] += 1
                if path.endswith("/jobs") and request.request.method == "POST":
                    state["job_requests"] += 1
                    payload = {"batch": False, "count": 1}
                elif path.endswith("/jobs"):
                    payload = {"items": [], "total": 0}
                else:
                    balance = {"label": "Задачи", "available": 10, "reserved": 0, "spent": 0, "granted": 10, "low": False}
                    payload = {"authenticated": state["authenticated"], "csrf_token": "TEST-CSRF",
                        "user": {"email": "private@example.org", "name": "Тест", "is_email_verified": True, "is_trial": True},
                        "balance": {"supplier_search": balance, "procurement_report": balance, "money": {"available_kopeks": 10000}},
                        "tariff_groups": {"supplier_search": [], "exact_product": [], "procurement_report": []}}
                request.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
            elif "telegram.org" in url:
                request.fulfill(status=200, content_type="application/javascript", body="")
            else: request.continue_()
        context.route("**/*", route)
        return context, state

    for consent, ua, label in [(None, None, "unknown"), ("denied", None, "denied"),
                              (None, "Mozilla/5.0 (compatible; YandexBot/3.0)", "bot_without_consent")]:
        context, state = make_context(consent, ua)
        page = context.new_page()
        page.goto(base + "/cabinet", wait_until="networkidle")
        assert state["sdk_requests"] == 0, label
        assert page.evaluate("typeof window.ym === 'undefined'"), label
        results.append({"check": label + "_loads_no_analytics", "status": "passed"})
        context.close()

    context, state = make_context("granted")
    page = context.new_page()
    page.goto(base + "/cabinet?private=SECRET#private@example.org", wait_until="networkidle")
    page.wait_for_function("window.__analyticsTestCalls && window.__analyticsTestCalls.some(x => x[1] === 'hit')")
    calls = page.evaluate("window.__analyticsTestCalls")
    assert state["sdk_requests"] == 1
    init = next(call for call in calls if call[1] == "init")
    assert all(init[2][key] is False for key in ["webvisor", "clickmap", "trackLinks", "sendTitle"])
    assert len([call for call in calls if call[1] == "hit"]) == 1
    assert "SECRET" not in json.dumps(calls) and "private@example.org" not in json.dumps(calls)
    page.get_by_role("button", name="Регистрация", exact=True).click()
    page.get_by_placeholder("Ваше имя").fill("Тест")
    page.get_by_placeholder("name@company.ru").fill("private@example.org")
    page.get_by_placeholder("••••••••").fill("Private-Password-123")
    page.locator('form input[type="checkbox"]').nth(0).check()
    page.locator('form input[type="checkbox"]').nth(1).check()
    page.locator('form button[type="submit"]').click()
    page.wait_for_function("window.__analyticsTestCalls.some(x => x[2] === 'registration_success')")
    assert state["register_requests"] == 1
    page.locator("textarea").first.fill("PRIVATE TECHNICAL REQUIREMENTS — do not send to analytics")
    page.locator('form button[type="submit"]').last.click()
    page.wait_for_function("window.__analyticsTestCalls.some(x => x[2] === 'task_started')")
    assert state["job_requests"] == 1
    calls = page.evaluate("window.__analyticsTestCalls")
    serialized = json.dumps(calls)
    assert all(secret not in serialized for secret in ["SECRET", "private@example.org", "Private-Password", "PRIVATE TECHNICAL", "TEST-CSRF"])
    assert len([call for call in calls if call[2:3] == ["registration_success"]]) == 1
    results.append({"check": "successful_registration_and_task_no_private_payload", "status": "passed"})
    before = len(calls)
    page.get_by_role("button", name="Настройки аналитики", exact=True).click()
    page.get_by_role("button", name="Только необходимые", exact=True).click()
    page.wait_for_timeout(150)
    assert any(call[1] == "destruct" for call in page.evaluate("window.__analyticsTestCalls")[before:])
    results.append({"check": "consent_can_be_revoked", "status": "passed"})
    context.close()

    context, state = make_context("granted", authenticated=True)
    page = context.new_page()
    page.goto(base + "/cabinet#registration_success", wait_until="networkidle")
    page.wait_for_function("window.__analyticsTestCalls.some(x => x[2] === 'registration_success')")
    assert not page.url.endswith("#registration_success")
    page.reload(wait_until="networkidle")
    assert not any(call[2:3] == ["registration_success"] for call in page.evaluate("window.__analyticsTestCalls"))
    results.append({"check": "oauth_goal_once_after_authenticated_session", "status": "passed"})
    context.close()

    for scenario in ["supplier_search", "exact_product", "procurement_report", "analysis_and_suppliers", "doc_analysis"]:
        context, _ = make_context(authenticated=True)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + "/cabinet?scenario=" + scenario, wait_until="networkidle")
        assert page.get_by_role("tab", selected=True).count() == 1, scenario
        label = page.get_by_role("tab", selected=True).inner_text()
        assert ("Анализ" in label if scenario in ["procurement_report", "doc_analysis"] else True), label
        assert not errors, (scenario, errors)
        context.close()
    results.append({"check": "all_four_modules_and_legacy_analysis_link_render", "status": "passed"})

    context, _ = make_context("denied")
    page = context.new_page()
    page.goto(base + "/", wait_until="networkidle")
    page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async text => {window.__copiedText = text;}}, configurable: true})")
    page.get_by_role("button", name="Скопировать текст КП", exact=True).click()
    page.get_by_role("button", name="Скопировано!", exact=True).wait_for()
    assert "5 000" in page.evaluate("window.__copiedText")
    page.evaluate("window.dispatchEvent(new Event('open_tenderlex_chat'))")
    page.get_by_placeholder("Напишите сообщение администратору...").fill("TEST — delivery failure fixture")
    page.locator("form").last.locator('button[type="submit"]').click()
    page.get_by_role("alert").filter(has_text="Сообщение не отправлено").wait_for()
    assert page.get_by_placeholder("Напишите сообщение администратору...").input_value().startswith("TEST")
    results.append({"check": "rfq_copies_actual_text_and_chat_http_error_is_visible", "status": "passed"})
    context.close()

    context, _ = make_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(base + "/", wait_until="networkidle")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    if args.evidence_dir:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(args.evidence_dir / "home-mobile.png"), full_page=True)
    results.append({"check": "mobile_home_has_no_horizontal_overflow", "status": "passed"})
    context.close()
    browser.close()

if args.evidence_dir:
    (args.evidence_dir / "browser-analytics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
print(json.dumps({"status": "passed", "checks": results}, ensure_ascii=False))
