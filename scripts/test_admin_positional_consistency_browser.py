"""Admin selection / expert actions with synthetic API only; no live mutations.

Use ADMIN_QA_BASE_URL for a local Vite server, or ADMIN_QA_DIST for a candidate
build served entirely by Playwright. All API requests and external URLs are intercepted.
"""
import asyncio
import json
import mimetypes
import os
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright
from test_admin_navigation_browser import payload

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get('ADMIN_QA_BASE_URL', 'http://admin.test/')
DIST = Path(os.environ.get('ADMIN_QA_DIST', ROOT / 'frontend' / 'dist'))


def fixture(job_id, mode, status, *, confirmed=False):
    selection = {'revision': f'rev-{job_id}', 'mode': mode, 'items': [
        {'id': f'row-{i}', 'position_no': i, 'name': f'Клапан {i}'} for i in range(1, 13)],
        'selected_ids': ['row-2', 'row-9'] if confirmed else [], 'max_positions': 12 if mode != 'exact_product' else 5,
        'price_kopeks': 9900, 'confirmed': confirmed,
        'pricing_mode': 'per_found_position' if mode == 'price_monitoring' else 'fixed_task'}
    return {'id': job_id, 'job_number': 999, 'client_id': 'fixture-client', 'client_name': 'Тестовый клиент',
        'mode': mode, 'mode_label': mode, 'status': status, 'title': job_id, 'human_title': job_id,
        'created_at': '2026-10-24T06:00:00Z', 'progress': 25, 'message': 'Выберите позиции',
        'position_selection': selection, 'confirmation_kind': 'multi_item_strategy' if mode == 'supplier_search' else '',
        'delivery_city': 'Казань', 'geo_radius_km': 100, 'multi_item_mode': 'per_item',
        'supplier_search_policy': 'normal', 'result_files': [], 'admin_reruns': [], 'sources': [],
        'input_files': [], 'verified_count': 0, 'file_count': 1}


