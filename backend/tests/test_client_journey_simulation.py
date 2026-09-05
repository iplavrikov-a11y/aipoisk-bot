from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import app.bot as bot_module
from app.bot import (
    BUTTON_ACCESS,
    BUTTON_ANALYSIS_AND_SUPPLIERS,
    BUTTON_BACK_MAIN,
    BUTTON_CANCEL_BATCH,
    BUTTON_CANCEL_PROCESSING,
    BUTTON_CONTACTS,
    BUTTON_CREATE,
    BUTTON_HELP,
    BUTTON_LEGAL,
    BUTTON_POLICY,
    BUTTON_REPORT,
    BUTTON_RUN_BATCH,
    BUTTON_STATUS,
    BUTTON_SUPPLIERS,
    BUTTON_TARIFFS,
    SCENARIO_ANALYSIS_AND_SUPPLIERS,
    SCENARIO_REPORT,
    SCENARIO_SUPPLIERS,
    SUPPLIER_POLICY_MINPROM_ONLY,
    SUPPLIER_POLICY_MINPROM_PRIORITY,
    SUPPLIER_POLICY_NORMAL,
)
from app.jobs import MODE_ANALYSIS_AND_SUPPLIERS, MODE_PROCUREMENT_REPORT, MODE_SUPPLIER_SEARCH


