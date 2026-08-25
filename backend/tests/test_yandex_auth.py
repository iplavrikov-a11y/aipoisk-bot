from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import config
from app.db import Base, _ensure_schema
from app.main import (
    customer_yandex_auth_url_api,
    customer_yandex_callback_api,
    customer_yandex_login_api,
)
from app.models import Client, SystemSettings, WebUser
from app.web_auth import (
    CUSTOMER_COOKIE,
    YANDEX_OAUTH_COOKIE,
    build_yandex_oauth_url,
    get_or_create_yandex_web_user,
    get_web_session_by_token,
)


class YandexAuthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()
        settings = SystemSettings(
            id=1,
            trial_enabled=True,
            trial_supplier_search_limit=2,
            trial_procurement_report_limit=2,
            trial_file_limit=10,
            public_base_url="https://tenderlex.ru",
        )
        self.db.add(settings)
        self.db.commit()

        self.config_patcher1 = patch.object(config, "yandex_oauth_client_id", "test_client_id_123")
        self.config_patcher2 = patch.object(config, "yandex_oauth_client_secret", "test_client_secret_123")
        self.config_patcher1.start()
        self.config_patcher2.start()

    def tearDown(self) -> None:
        self.config_patcher1.stop()
        self.config_patcher2.stop()
        self.db.close()
        self.engine.dispose()

    def test_build_yandex_oauth_url(self) -> None:
        url = build_yandex_oauth_url(
            redirect_uri="https://tenderlex.ru/api/customer/auth/yandex/callback",
            state="test_state_123",
        )
        self.assertIn("https://oauth.yandex.ru/authorize", url)
        self.assertIn("client_id=test_client_id_123", url)
        self.assertIn("state=test_state_123", url)
        self.assertIn("response_type=code", url)

    def test_get_or_create_yandex_web_user_new(self) -> None:
        user, is_new = get_or_create_yandex_web_user(
            self.db,
            yandex_user_id="yandex_uid_999",
            email="ivan.ivanov@yandex.ru",
            name="Иван Иванов",
        )
        self.assertTrue(is_new)
        self.assertEqual(user.email, "ivan.ivanov@yandex.ru")
        self.assertEqual(user.yandex_id, "yandex_uid_999")
        self.assertEqual(user.name, "Иван Иванов")
        self.assertTrue(user.is_email_verified)
        self.assertIsNotNone(user.client)
        self.assertTrue(user.client.is_trial)

    def test_get_or_create_yandex_web_user_existing_email(self) -> None:
        # Create existing user without yandex_id
        client = Client(telegram_id="web:manual_1", name="Петр", is_trial=False)
        self.db.add(client)
        self.db.flush()
        existing_user = WebUser(
            client_id=client.id,
            email="petr@yandex.ru",
            password_hash="pbkdf2$hash",
            name="Петр",
            is_email_verified=False,
            yandex_id=None,
        )
        self.db.add(existing_user)
        self.db.commit()

        # Login with Yandex ID with same email
        user, is_new = get_or_create_yandex_web_user(
            self.db,
            yandex_user_id="yandex_uid_petr",
            email="petr@yandex.ru",
            name="Петр Петров",
        )
        self.assertFalse(is_new)
        self.assertEqual(user.id, existing_user.id)
        self.assertEqual(user.yandex_id, "yandex_uid_petr")
        self.assertTrue(user.is_email_verified)

    def test_get_or_create_yandex_web_user_existing_yandex_id(self) -> None:
        user1, is_new1 = get_or_create_yandex_web_user(
            self.db,
            yandex_user_id="yandex_uid_repeat",
            email="repeat@yandex.ru",
            name="Повтор",
        )
        self.assertTrue(is_new1)

        user2, is_new2 = get_or_create_yandex_web_user(
            self.db,
            yandex_user_id="yandex_uid_repeat",
            email="repeat_new_email@yandex.ru",
            name="Повтор Новый",
        )
        self.assertFalse(is_new2)
        self.assertEqual(user1.id, user2.id)

    def test_customer_yandex_login_api(self) -> None:
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"), cookies={})
        response = Response()
        redirect_resp = customer_yandex_login_api(request, response, db=self.db)
        self.assertEqual(redirect_resp.status_code, 303)
        self.assertIn("https://oauth.yandex.ru/authorize", redirect_resp.headers.get("location", ""))
        self.assertIn(YANDEX_OAUTH_COOKIE, str(redirect_resp.headers.get("set-cookie", "")))

    def test_customer_yandex_auth_url_api(self) -> None:
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"), cookies={})
        response = Response()
        result = customer_yandex_auth_url_api(request, response, db=self.db)
        self.assertIn("url", result)
        self.assertIn("state", result)
        self.assertIn("https://oauth.yandex.ru/authorize", result["url"])

    @patch("app.main.fetch_yandex_oauth_profile")
    def test_customer_yandex_callback_api_success(self, mock_fetch) -> None:
        mock_fetch.return_value = {
            "yandex_id": "yandex_uid_success",
            "email": "success@yandex.ru",
            "name": "Успешный Пользователь",
            "avatar_id": "123",
        }

        test_state = "valid_state_abc"
        request = SimpleNamespace(
            headers={"user-agent": "TestBrowser/1.0"},
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={YANDEX_OAUTH_COOKIE: test_state},
        )
        response = Response()

        redirect_resp = customer_yandex_callback_api(
            request,
            response,
            code="test_oauth_code",
            state=test_state,
            db=self.db,
        )

        self.assertEqual(redirect_resp.status_code, 303)
        self.assertEqual(redirect_resp.headers.get("location"), "/cabinet")
        set_cookie = str(redirect_resp.headers.get("set-cookie", ""))
        self.assertIn(CUSTOMER_COOKIE, set_cookie)

        # Verify user in database
        user = self.db.query(WebUser).filter(WebUser.yandex_id == "yandex_uid_success").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "success@yandex.ru")
        self.assertTrue(user.is_email_verified)

    def test_customer_yandex_callback_api_state_mismatch(self) -> None:
        request = SimpleNamespace(
            headers={},
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={YANDEX_OAUTH_COOKIE: "state_one"},
        )
        response = Response()
        redirect_resp = customer_yandex_callback_api(
            request,
            response,
            code="test_code",
            state="state_two_different",
            db=self.db,
        )
        self.assertEqual(redirect_resp.status_code, 303)
        self.assertIn("auth_error=invalid_state", redirect_resp.headers.get("location", ""))

    def test_customer_yandex_callback_api_declined(self) -> None:
        request = SimpleNamespace(
            headers={},
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={},
        )
        response = Response()
        redirect_resp = customer_yandex_callback_api(
            request,
            response,
            error="access_denied",
            error_description="User denied access",
            db=self.db,
        )
        self.assertEqual(redirect_resp.status_code, 303)
        self.assertIn("auth_error=yandex_declined", redirect_resp.headers.get("location", ""))


if __name__ == "__main__":
    unittest.main()
