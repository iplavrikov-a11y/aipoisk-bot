"""Admin source-row choice with synthetic API; no real admin operations."""
import asyncio, json, os
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright
from test_admin_navigation_browser import payload

BASE=os.environ.get('ADMIN_QA_BASE_URL','http://127.0.0.1:3197/')
OUT=Path(os.environ.get('ADMIN_QA_OUTPUT','/tmp/tenderlex-admin-exact-selection.json'))

async def main():
    rows=[{'id':f'row-{i}','position_no':i,'name':f'Клапан {i}'} for i in range(1,13)]
    selection={'revision':'fixture-only','items':rows,'selected_ids':[],'max_positions':5,'price_kopeks':9900,'confirmed':False}
    job={'id':'fixture-exact','job_number':999,'client_id':'fixture-client','client_name':'Тестовый клиент','mode':'exact_product',
        'mode_label':'Подбор товара и аналогов','status':'awaiting_exact_selection','title':'Проверка выбора товаров','human_title':'Проверка выбора товаров',
        'created_at':'2026-10-22T06:00:00Z','progress':25,'message':'Выберите товары','exact_product_selection':selection,
        'result_files':[],'admin_reruns':[],'sources':[],'input_files':[],'verified_count':0,'file_count':1}
    mutations=[]; errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        page=await browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda e: errors.append(str(e)))
        async def intercept(route):
            r=route.request; u=urlsplit(r.url)
            if u.netloc!=urlsplit(BASE).netloc: await route.abort(); return
            if not u.path.startswith('/api/'): await route.continue_(); return
            if r.method not in ('GET','HEAD'):
                assert u.path=='/api/jobs/fixture-exact/exact-selection',u.path
                mutations.append(r.post_data_json)
                job['status']='running'
                data={'ok':True,'job':job}
            else:
                data=[job] if u.path=='/api/jobs' else payload(u.path+('?'+u.query if u.query else ''))
            await route.fulfill(status=200,content_type='application/json',body=json.dumps(data))
        await page.route('**/*',intercept)
        await page.goto(BASE,wait_until='networkidle')
        await page.locator('a[href="#jobs"]').click()
        panel=page.get_by_role('region',name='Выбор товаров для подбора')
        await panel.wait_for()
        assert await panel.get_by_role('checkbox').count()==12
        submit=panel.get_by_role('button',name='Подтвердить выбор товаров')
        assert not await submit.is_enabled()
        for index in range(5): await panel.get_by_role('checkbox').nth(index).check()
        assert not await panel.get_by_role('checkbox').nth(5).is_enabled()
        for index in range(5): await panel.get_by_role('checkbox').nth(index).uncheck()
        await panel.get_by_role('checkbox').nth(1).check()
        await panel.get_by_role('checkbox').nth(8).check()
        await submit.click()
        await page.wait_for_timeout(300)
        assert mutations==[{'revision':'fixture-only','selected_item_ids':['row-2','row-9']}]
        assert not errors,errors
        await browser.close()
    report={'status':'passed','checks':['all12 source rows visible','empty selection blocked','max5 enforced','source2and9 selected','revision and IDs sent','no runtime errors'], 'mutations':mutations,'boundary':'Every API intercepted; no paid or real admin operations.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)); print(json.dumps(report,ensure_ascii=False))

asyncio.run(main())