class ClientJourneySimulationTests(unittest.IsolatedAsyncioTestCase):
    class FakeUser:
        def __init__(self, user_id: int = 1001, username: str = "testbuyer"):
            self.id = user_id
            self.username = username
            self.first_name = "Иван"
            self.last_name = "Закупщик"
            self.is_bot = False

    class FakeChat:
        def __init__(self, chat_id: int = 1001):
            self.id = chat_id
            self.type = "private"

    class FakeMessage:
        def __init__(self, text: str = "", chat_id: int = 1001, document=None):
            self.text = text
            self.caption = ""
            self.chat = ClientJourneySimulationTests.FakeChat(chat_id)
            self.from_user = ClientJourneySimulationTests.FakeUser(chat_id)
            self.message_id = 42
            self.document = document
            self.reply_to_message = None
            self.answers: list[tuple[str, dict]] = []

        async def answer(self, text: str, **kwargs) -> ClientJourneySimulationTests.FakeSentMessage:
            self.answers.append((text, kwargs))
            return ClientJourneySimulationTests.FakeSentMessage(text, kwargs, self.chat.id)

    class FakeSentMessage:
        def __init__(self, text: str, kwargs: dict, chat_id: int):
            self.text = text
            self.kwargs = kwargs
            self.chat = ClientJourneySimulationTests.FakeChat(chat_id)
            self.message_id = 99
            self.edited_answers: list[tuple[str, dict]] = []

        async def edit_text(self, text: str, **kwargs):
            self.edited_answers.append((text, kwargs))
            self.text = text
            self.kwargs.update(kwargs)

    class FakeCallbackQuery:
        def __init__(self, data: str, message: ClientJourneySimulationTests.FakeSentMessage):
            self.data = data
            self.message = message
            self.from_user = message.chat
            self.answered_text: str | None = None

        async def answer(self, text: str | None = None, **kwargs):
            self.answered_text = text

    async def asyncSetUp(self):
        self.chat_id = 88001
        bot_module.PENDING_UPLOADS.clear()
        bot_module.PENDING_MODES.clear()
        bot_module.PENDING_SUPPLIER_POLICIES.clear()
        bot_module.BATCH_RUNNING_CHATS.clear()

    async def asyncTearDown(self):
        bot_module.PENDING_UPLOADS.clear()
        bot_module.PENDING_MODES.clear()
        bot_module.PENDING_SUPPLIER_POLICIES.clear()
        bot_module.BATCH_RUNNING_CHATS.clear()

    async def test_full_client_journey_simulation(self):
        chat_id = self.chat_id

        # 1. /start command
        start_msg = self.FakeMessage(text="/start", chat_id=chat_id)
        with patch.object(bot_module, "_record_telegram_event"):
            await bot_module.start(start_msg)
        self.assertTrue(len(start_msg.answers) >= 1)
        self.assertIn("TenderLex", start_msg.answers[0][0])

        # 2. User presses 🚀 Создать
        create_msg = self.FakeMessage(text=BUTTON_CREATE, chat_id=chat_id)
        with patch.object(bot_module, "_record_telegram_event"):
            await bot_module.create_button(create_msg)
        self.assertEqual(len(create_msg.answers), 1)
        self.assertIn("Выберите сценарий", create_msg.answers[0][0])
        reply_kb = create_msg.answers[0][1].get("reply_markup")
        kb_buttons = [b.text for row in reply_kb.inline_keyboard for b in row]
        self.assertTrue(any("Поставщики по ТЗ" in b for b in kb_buttons))
        self.assertTrue(any("Анализ закупки" in b for b in kb_buttons))
        self.assertTrue(any("Анализ + поиск" in b for b in kb_buttons))

        # 3. User selects 🔎 Поставщики по ТЗ
        suppliers_msg = self.FakeMessage(text=BUTTON_SUPPLIERS, chat_id=chat_id)
        with patch.object(bot_module, "_record_telegram_event"):
            await bot_module.supplier_single_button(suppliers_msg)
        
        # Must answer with policy prompt and inline keyboard
        self.assertEqual(len(suppliers_msg.answers), 1)
        policy_prompt = suppliers_msg.answers[0][0]
        self.assertIn("Поставщики по ТЗ", policy_prompt)
        self.assertIn("Обычный поиск", policy_prompt)
        inline_kb = suppliers_msg.answers[0][1].get("reply_markup")
        inline_labels = [b.text for row in inline_kb.inline_keyboard for b in row]
        self.assertTrue(any("Обычный поиск" in label for label in inline_labels))
        self.assertTrue(any("Только реестр" in label for label in inline_labels))
        self.assertTrue(any("Реестр в приоритете" in label for label in inline_labels))

        # 4. User clicks inline button "Только реестр"
        sent_msg = self.FakeSentMessage(policy_prompt, suppliers_msg.answers[0][1], chat_id)
        cb_query = self.FakeCallbackQuery(f"supplier_policy:{SUPPLIER_POLICY_MINPROM_ONLY}", sent_msg)
        await bot_module.supplier_policy_callback(cb_query)
        self.assertEqual(bot_module.PENDING_SUPPLIER_POLICIES[chat_id], SUPPLIER_POLICY_MINPROM_ONLY)
        self.assertIn("Только реестр", cb_query.answered_text)
        self.assertTrue(any("✅ Только реестр" in b.text for row in sent_msg.kwargs["reply_markup"].inline_keyboard for b in row))

        # 5. User uploads ТЗ text directly
        tz_text = "Техническое задание на поставку кабеля ВВГнг-LS 3x2.5 ГОСТ 31996-2012 количество 5000 м."
        tz_msg = self.FakeMessage(text=tz_text, chat_id=chat_id)
        with patch.object(bot_module, "_record_telegram_event"):
            await bot_module.unknown_text(tz_msg)
        
        self.assertIn(chat_id, bot_module.PENDING_UPLOADS)
        pending = bot_module.PENDING_UPLOADS[chat_id]
        self.assertEqual(pending.mode, MODE_SUPPLIER_SEARCH)
        self.assertEqual(pending.supplier_search_policy, SUPPLIER_POLICY_MINPROM_ONLY)
        self.assertTrue(len(tz_msg.answers) >= 1)
        self.assertIn("ТЗ добавлено", tz_msg.answers[0][0])
        self.assertIn("Только реестр", tz_msg.answers[0][0])

        # 6. User clicks ⚙️ Режим поиска
        policy_btn_msg = self.FakeMessage(text=BUTTON_POLICY, chat_id=chat_id)
        await bot_module.policy_button(policy_btn_msg)
        self.assertEqual(len(policy_btn_msg.answers), 1)
        self.assertIn("Режим реестра", policy_btn_msg.answers[0][0])

        # 7. User clicks 🗑 Очистить
        clear_msg = self.FakeMessage(text=BUTTON_CANCEL_BATCH, chat_id=chat_id)
        await bot_module.cancel_batch_button(clear_msg)
        self.assertNotIn(chat_id, bot_module.PENDING_UPLOADS)

        # 8. User selects 📄 Анализ закупки
        report_msg = self.FakeMessage(text=BUTTON_REPORT, chat_id=chat_id)
        with patch.object(bot_module, "_record_telegram_event"):
            await bot_module.report_button(report_msg)
        self.assertEqual(len(report_msg.answers), 1)
        self.assertIn("Анализ закупки", report_msg.answers[0][0])

        # 9. User sends procurement notice number
        notice_msg = self.FakeMessage(text="0373200001424000123", chat_id=chat_id)
        with patch.object(bot_module, "_record_telegram_event"):
            await bot_module.unknown_text(notice_msg)
        self.assertIn(chat_id, bot_module.PENDING_UPLOADS)
        self.assertEqual(bot_module.PENDING_UPLOADS[chat_id].mode, MODE_PROCUREMENT_REPORT)

        # 10. User clears batch and selects 📄🔎 Анализ + поиск
        await bot_module.cancel_batch_button(self.FakeMessage(text=BUTTON_CANCEL_BATCH, chat_id=chat_id))
        combo_msg = self.FakeMessage(text=BUTTON_ANALYSIS_AND_SUPPLIERS, chat_id=chat_id)
        with patch.object(bot_module, "_record_telegram_event"):
            await bot_module.analysis_and_suppliers_button(combo_msg)
        self.assertEqual(len(combo_msg.answers), 1)
        self.assertIn("Анализ + поиск", combo_msg.answers[0][0])

        # Switch policy to "Реестр в приоритете"
        combo_sent_msg = self.FakeSentMessage(combo_msg.answers[0][0], combo_msg.answers[0][1], chat_id)
        cb_priority = self.FakeCallbackQuery(f"supplier_policy:{SUPPLIER_POLICY_MINPROM_PRIORITY}", combo_sent_msg)
        await bot_module.supplier_policy_callback(cb_priority)
        self.assertEqual(bot_module.PENDING_SUPPLIER_POLICIES[chat_id], SUPPLIER_POLICY_MINPROM_PRIORITY)

        # 11. Test Info buttons: 📊 Кабинет, 💳 Тарифы, ❓ Помощь, 📞 Контакты, ⚖️ Правовая информация, 🕘 Задачи
        access_msg = self.FakeMessage(text=BUTTON_ACCESS, chat_id=chat_id)
        with patch.object(bot_module, "_cabinet_text", return_value="📊 Личный кабинет TenderLex\nБаланс: активен"):
            await bot_module.access_button(access_msg)
        self.assertIn("Личный кабинет", access_msg.answers[0][0])

        tariffs_msg = self.FakeMessage(text=BUTTON_TARIFFS, chat_id=chat_id)
        with patch.object(bot_module, "_tariffs_text", return_value="💳 Тарифные пакеты TenderLex"):
            await bot_module.tariffs_button(tariffs_msg)
        self.assertIn("Тарифные пакеты", tariffs_msg.answers[0][0])

        help_msg = self.FakeMessage(text=BUTTON_HELP, chat_id=chat_id)
        await bot_module.help_button(help_msg)
        self.assertIn("Помощь", help_msg.answers[0][0])

        contacts_msg = self.FakeMessage(text=BUTTON_CONTACTS, chat_id=chat_id)
        await bot_module.contacts_button(contacts_msg)
        self.assertIn("Контакты", contacts_msg.answers[0][0])

        legal_msg = self.FakeMessage(text=BUTTON_LEGAL, chat_id=chat_id)
        await bot_module.legal_info(legal_msg)
        self.assertIn("Документы TenderLex", legal_msg.answers[0][0])

        status_msg = self.FakeMessage(text=BUTTON_STATUS, chat_id=chat_id)
        await bot_module.status_button(status_msg)
        self.assertTrue(len(status_msg.answers) >= 1)
        self.assertTrue(any("Задач" in a[0] for a in status_msg.answers))

        # 12. Return to root menu with ⬅️ Меню
        back_msg = self.FakeMessage(text=BUTTON_BACK_MAIN, chat_id=chat_id)
        await bot_module.back_main_button(back_msg)
        self.assertEqual(len(back_msg.answers), 1)
        self.assertIn("Меню", back_msg.answers[0][0])

    async def test_client_account_linking_flow(self):
        chat_id = self.chat_id
        # Test /start link_<token> deep link flow
        link_msg = self.FakeMessage(text="/start link_testtoken123", chat_id=chat_id)
        command_obj = SimpleNamespace(args="link_testtoken123")
        fake_client = SimpleNamespace(id=1, email="buyer@tenderlex.ru", web_balance=10)
        with patch.object(bot_module, "consume_web_to_telegram_token", return_value=SimpleNamespace(client_id=1)):
            with patch.object(bot_module, "get_or_create_trial_client_by_telegram_id", return_value=(fake_client, None)):
                with patch.object(bot_module, "_record_telegram_event"):
                    await bot_module.start(link_msg, command=command_obj)
        self.assertTrue(len(link_msg.answers) >= 1)
        self.assertIn("привязан к вашему кабинету", link_msg.answers[0][0])

    async def test_client_batch_run_with_selected_policy(self):
        chat_id = self.chat_id
        bot_module.PENDING_MODES[chat_id] = SCENARIO_SUPPLIERS
        bot_module.PENDING_SUPPLIER_POLICIES[chat_id] = SUPPLIER_POLICY_MINPROM_ONLY
        bot_module.PENDING_UPLOADS[chat_id] = bot_module.PendingBatch(
            telegram_id=str(chat_id),
            mode=MODE_SUPPLIER_SEARCH,
            files=[("tz1.docx", b"content1"), ("tz2.docx", b"content2")],
            supplier_search_policy=SUPPLIER_POLICY_MINPROM_ONLY,
        )

        run_msg = self.FakeMessage(text=BUTTON_RUN_BATCH, chat_id=chat_id)
        created_jobs = []

        def mock_create_job(db, **kwargs):
            job_mock = SimpleNamespace(id=f"job-{len(created_jobs)+1}", status="pending", message="")
            created_jobs.append(job_mock)
            return job_mock

        fake_client = SimpleNamespace(id=1, is_active=True, runs_left=10, trial_runs_left=0)
        with patch.object(bot_module, "get_or_create_trial_client_by_telegram_id", return_value=(fake_client, None)):
            with patch.object(bot_module, "client_access_error", return_value=None):
                with patch.object(bot_module, "create_job", side_effect=mock_create_job):
                    with patch.object(bot_module, "_reserve_created_job", return_value=None):
                        with patch.object(bot_module, "_record_telegram_terms_acceptance"):
                            with patch.object(bot_module, "watch_job_progress", return_value=None):
                                with patch.object(bot_module, "_record_telegram_event"):
                                    await bot_module.run_batch_button(run_msg)

        self.assertEqual(len(created_jobs), 2)
        self.assertNotIn(chat_id, bot_module.PENDING_UPLOADS)

    async def test_client_cancel_processing_and_clear(self):
        chat_id = self.chat_id
        bot_module.BATCH_RUNNING_CHATS.add(chat_id)
        bot_module.PENDING_UPLOADS[chat_id] = bot_module.PendingBatch(
            telegram_id=str(chat_id),
            mode=MODE_SUPPLIER_SEARCH,
            files=[("tz.docx", b"content")],
        )

        cancel_msg = self.FakeMessage(text=BUTTON_CANCEL_PROCESSING, chat_id=chat_id)
        with patch.object(bot_module, "_cancel_processing_jobs_for_chat", return_value=1):
            await bot_module.cancel_processing_button(cancel_msg)

        self.assertNotIn(chat_id, bot_module.BATCH_RUNNING_CHATS)
        self.assertNotIn(chat_id, bot_module.PENDING_UPLOADS)
        self.assertTrue(len(cancel_msg.answers) >= 1)
        self.assertIn("Задача отменена", cancel_msg.answers[0][0])


if __name__ == "__main__":
    unittest.main()
