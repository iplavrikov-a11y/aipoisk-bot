from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import billing
from app.billing import (
    KIND_EXACT_PRODUCT,
    OP_CHARGE,
    OP_RELEASE,
    cancel_exact_product_job,
    expire_stale_confirmations,
    reserve_job_units,
    settle_exact_product_job,
)
from app.db import Base
from app.models import BillingTransaction, Client, Job, SystemSettings, now_utc


@pytest.fixture
def exact_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'exact-settlement.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(billing.config, "storage_dir", str(tmp_path / "storage"))
    yield sessions
    engine.dispose()


def _create_job(sessions, *, status: str = "running") -> tuple[str, str]:
    with sessions() as db:
        client = Client(
            telegram_id=f"exact-settlement-{status}",
            money_balance_kopeks=100_000,
        )
        db.add_all((SystemSettings(), client))
        db.flush()
        job = Job(client_id=client.id, mode=KIND_EXACT_PRODUCT, status=status, title="Exact settlement")
        db.add(job)
        db.commit()
        return client.id, job.id


def _reserve(sessions, job_id: str) -> None:
    with sessions() as db:
        job = db.get(Job, job_id)
        reserve_job_units(db, db.get(Client, job.client_id), job)


def _operations(db, job_id: str) -> dict[str, BillingTransaction]:
    return {
        row.operation: row
        for row in db.query(BillingTransaction).filter(BillingTransaction.job_id == job_id).all()
    }


def test_stale_exact_cancellation_cannot_overwrite_a_settled_job(exact_db):
    client_id, job_id = _create_job(exact_db)
    _reserve(exact_db, job_id)

    with exact_db() as stale_cancel_db:
        stale = stale_cancel_db.get(Job, job_id)
        assert stale.status == "running"

        with exact_db() as worker_db:
            assert settle_exact_product_job(worker_db, worker_db.get(Job, job_id), confirmed_count=1)

        assert not cancel_exact_product_job(
            stale_cancel_db,
            stale,
            note="stale cancel",
            message="stale cancel",
        )

    with exact_db() as db:
        client = db.get(Client, client_id)
        assert db.get(Job, job_id).status == "completed"
        assert client.money_balance_kopeks == 90_100
        assert client.money_reserved_kopeks == 0
        assert OP_CHARGE in _operations(db, job_id)


def test_zero_confirmed_exact_results_release_the_reservation(exact_db):
    client_id, job_id = _create_job(exact_db)
    _reserve(exact_db, job_id)

    with exact_db() as db:
        assert not settle_exact_product_job(db, db.get(Job, job_id), confirmed_count=0)

    with exact_db() as db:
        client = db.get(Client, client_id)
        operations = _operations(db, job_id)
        assert db.get(Job, job_id).status == "completed"
        assert client.money_balance_kopeks == 100_000
        assert client.money_reserved_kopeks == 0
        assert OP_CHARGE not in operations
        assert operations[OP_RELEASE].amount_kopeks == 9_900


def test_exact_settlement_keeps_pending_report_metadata(exact_db):
    _client_id, job_id = _create_job(exact_db)
    _reserve(exact_db, job_id)

    with exact_db() as db:
        job = db.get(Job, job_id)
        job.result_path = "/tmp/exact.docx"
        job.evidence_path = "/tmp/exact-evidence.json"
        job.verified_count = 2
        job.yandex_requests_count = 11
        assert settle_exact_product_job(db, job, confirmed_count=2)

    with exact_db() as db:
        job = db.get(Job, job_id)
        assert job.status == "completed"
        assert job.result_path == "/tmp/exact.docx"
        assert job.evidence_path == "/tmp/exact-evidence.json"
        assert job.verified_count == 2
        assert job.yandex_requests_count == 11


def test_stale_unconfirmed_exact_selection_expires_and_releases_its_reserve(exact_db):
    client_id, job_id = _create_job(exact_db, status="awaiting_exact_selection")
    _reserve(exact_db, job_id)
    with exact_db() as db:
        job = db.get(Job, job_id)
        job.updated_at = now_utc() - timedelta(hours=25)
        db.commit()
        assert expire_stale_confirmations(db) == 1

    with exact_db() as db:
        client = db.get(Client, client_id)
        job = db.get(Job, job_id)
        assert job.status == "confirmation_expired"
        assert client.money_reserved_kopeks == 0
        assert OP_RELEASE in _operations(db, job_id)
