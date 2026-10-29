#!/usr/bin/env python3
"""Drive the real cabinet UI with synthetic sessions and ALL APIs intercepted.

No account is created, no file is uploaded to the server, and no paid operation
can escape the browser fixture. Run with crawler-env Python / Playwright.
"""
from __future__ import annotations

import argparse
import json
import re
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base", default="http://127.0.0.1:3098")
parser.add_argument("--evidence-dir", type=Path, required=True)
args = parser.parse_args()
base = args.base.rstrip("/")
args.evidence_dir.mkdir(parents=True, exist_ok=True)
checks = []
errors = []


def check(name, condition=True):
    assert condition, name
    checks.append(name)


def job(job_id="fixture-supplier", mode="supplier_search", **changes):
    labels = {"supplier_search": "Поиск поставщиков", "exact_product": "Подбор товара и аналогов", "procurement_report": "Анализ документации", "analysis_and_suppliers": "Анализ + поиск"}
    result = dict(id=job_id, job_number=100, mode=mode, mode_label=labels.get(mode, mode),
        human_title="Спецификация кабельной продукции", supplier_search_policy="normal", multi_item_mode="balanced",
        status="completed", status_label="Готово", progress=100, message="Результат готов",
        target_suppliers=10, verified_count=8, file_count=1, has_result=True, can_download=True,
        can_cancel=False, can_find_more_suppliers=mode=="supplier_search", can_start_supplier_search=mode=="exact_product",
        awaiting_customer_confirmation=False, error="", created_at="2026-10-18T09:00:00Z", updated_at="2026-10-18T09:30:00Z",
        completed_at="2026-10-18T09:30:00Z", result_files=[{"kind":"report", "label":"Отчёт", "filename":"result.docx"}])
    if mode == "exact_product":
        result["exact_product_summary"] = dict(primary_product="Арматура трубопроводная", alternatives=["Клапан Ду100"],total_positions=2)
    if mode == "supplier_search":
        result["result_files"] = [{"kind":"suppliers_excel","label":"Реестр поставщиков","filename":"suppliers.xlsx"},{"kind":"quote_request","label":"Запрос КП","filename":"request.docx"}]
    result.update(changes)
    return result


def form_payload(request):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        try: return request.post_data_json
        except Exception: return {}
    message = BytesParser(policy=default).parsebytes(b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + request.post_data_buffer)
    fields = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if part.get_filename(): fields.setdefault("files", []).append(part.get_filename())
        else: fields[name] = part.get_payload(decode=True).decode('utf-8')
    return fields


