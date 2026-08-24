from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.billing import (
    KIND_PROCUREMENT_REPORT,
    KIND_SUPPLIER_SEARCH,
    KIND_SUPPLIER_SEARCH_EXTRA,
    OP_GRANT,
    OP_RESERVE,
    OP_CHARGE,
    OP_RELEASE,
    STATUS_AWAITING_CUSTOMER_CONFIRMATION,
    STATUS_CONFIRMATION_EXPIRED,
    STATUS_CUSTOMER_DECLINED,
)
from app.db import Base
from app.jobs import MODE_SUPPLIER_SEARCH
from app.legal import LEGAL_VERSION
from app.main import (
    admin_verify_web_user_email,
    create_additional_supplier_search_api,
    customer_email_change_api,
    create_customer_job_api,
    customer_register_api,
    customer_jobs_api,
    customer_job_to_dict,
    customer_quote_request_api,
    customer_session_payload,
    accept_customer_partial_job_api,
    cancel_customer_job_api,
    decline_customer_partial_job_api,
    download_customer_job_api,
    download_customer_job_file_api,
    download_customer_quote_request_docx_api,
)
from app.main import complete_web_password_reset, customer_password_reset_request_api
from app.models import BillingTransaction, Client, ClientTariffOverride, Job, JobFile, LegalAcceptance, SupplierResult, SystemSettings, TariffPackage, WebEmailVerificationToken, WebPasswordResetRequest, WebRegistrationAttempt, WebUser, now_utc
from app.schemas import WebEmailChangeRequest, WebPasswordResetComplete, WebPasswordResetRequestCreate, WebRegisterRequest
from app.web_auth import (
    CSRF_HEADER,
    WebAuthContext,
    authenticate_web_user,
    create_email_verification_token,
    create_web_session,
    create_web_user,
    get_web_session_by_token,
    verify_email_token,
)


