#!/usr/bin/env python3
"""Exercise exact-product position selection with a fully intercepted API.

No real account, billing operation, task, or external request is used.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", default="http://127.0.0.1:3198")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--width", type=int, default=1280)
parser.add_argument("--height", type=int, default=900)
args = parser.parse_args()
base = args.base.rstrip("/")


def position(number: int) -> dict:
    return {
        "id": f"position-{number}",
        "position_no": number,
        "name": f"Позиция {number}",
        "requirements": {"ГОСТ": f"1234-{number}", "Материал": "сталь"},
        "quantity": str(number),
        "unit": "шт.",
        "source_excerpt": f"Фрагмент ТЗ {number}",
    }


def exact_job(job_id: str, *, status: str = "awaiting_exact_selection", confirmed: bool = False) -> dict:
    items = [position(number) for number in range(1, 9)]
    return {
        "id": job_id,
        "job_number": 100,
        "mode": "exact_product",
        "mode_label": "Подбор товара и аналогов",
        "human_title": "Тестовая спецификация",
        "status": status,
        "status_label": "Выберите позиции" if status == "awaiting_exact_selection" else "Готово",
        "progress": 15 if status == "awaiting_exact_selection" else 100,
        "message": "Выберите позиции для подбора" if status == "awaiting_exact_selection" else "Результат готов",
        "target_suppliers": 0,
        "verified_count": 0,
        "file_count": 1,
        "has_result": status != "awaiting_exact_selection",
        "can_download": False,
        "can_cancel": True,
        "can_find_more_suppliers": False,
        "awaiting_customer_confirmation": False,
        "error": "",
        "created_at": "2026-10-21T12:00:00Z",
        "updated_at": "2026-10-21T12:01:00Z",
        "result_files": [],
        "exact_product_selection": {
            "revision": "fixture-revision-1",
            "max_positions": 5,
            "price_kopeks": 9900,
            "groups": [
                {"id": "core", "name": "Основное оборудование", "item_ids": ["position-1", "position-2", "position-3"]},
                {"id": "accessories", "name": "Комплектующие", "item_ids": ["position-4", "position-5", "position-6", "position-7", "position-8"]},
            ],
            "items": items,
            "selected_ids": [],
            "confirmed": confirmed,
        },
    }


def price_monitoring_job(job_id: str) -> dict:
    items = [
        {
            "id": "source-position-11",
            "position_no": 11,
            "name": "Труба стальная",
            "requirements": [
                {"param_name": "Диаметр", "tz_requirement": "100 мм"},
                {"param_name": "Материал", "tz_requirement": "Сталь 20"},
            ],
            "quantity": "120",
            "unit": "м",
            "source_excerpt": "Труба стальная, диаметром 100 мм",
        },
        *[position(number) for number in range(12, 19)],
    ]
    return {
        "id": job_id,
        "job_number": 101,
        "mode": "price_monitoring",
        "mode_label": "Мониторинг цен",
        "human_title": "Тестовый мониторинг цен",
        "status": "awaiting_position_selection",
        "status_label": "Выберите позиции",
        "progress": 15,
        "message": "Выберите позиции для мониторинга цен",
        "target_suppliers": 0,
        "verified_count": 0,
        "file_count": 1,
        "has_result": False,
        "can_download": False,
        "can_cancel": True,
        "can_find_more_suppliers": False,
        "awaiting_customer_confirmation": False,
        "error": "",
        "created_at": "2026-10-21T12:00:00Z",
        "updated_at": "2026-10-21T12:01:00Z",
        "result_files": [],
        "position_selection": {
            "revision": "monitoring-revision-1",
            "max_positions": 8,
            "price_kopeks": 5000,
            "pricing_mode": "per_found_position",
            "groups": [
                {"id": "pipes", "name": "Трубопрокат", "item_ids": ["source-position-11", "position-12", "position-13"]},
                {"id": "equipment", "name": "Оборудование", "item_ids": ["position-14", "position-15", "position-16", "position-17", "position-18"]},
            ],
            "items": items,
            "selected_ids": [],
            "confirmed": False,
        },
    }


checks: dict[str, bool] = {}
mutations: list[dict] = []
requests: list[str] = []
runtime_errors: list[str] = []
jobs = [exact_job("fixture-parent")]
session = {
    "authenticated": True,
    "csrf_token": "FIXTURE-CSRF-NOT-A-REAL-SECRET",
    "user": {"email": "qa@example.invalid", "name": "QA", "is_trial": False, "is_email_verified": True, "allowed_geo_radius": False, "allowed_price_monitoring": False},
    "balance": {"money": {"balance_kopeks": 350000, "available_kopeks": 350000, "reserved_kopeks": 0, "balance_rub": 3500, "available_rub": 3500, "reserved_rub": 0}},
    "limits": {"max_files_per_batch": 10, "max_upload_mb": 120, "default_supplier_target": 10},
    "tariff_groups": {}, "deposit_packages": [], "contacts": {}, "payment": {}, "referral": {},
}


def record(name: str, value: bool) -> None:
    checks[name] = value
    assert value, name


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context(viewport={"width": args.width, "height": args.height})
    context.add_init_script("localStorage.setItem('tenderlex_analytics_consent','denied');")

    def route(route):
        request = route.request
        parsed = urlparse(request.url)
        requests.append(request.url)
        if parsed.netloc != urlparse(base).netloc:
            route.fulfill(status=200, content_type="application/javascript", body="")
            return
        if not parsed.path.startswith("/api/"):
            route.continue_()
            return
        if request.method not in ("GET", "HEAD"):
            try:
                payload = request.post_data_json
            except Exception:
                payload = {}
            mutations.append({"path": parsed.path, "method": request.method, "payload": payload, "csrf": request.headers.get("x-csrf-token")})

        if parsed.path == "/api/customer/auth/session":
            payload = session
        elif parsed.path == "/api/customer/jobs" and request.method == "GET":
            payload = {"items": jobs, "total": len(jobs), "limit": 15, "offset": 0}
        elif parsed.path.endswith("/exact-selection/retry"):
            selected = request.post_data_json["selected_item_ids"]
            child = exact_job("fixture-retry")
            child["exact_product_selection"]["selected_ids"] = selected
            jobs.append(child)
            payload = {"message": "Создан новый подбор"}
        elif parsed.path.endswith("/exact-selection"):
            selected = request.post_data_json["selected_item_ids"]
            jobs[0] = {**jobs[0], "status": "running", "status_label": "Подбор выполняется", "progress": 25,
                       "exact_product_selection": {**jobs[0]["exact_product_selection"], "selected_ids": selected, "confirmed": True}}
            payload = {"message": "Выбор подтверждён"}
        elif parsed.path.endswith("/position-selection"):
            selected = request.post_data_json["selected_item_ids"]
            jobs[0] = {**jobs[0], "status": "running", "status_label": "Мониторинг выполняется", "progress": 25,
                       "position_selection": {**jobs[0]["position_selection"], "selected_ids": selected, "confirmed": True}}
            payload = {"message": "Выбор позиций для мониторинга подтверждён"}
        elif parsed.path.startswith("/api/chat/"):
            payload = {"messages": [], "ok": True}
        else:
            route.fulfill(status=400, content_type="application/json", body=json.dumps({"detail": "Unexpected fixture request"}))
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload, ensure_ascii=False))

    context.route("**/*", route)
    page = context.new_page()
    page.set_default_timeout(5000)
    page.on("pageerror", lambda error: runtime_errors.append(str(error)))
    page.goto(base + "/cabinet?scenario=exact_product", wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    if not page.get_by_role("dialog", name="Выберите позиции").is_visible():
        raise AssertionError(f"exact selection dialog did not open; requests: {requests}; page text: {page.locator('body').inner_text()[:800]}; runtime errors: {runtime_errors}")

    dialog = page.get_by_role("dialog", name="Выберите позиции")
    dialog.wait_for()
    record("no_horizontal_page_overflow", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(args.output.with_suffix(".png")), full_page=True)
    record("all_eight_positions_are_visible", dialog.get_by_role("checkbox").count() == 8)
    record("groups_and_rows_are_distinguished", bool(re.search(r"Категорий:\s*2", dialog.inner_text())) and "8 товарных строк" in dialog.inner_text())
    record("exact_fixed_task_price_is_visible", dialog.get_by_text(re.compile(r"Стоимость задачи фиксирована:\s*99\s*₽ за подбор выбранных позиций независимо от их количества")).is_visible())
    record("exact_has_no_per_position_price", "за позицию" not in dialog.inner_text())
    record("select_all_is_disabled_above_maximum", not dialog.get_by_role("button", name="Выбрать все", exact=True).is_enabled())
    dialog.get_by_role("button", name="Выбрать категорию", exact=True).first.click()
    record("category_selects_its_three_explicit_rows", dialog.get_by_role("checkbox").evaluate_all("els => els.filter(el => el.checked).length") == 3)
    dialog.get_by_role("button", name="Выбрать категорию", exact=True).last.click()
    record("oversized_category_is_explained_without_hidden_truncation", dialog.get_by_role("alert").get_by_text(re.compile(r"превысит лимит 5")).is_visible())
    for index in (3, 4):
        dialog.get_by_role("checkbox").nth(index).check()
    record("five_positions_can_be_selected", dialog.get_by_role("checkbox").evaluate_all("els => els.filter(el => el.checked).length") == 5)
    dialog.get_by_role("checkbox").nth(5).click(force=True)
    record("sixth_position_is_rejected_inline", dialog.get_by_role("alert").get_by_text("Можно выбрать не более 5 позиций.", exact=True).is_visible())
    dialog.get_by_role("button", name="Подтвердить выбор", exact=True).click()
    page.wait_for_timeout(250)
    exact_mutation = next(item for item in mutations if item["path"].endswith("/exact-selection"))
    record("confirmation_uses_csrf", exact_mutation["csrf"] == "FIXTURE-CSRF-NOT-A-REAL-SECRET")
    record("confirmation_sends_revision", exact_mutation["payload"]["revision"] == "fixture-revision-1")
    record("confirmation_sends_only_five_explicit_ids", exact_mutation["payload"]["selected_item_ids"] == [f"position-{number}" for number in range(1, 6)])
    jobs[0] = {
        **jobs[0],
        "status": "completed",
        "status_label": "Готово",
        "progress": 100,
        "has_result": True,
        "exact_product_positions": [{
            "id": "position-1", "position_no": 1, "name": "Позиция 1",
            "status": "Не удалось подтвердить модель", "error": "Недостаточно данных для сопоставления",
            "can_retry_position": True,
        }],
    }
    page.reload(wait_until="networkidle")
    page.get_by_text("Результаты по позициям", exact=True).click()
    page.get_by_role("button", name="Новый подбор", exact=True).click()
    page.wait_for_timeout(200)
    retry_mutation = next(item for item in mutations if item["path"].endswith("/exact-selection/retry"))
    record("position_retry_uses_dedicated_endpoint", retry_mutation["method"] == "POST")
    record("position_retry_keeps_revision", retry_mutation["payload"]["revision"] == "fixture-revision-1")
    record("position_retry_sends_one_explicit_id", retry_mutation["payload"]["selected_item_ids"] == ["position-1"])
    record("position_retry_creates_new_confirmation", page.get_by_role("dialog", name="Выберите позиции").is_visible())

    jobs[:] = [price_monitoring_job("fixture-monitoring")]
    session["user"]["allowed_price_monitoring"] = True
    page.goto(base + "/cabinet?scenario=price_monitoring", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    monitoring_dialog = page.get_by_role("dialog", name="Выберите позиции")
    monitoring_dialog.wait_for()
    monitoring_text = monitoring_dialog.inner_text()
    record("monitoring_all_eight_rows_are_visible", monitoring_dialog.get_by_role("checkbox").count() == 8)
    record("monitoring_select_all_is_available_within_limit", monitoring_dialog.get_by_role("button", name="Выбрать все", exact=True).is_enabled())
    record("monitoring_requirements_are_human_readable", "Диаметр: 100 мм" in monitoring_text and "Материал: Сталь 20" in monitoring_text)
    record("monitoring_internal_requirement_keys_are_hidden", "param_name" not in monitoring_text and "tz_requirement" not in monitoring_text)
    record("monitoring_per_position_price_and_maximum_are_visible", bool(re.search(r"50\s*₽ за позицию с найденной ценой", monitoring_text)) and bool(re.search(r"Максимальная сумма при выборе 8 позиций:\s*400\s*₽", monitoring_text)))
    monitoring_dialog.get_by_role("button", name="Выбрать все", exact=True).click()
    monitoring_dialog.get_by_role("button", name="Подтвердить выбор", exact=True).click()
    page.wait_for_timeout(250)
    monitoring_mutation = next(item for item in mutations if item["path"].endswith("/position-selection"))
    record("monitoring_uses_position_selection_endpoint", monitoring_mutation["method"] == "POST")
    record("monitoring_sends_all_explicit_source_position_ids", monitoring_mutation["payload"] == {"revision": "monitoring-revision-1", "selected_item_ids": ["source-position-11", *[f"position-{number}" for number in range(12, 19)]]})
    jobs[:] = [{**exact_job("fixture-supplier"), "mode": "supplier_search", "mode_label": "Поиск поставщиков", "status": "awaiting_customer_confirmation", "awaiting_customer_confirmation": True, "confirmation_kind": "multi_item_strategy", "exact_product_selection": None, "multi_item_details": {"items": [
        {"id": "panels", "name": "Панели", "included_sub_items": ["Стеновая 100", "Стеновая 50", "Кровельная"]},
        {"id": "accessories", "name": "Комплектующие", "included_sub_items": ["Саморез 140", "Саморез 95", "Уголок внутренний", "Уголок наружный", "Фасонный элемент"]}
    ], "total_items": 2}}]
    page.reload(wait_until="networkidle")
    strategy_dialog = page.get_by_role("dialog")
    strategy_dialog.wait_for()
    record("supplier_strategy_counts_two_categories_and_eight_rows", bool(re.search(r"2 категории\s*/\s*8 товарных строк", strategy_dialog.inner_text())))
    jobs[0].update(status="cancelled", awaiting_customer_confirmation=False)
    page.reload(wait_until="networkidle")
    record("supplier_card_distinguishes_categories_from_rows", bool(re.search(r"Категорий:\s*2.*Товарных строк:\s*8", page.locator("body").inner_text(), re.S)))
    record("no_runtime_errors", not runtime_errors)
    browser.close()

report = {"status": "passed", "checks": checks, "mutations": mutations, "boundary": "Every API was intercepted; no account, paid task, or external request was used."}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False))
