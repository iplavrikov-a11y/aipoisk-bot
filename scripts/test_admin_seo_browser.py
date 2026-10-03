#!/usr/bin/env python3
"""Browser regressions using synthetic data and built assets; no external calls."""
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PERIOD = {'start_date': '2026-09-01', 'end_date': '2026-09-28', 'timezone': 'Europe/Moscow'}
SNAPSHOT = {
    'schema_version': 2, 'updated_at': '2026-10-04T01:00:00+00:00', 'collection_status': 'active',
    'metrika': {'period': PERIOD, 'users': 15, 'visits': 26, 'pageviews': 33, 'bounce_rate': 23.1,
                'avg_duration_seconds': 145, 'sources': [{'name':'Link traffic','visits':1,'users':1}], 'top_pages': [], 'goals': [],
                'primary_conversion': {'status': 'available', 'visits': 0, 'goal_visits': 0,
                 'rate_percent': None, 'reason': 'No visits in the measured registration period.',
                 'period': {'start_date': '2026-10-01', 'end_date': '2026-10-03'},
                 'organic': {'visits': 0, 'goal_visits': 0, 'rate_percent': None}}},
    'webmaster': {'sqi': 10, 'searchable_pages': 60, 'period': PERIOD,
                 'top_queries': [{'text': 'поиск поставщиков', 'shows': 40, 'clicks': 0, 'avg_position': 7}],
                 'daily_dynamics': [{'date': '2026-09-28', 'shows': 40, 'clicks': 0, 'avg_position': 7}]},
    'google': {'status': 'active', 'period': PERIOD, 'totals_status': 'available',
               'property_totals': {'impressions': 892, 'clicks': 11, 'avg_position': 15, 'ctr_percent': 1.23},
               'top_queries': [{'text': 'подбор аналогов', 'impressions': 30, 'clicks': 1, 'position': 15}],
               'daily_dynamics': [{'date': '2026-09-28', 'shows': 34, 'clicks': 1, 'avg_position': 15}]},
    'recommendations': [{'id': 'test', 'status': 'pending', 'title': 'Проверка', 'description': 'Тест'}],
}

checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
    for mode,width in [('available',1440),('mobile',390),('unavailable',1440),('error',1440),('malformed',1440),('recovery',1440),('stale',1440),('unauthorized',1440),('login',1440),('reopen',1440),('network',1440)]:
        fixture=json.loads(json.dumps(SNAPSHOT)); requests=[]; errors=[]
        if mode=='unavailable':
            fixture['metrika']['error']='test source unavailable'
            for key in ['visits','users','pageviews','avg_duration_seconds','bounce_rate']: fixture['metrika'][key]=None
            fixture['google']['status']='unavailable';fixture['google']['property_totals']=dict.fromkeys(fixture['google']['property_totals']);fixture['google']['top_queries']=[];fixture['google']['daily_dynamics']=[]
        if mode=='malformed': fixture={'metrika':None,'webmaster':None,'google':None}
        context=browser.new_context(viewport={'width':width,'height':950})
        def intercept(route):
            path=urlparse(route.request.url).path
            if path.startswith('/api/'):
                if path=='/api/seo-analytics':
                    requests.append(route.request.method)
                    if mode=='network': return route.abort('timedout')
                    status = 503 if mode=='error' or (mode=='recovery' and len(requests)==1) or (mode=='stale' and len(requests)>1) else 401 if mode=='unauthorized' else 200
                    return route.fulfill(status=status,content_type='application/json',body=json.dumps(fixture))
                if path=='/api/auth/session': data={'ok':mode!='login'}
                elif path=='/api/auth/login': data={'ok':True,'username':'test'}
                elif path=='/api/dashboard': data=dict.fromkeys(['clients','active_clients','jobs','running_jobs','completed_jobs','failed_jobs','suppliers'],0)
                elif path=='/api/settings': data={'settings':{}}
                elif path.startswith('/api/ops/') or path.startswith('/api/analytics/'):data=None
                else:data=[]
                route.fulfill(status=200,content_type='application/json',body=json.dumps(data))
            else:
                asset=ROOT/'frontend/dist'/path.lstrip('/') if path.startswith('/assets/') else ROOT/'frontend/dist/index.html'
                route.fulfill(status=200,content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream',body=asset.read_bytes())
        context.route('**/*',intercept); page=context.new_page();page.clock.install();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://tenderlex.test/#seo',wait_until='networkidle')
        if mode=='login':
            page.locator('input').first.fill('test');page.locator('input[type=password]').fill('test');page.get_by_role('button',name='Войти',exact=True).click()
        page.wait_for_timeout(900)
        assert not errors,errors
        if mode=='reopen':
            page.evaluate("location.hash='dashboard'");page.wait_for_timeout(100)
            page.evaluate("location.hash='seo'");page.wait_for_timeout(300)
            assert len(requests)==2,requests
        if mode in ['recovery','stale']:
            page.clock.fast_forward(121000); page.wait_for_timeout(300)
            assert len(requests)==2,requests
        assert page.locator('.seo-overview').count()==1
        assert page.locator('.seo-overview button').count()==0,'SEO must not require action buttons'
        text=page.locator('main').inner_text()
        assert not re.search(r'Согласовать|Отклонить|Согласование владельцем|No visits|Today values|Позиции растут|Снижение позиций',text),text[-1000:]
        if mode in ['available','mobile']:
            assert '892' in text and '11' in text
            assert 'Переходы по ссылкам' in text and 'Link traffic' not in text
            if width==1440:
                assert page.locator('.seo-table-scroll').evaluate_all('(tables)=>tables.every(t=>t.scrollWidth <= t.clientWidth+1)'), 'Desktop SEO columns must be visible without horizontal scrolling'
            assert 'Часть источников не предоставила' not in text
            assert 'В периоде регистрации ещё нет визитов' in text
            assert page.locator('.seo-daily tbody tr').count()==2,'Both source histories render automatically'
        if mode in ['error','stale','network']:
            assert 'Не удалось обновить данные' in text
            assert len(requests)==(2 if mode=='stale' else 1),'No request loop on failure'
        if mode=='recovery': assert '892' in text and 'Не удалось обновить данные' not in text
        if mode=='stale': assert '892' in text, 'Keep last known snapshot during failure'
        if mode=='unavailable': assert 'В выборке 0 видимых фраз' not in text, 'Unavailable query count must not look like zero'
        if mode=='unauthorized': assert 'Сессия завершилась' in text
        assert requests and all(method=='GET' for method in requests)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'page overflow'
        checks.append({'mode':mode,'width':width,'status':'passed'});context.close()
    browser.close()
print(json.dumps({'checks':checks},ensure_ascii=False))
