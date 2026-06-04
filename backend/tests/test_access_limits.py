from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

import app.db as app_db
from app.db import Base
from app.jobs import MODE_ANALYSIS_AND_SUPPLIERS, MODE_PROCUREMENT_REPORT, MODE_SUPPLIER_SEARCH
from app.models import Client, ClientTelegramAccount, Job, SystemSettings
from app.repository import client_access_error, get_client_by_telegram_id, get_or_create_trial_client_by_telegram_id


class AccessLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def test_multiple_telegram_accounts_share_customer_supplier_limit(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="client-1",
                telegram_id="100",
                name="Customer",
                monthly_supplier_search_limit=1,
                monthly_procurement_report_limit=10,
                allowed_procurement_report=True,
            )
            db.add(client)
            db.add(ClientTelegramAccount(client_id="client-1", telegram_id="100"))
            db.add(ClientTelegramAccount(client_id="client-1", telegram_id="200"))
            db.add(Job(client_id="client-1", mode=MODE_SUPPLIER_SEARCH, file_count=1))
            db.commit()

            resolved, account_error = get_client_by_telegram_id(db, "200")
            error = account_error or client_access_error(db, resolved, MODE_SUPPLIER_SEARCH)

            self.assertEqual(resolved.id, "client-1")
            self.assertIn("лимит поиска поставщиков", error)
        finally:
            db.close()

    def test_analysis_and_suppliers_consumes_both_function_limits(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="client-1",
                telegram_id="100",
                monthly_supplier_search_limit=2,
                monthly_procurement_report_limit=1,
                allowed_procurement_report=True,
            )
            db.add(client)
            db.add(Job(client_id="client-1", mode=MODE_ANALYSIS_AND_SUPPLIERS, file_count=1))
            db.commit()

            supplier_error = client_access_error(db, client, MODE_SUPPLIER_SEARCH)
            report_error = client_access_error(db, client, MODE_PROCUREMENT_REPORT)

            self.assertEqual(supplier_error, "")
            self.assertIn("лимит анализа документации", report_error)
        finally:
            db.close()

    def test_mass_supplier_request_checks_each_tz_against_supplier_limit(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100", monthly_supplier_search_limit=3)
            db.add(client)
            db.add(Job(client_id="client-1", mode=MODE_SUPPLIER_SEARCH, file_count=1))
            db.commit()

            self.assertEqual(client_access_error(db, client, MODE_SUPPLIER_SEARCH, supplier_search_count=2), "")
            error = client_access_error(db, client, MODE_SUPPLIER_SEARCH, supplier_search_count=3)

            self.assertIn("лимит поиска поставщиков", error)
        finally:
            db.close()

    def test_trial_client_is_created_with_configured_separate_limits(self) -> None:
        db = self.Session()
        try:
            db.add(
                SystemSettings(
                    id=1,
                    trial_enabled=True,
                    trial_supplier_search_limit=2,
                    trial_procurement_report_limit=1,
                    trial_file_limit=5,
                )
            )
            db.commit()

            client, account_error = get_or_create_trial_client_by_telegram_id(
                db,
                "555",
                username="buyer",
                name="Buyer One",
            )

            self.assertEqual(account_error, "")
            self.assertTrue(client.is_trial)
            self.assertEqual(client.monthly_supplier_search_limit, 2)
            self.assertEqual(client.monthly_procurement_report_limit, 1)
            self.assertEqual(len(client.telegram_accounts), 1)
            self.assertEqual(client.telegram_accounts[0].telegram_id, "555")
        finally:
            db.close()

    def test_file_count_is_not_a_commercial_access_limit(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="client-1",
                telegram_id="100",
                monthly_supplier_search_limit=10,
                monthly_file_limit=0,
            )
            db.add(client)
            db.commit()

            error = client_access_error(db, client, MODE_SUPPLIER_SEARCH, incoming_file_count=5)

            self.assertEqual(error, "")
        finally:
            db.close()

    def test_trial_rejects_combined_and_mass_supplier_modes(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="trial-1",
                telegram_id="555",
                is_trial=True,
                monthly_supplier_search_limit=10,
                monthly_procurement_report_limit=10,
                allowed_procurement_report=True,
            )
            db.add(client)
            db.commit()

            combined_error = client_access_error(db, client, MODE_ANALYSIS_AND_SUPPLIERS)
            mass_error = client_access_error(db, client, MODE_SUPPLIER_SEARCH, supplier_search_count=2)
            single_error = client_access_error(db, client, MODE_SUPPLIER_SEARCH, supplier_search_count=1)

            self.assertIn("Анализ + поставщики", combined_error)
            self.assertIn("массовая обработка", mass_error)
            self.assertEqual(single_error, "")
        finally:
            db.close()

    def test_disabled_telegram_account_denies_access_before_customer_limits(self) -> None:
        db = self.Session()
        try:
            db.add(Client(id="client-1", telegram_id="100", monthly_supplier_search_limit=10))
            db.add(ClientTelegramAccount(client_id="client-1", telegram_id="200", is_active=False))
            db.commit()

            client, account_error = get_client_by_telegram_id(db, "200")

            self.assertEqual(client.id, "client-1")
            self.assertIn("Telegram-аккаунт отключён", account_error)
        finally:
            db.close()

    def test_init_db_migrates_legacy_clients_to_separate_function_limits_and_accounts(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE clients (
                        id VARCHAR(32) PRIMARY KEY,
                        telegram_id VARCHAR(64) UNIQUE,
                        name VARCHAR(255) DEFAULT '',
                        username VARCHAR(255) DEFAULT '',
                        is_active BOOLEAN DEFAULT 1,
                        access_until VARCHAR(32) DEFAULT '',
                        allowed_supplier_search BOOLEAN DEFAULT 1,
                        allowed_procurement_report BOOLEAN DEFAULT 0,
                        monthly_job_limit INTEGER DEFAULT 100,
                        monthly_file_limit INTEGER DEFAULT 300,
                        notes TEXT DEFAULT '',
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO clients (
                        id,
                        telegram_id,
                        name,
                        username,
                        monthly_job_limit,
                        monthly_file_limit,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        'client-1',
                        '123',
                        'Legacy customer',
                        'buyer',
                        7,
                        21,
                        '2026-06-01T00:00:00',
                        '2026-06-01T00:00:00'
                    )
                    """
                )
            )
        original_engine = app_db.engine
        try:
            app_db.engine = engine
            app_db.init_db()
            inspector = inspect(engine)
            client_columns = {column["name"] for column in inspector.get_columns("clients")}
            self.assertIn("is_trial", client_columns)
            self.assertIn("monthly_supplier_search_limit", client_columns)
            self.assertIn("monthly_procurement_report_limit", client_columns)
            with engine.connect() as connection:
                row = connection.execute(
                    text(
                        """
                        SELECT
                            monthly_supplier_search_limit,
                            monthly_procurement_report_limit
                        FROM clients
                        WHERE id = 'client-1'
                        """
                    )
                ).one()
                account_count = connection.execute(text("SELECT count(*) FROM client_telegram_accounts WHERE telegram_id = '123'")).scalar_one()
            self.assertEqual(row.monthly_supplier_search_limit, 7)
            self.assertEqual(row.monthly_procurement_report_limit, 7)
            self.assertEqual(account_count, 1)
        finally:
            app_db.engine = original_engine


if __name__ == "__main__":
    unittest.main()
