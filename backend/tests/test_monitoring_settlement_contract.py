from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import billing
from app.billing import (
    BillingError,
    KIND_PRICE_MONITORING,
    OP_CHARGE,
    OP_RELEASE,
    OP_RESERVE,
    cancel_price_monitoring_job,
    charge_price_monitoring_job,
    effective_job_unit_price_kopeks,
    expire_stale_confirmations,
    reserve_price_monitoring_job,
)
from app.db import Base
from app.models import BillingTransaction, Client, Job, SystemSettings, now_utc
from app.position_selection import build_selection_snapshot
from app.repository import client_access_error


@pytest.fixture
def settlement_db(tmp_path, monkeypatch):
    database_path = tmp_path / "monitoring-settlement.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(billing.config, "storage_dir", str(tmp_path / "storage"))
    yield sessions
    engine.dispose()


def _create_job(
    sessions,
    *,
    balance: int = 100_000,
    reserved: int = 0,
    status: str = "running",
    geo_radius_km: int | None = None,
    unit_price: int = 10_000,
) -> tuple[str, str]:
    with sessions() as db:
        settings = SystemSettings(
            price_monitoring_default_price_kopeks=unit_price,
            geo_radius_surcharge_pct=30.0,
            geo_radius_search_enabled_global=True,
        )
        client = Client(
            telegram_id=f"monitoring-{balance}-{status}-{geo_radius_km}",
            money_balance_kopeks=balance,
            money_reserved_kopeks=reserved,
            allowed_price_monitoring=True,
        )
        db.add_all([settings, client])
        db.commit()
        job = Job(
            client_id=client.id,
            mode=KIND_PRICE_MONITORING,
            status=status,
            title="Settlement contract",
            geo_radius_km=geo_radius_km,
            delivery_city="Казань" if geo_radius_km else "",
        )
        db.add(job)
        db.commit()
        return client.id, job.id


def _transactions(db, job_id: str) -> dict[str, BillingTransaction]:
    rows = db.query(BillingTransaction).filter(BillingTransaction.job_id == job_id).all()
    return {row.operation: row for row in rows}


def test_reserve_monitoring_max_budget_uses_geo_snapshot_and_is_idempotent(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000, geo_radius_km=100)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        client = db.get(Client, client_id)
        unit_price = effective_job_unit_price_kopeks(db, client, KIND_PRICE_MONITORING, job=job)
        assert unit_price == 13_000

        first = reserve_price_monitoring_job(
            db,
            job,
            total_positions=3,
            price_per_item_kopeks=unit_price,
        )
        second = reserve_price_monitoring_job(
            db,
            job,
            total_positions=3,
            price_per_item_kopeks=unit_price,
        )

        db.refresh(client)
        reserve = _transactions(db, job_id)[OP_RESERVE]
        assert first == second == 39_000
        assert reserve.units == 3
        assert reserve.amount_kopeks == 39_000
        assert client.money_balance_kopeks == 100_000
        assert client.money_reserved_kopeks == 39_000


def test_reserve_monitoring_rejects_insufficient_available_balance_without_mutation(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=25_000, reserved=5_000)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        client = db.get(Client, client_id)

        with pytest.raises(BillingError, match="Недостаточно средств"):
            reserve_price_monitoring_job(
                db,
                job,
                total_positions=3,
                price_per_item_kopeks=10_000,
            )

        db.refresh(client)
        assert client.money_balance_kopeks == 25_000
        assert client.money_reserved_kopeks == 5_000
        assert db.query(BillingTransaction).filter_by(job_id=job_id).count() == 0


