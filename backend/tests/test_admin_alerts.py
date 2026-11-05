from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.admin_alerts import (
    _ALERT_THROTTLE,
    get_active_incidents,
    notify_ai_provider_error,
    notify_job_infrastructure_failure,
    notify_low_yandex_balance,
    notify_yandex_search_error,
    record_incident,
    send_telegram_admin_alert,
)


class AdminAlertsTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _ALERT_THROTTLE.clear()

    @patch("app.admin_alerts.is_pytest", return_value=False)
    @patch("app.admin_alerts.config")
    @patch("httpx.AsyncClient.post")
    async def test_send_telegram_admin_alert_success(
        self, mock_post: AsyncMock, mock_config: AsyncMock, mock_pytest: AsyncMock
    ) -> None:
        mock_config.bot_token = "test-token"
        mock_config.owner_telegram_id = "123456"

        from unittest.mock import MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_post.return_value = mock_resp

        res = await send_telegram_admin_alert("<b>Test alert</b>", deduplicate_key="test_key")
        self.assertTrue(res)
        self.assertEqual(mock_post.call_count, 1)

        # Immediate second call with same key should be throttled
        res_throttled = await send_telegram_admin_alert("<b>Test alert</b>", deduplicate_key="test_key")
        self.assertFalse(res_throttled)
        self.assertEqual(mock_post.call_count, 1)

    def test_record_incident_and_get(self) -> None:
        record_incident("yandex_search", "Test incident", "Details here", level="critical")
        incidents = get_active_incidents(5)
        self.assertTrue(any(inc["service"] == "yandex_search" and inc["title"] == "Test incident" for inc in incidents))

    @patch("app.admin_alerts.dispatch_telegram_admin_alert")
    def test_notify_yandex_search_error(self, mock_dispatch: AsyncMock) -> None:
        # Non-critical status should be ignored
        notify_yandex_search_error(500, "Internal error")
        mock_dispatch.assert_not_called()

        # 403 PermissionDenied should trigger alert
        notify_yandex_search_error(403, "rpc error: code = PermissionDenied desc = Permission denied", query="тест")
        self.assertEqual(mock_dispatch.call_count, 1)
        args, kwargs = mock_dispatch.call_args
        self.assertIn("Критический сбой Яндекс.Поиск API", args[0])
        self.assertIn("PermissionDenied", args[0])
        self.assertEqual(kwargs.get("deduplicate_key"), "yandex_search_permission_denied")

    @patch("app.admin_alerts.dispatch_telegram_admin_alert")
    def test_notify_low_yandex_balance(self, mock_dispatch: AsyncMock) -> None:
        notify_low_yandex_balance(45.50, True)
        self.assertEqual(mock_dispatch.call_count, 1)
        args, kwargs = mock_dispatch.call_args
        self.assertIn("45.50 ₽", args[0])
        self.assertEqual(kwargs.get("deduplicate_key"), "yandex_balance_low")

    @patch("app.admin_alerts.dispatch_telegram_admin_alert")
    def test_notify_ai_provider_error(self, mock_dispatch: AsyncMock) -> None:
        # Rate limit / 429
        notify_ai_provider_error("OpenRouter", "gpt-4", 429, "Rate limit exceeded")
        self.assertEqual(mock_dispatch.call_count, 1)
        args, kwargs = mock_dispatch.call_args
        self.assertIn("OpenRouter", args[0])

        mock_dispatch.reset_mock()
        # 401 Unauthorized
        notify_ai_provider_error("Gemini", "gemini-flash", 401, "API key expired")
        self.assertEqual(mock_dispatch.call_count, 1)
        args, kwargs = mock_dispatch.call_args
        self.assertIn("Сбой AI-провайдера", args[0])
