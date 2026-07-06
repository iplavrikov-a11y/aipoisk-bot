from __future__ import annotations

import asyncio
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

import app.main as main
from app.main import (
    build_bot_analytics,
    build_supplier_quality_snapshot,
    build_system_status,
    client_to_dict,
    create_client,
    create_client_telegram_account,
    create_manual_job,
    delete_client,
    delete_client_web_user,
    delete_client_telegram_account,
    grant_client_billing_units,
    job_to_dict,
    list_jobs,
    merge_client,
    public_site_payload,
    read_job_evidence_payload,
    settings_to_public_dict,
    update_client_telegram_account,
    upload_job,
)
from app.billing import client_balance_summary
from app.models import DEFAULT_PAYMENT_INSTRUCTIONS, BillingTransaction, Client, ClientTelegramAccount, Job, SystemSettings, TariffPackage, WebEmailVerificationToken, WebPasswordResetRequest, WebSession, WebUser, now_utc
from app.schemas import AiTestRequest, BillingGrantCreate, ClientCreate, ClientMergeRequest, ClientTelegramAccountCreate, ClientTelegramAccountPatch, ManualJobCreate


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

        self.assertEqual(payload["human_title"], "Анализ + поиск: насосная станция")
        self.assertFalse(payload["is_internal"])
        self.assertEqual(payload["mode_label"], "Анализ + поставщики")
        self.assertEqual(payload["supplier_units"], 1)
        self.assertEqual(payload["procurement_report_units"], 1)
        self.assertEqual(payload["created_by_telegram_id"], "555")
        self.assertEqual(payload["supplier_search_policy"], "normal")
        self.assertEqual(payload["supplier_search_run_type"], "initial")

    def test_job_to_dict_exposes_supplier_search_policy_for_admin_ui(self) -> None:
        job = Job(
            id="job-1",
            mode="supplier_search",
            title="ТЗ_насос",
            supplier_search_policy="minprom_registry_only",
            supplier_search_run_type="additional",
        )

        payload = job_to_dict(job)

        self.assertEqual(payload["supplier_search_policy"], "minprom_registry_only")
        self.assertEqual(payload["supplier_search_run_type"], "additional")

    def test_job_to_dict_marks_internal_service_jobs(self) -> None:
        job = Job(id="job-1", mode="supplier_search", title="worker_smoke_patch", message="retest")

        payload = job_to_dict(job)

        self.assertTrue(payload["is_internal"])
        self.assertEqual(payload["human_title"], "Служебная проверка")

    def test_job_to_dict_marks_evidence_presence_for_admin_ui(self) -> None:
        job = Job(id="job-1", mode="supplier_search", title="ok", evidence_path="/tmp/evidence.json")

        payload = job_to_dict(job)

        self.assertTrue(payload["has_evidence"])

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
                supplier_target_min=35,
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
        self.assertEqual(payload["supplier_target_min"], 35)
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

    def test_delete_client_removes_jobs_billing_and_accounts_without_telegram_requirement(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client = Client(id="client-1", telegram_id="web:client-1", name="Web Client")
            db.add(client)
            db.add(WebUser(id="web-1", client_id="client-1", email="buyer@example.com", password_hash="hash"))
            db.add(Job(id="job-1", client_id="client-1", mode="supplier_search", title="ТЗ"))
            db.add(BillingTransaction(client_id="client-1", job_id="job-1", kind="supplier_search", operation="grant", units=10))
            db.commit()

            result = delete_client("client-1", db=db)

            client_count = db.query(Client).count()
            user_count = db.query(WebUser).count()
            job_count = db.query(Job).count()
            billing_count = db.query(BillingTransaction).count()
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(client_count, 0)
        self.assertEqual(user_count, 0)
        self.assertEqual(job_count, 0)
        self.assertEqual(billing_count, 0)

    def test_delete_client_web_user_removes_login_only_and_preserves_client_state(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client = Client(id="client-1", telegram_id="web:client-1", name="Marina", money_balance_kopeks=84_000)
            db.add(client)
            db.add(ClientTelegramAccount(client_id="client-1", telegram_id="320433711", username="lexelence", name="Алексей"))
            db.add(WebUser(id="web-1", client_id="client-1", email="m.timoshenko@bm-corp.ru", password_hash="hash"))
            db.add(WebSession(id="session-1", user_id="web-1", token_hash="token", expires_at=now_utc() + timedelta(days=1)))
            db.add(WebPasswordResetRequest(id="reset-1", user_id="web-1", email="m.timoshenko@bm-corp.ru"))
            db.add(
                WebEmailVerificationToken(
                    id="verify-1",
                    user_id="web-1",
                    email="m.timoshenko@bm-corp.ru",
                    token_hash="verify-token",
                    expires_at=now_utc() + timedelta(days=1),
                )
            )
            db.commit()

            result = delete_client_web_user("client-1", "web-1", db=db)
            client_after = db.get(Client, "client-1")
            telegram_accounts = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == "client-1").count()
            web_users = db.query(WebUser).filter(WebUser.client_id == "client-1").count()
            sessions = db.query(WebSession).count()
            reset_requests = db.query(WebPasswordResetRequest).count()
            verification_tokens = db.query(WebEmailVerificationToken).count()
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(result["client"]["web_users"], [])
        self.assertEqual(client_after.telegram_id, "320433711")
        self.assertEqual(client_after.money_balance_kopeks, 84_000)
        self.assertEqual(telegram_accounts, 1)
        self.assertEqual(web_users, 0)
        self.assertEqual(sessions, 0)
        self.assertEqual(reset_requests, 0)
        self.assertEqual(verification_tokens, 0)

    def test_merge_client_moves_web_login_jobs_billing_and_telegram_accounts(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            target = create_client(ClientCreate(name="Тимошенко", telegram_id="1743101322", username="@bookwap"), db=db)
            db.add(BillingTransaction(client_id=target["id"], kind="procurement_report", operation="grant", units=2))
            source = Client(
                id="web-client",
                telegram_id="web:web-client",
                name="Marina",
                monthly_job_limit=12,
                monthly_supplier_search_limit=50,
                monthly_procurement_report_limit=3,
                allowed_procurement_report=True,
            )
            db.add(source)
            db.add(WebUser(id="web-1", client_id="web-client", email="m.timoshenko@bm-corp.ru", password_hash="hash", is_email_verified=True))
            db.add(Job(id="job-1", client_id="web-client", mode="procurement_report", title="Анализ"))
            db.add(BillingTransaction(client_id="web-client", job_id="job-1", kind="procurement_report", operation="grant", units=3))
            db.commit()

            result = merge_client(target["id"], ClientMergeRequest(source_client_id="web-client"), db=db)
            merged = db.get(Client, target["id"])
            web_user = db.query(WebUser).filter(WebUser.email == "m.timoshenko@bm-corp.ru").one()
            moved_job = db.get(Job, "job-1")
            moved_billing = db.query(BillingTransaction).filter(BillingTransaction.job_id == "job-1").one()
            balance = client_balance_summary(db, merged)
            source_after = db.get(Client, "web-client")
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertIsNone(source_after)
        self.assertEqual(web_user.client_id, target["id"])
        self.assertEqual(moved_job.client_id, target["id"])
        self.assertEqual(moved_billing.client_id, target["id"])
        self.assertEqual(balance["procurement_report"]["available"], 5)
        self.assertEqual(merged.telegram_id, "1743101322")
        self.assertEqual(merged.monthly_job_limit, 12)
        self.assertEqual(merged.monthly_supplier_search_limit, 50)
        self.assertEqual(merged.monthly_procurement_report_limit, 3)
        self.assertTrue(merged.allowed_procurement_report)

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

    def test_delete_last_telegram_account_leaves_client_editable(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_id="777", username="@manager"), db=db)
            account_id = client_payload["telegram_accounts"][0]["id"]

            result = delete_client_telegram_account(client_payload["id"], account_id, db=db)
            client = db.get(Client, client_payload["id"])
            accounts_count = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == client_payload["id"]).count()
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(accounts_count, 0)
        self.assertTrue(client.telegram_id.startswith("pending:"))
        self.assertEqual(client.username, "")

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

    def test_existing_telegram_account_requires_transfer_confirmation(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            source = create_client(ClientCreate(name="Source", telegram_id="222", username="@manager"), db=db)
            target = create_client(ClientCreate(name="Target", telegram_id="111", username="@owner"), db=db)

            with self.assertRaises(HTTPException) as raised:
                create_client_telegram_account(
                    target["id"],
                    ClientTelegramAccountCreate(telegram_id="222", username="@manager"),
                    db=db,
                )
        finally:
            db.close()

        self.assertEqual(source["telegram_id"], "222")
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("Подтвердите перенос", str(raised.exception.detail))

    def test_trial_client_can_be_merged_into_existing_client_by_transferring_account(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            target = create_client(ClientCreate(name="Customer", telegram_id="111", username="@owner"), db=db)
            source = create_client(
                ClientCreate(name="Trial Manager", telegram_id="222", username="@manager", is_trial=True),
                db=db,
            )
            source_id = source["id"]
            db.add(Job(id="job-1", client_id=source_id, mode="supplier_search", status="completed", title="ТЗ", created_by_telegram_id="222"))
            db.add(
                BillingTransaction(
                    client_id=source_id,
                    job_id="job-1",
                    kind="supplier_search",
                    operation="grant",
                    units=1,
                    note="trial",
                )
            )
            db.commit()

            account = create_client_telegram_account(
                target["id"],
                ClientTelegramAccountCreate(
                    telegram_id="222",
                    username="@manager",
                    name="Manager",
                    transfer_existing=True,
                ),
                db=db,
            )
            source_after = db.get(Client, source_id)
            target_client = db.get(Client, target["id"])
            target_primary_id = target_client.telegram_id if target_client else ""
            target_account_count = (
                db.query(ClientTelegramAccount)
                .filter(ClientTelegramAccount.client_id == target["id"])
                .count()
            )
            moved_job = db.get(Job, "job-1")
            moved_job_client_id = moved_job.client_id if moved_job else ""
            moved_billing = db.query(BillingTransaction).filter(BillingTransaction.job_id == "job-1").first()
            moved_billing_client_id = moved_billing.client_id if moved_billing else ""
        finally:
            db.close()

        self.assertEqual(account["telegram_id"], "222")
        self.assertEqual(account["username"], "manager")
        self.assertEqual(account["name"], "Manager")
        self.assertIsNone(source_after)
        self.assertEqual(target_primary_id, "111")
        self.assertEqual(target_account_count, 2)
        self.assertEqual(moved_job_client_id, target["id"])
        self.assertEqual(moved_billing_client_id, target["id"])

    def test_transfer_to_pending_client_promotes_moved_telegram_id(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            target = create_client(ClientCreate(name="Customer", username="@owner"), db=db)
            source = create_client(ClientCreate(name="Trial Manager", telegram_id="222", username="@manager", is_trial=True), db=db)
            source_id = source["id"]

            account = create_client_telegram_account(
                target["id"],
                ClientTelegramAccountCreate(
                    telegram_id="222",
                    username="@manager",
                    transfer_existing=True,
                ),
                db=db,
            )
            source_after = db.get(Client, source_id)
            target_client = db.get(Client, target["id"])
            target_primary_id = target_client.telegram_id if target_client else ""
            target_accounts = (
                db.query(ClientTelegramAccount)
                .filter(ClientTelegramAccount.client_id == target["id"])
                .all()
            )
        finally:
            db.close()

        self.assertEqual(account["telegram_id"], "222")
        self.assertIsNone(source_after)
        self.assertEqual(target_primary_id, "222")
        self.assertEqual({item.username for item in target_accounts}, {"owner", "manager"})

    def test_transferring_account_from_regular_multi_account_client_keeps_source_client(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            target = create_client(ClientCreate(name="Target", telegram_id="111", username="@owner"), db=db)
            source = create_client(ClientCreate(name="Source", telegram_id="222", username="@manager"), db=db)
            create_client_telegram_account(
                source["id"],
                ClientTelegramAccountCreate(telegram_id="333", username="@second"),
                db=db,
            )

            account = create_client_telegram_account(
                target["id"],
                ClientTelegramAccountCreate(telegram_id="222", username="@manager", transfer_existing=True),
                db=db,
            )
            source_client = db.get(Client, source["id"])
            target_accounts = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == target["id"]).all()
            source_accounts = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == source["id"]).all()
        finally:
            db.close()

        self.assertEqual(account["telegram_id"], "222")
        self.assertIsNotNone(source_client)
        self.assertTrue(source_client.is_active)
        self.assertEqual(source_client.telegram_id, "333")
        self.assertEqual(len(source_accounts), 1)
        self.assertEqual(source_accounts[0].telegram_id, "333")
        self.assertEqual({item.telegram_id for item in target_accounts}, {"111", "222"})

    def test_transfer_from_regular_client_to_pending_client_reassigns_both_primaries(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            target = create_client(ClientCreate(name="Target", username="@owner"), db=db)
            source = create_client(ClientCreate(name="Source", telegram_id="222", username="@manager"), db=db)
            create_client_telegram_account(
                source["id"],
                ClientTelegramAccountCreate(telegram_id="333", username="@second"),
                db=db,
            )

            account = create_client_telegram_account(
                target["id"],
                ClientTelegramAccountCreate(telegram_id="222", username="@manager", transfer_existing=True),
                db=db,
            )
            target_client = db.get(Client, target["id"])
            source_client = db.get(Client, source["id"])
            target_primary_id = target_client.telegram_id if target_client else ""
            source_primary_id = source_client.telegram_id if source_client else ""
        finally:
            db.close()

        self.assertEqual(account["telegram_id"], "222")
        self.assertEqual(target_primary_id, "222")
        self.assertEqual(source_primary_id, "333")

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

    def test_last_telegram_account_can_be_deleted_and_keeps_client_editable(self) -> None:
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

            result = delete_client_telegram_account(client_payload["id"], account_id, db=db)
            client = db.get(Client, client_payload["id"])
            accounts_count = db.query(ClientTelegramAccount).filter(ClientTelegramAccount.client_id == client_payload["id"]).count()
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(accounts_count, 0)
        self.assertTrue(client.telegram_id.startswith("pending:"))
        self.assertEqual(client.username, "")

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

    def test_manual_billing_debit_reduces_available_and_rejects_overdraft(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_id="778"), db=db)
            grant_client_billing_units(
                client_payload["id"],
                BillingGrantCreate(kind="procurement_report", units=4),
                db=db,
            )
            result = grant_client_billing_units(
                client_payload["id"],
                BillingGrantCreate(kind="procurement_report", units=2, operation="debit", note="wrong client correction"),
                db=db,
            )
            with self.assertRaises(HTTPException) as raised:
                grant_client_billing_units(
                    client_payload["id"],
                    BillingGrantCreate(kind="procurement_report", units=3, operation="debit"),
                    db=db,
                )
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(result["transaction"]["operation"], "manual_debit")
        self.assertEqual(result["transaction"]["operation_label"], "ручное списание")
        self.assertEqual(result["client"]["usage"]["procurement_report"]["available"], 2)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("Недостаточно доступных генераций", str(raised.exception.detail))

    def test_admin_money_top_up_credits_only_money_balance(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_id="779"), db=db)
            result = grant_client_billing_units(
                client_payload["id"],
                BillingGrantCreate(kind="money", amount_kopeks=25_000, note="manual topup"),
                db=db,
            )
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(result["transaction"]["kind"], "money")
        self.assertEqual(result["transaction"]["kind_label"], "Баланс")
        self.assertEqual(result["transaction"]["units"], 0)
        self.assertEqual(result["client"]["usage"]["money"]["available_kopeks"], 25_000)
        self.assertEqual(result["client"]["usage"]["supplier_search"]["available"], 0)
        self.assertEqual(result["client"]["usage"]["procurement_report"]["available"], 0)

    def test_admin_money_debit_reduces_money_balance_and_rejects_overdraft(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            client_payload = create_client(ClientCreate(name="Customer", telegram_id="780"), db=db)
            grant_client_billing_units(
                client_payload["id"],
                BillingGrantCreate(kind="money", amount_kopeks=25_000, note="manual topup"),
                db=db,
            )
            result = grant_client_billing_units(
                client_payload["id"],
                BillingGrantCreate(kind="money", amount_kopeks=10_000, operation="debit", note="balance correction"),
                db=db,
            )
            with self.assertRaises(HTTPException) as raised:
                grant_client_billing_units(
                    client_payload["id"],
                    BillingGrantCreate(kind="money", amount_kopeks=20_000, operation="debit"),
                    db=db,
                )
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(result["transaction"]["kind"], "money")
        self.assertEqual(result["transaction"]["kind_label"], "Баланс")
        self.assertEqual(result["transaction"]["operation"], "manual_debit")
        self.assertEqual(result["transaction"]["operation_label"], "ручное списание")
        self.assertEqual(result["transaction"]["units"], 0)
        self.assertEqual(result["transaction"]["amount_kopeks"], 10_000)
        self.assertEqual(result["client"]["usage"]["money"]["available_kopeks"], 15_000)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("Недостаточно денег для списания", str(raised.exception.detail))

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

    def test_delete_client_removes_clients_with_jobs(self) -> None:
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

            result = delete_client("client-1", db=db)
            client_count = db.query(Client).count()
            job_count = db.query(Job).count()
        finally:
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(client_count, 0)
        self.assertEqual(job_count, 0)

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
            contact_max="@ownermax",
            contact_max_link="https://max.ru/invite/owner",
            contact_website="https://aipoisk.example",
            payment_instructions="",
        )

        payload = settings_to_public_dict(settings)

        self.assertEqual(payload["bot_telegram"], "@tenderlex_bot")
        self.assertEqual(payload["contact_max"], "@ownermax")
        self.assertEqual(payload["contact_max_link"], "https://max.ru/invite/owner")
        self.assertEqual(payload["contact_website"], "https://aipoisk.example")
        self.assertEqual(payload["payment_instructions"], DEFAULT_PAYMENT_INSTRUCTIONS)

    def test_minprom_registry_upload_ops_builds_indexes(self) -> None:
        from openpyxl import Workbook

        class FakeUpload:
            filename = "registry.xlsx"

            def __init__(self, content: bytes) -> None:
                self._content = content

            async def read(self) -> bytes:
                return self._content

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Предприятие-изготовитель", "Продукция", "ИНН", "Реестровый номер"])
        sheet.append(['АО "Катайский насосный завод"', "Насос центробежный типа Д", "4509000018", "РПП-НАСОС"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        workbook.close()

        with tempfile.TemporaryDirectory() as tmp:
            old_env = {
                "SUPPLIER_MINPROM_REGISTRY_INDEX_PATH": os.environ.get("SUPPLIER_MINPROM_REGISTRY_INDEX_PATH"),
                "SUPPLIER_MINPROM_REGISTRY_SQLITE_PATH": os.environ.get("SUPPLIER_MINPROM_REGISTRY_SQLITE_PATH"),
                "SUPPLIER_MINPROM_REGISTRY_XLSX_CACHE_PATH": os.environ.get("SUPPLIER_MINPROM_REGISTRY_XLSX_CACHE_PATH"),
            }
            os.environ["SUPPLIER_MINPROM_REGISTRY_INDEX_PATH"] = str(Path(tmp) / "registry.jsonl")
            os.environ["SUPPLIER_MINPROM_REGISTRY_SQLITE_PATH"] = str(Path(tmp) / "registry.sqlite")
            os.environ["SUPPLIER_MINPROM_REGISTRY_XLSX_CACHE_PATH"] = str(Path(tmp) / "registry.xlsx")
            try:
                status = asyncio.run(main.minprom_registry_upload_ops(FakeUpload(buffer.getvalue())))
            finally:
                for key, value in old_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        self.assertTrue(status["xlsx_exists"])
        self.assertTrue(status["index_exists"])
        self.assertTrue(status["sqlite_ready"])
        self.assertEqual(status["sqlite_count"], 1)

    def test_bot_analytics_exposes_funnel_trial_followups_and_payment_readiness(self) -> None:
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
                    payment_provider="yookassa",
                    yookassa_shop_id="shop-1",
                    yookassa_secret_key="secret",
                )
            )
            db.add(Client(id="trial-1", telegram_id="100", username="trial", name="Trial User", is_trial=True, monthly_supplier_search_limit=1))
            db.add(Client(id="paid-1", telegram_id="200", username="paid", name="Paid User", monthly_supplier_search_limit=10))
            db.add(Client(id="admin-web", telegram_id="web:admin", name="Алекс", is_trial=True, monthly_supplier_search_limit=1000))
            db.add(Client(id="admin-telegram", telegram_id="320433711", username="lexelence", name="Алексей", monthly_supplier_search_limit=1000))
            db.add(ClientTelegramAccount(client_id="trial-1", telegram_id="100", username="trial"))
            db.add(ClientTelegramAccount(client_id="paid-1", telegram_id="200", username="paid"))
            db.add(ClientTelegramAccount(client_id="admin-telegram", telegram_id="320433711", username="lexelence"))
            db.add(WebUser(id="web-1", client_id="admin-web", email="79210629909@ya.ru", password_hash="hash", name="Алекс"))
            db.add(Job(id="job-1", client_id="trial-1", mode="supplier_search", status="completed", created_by_telegram_id="100", created_at=now_utc()))
            db.add(Job(id="job-2", client_id="paid-1", mode="procurement_report", status="failed", created_by_telegram_id="200", created_at=now_utc()))
            db.add(Job(id="job-admin-web", client_id="admin-web", mode="supplier_search", status="completed", created_by_telegram_id="", created_at=now_utc()))
            db.add(Job(id="job-admin-telegram", client_id="admin-telegram", mode="supplier_search", status="completed", created_by_telegram_id="320433711", created_at=now_utc()))
            db.add(BillingTransaction(client_id="paid-1", kind="supplier_search", operation="grant", units=10, created_at=now_utc()))
            db.add(BillingTransaction(client_id="admin-web", kind="supplier_search", operation="grant", units=1000, created_at=now_utc()))
            db.add(BillingTransaction(client_id="admin-telegram", kind="procurement_report", operation="grant", units=1000, created_at=now_utc()))
            db.commit()

            payload = build_bot_analytics(db, period_days=30)
        finally:
            db.close()

        self.assertEqual(payload["summary"]["clients_total"], 2)
        self.assertEqual(payload["summary"]["telegram_accounts"], 2)
        self.assertEqual(payload["summary"]["period_jobs"], 2)
        self.assertEqual(payload["funnel"]["trial_started"], 1)
        self.assertEqual(payload["funnel"]["trial_used_bot"], 1)
        self.assertEqual(payload["funnel"]["trial_with_grants"], 0)
        self.assertTrue(payload["billing"]["yookassa_ready"])
        self.assertNotIn("admin-web", {item["client_id"] for item in payload["top_clients"]})
        self.assertNotIn("admin-telegram", {item["client_id"] for item in payload["top_clients"]})
        self.assertEqual(next(item for item in payload["billing"]["period"] if item["kind"] == "supplier_search")["granted"], 10)
        self.assertEqual(payload["trial_followups"][0]["client_id"], "trial-1")
        self.assertEqual(payload["top_clients"][0]["jobs_total"], 1)

    def test_daily_job_series_groups_by_moscow_calendar_day(self) -> None:
        rows = main._daily_job_series(
            [
                SimpleNamespace(mode="supplier_search", created_at=datetime(2026, 6, 10, 20, 30, tzinfo=timezone.utc)),
                SimpleNamespace(mode="procurement_report", created_at=datetime(2026, 6, 10, 21, 15, tzinfo=timezone.utc)),
            ],
            now=datetime(2026, 6, 10, 21, 30, tzinfo=timezone.utc),
            period_days=2,
        )

        self.assertEqual([item["date"] for item in rows], ["2026-06-10", "2026-06-11"])
        self.assertEqual(rows[0]["supplier_search"], 1)
        self.assertEqual(rows[1]["procurement_report"], 1)

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
                    contact_max="+79210629909",
                    contact_max_link="https://max.ru/invite/max-owner",
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
        self.assertEqual(payload["contacts"]["max"], "+79210629909")
        self.assertEqual(payload["contacts"]["max_url"], "https://max.ru/invite/max-owner")
        self.assertEqual(payload["contacts"]["website_url"], "https://tenderlex.ru")
        self.assertEqual(len(payload["tariffs"]), 1)
        self.assertEqual(payload["tariffs"][0]["label"], "Поставщики")
        self.assertEqual(payload["tariff_groups"]["supplier_search"][0]["name"], "10 запросов")
        self.assertEqual(payload["tariff_groups"]["procurement_report"], [])

    def test_max_phone_does_not_become_public_url(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        self.assertEqual(main.max_public_url("+79210629909"), "")
        self.assertEqual(main.max_public_url("79210629909"), "")
        self.assertEqual(main.max_public_url("@ownermax"), "https://max.ru/ownermax")

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            db.add(SystemSettings(id=1, contact_max="+79210629909", contact_max_link=""))
            db.commit()

            payload = public_site_payload(db)
            client = Client(id="client-1", telegram_id="web:client-1")
            user = WebUser(id="user-1", client_id="client-1", email="client@example.ru", password_hash="hash")
            client.web_users.append(user)
            db.add(client)
            db.commit()
            session_payload = main.customer_session_payload(db, user)
        finally:
            db.close()

        self.assertEqual(payload["contacts"]["max"], "+79210629909")
        self.assertEqual(payload["contacts"]["max_url"], "")
        self.assertEqual(session_payload["contacts"]["max"], "+79210629909")
        self.assertEqual(session_payload["contacts"]["max_url"], "")

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
    async def test_ai_test_returns_selected_provider_and_model(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_call_llm = main.call_llm

        async def fake_call_llm(_settings, _prompt: str, **kwargs):
            kwargs["metadata"].update(
                {
                    "provider_id": "polza",
                    "provider_name": "Polza",
                    "model": "x-ai/grok-4.1-fast",
                    "attempted_models": ["Polza:x-ai/grok-4.1-fast"],
                }
            )
            return "ok"

        try:
            db.add(
                SystemSettings(
                    id=1,
                    custom_ai_providers_json='[{"id":"polza","name":"Polza","baseUrl":"https://api.polza.ai/v1","apiKey":"key"}]',
                    light_provider="polza",
                    light_model="x-ai/grok-4.1-fast",
                )
            )
            db.commit()
            main.call_llm = fake_call_llm

            result = await main.test_ai(
                AiTestRequest(provider="polza", model="x-ai/grok-4.1-fast"),
                db=db,
            )
        finally:
            main.call_llm = original_call_llm
            db.close()

        self.assertTrue(result["success"])
        self.assertEqual(result["response"], "ok")
        self.assertEqual(result["provider_id"], "polza")
        self.assertEqual(result["provider_name"], "Polza")
        self.assertEqual(result["model"], "x-ai/grok-4.1-fast")

    async def test_ai_test_surfaces_provider_errors(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        original_call_llm = main.call_llm

        async def fake_call_llm(*_args, **_kwargs):
            raise RuntimeError("AI provider requires baseUrl, apiKey and model")

        try:
            db.add(SystemSettings(id=1, light_provider="polza", light_model="model"))
            db.commit()
            main.call_llm = fake_call_llm

            with self.assertRaises(HTTPException) as raised:
                await main.test_ai(AiTestRequest(provider="polza", model="model"), db=db)
        finally:
            main.call_llm = original_call_llm
            db.close()

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("Проверка модели не прошла", str(raised.exception.detail))

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
                    supplier_target_min=33,
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
        self.assertEqual(captured[0]["target_suppliers"], 33)
        self.assertEqual(captured[1]["title"], "ТЗ вентиляция")
        self.assertEqual(captured[1]["files"], [("ТЗ вентиляция.docx", b"vent")])
        self.assertEqual(captured[1]["target_suppliers"], 33)
        self.assertEqual(captured[0]["sources"], [])


if __name__ == "__main__":
    unittest.main()
