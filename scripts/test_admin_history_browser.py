#!/usr/bin/env python3
"""A late initial 100-job response must not replace the full Jobs history.

Every API is synthetic; external traffic and mutations are blocked.
"""
import asyncio
import json
import os
from urllib.parse import urlsplit, parse_qs
from playwright.async_api import async_playwright
from test_admin_navigation_browser import payload

BASE = os.environ.get('ADMIN_QA_BASE_URL', 'https://admin.tenderlex.ru/')

async def main():
    pending = asyncio.Event()
    release = asyncio.Event()
    errors = []
    mutations = []
    sentinel = {
        'id': 'qa-full-history', 'job_number': 9001, 'client_id': 'qa-client', 'client_name': 'Тест',
        'telegram_id': '', 'created_by_telegram_id': 'web:fixture', 'mode': 'supplier_search',
        'mode_label': 'Поиск поставщиков', 'supplier_search_policy': 'normal',
        'supplier_search_run_type': 'initial', 'status': 'completed', 'progress': 100,
        'message': '', 'title': 'Запись полной истории', 'human_title': 'Запись полной истории',
        'is_internal': False, 'supplier_units': 1, 'procurement_report_units': 0,
        'target_suppliers': 10, 'verified_count': 0, 'file_count': 0, 'has_result': False,
        'result_files': [], 'has_evidence': False, 'error': '',
        'created_at': '2026-10-19T07:00:00Z', 'updated_at': None, 'completed_at': '2026-10-19T07:01:00Z',
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        async def intercept(route):
            r = route.request
            u = urlsplit(r.url)
            if r.method not in ('GET', 'HEAD'):
                mutations.append(u.path)
                await route.abort(); return
            if u.netloc != urlsplit(BASE).netloc:
                await route.abort(); return
            if not u.path.startswith('/api/'):
                await route.continue_(); return
            data = payload(u.path + '?' + u.query)
            if u.path == '/api/jobs':
                limit = parse_qs(u.query).get('limit', [''])[0]
                if limit == '100':
                    pending.set()
                    await release.wait()
                    data = []
                elif limit == '2000':
                    data = [sentinel]
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
        await page.route('**/*', intercept)
        await page.goto(BASE, wait_until='domcontentloaded')
        await asyncio.wait_for(pending.wait(), 10)
        await page.locator('a[href="#jobs"]').click()
        row = page.get_by_role('heading', name='Запись полной истории', exact=True)
        await row.wait_for()
        release.set()
        await page.wait_for_timeout(300)
        checks = {'late_short_list_does_not_replace_full_history': await row.count() == 1,
                  'no_mutations': not mutations, 'no_runtime_errors': not errors}
        print(json.dumps({'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
                          'runtime_errors': errors, 'boundary': 'All API synthetic; held initial100 then full2000.'}, ensure_ascii=False))
        await browser.close()
        assert all(checks.values())

asyncio.run(main())