def fake_request(*, method: str = "POST", csrf_token: str = "") -> SimpleNamespace:
    headers = {"user-agent": "tests"}
    if csrf_token:
        headers[CSRF_HEADER] = csrf_token
    return SimpleNamespace(
        method=method,
        client=SimpleNamespace(host="127.0.0.1"),
        headers=headers,
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
            db.add_all([
                TariffPackage(kind=KIND_SUPPLIER_SEARCH, name="Базовый поиск", units=1, price_kopeks=6_000, is_active=True),
                TariffPackage(kind=KIND_PROCUREMENT_REPORT, name="Базовый анализ", units=1, price_kopeks=10_000, is_active=True),
            ])
            db.commit()

            user = create_web_user(db, email="Buyer@Example.COM", password="StrongPass123", name="Buyer")
            authenticated = authenticate_web_user(db, "buyer@example.com", "StrongPass123")
            wrong_password = authenticate_web_user(db, "buyer@example.com", "wrong")

            self.assertEqual(user.email, "buyer@example.com")
            self.assertTrue(user.client.telegram_id.startswith("web:"))
            self.assertTrue(user.client.is_trial)
            self.assertEqual(user.client.monthly_supplier_search_limit, 2)
            self.assertEqual(user.client.monthly_procurement_report_limit, 1)
            self.assertEqual(user.client.money_balance_kopeks, 22_000)
            self.assertEqual(
                db.query(BillingTransaction)
                .filter(BillingTransaction.client_id == user.client.id)
                .filter(BillingTransaction.operation == OP_GRANT)
                .filter(BillingTransaction.created_by == "system")
                .count(),
                2,
            )
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
                        terms_accepted=True,
                        personal_data_consent=True,
                        legal_version=LEGAL_VERSION,
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
                        terms_accepted=True,
                        personal_data_consent=True,
                        legal_version=LEGAL_VERSION,
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

    def test_registration_requires_and_records_separate_legal_acceptances(self) -> None:
        db = self.Session()
        try:
            with self.assertRaises(HTTPException) as raised:
                customer_register_api(
                    WebRegisterRequest(email="no-consent@example.com", password="StrongPass123"),
                    fake_request(),
                    Response(),
                    db,
                )
            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(db.query(WebUser).count(), 0)

            payload = customer_register_api(
                WebRegisterRequest(
                    email="accepted@example.com",
                    password="StrongPass123",
                    terms_accepted=True,
                    personal_data_consent=True,
                    legal_version=LEGAL_VERSION,
                ),
                fake_request(),
                Response(),
                db,
            )
            user = db.query(WebUser).filter(WebUser.email == "accepted@example.com").one()
            acceptances = db.query(LegalAcceptance).filter(LegalAcceptance.subject_id == user.id).all()

            self.assertTrue(payload["authenticated"])
            self.assertEqual({item.document_type for item in acceptances}, {"terms", "personal_data"})
            self.assertEqual({item.document_version for item in acceptances}, {LEGAL_VERSION})
            self.assertEqual({item.source for item in acceptances}, {"web"})
            self.assertEqual({item.ip_address for item in acceptances}, {"127.0.0.1"})
        finally:
            db.close()

    def test_registration_rolls_back_account_when_acceptance_cannot_be_recorded(self) -> None:
        db = self.Session()
        try:
            with patch("app.main.record_legal_acceptance", side_effect=RuntimeError("acceptance storage failed")):
                with self.assertRaisesRegex(RuntimeError, "acceptance storage failed"):
                    customer_register_api(
                        WebRegisterRequest(
                            email="rollback@example.com",
                            password="StrongPass123",
                            terms_accepted=True,
                            personal_data_consent=True,
                            legal_version=LEGAL_VERSION,
                        ),
                        fake_request(),
                        Response(),
                        db,
                    )

            self.assertEqual(db.query(WebUser).count(), 0)
            self.assertEqual(db.query(Client).count(), 0)
            self.assertEqual(db.query(LegalAcceptance).count(), 0)
        finally:
            db.close()

    def test_duplicate_registration_with_same_email_is_blocked(self) -> None:
        db = self.Session()
        try:
            # First registration succeeds
            customer_register_api(
                WebRegisterRequest(
                    email="duplicate@example.com",
                    password="StrongPass123",
                    terms_accepted=True,
                    personal_data_consent=True,
                    legal_version=LEGAL_VERSION,
                ),
                fake_request(),
                Response(),
                db,
            )
            self.assertEqual(db.query(WebUser).filter(WebUser.email == "duplicate@example.com").count(), 1)

            # Second registration with identical email must raise 409 HTTPException
            from fastapi import HTTPException

            with self.assertRaises(HTTPException) as ctx:
                customer_register_api(
                    WebRegisterRequest(
                        email="duplicate@example.com",
                        password="AnotherPass456",
                        terms_accepted=True,
                        personal_data_consent=True,
                        legal_version=LEGAL_VERSION,
                    ),
                    fake_request(),
                    Response(),
                    db,
                )
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertIn("уже зарегистрирован", ctx.exception.detail)
            # Ensure only 1 user exists
            self.assertEqual(db.query(WebUser).filter(WebUser.email == "duplicate@example.com").count(), 1)
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

    def test_resending_verification_keeps_previous_fresh_link_valid(self) -> None:
        db = self.Session()
        try:
            user = create_web_user(db, email="buyer@example.com", password="StrongPass123", name="Buyer")
            first_token, first_record = create_email_verification_token(db, user, request=fake_request())
            second_token, second_record = create_email_verification_token(db, user, request=fake_request())
            db.refresh(first_record)
            self.assertIsNone(first_record.used_at)

            verified = verify_email_token(db, first_token)
            db.refresh(first_record)
            db.refresh(second_record)

            self.assertTrue(verified.is_email_verified)
            self.assertIsNotNone(first_record.used_at)
            self.assertIsNotNone(second_record.used_at)
            with self.assertRaises(ValueError):
                verify_email_token(db, second_token)
        finally:
            db.close()

    def test_verification_link_for_old_email_does_not_confirm_changed_email(self) -> None:
        db = self.Session()
        try:
            user = create_web_user(db, email="old@example.com", password="StrongPass123", name="Buyer")
            token, _record = create_email_verification_token(db, user, request=fake_request())
            user.email = "new@example.com"
            db.commit()

            with self.assertRaises(ValueError):
                verify_email_token(db, token)
        finally:
            db.close()

    def test_customer_can_change_unverified_email_and_send_new_verification(self) -> None:
        db = self.Session()
        try:
            user = create_web_user(db, email="wrong@example.com", password="StrongPass123", name="Buyer")
            _session_token, csrf_token, session = create_web_session(db, user, request=fake_request())

            with patch("app.main.send_email_verification", return_value=True):
                payload = customer_email_change_api(
                    WebEmailChangeRequest(email="Correct@Example.com"),
                    fake_request(method="PATCH", csrf_token=csrf_token),
                    WebAuthContext(user=user, session=session),
                    db,
                )

            db.refresh(user)
            open_tokens = (
                db.query(WebEmailVerificationToken)
                .filter(WebEmailVerificationToken.user_id == user.id)
                .filter(WebEmailVerificationToken.email == "correct@example.com")
                .filter(WebEmailVerificationToken.used_at.is_(None))
                .count()
            )

            self.assertEqual(user.email, "correct@example.com")
            self.assertFalse(user.is_email_verified)
            self.assertTrue(payload["verification_email_sent"])
            self.assertEqual(payload["user"]["email"], "correct@example.com")
            self.assertEqual(open_tokens, 1)
        finally:
            db.close()

    def test_send_email_verification_uses_email_relay(self) -> None:
        from app import web_auth

        db = self.Session()
        try:
            user = create_web_user(db, email="relay-buyer@example.com", password="StrongPass123", name="Buyer")
            captured: dict = {}

            class FakeResponse:
                status_code = 200

                def json(self) -> dict:
                    return {"success": True}

            class FakeClient:
                def __init__(self, timeout: float) -> None:
                    captured["timeout"] = timeout

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return False

                def post(self, url: str, *, headers: dict, json: dict):
                    captured["url"] = url
                    captured["headers"] = headers
                    captured["json"] = json
                    return FakeResponse()

            with (
                patch.object(web_auth.config, "email_relay_url", "http://relay.example"),
                patch.object(web_auth.config, "email_relay_api_key", "relay-key"),
                patch.object(web_auth.config, "email_from_name", "TenderLex"),
                patch.object(web_auth.config, "email_from_email", "noreply@example.com"),
                patch.object(web_auth.httpx, "Client", FakeClient),
            ):
                sent = web_auth.send_email_verification(user, "verify-token", public_base_url="https://tenderlex.ru")

            self.assertTrue(sent)
            self.assertEqual(captured["url"], "http://relay.example/send")
            self.assertEqual(captured["headers"]["Authorization"], "Bearer relay-key")
            self.assertEqual(captured["json"]["to"], "relay-buyer@example.com")
            self.assertEqual(captured["json"]["from_name"], "TenderLex")
            self.assertEqual(captured["json"]["from_email"], "noreply@example.com")
            self.assertEqual(captured["json"]["attachments"], [])
            self.assertIn("Подтвердите email", captured["json"]["html"])
            self.assertIn("verify-token", captured["json"]["html"])
        finally:
            db.close()

    def test_send_email_verification_keeps_smtp_fallback(self) -> None:
        from app import web_auth

        db = self.Session()
        try:
            user = create_web_user(db, email="smtp-buyer@example.com", password="StrongPass123", name="Buyer")
            captured: dict = {}

            class FakeSmtp:
                def __init__(self, host: str, port: int, timeout: int) -> None:
                    captured["smtp"] = {"host": host, "port": port, "timeout": timeout}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return False

                def starttls(self) -> None:
                    captured["starttls"] = True

                def login(self, username: str, password: str) -> None:
                    captured["login"] = {"username": username, "password": password}

                def send_message(self, message) -> None:
                    captured["message"] = message

            with (
                patch.object(web_auth.config, "email_relay_url", ""),
                patch.object(web_auth.config, "email_relay_api_key", ""),
                patch.object(web_auth.config, "email_from_name", "TenderLex"),
                patch.object(web_auth.config, "email_from_email", ""),
                patch.object(web_auth.config, "smtp_host", "smtp.example"),
                patch.object(web_auth.config, "smtp_port", 587),
                patch.object(web_auth.config, "smtp_username", "smtp-user"),
                patch.object(web_auth.config, "smtp_password", "smtp-password"),
                patch.object(web_auth.config, "smtp_from", "noreply@example.com"),
                patch.object(web_auth.config, "smtp_use_tls", True),
                patch.object(web_auth.config, "smtp_use_ssl", False),
                patch.object(web_auth.config, "smtp_timeout_seconds", 15),
                patch.object(web_auth.smtplib, "SMTP", FakeSmtp),
            ):
                sent = web_auth.send_email_verification(user, "verify-token", public_base_url="https://tenderlex.ru")

            self.assertTrue(sent)
            self.assertEqual(captured["smtp"], {"host": "smtp.example", "port": 587, "timeout": 15})
            self.assertTrue(captured["starttls"])
            self.assertEqual(captured["login"], {"username": "smtp-user", "password": "smtp-password"})
            self.assertEqual(captured["message"]["To"], "smtp-buyer@example.com")
            self.assertIn("TenderLex", captured["message"]["Subject"])
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

    def test_customer_session_uses_supplier_fallback_for_extra_search_balance(self) -> None:
        db = self.Session()
        try:
            db.add(SystemSettings(id=1))
            client = Client(
                id="client-1",
                telegram_id="web:client-1",
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
            user = create_web_user(
                db,
                email="buyer-extra-fallback@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
                email_verified=True,
            )

            payload = customer_session_payload(db, user)
            extra = payload["balance"][KIND_SUPPLIER_SEARCH_EXTRA]
        finally:
            db.close()

        self.assertEqual(extra["source"], "supplier_search_access_fallback")
        self.assertEqual(extra["available"], 1000)
        self.assertEqual(extra["price_kopeks"], 5_000)
        self.assertFalse(extra["low"])

    def test_customer_session_keeps_individual_extra_supplier_price(self) -> None:
        db = self.Session()
        try:
            db.add(SystemSettings(id=1))
            client = Client(
                id="client-1",
                telegram_id="web:client-1",
                monthly_supplier_search_limit=10,
                monthly_procurement_report_limit=10,
                money_balance_kopeks=84_000,
            )
            db.add_all([
                client,
                ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH, price_kopeks=6_000),
                ClientTariffOverride(client_id=client.id, kind=KIND_PROCUREMENT_REPORT, price_kopeks=6_000),
                ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH_EXTRA, price_kopeks=3_000),
            ])
            db.commit()
            user = create_web_user(
                db,
                email="buyer-extra-individual@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
                email_verified=True,
            )

            payload = customer_session_payload(db, user)
            extra = payload["balance"][KIND_SUPPLIER_SEARCH_EXTRA]
            extra_price = payload["balance"]["effective_prices"][KIND_SUPPLIER_SEARCH_EXTRA]
        finally:
            db.close()

        self.assertEqual(extra["source"], "supplier_search_access_fallback")
        self.assertEqual(extra["available"], 10)
        self.assertEqual(extra["price_kopeks"], 3_000)
        self.assertEqual(extra_price["price_kopeks"], 3_000)
        self.assertEqual(extra_price["source"], "client_override")

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

    async def test_customer_supplier_job_uses_client_supplier_target_override(self) -> None:
        db = self.Session()
        try:
            db.add(SystemSettings(id=1, default_supplier_target=25))
            client = Client(
                id="client-1",
                telegram_id="web:client-1",
                monthly_supplier_search_limit=3,
                supplier_target_min=40,
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

            payload = await create_customer_job_api(
                mode=MODE_SUPPLIER_SEARCH,
                text="Нужно найти поставщиков кабельных лотков для строительного объекта",
                source_urls="",
                target_suppliers=3,
                files=[],
                context=WebAuthContext(user=user, session=None),
                db=db,
            )

            self.assertEqual(payload["job"]["target_suppliers"], 40)
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
                    status="partial",
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
                quote_path = out_dir / "quote.docx"
                quote_md_path = out_dir / "quote.md"
                analysis_path.write_bytes(b"docx")
                suppliers_path.write_bytes(b"xlsx")
                quote_path.write_bytes(b"quote-docx")
                quote_md_path.write_text("ЗАПРОС КП\n\n| № | Наименование |\n|---|---|\n| 1 | Товар |", encoding="utf-8")
                evidence_path = out_dir / "evidence.json"
                evidence_path.write_text(
                    """
{
  "output_files": [
    {"kind": "analysis", "path": "%s"},
    {"kind": "suppliers", "path": "%s"},
    {"kind": "quote_request", "label": "Запрос КП", "path": "%s", "content_path": "%s"}
  ]
}
"""
                    % (analysis_path, suppliers_path, quote_path, quote_md_path),
                    encoding="utf-8",
                )
                job = Job(
                    id="job-1",
                    client_id=client.id,
                    mode="analysis_and_suppliers",
                    status="partial",
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
                quote_payload = customer_quote_request_api(
                    job.id,
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )
                quote_response = download_customer_job_file_api(
                    job.id,
                    "quote_request",
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )
                edited_quote_response = download_customer_quote_request_docx_api(
                    job.id,
                    content=quote_payload["content"],
                    filename="custom-quote.docx",
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
                {"kind": "quote_request", "label": "Запрос КП", "filename": "quote.docx"},
            ],
        )
        self.assertEqual(analysis_response.filename, "analysis.docx")
        self.assertEqual(suppliers_response.filename, "suppliers.xlsx")
        self.assertEqual(quote_payload["filename"], "quote.docx")
        self.assertIn("ЗАПРОС КП", quote_payload["content"])
        self.assertEqual(quote_response.filename, "quote.docx")
        self.assertEqual(
            edited_quote_response.media_type,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertIn("custom-quote.docx", edited_quote_response.headers["content-disposition"])
        self.assertEqual(sorted((item.kind, item.units) for item in charges), [(KIND_PROCUREMENT_REPORT, 1), (KIND_SUPPLIER_SEARCH, 1)])

    def test_customer_can_start_find_more_suppliers_job_with_exclusions(self) -> None:
        import app.jobs as jobs
        import app.main as main_module

        original_job_dir = jobs.job_dir
        original_enqueue = main_module.enqueue_job
        db = self.Session()
        try:
            db.add(SystemSettings(id=1, default_supplier_target=25))
            client = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=2)
            db.add(client)
            db.commit()
            user = create_web_user(
                db,
                email="buyer-more@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
                email_verified=True,
            )
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs.job_dir = lambda job_id: root / "jobs" / job_id
                main_module.enqueue_job = lambda _job_id: None
                source_path = root / "previous-tz.txt"
                source_path.write_text("ТЗ: нужны поставщики промышленных насосов", encoding="utf-8")
                original = Job(
                    id="job-1",
                    client_id=client.id,
                    mode=MODE_SUPPLIER_SEARCH,
                    status="partial",
                    title="Промышленные насосы",
                    target_suppliers=25,
                    verified_count=11,
                    file_count=1,
                )
                db.add(original)
                db.add(JobFile(job_id=original.id, original_filename="tz.txt", stored_path=str(source_path)))
                db.add(
                    SupplierResult(
                        job_id=original.id,
                        company_name="ООО Насос",
                        site="https://pump.example",
                        evidence_status="verified",
                    )
                )
                db.commit()

                payload = create_additional_supplier_search_api(
                    original.id,
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )
                new_job = db.get(Job, payload["job"]["id"])
                exclusions_path = jobs.job_dir(new_job.id) / "input" / "excluded_suppliers.json"
                self.assertTrue(exclusions_path.exists())
                exclusions_text = exclusions_path.read_text(encoding="utf-8")

            reserve = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.job_id == new_job.id)
                .filter(BillingTransaction.operation == OP_RESERVE)
                .one()
            )
            self.assertTrue(payload["success"])
            self.assertTrue(customer_job_to_dict(original)["can_find_more_suppliers"])
            self.assertEqual(new_job.mode, MODE_SUPPLIER_SEARCH)
            self.assertEqual(new_job.target_suppliers, 14)
            self.assertEqual(payload["job"]["prior_verified_count"], 11)
            self.assertEqual(payload["job"]["cumulative_verified_count"], 11)
            self.assertEqual(reserve.kind, KIND_SUPPLIER_SEARCH)
            self.assertEqual(reserve.units, 1)
            self.assertIn("pump.example", exclusions_text)
        finally:
            jobs.job_dir = original_job_dir
            main_module.enqueue_job = original_enqueue
            db.close()

    def test_customer_find_more_suppliers_uses_extra_tariff_when_configured(self) -> None:
        import app.jobs as jobs
        import app.main as main_module

        original_job_dir = jobs.job_dir
        original_enqueue = main_module.enqueue_job
        db = self.Session()
        try:
            db.add(SystemSettings(id=1, default_supplier_target=25))
            db.add(TariffPackage(kind=KIND_SUPPLIER_SEARCH_EXTRA, name="Добор", units=1, price_kopeks=3_000, is_active=True))
            client = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=2, money_balance_kopeks=3_000)
            db.add(client)
            db.add(
                BillingTransaction(
                    client_id=client.id,
                    kind=KIND_SUPPLIER_SEARCH_EXTRA,
                    operation=OP_GRANT,
                    units=1,
                    amount_kopeks=3_000,
                    balance_after_kopeks=3_000,
                    created_by="admin",
                )
            )
            db.commit()
            user = create_web_user(
                db,
                email="buyer-extra@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
                email_verified=True,
            )
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs.job_dir = lambda job_id: root / "jobs" / job_id
                main_module.enqueue_job = lambda _job_id: None
                source_path = root / "previous-tz.txt"
                source_path.write_text("ТЗ: нужны поставщики промышленных насосов", encoding="utf-8")
                original = Job(
                    id="job-1",
                    client_id=client.id,
                    mode=MODE_SUPPLIER_SEARCH,
                    status="partial",
                    title="Промышленные насосы",
                    target_suppliers=25,
                    verified_count=11,
                    file_count=1,
                )
                db.add(original)
                db.add(JobFile(job_id=original.id, original_filename="tz.txt", stored_path=str(source_path)))
                db.add(SupplierResult(job_id=original.id, company_name="ООО Насос", site="https://pump.example", evidence_status="verified"))
                db.commit()

                payload = create_additional_supplier_search_api(
                    original.id,
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )
                new_job = db.get(Job, payload["job"]["id"])

            reserve = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.job_id == new_job.id)
                .filter(BillingTransaction.operation == OP_RESERVE)
                .one()
            )
            db.refresh(client)
            self.assertEqual(reserve.kind, KIND_SUPPLIER_SEARCH_EXTRA)
            self.assertEqual(reserve.units, 1)
            self.assertEqual(reserve.amount_kopeks, 3_000)
            self.assertEqual(client.money_reserved_kopeks, 3_000)
        finally:
            jobs.job_dir = original_job_dir
            main_module.enqueue_job = original_enqueue
            db.close()

    def test_repeated_find_more_suppliers_keeps_previous_exclusions(self) -> None:
        import app.jobs as jobs
        import app.main as main_module

        original_job_dir = jobs.job_dir
        original_enqueue = main_module.enqueue_job
        db = self.Session()
        try:
            db.add(SystemSettings(id=1, default_supplier_target=25))
            client = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=10)
            db.add(client)
            db.commit()
            user = create_web_user(
                db,
                email="buyer-chain@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
                email_verified=True,
            )
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs.job_dir = lambda job_id: root / "jobs" / job_id
                main_module.enqueue_job = lambda _job_id: None
                source_path = root / "previous-tz.txt"
                source_path.write_text("ТЗ: нужны поставщики промышленных насосов", encoding="utf-8")
                original = Job(
                    id="job-1",
                    client_id=client.id,
                    mode=MODE_SUPPLIER_SEARCH,
                    status="completed",
                    title="Промышленные насосы",
                    target_suppliers=25,
                    verified_count=11,
                    file_count=1,
                )
                db.add(original)
                db.add(JobFile(job_id=original.id, original_filename="tz.txt", stored_path=str(source_path)))
                db.add(SupplierResult(job_id=original.id, company_name="ООО Насос", site="https://pump.example", evidence_status="verified"))
                db.commit()

                first_payload = create_additional_supplier_search_api(
                    original.id,
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )
                first_more = db.get(Job, first_payload["job"]["id"])
                self.assertEqual(first_more.target_suppliers, 14)
                first_more.status = "completed"
                first_more.verified_count = 4
                db.add(SupplierResult(job_id=first_more.id, company_name="ООО Арматура", site="https://valve.example", evidence_status="verified"))
                db.commit()

                second_payload = create_additional_supplier_search_api(
                    first_more.id,
                    context=WebAuthContext(user=user, session=None),
                    db=db,
                )
                second_more = db.get(Job, second_payload["job"]["id"])
                exclusions_path = jobs.job_dir(second_more.id) / "input" / "excluded_suppliers.json"
                exclusions_text = exclusions_path.read_text(encoding="utf-8")

            self.assertIn("pump.example", exclusions_text)
            self.assertIn("valve.example", exclusions_text)
            self.assertEqual(second_more.target_suppliers, 10)
            self.assertEqual(second_payload["job"]["prior_verified_count"], 15)
            self.assertEqual(second_payload["job"]["cumulative_verified_count"], 15)
        finally:
            jobs.job_dir = original_job_dir
            main_module.enqueue_job = original_enqueue
            db.close()

    def test_customer_jobs_api_returns_paginated_payload_when_requested(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-1", telegram_id="web:client-1")
            db.add(client)
            db.add_all(
                [
                    Job(client_id=client.id, mode=MODE_SUPPLIER_SEARCH, title=f"ТЗ {index}")
                    for index in range(5)
                ]
            )
            db.commit()
            user = create_web_user(db, email="owner@example.com", password="StrongPass123", name="Owner", client=client)
            response = Response()

            page = customer_jobs_api(
                response=response,
                limit=2,
                offset=2,
                include_pagination=True,
                context=WebAuthContext(user=user, session=None),
                db=db,
            )

            self.assertEqual(page["total"], 5)
            self.assertEqual(page["limit"], 2)
            self.assertEqual(page["offset"], 2)
            self.assertEqual(len(page["items"]), 2)
            self.assertIn("no-store", response.headers["cache-control"])
            self.assertEqual(response.headers["pragma"], "no-cache")
        finally:
            db.close()

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

    def test_registry_fallback_offer_payload_exposes_exact_counts_deadline_and_charge(self) -> None:
        db = self.Session()
        try:
            offered_at = now_utc()
            client = Client(id="client-registry-offer", telegram_id="web:registry-offer")
            job = Job(
                id="job-registry-offer",
                client_id=client.id,
                mode=MODE_SUPPLIER_SEARCH,
                status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
                progress=100,
                verified_count=24,
                confirmation_kind="registry_fallback",
                confirmation_outcome="pending",
                confirmation_offered_at=offered_at,
                confirmation_expires_at=offered_at + timedelta(hours=24),
                active_output_manifest="locked_offer",
                active_output_manifest_version=1,
            )
            db.add_all(
                [
                    client,
                    job,
                    BillingTransaction(
                        client_id=client.id,
                        job_id=job.id,
                        kind=KIND_SUPPLIER_SEARCH,
                        operation=OP_RESERVE,
                        units=1,
                        amount_kopeks=6_000,
                    ),
                ]
            )
            db.commit()

            payload = customer_job_to_dict(job, db=db)
        finally:
            db.close()

        offer = payload["result_offer"]
        self.assertEqual(offer["kind"], "registry_fallback")
        self.assertEqual(offer["registry_verified_count"], 0)
        self.assertEqual(offer["alternative_verified_count"], 24)
        self.assertEqual(offer["decision_outcome"], "pending")
        self.assertEqual(offer["decision_expires_at"], f"{job.confirmation_expires_at.isoformat()}+00:00")
        self.assertEqual(offer["delivery_outcome"], "")
        self.assertEqual(offer["active_manifest_version"], 1)
        self.assertEqual(
            offer["charge"],
            {
                "billing_kind": KIND_SUPPLIER_SEARCH,
                "units": 1,
                "amount_kopeks": 6_000,
                "currency": "RUB",
                "items": [{"billing_kind": KIND_SUPPLIER_SEARCH, "units": 1, "amount_kopeks": 6_000}],
            },
        )
        self.assertTrue(offer["can_accept"])
        self.assertTrue(offer["can_decline"])
        self.assertFalse(payload["can_download"])
        self.assertEqual(payload["result_files"], [])

    def test_registry_fallback_delivery_expiry_keeps_accepted_history_and_hides_files(self) -> None:
        decided_at = now_utc() - timedelta(hours=25)
        expired_at = now_utc()
        job = Job(
            id="job-registry-delivery-expired",
            mode=MODE_SUPPLIER_SEARCH,
            status="delivery_expired",
            progress=100,
            verified_count=7,
            result_path="/tmp/stale-registry-fallback.xlsx",
            confirmation_kind="registry_fallback",
            confirmation_outcome="accepted",
            confirmation_decided_at=decided_at,
            delivery_expires_at=decided_at + timedelta(hours=24),
            offer_delivery_outcome="expired",
            offer_delivery_expired_at=expired_at,
            active_output_manifest="none",
            active_output_manifest_version=3,
        )

        payload = customer_job_to_dict(job)

        self.assertEqual(payload["status"], "delivery_expired")
        self.assertEqual(payload["result_offer"]["decision_outcome"], "accepted")
        self.assertEqual(payload["result_offer"]["delivery_outcome"], "expired")
        self.assertEqual(payload["result_offer"]["active_manifest_version"], 3)
        self.assertFalse(payload["result_offer"]["can_accept"])
        self.assertFalse(payload["result_offer"]["can_decline"])
        self.assertFalse(payload["can_download"])
        self.assertEqual(payload["result_files"], [])

    def test_registry_fallback_accept_then_download_delivers_and_charges_once(self) -> None:
        import app.jobs as jobs

        original_job_dir = jobs.job_dir
        db = self.Session()
        try:
            client = Client(id="client-registry-delivery", telegram_id="web:registry-delivery")
            db.add(client)
            db.commit()
            user = create_web_user(
                db,
                email="registry-delivery@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
            )
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs.job_dir = lambda job_id: root / "jobs" / job_id
                out_dir = jobs.job_dir("job-registry-delivery") / "output"
                out_dir.mkdir(parents=True)
                result_path = out_dir / "Поставщики_без_подтверждения_реестра.xlsx"
                result_path.write_bytes(b"xlsx")
                evidence_path = out_dir / "evidence.json"
                evidence_path.write_text(
                    """
{
  "output_manifests": {
    "full": {
      "archive_path": "%s",
      "entitlements": ["supplier_search"],
      "files": [
        {"kind": "suppliers", "label": "Поставщики", "path": "%s", "billing_kind": "supplier_search"}
      ]
    }
  }
}
"""
                    % (result_path, result_path),
                    encoding="utf-8",
                )
                offered_at = now_utc()
                job = Job(
                    id="job-registry-delivery",
                    client_id=client.id,
                    mode=MODE_SUPPLIER_SEARCH,
                    status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
                    progress=100,
                    verified_count=5,
                    evidence_path=str(evidence_path),
                    confirmation_kind="registry_fallback",
                    confirmation_outcome="pending",
                    confirmation_offered_at=offered_at,
                    confirmation_expires_at=offered_at + timedelta(hours=24),
                    active_output_manifest="locked_offer",
                    active_output_manifest_version=1,
                    active_entitlements_json="[]",
                )
                db.add_all(
                    [
                        job,
                        BillingTransaction(
                            client_id=client.id,
                            job_id=job.id,
                            kind=KIND_SUPPLIER_SEARCH,
                            operation=OP_RESERVE,
                            units=1,
                            amount_kopeks=6_000,
                        ),
                    ]
                )
                db.commit()
                context = WebAuthContext(user=user, session=None)

                accepted = accept_customer_partial_job_api(job.id, context=context, db=db)
                response = download_customer_job_api(job.id, context=context, db=db)
                second_response = download_customer_job_api(job.id, context=context, db=db)

                db.refresh(job)
                charges = (
                    db.query(BillingTransaction)
                    .filter(BillingTransaction.job_id == job.id)
                    .filter(BillingTransaction.operation == OP_CHARGE)
                    .all()
                )
        finally:
            jobs.job_dir = original_job_dir
            db.close()

        self.assertTrue(accepted["success"])
        self.assertEqual(accepted["job"]["result_offer"]["decision_outcome"], "accepted")
        self.assertTrue(accepted["job"]["can_download"])
        self.assertEqual(response.filename, result_path.name)
        self.assertEqual(second_response.filename, result_path.name)
        self.assertEqual(job.offer_delivery_outcome, "delivered")
        self.assertEqual([(item.kind, item.units, item.amount_kopeks) for item in charges], [(KIND_SUPPLIER_SEARCH, 1, 6_000)])

    def test_combined_registry_fallback_decline_exposes_analysis_only(self) -> None:
        import app.jobs as jobs

        original_job_dir = jobs.job_dir
        db = self.Session()
        try:
            client = Client(id="client-registry-combined", telegram_id="web:registry-combined")
            db.add(client)
            db.commit()
            user = create_web_user(
                db,
                email="registry-combined@example.com",
                password="StrongPass123",
                name="Buyer",
                client=client,
            )
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                jobs.job_dir = lambda job_id: root / "jobs" / job_id
                out_dir = jobs.job_dir("job-registry-combined") / "output"
                out_dir.mkdir(parents=True)
                analysis_path = out_dir / "analysis.docx"
                suppliers_path = out_dir / "suppliers.xlsx"
                full_path = out_dir / "full.zip"
                analysis_path.write_bytes(b"analysis")
                suppliers_path.write_bytes(b"suppliers")
                full_path.write_bytes(b"archive")
                evidence_path = out_dir / "evidence.json"
                evidence_path.write_text(
                    """
{
  "report": {"warning": ""},
  "output_manifests": {
    "full": {
      "archive_path": "%s",
      "entitlements": ["procurement_report", "supplier_search"],
      "files": [
        {"kind": "analysis", "path": "%s", "billing_kind": "procurement_report"},
        {"kind": "suppliers", "path": "%s", "billing_kind": "supplier_search"}
      ]
    },
    "analysis_only": {
      "archive_path": "%s",
      "entitlements": ["procurement_report"],
      "files": [
        {"kind": "analysis", "path": "%s", "billing_kind": "procurement_report"}
      ]
    }
  }
}
"""
                    % (full_path, analysis_path, suppliers_path, analysis_path, analysis_path),
                    encoding="utf-8",
                )
                offered_at = now_utc()
                job = Job(
                    id="job-registry-combined",
                    client_id=client.id,
                    mode="analysis_and_suppliers",
                    status=STATUS_AWAITING_CUSTOMER_CONFIRMATION,
                    progress=100,
                    verified_count=3,
                    evidence_path=str(evidence_path),
                    confirmation_kind="registry_fallback",
                    confirmation_outcome="pending",
                    confirmation_offered_at=offered_at,
                    confirmation_expires_at=offered_at + timedelta(hours=24),
                    active_output_manifest="locked_offer",
                    active_output_manifest_version=1,
                    active_entitlements_json="[]",
                )
                db.add(job)
                db.add_all(
                    [
                        BillingTransaction(client_id=client.id, job_id=job.id, kind=KIND_PROCUREMENT_REPORT, operation=OP_RESERVE, units=1),
                        BillingTransaction(client_id=client.id, job_id=job.id, kind=KIND_SUPPLIER_SEARCH, operation=OP_RESERVE, units=1),
                    ]
                )
                db.commit()
                context = WebAuthContext(user=user, session=None)

                declined = decline_customer_partial_job_api(job.id, context=context, db=db)
                with self.assertRaises(HTTPException) as supplier_denied:
                    download_customer_job_file_api(job.id, "suppliers", context=context, db=db)
                analysis_response = download_customer_job_file_api(job.id, "analysis", context=context, db=db)
                settlements = (
                    db.query(BillingTransaction)
                    .filter(BillingTransaction.job_id == job.id)
                    .filter(BillingTransaction.operation.in_([OP_CHARGE, OP_RELEASE]))
                    .all()
                )
        finally:
            jobs.job_dir = original_job_dir
            db.close()

        self.assertEqual(declined["job"]["result_offer"]["decision_outcome"], "declined")
        self.assertEqual(declined["job"]["result_files"], [{"kind": "analysis", "label": "Анализ", "filename": "analysis.docx"}])
        self.assertTrue(declined["job"]["can_download"])
        self.assertEqual(supplier_denied.exception.status_code, 404)
        self.assertEqual(analysis_response.filename, "analysis.docx")
        self.assertEqual(
            sorted((item.kind, item.operation) for item in settlements),
            [(KIND_PROCUREMENT_REPORT, OP_CHARGE), (KIND_SUPPLIER_SEARCH, OP_RELEASE)],
        )

    def test_customer_can_cancel_own_running_job_and_release_reservation(self) -> None:
        db = self.Session()
        try:
            owner = Client(id="client-1", telegram_id="web:client-1", monthly_supplier_search_limit=1)
            other = Client(id="client-2", telegram_id="web:client-2", monthly_supplier_search_limit=1)
            db.add_all([owner, other])
            db.commit()
            owner_user = create_web_user(db, email="owner@example.com", password="StrongPass123", name="Owner", client=owner)
            other_user = create_web_user(db, email="other@example.com", password="StrongPass123", name="Other", client=other)
            job = Job(
                id="job-1",
                client_id=owner.id,
                mode=MODE_SUPPLIER_SEARCH,
                status="running",
                progress=35,
                message="Проверяю сайты",
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
                cancel_customer_job_api(job.id, context=WebAuthContext(user=other_user, session=None), db=db)
            payload = cancel_customer_job_api(job.id, context=WebAuthContext(user=owner_user, session=None), db=db)

            db.refresh(job)
            self.assertEqual(raised.exception.status_code, 404)
            self.assertTrue(payload["success"])
            self.assertEqual(job.status, "cancelled")
            self.assertEqual(job.progress, 100)
            self.assertFalse(payload["job"]["can_cancel"])
            release = (
                db.query(BillingTransaction)
                .filter(BillingTransaction.job_id == job.id)
                .filter(BillingTransaction.operation == OP_RELEASE)
                .one()
            )
            self.assertEqual(release.units, 1)
        finally:
            db.close()

    def test_cancelled_job_hides_result_files_even_if_worker_wrote_outputs(self) -> None:
        job = Job(
            id="job-cancelled",
            mode=MODE_SUPPLIER_SEARCH,
            status="cancelled",
            progress=100,
            title="ТЗ",
            result_path="/tmp/should-not-show.xlsx",
            evidence_path="/tmp/should-not-show.json",
        )

        payload = customer_job_to_dict(job)

        self.assertFalse(payload["has_result"])
        self.assertFalse(payload["can_download"])
        self.assertEqual(payload["result_files"], [])

    def test_confirmation_expired_job_hides_and_blocks_all_customer_results(self) -> None:
        db = self.Session()
        try:
            client = Client(id="client-expired", telegram_id="web:expired")
            job = Job(
                id="job-expired",
                client_id=client.id,
                mode=MODE_SUPPLIER_SEARCH,
                status=STATUS_CONFIRMATION_EXPIRED,
                progress=100,
                title="ТЗ",
                result_path="/tmp/existing-result.xlsx",
            )
            db.add_all([client, job])
            db.commit()
            context = WebAuthContext(user=SimpleNamespace(client_id=client.id), session=None)

            payload = customer_job_to_dict(job)
            with self.assertRaises(HTTPException) as raised:
                download_customer_job_api(job.id, context=context, db=db)
        finally:
            db.close()

        self.assertFalse(payload["has_result"])
        self.assertFalse(payload["can_download"])
        self.assertEqual(payload["result_files"], [])
        self.assertEqual(raised.exception.status_code, 410)


if __name__ == "__main__":
    unittest.main()
