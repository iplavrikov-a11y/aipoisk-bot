import json
from datetime import timedelta
from unittest.mock import AsyncMock

from app import jobs, main
from app.billing import cancel_price_monitoring_job, expire_stale_confirmations, reserve_price_monitoring_job
from app.models import BillingTransaction, Job, SystemSettings, now_utc
from app.position_selection import build_selection_snapshot, read_selection, confirm_position_selection
from test_exact_selection_workflow import context_db


def test_monitoring_preview_does_not_reserve_or_search(context_db, monkeypatch):
    context, db = context_db
    job = Job(client_id=context.user.client_id, mode='price_monitoring', status='running')
    db.add(job); db.commit()
    prepare = AsyncMock(return_value=[{'position_no':i,'name':f'Товар {i}','unit':'шт'} for i in range(1,9)])
    pipeline = AsyncMock()
    monkeypatch.setattr(jobs,'prepare_job_product_positions',prepare)
    monkeypatch.setattr(jobs,'run_price_monitoring_pipeline',pipeline)
    jobs._process_price_monitoring(db,job,db.query(SystemSettings).first(),'Спецификация товаров')
    assert job.status=='awaiting_position_selection'
    assert len(read_selection(job)['items'])==8
    assert read_selection(job)['pricing_mode']=='per_found_position'
    assert db.query(BillingTransaction).filter_by(job_id=job.id).count()==0
    pipeline.assert_not_awaited()
    assert context.user.client.money_balance_kopeks==100_000


def test_monitoring_all_eight_and_subset_are_valid_source_choices(context_db):
    context, db = context_db
    job=Job(client_id=context.user.client_id,mode='price_monitoring',status='awaiting_position_selection',position_selection_json=build_selection_snapshot(
        [{'position_no':i,'name':'Одинаковое название'} for i in range(1,9)],price_kopeks=100,mode='price_monitoring'))
    db.add(job);db.commit()
    selection=read_selection(job)
    ids=[row['id'] for row in selection['items']]
    assert confirm_position_selection(db,job,selection['revision'],ids)
    assert not confirm_position_selection(db,job,selection['revision'],ids)
    assert read_selection(job)['selected_ids']==ids
    assert job.status=='pending'


def test_monitoring_preview_cancel_and_expiry_release_any_legacy_reserve(context_db):
    context, db = context_db
    job = Job(
        client_id=context.user.client_id,
        mode="price_monitoring",
        status="running",
        position_selection_json=build_selection_snapshot(
            [{"position_no": 1, "name": "Панель"}],
            price_kopeks=1_000,
            mode="price_monitoring",
        ),
    )
    db.add(job)
    db.commit()
    reserve_price_monitoring_job(db, job, total_positions=1, price_per_item_kopeks=1_000)

    job.status = "awaiting_position_selection"
    db.commit()
    assert cancel_price_monitoring_job(db, job, note="cancel", message="cancelled")
    db.refresh(context.user.client)
    assert job.status == "cancelled"
    assert context.user.client.money_reserved_kopeks == 0

    expired = Job(
        client_id=context.user.client_id,
        mode="price_monitoring",
        status="awaiting_position_selection",
        position_selection_json=build_selection_snapshot(
            [{"position_no": 1, "name": "Уголок"}],
            price_kopeks=1_000,
            mode="price_monitoring",
        ),
        updated_at=now_utc() - timedelta(days=2),
    )
    db.add(expired)
    db.commit()
    assert expire_stale_confirmations(db) == 1
    db.refresh(expired)
    assert expired.status == "confirmation_expired"


def test_monitoring_customer_api_preserves_owner_and_queues_once(context_db,monkeypatch):
    from fastapi import HTTPException
    from types import SimpleNamespace
    import pytest
    context,db=context_db
    job=Job(client_id=context.user.client_id,mode='price_monitoring',status='awaiting_position_selection',position_selection_json=build_selection_snapshot(
        [{'position_no':2,'name':'Панель'},{'position_no':9,'name':'Уголок'}],price_kopeks=100,mode='price_monitoring'))
    db.add(job);db.commit()
    snapshot=read_selection(job);ids=[snapshot['items'][1]['id']];queued=[]
    monkeypatch.setattr(main,'enqueue_job',queued.append)
    for _ in range(2):
        main.choose_product_positions_api(job.id,revision=snapshot['revision'],selected_item_ids=ids,context=context,db=db)
    assert queued==[job.id]
    assert main.customer_job_to_dict(job)['position_selection']['selected_ids']==ids
    with pytest.raises(HTTPException) as error:
        main.choose_product_positions_api(job.id,revision=snapshot['revision'],selected_item_ids=ids,context=SimpleNamespace(user=SimpleNamespace(client_id='other')),db=db)
    assert error.value.status_code==404


def test_categories_are_a_view_and_never_merge_distinct_skus():
    rows=[{'position_no':i,'name':name} for i,name in enumerate([
        'Стеновые панели 100мм','Стеновые панели 50мм','Кровельные панели 100мм',
        'Саморез 140мм','Саморез 95мм','Уголок внутренний','Уголок наружный','Фасонный элемент'],1)]
    snap=json.loads(build_selection_snapshot(rows,price_kopeks=100,mode='price_monitoring'))
    assert len(snap['items'])==8
    assert [group['name'] for group in snap['groups']]==['Позиции спецификации']
    assert len(snap['groups'][0]['item_ids'])==8
    assert len({value for group in snap['groups'] for value in group['item_ids']})==8
    assert snap['max_positions']==8 and snap['pricing_mode']=='per_found_position'


def test_insufficient_preview_budget_keeps_choice_open(context_db):
    import pytest
    context,db=context_db
    context.user.client.money_balance_kopeks=150
    job=Job(client_id=context.user.client_id,mode='price_monitoring',status='awaiting_position_selection',position_selection_json=build_selection_snapshot(
        [{'position_no':1,'name':'Панель'},{'position_no':2,'name':'Уголок'}],price_kopeks=100,mode='price_monitoring'))
    db.add(job);db.commit()
    snap=read_selection(job)
    with pytest.raises(ValueError,match='Недостаточно средств'):
        confirm_position_selection(db,job,snap['revision'],[row['id'] for row in snap['items']])
    assert job.status=='awaiting_position_selection'
    assert not read_selection(job)['confirmed']