def test_charge_monitoring_settles_found_and_releases_unused_reserve_idempotently(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        client = db.get(Client, client_id)
        reserve_price_monitoring_job(db, job, total_positions=3, price_per_item_kopeks=10_000)

        first = charge_price_monitoring_job(
            db,
            job,
            found_count=2,
            price_per_item_kopeks=10_000,
        )
        second = charge_price_monitoring_job(
            db,
            job,
            found_count=99,
            price_per_item_kopeks=99_000,
        )

        db.refresh(client)
        transactions = _transactions(db, job_id)
        assert first == second == 20_000
        assert transactions[OP_CHARGE].units == 2
        assert transactions[OP_CHARGE].amount_kopeks == 20_000
        assert transactions[OP_RELEASE].units == 1
        assert transactions[OP_RELEASE].amount_kopeks == 10_000
        assert client.money_balance_kopeks == 80_000
        assert client.money_reserved_kopeks == 0
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_CHARGE).count() == 1


def test_zero_found_releases_entire_monitoring_reserve(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        client = db.get(Client, client_id)
        reserve_price_monitoring_job(db, job, total_positions=3, price_per_item_kopeks=10_000)

        charged = charge_price_monitoring_job(
            db,
            job,
            found_count=0,
            price_per_item_kopeks=10_000,
        )

        db.refresh(client)
        transactions = _transactions(db, job_id)
        assert charged == 0
        assert OP_CHARGE not in transactions
        assert transactions[OP_RELEASE].units == 3
        assert transactions[OP_RELEASE].amount_kopeks == 30_000
        assert client.money_balance_kopeks == 100_000
        assert client.money_reserved_kopeks == 0


def test_invalid_settlement_input_leaves_a_running_job_available_for_recovery(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        reserve_price_monitoring_job(db, job, total_positions=2, price_per_item_kopeks=10_000)

        with pytest.raises(BillingError, match="превышает исходный резерв"):
            charge_price_monitoring_job(
                db,
                job,
                found_count=3,
                price_per_item_kopeks=10_000,
            )

        db.expire_all()
        client = db.get(Client, client_id)
        assert db.get(Job, job_id).status == "running"
        assert client.money_balance_kopeks == 100_000
        assert client.money_reserved_kopeks == 20_000
        assert OP_CHARGE not in _transactions(db, job_id)


def test_settlement_keeps_unflushed_monitoring_artifacts_before_the_atomic_commit(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        reserve_price_monitoring_job(db, job, total_positions=2, price_per_item_kopeks=10_000)

        # The worker deliberately keeps these output fields uncommitted until
        # settlement, so the result and the ledger become visible together.
        db.autoflush = False
        job.result_path = "/tmp/report.xlsx"
        job.evidence_path = "/tmp/evidence.json"
        job.verified_count = 1
        job.yandex_requests_count = 12
        job.yandex_cost_rub = 3.5
        charge_price_monitoring_job(
            db,
            job,
            found_count=1,
            price_per_item_kopeks=10_000,
        )

    with settlement_db() as check_db:
        client = check_db.get(Client, client_id)
        settled = check_db.get(Job, job_id)
        assert settled.status == "completed"
        assert settled.result_path == "/tmp/report.xlsx"
        assert settled.evidence_path == "/tmp/evidence.json"
        assert settled.verified_count == 1
        assert settled.yandex_requests_count == 12
        assert settled.yandex_cost_rub == 3.5
        assert client.money_balance_kopeks == 90_000


def test_cross_session_cancelled_job_cannot_be_charged(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as setup_db:
        job = setup_db.get(Job, job_id)
        reserve_price_monitoring_job(setup_db, job, total_positions=2, price_per_item_kopeks=10_000)

    with settlement_db() as cancel_db:
        cancelled = cancel_db.get(Job, job_id)
        cancelled.status = "cancelled"
        cancel_db.commit()

    with settlement_db() as worker_db:
        stale_job = worker_db.get(Job, job_id)
        with pytest.raises(BillingError, match="отменена"):
            charge_price_monitoring_job(
                worker_db,
                stale_job,
                found_count=1,
                price_per_item_kopeks=10_000,
            )

    with settlement_db() as check_db:
        client = check_db.get(Client, client_id)
        assert client.money_balance_kopeks == 100_000
        assert client.money_reserved_kopeks == 20_000
        assert check_db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_CHARGE).count() == 0


def test_stale_cancellation_cas_cannot_overwrite_settled_monitoring_job(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as setup_db:
        reserve_price_monitoring_job(
            setup_db,
            setup_db.get(Job, job_id),
            total_positions=2,
            price_per_item_kopeks=10_000,
        )

    # A cancellation request can have read "running" before the worker settles.
    # Its write must still use the status in the database as a compare-and-swap guard.
    with settlement_db() as stale_cancel_db:
        assert stale_cancel_db.get(Job, job_id).status == "running"

        with settlement_db() as worker_db:
            charged = charge_price_monitoring_job(
                worker_db,
                worker_db.get(Job, job_id),
                found_count=1,
                price_per_item_kopeks=10_000,
            )
        assert charged == 10_000

        cancelled_rows = (
            stale_cancel_db.query(Job)
            .filter(Job.id == job_id, Job.status.in_(("pending", "running", "awaiting_customer_confirmation")))
            .update({Job.status: "cancelled"}, synchronize_session=False)
        )
        stale_cancel_db.commit()
        assert cancelled_rows == 0

    with settlement_db() as check_db:
        client = check_db.get(Client, client_id)
        assert check_db.get(Job, job_id).status == "completed"
        assert client.money_balance_kopeks == 90_000
        assert client.money_reserved_kopeks == 0


def test_cancel_helper_rejects_a_stale_session_after_monitoring_settlement(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as setup_db:
        reserve_price_monitoring_job(
            setup_db,
            setup_db.get(Job, job_id),
            total_positions=2,
            price_per_item_kopeks=10_000,
        )

    with settlement_db() as stale_cancel_db:
        stale_job = stale_cancel_db.get(Job, job_id)
        assert stale_job.status == "running"

        with settlement_db() as worker_db:
            charge_price_monitoring_job(
                worker_db,
                worker_db.get(Job, job_id),
                found_count=1,
                price_per_item_kopeks=10_000,
            )

        assert not cancel_price_monitoring_job(
            stale_cancel_db,
            stale_job,
            note="test cancellation",
            message="test cancellation",
        )

    with settlement_db() as check_db:
        client = check_db.get(Client, client_id)
        assert check_db.get(Job, job_id).status == "completed"
        assert client.money_balance_kopeks == 90_000
        assert client.money_reserved_kopeks == 0


def test_cancel_helper_releases_the_monitoring_reserve_with_the_status_change(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        reserve_price_monitoring_job(db, job, total_positions=2, price_per_item_kopeks=10_000)

        assert cancel_price_monitoring_job(
            db,
            job,
            note="Cancelled by test",
            message="Cancelled by test",
        )

        client = db.get(Client, client_id)
        transactions = _transactions(db, job_id)
        assert db.get(Job, job_id).status == "cancelled"
        assert client.money_balance_kopeks == 100_000
        assert client.money_reserved_kopeks == 0
        assert transactions[OP_RELEASE].amount_kopeks == 20_000
        assert OP_CHARGE not in transactions


def test_preview_cancellation_releases_existing_monitoring_reserve(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        reserve_price_monitoring_job(db, job, total_positions=2, price_per_item_kopeks=10_000)
        job.status = "awaiting_position_selection"
        db.commit()

        assert cancel_price_monitoring_job(
            db,
            job,
            note="Preview cancelled by test",
            message="Preview cancelled by test",
        )

        client = db.get(Client, client_id)
        transactions = _transactions(db, job_id)
        assert db.get(Job, job_id).status == "cancelled"
        assert client.money_reserved_kopeks == 0
        assert transactions[OP_RELEASE].amount_kopeks == 20_000


def test_preview_expiry_releases_stale_reserve_but_keeps_fresh_and_confirmed_selection(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as db:
        stale = db.get(Job, job_id)
        reserve_price_monitoring_job(db, stale, total_positions=1, price_per_item_kopeks=10_000)
        stale.status = "awaiting_position_selection"
        stale.position_selection_json = build_selection_snapshot(
            [{"position_no": 1, "name": "Старая позиция"}],
            price_kopeks=10_000,
            mode="price_monitoring",
        )
        stale.updated_at = now_utc() - timedelta(hours=25)

        fresh = Job(
            client_id=client_id,
            mode=KIND_PRICE_MONITORING,
            status="awaiting_position_selection",
            position_selection_json=build_selection_snapshot(
                [{"position_no": 1, "name": "Свежая позиция"}],
                price_kopeks=10_000,
                mode="price_monitoring",
            ),
        )
        confirmed_snapshot = json.loads(build_selection_snapshot(
            [{"position_no": 1, "name": "Подтверждённая позиция"}],
            price_kopeks=10_000,
            mode="price_monitoring",
        ))
        confirmed_snapshot["confirmed"] = True
        confirmed = Job(
            client_id=client_id,
            mode=KIND_PRICE_MONITORING,
            status="awaiting_position_selection",
            position_selection_json=json.dumps(confirmed_snapshot, ensure_ascii=False),
            updated_at=now_utc() - timedelta(hours=25),
        )
        db.add_all([fresh, confirmed])
        db.commit()

        assert expire_stale_confirmations(db) == 1
        db.expire_all()
        client = db.get(Client, client_id)
        assert db.get(Job, stale.id).status == "confirmation_expired"
        assert db.get(Job, fresh.id).status == "awaiting_position_selection"
        assert db.get(Job, confirmed.id).status == "awaiting_position_selection"
        assert client.money_reserved_kopeks == 0
        assert _transactions(db, stale.id)[OP_RELEASE].amount_kopeks == 10_000


def test_legacy_monitoring_charge_requires_sufficient_available_money(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=15_000, reserved=5_000)
    with settlement_db() as db:
        job = db.get(Job, job_id)
        client = db.get(Client, client_id)

        with pytest.raises(BillingError, match="Недостаточно средств"):
            charge_price_monitoring_job(
                db,
                job,
                found_count=2,
                price_per_item_kopeks=10_000,
            )

        db.refresh(client)
        assert client.money_balance_kopeks == 15_000
        assert client.money_reserved_kopeks == 5_000
        assert db.query(BillingTransaction).filter_by(job_id=job_id).count() == 0


def test_concurrent_repeat_charge_returns_existing_and_deducts_once(settlement_db):
    client_id, job_id = _create_job(settlement_db, balance=100_000)
    with settlement_db() as db:
        reserve_price_monitoring_job(
            db,
            db.get(Job, job_id),
            total_positions=2,
            price_per_item_kopeks=10_000,
        )

    def settle() -> int:
        with settlement_db() as db:
            return charge_price_monitoring_job(
                db,
                db.get(Job, job_id),
                found_count=1,
                price_per_item_kopeks=10_000,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        amounts = list(pool.map(lambda _index: settle(), range(2)))

    with settlement_db() as db:
        client = db.get(Client, client_id)
        assert amounts == [10_000, 10_000]
        assert client.money_balance_kopeks == 90_000
        assert client.money_reserved_kopeks == 0
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_CHARGE).count() == 1
        assert db.query(BillingTransaction).filter_by(job_id=job_id, operation=OP_RELEASE).count() == 1


def test_monitoring_access_gate_uses_available_money_and_optional_geo_price(settlement_db):
    client_id, _job_id = _create_job(settlement_db, balance=10_000, reserved=6_000, unit_price=5_000)
    with settlement_db() as db:
        client = db.get(Client, client_id)
        base_error = client_access_error(db, client, KIND_PRICE_MONITORING)
        assert "Доступно 40.0 ₽" in base_error

        client.money_reserved_kopeks = 4_000
        db.commit()
        geo_error = client_access_error(
            db,
            client,
            KIND_PRICE_MONITORING,
            geo_radius_km=100,
        )
        assert "нужно минимум 65.0 ₽" in geo_error