async def main():
    jobs = [fixture('exact-wait', 'exact_product', 'awaiting_exact_selection'),
            fixture('monitor-wait', 'price_monitoring', 'awaiting_position_selection'),
            fixture('supplier-wait', 'supplier_search', 'awaiting_customer_confirmation'),
            fixture('expired', 'exact_product', 'confirmation_expired'),
            fixture('finished', 'price_monitoring', 'completed', confirmed=True)]
    jobs[-1]['admin_reruns'] = [{'id': 'child-failed', 'job_number': 1001, 'status': 'failed', 'progress': 20,
                               'message': 'Ошибка источника', 'files': []}]
    jobs[-1]['admin_rerun'] = jobs[-1]['admin_reruns'][0]
    for mode, status in [('exact_product', 'awaiting_exact_selection'), ('price_monitoring', 'awaiting_position_selection'), ('supplier_search', 'awaiting_customer_confirmation')]:
        parent = fixture(f'parent-child-{mode}', mode, 'completed', confirmed=True)
        child = fixture(f'child-{mode}', mode, status)
        child['files'] = []
        if mode == 'supplier_search':
            child['multi_item_selection'] = child.pop('position_selection')
            child['multi_item_selection']['mode'] = 'per_item'
        parent['admin_rerun'] = child
        parent['admin_reruns'] = [child]
        jobs.append(parent)
    jobs[2]['multi_item_selection'] = jobs[2].pop('position_selection')
    jobs[2]['multi_item_selection']['mode'] = 'per_item'
    for job_id, status in [('supplier-balanced', 'awaiting_customer_confirmation'), ('supplier-expired', 'confirmation_expired'), ('supplier-stale', 'awaiting_customer_confirmation')]:
        supplier = fixture(job_id, 'supplier_search', status)
        supplier['multi_item_selection'] = supplier.pop('position_selection')
        supplier['multi_item_selection']['mode'] = 'balanced'
        jobs.append(supplier)
    mutations, errors, dialogs = [], [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.set_default_timeout(5000)
        page.on('pageerror', lambda e: errors.append(str(e)))
        async def accept_dialog(dialog):
            dialogs.append(dialog.message)
            await dialog.accept()
        page.on('dialog', accept_dialog)

        async def intercept(route):
            request = route.request
            url = urlsplit(request.url)
            if url.netloc != urlsplit(BASE).netloc:
                await route.abort()
                return
            if not url.path.startswith('/api/'):
                if url.hostname != 'admin.test':
                    await route.continue_()
                    return
                file = DIST / (url.path.lstrip('/') if url.path.startswith('/assets/') else 'index.html')
                await route.fulfill(status=200, content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream', body=file.read_bytes())
                return
            if request.method not in ('GET', 'HEAD'):
                body = request.post_data_json if 'application/json' in request.headers.get('content-type', '') else request.post_data
                mutations.append({'path': url.path, 'query': url.query, 'body': body})
                job = next(j for j in jobs if j['id'] == url.path.split('/')[3])
                if job['id'] == 'supplier-stale':
                    await route.fulfill(status=400, content_type='application/json', body=json.dumps({'detail': 'Список позиций обновился. Обновите карточку и повторите выбор.'}))
                    return
                if url.path.endswith('/admin-rerun'):
                    job['admin_rerun'] = {'id': 'new-expert-child', 'job_number': 1002, 'status': 'running', 'progress': 1,
                                          'message': 'Новый экспертный поиск', 'files': []}
                    job['admin_reruns'].insert(0, job['admin_rerun'])
                elif not url.path.endswith('/admin-supplement'):
                    job['status'] = 'running'
                data = {'ok': True, 'job': deepcopy(job)}
            elif url.path == '/api/jobs':
                data = deepcopy(jobs)
            elif url.path.startswith('/api/jobs/') and len(url.path.split('/')) == 4:
                data = deepcopy(next(j for j in jobs if j['id'] == url.path.split('/')[3]))
            elif url.path.endswith('/supplement-candidates'):
                data = {'candidates': []}
            else:
                data = payload(url.path + ('?' + url.query if url.query else ''))
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(data))

        await page.route('**/*', intercept)
        await page.goto(BASE, wait_until='networkidle')
        await page.locator('a[href="#jobs"]').click()
        card = lambda title: page.locator('article.job-card').filter(has=page.get_by_role('heading', name=title, exact=True))
        exact = card('exact-wait')
        await exact.get_by_text('Распознано: 12 · Подтверждено: 0', exact=True).wait_for()
        for title in ('exact-wait', 'monitor-wait', 'supplier-wait'):
            current = card(title)
            assert await current.get_by_text('Ожидает выбора позиций', exact=True).count() == 1
            assert await current.locator('[title="Сначала подтвердите позиции в карточке задачи"]').is_disabled()
        for mode in ('exact_product', 'price_monitoring', 'supplier_search'):
            child_card = card(f'parent-child-{mode}')
            assert await child_card.locator('[title="Экспертная задача уже активна; продолжите её в карточке"]').is_disabled()
            assert await child_card.get_by_text('Экспертная задача без списания с клиента.', exact=False).count() == 1
            assert await child_card.get_by_role('checkbox').count() == 12
        assert not mutations, 'Merely viewing paused jobs launched processing'
        assert await exact.get_by_text('0 тов.', exact=True).count() == 0
        monitor = card('monitor-wait')
        for index in range(12):
            await monitor.get_by_role('checkbox').nth(index).check()
        for index in range(12):
            await monitor.get_by_role('checkbox').nth(index).uncheck()
        await monitor.get_by_role('checkbox').nth(1).check()
        await monitor.get_by_role('checkbox').nth(8).check()
        await monitor.get_by_role('button', name='Подтвердить позиции для мониторинга').click()
        assert mutations[-1]['path'] == '/api/jobs/monitor-wait/position-selection'
        assert mutations[-1]['body'] == {'revision': 'rev-monitor-wait', 'selected_item_ids': ['row-2', 'row-9']}
        for index in range(5):
            await exact.get_by_role('checkbox').nth(index).check()
        assert not await exact.get_by_role('checkbox').nth(5).is_enabled()
        for index in range(5):
            await exact.get_by_role('checkbox').nth(index).uncheck()
        await exact.get_by_role('checkbox').nth(8).check()
        await exact.get_by_role('button', name='Подтвердить выбор товаров', exact=True).click()
        assert mutations[-1]['body'] == {'revision': 'rev-exact-wait', 'selected_item_ids': ['row-9']}
        assert mutations[-1]['path'].endswith('/exact-selection')
        supplier = card('supplier-wait')
        await supplier.get_by_role('checkbox').nth(1).check()
        await supplier.get_by_role('checkbox').nth(8).check()
        await supplier.get_by_role('combobox', name='Стратегия поиска поставщиков').select_option('per_item')
        await supplier.get_by_role('button', name='Подтвердить позиции и стратегию').click()
        from urllib.parse import parse_qs
        assert mutations[-1]['path'] == '/api/jobs/supplier-wait/choose-strategy'
        query = parse_qs(mutations[-1]['query'])
        assert query == {'multi_item_mode': ['per_item'], 'revision': ['rev-supplier-wait'], 'selected_item_ids': ['row-2', 'row-9']}
        stale = card('supplier-stale')
        await stale.get_by_role('checkbox').nth(1).check()
        before_stale = len(mutations)
        await stale.get_by_role('button', name='Подтвердить позиции и стратегию').click()
        await stale.get_by_role('alert').filter(has_text='Список позиций обновился').wait_for()
        await page.wait_for_timeout(200)
        assert len(mutations) == before_stale + 1, 'Stale choice retried automatically'
        assert await stale.get_by_role('checkbox').nth(1).is_checked()
        assert next(j for j in jobs if j['id'] == 'supplier-stale')['status'] == 'awaiting_customer_confirmation'
        assert parse_qs(mutations[-1]['query'])['revision'] == ['rev-supplier-stale']
        balanced = card('supplier-balanced')
        await balanced.get_by_role('combobox', name='Стратегия поиска поставщиков').select_option('balanced')
        await balanced.get_by_role('checkbox').nth(8).check()
        await balanced.get_by_role('button', name='Подтвердить позиции и стратегию').click()
        assert mutations[-1]['path'] == '/api/jobs/supplier-balanced/choose-strategy'
        assert parse_qs(mutations[-1]['query']) == {'multi_item_mode': ['balanced'], 'revision': ['rev-supplier-balanced'], 'selected_item_ids': ['row-9']}
        expired_supplier = card('supplier-expired')
        await expired_supplier.get_by_role('combobox', name='Стратегия поиска поставщиков').select_option('per_item')
        await expired_supplier.get_by_role('checkbox').nth(1).check()
        await expired_supplier.get_by_role('button', name='Создать экспертный поиск с выбранными позициями').click()
        assert mutations[-1]['path'] == '/api/jobs/supplier-expired/admin-rerun'
        assert mutations[-1]['body'] == {'revision': 'rev-supplier-expired', 'selected_item_ids': ['row-2']}
        assert parse_qs(mutations[-1]['query']) == {'multi_item_mode': ['per_item']}
        assert next(j for j in jobs if j['id'] == 'supplier-expired')['status'] == 'confirmation_expired'
        expired = card('expired')
        await expired.get_by_text('Срок выбора истёк · поиск не запущен', exact=True).wait_for()
        await expired.get_by_role('checkbox').nth(8).check()
        await expired.get_by_role('button', name='Создать экспертный поиск с выбранными позициями').click()
        assert mutations[-1]['path'] == '/api/jobs/expired/admin-rerun'
        assert mutations[-1]['body'] == {'revision': 'rev-expired', 'selected_item_ids': ['row-9']}
        assert next(j for j in jobs if j['id'] == 'expired')['status'] == 'confirmation_expired'
        assert await expired.locator('[title="Экспертная задача уже активна; продолжите её в карточке"]').is_disabled()
        finished = card('finished')
        await finished.get_by_role('button', name='Новый экспертный поиск без списания с клиента').click()
        assert mutations[-1]['path'] == '/api/jobs/finished/admin-rerun'
        assert mutations[-1]['body'] is None
        assert 'Подтверждённые позиции: 2' in dialogs[-1]
        assert 'Казань, радиус 100 км' in dialogs[-1]
        assert 'Баланс клиента не списывается' in dialogs[-1]
        await finished.get_by_role('button', name='Экспертная задача уже активна; продолжите её в карточке').wait_for()
        await finished.get_by_text('Экспертные поиски: 2 · последний: в работе', exact=True).wait_for()
        await finished.get_by_role('button', name='Дополнить отчет / отправить клиенту').click()
        modal = page.locator('.supplement-modal')
        await modal.get_by_text('Прикрепите комментарий и готовые файлы', exact=False).wait_for()
        await modal.locator('input[type="file"]').set_input_files({'name': 'expert.txt', 'mimeType': 'text/plain', 'buffer': b'synthetic expert note'})
        await modal.get_by_role('checkbox', name='Отправить уведомление и файл в Telegram бот клиенту').uncheck()
        before = len(mutations)
        await modal.get_by_role('button', name='Сохранить дополнение в кабинете').click()
        assert len(mutations) == before + 1
        assert mutations[-1]['path'] == '/api/jobs/finished/admin-supplement'
        assert 'filename="expert.txt"' in mutations[-1]['body']
        assert 'name="notify_telegram"' in mutations[-1]['body']
        assert '\r\nfalse\r\n' in mutations[-1]['body']
        report = {'status': 'passed', 'checks': ['waiting states and counts for 3 modes', 'child waiting controls and no duplicate expert launch',
            'exact max5', 'monitoring 12 rows selectable', 'exact and PM revision plus IDs', 'supplier subset and current revision in both strategies', 'stale supplier revision retains choice and shows error without automatic retry',
            'expired exact and supplier create child with revision plus IDs', 'confirmed expert scope, geography and no debit',
            'supplement files plus comment, explicit Telegram option, no search', 'single-parent refresh after mutation'],
            'mutations': [{**entry, 'body': '<synthetic multipart file/comment>' if entry['path'].endswith('/admin-supplement') else entry['body']} for entry in mutations],
            'runtime_errors': errors}
        Path(os.environ.get('ADMIN_QA_OUTPUT', '/tmp/tenderlex-admin-positional-consistency.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False))
        assert not errors, errors
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
