import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import billing
from app.db import Base
from app.models import BillingTransaction, Client, Job


@pytest.fixture
def expert_sessions(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "expert.db"}')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    yield sessions
    engine.dispose()


def _job(sessions, mode, *, reserved=False, internal=True):
    with sessions() as db:
        client = Client(telegram_id='fixture-expert', money_balance_kopeks=10000,
                        money_reserved_kopeks=1000 if reserved else 0)
        db.add(client); db.flush()
        job = Job(client_id=client.id, mode=mode, status='running', is_admin_rerun=internal)
        db.add(job); db.flush()
        if reserved:
            db.add(BillingTransaction(client_id=client.id, job_id=job.id, kind=mode,
                operation='reserve', units=1, amount_kopeks=1000,
                balance_after_kopeks=10000, reserved_after_kopeks=1000))
        db.commit()
        return client.id, job.id


def _finalizer(mode):
    return billing.finalize_internal_exact_product_job if mode == 'exact_product' else billing.finalize_internal_price_monitoring_job


def _cancel(db, job):
    fn = billing.cancel_exact_product_job if job.mode == 'exact_product' else billing.cancel_price_monitoring_job
    return fn(db, job, note='fixture cancel', message='cancelled')


@pytest.mark.parametrize('mode', ['exact_product', 'price_monitoring'])
@pytest.mark.parametrize('reserved', [False, True])
def test_internal_completion_is_durable_and_never_charges_customer(expert_sessions, mode, reserved):
    client_id, job_id = _job(expert_sessions, mode, reserved=reserved)
    with expert_sessions() as db:
        job = db.get(Job, job_id)
        _finalizer(mode)(db, job)
    # A completed transaction cannot leave an unrecoverable intermediate state.
    with expert_sessions() as db:
        assert db.get(Job, job_id).status == 'completed'
        client = db.get(Client, client_id)
        assert client.money_balance_kopeks == 10000
        assert client.money_reserved_kopeks == 0
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation='charge').count() == 0
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation='release').count() == int(reserved)


@pytest.mark.parametrize('mode', ['exact_product', 'price_monitoring'])
def test_cancelled_internal_job_cannot_be_published_by_stale_worker(expert_sessions, mode):
    client_id, job_id = _job(expert_sessions, mode, reserved=True)
    with expert_sessions() as stale, expert_sessions() as current:
        stale_job = stale.get(Job, job_id)
        assert _cancel(current, current.get(Job, job_id))
        with pytest.raises(billing.BillingError):
            _finalizer(mode)(stale, stale_job)
        stale.rollback()
    with expert_sessions() as db:
        assert db.get(Job, job_id).status == 'cancelled'
        assert db.get(Client, client_id).money_balance_kopeks == 10000
        assert db.get(Client, client_id).money_reserved_kopeks == 0
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation='charge').count() == 0


@pytest.mark.parametrize('mode', ['exact_product', 'price_monitoring'])
def test_completed_internal_job_cannot_be_cancelled_by_stale_request(expert_sessions, mode):
    _, job_id = _job(expert_sessions, mode)
    with expert_sessions() as stale, expert_sessions() as worker:
        stale_job = stale.get(Job, job_id)
        _finalizer(mode)(worker, worker.get(Job, job_id))
        assert not _cancel(stale, stale_job)
    with expert_sessions() as db:
        assert db.get(Job, job_id).status == 'completed'


@pytest.mark.parametrize('mode', ['exact_product', 'price_monitoring'])
def test_free_internal_finalizer_rejects_normal_customer_job(expert_sessions, mode):
    _, job_id = _job(expert_sessions, mode, internal=False)
    with expert_sessions() as db:
        with pytest.raises(billing.BillingError):
            _finalizer(mode)(db, db.get(Job, job_id))
        db.rollback()
        assert db.get(Job, job_id).status == 'running'


def test_expert_monitoring_report_does_not_claim_a_customer_service_charge(expert_sessions, monkeypatch, tmp_path):
    import json
    from pathlib import Path
    from app import jobs
    from app.models import SystemSettings
    from app.position_selection import build_selection_snapshot
    from app.price_monitoring.models import BatchMonitoringResult, ItemPriceResult, SupplierQuote

    _, job_id = _job(expert_sessions, 'price_monitoring')
    monkeypatch.setattr(jobs, 'job_dir', lambda jid: tmp_path / jid)
    monkeypatch.setattr(jobs, '_check_cancelled', lambda *args, **kwargs: None)
    monkeypatch.setattr(jobs, '_populate_job_ai_metadata', lambda *args: None)

    async def pipeline(**kwargs):
        assert kwargs['price_per_position_rub'] == 0
        Path(kwargs['output_excel_path']).write_bytes(b'fixture report')
        item = ItemPriceResult(1, 'Товар', 'Товар', 'шт', quotes=[
            SupplierQuote(company_name='Fixture', price_rub=10, url='https://example.invalid'),
        ])
        return BatchMonitoringResult(job_id=job_id, items=[item], total_positions=1,
            found_positions=1, not_found_positions=0, price_per_position_rub=0, total_charged_rub=0)

    monkeypatch.setattr(jobs, 'run_price_monitoring_pipeline', pipeline)
    with expert_sessions() as db:
        settings = SystemSettings(price_monitoring_default_price_kopeks=1000)
        db.add(settings)
        job = db.get(Job, job_id)
        selection = json.loads(build_selection_snapshot([{'name': 'Товар', 'unit': 'шт'}],
            price_kopeks=1000, mode='price_monitoring'))
        selection.update(confirmed=True, selected_ids=[selection['items'][0]['id']])
        job.position_selection_json = json.dumps(selection)
        db.commit()
        jobs._process_price_monitoring(db, job, settings, 'Товар')
        assert job.status == 'completed'
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation='charge').count() == 0
