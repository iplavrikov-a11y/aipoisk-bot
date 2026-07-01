from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

import app.db as app_db
from app.billing import KIND_PROCUREMENT_REPORT, KIND_SUPPLIER_SEARCH, OP_GRANT, client_uses_trial_access
from app.db import Base
from app.jobs import MODE_ANALYSIS_AND_SUPPLIERS, MODE_PROCUREMENT_REPORT, MODE_SUPPLIER_SEARCH
from app.models import BillingTransaction, Client, ClientTelegramAccount, Job, SystemSettings, TariffPackage
from app.repository import (
    client_access_error,
    ensure_pending_client_telegram_account,
    get_client_by_telegram_id,
    get_or_create_trial_client_by_telegram_id,
    is_pending_telegram_id,
    supplier_target_for_client,
)


class AccessLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def test_legacy_settings_schema_adds_supplier_ai_and_yookassa_columns(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        original_engine = app_db.engine
        app_db.engine = engine
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE system_settings (
                            id INTEGER PRIMARY KEY,
                            light_provider VARCHAR(80) DEFAULT '',
                            light_model VARCHAR(160) DEFAULT ''
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO system_settings (id, light_provider, light_model)
                        VALUES (1, 'polza', 'cheap-model')
                        """
                    )
                )
                connection.execute(text("CREATE TABLE clients (id VARCHAR(32) PRIMARY KEY, monthly_job_limit INTEGER DEFAULT 0)"))
                connection.execute(text("CREATE TABLE jobs (id VARCHAR(32) PRIMARY KEY)"))
                connection.execute(text("CREATE TABLE supplier_results (id VARCHAR(32) PRIMARY KEY)"))

            app_db._ensure_schema()
            inspector = inspect(engine)
            settings_columns = {column["name"] for column in inspector.get_columns("system_settings")}
            with engine.connect() as connection:
                row = connection.execute(
                    text("SELECT supplier_ai_provider, supplier_ai_model, payment_provider, yookassa_shop_id, yookassa_secret_key, yookassa_return_url FROM system_settings WHERE id = 1")
                ).mappings().first()
        finally:
            app_db.engine = original_engine

        self.assertIn("supplier_ai_provider", settings_columns)
        self.assertIn("supplier_ai_model", settings_columns)
        self.assertIn("payment_provider", settings_columns)
        self.assertEqual(row["supplier_ai_provider"], "polza")
        self.assertEqual(row["supplier_ai_model"], "cheap-model")
        self.assertEqual(row["payment_provider"], "manual")
        self.assertEqual(row["yookassa_shop_id"], "")
        self.assertEqual(row["yookassa_secret_key"], "")
        self.assertEqual(row["yookassa_return_url"], "")

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
            self.assertIn("Недостаточно генераций", error)
            self.assertIn("Поставщики", error)
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
            self.assertIn("Недостаточно генераций", report_error)
            self.assertIn("Анализ документации", report_error)
        finally:
            db.close()

    def test_balance_enables_functions_without_manual_function_flags(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="client-1",
                telegram_id="100",
                allowed_supplier_search=False,
                allowed_procurement_report=False,
                monthly_supplier_search_limit=2,
                monthly_procurement_report_limit=1,
            )
            db.add(client)
            db.commit()

            supplier_error = client_access_error(db, client, MODE_SUPPLIER_SEARCH)
            report_error = client_access_error(db, client, MODE_PROCUREMENT_REPORT)
            combined_error = client_access_error(db, client, MODE_ANALYSIS_AND_SUPPLIERS)
        finally:
            db.close()

        self.assertEqual(supplier_error, "")
        self.assertEqual(report_error, "")
        self.assertEqual(combined_error, "")

    def test_mass_supplier_request_checks_each_tz_against_supplier_limit(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="100", monthly_supplier_search_limit=3)
            db.add(client)
            db.add(Job(client_id="client-1", mode=MODE_SUPPLIER_SEARCH, file_count=1))
            db.commit()

            self.assertEqual(client_access_error(db, client, MODE_SUPPLIER_SEARCH, supplier_search_count=2), "")
            error = client_access_error(db, client, MODE_SUPPLIER_SEARCH, supplier_search_count=3)

            self.assertIn("Недостаточно генераций", error)
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
            db.add_all([
                TariffPackage(kind=KIND_SUPPLIER_SEARCH, name="Базовый поиск", units=1, price_kopeks=6_000, is_active=True),
                TariffPackage(kind=KIND_PROCUREMENT_REPORT, name="Базовый анализ", units=1, price_kopeks=10_000, is_active=True),
            ])
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
            self.assertEqual(client.money_balance_kopeks, 22_000)
            self.assertTrue(client_uses_trial_access(db, client))
            self.assertEqual(
                db.query(BillingTransaction)
                .filter(BillingTransaction.client_id == client.id)
                .filter(BillingTransaction.operation == OP_GRANT)
                .filter(BillingTransaction.created_by == "system")
                .count(),
                2,
            )
            self.assertEqual(len(client.telegram_accounts), 1)
            self.assertEqual(client.telegram_accounts[0].telegram_id, "555")
        finally:
            db.close()

    def test_existing_unused_trial_client_receives_missing_money_grants(self) -> None:
        db = self.Session()
        try:
            db.add(
                SystemSettings(
                    id=1,
                    trial_enabled=True,
                    trial_supplier_search_limit=1,
                    trial_procurement_report_limit=1,
                    trial_file_limit=5,
                )
            )
            db.add_all([
                TariffPackage(kind=KIND_SUPPLIER_SEARCH, name="Базовый поиск", units=1, price_kopeks=6_000, is_active=True),
                TariffPackage(kind=KIND_PROCUREMENT_REPORT, name="Базовый анализ", units=1, price_kopeks=10_000, is_active=True),
            ])
            client = Client(
                id="client-1",
                telegram_id="555",
                name="Existing trial",
                is_trial=True,
                monthly_supplier_search_limit=1,
                monthly_procurement_report_limit=1,
                money_balance_kopeks=0,
            )
            db.add(client)
            db.add(ClientTelegramAccount(client_id="client-1", telegram_id="555", username="buyer", name="Buyer One"))
            db.commit()

            resolved, account_error = get_or_create_trial_client_by_telegram_id(db, "555", username="buyer", name="Buyer One")

            self.assertEqual(account_error, "")
            self.assertEqual(resolved.id, "client-1")
            self.assertEqual(resolved.money_balance_kopeks, 16_000)
            self.assertEqual(
                db.query(BillingTransaction)
                .filter(BillingTransaction.client_id == "client-1")
                .filter(BillingTransaction.operation == OP_GRANT)
                .filter(BillingTransaction.created_by == "system")
                .count(),
                2,
            )
        finally:
            db.close()

    def test_existing_used_trial_client_does_not_receive_backfill_grants(self) -> None:
        db = self.Session()
        try:
            db.add(
                SystemSettings(
                    id=1,
                    trial_enabled=True,
                    trial_supplier_search_limit=1,
                    trial_procurement_report_limit=1,
                    trial_file_limit=5,
                )
            )
            db.add_all([
                TariffPackage(kind=KIND_SUPPLIER_SEARCH, name="Базовый поиск", units=1, price_kopeks=6_000, is_active=True),
                TariffPackage(kind=KIND_PROCUREMENT_REPORT, name="Базовый анализ", units=1, price_kopeks=10_000, is_active=True),
            ])
            client = Client(
                id="client-1",
                telegram_id="555",
                name="Existing trial",
                is_trial=True,
                monthly_supplier_search_limit=1,
                monthly_procurement_report_limit=1,
                money_balance_kopeks=0,
            )
            db.add(client)
            db.add(ClientTelegramAccount(client_id="client-1", telegram_id="555", username="buyer", name="Buyer One"))
            db.add(Job(client_id="client-1", mode=MODE_SUPPLIER_SEARCH, status="completed"))
            db.commit()

            resolved, account_error = get_or_create_trial_client_by_telegram_id(db, "555", username="buyer", name="Buyer One")

            self.assertEqual(account_error, "")
            self.assertEqual(resolved.id, "client-1")
            self.assertEqual(resolved.money_balance_kopeks, 0)
            self.assertEqual(
                db.query(BillingTransaction)
                .filter(BillingTransaction.client_id == "client-1")
                .filter(BillingTransaction.operation == OP_GRANT)
                .count(),
                0,
            )
        finally:
            db.close()

    def test_supplier_target_uses_client_override_or_settings_default(self) -> None:
        settings = SystemSettings(default_supplier_target=25)
        regular_client = Client(telegram_id="100")
        vip_client = Client(telegram_id="200", supplier_target_min=40)
        excessive_client = Client(telegram_id="300", supplier_target_min=150)

        self.assertEqual(supplier_target_for_client(settings, regular_client), 25)
        self.assertEqual(supplier_target_for_client(settings, vip_client), 40)
        self.assertEqual(supplier_target_for_client(settings, excessive_client), 100)

    def test_pending_username_account_resolves_on_first_bot_contact(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="pending:client-1", name="Customer")
            db.add(client)
            db.flush()
            account = ensure_pending_client_telegram_account(db, client, "@BuyerOne")
            db.commit()

            resolved, account_error = get_or_create_trial_client_by_telegram_id(
                db,
                "777",
                username="buyerone",
                name="Buyer One",
            )
            db.refresh(account)
            db.refresh(client)

            self.assertEqual(account_error, "")
            self.assertEqual(resolved.id, "client-1")
            self.assertEqual(account.telegram_id, "777")
            self.assertEqual(client.telegram_id, "777")
            self.assertFalse(is_pending_telegram_id(account.telegram_id))
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

    def test_access_until_is_ignored_for_non_expiring_packages(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="client-1",
                telegram_id="100",
                access_until="2020-01-01",
                monthly_supplier_search_limit=10,
            )
            db.add(client)
            db.commit()

            error = client_access_error(db, client, MODE_SUPPLIER_SEARCH)

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

    def test_existing_paid_grants_lift_trial_mode_restrictions(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="trial-paid",
                telegram_id="555",
                is_trial=True,
                monthly_supplier_search_limit=1,
                monthly_procurement_report_limit=1,
                allowed_procurement_report=True,
            )
            db.add(client)
            db.add_all(
                [
                    BillingTransaction(
                        client_id=client.id,
                        kind=KIND_SUPPLIER_SEARCH,
                        operation=OP_GRANT,
                        units=2,
                        created_by="admin",
                    ),
                    BillingTransaction(
                        client_id=client.id,
                        kind=KIND_PROCUREMENT_REPORT,
                        operation=OP_GRANT,
                        units=1,
                        created_by="admin",
                    ),
                ]
            )
            db.commit()

            combined_error = client_access_error(db, client, MODE_ANALYSIS_AND_SUPPLIERS)
            mass_error = client_access_error(db, client, MODE_SUPPLIER_SEARCH, supplier_search_count=2)

            self.assertEqual(combined_error, "")
            self.assertEqual(mass_error, "")
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
            self.assertIn("supplier_target_min", client_columns)
            with engine.connect() as connection:
                row = connection.execute(
                    text(
                        """
                        SELECT
                            monthly_supplier_search_limit,
                            monthly_procurement_report_limit,
                            supplier_target_min
                        FROM clients
                        WHERE id = 'client-1'
                        """
                    )
                ).one()
                account_count = connection.execute(text("SELECT count(*) FROM client_telegram_accounts WHERE telegram_id = '123'")).scalar_one()
            self.assertEqual(row.monthly_supplier_search_limit, 7)
            self.assertEqual(row.monthly_procurement_report_limit, 7)
            self.assertEqual(row.supplier_target_min, 0)
            self.assertEqual(account_count, 1)
        finally:
            app_db.engine = original_engine


if __name__ == "__main__":
    unittest.main()
