from pathlib import Path
import importlib.util

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client_module(monkeypatch):
    spec = importlib.util.spec_from_file_location('tenderlex_mcp_client', ROOT / 'mcp_server/server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'API_KEY', 'SYNTHETIC-NO-REAL-REQUESTS')
    return module


def test_public_mcp_download_matches_client():
    assert (ROOT / 'mcp_server/server.py').read_bytes() == (ROOT / 'site/public/scripts/tenderlex_mcp.py').read_bytes()


def test_mcp_status_includes_actionable_selection_ids_and_requirements(client_module, monkeypatch):
    selection = {'revision':'r1','items':[{'id':'item-17','name':'Насос','requirements':'DN80'}]}
    monkeypatch.setattr(client_module, '_http_request', lambda *args, **kwargs: {'job':{'id':'job-1','position_selection':selection}})
    output = client_module.handle_tool_call('tenderlex_get_queued_job', {'job_id':'job-1'})
    text = '\n'.join(row['text'] for row in output)
    assert 'item-17' in text and 'DN80' in text


@pytest.mark.parametrize('action,endpoint,payload', [
    ('strategy', 'choose-strategy', {'multi_item_mode':'per_item', 'selected_item_ids':['item-17']}),
    ('accept', 'accept', {}),
    ('decline', 'decline', {}),
])
def test_mcp_can_finish_supplier_strategy_and_partial_decision(client_module, monkeypatch, action, endpoint, payload):
    requests=[]
    def request(path, **kwargs):
        requests.append((path,kwargs));return {'job':{'status':'pending'}}
    monkeypatch.setattr(client_module, '_http_request', request)
    output = client_module.handle_tool_call('tenderlex_update_queued_job', {'job_id':'job-1','action':action, **payload})
    assert not any(row.get('_tenderlex_error') for row in output)
    assert requests == [(f'/api/v1/mcp/jobs/job-1/{endpoint}', {'method':'POST','payload':payload})]


def test_mcp_missing_key_is_error(client_module, monkeypatch):
    monkeypatch.setattr(client_module,'API_KEY','')
    output=client_module.handle_tool_call('tenderlex_check_balance', {})
    assert any(row.get('_tenderlex_error') for row in output)


@pytest.mark.parametrize('tool', ['tenderlex_find_suppliers','tenderlex_find_exact_and_analogs','tenderlex_analyze_procurement'])
def test_direct_mcp_tools_forward_retry_identity(client_module, monkeypatch, tool):
    requests=[]
    def request(path, **kwargs):
        requests.append(kwargs);return {}
    monkeypatch.setattr(client_module, '_http_request', request)
    client_module.handle_tool_call(tool, {'specification':'Насос','document_text':'ТЗ','idempotency_key':'operation-17'})
    assert requests[0]['idempotency_key']=='operation-17'


def test_mcp_balance_includes_monitoring_permission_and_quota(client_module, monkeypatch):
    monkeypatch.setattr(client_module, '_http_request', lambda *args, **kwargs: {
        'price_monitoring': {'allowed': True, 'remaining': 5, 'spent': 2},
    })
    output = client_module.handle_tool_call('tenderlex_check_balance', {})
    text = '\n'.join(row['text'] for row in output)
    assert 'Мониторинг цен: Остаток: **5** (Использовано: 2)' in text


def test_mcp_exact_report_uses_customer_facing_comparison_heading(client_module, monkeypatch):
    monkeypatch.setattr(client_module, '_http_request', lambda *args, **kwargs: {
        'positions': [{'specs_breakdown': [{
            'param_name': 'Размер', 'tz_requirement': '10 мм',
            'product_fact': '10 мм', 'status': 'match',
        }]}],
    })
    output = client_module.handle_tool_call('tenderlex_find_exact_and_analogs', {'specification': 'ТЗ'})
    text = '\n'.join(row['text'] for row in output)
    assert 'Сверка ключевых параметров под ТЗ' in text
    assert '(Форма 2)' not in text
