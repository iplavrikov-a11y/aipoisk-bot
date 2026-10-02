from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot import (
    _alert_owner_about_low_balance,
    _is_insufficient_funds_error,
    _low_balance_contact_info,
    _money_balance_warning,
    _telegram_contact_url_with_text,
    cabinet_inline_keyboard,
    low_balance_inline_keyboard,
    reset_client_low_balance_alert,
)
from app.models import Client, SystemSettings


class LowBalanceNotificationTests(unittest.IsolatedAsyncioTestCase):
    def test_is_insufficient_funds_error(self) -> None:
        self.assertTrue(_is_insufficient_funds_error("Недостаточно средств для услуги «Поиск поставщиков»"))
        self.assertTrue(_is_insufficient_funds_error("Недостаточно доступных генераций: Поиск поставщиков"))
        self.assertTrue(_is_insufficient_funds_error("Недостаточно генераций: Анализ закупки"))
        self.assertFalse(_is_insufficient_funds_error("Формат файла не поддерживается"))
        self.assertFalse(_is_insufficient_funds_error("Доступ отключён"))
        self.assertFalse(_is_insufficient_funds_error(""))

    def test_telegram_contact_url_with_text(self) -> None:
        import urllib.parse
        url = _telegram_contact_url_with_text("@lexelence", "Здравствуйте! Хочу пополнить.")
        self.assertTrue(url.startswith("https://t.me/lexelence?text="))
        self.assertIn("Здравствуйте", urllib.parse.unquote(url))

        url_direct = _telegram_contact_url_with_text("https://t.me/lexelence", "Тест")
        self.assertTrue(url_direct.startswith("https://t.me/lexelence?text="))

        url_fallback = _telegram_contact_url_with_text("", "Тест")
        self.assertTrue(url_fallback.startswith("https://t.me/lexelence?text="))

    def test_low_balance_contact_info(self) -> None:
        settings = SystemSettings(contact_telegram="@lexelence")
        client = Client(id="client123", client_number=42)

        handle, url = _low_balance_contact_info(settings, client)
        self.assertEqual(handle, "@lexelence")
        self.assertIn("%2342", url)  # encoded #42

    def test_low_balance_inline_keyboard(self) -> None:
        settings = SystemSettings(contact_telegram="@lexelence")
        client = Client(id="client123", client_number=10)

        kb = low_balance_inline_keyboard(settings, client)
        self.assertEqual(len(kb.inline_keyboard), 2)
        top_btn = kb.inline_keyboard[0][0]
        self.assertIn("Написать в Telegram", top_btn.text)
        self.assertTrue(top_btn.url.startswith("https://t.me/lexelence?text="))

    def test_cabinet_inline_keyboard_with_and_without_contact(self) -> None:
        kb_without = cabinet_inline_keyboard("https://tenderlex.ru/cabinet", has_web_user=True)
        self.assertEqual(len(kb_without.inline_keyboard), 2)
        self.assertEqual(kb_without.inline_keyboard[0][0].text, "🌐 Открыть веб-кабинет")

        kb_with = cabinet_inline_keyboard(
            "https://tenderlex.ru/cabinet",
            has_web_user=True,
            contact_url="https://t.me/lexelence",
        )
        self.assertEqual(len(kb_with.inline_keyboard), 3)
        self.assertEqual(kb_with.inline_keyboard[0][0].text, "💬 Пополнить баланс в Telegram")
        self.assertEqual(kb_with.inline_keyboard[0][0].url, "https://t.me/lexelence")

    def test_money_balance_warning(self) -> None:
        settings = SystemSettings(contact_telegram="@lexelence")

        # Zero balance
        balances_zero = {"money": {"available_kopeks": 0, "low": True}}
        msg = _money_balance_warning(balances_zero, settings=settings)
        self.assertIn("Баланс исчерпан (0 ₽)", msg)
        self.assertIn("@lexelence", msg)

        # Low balance (> 0 but low)
        balances_low = {"money": {"available_kopeks": 15000, "low": True}}
        msg = _money_balance_warning(balances_low, settings=settings)
        self.assertIn("Баланс подходит к концу (150.0 ₽)", msg)
        self.assertIn("@lexelence", msg)

        # Normal balance
        balances_normal = {"money": {"available_kopeks": 500000, "low": False}}
        self.assertEqual(_money_balance_warning(balances_normal, settings=settings), "")

    @patch("app.bot.config")
    async def test_alert_owner_about_low_balance(self, mock_config: MagicMock) -> None:
        mock_config.owner_telegram_id = "998877"
        mock_config.bot_token = "fake-token"

        bot = AsyncMock()
        client = Client(
            id="c_test_1",
            client_number=7,
            name="ООО Ромашка",
            username="romashka_user",
            telegram_id="112233",
            money_balance_kopeks=0,
        )

        reset_client_low_balance_alert(client.id)

        # 1. First alert should be sent
        await _alert_owner_about_low_balance(
            bot,
            client,
            reason="Попытка запуска без средств",
            mode="supplier_search",
        )
        self.assertEqual(bot.send_message.call_count, 1)
        args, kwargs = bot.send_message.call_args
        self.assertEqual(kwargs.get("chat_id"), 998877)
        sent_text = kwargs.get("text", "")
        self.assertIn("У клиента закончился баланс!", sent_text)
        self.assertIn("ООО Ромашка", sent_text)
        self.assertIn("@romashka_user", sent_text)
        self.assertIn("#7", sent_text)
        self.assertIn("0.00 ₽", sent_text)
        self.assertIn("Попытка запуска без средств", sent_text)
        self.assertIn("https://t.me/romashka_user", sent_text)

        # 2. Throttling: immediate second alert should NOT be sent
        bot.send_message.reset_mock()
        await _alert_owner_about_low_balance(
            bot,
            client,
            reason="Повторная попытка",
        )
        bot.send_message.assert_not_called()

        # 3. Reset throttle
        reset_client_low_balance_alert(client.id)
        await _alert_owner_about_low_balance(
            bot,
            client,
            reason="Попытка после сброса",
        )
        self.assertEqual(bot.send_message.call_count, 1)

    @patch("app.bot.config")
    async def test_alert_owner_skips_when_client_is_owner(self, mock_config: MagicMock) -> None:
        mock_config.owner_telegram_id = "998877"
        mock_config.bot_token = "fake-token"

        bot = AsyncMock()
        owner_client = Client(
            id="c_owner",
            client_number=1,
            name="Владелец",
            telegram_id="998877",  # same as owner_id
            money_balance_kopeks=0,
        )
        reset_client_low_balance_alert(owner_client.id)

        await _alert_owner_about_low_balance(
            bot,
            owner_client,
            reason="Тест",
        )
        bot.send_message.assert_not_called()

    @patch("app.bot.config")
    async def test_alert_owner_skips_when_bot_is_none_or_dummy_client(self, mock_config: MagicMock) -> None:
        mock_config.owner_telegram_id = "998877"
        mock_config.bot_token = "fake-token"

        bot = AsyncMock()
        blocked_client = Client(
            id="blocked-client",
            name="Blocked",
            telegram_id="blocked",
            money_balance_kopeks=0,
        )
        # Blocked client should be suppressed
        await _alert_owner_about_low_balance(
            bot,
            blocked_client,
            reason="Тест блокировки",
        )
        bot.send_message.assert_not_called()

        # None bot should be safely skipped without creating real bot or raising
        normal_client = Client(
            id="c_normal",
            client_number=42,
            name="Нормальный",
            telegram_id="554433",
            money_balance_kopeks=0,
        )
        await _alert_owner_about_low_balance(
            None,
            normal_client,
            reason="Без бота",
        )
        # Should not raise or attempt network call

    @patch("app.bot.config")
    async def test_alert_owner_includes_inline_button_and_service(self, mock_config: MagicMock) -> None:
        mock_config.owner_telegram_id = "998877"
        mock_config.bot_token = "fake-token"

        bot = AsyncMock()
        client = Client(
            id="c_user_42",
            client_number=42,
            name="Иван Иванов",
            username="ivan_tg",
            telegram_id="778899",
            money_balance_kopeks=0,
        )
        reset_client_low_balance_alert(client.id)

        await _alert_owner_about_low_balance(
            bot,
            client,
            reason="Недостаточно средств при резервировании задачи",
            job_title="Закупка спецодежды.pdf",
            mode="supplier_search",
        )
        self.assertEqual(bot.send_message.call_count, 1)
        args, kwargs = bot.send_message.call_args
        text = kwargs.get("text", "")
        self.assertIn("<b>Иван Иванов</b> (@ivan_tg)", text)
        self.assertIn("№ 42", text)
        self.assertIn("778899", text)
        self.assertIn("Поиск поставщиков", text)
        self.assertIn("Закупка спецодежды.pdf", text)
        reply_markup = kwargs.get("reply_markup")
        self.assertIsNotNone(reply_markup)
        self.assertEqual(reply_markup.inline_keyboard[0][0].text, "💬 Написать @ivan_tg")
        self.assertEqual(reply_markup.inline_keyboard[0][0].url, "https://t.me/ivan_tg")

    @patch("app.bot.config")
    async def test_alert_owner_when_balance_is_100_rubles_or_less(self, mock_config: MagicMock) -> None:
        mock_config.owner_telegram_id = "998877"
        mock_config.bot_token = "fake-token"

        bot = AsyncMock()
        client = Client(
            id="c_user_99",
            client_number=99,
            name="Ольга Петрова",
            username="olga_petrova",
            telegram_id="998811",
            money_balance_kopeks=10_000,  # exactly 100.00 ₽
        )
        reset_client_low_balance_alert(client.id)

        await _alert_owner_about_low_balance(
            bot,
            client,
            reason="Осталось ≤ 100 ₽ (100.00 ₽) после выполнения задачи",
            job_title="Спецификация_оборудование.xlsx",
            mode="supplier_search",
        )
        self.assertEqual(bot.send_message.call_count, 1)
        args, kwargs = bot.send_message.call_args
        text = kwargs.get("text", "")
        self.assertIn("У клиента заканчивается баланс (осталось ≤ 100 ₽)!", text)
        self.assertIn("100.00 ₽ (хватит не более чем на 1 задачу)", text)
        self.assertIn("Напомните клиенту об оплате, чтобы не блокировать следующую задачу.", text)
        self.assertIn("Ольга Петрова", text)
        self.assertIn("№ 99", text)


