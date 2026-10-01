#!/usr/bin/env python3
"""Render the built SEO admin with mocked APIs; no production calls or login."""
import json
import mimetypes
import re
from urllib.parse import urlparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / '.agent/tasks/2026-09-30-seo-repair/raw'
snapshot = json.loads((RAW / 'snapshot-after.json').read_text())
checks = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    for mode in ['available', 'unavailable']:
        fixture = json.loads(json.dumps(snapshot))
        if mode == 'unavailable':
            for key in ['visits', 'users', 'pageviews', 'avg_duration_seconds', 'bounce_rate']:
                fixture['metrika'][key] = None
            fixture['metrika']['error'] = 'TEST unavailable source'
            fixture['google']['status'] = 'unavailable'
            fixture['google']['query_sample']['status'] = 'unavailable'
            fixture['google']['top_queries'] = []
            fixture['metrika']['goals'] = [{'id': 123, 'name': 'Unknown goal metric', 'type': 'action', 'reaches': None}]
            fixture['google']['errors'] = ['TEST unavailable source']
            fixture['google']['property_totals'] = dict.fromkeys(fixture['google']['property_totals'])
            for key in ['total_impressions', 'total_clicks', 'avg_position', 'avg_ctr_percent']:
                fixture['google'][key] = None
            fixture['webmaster']['sqi'] = None
            fixture['webmaster']['searchable_pages'] = None
            fixture['webmaster']['excluded_pages'] = None
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        def intercept(route):
            path = urlparse(route.request.url).path
            if path.startswith('/api/'):
                if path == '/api/seo-analytics': data = fixture
                elif path == '/api/auth/session': data = {'ok': True}
                elif path == '/api/dashboard': data = dict.fromkeys(['clients', 'active_clients', 'jobs', 'running_jobs', 'completed_jobs', 'failed_jobs', 'suppliers'], 0)
                elif path == '/api/settings': data = {'settings': {}}
                elif path.startswith('/api/ops/'): data = None
                elif path.startswith('/api/analytics/'): data = None
                else: data = []
                route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
            elif path.startswith('/assets/'):
                asset = ROOT / 'frontend/dist' / path.lstrip('/')
                route.fulfill(status=200, content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream', body=asset.read_bytes())
            elif path in ['/', '/index.html']:
                route.fulfill(status=200, content_type='text/html', body=(ROOT / 'frontend/dist/index.html').read_text())
            else: route.fulfill(status=404, body='')
        context.route('**/*', intercept)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://tenderlex.test/#seo', wait_until='networkidle')
        assert not errors, errors
        page.get_by_text('Основная конверсия', exact=True).wait_for(timeout=5000)
        page.get_by_text('несопоставимые показатели не суммируются', exact=False).wait_for()
        text = page.inner_text('body')
        assert not errors, errors
        assert '26.83%' not in text
        assert '01.10.2026' in text
        if mode == 'available':
            assert '895' in text and '9' in text
        else:
            assert 'Данные недоступны' in text and 'TEST unavailable source' in text
            assert '— действий' in page.get_by_text('Unknown goal metric', exact=True).locator('../..').inner_text()
        page.get_by_role('button', name=re.compile(r'Google \(')).click()
        assert not errors, errors
        checks.append({'check': f'admin_{mode}_nullable_and_separate_periods', 'status': 'passed'})
        if mode == 'available': page.screenshot(path=str(RAW / 'admin-seo.png'), full_page=True)
        context.close()
    browser.close()
(RAW / 'browser-admin.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2))
print(json.dumps({'status': 'passed', 'checks': checks}, ensure_ascii=False))
