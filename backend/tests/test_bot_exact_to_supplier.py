import unittest
from unittest.mock import MagicMock

from app.bot import (
    _exact_to_suppliers_offer_text,
    _exact_to_suppliers_offer_keyboard,
    _exact_to_suppliers_confirmation_text,
    _exact_to_suppliers_confirmation_keyboard,
)


class TestBotExactToSupplier(unittest.TestCase):
    def test_exact_to_suppliers_offer(self):
        text = _exact_to_suppliers_offer_text()
        self.assertIn("Рекомендуемый следующий шаг", text)
        self.assertIn("дилеров", text)

        kb = _exact_to_suppliers_offer_keyboard("test-job-123")
        self.assertIsNotNone(kb)
        buttons = kb.inline_keyboard
        self.assertEqual(len(buttons), 2)
        self.assertEqual(buttons[0][0].callback_data, "exact_suppliers_prompt:test-job-123")
        self.assertIn("Найти поставщиков", buttons[0][0].text)

    def test_exact_to_suppliers_confirmation(self):
        text = _exact_to_suppliers_confirmation_text()
        self.assertIn("Запустить поиск проверенных поставщиков", text)
        self.assertIn("1 поиск поставщиков", text)

        kb = _exact_to_suppliers_confirmation_keyboard("test-job-123")
        self.assertIsNotNone(kb)
        buttons = kb.inline_keyboard
        self.assertEqual(buttons[0][0].callback_data, "exact_suppliers_yes:test-job-123")
        self.assertEqual(buttons[1][0].callback_data, "exact_suppliers_no:test-job-123")
