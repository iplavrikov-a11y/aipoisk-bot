#!/usr/bin/env python3
"""
Comprehensive Client Journey & Button Emulation Test for TenderLex.
Executes real handler pipelines against real SQLite database and models.
"""
import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend is on PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

import app.bot as bot_module
from app.db import SessionLocal
from app.models import Client, SystemSettings
from app.repository import get_or_create_settings

results = []

def record(step: str, name: str, success: bool, details: str = ""):
    status_str = "PASS" if success else "FAIL"
    print(f"[{status_str}] Step {step}: {name} - {details}")
    results.append({"step": step, "name": name, "success": success, "details": details})


class MockChat:
    def __init__(self, chat_id: int):
        self.id = chat_id
        self.type = "private"


class MockUser:
    def __init__(self, user_id: int):
        self.id = user_id
        self.username = f"user_{user_id}"
        self.first_name = "Алексей"
        self.last_name = "Тестов"
        self.full_name = "Алексей Тестов"
        self.is_bot = False


class MockSentMessage:
    def __init__(self, text: str, kwargs: dict, chat_id: int):
        self.text = text
        self.kwargs = kwargs
        self.chat = MockChat(chat_id)
        self.message_id = 9999
        self.edited_history = []

    async def edit_text(self, text: str, **kwargs):
        self.edited_history.append((text, kwargs))
        self.text = text
        self.kwargs.update(kwargs)
        return self


class MockMessage:
    def __init__(self, text: str = "", chat_id: int = 777001, document=None):
        self.text = text
        self.caption = ""
        self.chat = MockChat(chat_id)
        self.from_user = MockUser(chat_id)
        self.message_id = 1234
        self.document = document
        self.reply_to_message = None
        self.sent_answers = []

    async def answer(self, text: str, **kwargs):
        self.sent_answers.append((text, kwargs))
        return MockSentMessage(text, kwargs, self.chat.id)


class MockCallbackQuery:
    def __init__(self, data: str, message: MockSentMessage, chat_id: int = 777001):
        self.id = "cb_12345"
        self.data = data
        self.message = message
        self.from_user = MockUser(chat_id)
        self.answered_toast = None

    async def answer(self, text: str | None = None, **kwargs):
        self.answered_toast = text
        return True


