from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException, Response, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.billing import (
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    OP_GRANT,
    OP_RESERVE,
    OP_CHARGE,
    OP_RELEASE,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CUSTOMER_DECLINED,
)
from app.db import Base
from app.jobs import MODE_SUPPLIER_SEARCH
from app.main import (
    admin_verify_web_user_email,
    create_customer_job_api,
    customer_register_api,
    customer_job_to_dict,
    customer_session_payload,
    decline_customer_partial_job_api,
    download_customer_job_api,
    download_customer_job_file_api,
)
from app.main import complete_web_password_reset, customer_password_reset_request_api
from app.models import BillingTransaction, Client, Job, SystemSettings, WebEmailVerificationToken, WebPasswordResetRequest, WebRegistrationAttempt, WebUser
from app.schemas import WebPasswordResetComplete, WebPasswordResetRequestCreate, WebRegisterRequest
from app.web_auth import (
    WebAuthContext,
    authenticate_web_user,
    create_email_verification_token,
    create_web_session,
    create_web_user,
    get_web_session_by_token,
    verify_email_token,
)


def fake_request() -> SimpleNamespace:
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "tests"},
        cookies={},
    )


class CustomerApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def test_create_web_user_creates_separate_client_with_protected_trial(self) -> None:
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

            user = create_web_user(db, email="Buyer@Example.COM", password="StrongPass123", name="Buyer")
            authenticated = authenticate_web_user(db, "buyer@example.com", "StrongPass123")
            wrong_password = authenticate_web_user(db, "buyer@example.com", "wrong")

            self.assertEqual(user.email, "buyer@example.com")
            self.assertTrue(user.client.telegram_id.startswith("web:"))
            self.assertTrue(user.client.is_trial)
            self.assertEqual(user.client.monthly_supplier_search_limit, 2)
            self.assertEqual(user.client.monthly_procurement_report_limit, 1)
            self.assertEqual(user.client.monthly_file_limit, 5)
            self.assertTrue(user.client.allowed_procurement_report)
            self.assertFalse(user.is_email_verified)
            self.assertEqual(user.client.telegram_accounts, [])
            self.assertIn("Email verification required", user.client.notes)
            self.assertNotIn("StrongPass123", user.password_hash)
            self.assertEqual(authenticated.id, user.id)
            self.assertIsNone(wrong_password)
        finally:
            db.close()

    def test_web_session_uses_token_hash_and_csrf(self) -> None:
        db = self.Session()
        try:
            user = create_web_user(db, email="buyer@example.com", password="StrongPass123", name="Buyer")
            token, csrf_token, session = create_web_session(db, user, request=fake_request())

            self.assertTrue(token)
            self.assertTrue(csrf_token)
            self.assertNotEqual(session.token_hash, token)
            self.assertEqual(session.csrf_token, csrf_token)
            self.assertEqual(get_web_session_by_token(db, token).id, session.id)
        finally:
            db.close()

    def test_registration_honeypot_blocks_bot_without_creating_user(self) -> None:
        db = self.Session()
        try:
            with self.assertRaises(HTTPException) as raised:
                customer_register_api(
                    WebRegisterRequest(
                        email="bot@example.com",
                        password="StrongPass123",
                        name="Bot",
                        website="https://spam.example",
                    ),
                    fake_request(),
                    Response(),
                    db,
                )

            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(db.query(WebUser).count(), 0)
            self.assertEqual(db.query(WebRegistrationAttempt).filter(WebRegistrationAttempt.status == "bot_blocked").count(), 1)
        finally:
            db.close()

    def test_registration_rate_limit_counts_same_ip(self) -> None:
        db = self.Session()
        try:
            for index in range(3):
                payload = customer_register_api(
                    WebRegisterRequest(
                        email=f"buyer-{index}@example.com",
                        password="StrongPass123",
                        name="Buyer",
                    ),
                    fake_request(),
                    Response(),
                    db,
                )
                self.assertTrue(payload["authenticated"])

            with self.assertRaises(HTTPException) as raised:
                customer_register_api(
                    WebRegisterRequest(
                        email="buyer-limited@example.com",
                        password="StrongPass123",
                        name="Buyer",
                    ),
                    fake_request(),
                    Response(),
                    db,
                )

            self.assertEqual(raised.exception.status_code, 429)
            self.assertEqual(db.query(WebUser).count(), 3)
            self.assertEqual(db.query(WebRegistrationAttempt).filter(WebRegistrationAttempt.status == "rate_limited").count(), 1)
        finally:
            db.close()

    def test_admin_can_manually_verify_web_user_email(self) -> None:
        db = self.Session()
        try:
            user = create_web_user(db, email="buyer@example.com", password="StrongPass123", name="Buyer")
            token, _record = create_email_verification_token(db, user, request=fake_request())

            payload = admin_verify_web_user_email(user.client_id, user.id, db)
            db.refresh(user)
            open_token = (
                db.query(WebEmailVerificationToken)
                .filter(WebEmailVerificationToken.token_hash.isnot(None))
                .filter(WebEmailVerificationToken.used_at.is_(None))
                .first()
            )

            self.assertTrue(payload["success"])
            self.assertTrue(user.is_email_verified)
            self.assertIsNone(open_token)
            self.assertTrue(token)
        finally:
            db.close()

    async def test_new_web_trial_user_must_verify_email_before_starting_job(self) -> None:
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
            db.commit()
            user = create_web_user(db, email="buyer@example.com", password="StrongPass123", name="Buyer")

            with self.assertRaises(HTTPException) as raised:
                await create_customer_job_api(
                    mode=MODE_SUPPLIER_SEARCH,
                    text="Нужно найти поставщиков сотового поликарбоната",
                    source_urls="",
                    target_suppliers=0,
                    files=[],
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )

            self.assertEqual(raised.exception.status_code, 403)
            self.assertIn("Подтвердите email", str(raised.exception.detail))
            self.assertEqual(db.query(Job).filter(Job.client_id == user.client_id).count(), 0)
        finally:
            db.close()

    async def test_verified_web_trial_user_can_start_trial_job(self) -> None:
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
            db.commit()
            user = create_web_user(db, email="buyer@example.com", password="StrongPass123", name="Buyer")
            token, _record = create_email_verification_token(db, user, request=fake_request())
            verified = verify_email_token(db, token)

            payload = await create_customer_job_api(
                mode=MODE_SUPPLIER_SEARCH,
                text="Нужно найти поставщиков сухих строительных смесей",
                source_urls="",
                target_suppliers=0,
                files=[],
                context=WebAuthContext(user=verified, session=None),
                db=db,
            )

            self.assertFalse(payload["batch"])
            self.assertTrue(verified.is_email_verified)
            self.assertEqual(db.query(Job).filter(Job.client_id == user.client_id).count(), 1)
        finally:
            db.close()

    def test_customer_session_hides_trial_label_when_paid_grants_exist(self) -> None:
        db = self.Session()
        try:
            client = Client(
                id="client-1",
                telegram_id="web:client-1",
                is_trial=True,
                monthly_supplier_search_limit=1,
                monthly_procurement_report_limit=1,
            )
            db.add(client)
            db.commit()
            user = create_web_user(
                db,
                email="buyer-paid@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
                email_verified=True,
            )
            db.add_all(
                [
                    BillingTransaction(
                        client_id=client.id,
                        kind=KIND_SUPPLIER_SEARCH,
                        operation=OP_GRANT,
                        units=499,
                        created_by="admin",
                    ),
                    BillingTransaction(
                        client_id=client.id,
                        kind=KIND_PROCUREMENT_REPORT,
                        operation=OP_GRANT,
                        units=499,
                        created_by="admin",
                    ),
                ]
            )
            db.commit()

            payload = customer_session_payload(db, user)

            self.assertFalse(payload["user"]["is_trial"])
            self.assertEqual(payload["balance"]["supplier_search"]["available"], 499)
            self.assertEqual(payload["balance"]["procurement_report"]["available"], 499)
        finally:
            db.close()

    def test_password_reset_request_and_admin_completion(self) -> None:
        db = self.Session()
        try:
            user = create_web_user(db, email="buyer-reset@example.com", password="StrongPass123", name="Buyer")
            _token, _csrf_token, session = create_web_session(db, user, request=fake_request())

            known = customer_password_reset_request_api(
                WebPasswordResetRequestCreate(email="Buyer-Reset@Example.com"),
                fake_request(),
                db,
            )
            unknown = customer_password_reset_request_api(
                WebPasswordResetRequestCreate(email="missing-reset@example.com"),
                fake_request(),
                db,
            )
            reset_request = db.query(WebPasswordResetRequest).one()

            completed = complete_web_password_reset(
                reset_request.id,
                WebPasswordResetComplete(password="NextPass123", note="manual support"),
                db,
            )
            db.refresh(session)

            self.assertTrue(known["success"])
            self.assertTrue(unknown["success"])
            self.assertEqual(completed["temporary_password"], "NextPass123")
            self.assertEqual(completed["request"]["status"], "completed")
            self.assertIsNone(authenticate_web_user(db, "buyer-reset@example.com", "StrongPass123"))
            self.assertEqual(authenticate_web_user(db, "buyer-reset@example.com", "NextPass123").id, user.id)
            self.assertIsNotNone(session.revoked_at)
        finally:
            db.close()

    async def test_customer_supplier_job_from_text_reserves_web_balance(self) -> None:
        db = self.Session()
        try:
            db.add(SystemSettings(id=1, default_supplier_target=7))
            client = Client(
                id="client-1",
                telegram_id="web:client-1",
                monthly_supplier_search_limit=3,
                allowed_procurement_report=True,
            )
            db.add(client)
            db.commit()
            user = create_web_user(
                db,
                email="buyer@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
                email_verified=True,
            )
            context = WebAuthContext(user=user, session=None)

            payload = await create_customer_job_api(
                mode=MODE_SUPPLIER_SEARCH,
                text="Нужно поставить насосы для водоснабжения",
                source_urls="",
                target_suppliers=0,
                files=[],
                context=context,
                db=db,
            )

            self.assertFalse(payload["batch"])
            self.assertEqual(payload["job"]["mode"], MODE_SUPPLIER_SEARCH)
            self.assertEqual(payload["job"]["target_suppliers"], 7)
            self.assertEqual(payload["job"]["file_count"], 1)
            self.assertEqual(payload["job"]["client_id"], "client-1")
            reserve = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.client_id == "client-1")
                .filter(BillingTransaction.operation == OP_RESERVE)
                .one()
            )
            self.assertEqual(reserve.kind, KIND_SUPPLIER_SEARCH)
            self.assertEqual(reserve.units, 1)
        finally:
            db.close()

    async def test_customer_supplier_batch_creates_one_job_per_file(self) -> None:
        db = self.Session()
        try:
            db.add(SystemSettings(id=1, default_supplier_target=15))
            client = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=5)
            db.add(client)
            db.commit()
            user = create_web_user(
                db,
                email="buyer@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
                email_verified=True,
            )
            context = WebAuthContext(user=user, session=None)
            files = [
                UploadFile(filename="tz-1.txt", file=BytesIO(b"first technical task")),
                UploadFile(filename="tz-2.txt", file=BytesIO(b"second technical task")),
            ]

            payload = await create_customer_job_api(
                mode=MODE_SUPPLIER_SEARCH,
                text="",
                source_urls="",
                target_suppliers=0,
                files=files,
                context=context,
                db=db,
            )

            self.assertTrue(payload["batch"])
            self.assertEqual(payload["count"], 2)
            self.assertEqual(db.query(Job).filter(Job.client_id == "client-1").count(), 2)
        finally:
            db.close()

    def test_customer_download_rejects_foreign_job_and_charges_owner_download(self) -> None:
        db = self.Session()
        try:
            owner = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=1)
            other = Client(id="client-2", telegram_id="web:client-2", monthly_supplier_search_limit=1)
            db.add_all([owner, other])
            db.commit()
            owner_user = create_web_user(db, email="owner@example.com", password="StrongPass123", name="Owner", client=owner)
            other_user = create_web_user(db, email="other@example.com", password="StrongPass123", name="Other", client=other)
            with tempfile.TemporaryDirectory() as tmp:
                output_path = Path(tmp) / "result.xlsx"
                output_path.write_bytes(b"xlsx")
                job = Job(
                    id="job-1",
                    client_id=owner.id,
                    mode=MODE_SUPPLIER_SEARCH,
                    status="completed",
                    result_path=str(output_path),
                )
                db.add(job)
                db.add(
                    BillingTransaction(
                        client_id=owner.id,
                        job_id=job.id,
                        kind=KIND_SUPPLIER_SEARCH,
                        operation=OP_RESERVE,
                        units=1,
                    )
                )
                db.commit()

                with self.assertRaises(HTTPException) as raised:
                    download_customer_job_api(job.id, context=WebAuthContext(user=other_user, session=None), db=db)
                response = download_customer_job_api(job.id, context=WebAuthContext(user=owner_user, session=None), db=db)

            self.assertEqual(raised.exception.status_code, 404)
            self.assertEqual(response.filename, "result.xlsx")
            charge = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.job_id == "job-1")
                .filter(BillingTransaction.operation == OP_CHARGE)
                .one()
            )
            self.assertEqual(charge.units, 1)
        finally:
            db.close()

    def test_customer_combined_job_exposes_and_downloads_separate_result_files(self) -> None:
        import app.jobs as jobs

        original_job_dir = jobs.job_dir
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=1)
            db.add(client)
            db.commit()
            user = create_web_user(db, email="owner@example.com", password="StrongPass123", name="Owner", client=client)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs.job_dir = lambda job_id: root / "jobs" / job_id
                out_dir = jobs.job_dir("job-1") / "output"
                out_dir.mkdir(parents=True)
                analysis_path = out_dir / "analysis.docx"
                suppliers_path = out_dir / "suppliers.xlsx"
                analysis_path.write_bytes(b"docx")
                suppliers_path.write_bytes(b"xlsx")
                evidence_path = out_dir / "evidence.json"
                evidence_path.write_text(
                    """
{
  "output_files": [
    {"kind": "analysis", "path": "%s"},
    {"kind": "suppliers", "path": "%s"}
  ]
}
"""
                    % (analysis_path, suppliers_path),
                    encoding="utf-8",
                )
                job = Job(
                    id="job-1",
                    client_id=client.id,
                    mode="analysis_and_suppliers",
                    status="completed",
                    result_path=str(out_dir / "archive.zip"),
                    evidence_path=str(evidence_path),
                )
                db.add(job)
                db.add_all(
                    [
                        BillingTransaction(
                            client_id=client.id,
                            job_id=job.id,
                            kind=KIND_PROCUREMENT_REPORT,
                            operation=OP_RESERVE,
                            units=1,
                        ),
                        BillingTransaction(
                            client_id=client.id,
                            job_id=job.id,
                            kind=KIND_SUPPLIER_SEARCH,
                            operation=OP_RESERVE,
                            units=1,
                        ),
                    ]
                )
                db.commit()

                payload = customer_job_to_dict(job)
                analysis_response = download_customer_job_file_api(
                    job.id,
                    "analysis",
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )
                suppliers_response = download_customer_job_file_api(
                    job.id,
                    "suppliers",
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )
                charges = (
                    db.query(BillingTransaction)
                    .filter(BillingTransaction.job_id == job.id)
                    .filter(BillingTransaction.operation == OP_CHARGE)
                    .all()
                )
        finally:
            jobs.job_dir = original_job_dir
            db.close()

        self.assertEqual(
            payload["result_files"],
            [
                {"kind": "analysis", "label": "Анализ", "filename": "analysis.docx"},
                {"kind": "suppliers", "label": "Поставщики", "filename": "suppliers.xlsx"},
            ],
        )
        self.assertEqual(analysis_response.filename, "analysis.docx")
        self.assertEqual(suppliers_response.filename, "suppliers.xlsx")
        self.assertEqual(sorted((item.kind, item.units) for item in charges), [(KIND_PROCUREMENT_REPORT, 1), (KIND_SUPPLIER_SEARCH, 1)])

    def test_customer_job_title_uses_result_subject_not_raw_filename(self) -> None:
        import app.jobs as jobs

        original_job_dir = jobs.job_dir
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=1)
            db.add(client)
            db.commit()
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs.job_dir = lambda job_id: root / "jobs" / job_id
                out_dir = jobs.job_dir("job-1") / "output"
                out_dir.mkdir(parents=True)
                result_path = out_dir / "Сотовый поликарбонат_поставщики.xlsx"
                result_path.write_bytes(b"xlsx")
                evidence_path = out_dir / "evidence.json"
                evidence_path.write_text(
                    """
{
  "subject": "Сотовый поликарбонат",
  "output_files": [
    {"kind": "suppliers", "path": "%s"}
  ]
}
"""
                    % result_path,
                    encoding="utf-8",
                )
                job = Job(
                    id="job-1",
                    client_id=client.id,
                    mode=MODE_SUPPLIER_SEARCH,
                    status="completed",
                    title="07 ТЗ",
                    result_path=str(result_path),
                    evidence_path=str(evidence_path),
                )
                db.add(job)
                db.commit()

                payload = customer_job_to_dict(job)
        finally:
            jobs.job_dir = original_job_dir
            db.close()

        self.assertEqual(payload["human_title"], "ТЗ: Сотовый поликарбонат")

    def test_customer_decline_partial_job_releases_reservation(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=1)
            db.add(client)
            db.commit()
            user = create_web_user(db, email="buyer@example.com", password="StrongPass123", name="Buyer", client=client)
            job = Job(
                id="job-1",
                client_id=client.id,
                mode=MODE_SUPPLIER_SEARCH,
                status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
            )
            db.add(job)
            db.add(
                BillingTransaction(
                    client_id=client.id,
                    job_id=job.id,
                    kind=KIND_SUPPLIER_SEARCH,
                    operation=OP_RESERVE,
                    units=1,
                )
            )
            db.commit()

            payload = decline_customer_partial_job_api(job.id, context=WebAuthContext(user=user, session=None), db=db)

            db.refresh(job)
            self.assertTrue(payload["success"])
            self.assertEqual(job.status, STATUS_CUSTOMER_DECLINED)
            release = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.job_id == job.id)
                .filter(BillingTransaction.operation == OP_RELEASE)
                .one()
            )
            self.assertEqual(release.units, 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
