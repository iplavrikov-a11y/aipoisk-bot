from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import billing, jobs
from app.billing import KIND_PRICE_MONITORING, OP_CHARGE, OP_RESERVE
from app.db import Base
from app.models import BillingTransaction, Client, Job, SystemSettings
from app.price_monitoring import cleaner
from app.price_monitoring.models import BatchMonitoringResult, ItemPriceResult, SupplierQuote


@pytest.fixture
def worker_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'worker-contract.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(billing.config, "storage_dir", str(tmp_path / "storage"))
    yield sessions, tmp_path
    engine.dispose()


def _job(sessions, *, balance: int = 100_000) -> tuple[str, str]:
    with sessions() as db:
        settings = SystemSettings(price_monitoring_default_price_kopeks=10_000)
        client = Client(
            telegram_id=f"monitor-worker-{balance}",
            money_balance_kopeks=balance,
            allowed_price_monitoring=True,
        )
        db.add_all((settings, client))
        db.flush()
        job = Job(
            client_id=client.id,
            mode=KIND_PRICE_MONITORING,
            status="running",
            title="Worker contract",
        )
        db.add(job)
        db.commit()
        return client.id, job.id


def _patch_worker(monkeypatch, tmp_path, items):
    monkeypatch.setattr(jobs, "job_dir", lambda _job_id: tmp_path / "job")
    monkeypatch.setattr(jobs, "_populate_job_ai_metadata", lambda *_args: None)
    monkeypatch.setattr(cleaner, "extract_items_from_files_or_text", lambda *_args, **_kwargs: items)
    # These financial contracts start after the separate inventory-confirmation stage.
    rows = [{"id": f"row-{i}", "position_no": i, "name": name, "unit": unit} for i, (name, unit) in enumerate(items, 1)]
    monkeypatch.setattr(jobs, "read_selection", lambda _job: {"confirmed": True})
    monkeypatch.setattr(jobs, "selected_positions", lambda _job: rows)

    async def run_without_cancellation(_job_id, discovery):
        return await discovery

    monkeypatch.setattr(jobs, "_run_supplier_discovery_with_cancellation", run_without_cancellation)


def _batch(job_id: str, *, total: int = 1, found: int = 1) -> BatchMonitoringResult:
    item = ItemPriceResult(
        1,
        "Товар",
        "Товар",
        "шт",
        quotes=[SupplierQuote(company_name="Поставщик", price_rub=100, url="https://example.invalid/item")],
        status="found",
    )
    return BatchMonitoringResult(
        job_id=job_id,
        items=[item],
        total_positions=total,
        found_positions=found,
        not_found_positions=total - found,
        price_per_position_rub=100,
        total_charged_rub=found * 100,
    )


def test_insufficient_full_monitoring_budget_prevents_pipeline_execution(worker_db, monkeypatch):
    sessions, tmp_path = worker_db
    _client_id, job_id = _job(sessions, balance=20_000)
    _patch_worker(monkeypatch, tmp_path, [("Первый", "шт"), ("Второй", "шт"), ("Третий", "шт")])
    pipeline_calls = 0

    async def fake_pipeline(**_kwargs):
        nonlocal pipeline_calls
        pipeline_calls += 1
        raise AssertionError("pipeline must not start without a full reserve")

    monkeypatch.setattr(jobs, "run_price_monitoring_pipeline", fake_pipeline)
    with sessions() as db:
        job = db.get(Job, job_id)
        settings = db.query(SystemSettings).one()
        with pytest.raises(billing.BillingError, match="Недостаточно средств"):
            jobs._process_price_monitoring(db, job, settings, "Товары")
        assert pipeline_calls == 0
        assert db.query(BillingTransaction).filter_by(job_id=job_id).count() == 0


def test_pipeline_exception_reaches_the_outer_job_handler(worker_db, monkeypatch):
    sessions, tmp_path = worker_db
    _client_id, job_id = _job(sessions)
    _patch_worker(monkeypatch, tmp_path, [("Товар", "шт")])

    async def broken_pipeline(**_kwargs):
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(jobs, "run_price_monitoring_pipeline", broken_pipeline)
    with sessions() as db:
        job = db.get(Job, job_id)
        settings = db.query(SystemSettings).one()
        with pytest.raises(RuntimeError, match="pipeline exploded"):
            jobs._process_price_monitoring(db, job, settings, "Товар")
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_CHARGE).count() == 0


def test_evidence_write_failure_never_charges_monitoring(worker_db, monkeypatch):
    sessions, tmp_path = worker_db
    _client_id, job_id = _job(sessions)
    _patch_worker(monkeypatch, tmp_path, [("Товар", "шт")])

    async def successful_pipeline(**kwargs):
        Path(kwargs["output_excel_path"]).write_bytes(b"test report")
        return _batch(job_id)

    monkeypatch.setattr(jobs, "run_price_monitoring_pipeline", successful_pipeline)
    monkeypatch.setattr(jobs, "write_evidence", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")))
    with sessions() as db:
        job = db.get(Job, job_id)
        settings = db.query(SystemSettings).one()
        with pytest.raises(OSError, match="disk full"):
            jobs._process_price_monitoring(db, job, settings, "Товар")
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_CHARGE).count() == 0


def test_successful_monitoring_commits_output_evidence_and_charge_together(worker_db, monkeypatch):
    sessions, tmp_path = worker_db
    client_id, job_id = _job(sessions)
    _patch_worker(monkeypatch, tmp_path, [("Товар", "шт")])

    async def successful_pipeline(**kwargs):
        Path(kwargs["output_excel_path"]).write_bytes(b"test report")
        return _batch(job_id)

    monkeypatch.setattr(jobs, "run_price_monitoring_pipeline", successful_pipeline)
    with sessions() as db:
        job = db.get(Job, job_id)
        settings = db.query(SystemSettings).one()
        jobs._process_price_monitoring(db, job, settings, "Товар")

    with sessions() as db:
        client = db.get(Client, client_id)
        job = db.get(Job, job_id)
        assert job.status == "completed"
        assert job.file_count == 0  # Text input has no uploaded files; product count is separate.
        assert Path(job.result_path).is_file()
        assert Path(job.evidence_path).is_file()
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_RESERVE).count() == 1
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_CHARGE).count() == 1
        assert client.money_balance_kopeks == 90_000


def test_outer_worker_rolls_back_a_reserved_monitoring_job_when_processing_fails(worker_db, monkeypatch):
    sessions, tmp_path = worker_db
    client_id, job_id = _job(sessions)
    monkeypatch.setattr(jobs, "SessionLocal", sessions)
    monkeypatch.setattr(jobs, "job_dir", lambda _job_id: tmp_path / "job")
    monkeypatch.setattr(jobs.document_parser, "is_substantive_tz_text", lambda _context: (True, ""))

    def reserve_then_fail(db, job, _settings, _context):
        reserve_price = 10_000
        billing.reserve_price_monitoring_job(
            db,
            job,
            total_positions=1,
            price_per_item_kopeks=reserve_price,
        )
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(jobs, "_process_price_monitoring", reserve_then_fail)
    jobs._process_job_sync(job_id)

    with sessions() as db:
        client = db.get(Client, client_id)
        job = db.get(Job, job_id)
        assert job.status == "failed"
        assert client.money_balance_kopeks == 100_000
        assert client.money_reserved_kopeks == 0
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_RESERVE).count() == 1
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation="release").count() == 1
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_CHARGE).count() == 0