def fixture(browser, authenticated=True, jobs=None, flags=True):
    context = browser.new_context(viewport={"width":1440,"height":1000}, accept_downloads=True)
    context.add_init_script("localStorage.setItem('tenderlex_analytics_consent','denied');")
    state = {"authenticated":authenticated,"jobs":jobs or [],"requests":[],"mutations":[],"unhandled":[],"jobs_queries":[]}
    counter = {"label":"Задачи","available":20,"reserved":0,"spent":0,"granted":20,"low":False,"price_rub":99}
    session = {"authenticated":True,"csrf_token":"FIXTURE-CSRF-NOT-A-REAL-SECRET",
        "user":{"email":"qa@example.invalid","name":"Проверка интерфейса","is_trial":False,"is_email_verified":True,"allowed_geo_radius":flags,"allowed_price_monitoring":flags,"geo_radius_surcharge_pct":40},
        "balance":{"supplier_search":counter,"procurement_report":counter,"supplier_search_extra":counter,
            "money":{"balance_kopeks":350000,"available_kopeks":350000,"reserved_kopeks":0,"balance_rub":3500,"available_rub":3500,"reserved_rub":0}},
        "limits":{"max_files_per_batch":10,"max_upload_mb":120,"default_supplier_target":10},
        "tariff_groups":{kind:[{"id":"fixture-"+kind,"kind":kind,"name":"1 задача","units":1,"price_kopeks":9900,"description":"Тестовый тариф"}] for kind in ["supplier_search","exact_product","procurement_report"]},
        "deposit_packages":[
            {"id":"fixture-deposit-1","name":"Старт","price_kopeks":100000,"price_rub":1000,"total_kopeks":100000,"total_rub":1000,"bonus_kopeks":0,"bonus_rub":0},
            {"id":"fixture-deposit-2","name":"Оптимальный","price_kopeks":300000,"price_rub":3000,"total_kopeks":350000,"total_rub":3500,"bonus_kopeks":50000,"bonus_rub":500},
            {"id":"fixture-deposit-3","name":"Про","price_kopeks":500000,"price_rub":5000,"total_kopeks":650000,"total_rub":6500,"bonus_kopeks":150000,"bonus_rub":1500},
            {"id":"fixture-deposit-4","name":"Бизнес","price_kopeks":1000000,"price_rub":10000,"total_kopeks":1400000,"total_rub":14000,"bonus_kopeks":400000,"bonus_rub":4000},
            {"id":"fixture-deposit-5","name":"Корпоративный","price_kopeks":2500000,"price_rub":25000,"total_kopeks":3750000,"total_rub":37500,"bonus_kopeks":1250000,"bonus_rub":12500},
        ],
        "contacts":{"email":"qa@example.invalid","telegram":"@example","telegram_url":"https://t.me/example","max":"","max_url":""},
        "payment":{"provider":"manual","instructions":"Тестовый экран без реального перевода","yookassa_ready":False},
        "referral":{"referral_code":"FIXTURE","invited_count":0,"activated_count":0,"bonus_earned_rub":0,"balance_rub":0,"invite_url_web":"https://example.invalid/","invite_url_bot":"https://example.invalid/"}}

    def route(route):
        request=route.request; url=urlparse(request.url); path=url.path
        if url.netloc != urlparse(base).netloc:
            route.fulfill(status=200,content_type="application/javascript",body="")
            return
        if not path.startswith('/api/'):
            route.continue_(); return
        state['requests'].append({'path':path,'method':request.method})
        if request.method not in ['GET','HEAD']:
            state['mutations'].append({'path':path,'method':request.method,'payload':form_payload(request),'csrf':request.headers.get('x-csrf-token')})
        payload = {}
        if path=='/api/customer/auth/session': payload=session if state['authenticated'] else {'authenticated':False,'csrf_token':'FIXTURE-CSRF'}
        elif path in ['/api/customer/auth/login','/api/customer/auth/register']:
            state['authenticated']=True;payload=session
        elif path=='/api/customer/auth/password-reset/request':payload={'message':'Заявка отправлена'}
        elif path=='/api/customer/auth/logout':state['authenticated']=False;payload={'ok':True}
        elif path=='/api/customer/jobs':
            if request.method=='POST':payload={'batch':False,'count':1}
            else:
                params=parse_qs(url.query);state['jobs_queries'].append(params)
                items=state['jobs']
                if params.get('q'): items=[item for item in items if params['q'][0].lower() in item['human_title'].lower()]
                if params.get('mode'): items=[item for item in items if item['mode']==params['mode'][0]]
                payload={'items':items,'total':len(items),'limit':15,'offset':0}
        elif path=='/api/customer/api-keys':payload={'keys':[]}
        elif path=='/api/customer/billing/transactions':payload={'items':[],'total':0}
        elif path.endswith('/choose-strategy'):
            state['jobs']=[];payload={'ok':True,'message':'Стратегия сохранена'}
        elif path.endswith('/quote-request'):
            payload={'content':'# Запрос коммерческого предложения\nКабель ВВГнг(А)-LS — 5000 м.','filename':'fixture-rfq.docx'}
        elif re.search(r'/download(?:/[^/]+)?$',path):
            route.fulfill(status=200,content_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename=fixture.docx'},body='synthetic fixture');return
        elif any(path.endswith('/'+suffix) for suffix in ['cancel','accept-partial','decline-partial','find-more-suppliers','start-supplier-search']):payload={'ok':True,'message':'Тестовый ответ'}
        elif path.startswith('/api/chat/'):payload={'messages':[],'ok':True}
        else:
            state['unhandled'].append(path)
            route.fulfill(status=400,content_type='application/json',body=json.dumps({'detail':'Blocked by browser fixture'}));return
        route.fulfill(status=200,content_type='application/json',body=json.dumps(payload,ensure_ascii=False))
    context.route('**/*',route)
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
    return context,page,state


def navigate(page, scenario='supplier_search'):
    page.goto(base+'/cabinet?scenario='+scenario,wait_until='networkidle')
    page.locator('#new-job').wait_for()


with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    # Real form handlers serialize the unchanged task contract.
    ctx,page,state=fixture(browser)
    for mode in ['procurement_report','supplier_search','analysis_and_suppliers','exact_product','price_monitoring']:
        navigate(page,mode)
        if mode=='price_monitoring': page.get_by_role('tab',name=re.compile('Мониторинг')).click()
        selected=page.get_by_role('tab',selected=True)
        check(mode+' scenario available',selected.count()==1)
        form=page.locator('form#new-job')
        textarea=form.locator('textarea')
        if textarea.count(): textarea.first.fill('Поставка кабеля ВВГнг(А)-LS 3×2,5 — 5000 м')
        else: form.get_by_role('textbox').first.fill('0173200001424000001')
        if mode=='supplier_search':
            page.get_by_role('button',name=re.compile('Реестр в приоритете')).first.click()
            page.get_by_label(re.compile('Приоритет в радиусе доставки')).check()
            page.get_by_placeholder(re.compile('Каменск')).fill('Екатеринбург')
            page.get_by_placeholder('300',exact=True).fill('500')
            form.locator('input[type=file]').set_input_files({'name':'Спецификация_пример.pdf','mimeType':'application/pdf','buffer':b'synthetic'})
        before=len(state['mutations']);form.locator('button[type=submit]').last.click()
        page.wait_for_timeout(350)
        if len(state['mutations'])==before:
            print('NO_MUTATION',mode,page.locator(':invalid').evaluate_all('(els)=>els.map(e=>({tag:e.tagName,type:e.type,value:e.value,validationMessage:e.validationMessage}))'),flush=True)
        else:
            print('FORM_SUBMITTED',mode,state['mutations'][-1]['path'],flush=True)
        check(mode+' task request sent',len(state['mutations'])>before)
        mutation=state['mutations'][before]
        check(mode+' posts to customer jobs',mutation['path']=='/api/customer/jobs')
        check(mode+' mode serialized',mutation['payload']['mode']==mode)
        check(mode+' CSRF retained',mutation['csrf']=='FIXTURE-CSRF-NOT-A-REAL-SECRET')
        check(mode+' default strategy retained',mutation['payload']['multi_item_mode']=='balanced')
        if mode=='supplier_search':
            check('registry policy serialized',mutation['payload']['supplier_search_policy']=='minprom_registry_priority')
            check('delivery city serialized',mutation['payload']['delivery_city']=='Екатеринбург')
            check('delivery radius serialized',mutation['payload']['geo_radius_km']=='500')
            check('file name retained in multipart',mutation['payload']['files']==['Спецификация_пример.pdf'])
    page.get_by_role('button',name='Выключить звуковые уведомления',exact=True).first.click()
    check('notification preference stored',page.evaluate("localStorage.getItem('tenderlex_notifications_enabled')")=='false')
    page.reload(wait_until='networkidle')
    check('notification preference survives reload',page.get_by_role('button',name='Включить звуковые уведомления',exact=True).count()>0)
    for width in [375,430,768,1024,1440]:
        page.set_viewport_size({'width':width,'height':900})
        check(f'authenticated cabinet no overflow {width}',page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
        page.screenshot(path=str(args.evidence_dir/f'cabinet-auth-{width}.png'),full_page=True)
    check('all requests handled in form fixture',not state['unhandled'])
    ctx.close()

    # Position-by-position selection runs the actual confirmation handler.
    pending=job('fixture-strategy',status='awaiting_customer_confirmation',status_label='Выберите стратегию',has_result=False,can_download=False,can_find_more_suppliers=False,awaiting_customer_confirmation=True,confirmation_kind='multi_item_strategy',multi_item_details={'items':[{'id':'cable','name':'Кабель ВВГнг(А)-LS','quantity':'5000','unit':'м'},{'id':'tray','name':'Лоток кабельный','quantity':'100','unit':'м'}],'total_items':2})
    ctx,page,state=fixture(browser,jobs=[pending])
    navigate(page)
    page.get_by_role('button',name=re.compile('Попозиционный глубокий поиск')).click()
    page.get_by_role('button',name='Применить',exact=True).click()
    page.wait_for_timeout(250)
    mutation=next(x for x in state['mutations'] if x['path'].endswith('/choose-strategy'))
    check('per-position confirmation endpoint retained',mutation['method']=='POST')
    check('per_item serialized',mutation['payload']['multi_item_mode']=='per_item')
    check('selected position IDs retained',set(mutation['payload']['selected_item_ids'])=={'cable','tray'})
    ctx.close()

    # Feature-flagged tasks and delivery radius remain hidden for ineligible users.
    ctx,page,state=fixture(browser,flags=False)
    navigate(page)
    check('price monitoring feature flag respected',page.get_by_role('tab',name=re.compile('Мониторинг')).count()==0)
    check('geo feature flag respected',page.get_by_label(re.compile('Приоритет в радиусе доставки')).count()==0)
    ctx.close()

    # Delivery radius is opt-in: its city becomes a real required field only
    # after it is enabled, and the expanded layout must fit every target width.
    ctx,page,state=fixture(browser)
    navigate(page,'supplier_search')
    form=page.locator('form#new-job')
    form.locator('textarea').fill('Поставка кабеля ВВГнг(А)-LS 3×2,5 — 5000 м')
    page.get_by_label(re.compile('Приоритет в радиусе доставки')).check()
    city=page.locator('#delivery-city')
    radius=page.locator('#delivery-radius')
    before=len(state['mutations'])
    form.locator('button[type=submit]').last.click()
    check('enabled geo requires a delivery city',city.evaluate('el=>el.matches(\':invalid\')'))
    check('empty delivery city prevents task request',len(state['mutations'])==before)
    city.fill('посёлок Каменский, Каменский городской округ, Свердловская область')
    radius.fill('2500')
    check('geo fee wording is visible',page.get_by_text('+40% к стоимости задачи',exact=True).is_visible())
    check('geo helper explains delivery boundary',page.get_by_text(re.compile('склад и сроки уточняются у поставщика')).is_visible())
    for width in [375,768,1024,1440]:
        page.set_viewport_size({'width':width,'height':900})
        check(f'expanded geo no overflow {width}',page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
        check(f'geo field controls fit {width}',page.locator('#delivery-city, #delivery-radius').evaluate_all('(els)=>els.every((el)=>{const r=el.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1})'))
        page.screenshot(path=str(args.evidence_dir/f'cabinet-geo-{width}.png'),full_page=True)
    ctx.close()

    # All existing result/account actions remain reachable in the real UI.
    ctx,page,state=fixture(browser,jobs=[job(),job('fixture-exact','exact_product')])
    navigate(page)
    page.locator('#jobs').wait_for()
    check('supplier results visible',page.locator('#jobs').get_by_text('Спецификация кабельной продукции',exact=True).count()==2)
    controls=page.locator('button').evaluate_all('(els)=>els.map(e=>({text:e.innerText.trim(),title:e.title,aria:e.getAttribute("aria-label")}))')
    (args.evidence_dir/'authenticated-controls.json').write_text(json.dumps(controls,ensure_ascii=False,indent=2))
    # Open API and verify all existing integration tabs; no key is created.
    page.get_by_title('API и интеграции (CRM, 1С, ИИ-ассистенты, MCP)',exact=True).click()
    check('API key list uses existing endpoint',any(x['path']=='/api/customer/api-keys' for x in state['requests']))
    check('MCP UI preserved',page.get_by_text(re.compile('MCP')).count()>0)
    page.screenshot(path=str(args.evidence_dir/'cabinet-api.png'),full_page=True)
    check('no key mutation from opening API',not state['mutations'])
    def close_dialog():
        dialog=page.get_by_role('dialog').last
        dialog.get_by_role('button',name=re.compile('^Закрыть')).last.click()
    close_dialog()
    for title, marker in [
        ('Баланс аккаунта. Нажмите, чтобы пополнить','Пополнение баланса'),
        ('История операций и списаний','История'),
        ('Пригласить коллегу: +1 000 ₽ на баланс за рекомендацию','Пригласить'),
        ('Справка: подробное описание 4 функций и пошаговый алгоритм работы','Справка')]:
        page.get_by_title(title,exact=True).click()
        dialog=page.get_by_role('dialog').last
        dialog.wait_for()
        check(marker+' dialog reachable',dialog.is_visible())
        if marker=='Пополнение баланса':
            dialog.get_by_role('button',name='Счёт для юрлиц',exact=True).click()
            check('legal invoice tab retained','счёт' in dialog.inner_text().lower())
            dialog.get_by_role('button',name=re.compile('^СБП')).click()
            check('SBP availability state retained','СБП' in dialog.inner_text())
            dialog.get_by_role('button',name='Оплата картой',exact=True).click()
            check('card payment tab retained','пакет' in dialog.inner_text().lower())
        close_dialog()
    check('opening all account dialogs has no mutations',not state['mutations'])
    # Tariffs open from the navigation rail but must use the full work column;
    # a package list with several purchase actions must never overflow.
    page.get_by_role('button',name=re.compile('^Тарифы')).click()
    tariffs=page.locator('.tl-cabinet-tariffs')
    tariffs.wait_for()
    check('expanded tariffs render outside sidebar',tariffs.evaluate("el=>!el.closest('.tl-cabinet-sidebar')"))
    check('all fixture deposit packages visible',tariffs.get_by_role('button',name='Купить',exact=True).count()==5)
    tariff_text_clipping=[]
    for width in [375,768,1024,1440]:
        page.set_viewport_size({'width':width,'height':900})
        check(f'expanded tariffs no overflow {width}',page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
        check(f'expanded tariff controls fit {width}',tariffs.locator('button').evaluate_all('(els)=>els.every((el)=>{const r=el.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1})'))
        entries=tariffs.locator('[class*="truncate"]').evaluate_all("(els)=>els.map((el)=>({text:el.textContent.trim(),clientWidth:el.clientWidth,scrollWidth:el.scrollWidth,clipped:el.scrollWidth>el.clientWidth+1}))")
        tariff_text_clipping.append({'width':width,'entries':entries})
        page.screenshot(path=str(args.evidence_dir/f'cabinet-tariffs-{width}.png'),full_page=True)
    (args.evidence_dir/'tariff-text-clipping.json').write_text(json.dumps(tariff_text_clipping,ensure_ascii=False,indent=2))
    check('all tariff text fits its price row',all(not entry['clipped'] for sample in tariff_text_clipping for entry in sample['entries']))
    check('full deposit amounts remain present',all(tariffs.get_by_text(amount,exact=True).count()==1 for amount in ['1 000 ₽ на баланс','3 500 ₽ на баланс','6 500 ₽ на баланс','14 000 ₽ на баланс','37 500 ₽ на баланс']))
    # On a phone the account tools are intentionally collapsed; opening
    # tariffs from that real control must still reveal the same panel.
    page.set_viewport_size({'width':375,'height':900})
    page.reload(wait_until='networkidle')
    page.get_by_role('button',name=re.compile('Меню кабинета')).click()
    mobile_tariffs=page.get_by_role('button',name=re.compile('^Тарифы'))
    mobile_tariffs.click()
    check('mobile tariffs trigger exposes expanded state',mobile_tariffs.get_attribute('aria-expanded')=='true')
    check('mobile tariff panel opens from collapsed account tools',page.locator('#cabinet-tariffs').is_visible())
    with page.expect_download() as download:
        page.get_by_role('button',name='Реестр поставщиков',exact=True).click()
    check('supplier result download works',download.value.suggested_filename.endswith('.docx'))
    page.get_by_role('button',name='Запрос КП',exact=True).click()
    check('RFQ actual endpoint retained',any(x['path'].endswith('/quote-request') for x in state['requests']))
    page.get_by_role('button',name=re.compile('^Закрыть')).last.click()
    page.get_by_title('Найти поставщиков по подобранным товарам и аналогам',exact=True).click()
    check('analog-to-supplier followup reachable',page.get_by_role('button',name=re.compile('Попозиционный глубокий поиск')).count()>0)
    page.get_by_role('button',name=re.compile('^Закрыть')).last.click()
    page.get_by_placeholder('Поиск по названию или номеру #...').fill('несуществующая задача')
    page.wait_for_timeout(650)
    check('history search forwarded to API',any(x.get('q')==['несуществующая задача'] for x in state['jobs_queries']))
    check('history empty filter removes result cards',page.locator('#jobs').get_by_text('Спецификация кабельной продукции',exact=True).count()==0)
    check('all requests handled in account fixture',not state['unhandled'])
    ctx.close()

    # Guest authorization, reset and legal controls stay available.
    ctx,page,state=fixture(browser,authenticated=False)
    page.goto(base+'/cabinet',wait_until='networkidle')
    check('Yandex login link preserved',page.locator('a[href="/api/customer/auth/yandex/login"]').count()==1)
    check('Telegram login link preserved',page.locator('a[href="/api/customer/auth/telegram/login"]').count()==1)
    page.get_by_role('button',name='Регистрация',exact=True).click()
    check('registration legal consents preserved',page.locator('form input[type=checkbox]').count()==2)
    page.get_by_placeholder('Ваше имя').fill('Тест')
    page.get_by_placeholder('name@company.ru').fill('qa@example.invalid')
    page.get_by_placeholder('••••••••').fill('Synthetic-Only-123')
    # Click the full labels, the same target a human uses, never force check.
    for i in range(2):page.locator('form label').filter(has=page.locator('input[type=checkbox]')).nth(i).click(position={'x':25,'y':10})
    page.locator('form button[type=submit]').click()
    page.locator('#new-job').wait_for()
    check('registration real handler posts to correct route',any(x['path']=='/api/customer/auth/register' for x in state['mutations']))
    check('registration authenticated UI renders',page.locator('#new-job').is_visible())
    ctx.close()
    check('zero JavaScript runtime errors',not errors)
    browser.close()

report={'status':'passed','passed':len(checks),'checks':checks,'runtimeErrors':errors,'boundary':'All customer APIs intercepted; no real account, file, task, payment or message mutations.'}
(args.evidence_dir/'cabinet-workflows.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
