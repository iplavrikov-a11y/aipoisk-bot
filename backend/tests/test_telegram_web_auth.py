from __future__ import annotations

import hashlib
import hmac
import time
from unittest import TestCase

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import config
from app.db import Base, db_session
from app.main import app
from app.models import (
    Client,
    ClientTelegramAccount,
    SystemSettings,
    TariffPackage,
    WebUser,
    now_utc,
)
from app.web_auth import (
    CUSTOMER_COOKIE,
    get_or_create_telegram_web_user,
    verify_telegram_auth_payload,
)


def _make_telegram_auth_payload(
    bot_token: str,
    *,
    telegram_id: int | str = 123456789,
    username: str = "testuser",
    first_name: str = "Test",
    last_name: str = "",
    auth_date: int | None = None,
) -> dict:
    payload = {
        "id": str(telegram_id),
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
    }
    check_pairs = [f"{k}={v}" for k, v in sorted(payload.items()) if v is not None]
    data_check_string = "\n".join(check_pairs)
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    payload["hash"] = expected_hash
    return payload


class TelegramWebAuthTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        Base.metadata.create_all(self.engine)

        with self.session_factory() as db:
            db.add(
                SystemSettings(
                    id=1,
                    public_base_url="https://tenderlex.ru",
                    bot_telegram="@tenderlex_bot",
                    trial_enabled=True,
                    trial_supplier_search_limit=2,
                    trial_procurement_report_limit=2,
                    trial_file_limit=10,
                )
            )
            db.add_all(
                [
                    TariffPackage(
                        kind="supplier_search",
                        name="Поиск поставщиков",
                        units=1,
                        price_kopeks=9900,
                        is_active=True,
                    ),
                    TariffPackage(
                        kind="procurement_report",
                        name="Анализ закупки",
                        units=1,
                        price_kopeks=9900,
                        is_active=True,
                    ),
                ]
            )
            db.commit()

        def override_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[db_session] = override_db
        self.client = TestClient(app)
        self.test_bot_token = "123456789:TEST_BOT_TOKEN_SECRET"
        self._orig_bot_token = config.bot_token
        config.bot_token = self.test_bot_token

    def tearDown(self) -> None:
        config.bot_token = self._orig_bot_token
        app.dependency_overrides.pop(db_session, None)
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_verify_telegram_auth_payload_success(self) -> None:
        payload = _make_telegram_auth_payload(
            self.test_bot_token, telegram_id=987654321, username="ivan_petrov"
        )
        self.assertTrue(
            verify_telegram_auth_payload(payload, self.test_bot_token)
        )

    def test_verify_telegram_auth_payload_invalid_hash(self) -> None:
        payload = _make_telegram_auth_payload(
            self.test_bot_token, telegram_id=987654321
        )
        payload["hash"] = "invalid_hash_signature"
        self.assertFalse(
            verify_telegram_auth_payload(payload, self.test_bot_token)
        )

    def test_verify_telegram_auth_payload_expired_auth_date(self) -> None:
        old_time = int(time.time()) - 90000  # > 24h
        payload = _make_telegram_auth_payload(
            self.test_bot_token, telegram_id=987654321, auth_date=old_time
        )
        self.assertFalse(
            verify_telegram_auth_payload(payload, self.test_bot_token)
        )

    def test_existing_telegram_bot_client_login_reuses_profile_and_balance(
        self,
    ) -> None:
        with self.session_factory() as db:
            # Emulate existing user in Telegram bot
            existing_client = Client(
                telegram_id="555444333",
                name="Existing Nikita",
                username="nikita_tg",
                is_active=True,
                is_trial=True,
                money_balance_kopeks=39600,
            )
            db.add(existing_client)
            db.flush()
            db.add(
                ClientTelegramAccount(
                    client_id=existing_client.id,
                    telegram_id="555444333",
                    username="nikita_tg",
                    name="Existing Nikita",
                    is_active=True,
                )
            )
            db.commit()
            existing_client_id = existing_client.id

        # Now user logs in via Telegram web auth
        with self.session_factory() as db:
            user, is_new = get_or_create_telegram_web_user(
                db,
                telegram_user_id="555444333",
                username="nikita_tg",
                first_name="Existing",
                last_name="Nikita",
            )
            self.assertFalse(is_new)
            self.assertEqual(user.client_id, existing_client_id)

            # Check that no second Client was created and balance remained intact
            total_clients = db.query(Client).count()
            self.assertEqual(total_clients, 1)
            refreshed = db.get(Client, existing_client_id)
            self.assertEqual(refreshed.money_balance_kopeks, 39600)

    def test_new_telegram_user_registration_creates_client_and_grants_trial(
        self,
    ) -> None:
        with self.session_factory() as db:
            user, is_new = get_or_create_telegram_web_user(
                db,
                telegram_user_id="777888999",
                username="new_user_tg",
                first_name="Ivan",
                last_name="Novikov",
            )
            self.assertTrue(is_new)
            client = db.get(Client, user.client_id)
            self.assertIsNotNone(client)
            self.assertTrue(client.is_trial)
            self.assertEqual(client.money_balance_kopeks, 39600)
            self.assertEqual(client.name, "Ivan Novikov")

            # Check ClientTelegramAccount created
            tg_account = (
                db.query(ClientTelegramAccount)
                .filter(ClientTelegramAccount.client_id == client.id)
                .first()
            )
            self.assertIsNotNone(tg_account)
            self.assertEqual(tg_account.telegram_id, "777888999")
            self.assertEqual(tg_account.username, "new_user_tg")

    def test_api_telegram_callback_success(self) -> None:
        payload = _make_telegram_auth_payload(
            self.test_bot_token,
            telegram_id="111222333",
            username="callback_user",
            first_name="Alex",
        )
        response = self.client.get(
            "/api/customer/auth/telegram/callback",
            params=payload,
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/cabinet")
        self.assertIn(CUSTOMER_COOKIE, response.cookies)

    def test_api_telegram_callback_with_tg_auth_result(self) -> None:
        import base64
        import json
        payload = _make_telegram_auth_payload(
            self.test_bot_token,
            telegram_id="777888999",
            username="oauth_user",
            first_name="Sergey",
        )
        tg_auth_result = base64.urlsafe_b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8")

        response = self.client.get(
            "/api/customer/auth/telegram/callback",
            params={"tgAuthResult": tg_auth_result},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/cabinet")
        self.assertIn(CUSTOMER_COOKIE, response.cookies)

    def test_api_telegram_login_redirect(self) -> None:
        response = self.client.get(
            "/api/customer/auth/telegram/login",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("https://oauth.telegram.org/auth?"))
        self.assertIn("bot_id=", response.headers["location"])
        self.assertIn("return_to=", response.headers["location"])