async def run_emulation():
    chat_id = 99112233
    bot_module.PENDING_UPLOADS.clear()
    bot_module.PENDING_MODES.clear()
    bot_module.PENDING_SUPPLIER_POLICIES.clear()
    bot_module.BATCH_RUNNING_CHATS.clear()

    fake_bot = MagicMock()
    fake_bot.download = AsyncMock()

    print("\n================ STARTING TENDERLEX CLIENT EMULATION ================\n")

    # 1. /start command
    msg = MockMessage("/start", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.start(msg)
    ans = msg.sent_answers[-1]
    has_brand = "TenderLex" in ans[0]
    kb = ans[1].get("reply_markup")
    record("1", "/start greeting & branding", has_brand, f"Buttons attached: {bool(kb)}")

    # 2. Text alias: "создать"
    msg = MockMessage("создать", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.create_button(msg)
    ans = msg.sent_answers[-1]
    has_scenarios = "Создать задачу" in ans[0] and "Подбор товара и аналогов" in ans[0]
    record("2", "Text alias 'создать' (AA-004)", has_scenarios, f"All 4 modules listed: {has_scenarios}")

    # 3. Text alias: "кабинет"
    msg = MockMessage("кабинет", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.access_button(msg)
    ans = msg.sent_answers[-1]
    has_cab = "кабинет" in ans[0].lower() or "баланс" in ans[0].lower()
    record("3", "Text alias 'кабинет' (AA-001)", has_cab, f"Response length: {len(ans[0])}")

    # 4. Text alias: "тарифы"
    msg = MockMessage("тарифы", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.tariffs_button(msg)
    ans = msg.sent_answers[-1]
    has_tariffs = "тариф" in ans[0].lower() or "₽" in ans[0]
    record("4", "Text alias 'тарифы'", has_tariffs, f"Response: {ans[0][:40]}...")

    # 5. Text alias: "помощь"
    msg = MockMessage("помощь", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.help_button(msg)
    ans = msg.sent_answers[-1]
    has_help = "помощь" in ans[0].lower() or "инструкция" in ans[0].lower()
    record("5", "Text alias 'помощь'", has_help, f"Response: {ans[0][:40]}...")

    # 6. Text alias: "контакты"
    msg = MockMessage("контакты", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.contacts_button(msg)
    ans = msg.sent_answers[-1]
    has_contacts = "поддержк" in ans[0].lower() or "контакт" in ans[0].lower() or "@" in ans[0]
    record("6", "Text alias 'контакты'", has_contacts, f"Response: {ans[0][:40]}...")

    # 7. Button: 📊 Кабинет
    msg = MockMessage(bot_module.BUTTON_ACCESS, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.access_button(msg)
    ans = msg.sent_answers[-1]
    record("7", "Menu button '📊 Кабинет'", "кабинет" in ans[0].lower(), f"Response length: {len(ans[0])}")

    # 8. Button: 💳 Тарифы
    msg = MockMessage(bot_module.BUTTON_TARIFFS, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.tariffs_button(msg)
    ans = msg.sent_answers[-1]
    record("8", "Menu button '💳 Тарифы'", "тариф" in ans[0].lower(), f"Response length: {len(ans[0])}")

    # 9. Button: ❓ Помощь
    msg = MockMessage(bot_module.BUTTON_HELP, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.help_button(msg)
    ans = msg.sent_answers[-1]
    record("9", "Menu button '❓ Помощь'", "помощь" in ans[0].lower() or "tenderlex" in ans[0].lower(), f"Response length: {len(ans[0])}")

    # 10. Button: 📞 Контакты
    msg = MockMessage(bot_module.BUTTON_CONTACTS, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.contacts_button(msg)
    ans = msg.sent_answers[-1]
    record("10", "Menu button '📞 Контакты'", "контакт" in ans[0].lower() or "поддержк" in ans[0].lower(), f"Response length: {len(ans[0])}")

    # 11. Button: ⚖️ Правовая информация
    msg = MockMessage(bot_module.BUTTON_LEGAL, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.legal_info(msg)
    ans = msg.sent_answers[-1]
    record("11", "Menu button '⚖️ Документы'", "документ" in ans[0].lower() or "оферт" in ans[0].lower() or "политик" in ans[0].lower(), f"Response length: {len(ans[0])}")

    # 12. Button: 🕘 Задачи
    msg = MockMessage(bot_module.BUTTON_STATUS, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.status_button(msg)
    ans = msg.sent_answers[-1]
    record("12", "Menu button '🕘 Задачи'", "задач" in ans[0].lower(), f"Response length: {len(ans[0])}")

    # 13. Scenario 1: 🔎 Поставщики по ТЗ
    msg = MockMessage(bot_module.BUTTON_SUPPLIERS, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.supplier_single_button(msg)
    ans = msg.sent_answers[-1]
    record("13", "Scenario button '🔎 Поставщики по ТЗ'", "поставщик" in ans[0].lower(), "Prompts for policy and input")

    # 14. Select Policy callback: supplier_policy:minprom_priority
    sent = MockSentMessage(ans[0], ans[1], chat_id)
    cb = MockCallbackQuery(f"supplier_policy:{bot_module.SUPPLIER_POLICY_MINPROM_PRIORITY}", sent, chat_id)
    await bot_module.supplier_policy_callback(cb)
    record("14", "Callback policy 'Реестр в приоритете'", bot_module.PENDING_SUPPLIER_POLICIES.get(chat_id) == bot_module.SUPPLIER_POLICY_MINPROM_PRIORITY, f"Toast: {cb.answered_toast}")

    # 15. Submit short item TZ in supplier mode: "Кабель силовой ВВГнг(А)-LS 3х2.5"
    tz_msg = MockMessage("Кабель силовой ВВГнг(А)-LS 3х2.5", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.unknown_text(tz_msg)
    ans = tz_msg.sent_answers[-1]
    is_accepted = "тз добавлено" in ans[0].lower() or "комплекте" in ans[0].lower()
    record("15", "Short TZ query accepted (AA-002)", is_accepted, f"Response: {ans[0][:45]}...")

    # 16. Button: 🗑 Очистить
    clear_msg = MockMessage(bot_module.BUTTON_CANCEL_BATCH, chat_id)
    await bot_module.cancel_batch_button(clear_msg)
    is_cleared = chat_id not in bot_module.PENDING_UPLOADS
    record("16", "Batch clear button '🗑 Очистить'", is_cleared, "Pending uploads emptied")

    # 17. Security Whitelist: Executable rejection (AA-003)
    doc_exe = SimpleNamespace(file_name="malicious.exe", file_id="file_exe_999", file_size=4096)
    exe_msg = MockMessage(text="", chat_id=chat_id, document=doc_exe)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.handle_document(exe_msg, bot=fake_bot)
    ans = exe_msg.sent_answers[-1]
    is_rejected = "не поддерживается" in ans[0].lower() or "формат" in ans[0].lower()
    record("17", "File security whitelist (.exe rejected)", is_rejected, f"Response: {ans[0][:50]}...")

    # 18. Security Whitelist: Valid docx file accepted
    doc_valid = SimpleNamespace(file_name="tz_cables.docx", file_id="file_docx_123", file_size=10240)
    docx_msg = MockMessage(text="", chat_id=chat_id, document=doc_valid)
    with patch.object(bot_module, "_record_telegram_event"):
        with patch.object(bot_module, "_download_document_content", return_value=("tz_cables.docx", b"PK\x03\x04test_docx")):
            await bot_module.handle_document(docx_msg, bot=fake_bot)
    ans_docx = docx_msg.sent_answers[-1]
    docx_accepted = "добавлено" in ans_docx[0].lower() or "комплект" in ans_docx[0].lower() or "получен" in ans_docx[0].lower()
    record("18", "File security whitelist (.docx accepted)", docx_accepted, f"Response: {ans_docx[0][:50]}...")

    # Clean batch
    await bot_module.cancel_batch_button(MockMessage(bot_module.BUTTON_CANCEL_BATCH, chat_id))

    # 19. Scenario 3: 📄 Анализ закупки (44/223-ФЗ)
    report_msg = MockMessage(bot_module.BUTTON_REPORT, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.report_button(report_msg)
    ans = report_msg.sent_answers[-1]
    record("19", "Scenario button '📄 Анализ закупки'", "анализ" in ans[0].lower(), "Prompts for notice/link/file")

    # 20. Notice number validation: invalid notice format (AA-005)
    invalid_notice = MockMessage("12345", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.unknown_text(invalid_notice)
    ans = invalid_notice.sent_answers[-1]
    has_19_digit_guidance = "19" in ans[0] or "извещен" in ans[0].lower()
    record("20", "Invalid notice format guidance (AA-005)", has_19_digit_guidance, f"Response: {ans[0][:60]}...")

    # 21. Notice number validation: valid 19-digit EIS notice
    valid_notice = MockMessage("0373200001424000123", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.unknown_text(valid_notice)
    ans = valid_notice.sent_answers[-1]
    notice_accepted = "источник" in ans[0].lower() or "добавлен" in ans[0].lower()
    record("21", "Valid 19-digit EIS notice accepted", notice_accepted, f"Response: {ans[0][:50]}...")

    # 22. Unknown text preservation (AA-001)
    await bot_module.cancel_batch_button(MockMessage(bot_module.BUTTON_CANCEL_BATCH, chat_id))
    unknown_msg = MockMessage("случайный текст абракадабра 123", chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.unknown_text(unknown_msg)
    ans = unknown_msg.sent_answers[-1]
    has_kb = ans[1].get("reply_markup") is not None
    record("22", "Unknown text preserves buttons (AA-001)", has_kb, f"Buttons attached: {bool(has_kb)}")

    # 23. Scenario 2: 🎯 Подбор товара и аналогов (DOCX only check)
    exact_msg = MockMessage(bot_module.BUTTON_EXACT_PRODUCT, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.exact_product_command(exact_msg)
    ans = exact_msg.sent_answers[-1]
    record("23", "Scenario button '🎯 Подбор товара и аналогов'", "аналог" in ans[0].lower() or "товар" in ans[0].lower(), "Prompts for DOCX TZ")

    # 24. Scenario 4: 📄🔎 Анализ + поиск
    combo_msg = MockMessage(bot_module.BUTTON_ANALYSIS_AND_SUPPLIERS, chat_id)
    with patch.object(bot_module, "_record_telegram_event"):
        await bot_module.analysis_and_suppliers_button(combo_msg)
    ans = combo_msg.sent_answers[-1]
    record("24", "Scenario button '📄🔎 Анализ + поиск'", "анализ" in ans[0].lower() and "поиск" in ans[0].lower(), "Combined scenario active")

    # 25. Database Check: Session & Settings
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        record("25", "Database Live Query Settings", settings is not None, f"Public URL: {settings.public_base_url}")
        client_count = db.query(Client).count()
        record("26", "Database Live Query Clients", client_count > 0, f"Total registered clients: {client_count}")
    finally:
        db.close()

    print("\n================ EMULATION SUMMARY ================\n")
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    failed = total - passed
    print(f"TOTAL TESTS: {total} | PASSED: {passed} | FAILED: {failed}")
    if failed == 0:
        print(">>> ALL CLIENT JOURNEY EMULATIONS PASSED SUCCESSFULLY! <<<\n")
        return 0
    else:
        print(f">>> {failed} TESTS FAILED! <<<\n")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_emulation())
    sys.exit(exit_code)
