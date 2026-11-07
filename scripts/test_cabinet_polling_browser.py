#!/usr/bin/env python3
"""Hold a background history response while the customer changes pages.

All APIs are synthetic. Poll timers are accelerated; real tasks, payments and
account mutations are blocked. Verifies usability during refresh and stale data.
"""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',default='http://127.0.0.1:3098')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
base=args.base.rstrip('/')

def task(page):
    return dict(id=f'fixture-page-{page}',job_number=page,mode='supplier_search',mode_label='Поиск поставщиков',
        human_title=f'Страница {page}: тестовая спецификация',supplier_search_policy='normal',multi_item_mode='balanced',
        status='completed',status_label='Готово',progress=100,message='Результат готов',target_suppliers=10,
        verified_count=8,file_count=0,has_result=False,can_download=False,can_cancel=False,can_find_more_suppliers=False,
        awaiting_customer_confirmation=False,created_at='2026-10-19T07:00:00Z',updated_at='2026-10-19T07:01:00Z',
        completed_at='2026-10-19T07:01:00Z',result_files=[])

async def main():
    checks={}
    errors=[]
    mutations=[]
    first_poll=asyncio.Event()
    release_poll=asyncio.Event()
    queries=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
        context=await browser.new_context(viewport={'width':1440,'height':1000})
        await context.add_init_script("""localStorage.setItem('tenderlex_analytics_consent','denied');
          const original=window.setInterval;
          window.setInterval=(fn,delay,...rest)=>original(fn,delay===7000||delay===3000?600:delay,...rest);""")
        page=await context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        session={'authenticated':True,'csrf_token':'SYNTHETIC-NOT-A-REAL-TOKEN',
            'user':{'email':'qa@example.invalid','is_trial':False,'is_email_verified':True,'allowed_geo_radius':False,'allowed_price_monitoring':False},
            'balance':{'money':{'available_kopeks':350000,'balance_kopeks':350000,'reserved_kopeks':0}},
            'limits':{'max_files_per_batch':10,'max_upload_mb':120,'default_supplier_target':10},
            'tariff_groups':{},'deposit_packages':[],'contacts':{},'payment':{},'referral':{}}
        async def intercept(route):
            request=route.request
            url=urlparse(request.url)
            if request.method not in ['GET','HEAD']:
                mutations.append(url.path)
                await route.abort();return
            if url.netloc!=urlparse(base).netloc:
                await route.abort();return
            if not url.path.startswith('/api/'):
                await route.continue_();return
            payload={}
            if url.path=='/api/customer/auth/session':payload=session
            elif url.path=='/api/customer/jobs':
                params=parse_qs(url.query)
                offset=int(params.get('offset',['0'])[0])
                queries.append(offset)
                if len(queries)==2 and offset==0:
                    first_poll.set()
                    await release_poll.wait()
                current=offset//15+1
                payload={'items':[task(current)],'total':45,'limit':15,'offset':offset}
            elif url.path.startswith('/api/chat/'):
                payload={'messages':[],'ok':True}
            await route.fulfill(status=200,content_type='application/json',body=json.dumps(payload,ensure_ascii=False))
        await context.route('**/*',intercept)
        await page.goto(base+'/cabinet',wait_until='domcontentloaded')
        await page.get_by_text('Страница 1: тестовая спецификация',exact=True).wait_for()
        await asyncio.wait_for(first_poll.wait(),timeout=10)
        await page.wait_for_timeout(100)
        forward=page.get_by_role('button',name='Вперёд',exact=True).first
        checks['forward_stays_enabled_during_background_refresh']=await forward.is_enabled()
        if checks['forward_stays_enabled_during_background_refresh']:
            await page.wait_for_timeout(1300)
            checks['slow_background_refresh_does_not_overlap']=len(queries)==2
            await forward.click()
            await page.get_by_text('Страница 2: тестовая спецификация',exact=True).wait_for(timeout=5000)
            checks['page_navigation_works_while_poll_pending']=15 in queries
            release_poll.set()
            await page.wait_for_timeout(300)
            checks['late_old_poll_cannot_replace_new_page']=await page.get_by_text('Страница 2: тестовая спецификация',exact=True).count()==1 and await page.get_by_text('Страница 1: тестовая спецификация',exact=True).count()==0
            checks['both_paginators_show_current_page']=await page.get_by_text('Страница 2 из 3',exact=True).count()==2
        else:
            release_poll.set()
        checks['no_mutations']=not mutations
        checks['no_runtime_errors']=not errors
        await browser.close()
    report={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'queries':queries,'runtimeErrors':errors,'boundary':'Every API intercepted; poll600ms, held response, no customer mutations.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))
    assert all(checks.values()),'History polling usability regression'

asyncio.run(main())
