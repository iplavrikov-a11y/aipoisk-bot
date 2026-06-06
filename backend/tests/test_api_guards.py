from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

import app.main as main
from app.main import (
    build_supplier_quality_snapshot,
    build_system_status,
    client_to_dict,
    create_client,
    create_client_telegram_account,
    create_manual_job,
    delete_client,
    delete_client_telegram_account,
    grant_client_billing_units,
    job_to_dict,
    list_jobs,
    public_site_payload,
    read_job_evidence_payload,
    settings_to_public_dict,
    update_client_telegram_account,
    upload_job,
)
from app.models import DEFAULT_PAYMENT_INSTRUCTIONS, BillingTransaction, Client, Job, SystemSettings, TariffPackage, now_utc
from app.schemas import BillingGrantCreate, ClientCreate, ClientTelegramAccountCreate, ClientTelegramAccountPatch, ManualJobCreate


class ApiGuardTests(unittest.TestCase):
    def test_manual_job_rejects_empty_no_input_job_before_db_access(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            create_manual_job(ManualJobCreate(telegram_id="123"), db=object())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("Upload a document", str(raised.exception.detail))

    def test_read_job_evidence_payload_reads_json_inside_storage_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_path = root / "jobs" / "job-1" / "output" / "evidence.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(json.dumps({"status": "failed", "ai_required": True}), encoding="utf-8")

            payload = read_job_evidence_payload(SimpleNamespace(evidence_path=str(evidence_path)), storage_root=root)

        self.assertEqual(payload["status"], "failed")
        self.assertTrue(payload["ai_required"])

    def test_read_job_evidence_payload_rejects_paths_outside_storage_root(self) -> None:
        with tempfile.TemporaryDirectory() as root_tmp, tempfile.TemporaryDirectory() as outside_tmp:
            outside = Path(outside_tmp) / "evidence.json"
            outside.write_text("{}", encoding="utf-8")

            with self.assertRaises(HTTPException) as raised:
                read_job_evidence_payload(SimpleNamespace(evidence_path=str(outside)), storage_root=Path(root_tmp))

        self.assertEqual(raised.exception.status_code, 404)

    def test_supplier_quality_snapshot_reads_provider_statuses_and_ai_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_path = root / "jobs" / "job-1" / "output" / "evidence.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(
                json.dumps(
                    {
                        "ai_required": True,
                        "stage": "supplier_search",
                        "search": {
                            "reports": [
                                {"provider": "yandex", "status": "ok"},
                                {"provider": "google", "status": "empty"},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            created_at = now_utc() - timedelta(seconds=90)
            jobs = [
                SimpleNamespace(
                    id="job-1",
                    mode="supplier_search",
                    title="failure",
                    status="failed",
                    verified_count=0,
                    target_suppliers=2,
                    error="AI failed",
                    evidence_path=str(evidence_path),
                    created_at=created_at,
                    completed_at=now_utc(),
                )
            ]

            snapshot = build_supplier_quality_snapshot(jobs, storage_root=root)

        self.assertEqual(snapshot["window_size"], 1)
        self.assertEqual(snapshot["status_counts"], {"failed": 1})
        self.assertEqual(snapshot["ai_required_failures"], 1)
        self.assertEqual(snapshot["provider_status_counts"]["yandex"], {"ok": 1})
        self.assertEqual(snapshot["provider_status_counts"]["google"], {"empty": 1})
        self.assertEqual(snapshot["recent_failures"][0]["stage"], "supplier_search")

    def test_auxiliary_search_source_does_not_alert_when_primary_search_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_path = root / "jobs" / "job-1" / "output" / "evidence.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(
                json.dumps(
                    {
                        "search": {
                            "reports": [
                                {"provider": "yandex", "status": "ok"},
                                {"provider": "tavily", "status": "empty"},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            jobs = [
                SimpleNamespace(
                    id="job-1",
                    mode="supplier_search",
                    title="ok",
                    status="completed",
                    verified_count=10,
                    target_suppliers=10,
                    error="",
                    evidence_path=str(evidence_path),
                    created_at=now_utc(),
                    completed_at=now_utc(),
                )
            ]

            snapshot = build_supplier_quality_snapshot(jobs, storage_root=root)

        self.assertNotIn("search_provider_no_ok", [item["code"] for item in snapshot["alerts"]])

    def test_job_to_dict_exposes_ui_contract_and_units(self) -> None:
        job = Job(
            id="job-1",
            mode="analysis_and_suppliers",
            title="ТЗ_насосная_станция",
            status="completed",
            created_by_telegram_id="555",
            target_suppliers=15,
            verified_count=7,
        )

        payload = job_to_dict(job)

        self.assertEqual(payload["human_title"], "ТЗ насосная станция")
        self.assertFalse(payload["is_internal"])
        self.assertEqual(payload["mode_label"], "Анализ + поставщики")
        self.assertEqual(payload["supplier_units"], 1)
        self.assertEqual(payload["procurement_report_units"], 1)
        self.assertEqual(payload["created_by_telegram_id"], "555")

    def test_job_to_dict_marks_internal_service_jobs(self) -> None:
        job = Job(id="job-1", mode="supplier_search", title="worker_smoke_patch", message="retest")

        payload = job_to_dict(job)

        self.assertTrue(payload["is_internal"])
        self.assertEqual(payload["human_title"], "Служебная проверка")

    def test_client_to_dict_includes_two_usage_counters_and_recent_writeoffs(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client = Client(
                id="client-1",
                telegram_id="100",
                name="Customer",
                monthly_supplier_search_limit=3,
                monthly_procurement_report_limit=2,
                allowed_procurement_report=True,
            )
            db.add(client)
            db.add(Job(client_id="client-1", mode="supplier_search", title="ТЗ насос", created_by_telegram_id="100"))
            db.add(Job(client_id="client-1", mode="analysis_and_suppliers", title="Документация", created_by_telegram_id="200"))
            db.add(Job(client_id="client-1", mode="supplier_search", title="worker_smoke_patch", created_by_telegram_id="999"))
            db.commit()
            db.refresh(client)

            payload = client_to_dict(client, db=db)
        finally:
            db.close()

        self.assertEqual(payload["usage"]["supplier_search"]["used"], 2)
        self.assertEqual(payload["usage"]["supplier_search"]["remaining"], 1)
        self.assertEqual(payload["usage"]["procurement_report"]["used"], 1)
        self.assertEqual(payload["usage"]["procurement_report"]["remaining"], 1)
        self.assertEqual(len(payload["recent_usage"]), 2)
        self.assertEqual({item["created_by_telegram_id"] for item in payload["recent_usage"]}, {"100", "200"})

    def test_create_client_accepts_pending_username_without_telegram_id(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            payload = create_client(
                ClientCreate(name="Customer", telegram_usernames=["@BuyerOne"]),
                db=db,
            )
        finally:
            db.close()

        self.assertEqual(payload["name"], "Customer")
        self.assertEqual(payload["telegram_id"], "")
        self.assertTrue(payload["is_pending"])
        self.assertEqual(payload["telegram_accounts"][0]["username"], "buyerone")
        self.assertEqual(payload["telegram_accounts"][0]["telegram_id"], "")
        self.assertTrue(payload["telegram_accounts"][0]["is_pending"])

    def test_manual_telegram_id_account_still_can_be_added_to_client(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_usernames=["@buyerone"]), db=db)
            account = create_client_telegram_account(
                client_payload["id"],
                ClientTelegramAccountCreate(telegram_id="777", username="@manager"),
                db=db,
            )
        finally:
            db.close()

        self.assertEqual(account["telegram_id"], "777")
        self.assertEqual(account["username"], "manager")
        self.assertFalse(account["is_pending"])

    def test_pending_account_can_be_completed_by_manual_telegram_id(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_usernames=["@buyerone"]), db=db)
            account_id = client_payload["telegram_accounts"][0]["id"]

            updated = update_client_telegram_account(
                client_payload["id"],
                account_id,
                ClientTelegramAccountPatch(telegram_id="888", username="@BuyerOne", name="Buyer One"),
                db=db,
            )
            client = db.get(Client, client_payload["id"])
            client_telegram_id = client.telegram_id if client else ""
        finally:
            db.close()

        self.assertEqual(updated["telegram_id"], "888")
        self.assertEqual(updated["username"], "buyerone")
        self.assertEqual(updated["name"], "Buyer One")
        self.assertFalse(updated["is_pending"])
        self.assertEqual(client_telegram_id, "888")

    def test_manual_telegram_id_patch_rejects_existing_id(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            create_client(ClientCreate(name="First", telegram_id="111"), db=db)
            second = create_client(ClientCreate(name="Second", telegram_usernames=["@second"]), db=db)
            account_id = second["telegram_accounts"][0]["id"]

            with self.assertRaises(HTTPException) as raised:
                update_client_telegram_account(
                    second["id"],
                    account_id,
                    ClientTelegramAccountPatch(telegram_id="111"),
                    db=db,
                )
        finally:
            db.close()

        self.assertEqual(raised.exception.status_code, 409)

    def test_extra_telegram_account_can_be_deleted(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_id="111"), db=db)
            extra = create_client_telegram_account(
                client_payload["id"],
                ClientTelegramAccountCreate(telegram_id="222", username="@manager"),
                db=db,
            )

            result = delete_client_telegram_account(client_payload["id"], extra["id"], db=db)
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(len(result["client"]["telegram_accounts"]), 1)
        self.assertEqual(result["client"]["telegram_accounts"][0]["telegram_id"], "111")

    def test_deleting_primary_telegram_account_reassigns_client_primary_id(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_id="111"), db=db)
            create_client_telegram_account(
                client_payload["id"],
                ClientTelegramAccountCreate(telegram_id="222", username="@manager"),
                db=db,
            )
            primary_id = next(
                item["id"]
                for item in client_payload["telegram_accounts"]
                if item["telegram_id"] == "111"
            )

            result = delete_client_telegram_account(client_payload["id"], primary_id, db=db)
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(result["client"]["telegram_id"], "222")
        self.assertEqual(len(result["client"]["telegram_accounts"]), 1)

    def test_last_telegram_account_cannot_be_deleted(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_id="111"), db=db)
            account_id = client_payload["telegram_accounts"][0]["id"]

            with self.assertRaises(HTTPException) as raised:
                delete_client_telegram_account(client_payload["id"], account_id, db=db)
        finally:
            db.close()

        self.assertEqual(raised.exception.status_code, 409)

    def test_manual_billing_grant_accepts_arbitrary_units_without_tariff(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_id="777"), db=db)
            result = grant_client_billing_units(
                client_payload["id"],
                BillingGrantCreate(kind="supplier_search", units=1012, note="manual random amount"),
                db=db,
            )
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(result["transaction"]["package_id"], "")
        self.assertEqual(result["transaction"]["units"], 1012)
        self.assertEqual(result["client"]["usage"]["supplier_search"]["available"], 1012)

    def test_delete_client_removes_client_without_history(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Draft", telegram_usernames=["@draft"]), db=db)
            result = delete_client(client_payload["id"], db=db)

            self.assertTrue(result["success"])
            self.assertEqual(db.query(Client).count(), 0)
        finally:
            db.close()

    def test_delete_client_removes_manual_billing_when_no_jobs_exist(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client = Client(id="client-1", telegram_id="100", name="Customer")
            db.add(client)
            db.add(BillingTransaction(client_id="client-1", kind="supplier_search", operation="grant", units=1))
            db.commit()

            result = delete_client("client-1", db=db)

            self.assertTrue(result["success"])
            self.assertEqual(db.query(Client).count(), 0)
            self.assertEqual(db.query(BillingTransaction).count(), 0)
        finally:
            db.close()

    def test_delete_client_rejects_clients_with_jobs_to_preserve_history(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client = Client(id="client-1", telegram_id="100", name="Customer")
            db.add(client)
            db.add(Job(client_id="client-1", mode="supplier_search", title="ТЗ"))
            db.commit()

            with self.assertRaises(HTTPException) as raised:
                delete_client("client-1", db=db)

            self.assertEqual(raised.exception.status_code, 409)
            self.assertIn("Отключите клиента", str(raised.exception.detail))
        finally:
            db.close()

    def test_list_jobs_hides_internal_jobs_by_default(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            db.add(Job(id="job-1", mode="supplier_search", title="Клиентская задача"))
            db.add(Job(id="job-2", mode="supplier_search", title="worker_smoke_patch"))
            db.commit()

            visible = list_jobs(include_internal=False, db=db)
            all_jobs = list_jobs(include_internal=True, db=db)
        finally:
            db.close()

        self.assertEqual([item["id"] for item in visible], ["job-1"])
        self.assertEqual({item["id"] for item in all_jobs}, {"job-1", "job-2"})

    def test_settings_public_payload_includes_supplier_search_ui_contract(self) -> None:
        settings = SystemSettings(id=1, supplier_search_provider_order="ddgs")

        payload = settings_to_public_dict(settings)

        self.assertEqual(payload["supplier_search_ui"]["active_provider"], "ddgs")
        self.assertEqual(payload["supplier_search_ui"]["active_label"], "Резерв DuckDuckGo")
        self.assertTrue(payload["supplier_search_ui"]["has_active_source"])
        self.assertIn("technical_sources", payload["supplier_search_ui"])

    def test_settings_public_payload_includes_contact_site_and_default_payment_text(self) -> None:
        settings = SystemSettings(
            id=1,
            bot_telegram="@tenderlex_bot",
            contact_website="https://aipoisk.example",
            payment_instructions="",
        )

        payload = settings_to_public_dict(settings)

        self.assertEqual(payload["bot_telegram"], "@tenderlex_bot")
        self.assertEqual(payload["contact_website"], "https://aipoisk.example")
        self.assertEqual(payload["payment_instructions"], DEFAULT_PAYMENT_INSTRUCTIONS)

    def test_public_site_payload_exposes_only_active_tariffs_and_contacts(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            db.add(
                SystemSettings(
                    id=1,
                    bot_telegram="@tenderlex_bot",
                    contact_email="snab@example.ru",
                    contact_telegram="@lexelence",
                    contact_website="tenderlex.ru",
                )
            )
            db.add(
                TariffPackage(
                    kind="supplier_search",
                    name="10 запросов",
                    units=10,
                    price_kopeks=100000,
                    description="Поиск поставщиков",
                    is_active=True,
                )
            )
            db.add(
                TariffPackage(
                    kind="procurement_report",
                    name="Скрытый пакет",
                    units=1,
                    price_kopeks=10000,
                    is_active=False,
                )
            )
            db.commit()

            payload = public_site_payload(db)
        finally:
            db.close()

        self.assertEqual(payload["site"]["domain"], "https://tenderlex.ru")
        self.assertEqual(payload["bot"]["telegram"], "@tenderlex_bot")
        self.assertEqual(payload["bot"]["telegram_url"], "https://t.me/tenderlex_bot")
        self.assertEqual(payload["contacts"]["email"], "snab@example.ru")
        self.assertEqual(payload["contacts"]["telegram_url"], "https://t.me/lexelence")
        self.assertEqual(payload["contacts"]["website_url"], "https://tenderlex.ru")
        self.assertEqual(len(payload["tariffs"]), 1)
        self.assertEqual(payload["tariffs"][0]["label"], "Поставщики")
        self.assertEqual(payload["tariff_groups"]["supplier_search"][0]["name"], "10 запросов")
        self.assertEqual(payload["tariff_groups"]["procurement_report"], [])

    def test_system_status_exposes_resources_queue_and_configured_services(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            settings = SystemSettings(
                id=1,
                yandex_search_folder_id="folder",
                yandex_search_api_key="key",
                custom_ai_providers_json='[{"id":"ai","baseUrl":"https://llm.example/v1","apiKey":"secret"}]',
            )
            db.add(settings)
            db.add(Job(id="job-1", status="pending"))
            db.add(Job(id="job-2", status="running"))
            db.commit()

            payload = build_system_status(settings, db)
        finally:
            db.close()

        self.assertIn("server", payload)
        self.assertEqual(payload["queue"]["pending"], 1)
        self.assertEqual(payload["queue"]["running"], 1)
        services = {item["id"]: item for item in payload["services"]}
        self.assertTrue(services["yandex"]["configured"])
        self.assertFalse(services["google"]["configured"])
        self.assertTrue(services["ai"]["configured"])


class ApiAsyncGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_rejects_empty_file_list_before_db_access(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await upload_job(telegram_id="123", files=[], db=object())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("at least one document", str(raised.exception.detail))

    async def test_upload_rejects_supplier_search_source_url_without_tz_file(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await upload_job(
                telegram_id="123",
                mode="supplier_search",
                files=[],
                source_urls="https://etp.example.ru/procedure/123",
                db=object(),
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("technical assignment file", str(raised.exception.detail))

    async def test_upload_accepts_report_source_url_without_files(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_create_job = main.create_job
        original_enqueue_job = main.enqueue_job
        captured: dict = {}

        def fake_create_job(*args, **kwargs):
            captured.update(kwargs)
            return Job(id="job-1", client_id="client-1", mode=kwargs["mode"], title=kwargs["title"], target_suppliers=kwargs["target_suppliers"])

        try:
            db.add(
                Client(
                    id="client-1",
                    telegram_id="123",
                    allowed_procurement_report=True,
                    monthly_procurement_report_limit=1,
                )
            )
            db.commit()
            main.create_job = fake_create_job
            main.enqueue_job = lambda _job_id: None

            result = await upload_job(
                telegram_id="123",
                mode="procurement_report",
                files=[],
                source_urls="https://etp.example.ru/procedure/123",
                db=db,
            )
        finally:
            main.create_job = original_create_job
            main.enqueue_job = original_enqueue_job
            db.close()

        self.assertEqual(result["id"], "job-1")
        self.assertEqual(captured["files"], [])
        self.assertEqual(captured["sources"][0]["value"], "https://etp.example.ru/procedure/123")

    async def test_upload_accepts_report_notice_number_without_files(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_create_job = main.create_job
        original_enqueue_job = main.enqueue_job
        captured: dict = {}

        def fake_create_job(*args, **kwargs):
            captured.update(kwargs)
            return Job(id="job-1", client_id="client-1", mode=kwargs["mode"], title=kwargs["title"], target_suppliers=kwargs["target_suppliers"])

        try:
            db.add(
                Client(
                    id="client-1",
                    telegram_id="123",
                    allowed_procurement_report=True,
                    monthly_procurement_report_limit=1,
                )
            )
            db.commit()
            main.create_job = fake_create_job
            main.enqueue_job = lambda _job_id: None

            result = await upload_job(
                telegram_id="123",
                mode="procurement_report",
                files=[],
                source_urls="0371100005626000040",
                db=db,
            )
        finally:
            main.create_job = original_create_job
            main.enqueue_job = original_enqueue_job
            db.close()

        self.assertEqual(result["id"], "job-1")
        self.assertEqual(captured["files"], [])
        self.assertEqual(captured["title"], "Закупка 0371100005626000040")
        self.assertEqual(captured["sources"][0]["kind"], "tenderplan_notice")
        self.assertEqual(captured["sources"][0]["value"], "0371100005626000040")

    async def test_upload_supplier_search_multiple_files_creates_separate_jobs(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        class FakeUpload:
            def __init__(self, filename: str, content: bytes) -> None:
                self.filename = filename
                self._content = content

            async def read(self) -> bytes:
                return self._content

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_create_job = main.create_job
        original_enqueue_job = main.enqueue_job
        captured: list[dict] = []
        enqueued: list[str] = []

        def fake_create_job(*args, **kwargs):
            captured.append(kwargs)
            return Job(
                id=f"job-{len(captured)}",
                client_id="client-1",
                mode=kwargs["mode"],
                title=kwargs["title"],
                target_suppliers=kwargs["target_suppliers"],
                file_count=len(kwargs["files"]),
            )

        try:
            db.add(
                Client(
                    id="client-1",
                    telegram_id="123",
                    allowed_supplier_search=True,
                    monthly_supplier_search_limit=2,
                )
            )
            db.commit()
            main.create_job = fake_create_job
            main.enqueue_job = lambda job_id: enqueued.append(job_id)

            result = await upload_job(
                telegram_id="123",
                mode="supplier_search",
                files=[
                    FakeUpload("ТЗ насос.docx", b"pump"),
                    FakeUpload("ТЗ вентиляция.docx", b"vent"),
                ],
                db=db,
            )
        finally:
            main.create_job = original_create_job
            main.enqueue_job = original_enqueue_job
            db.close()

        self.assertTrue(result["batch"])
        self.assertEqual(result["count"], 2)
        self.assertEqual([item["id"] for item in result["jobs"]], ["job-1", "job-2"])
        self.assertEqual(enqueued, ["job-1", "job-2"])
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0]["title"], "ТЗ насос")
        self.assertEqual(captured[0]["files"], [("ТЗ насос.docx", b"pump")])
        self.assertEqual(captured[1]["title"], "ТЗ вентиляция")
        self.assertEqual(captured[1]["files"], [("ТЗ вентиляция.docx", b"vent")])
        self.assertEqual(captured[0]["sources"], [])


if __name__ == "__main__":
    unittest.main()
