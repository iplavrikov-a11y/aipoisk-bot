"""Validate the geo contract before uploads/reservations and retain it on follow-ups."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import main, jobs
from app.billing import BillingError, effective_job_unit_price_kopeks
from app.db import Base
from app.models import Client, ClientTariffOverride, Job, SystemSettings

@pytest.fixture
def geo_env(monkeypatch,tmp_path):
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with Session(engine) as db:
        client=Client(telegram_id='geo-input-contract',money_balance_kopeks=1_000_000,is_active=True,allowed_price_monitoring=True)
        db.add_all([client,SystemSettings(geo_radius_search_enabled_global=True)]);db.commit()
        db.add(ClientTariffOverride(client_id=client.id,kind='supplier_search',price_kopeks=10_000));db.commit()
        context=SimpleNamespace(user=SimpleNamespace(id='fixture-user',is_email_verified=True,client=client))
        monkeypatch.setattr(jobs,'job_dir',lambda identifier: tmp_path/str(identifier))
        monkeypatch.setattr(main,'enqueue_job',lambda _id:None)
        yield db,client,context
    engine.dispose()

@pytest.mark.parametrize('mode,city,radius',[
 ('supplier_search','',300),('supplier_search','Москва',None),('supplier_search','Москва',0),
 ('supplier_search','Москва',-1),('supplier_search','Москва',5001),('supplier_search','Город-которого-не-существует',300),
 ('exact_product','Казань',300),('procurement_report','Казань',300),
])
def test_invalid_geo_rejected_before_upload_and_money(geo_env,monkeypatch,mode,city,radius):
    db,client,context=geo_env
    upload=AsyncMock(return_value=[]);monkeypatch.setattr(main,'_customer_upload_payload',upload)
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.create_customer_job_api(mode=mode,delivery_city=city,geo_radius_km=radius,text='Техническое задание на поставку насоса',context=context,db=db))
    assert error.value.status_code==400
    upload.assert_not_awaited()
    assert db.query(Job).count()==0
    assert client.money_reserved_kopeks==0


def test_shared_create_job_rejects_unanchored_geo(geo_env):
    db,client,_=geo_env
    with pytest.raises(ValueError):
        jobs.create_job(db,client_id=client.id,mode='supplier_search',title='fixture',target_suppliers=5,files=[],geo_radius_km=300)
    assert db.query(Job).count()==0


def test_positive_radius_without_city_cannot_be_billed(geo_env):
    db,client,_=geo_env
    job=Job(client_id=client.id,mode='supplier_search',delivery_city='',geo_radius_km=300)
    with pytest.raises(BillingError):
        effective_job_unit_price_kopeks(db,client,'supplier_search',job=job)


def test_find_more_inherits_geo(geo_env,monkeypatch):
    db,client,_=geo_env
    original=Job(client_id=client.id,mode='supplier_search',status='completed',title='fixture',delivery_city='Казань',geo_radius_km=300,target_suppliers=5,verified_count=5)
    db.add(original);db.commit()
    monkeypatch.setattr(main,'job_can_find_more_suppliers',lambda _job:True)
    monkeypatch.setattr(main,'_supplier_exclusions_from_job',lambda _job:[{'company_name':'Old supplier','site':'https://example.invalid'}])
    monkeypatch.setattr(main,'_repeat_supplier_search_input_files',lambda _job:[('spec.txt',b'fixture')])
    monkeypatch.setattr(main,'write_supplier_exclusions',lambda *a,**kw:None)
    monkeypatch.setattr(main,'write_dobor_context',lambda *a,**kw:None)
    monkeypatch.setattr(main,'read_supplier_exclusions_payload',lambda _job:{})
    child=main.create_additional_supplier_search_for_client(db,client=client,original_job=original,created_by_telegram_id='fixture')
    assert (child.delivery_city,child.geo_radius_km)==('Казань',300)
    assert client.money_reserved_kopeks>0


def test_supplier_search_from_exact_can_set_its_own_geo(geo_env,monkeypatch):
    db,client,_=geo_env
    parent=Job(client_id=client.id,mode='exact_product',status='completed',title='fixture')
    db.add(parent);db.commit()
    monkeypatch.setattr(main,'_repeat_supplier_search_input_files',lambda _job:[])
    monkeypatch.setattr(main,'read_job_evidence_payload',lambda _job:{})
    monkeypatch.setattr(main,'_build_exact_product_supplier_selection_text',lambda **kw:'fixture specification')
    child=main.create_supplier_search_from_exact_product(db,client=client,original_job=parent,created_by_telegram_id='fixture',delivery_city='Казань',geo_radius_km=300)
    assert (child.delivery_city,child.geo_radius_km)==('Казань',300)


def test_customer_key_shown_once_and_not_stored(geo_env,monkeypatch):
    db,client,context=geo_env
    monkeypatch.setattr(main,'require_customer_csrf',lambda *a:None)
    response=main.customer_create_api_key(SimpleNamespace(),context=context,db=db)
    raw=response['raw_key']
    from app.models import ApiKey
    key=db.get(ApiKey,response['id'])
    assert key.secret_token in ('',None)
    listed=main.customer_list_api_keys(context=context,db=db)
    assert 'raw_key' not in listed['keys'][0]
    assert raw not in str(listed)


def test_reservation_failure_never_leaves_unlaunched_job_pending(geo_env,monkeypatch):
    db,client,context=geo_env
    monkeypatch.setattr(main,'_customer_upload_payload',AsyncMock(return_value=[('a.txt',b'A'),('b.txt',b'B')]))
    monkeypatch.setattr(main,'client_access_error',lambda *a,**kw:'')
    queued=[];monkeypatch.setattr(main,'enqueue_job',queued.append)
    def failed_reserve(*args,**kwargs):
        raise BillingError('synthetic reserve failure')
    monkeypatch.setattr(main,'reserve_job_units',failed_reserve)
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.create_customer_job_api(mode='supplier_search',context=context,db=db))
    assert error.value.status_code==403
    assert not queued
    db.refresh(client)
    assert client.money_reserved_kopeks==0
    assert not db.query(Job).filter(Job.status.in_(['draft','pending','running'])).count()
