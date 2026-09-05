from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.billing import (
    KIND_MONEY,
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    KIND_SUPPLIER_SEARCH_EXTRA,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    BillingError,
    OP_CHARGE,
    OP_GRANT,
    OP_MANUAL_DEBIT,
    OP_RESERVE,
    access_error_for_units,
    balance_counter,
    charge_job_reservation,
    client_balance_summary,
    client_service_balance_summary,
    client_uses_trial_access,
    debit_money_balance,
    debit_package_units,
    effective_price_kopeks,
    expire_stale_confirmations,
    grant_money_balance,
    grant_package_units,
    grant_trial_balance,
    job_has_unsettled_reservation,
    release_job_reservation,
    reserve_job_units,
    transaction_to_dict,
)
from app.db import Base
from app.models import BillingTransaction, Client, Job, TariffPackage, now_utc
from app.models import ClientTariffOverride


class BillingLedgerTests(unittest.TestCase):
    def test_concurrent_jobs_cannot_reserve_the_same_last_money(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_engine(
                f"sqlite:///{Path(tmp) / 'billing.db'}",
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            setup = Session()
            try:
                client = Client(id="client-money-race", telegram_id="race", money_balance_kopeks=6_000)
                setup.add_all(
                    [
                        client,
                        Job(id="job-money-race-1", client_id=client.id, mode="supplier_search"),
                        Job(id="job-money-race-2", client_id=client.id, mode="supplier_search"),
                        ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
                    ]
                )
                setup.commit()
            finally:
                setup.close()

            barrier = threading.Barrier(2)
            outcomes: list[str] = []

            def reserve(job_id: str) -> None:
                db = Session()
                try:
                    client = db.get(Client, "client-money-race")
                    job = db.get(Job, job_id)
                    barrier.wait(timeout=5)
                    try:
                        reserve_job_units(db, client, job)
                        outcomes.append("reserved")
                    except BillingError:
                        outcomes.append("blocked")
                finally:
                    db.close()

            threads = [
                threading.Thread(target=reserve, args=(job_id,))
                for job_id in ("job-money-race-1", "job-money-race-2")
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

            verify = Session()
            try:
                client = verify.get(Client, "client-money-race")
                reserve_rows = (
                    verify.query(BillingTransaction)
                    .filter(BillingTransaction.client_id == client.id)
                    .filter(BillingTransaction.operation == OP_RESERVE)
                    .all()
                )
                reserved_money = client.money_reserved_kopeks
            finally:
                verify.close()

        self.assertEqual(sorted(outcomes), ["blocked", "reserved"])
        self.assertEqual(len(reserve_rows), 1)
        self.assertEqual(reserve_rows[0].amount_kopeks, 6_000)
        self.assertEqual(reserved_money, 6_000)

    def test_concurrent_money_grants_do_not_overwrite_each_other(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_engine(
                f"sqlite:///{Path(tmp) / 'billing-grants.db'}",
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            setup = Session()
            try:
                setup.add(Client(id="client-grant-race", telegram_id="grant-race"))
                setup.commit()
            finally:
                setup.close()

            barrier = threading.Barrier(2)
            errors: list[Exception] = []

            def grant() -> None:
                db = Session()
                try:
                    client = db.get(Client, "client-grant-race")
                    barrier.wait(timeout=5)
                    grant_money_balance(db, client, amount_kopeks=10_000)
                except Exception as exc:  # pragma: no cover - failure is asserted below
                    errors.append(exc)
                finally:
                    db.close()

            threads = [threading.Thread(target=grant) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

            verify = Session()
            try:
                client = verify.get(Client, "client-grant-race")
                grants = (
                    verify.query(BillingTransaction)
                    .filter(BillingTransaction.client_id == client.id)
                    .filter(BillingTransaction.kind == KIND_MONEY)
                    .filter(BillingTransaction.operation == OP_GRANT)
                    .all()
                )
                balance = client.money_balance_kopeks
            finally:
                verify.close()

        self.assertEqual(errors, [])
        self.assertEqual(len(grants), 2)
        self.assertEqual(balance, 20_000)

    def test_concurrent_money_debits_cannot_overdraw_balance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_engine(
                f"sqlite:///{Path(tmp) / 'billing-debits.db'}",
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            setup = Session()
            try:
                setup.add(
                    Client(
                        id="client-debit-race",
                        telegram_id="debit-race",
                        money_balance_kopeks=10_000,
                    )
                )
                setup.commit()
            finally:
                setup.close()

            barrier = threading.Barrier(2)
            outcomes: list[str] = []

            def debit() -> None:
                db = Session()
                try:
                    client = db.get(Client, "client-debit-race")
                    barrier.wait(timeout=5)
                    try:
                        debit_money_balance(db, client, amount_kopeks=6_000)
                        outcomes.append("debited")
                    except BillingError:
                        outcomes.append("blocked")
                finally:
                    db.close()

            threads = [threading.Thread(target=debit) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

            verify = Session()
            try:
                client = verify.get(Client, "client-debit-race")
                debits = (
                    verify.query(BillingTransaction)
                    .filter(BillingTransaction.client_id == client.id)
                    .filter(BillingTransaction.operation == OP_MANUAL_DEBIT)
                    .all()
                )
                balance = client.money_balance_kopeks
            finally:
                verify.close()

        self.assertEqual(sorted(outcomes), ["blocked", "debited"])
        self.assertEqual(len(debits), 1)
        self.assertEqual(balance, 4_000)

    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def test_grant_reserve_charge_updates_non_expiring_balance(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100")
            job = Job(id="job-1", client_id="client-1", mode="supplier_search")
            db.add_all([client, job])
            db.commit()

            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=3, note="paid")
            reserve_job_units(db, client, job)

            reserved = balance_counter(db, client, KIND_SUPPLIER_SEARCH)
            self.assertEqual(reserved["available"], 2)
            self.assertEqual(reserved["reserved"], 1)

            charge_job_reservation(db, job)
            charged = balance_counter(db, client, KIND_SUPPLIER_SEARCH)

            self.assertEqual(charged["available"], 2)
            self.assertEqual(charged["reserved"], 0)
            self.assertEqual(charged["spent"], 1)
        finally:
            db.close()

    def test_supplier_search_result_surplus_does_not_add_billing_units(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-surplus", telegram_id="101")
            job = Job(
                id="job-surplus",
                client_id="client-surplus",
                mode="supplier_search",
                target_suppliers=3,
                verified_count=12,
            )
            db.add_all([client, job])
            db.commit()

            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1, note="paid search")
            reserve_job_units(db, client, job)
            charge_job_reservation(db, job)

            counter = balance_counter(db, client, KIND_SUPPLIER_SEARCH)
            self.assertEqual(counter["available"], 0)
            self.assertEqual(counter["spent"], 1)
        finally:
            db.close()

    def test_manual_grant_lifts_trial_access_for_paid_client(self) -> None:
        db = self.Session()
        try:
            client = Client(id="trial-1", telegram_id="100", is_trial=True)
            db.add(client)
            db.commit()

            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1, created_by="admin")
            db.refresh(client)

            self.assertTrue(client.is_trial)
            self.assertFalse(client_uses_trial_access(db, client))
        finally:
            db.close()

    def test_trial_balance_is_cash_only_and_charges_money(self) -> None:
        db = self.Session()
        try:
            client = Client(id="trial-money", telegram_id="100", is_trial=True)
            job = Job(id="job-1", client_id="trial-money", mode="supplier_search")
            db.add_all([
                client,
                job,
                TariffPackage(kind=KIND_SUPPLIER_SEARCH, name="Поиск", units=1, price_kopeks=6_000, is_active=True),
                TariffPackage(kind=KIND_PROCUREMENT_REPORT, name="Анализ", units=1, price_kopeks=10_000, is_active=True),
            ])
            db.commit()

            grant_trial_balance(db, client, supplier_search_units=1, procurement_report_units=1)
            db.commit()
            db.refresh(client)

            grant_trial_balance(db, client, supplier_search_units=1, procurement_report_units=1)
            db.commit()
            db.refresh(client)

            self.assertTrue(client_uses_trial_access(db, client))
            self.assertEqual(client.money_balance_kopeks, 16_000)
            trial_grants = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.client_id == client.id)
                .filter(BillingTransaction.operation == OP_GRANT)
                .all()
            )
            self.assertEqual(len(trial_grants), 2)
            self.assertTrue(all(item.kind == KIND_MONEY for item in trial_grants))
            self.assertTrue(all(item.units == 0 for item in trial_grants))
            self.assertEqual(sum(item.amount_kopeks for item in trial_grants), 16_000)
            self.assertEqual(balance_counter(db, client, KIND_SUPPLIER_SEARCH)["available"], 0)
            self.assertEqual(balance_counter(db, client, KIND_PROCUREMENT_REPORT)["available"], 0)

            reserve_job_units(db, client, job)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 16_000)
            self.assertEqual(client.money_reserved_kopeks, 6_000)

            charge_job_reservation(db, job)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 10_000)
            self.assertEqual(client.money_reserved_kopeks, 0)
            self.assertEqual(balance_counter(db, client, KIND_SUPPLIER_SEARCH)["available"], 0)
            self.assertEqual(balance_counter(db, client, KIND_PROCUREMENT_REPORT)["available"], 0)
        finally:
            db.close()

    def test_paid_service_does_not_use_legacy_units_without_money(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="client-paid-legacy",
                telegram_id="paid-legacy",
                monthly_supplier_search_limit=10,
            )
            job = Job(id="job-paid-legacy", client_id=client.id, mode="supplier_search")
            db.add_all([
                client,
                job,
                ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
            ])
            db.commit()

            error = access_error_for_units(db, client, {KIND_SUPPLIER_SEARCH: 1})
            self.assertIn("Недостаточно средств", error)
            with self.assertRaises(BillingError):
                reserve_job_units(db, client, job)
            self.assertFalse(
                db.query(BillingTransaction.id)
                .filter(BillingTransaction.job_id == job.id)
                .filter(BillingTransaction.operation == OP_RESERVE)
                .first()
            )
        finally:
            db.close()

    def test_unused_legacy_trial_units_are_reissued_as_money(self) -> None:
        db = self.Session()
        try:
            client = Client(id="trial-legacy-units", telegram_id="trial-legacy-units", is_trial=True)
            db.add_all([
                client,
                TariffPackage(kind=KIND_SUPPLIER_SEARCH, name="Поиск", units=1, price_kopeks=6_000, is_active=True),
                TariffPackage(kind=KIND_PROCUREMENT_REPORT, name="Анализ", units=1, price_kopeks=10_000, is_active=True),
                BillingTransaction(
                    client_id=client.id,
                    kind=KIND_SUPPLIER_SEARCH,
                    operation=OP_GRANT,
                    units=1,
                    amount_kopeks=0,
                    created_by="system",
                ),
            ])
            db.commit()

            grant_trial_balance(db, client, supplier_search_units=1, procurement_report_units=1)
            db.commit()
            db.refresh(client)

            money_grants = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.client_id == client.id)
                .filter(BillingTransaction.kind == KIND_MONEY)
                .filter(BillingTransaction.operation == OP_GRANT)
                .all()
            )
            self.assertEqual(sum(item.amount_kopeks for item in money_grants), 16_000)
            self.assertEqual(client.money_balance_kopeks, 16_000)
        finally:
            db.close()

    def test_paid_service_reserves_full_price_even_with_granted_units(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-paid-units", telegram_id="paid-units", money_balance_kopeks=6_000)
            job = Job(id="job-paid-units", client_id=client.id, mode="supplier_search")
            db.add_all([
                client,
                job,
                ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
                BillingTransaction(
                    client_id=client.id,
                    kind=KIND_SUPPLIER_SEARCH,
                    operation=OP_GRANT,
                    units=10,
                    amount_kopeks=0,
                    created_by="system",
                ),
            ])
            db.commit()

            reserve_job_units(db, client, job)
            db.refresh(client)
            reserve = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.job_id == job.id)
                .filter(BillingTransaction.operation == OP_RESERVE)
                .one()
            )

            self.assertEqual(reserve.amount_kopeks, 6_000)
            self.assertEqual(client.money_reserved_kopeks, 6_000)
        finally:
            db.close()

    def test_disabled_client_tariff_cannot_fall_back_to_legacy_units(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-disabled", telegram_id="disabled", monthly_supplier_search_limit=10)
            job = Job(id="job-disabled", client_id=client.id, mode="supplier_search")
            db.add_all([
                client,
                job,
                ClientTariffOverride(
                    client_id=client.id,
                    kind=KIND_SUPPLIER_SEARCH,
                    price_kopeks=0,
                    is_enabled=False,
                ),
            ])
            db.commit()

            with self.assertRaises(BillingError) as raised:
                reserve_job_units(db, client, job)

            self.assertIn("отключена", str(raised.exception))
        finally:
            db.close()

    def test_repeated_reserve_for_same_paid_job_is_idempotent(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-reserve-repeat", telegram_id="reserve-repeat", money_balance_kopeks=6_000)
            job = Job(id="job-reserve-repeat", client_id=client.id, mode="supplier_search")
            db.add_all([
                client,
                job,
                ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
            ])
            db.commit()

            reserve_job_units(db, client, job)
            reserve_job_units(db, client, job)
            db.refresh(client)

            reserves = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.job_id == job.id)
                .filter(BillingTransaction.operation == OP_RESERVE)
                .all()
            )
            self.assertEqual(len(reserves), 1)
            self.assertEqual(reserves[0].amount_kopeks, 6_000)
            self.assertEqual(client.money_reserved_kopeks, 6_000)
        finally:
            db.close()

    def test_manual_debit_reduces_available_without_counting_as_job_spend(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100")
            db.add(client)
            db.commit()

            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=5)
            debit_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=2, note="wrong client correction")
            counter = balance_counter(db, client, KIND_SUPPLIER_SEARCH)

            self.assertEqual(counter["granted"], 5)
            self.assertEqual(counter["manual_debited"], 2)
            self.assertEqual(counter["available"], 3)
            self.assertEqual(counter["spent"], 0)
        finally:
            db.close()

    def test_manual_debit_by_amount_reduces_money_without_unit_balance(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-money", telegram_id="101", money_balance_kopeks=10_000)
            db.add(client)
            db.commit()

            transaction = debit_package_units(
                db,
                client,
                kind=KIND_SUPPLIER_SEARCH,
                units=1,
                amount_kopeks=3_000,
                note="balance correction",
            )
            db.refresh(client)

            self.assertEqual(transaction.amount_kopeks, 3_000)
            self.assertEqual(client.money_balance_kopeks, 7_000)
            self.assertEqual(balance_counter(db, client, KIND_SUPPLIER_SEARCH)["available"], 0)
        finally:
            db.close()

    def test_money_grant_top_up_pays_for_service_at_effective_price(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-topup", telegram_id="102")
            job = Job(id="job-topup", client_id=client.id, mode="supplier_search")
            db.add_all([
                client,
                job,
                ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
            ])
            db.commit()

            transaction = grant_money_balance(db, client, amount_kopeks=12_300, note="manual topup")
            reserve_job_units(db, client, job)
            charge_job_reservation(db, job)
            db.refresh(client)
            payload = transaction_to_dict(transaction)

            self.assertEqual(client.money_balance_kopeks, 6_300)
            self.assertEqual(client.money_reserved_kopeks, 0)
            self.assertEqual(transaction.kind, KIND_MONEY)
            self.assertEqual(transaction.units, 0)
            self.assertEqual(payload["kind_label"], "Баланс")
        finally:
            db.close()

    def test_money_balance_is_used_after_legacy_units_are_exhausted(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-money-fallback", telegram_id="103", money_balance_kopeks=600_000)
            job = Job(id="job-money-fallback", client_id=client.id, mode="supplier_search")
            db.add_all([
                client,
                job,
                ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
                BillingTransaction(
                    client_id=client.id,
                    kind=KIND_SUPPLIER_SEARCH,
                    operation=OP_GRANT,
                    units=1,
                    created_by="admin",
                ),
                BillingTransaction(
                    client_id=client.id,
                    kind=KIND_SUPPLIER_SEARCH,
                    operation=OP_RESERVE,
                    units=1,
                    created_by="system",
                ),
                BillingTransaction(
                    client_id=client.id,
                    kind=KIND_SUPPLIER_SEARCH,
                    operation=OP_CHARGE,
                    units=1,
                    created_by="system",
                ),
            ])
            db.commit()

            self.assertEqual(access_error_for_units(db, client, {KIND_SUPPLIER_SEARCH: 1}), "")
            reserve_job_units(db, client, job)
            db.refresh(client)
            self.assertEqual(client.money_reserved_kopeks, 6_000)

            charge_job_reservation(db, job)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 594_000)
            self.assertEqual(client.money_reserved_kopeks, 0)
        finally:
            db.close()

    def test_failed_job_releases_reserved_units(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100")
            job = Job(id="job-1", client_id="client-1", mode="procurement_report")
            db.add_all([client, job])
            db.commit()

            grant_package_units(db, client, kind=KIND_PROCUREMENT_REPORT, units=1)
            reserve_job_units(db, client, job)
            release_job_reservation(db, job, note="failed")

            counter = balance_counter(db, client, KIND_PROCUREMENT_REPORT)
            self.assertEqual(counter["available"], 1)
            self.assertEqual(counter["reserved"], 0)
            self.assertEqual(counter["spent"], 0)
        finally:
            db.close()

    def test_unsettled_reservation_marks_result_as_recoverable_until_charge(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100")
            job = Job(id="job-1", client_id="client-1", mode="supplier_search", status="completed")
            db.add_all([client, job])
            db.commit()

            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
            reserve_job_units(db, client, job)

            self.assertTrue(job_has_unsettled_reservation(db, job))

            charge_job_reservation(db, job)

            self.assertFalse(job_has_unsettled_reservation(db, job))
        finally:
            db.close()

    def test_legacy_monthly_limit_is_initialized_on_first_reserve(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100", monthly_supplier_search_limit=2)
            job = Job(id="job-1", client_id="client-1", mode="supplier_search")
            db.add_all([client, job])
            db.commit()

            reserve_job_units(db, client, job)
            summary = client_balance_summary(db, client)

            self.assertEqual(summary[KIND_SUPPLIER_SEARCH]["source"], "ledger")
            self.assertEqual(summary[KIND_SUPPLIER_SEARCH]["available"], 1)
            self.assertEqual(summary[KIND_SUPPLIER_SEARCH]["reserved"], 1)
        finally:
            db.close()

    def test_stale_partial_confirmation_releases_reserve(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100")
            job = Job(
                id="job-1",
                client_id="client-1",
                mode="supplier_search",
                status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
                updated_at=now_utc() - timedelta(hours=25),
            )
            db.add_all([client, job])
            db.commit()

            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
            reserve_job_units(db, client, job)
            expired = expire_stale_confirmations(db, older_than=timedelta(hours=24))
            db.refresh(job)
            counter = balance_counter(db, client, KIND_SUPPLIER_SEARCH)

            self.assertEqual(expired, 1)
            self.assertEqual(job.status, STATUS_CONFIRMATION_EXPIRED)
            self.assertEqual(counter["available"], 1)
            self.assertEqual(counter["reserved"], 0)
        finally:
            db.close()

    def test_stale_accepted_partial_without_download_releases_reserve(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-partial", telegram_id="101")
            job = Job(
                id="job-partial",
                client_id=client.id,
                mode="supplier_search",
                status="partial",
                updated_at=now_utc() - timedelta(hours=25),
            )
            db.add_all([client, job])
            db.commit()
            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
            reserve_job_units(db, client, job)

            expired = expire_stale_confirmations(db, older_than=timedelta(hours=24))

            self.assertEqual(expired, 1)
            self.assertEqual(job.status, STATUS_CONFIRMATION_EXPIRED)
            self.assertEqual(balance_counter(db, client, KIND_SUPPLIER_SEARCH)["available"], 1)
        finally:
            db.close()

    def test_downloaded_partial_is_not_expired_or_refunded(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-downloaded", telegram_id="102")
            job = Job(
                id="job-downloaded",
                client_id=client.id,
                mode="supplier_search",
                status="partial",
                updated_at=now_utc() - timedelta(hours=25),
            )
            db.add_all([client, job])
            db.commit()
            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
            reserve_job_units(db, client, job)
            charge_job_reservation(db, job)

            expired = expire_stale_confirmations(db, older_than=timedelta(hours=24))

            self.assertEqual(expired, 0)
            self.assertEqual(job.status, "partial")
            self.assertEqual(balance_counter(db, client, KIND_SUPPLIER_SEARCH)["available"], 0)
        finally:
            db.close()

    def test_balance_summary_does_not_convert_units_to_money_on_read(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100", monthly_supplier_search_limit=3)
            db.add_all([
                client,
                ClientTariffOverride(client_id="client-1", kind=KIND_SUPPLIER_SEARCH, price_kopeks=6000),
            ])
            db.commit()

            summary = client_balance_summary(db, client)
            db.refresh(client)

            self.assertEqual(summary["money"]["available_kopeks"], 0)
            self.assertEqual(client.money_balance_kopeks, 0)
            self.assertEqual(summary[KIND_SUPPLIER_SEARCH]["available"], 3)
        finally:
            db.close()

    def test_service_balance_summary_defaults_extra_search_to_half_supplier_price(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="client-1",
                telegram_id="100",
                monthly_supplier_search_limit=1000,
                monthly_procurement_report_limit=1000,
                money_balance_kopeks=9_940_000,
            )
            db.add_all([
                client,
                TariffPackage(kind=KIND_SUPPLIER_SEARCH, name="Поиск", units=1, price_kopeks=10_000, is_active=True),
                TariffPackage(kind=KIND_PROCUREMENT_REPORT, name="Анализ", units=1, price_kopeks=10_000, is_active=True),
            ])
            db.commit()

            raw = client_balance_summary(db, client)
            display = client_service_balance_summary(db, client)

            self.assertTrue(raw[KIND_SUPPLIER_SEARCH_EXTRA]["low"])
            self.assertEqual(raw[KIND_SUPPLIER_SEARCH_EXTRA]["available"], 0)
            self.assertEqual(display[KIND_SUPPLIER_SEARCH_EXTRA]["source"], "supplier_search_access_fallback")
            self.assertEqual(display[KIND_SUPPLIER_SEARCH_EXTRA]["fallback_kind"], KIND_SUPPLIER_SEARCH)
            self.assertEqual(display[KIND_SUPPLIER_SEARCH_EXTRA]["available"], 1000)
            self.assertEqual(display[KIND_SUPPLIER_SEARCH_EXTRA]["price_kopeks"], 5_000)
            self.assertFalse(display[KIND_SUPPLIER_SEARCH_EXTRA]["low"])
            self.assertEqual(
                display["effective_prices"][KIND_SUPPLIER_SEARCH_EXTRA]["source"],
                "supplier_search_default_50_percent",
            )
        finally:
            db.close()

    def test_extra_search_override_keeps_individual_half_price_contract(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100")
            db.add_all([
                client,
                ClientTariffOverride(client_id="client-1", kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
                ClientTariffOverride(client_id="client-1", kind=KIND_SUPPLIER_SEARCH_EXTRA, price_kopeks=3_000),
            ])
            db.commit()

            self.assertEqual(effective_price_kopeks(db, client, KIND_SUPPLIER_SEARCH), 6_000)
            self.assertEqual(effective_price_kopeks(db, client, KIND_SUPPLIER_SEARCH_EXTRA), 3_000)
            summary = client_service_balance_summary(db, client)
            self.assertEqual(summary["effective_prices"][KIND_SUPPLIER_SEARCH_EXTRA]["source"], "client_override")
            self.assertEqual(summary[KIND_SUPPLIER_SEARCH_EXTRA]["price_kopeks"], 3_000)
        finally:
            db.close()

    def test_additional_supplier_search_reserves_half_price_from_supplier_access(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100")
            job = Job(
                id="job-extra",
                client_id="client-1",
                mode="supplier_search",
                supplier_search_run_type="additional",
            )
            db.add_all([
                client,
                job,
                ClientTariffOverride(client_id="client-1", kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
            ])
            db.commit()
            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=2, amount_kopeks=12_000)

            reserve_job_units(db, client, job)
            db.refresh(client)
            reserved = client_service_balance_summary(db, client)

            self.assertEqual(reserved[KIND_SUPPLIER_SEARCH_EXTRA]["available"], 1)
            self.assertEqual(reserved[KIND_SUPPLIER_SEARCH_EXTRA]["reserved"], 1)
            self.assertEqual(reserved[KIND_SUPPLIER_SEARCH_EXTRA]["price_kopeks"], 3_000)
            self.assertEqual(client.money_reserved_kopeks, 3_000)

            charge_job_reservation(db, job)
            db.refresh(client)
            charged = client_service_balance_summary(db, client)

            self.assertEqual(client.money_balance_kopeks, 9_000)
            self.assertEqual(client.money_reserved_kopeks, 0)
            self.assertEqual(charged[KIND_SUPPLIER_SEARCH_EXTRA]["available"], 1)
            self.assertEqual(charged[KIND_SUPPLIER_SEARCH_EXTRA]["spent"], 1)
        finally:
            db.close()

    def test_unit_balance_cannot_pay_for_priced_service(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100", monthly_supplier_search_limit=1)
            job = Job(id="job-1", client_id="client-1", mode="supplier_search")
            db.add_all([
                client,
                job,
                ClientTariffOverride(client_id="client-1", kind=KIND_SUPPLIER_SEARCH, price_kopeks=6000),
            ])
            db.commit()

            with self.assertRaises(BillingError):
                reserve_job_units(db, client, job)
            db.refresh(client)
            counter = balance_counter(db, client, KIND_SUPPLIER_SEARCH)

            self.assertEqual(counter["available"], 1)
            self.assertEqual(counter["spent"], 0)
            self.assertEqual(client.money_balance_kopeks, 0)
        finally:
            db.close()

    def test_common_money_balance_is_fungible_across_services(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100")
            supplier_job = Job(id="supplier-job", client_id="client-1", mode="supplier_search")
            report_job = Job(id="report-job", client_id="client-1", mode="procurement_report")
            db.add_all([client, supplier_job, report_job])
            db.commit()

            grant_package_units(db, client, kind=KIND_SUPPLIER_SEARCH, units=1)
            db.add_all([
                ClientTariffOverride(client_id="client-1", kind=KIND_SUPPLIER_SEARCH, price_kopeks=6000),
                ClientTariffOverride(client_id="client-1", kind=KIND_PROCUREMENT_REPORT, price_kopeks=6000),
            ])
            db.commit()
            grant_package_units(db, client, kind=KIND_PROCUREMENT_REPORT, units=1, amount_kopeks=6000)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 6000)

            reserve_job_units(db, client, supplier_job)
            charge_job_reservation(db, supplier_job)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 0)

            with self.assertRaises(BillingError):
                reserve_job_units(db, client, report_job)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
