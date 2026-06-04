from __future__ import annotations

import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.billing import (
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    balance_counter,
    charge_job_reservation,
    client_balance_summary,
    expire_stale_confirmations,
    grant_package_units,
    job_has_unsettled_reservation,
    release_job_reservation,
    reserve_job_units,
)
from app.db import Base
from app.models import Client, Job, now_utc


class BillingLedgerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
