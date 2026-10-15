#!/usr/bin/env python3
"""E2E Playwright test suite for TenderLex tariffs and top-up bonus system."""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output" / "playwright"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:3093")

def run_e2e_tests():
    print(f"[E2E] Starting tests against {SITE_URL}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/bin/google-chrome",
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )

        # ---------------------------------------------------------
        # TEST 1: Public Landing Page (#pricing)
        # ---------------------------------------------------------
        print("[E2E] 1. Testing Landing Page Pricing Section...")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(f"{SITE_URL}/#pricing", wait_until="networkidle", timeout=30000)
        page.wait_for_selector("#pricing", timeout=10000)

        # Verify heading
        pricing_heading = page.locator("#pricing h2").inner_text()
        print(f"      Pricing Heading: {pricing_heading}")
        assert "Тарифы" in pricing_heading or "баланс" in pricing_heading.lower(), f"Unexpected heading: {pricing_heading}"

        # Verify flat function chips
        content = page.content()
        assert "99 ₽" in content, "Flat rate 99 ₽ not found on landing page"
        assert "198 ₽" in content, "Combo rate 198 ₽ not found on landing page"
        assert "Поиск поставщиков" in content, "Поиск поставщиков not found"
        assert "Подбор товара и аналогов" in content, "Подбор товара и аналогов not found"
        assert "Анализ документации" in content, "Анализ документации not found"

        # Verify package tiers
        assert "Старт" in content, "Package 'Старт' not found"
        assert "Оптимальный" in content, "Package 'Оптимальный' not found"
        assert "Про" in content, "Package 'Про' not found"
        assert "Бизнес" in content, "Package 'Бизнес' not found"
        assert "Корпоративный" in content or "КОРПОРАТИВНЫЙ" in content or "корпоративный" in content.lower(), "Package 'Корпоративный' not found"

        # Verify bonus indicators with normalized whitespace
        clean_text = " ".join(content.replace("\u00a0", " ").replace("&nbsp;", " ").split())
        assert "500 ₽ бонус" in clean_text or ("500" in clean_text and "бонус" in clean_text), "Bonus 500 ₽ not found"
        assert "1 500 ₽ бонус" in clean_text or ("1 500" in clean_text and "бонус" in clean_text), "Bonus 1 500 ₽ not found"
        assert "4 000 ₽ бонус" in clean_text or ("4 000" in clean_text and "бонус" in clean_text), "Bonus 4 000 ₽ not found"
        assert "+50% к балансу" in clean_text or "37 500" in clean_text, "Corporate bonus +50% or 37 500 ₽ not found"

        # Capture landing screenshot
        screenshot_landing = OUTPUT_DIR / "tariffs_landing.png"
        page.screenshot(path=str(screenshot_landing), full_page=False)
        print(f"      Screenshot saved: {screenshot_landing}")

        context.close()

        # ---------------------------------------------------------
        # TEST 2: Cabinet Balance & Top-up Modal
        # ---------------------------------------------------------
        print("[E2E] 2. Testing Cabinet Client Balance & Top-up Modal...")
        context = browser.new_context(viewport={"width": 1440, "height": 900})

        # Intercept customer session to simulate an authenticated client with 1 200 ₽ balance
        mock_session = {
            "authenticated": True,
            "csrf_token": "mock-csrf-token",
            "user": {
                "email": "procurement_lead@example.com",
                "name": "Иван Смирнов",
                "is_trial": False,
                "is_email_verified": True
            },
            "balance": {
                "supplier_search": {"label": "Поиск поставщиков", "available": 12, "reserved": 0, "spent": 5, "granted": 17, "low": False, "price_rub": 99},
                "procurement_report": {"label": "Анализ закупки", "available": 12, "reserved": 0, "spent": 3, "granted": 15, "low": False, "price_rub": 99},
                "supplier_search_extra": {"label": "Добор поставщиков", "available": 12, "reserved": 0, "spent": 0, "granted": 12, "low": False, "price_rub": 49},
                "money": {
                    "balance_kopeks": 120000,
                    "reserved_kopeks": 0,
                    "available_kopeks": 120000,
                    "balance_rub": 1200,
                    "reserved_rub": 0,
                    "available_rub": 1200
                },
                "effective_prices": {
                    "supplier_search": {"label": "Поиск поставщиков", "price_kopeks": 9900, "price_rub": 99, "enabled": True, "source": "tariff"},
                    "supplier_search_extra": {"label": "Добор поставщиков", "price_kopeks": 4900, "price_rub": 49, "enabled": True, "source": "tariff"},
                    "procurement_report": {"label": "Анализ закупки", "price_kopeks": 9900, "price_rub": 99, "enabled": True, "source": "tariff"},
                    "exact_product": {"label": "Подбор точного товара", "price_kopeks": 9900, "price_rub": 99, "enabled": True, "source": "tariff"}
                }
            },
            "limits": {"max_upload_mb": 50, "max_files_per_batch": 20, "default_supplier_target": 10},
            "deposit_packages": [
                {"id": "dep-1000", "kind": "deposit", "name": "Старт", "units": 10, "price_kopeks": 100000, "price_rub": 1000, "bonus_kopeks": 0, "bonus_rub": 0, "total_kopeks": 100000, "total_rub": 1000, "credit_rub": 1000, "badge": "", "approx_tasks": 10},
                {"id": "dep-3000", "kind": "deposit", "name": "Оптимальный", "units": 35, "price_kopeks": 300000, "price_rub": 3000, "bonus_kopeks": 50000, "bonus_rub": 500, "total_kopeks": 350000, "total_rub": 3500, "credit_rub": 3500, "badge": "+500 ₽", "approx_tasks": 35},
                {"id": "dep-5000", "kind": "deposit", "name": "Про", "units": 65, "price_kopeks": 500000, "price_rub": 5000, "bonus_kopeks": 150000, "bonus_rub": 1500, "total_kopeks": 650000, "total_rub": 6500, "credit_rub": 6500, "badge": "Хит", "approx_tasks": 65},
                {"id": "dep-10000", "kind": "deposit", "name": "Бизнес", "units": 140, "price_kopeks": 1000000, "price_rub": 10000, "bonus_kopeks": 400000, "bonus_rub": 4000, "total_kopeks": 1400000, "total_rub": 14000, "credit_rub": 14000, "badge": "+4 000 ₽", "approx_tasks": 140},
                {"id": "dep-25000", "kind": "deposit", "name": "Корпоративный", "units": 375, "price_kopeks": 2500000, "price_rub": 25000, "bonus_kopeks": 1250000, "bonus_rub": 12500, "total_kopeks": 3750000, "total_rub": 37500, "credit_rub": 37500, "badge": "+12 500 ₽", "approx_tasks": 375}
            ],
            "function_prices": {
                "supplier_search": {"price_kopeks": 9900, "price_rub": 99},
                "supplier_search_extra": {"price_kopeks": 4900, "price_rub": 49},
                "procurement_report": {"price_kopeks": 9900, "price_rub": 99},
                "exact_product": {"price_kopeks": 9900, "price_rub": 99},
                "analysis_and_suppliers": {"price_kopeks": 19800, "price_rub": 198}
            },
            "contacts": {
                "email": "info@tenderlex.ru",
                "telegram": "@lexelence",
                "telegram_url": "https://t.me/lexelence"
            },
            "payment": {
                "provider": "manual",
                "instructions": "Перевод на карту"
            }
        }

        def intercept_session(route):
            url = route.request.url
            if "/api/customer/auth/session" in url or "/api/customer/session" in url or "/api/customer/me" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_session))
            elif "/api/customer/jobs" in url:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"items": [], "total": 0, "limit": 15, "offset": 0}))
            else:
                route.continue_()

        context.route("**/api/customer/**", intercept_session)
        page = context.new_page()

        page.goto(f"{SITE_URL}/cabinet", wait_until="networkidle", timeout=30000)

        # Verify Interactive Balance Button (acts as Top-Up trigger)
        balance_btn = page.locator("button:has-text('Баланс')").first
        assert balance_btn.is_visible(), "Balance button not visible in cabinet header"
        balance_text = balance_btn.inner_text()
        print(f"      Balance button displayed: {balance_text}")
        clean_balance = balance_text.replace("\u00a0", " ")
        assert "1 200" in clean_balance, f"Balance mismatch: {balance_text}"

        screenshot_header = OUTPUT_DIR / "cabinet_header_clean.png"
        page.screenshot(path=str(screenshot_header), full_page=False)
        print(f"      Screenshot saved: {screenshot_header}")

        # Test Tariffs Collapsible Box
        tariffs_btn = page.locator("button:has-text('Тарифы')").first
        tariffs_btn.click()
        page.wait_for_timeout(500)

        cab_content = page.content()
        assert "Списание за задачи с баланса" in cab_content, "Tariff breakdown missing operations table"
        assert "Бонусы при пополнении баланса" in cab_content, "Tariff breakdown missing bonus tiers"
        print("      Collapsible tariffs box verified.")

        # Click Balance Button to open Top-Up Modal
        balance_btn.click()
        page.wait_for_selector("#topup-modal-title", timeout=5000)
        modal_title = page.locator("#topup-modal-title").inner_text()
        print(f"      Modal Title: {modal_title}")
        assert "Пополнение баланса" in modal_title, f"Unexpected modal title: {modal_title}"

        # Verify package options in modal
        modal_content = page.locator("section[aria-labelledby='topup-modal-title']").inner_text()
        assert "Старт" in modal_content, "Package Старт missing in modal"
        assert "Оптимальный" in modal_content, "Package Оптимальный missing in modal"
        assert "Про" in modal_content, "Package Про missing in modal"
        assert "Бизнес" in modal_content, "Package Бизнес missing in modal"
        assert "Корпоративный" in modal_content, "Package Корпоративный missing in modal"

        # Verify live calculation
        assert "Поступит на баланс:" in modal_content, "Calculation missing from modal"
        assert "Инструкция по оплате переводом:" in modal_content, "Transfer instructions missing"
        assert "procurement_lead@example.com" in modal_content, "User email missing in transfer box"

        # Test clicking package «Бизнес» (10 000 ₽)
        biz_card = page.locator("button:has-text('Бизнес')")
        biz_card.click()
        page.wait_for_timeout(300)

        updated_modal_text = page.locator("section[aria-labelledby='topup-modal-title']").inner_text()
        clean_modal = updated_modal_text.replace("\u00a0", " ")
        assert "10 000 ₽" in clean_modal, f"10 000 ₽ not updated in calculation: {clean_modal}"
        assert "+4 000 ₽" in clean_modal, f"+4 000 ₽ bonus not updated: {clean_modal}"
        assert "14 000 ₽" in clean_modal, f"14 000 ₽ total credited not updated: {clean_modal}"
        print("      Package selection and calculation reactivity verified (10k -> 14k).")

        # Capture modal screenshot
        screenshot_modal = OUTPUT_DIR / "cabinet_topup_modal.png"
        page.screenshot(path=str(screenshot_modal), full_page=False)
        print(f"      Screenshot saved: {screenshot_modal}")

        context.close()
        browser.close()

    print("[E2E] ALL PLAYWRIGHT E2E TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_e2e_tests()
