#!/usr/bin/env python3
"""Check sticky navigation and short-phone menu reachability, without mutations."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', default='http://127.0.0.1:3098')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
base = args.base.rstrip('/')
checks = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    context.add_init_script("localStorage.setItem('tenderlex_analytics_consent','denied');")
    def safe_route(route):
        if route.request.method not in ['GET', 'HEAD'] or urlparse(route.request.url).netloc != urlparse(base).netloc:
            route.abort()
        else:
            route.continue_()
    context.route('**/*', safe_route)
    page = context.new_page()
    for path in ['/', '/baza-znaniy/kak-naiti-postavshchika-po-tz', '/otrasli/metalloprokat', '/regiony/moskva', '/poisk-postavshchikov-po-tz']:
        page.goto(base+path, wait_until='networkidle')
        page.evaluate('window.scrollTo(0, 1200)')
        page.wait_for_timeout(150)
        top = page.locator('.tl-site-header').bounding_box()['y']
        assert abs(top) <= 1, (path, top)
        checks.append({'check': 'sticky header', 'path': path, 'top': top})
    page.set_viewport_size({'width': 375, 'height': 644})
    page.goto(base, wait_until='networkidle')
    menu = page.locator('.tl-site-header__mobile')
    menu.locator('summary').click()
    nav = menu.locator('nav')
    assert nav.evaluate('(e) => e.scrollHeight > e.clientHeight'), 'short phone menu must scroll internally'
    cabinet = nav.locator('a[href="/cabinet"]')
    cabinet.scroll_into_view_if_needed()
    box = cabinet.bounding_box()
    assert 0 <= box['y'] < box['y']+box['height'] <= 644, box
    checks.append({'check': 'last mobile action reachable', 'viewport': '375x644', 'bounds': box})
    cabinet.click()
    page.wait_for_url('**/cabinet')
    checks.append({'check': 'mobile cabinet link navigates'})
    page.goto(base, wait_until='networkidle')
    menu.locator('summary').click()
    page.keyboard.press('Escape')
    assert not menu.evaluate('(e) => e.open'), 'Escape closes the mobile menu'
    checks.append({'check': 'Escape closes mobile menu'})
    page.screenshot(path=str(args.output.with_suffix('.png')))
    browser.close()

report = {'status': 'passed', 'checks': checks}
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False))
