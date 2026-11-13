#!/usr/bin/env python3
"""Render every sitemap page on phone and desktop, without external analytics."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

from playwright.async_api import async_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', default='http://127.0.0.1:3098')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
base = args.base.rstrip('/')


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        for width in [375, 1440]:
            context = await browser.new_context(viewport={'width': width, 'height': 1000})
            await context.add_init_script("localStorage.setItem('tenderlex_analytics_consent','denied');")
            async def safe_route(route):
                request = route.request
                if request.method not in ['GET', 'HEAD'] or urlparse(request.url).netloc != urlparse(base).netloc:
                    await route.abort()
                elif '/api/chat/' in request.url:
                    await route.fulfill(status=200, content_type='application/json', body='{"messages":[]}')
                else:
                    await route.continue_()
            await context.route('**/*', safe_route)
            response = await context.request.get(base+'/sitemap.xml')
            xml = ElementTree.fromstring(await response.text())
            urls = [node.text for node in xml.iter() if node.tag.endswith('}loc')]
            sem = asyncio.Semaphore(2)
            async def inspect(index, url):
                async with sem:
                    page = await context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    path = urlparse(url).path or '/'
                    row = {'url': url, 'width': width}
                    try:
                        response = await page.goto(base+path, wait_until='networkidle', timeout=30000)
                        row.update(status=response.status, title=await page.title(), h1=await page.locator('h1').count(),
                            canonical=await page.locator('link[rel=canonical]').get_attribute('href'),
                            robots=await page.locator('meta[name=robots]').get_attribute('content'),
                            overflow=await page.evaluate('document.documentElement.scrollWidth > innerWidth + 1'),
                            header=await page.locator('.tl-site-header').count(),
                            theme=await page.locator('body.tl-theme').count(), runtimeErrors=errors)
                        if index in [0, 1, 2, 7, 8, 12, 13, 72, 73, 90]:
                            await page.screenshot(path=str(args.output.parent/f'public-{width}-{index}.jpg'), type='jpeg', quality=70, full_page=False)
                    except Exception as error:
                        row['error'] = str(error)[:250]
                    results.append(row)
                    await page.close()
            await asyncio.gather(*(inspect(i, url) for i, url in enumerate(urls)))
            await context.close()
        await browser.close()
    failures = [row for row in results if row.get('status') != 200 or row.get('h1') != 1 or row.get('overflow') or row.get('runtimeErrors') or row.get('theme') != 1 or row.get('header') != 1 or row.get('canonical', '').rstrip('/') != row['url'].rstrip('/') or 'noindex' in row.get('robots', '')]
    report = {'status': 'failed' if failures else 'passed', 'pages': len(results)//2, 'renderChecks': len(results), 'failures': failures, 'results': results}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}, ensure_ascii=False))
    assert not failures, 'Public page browser release gate failed'


args.output.parent.mkdir(parents=True, exist_ok=True)
asyncio.run(main())
