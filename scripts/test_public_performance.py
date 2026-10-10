#!/usr/bin/env python3
"""Capture a small synthetic public-page performance snapshot without analytics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, Route, sync_playwright


def block_nonessential(route: Route) -> None:
    url = route.request.url.lower()
    if any(part in url for part in ("mc.yandex", "metrika", "google-analytics", "googletagmanager")):
        route.abort()
        return
    route.continue_()


def install_metrics(page: Page) -> None:
    page.add_init_script(
        """
        window.__tenderlexPerf = { lcp: null, cls: 0 };
        new PerformanceObserver((entries) => {
          const entriesList = entries.getEntries();
          const last = entriesList[entriesList.length - 1];
          if (last) window.__tenderlexPerf.lcp = last.startTime;
        }).observe({ type: 'largest-contentful-paint', buffered: true });
        new PerformanceObserver((entries) => {
          for (const entry of entries.getEntries()) {
            if (!entry.hadRecentInput) window.__tenderlexPerf.cls += entry.value;
          }
        }).observe({ type: 'layout-shift', buffered: true });
        """
    )


def measure(browser: Browser, url: str) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
    context.route("**/*", block_nonessential)
    page = context.new_page()
    install_metrics(page)
    client = context.new_cdp_session(page)
    client.send("Network.enable")
    client.send(
        "Network.emulateNetworkConditions",
        {"offline": False, "latency": 150, "downloadThroughput": 200_000, "uploadThroughput": 200_000},
    )
    client.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    response = page.goto(url, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(500)
    entries = page.evaluate("performance.getEntriesByType('resource')")
    navigation = page.evaluate("performance.getEntriesByType('navigation')[0]")
    metrics = page.evaluate("window.__tenderlexPerf")
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    context.close()
    return {
        "url": url,
        "status": response.status if response else None,
        "lcpMs": round(metrics["lcp"], 1) if metrics["lcp"] is not None else None,
        "cls": round(metrics["cls"], 4),
        "overflow": overflow,
        "ttfbMs": round(navigation["responseStart"], 1) if navigation else None,
        "domContentLoadedMs": round(navigation["domContentLoadedEventEnd"], 1) if navigation else None,
        "scriptTransferBytes": sum(
            item.get("transferSize", 0)
            for item in entries
            if item.get("initiatorType") == "script"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://tenderlex.ru/")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        result = {
            "kind": "synthetic_lab",
            "conditions": {"viewport": "390x844", "cpuSlowdown": 4, "downloadBytesPerSecond": 200_000, "latencyMs": 150},
            "limitations": "One synthetic run; this is not field CWV, INP data, or a ranking prediction. Analytics is blocked and no customer task is started.",
            "page": measure(browser, args.url),
        }
        browser.close()
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
