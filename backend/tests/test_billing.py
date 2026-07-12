from __future__ import annotations

import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.billing import (
    KIND_MONEY,
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    KIND_SUPPLIER_SEARCH_EXTRA,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    balance_counter,
    charge_job_reservation,
    client_balance_summary,
    client_service_balance_summary,
    client_uses_trial_access,
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
from app.models import Client, Job, TariffPackage, now_utc
from app.models import ClientTariffOverride


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

    def test_trial_balance_uses_base_prices_and_charges_money(self) -> None:
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

            self.assertTrue(client_uses_trial_access(db, client))
            self.assertEqual(client.money_balance_kopeks, 16_000)
            self.assertEqual(balance_counter(db, client, KIND_SUPPLIER_SEARCH)["available"], 1)
            self.assertEqual(balance_counter(db, client, KIND_PROCUREMENT_REPORT)["available"], 1)

            reserve_job_units(db, client, job)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 16_000)
            self.assertEqual(client.money_reserved_kopeks, 6_000)

            charge_job_reservation(db, job)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 10_000)
            self.assertEqual(client.money_reserved_kopeks, 0)
            self.assertEqual(balance_counter(db, client, KIND_SUPPLIER_SEARCH)["available"], 0)
            self.assertEqual(balance_counter(db, client, KIND_PROCUREMENT_REPORT)["available"], 1)
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

    def test_money_grant_top_up_records_balance_without_unit_access(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-topup", telegram_id="102")
            db.add(client)
            db.commit()

            transaction = grant_money_balance(db, client, amount_kopeks=12_300, note="manual topup")
            db.refresh(client)
            payload = transaction_to_dict(transaction)

            self.assertEqual(client.money_balance_kopeks, 12_300)
            self.assertEqual(transaction.kind, KIND_MONEY)
            self.assertEqual(transaction.units, 0)
            self.assertEqual(payload["kind_label"], "Баланс")
            self.assertEqual(balance_counter(db, client, KIND_SUPPLIER_SEARCH)["available"], 0)
            self.assertEqual(balance_counter(db, client, KIND_PROCUREMENT_REPORT)["available"], 0)
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

    def test_unit_balance_works_with_price_and_no_money_balance(self) -> None:
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

            reserve_job_units(db, client, job)
            charge_job_reservation(db, job)
            db.refresh(client)
            counter = balance_counter(db, client, KIND_SUPPLIER_SEARCH)

            self.assertEqual(counter["available"], 0)
            self.assertEqual(counter["spent"], 1)
            self.assertEqual(client.money_balance_kopeks, 0)
        finally:
            db.close()

    def test_money_grant_for_report_is_not_spent_on_supplier_search(self) -> None:
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
            self.assertEqual(client.money_balance_kopeks, 6000)

            reserve_job_units(db, client, report_job)
            charge_job_reservation(db, report_job)
            db.refresh(client)
            self.assertEqual(client.money_balance_kopeks, 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
