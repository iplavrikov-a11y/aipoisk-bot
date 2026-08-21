from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ReplyKeyboardRemove

import app.bot as bot_module
from app.bot import (
    AI_HELP_NOTE,
    BOT_PAYMENT_INSTRUCTIONS,
    BOT_DESCRIPTION,
    BOT_SHORT_DESCRIPTION,
    BRAND_NAME,
    BUTTON_ANALYSIS_AND_SUPPLIERS,
    BUTTON_ACCESS,
    BUTTON_CANCEL_BATCH,
    BUTTON_CANCEL_PROCESSING,
    BUTTON_CONTACTS,
    BUTTON_CREATE,
    BUTTON_HELP,
    BUTTON_LEGAL,
    BUTTON_PROCESSING_STATUS,
    BUTTON_REPORT,
    BUTTON_RUN_BATCH,
    BUTTON_STATUS,
    BUTTON_SUPPLIERS,
    BUTTON_TARIFFS,
    INDIVIDUAL_TERMS_NOTE,
    JobProgressSnapshot,
    OWNER_ALERT_STATUSES,
    PendingBatch,
    _add_pending_sources,
    _cabinet_text,
    _contacts_text,
    _edit_or_send_status,
    _find_more_suppliers_confirmation_text,
    _find_more_suppliers_offer_keyboard,
    _find_more_suppliers_offer_text,
    _download_document_content,
    _legal_keyboard,
    _legal_text,
    _format_job_progress,
    _job_eta_text,
    _job_mode_for_scenario,
    _handle_source_text,
    _handle_supplier_text_tz,
    _looks_like_supplier_text_tz,
    _mode_label,
    _owner_problem_alert_text,
    _partial_confirmation_keyboard,
    _partial_confirmation_text,
    _pending_input_count,
    _progress_bar,
    _source_added_text,
    _send_job_outputs,
    _scenario_accepts_source_links,
    _source_link_rejection_text,
    _source_payloads_for_scenario,
    _status_label,
    _start_text,
    _pending_added_text,
    _batch_running_text,
    _chat_has_processing_job,
    _cancel_job_inline_keyboard,
    _contact_message_options,
    _menu_for_chat,
    _progress_status_keyboard,
    _supplier_multi_intro_text,
    _supplier_multi_job_specs,
    _supplier_text_tz_payload,
    _tariffs_text,
    batch_inline_keyboard,
    batch_menu,
    configure_bot_profile,
    create_inline_keyboard,
    create_menu,
    main_inline_keyboard,
    main_menu,
    processing_menu,
    watch_job_progress,
)
from app.jobs import MODE_ANALYSIS_AND_SUPPLIERS, MODE_PROCUREMENT_REPORT, MODE_SUPPLIER_SEARCH
from app.models import Client, SystemSettings, TariffPackage


class BotProgressFormattingTests(unittest.TestCase):
    def test_progress_bar_uses_ten_stable_segments(self) -> None:
        self.assertEqual(_progress_bar(0), "⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜")
        self.assertEqual(_progress_bar(37), "🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜")
        self.assertEqual(_progress_bar(100), "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩")

    def test_processing_menu_exposes_cancel_button(self) -> None:
        self.assertIsInstance(processing_menu(), ReplyKeyboardRemove)

    def test_progress_message_exposes_inline_cancel_button_for_active_job(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-1",
            mode=MODE_SUPPLIER_SEARCH,
            status="running",
            progress=25,
            message="Ищу поставщиков",
            error="",
            created_at=None,
        )

        keyboard = _progress_status_keyboard(snapshot)

        self.assertIsNotNone(keyboard)
        assert keyboard is not None
        self.assertEqual(keyboard.inline_keyboard[0][0].text, "⛔ Отменить задачу")
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "cancel_job:job-1")
        self.assertIsNone(_progress_status_keyboard(snapshot.__class__(**{**snapshot.__dict__, "status": "completed"})))

    def test_cancel_job_inline_keyboard_targets_exact_job(self) -> None:
        keyboard = _cancel_job_inline_keyboard("job-42")

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "cancel_job:job-42")

    def test_format_job_progress_explains_stage_and_eta(self) -> None:
        now = datetime(2026, 6, 2, 12, 10, tzinfo=timezone.utc)
        snapshot = JobProgressSnapshot(
            id="0291e2d4e2074858b91cf3d4062bc6f8",
            mode="supplier_search",
            status="running",
            progress=50,
            message="Ищу сайты поставщиков: поисковых запросов 12",
            error="",
            created_at=now - timedelta(minutes=10),
        )

        text = _format_job_progress(snapshot, now=now)

        self.assertIn("🔎 Ищу поставщиков", text)
        self.assertNotIn("0291e2d4", text)
        self.assertNotIn("Режим:", text)
        self.assertIn("🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜ 50%", text)
        self.assertIn("• Этап: ищу сайты компаний", text)
        self.assertIn("• Прошло: 10 мин", text)
        self.assertIn("• Ориентир: около", text)

    def test_terminal_job_eta_says_finished(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job",
            mode="supplier_search",
            status="completed",
            progress=100,
            message="Готово",
            error="",
            created_at=None,
        )

        self.assertEqual(_status_label("completed"), "готово")
        self.assertEqual(_job_eta_text(snapshot), "завершено")

    def test_completed_procurement_progress_uses_finished_wording(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job",
            mode=MODE_PROCUREMENT_REPORT,
            status="completed",
            progress=100,
            message="Анализ документации готов",
            error="",
            created_at=None,
        )

        text = _format_job_progress(snapshot)

        self.assertIn("✅ Файл готов", text)
        self.assertIn("анализ документации готов", text)
        self.assertNotIn("готовлю анализ документации", text)

    def test_failed_progress_hides_technical_error(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job",
            mode="supplier_search",
            status="failed",
            progress=100,
            message="Ошибка обработки",
            error="AI candidate reranking failed after retry: TimeoutError",
            created_at=None,
        )

        text = _format_job_progress(snapshot)

        self.assertIn("⚠️ Не удалось подготовить файл", text)
        self.assertIn("не удалось надёжно отобрать подходящие сайты поставщиков", text)
        self.assertIn("Баланс не списан", text)
        self.assertNotIn("не отправлять непроверенный список", text)
        self.assertNotIn("AI candidate reranking", text)
        self.assertNotIn("TimeoutError", text)

    def test_cancelled_progress_returns_user_to_next_action(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-1",
            mode=MODE_ANALYSIS_AND_SUPPLIERS,
            status="cancelled",
            progress=100,
            message="Задача отменена клиентом",
            error="",
            created_at=None,
        )

        text = _format_job_progress(snapshot)

        self.assertIn("⛔ Задача отменена", text)
        self.assertIn("Резерв возвращён", text)
        self.assertNotIn("Готовлю анализ", text)

    def test_failed_query_generation_uses_specific_customer_reason(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job",
            mode="supplier_search",
            status="failed",
            progress=100,
            message="Ошибка обработки",
            error="AI supplier query generation failed after retry: TimeoutError",
            created_at=None,
        )

        text = _format_job_progress(snapshot)

        self.assertIn("не удалось подготовить поисковые запросы для поставщиков", text)
        self.assertNotIn("AI supplier query generation", text)
        self.assertNotIn("TimeoutError", text)

    def test_partial_confirmation_text_requires_explicit_paid_delivery_consent(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job",
            mode="supplier_search",
            status="awaiting_customer_confirmation",
            progress=100,
            message="Найдено меньше поставщиков: найдено и проверено 8",
            error="",
            created_at=None,
        )

        text = _partial_confirmation_text(snapshot)

        self.assertIn("Отправить отчёт?", text)
        self.assertIn("будет списана стоимость результата", text)
        self.assertIn("только подтверждённые компании", text)
        self.assertNotIn("target", text.lower())

    def test_registry_fallback_confirmation_distinguishes_registry_and_alternative(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-registry-fallback",
            mode=MODE_SUPPLIER_SEARCH,
            status="awaiting_customer_confirmation",
            progress=100,
            message="Найдено и проверено 24",
            error="",
            created_at=None,
            confirmation_kind="registry_fallback",
            registry_verified_count=0,
            alternative_verified_count=24,
            offer_charge_text="900 ₽",
        )

        text = _partial_confirmation_text(snapshot)
        keyboard = _partial_confirmation_keyboard(snapshot.id, snapshot.confirmation_kind)

        self.assertIn("Подтверждено по реестру: 0", text)
        self.assertIn("Найдено и проверено вне реестра: 24", text)
        self.assertIn("после успешной отправки: 900 ₽", text)
        self.assertIn("При отказе", text)
        self.assertNotIn("техническ", text.lower())
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "result_offer_yes:job-registry-fallback")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, "result_offer_no:job-registry-fallback")

    def test_legacy_partial_confirmation_callbacks_remain_compatible(self) -> None:
        keyboard = _partial_confirmation_keyboard("legacy-job")

        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "partial_yes:legacy-job")
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, "partial_no:legacy-job")

    def test_delivery_expired_is_not_presented_as_customer_decline(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-delivery-expired",
            mode=MODE_SUPPLIER_SEARCH,
            status="delivery_expired",
            progress=100,
            message="",
            error="",
            created_at=None,
            confirmation_kind="registry_fallback",
            confirmation_outcome="accepted",
            offer_delivery_outcome="expired",
        )

        text = _format_job_progress(snapshot)

        self.assertEqual(_status_label("delivery_expired"), "срок выдачи истёк")
        self.assertIn("Вы согласились", text)
        self.assertIn("списания нет", text)
        self.assertNotIn("отказались", text)

    def test_partial_confirmation_status_is_not_internal_owner_alert(self) -> None:
        self.assertNotIn("awaiting_customer_confirmation", OWNER_ALERT_STATUSES)

    def test_contacts_text_includes_site_when_configured(self) -> None:
        settings = SystemSettings(
            id=1,
            contact_telegram="@owner",
            contact_max="+79210629909",
            contact_max_link="https://max.ru/invite/owner",
            contact_email="owner@example.ru",
            contact_website="https://aipoisk.example",
        )

        text = _contacts_text(settings, telegram_id="123")

        self.assertIn('Telegram: <a href="https://t.me/owner">Написать в Telegram</a>', text)
        self.assertNotIn("MAX", text)
        self.assertNotIn("max.ru/invite/owner", text)
        self.assertIn("Email: owner@example.ru", text)
        self.assertIn("Сайт: https://aipoisk.example", text)
        self.assertIn("Ваш Telegram ID: 123", text)

    def test_contact_message_options_disable_link_preview(self) -> None:
        options = _contact_message_options()

        self.assertEqual(options["parse_mode"], "HTML")
        self.assertTrue(options["disable_web_page_preview"])

    def test_tariffs_text_uses_rubles_and_default_payment_instruction(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            settings = SystemSettings(id=1, payment_instructions="")
            db.add(settings)
            db.add(
                TariffPackage(
                    kind="supplier_search",
                    name="Поставщики 20",
                    units=20,
                    price_kopeks=150000,
                    is_active=True,
                )
            )
            db.commit()

            text = _tariffs_text(db, settings)
        finally:
            db.close()

        self.assertIn("Поставщики 20", text)
        self.assertIn("1 500 ₽", text)
        self.assertIn("1 добор поставщиков", text)
        self.assertIn("50% от цены поиска поставщиков", text)
        self.assertIn(BOT_PAYMENT_INSTRUCTIONS, text)
        self.assertNotIn("MAX", text)
        self.assertIn(INDIVIDUAL_TERMS_NOTE, text)
        self.assertIn(AI_HELP_NOTE, text)
        self.assertNotIn("Как купить пакет:\n🧾 Чтобы купить пакет:", text)

    def test_cabinet_text_does_not_warn_about_extra_supplier_fallback_balance(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            settings = SystemSettings(id=1)
            client = Client(
                id="client-1",
                telegram_id="100",
                monthly_supplier_search_limit=1000,
                monthly_procurement_report_limit=1000,
                money_balance_kopeks=9_940_000,
            )
            db.add_all([
                settings,
                client,
                TariffPackage(kind="supplier_search", name="Поиск", units=1, price_kopeks=10_000, is_active=True),
                TariffPackage(kind="procurement_report", name="Анализ", units=1, price_kopeks=10_000, is_active=True),
            ])
            db.commit()

            text = _cabinet_text(db, client, settings)
        finally:
            db.close()

        self.assertIn("Баланс: 99 400 ₽", text)
        self.assertIn("Добор поставщиков: 50 ₽", text)
        self.assertNotIn("Добор поставщиков: доступно 0", text)
        self.assertNotIn("Заканчивается баланс: Добор поставщиков", text)

    def test_cabinet_warning_uses_money_balance_instead_of_legacy_units(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            settings = SystemSettings(id=1)
            funded_client = Client(
                id="funded-client",
                telegram_id="101",
                money_balance_kopeks=600_000,
            )
            low_money_client = Client(
                id="low-money-client",
                telegram_id="102",
                monthly_supplier_search_limit=1000,
                monthly_procurement_report_limit=1000,
                money_balance_kopeks=2_000,
            )
            db.add_all([
                settings,
                funded_client,
                low_money_client,
                TariffPackage(kind="supplier_search", name="Поиск", units=1, price_kopeks=6_000, is_active=True),
                TariffPackage(kind="procurement_report", name="Анализ", units=1, price_kopeks=12_000, is_active=True),
            ])
            db.commit()

            funded_text = _cabinet_text(db, funded_client, settings)
            low_money_text = _cabinet_text(db, low_money_client, settings)
        finally:
            db.close()

        self.assertNotIn("⚠️", funded_text)
        self.assertIn("⚠️ Баланс заканчивается.", low_money_text)
        self.assertNotIn("Поиск поставщиков, Анализ закупки", low_money_text)

    def test_after_delivery_warning_uses_money_balance_instead_of_legacy_units(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            funded_client = Client(id="funded-client", telegram_id="103", money_balance_kopeks=600_000)
            low_money_client = Client(
                id="low-money-client",
                telegram_id="104",
                monthly_supplier_search_limit=1000,
                monthly_procurement_report_limit=1000,
                money_balance_kopeks=2_000,
            )
            db.add_all([
                funded_client,
                low_money_client,
                TariffPackage(kind="supplier_search", name="Поиск", units=1, price_kopeks=6_000, is_active=True),
                TariffPackage(kind="procurement_report", name="Анализ", units=1, price_kopeks=12_000, is_active=True),
            ])
            db.commit()

            funded_text = bot_module._after_delivery_balance_text(db, funded_client)
            low_money_text = bot_module._after_delivery_balance_text(db, low_money_client)
        finally:
            db.close()

        self.assertNotIn("⚠️", funded_text)
        self.assertIn("⚠️ Баланс заканчивается.", low_money_text)

    def test_tariffs_text_hides_max_from_custom_bot_payment_instruction(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            settings = SystemSettings(id=1, payment_instructions="Напишите в Telegram, MAX или email.")
            db.add(settings)
            db.commit()

            text = _tariffs_text(db, settings)
        finally:
            db.close()

        self.assertIn(BOT_PAYMENT_INSTRUCTIONS, text)
        self.assertNotIn("MAX", text)

    def test_find_more_supplier_copy_requires_explicit_paid_confirmation(self) -> None:
        offer_text = _find_more_suppliers_offer_text()
        confirmation_text = _find_more_suppliers_confirmation_text()
        keyboard = _find_more_suppliers_offer_keyboard("job-1")

        self.assertIn("Найти ещё", keyboard.inline_keyboard[0][0].text)
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "find_more_prompt:job-1")
        self.assertIn("дополнительный поиск", offer_text)
        self.assertIn("Будет списана стоимость добора поставщиков", confirmation_text)
        self.assertIn("исключит уже найденные компании", confirmation_text)

    def test_start_text_uses_tenderlex_brand(self) -> None:
        text = _start_text()

        self.assertIn(f"Добро пожаловать в {BRAND_NAME}", text)
        self.assertNotIn("AI Poisk", text)
        self.assertNotIn("Аипоиск", text)

    def test_owner_problem_alert_keeps_actionable_context_short(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-123",
            mode=MODE_PROCUREMENT_REPORT,
            status="needs_review",
            progress=100,
            message="Анализ готов, нужна проверка ИИ-настроек",
            error="AI report verification failed: timeout after 180 seconds",
            created_at=None,
        )

        text = _owner_problem_alert_text(
            snapshot,
            title="Закупка на поставку оборудования",
            client_telegram_id="555",
            evidence_path="/tmp/evidence.json",
            result_path="/tmp/report.docx",
        )

        self.assertIn("нужна проверка задачи", text)
        self.assertIn("job-123", text)
        self.assertIn("анализ документации", text)
        self.assertIn("555", text)
        self.assertIn("Данные проверки: /tmp/evidence.json", text)
        self.assertNotIn("Evidence:", text)
        self.assertIn("проверить настройки модели", text)

    def test_main_menu_is_button_driven_and_mobile_readable(self) -> None:
        self.assertIsInstance(main_menu(), ReplyKeyboardRemove)
        inline_kb = main_inline_keyboard()
        labels = [button.text for row in inline_kb.inline_keyboard for button in row]
        self.assertTrue(any("Поставщики по ТЗ" in label for label in labels))
        self.assertTrue(any("Анализ закупки" in label for label in labels))
        self.assertTrue(any("Анализ + поиск" in label for label in labels))
        self.assertTrue(any("Кабинет" in label for label in labels))
        self.assertTrue(any("Задачи" in label for label in labels))
        self.assertTrue(any("Тарифы" in label for label in labels))
        self.assertTrue(any("Помощь" in label for label in labels))
        self.assertTrue(any("Контакты" in label for label in labels))

    def test_legal_prompt_is_optional_reference_without_acceptance_actions(self) -> None:
        keyboard = _legal_keyboard()
        buttons = [button for row in keyboard.inline_keyboard for button in row]
        callback_data = {button.callback_data for button in buttons if button.callback_data}
        urls = {button.url for button in buttons if button.url}

        self.assertEqual(callback_data, set())
        self.assertTrue(all(str(url).startswith("https://tenderlex.ru/") for url in urls))
        self.assertIn("Документы TenderLex", _legal_text())
        self.assertIn("https://tenderlex.ru/legal", _legal_text())
        self.assertNotIn("Подтвердите", _legal_text())
        self.assertNotIn("Принимаю", _legal_text())

    def test_start_copy_is_short_value_first_and_has_no_legal_gate(self) -> None:
        text = _start_text()

        self.assertLessEqual(len(text), 650)
        self.assertIn("ТЗ", text)
        self.assertIn("Списание", text)
        self.assertNotIn("оферт", text.lower())
        self.assertNotIn("политик", text.lower())
        self.assertNotIn("согласи", text.lower())

    def test_telegram_download_removes_temporary_file_after_read(self) -> None:
        class FakeBot:
            async def get_file(self, _file_id, request_timeout=60):
                return SimpleNamespace(file_path="remote/document.docx")

            async def download_file(self, _file_path, destination, timeout=120):
                Path(destination).write_bytes(b"document bytes")

        message = SimpleNamespace(
            document=SimpleNamespace(file_name="test.docx", file_id="file-1"),
            chat=SimpleNamespace(id=123),
        )
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(bot_module.config, "storage_dir", temp_dir):
            filename, content = asyncio.run(_download_document_content(message, FakeBot()))

            self.assertEqual(filename, "test.docx")
            self.assertEqual(content, b"document bytes")
            self.assertFalse((Path(temp_dir) / "telegram" / "123" / "test.docx").exists())

    def test_create_menu_is_compact_two_column_layout(self) -> None:
        keyboard = create_inline_keyboard().inline_keyboard
        labels = [button.text for row in keyboard for button in row]
        self.assertTrue(any("Поставщики по ТЗ" in label for label in labels))
        self.assertTrue(any("Анализ закупки" in label for label in labels))
        self.assertTrue(any("Анализ + поиск" in label for label in labels))

    def test_customer_buttons_use_procurement_language(self) -> None:
        labels = [
            BUTTON_SUPPLIERS,
            BUTTON_REPORT,
            BUTTON_ANALYSIS_AND_SUPPLIERS,
            BUTTON_RUN_BATCH,
            BUTTON_CANCEL_BATCH,
        ]
        joined = " ".join(labels)

        self.assertIn("Поставщики по ТЗ", joined)
        self.assertIn("Анализ закупки", joined)
        self.assertIn("Анализ + поиск", joined)
        self.assertNotIn("Одно ТЗ", joined)
        self.assertNotIn("Несколько ТЗ", joined)
        self.assertNotIn("Word", joined)
        self.assertNotIn("пач", joined.lower())

    def test_batch_menu_keeps_only_current_batch_actions(self) -> None:
        pending = PendingBatch(
            telegram_id="123",
            mode=MODE_SUPPLIER_SEARCH,
            files=[("test.docx", b"content")],
        )
        keyboard = batch_inline_keyboard(pending).inline_keyboard
        labels = [button.text for row in keyboard for button in row]
        self.assertTrue(any("Запустить" in label for label in labels))
        self.assertTrue(any("Очистить" in label for label in labels))

    def test_processing_menu_hides_new_start_actions(self) -> None:
        self.assertIsInstance(processing_menu(), ReplyKeyboardRemove)

    def test_menu_for_chat_uses_processing_state_from_database(self) -> None:
        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return ("job-1",)

        class FakeDb:
            def __init__(self) -> None:
                self.closed = False

            def query(self, *_args, **_kwargs):
                return FakeQuery()

            def close(self) -> None:
                self.closed = True

        fake_db = FakeDb()
        original_session = bot_module.SessionLocal
        running_chats = set(bot_module.BATCH_RUNNING_CHATS)
        try:
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.SessionLocal = lambda: fake_db

            self.assertTrue(_chat_has_processing_job(777))
            self.assertIsInstance(_menu_for_chat(777), ReplyKeyboardRemove)
        finally:
            bot_module.SessionLocal = original_session
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.update(running_chats)

        self.assertTrue(fake_db.closed)

    def test_early_job_eta_does_not_show_zero_seconds(self) -> None:
        now = datetime(2026, 6, 2, 12, 10, tzinfo=timezone.utc)
        snapshot = JobProgressSnapshot(
            id="job",
            mode="supplier_search",
            status="running",
            progress=50,
            message="Проверено сайтов: 10",
            error="",
            created_at=now - timedelta(seconds=5),
        )

        text = _format_job_progress(snapshot, now=now)

        self.assertIn("• Ориентир: рассчитываю время", text)
        self.assertNotIn("около 0 сек", text)

    def test_bot_profile_hides_command_menu_for_button_driven_onboarding(self) -> None:
        class FakeBot:
            def __init__(self) -> None:
                self.calls: list[tuple[str, object]] = []

            async def set_my_short_description(self, *, short_description: str) -> None:
                self.calls.append(("short_description", short_description))

            async def set_my_description(self, *, description: str) -> None:
                self.calls.append(("description", description))

            async def delete_my_commands(self) -> None:
                self.calls.append(("delete_commands", True))

            async def set_chat_menu_button(self, *, menu_button) -> None:
                self.calls.append(("menu_button", menu_button))

        bot = FakeBot()

        import asyncio

        asyncio.run(configure_bot_profile(bot))

        calls = dict(bot.calls)
        self.assertEqual(calls["short_description"], BOT_SHORT_DESCRIPTION)
        self.assertEqual(calls["description"], BOT_DESCRIPTION)
        self.assertIn(BRAND_NAME, BOT_SHORT_DESCRIPTION)
        self.assertIn(BRAND_NAME, BOT_DESCRIPTION)
        self.assertIn("Start", BOT_DESCRIPTION)
        self.assertIn("Запустить", BOT_DESCRIPTION)
        self.assertNotIn("AI Poisk", BOT_DESCRIPTION)
        self.assertTrue(calls["delete_commands"])
        self.assertEqual(calls["menu_button"].type, "default")

    def test_supplier_multi_intro_explains_mass_processing_contract(self) -> None:
        text = _supplier_multi_intro_text()

        self.assertIn("ТЗ файлом, текстом или архивом", text)
        self.assertIn("отдельный поиск поставщиков", text)
        self.assertIn("Проверьте количество добавленных ТЗ", text)
        self.assertIn("одним архивом", text)
        self.assertIn(BUTTON_RUN_BATCH, text)

    def test_supplier_multi_added_text_explains_next_step(self) -> None:
        pending = PendingBatch(
            telegram_id="123",
            mode=MODE_SUPPLIER_SEARCH,
            files=[("one.docx", b"1"), ("two.docx", b"2")],
        )

        text = _pending_added_text(pending, max_files=20)

        self.assertIn("✅ ТЗ добавлено", text)
        self.assertIn("В комплекте: 2/20", text)
        self.assertIn("разные ТЗ", text)
        self.assertIn("одним архивом", text)
        self.assertIn("нажмите кнопку ниже", text)

    def test_batch_running_text_hides_add_document_buttons_intent(self) -> None:
        text = _batch_running_text()

        self.assertIn("Обработка уже идёт", text)
        self.assertIn("пришлю файл", text)

    def test_mode_labels_are_customer_facing(self) -> None:
        self.assertEqual(_mode_label(MODE_SUPPLIER_SEARCH), "поиск поставщиков")
        self.assertEqual(_mode_label(MODE_PROCUREMENT_REPORT), "анализ документации")
        self.assertEqual(_mode_label(MODE_ANALYSIS_AND_SUPPLIERS), "анализ и поиск поставщиков")
        self.assertEqual(_job_mode_for_scenario("analysis_and_suppliers"), MODE_ANALYSIS_AND_SUPPLIERS)

    def test_pending_batch_counts_source_links_as_inputs(self) -> None:
        pending = PendingBatch(
            telegram_id="123",
            mode=MODE_PROCUREMENT_REPORT,
            files=[],
            sources=[{"kind": "procurement_url", "value": "https://etp.example.ru/procedure/123"}],
        )

        self.assertEqual(_pending_input_count(pending), 1)

    def test_source_links_are_only_for_documentation_analysis_modes(self) -> None:
        self.assertFalse(_scenario_accepts_source_links(bot_module.SCENARIO_SUPPLIERS))
        self.assertTrue(_scenario_accepts_source_links("report"))
        self.assertTrue(_scenario_accepts_source_links("analysis_and_suppliers"))

        text = _source_link_rejection_text()

        self.assertIn("Номер извещения", text)
        self.assertIn("файл ТЗ", text)
        self.assertIn(BUTTON_REPORT, text)
        self.assertIn(BUTTON_ANALYSIS_AND_SUPPLIERS, text)

    def test_document_caption_source_link_is_captured_only_for_analysis(self) -> None:
        caption = "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0317400001026000049"

        report_sources = _source_payloads_for_scenario("report", caption)
        supplier_sources = _source_payloads_for_scenario(bot_module.SCENARIO_SUPPLIERS, caption)

        self.assertEqual(len(report_sources), 1)
        self.assertEqual(report_sources[0]["value"], caption)
        self.assertEqual(supplier_sources, [])

    def test_notice_number_is_captured_only_for_analysis_modes(self) -> None:
        report_sources = _source_payloads_for_scenario("analysis_and_suppliers", "0371100005626000040")
        supplier_sources = _source_payloads_for_scenario(bot_module.SCENARIO_SUPPLIERS, "0371100005626000040")

        self.assertEqual(len(report_sources), 1)
        self.assertEqual(report_sources[0]["kind"], "tenderplan_notice")
        self.assertEqual(report_sources[0]["value"], "0371100005626000040")
        self.assertEqual(supplier_sources, [])

    def test_notice_number_in_supplier_mode_is_rejected_without_switching_modes(self) -> None:
        class FakeDb:
            def close(self) -> None:
                pass

        class FakeMessage:
            text = "32616063169"
            chat = SimpleNamespace(id=456)
            from_user = SimpleNamespace(id=123, username="", first_name="", last_name="")

            def __init__(self) -> None:
                self.answers = []

            async def answer(self, value: str, reply_markup=None):
                self.answers.append((value, reply_markup))
                return self

        message = FakeMessage()
        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "get_or_create_trial_client_by_telegram_id": bot_module.get_or_create_trial_client_by_telegram_id,
            "client_access_error": bot_module.client_access_error,
            "get_or_create_settings": bot_module.get_or_create_settings,
        }
        pending_modes = dict(bot_module.PENDING_MODES)
        pending_uploads = dict(bot_module.PENDING_UPLOADS)
        running_chats = set(bot_module.BATCH_RUNNING_CHATS)
        try:
            bot_module.PENDING_MODES.clear()
            bot_module.PENDING_UPLOADS.clear()
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.PENDING_MODES[message.chat.id] = bot_module.SCENARIO_SUPPLIERS
            bot_module.SessionLocal = lambda: FakeDb()
            bot_module.get_or_create_trial_client_by_telegram_id = (
                lambda _db, telegram_id, username="", name="": (SimpleNamespace(id="client-1"), "")
            )
            bot_module.client_access_error = lambda *_args, **_kwargs: ""
            bot_module.get_or_create_settings = lambda _db: SimpleNamespace(default_supplier_target=3)

            handled = asyncio.run(_handle_source_text(message))
            switched_scenario = bot_module.PENDING_MODES.get(message.chat.id)
            pending_exists = message.chat.id in bot_module.PENDING_UPLOADS
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)
            bot_module.PENDING_MODES.clear()
            bot_module.PENDING_MODES.update(pending_modes)
            bot_module.PENDING_UPLOADS.clear()
            bot_module.PENDING_UPLOADS.update(pending_uploads)
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.update(running_chats)

        self.assertTrue(handled)
        self.assertFalse(pending_exists)
        self.assertEqual(switched_scenario, bot_module.SCENARIO_SUPPLIERS)
        self.assertIn("нужен файл ТЗ/ООЗ", message.answers[0][0])

    def test_add_pending_sources_deduplicates_caption_and_text_links(self) -> None:
        pending = PendingBatch(telegram_id="123", mode=MODE_PROCUREMENT_REPORT, files=[])
        sources = [
            {"kind": "official_eis", "value": "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=123"},
            {"kind": "official_eis", "value": "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=123"},
        ]

        added = _add_pending_sources(pending, sources)

        self.assertEqual(added, 1)
        self.assertEqual(_pending_input_count(pending), 1)

    def test_pending_added_text_counts_procurement_sources_not_only_links(self) -> None:
        pending = PendingBatch(
            telegram_id="123",
            mode=MODE_PROCUREMENT_REPORT,
            files=[("Извещение.docx", b"notice")],
            sources=[{"kind": "tenderplan_notice", "value": "0371100005626000040"}],
        )

        text = _pending_added_text(pending, max_files=20, added_sources=1)

        self.assertIn("✅ Материалы добавлены", text)
        self.assertIn("Файлов: 1/20", text)
        self.assertIn("Источников: 1", text)

    def test_source_added_text_is_short_and_customer_facing(self) -> None:
        pending = PendingBatch(
            telegram_id="123",
            mode=MODE_PROCUREMENT_REPORT,
            files=[],
            sources=[{"kind": "tenderplan_notice", "value": "0371100005626000040"}],
        )

        text = _source_added_text(pending)

        self.assertIn("📎 Источник добавлен", text)
        self.assertIn("Источников: 1", text)
        self.assertIn("запустить обработку", text)
        self.assertNotIn("Tenderplan", text)

    def test_supplier_multi_specs_split_each_tz_into_separate_job_payload(self) -> None:
        pending = PendingBatch(
            telegram_id="123",
            mode=MODE_SUPPLIER_SEARCH,
            files=[
                ("ТЗ насос.docx", b"pump"),
                ("ТЗ вентиляция.docx", b"vent"),
            ],
        )

        specs = _supplier_multi_job_specs(pending)

        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0][0], "ТЗ насос")
        self.assertEqual(specs[0][1], [("ТЗ насос.docx", b"pump")])
        self.assertEqual(specs[1][0], "ТЗ вентиляция")
        self.assertEqual(specs[1][1], [("ТЗ вентиляция.docx", b"vent")])

    def test_supplier_multi_specs_ignore_documentation_analysis_modes(self) -> None:
        pending = PendingBatch(
            telegram_id="123",
            mode=MODE_PROCUREMENT_REPORT,
            files=[
                ("Извещение.docx", b"notice"),
                ("Проект договора.docx", b"contract"),
            ],
        )

        self.assertEqual(_supplier_multi_job_specs(pending), [])

    def test_supplier_text_tz_detection_and_payload_use_txt_input(self) -> None:
        text = (
            "Техническое задание\n"
            "Поставка насосов ЦНС 60-330, количество 3 шт. "
            "Нужны производители или поставщики с контактами для запроса КП."
        )

        self.assertTrue(_looks_like_supplier_text_tz(text))
        self.assertFalse(_looks_like_supplier_text_tz("https://etp.example.ru/procedure/123"))

        filename, content, title = _supplier_text_tz_payload(text)

        self.assertTrue(filename.endswith(".txt"))
        self.assertEqual(title, "Техническое задание")
        self.assertIn("Поставка насосов", content.decode("utf-8"))


class BotOutputDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_edit_failure_replaces_and_deletes_old_progress_message(self) -> None:
        class ReplacementMessage:
            pass

        class FakeStatusMessage:
            def __init__(self) -> None:
                self.answers: list[str] = []
                self.deleted = False
                self.replacement = ReplacementMessage()

            async def edit_text(self, value: str, reply_markup=None):
                raise TelegramBadRequest(method=None, message="Bad Request: message can't be edited")

            async def answer(self, value: str, reply_markup=None):
                self.answers.append(value)
                return self.replacement

            async def delete(self) -> None:
                self.deleted = True

        status_message = FakeStatusMessage()

        result = await _edit_or_send_status(status_message, "новый статус")

        self.assertIs(result, status_message.replacement)
        self.assertEqual(status_message.answers, ["новый статус"])
        self.assertTrue(status_message.deleted)

    async def test_watch_job_progress_can_reuse_launch_message(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-1",
            mode=MODE_PROCUREMENT_REPORT,
            status="completed",
            progress=100,
            message="Анализ документации готов",
            error="",
            created_at=None,
        )

        class FakeMessage:
            def __init__(self) -> None:
                self.answers: list[tuple[str, object]] = []

            async def answer(self, value: str, reply_markup=None):
                self.answers.append((value, reply_markup))
                return self

        class FakeStatusMessage:
            def __init__(self) -> None:
                self.edits: list[tuple[str, object]] = []

            async def edit_text(self, value: str, reply_markup=None):
                self.edits.append((value, reply_markup))
                return self

            async def answer(self, value: str, reply_markup=None):
                raise AssertionError(f"unexpected fallback status message: {value}")

        message = FakeMessage()
        status_message = FakeStatusMessage()
        original_load = bot_module._load_job_snapshot
        try:
            bot_module._load_job_snapshot = lambda _job_id: snapshot

            result = await watch_job_progress(message, "job-1", status_message=status_message)
        finally:
            bot_module._load_job_snapshot = original_load

        self.assertEqual(result, snapshot)
        self.assertEqual(message.answers, [])
        self.assertGreaterEqual(len(status_message.edits), 1)
        self.assertIn("анализ документации готов", status_message.edits[-1][0])

    async def test_watch_job_progress_attaches_inline_cancel_to_running_message(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-1",
            mode=MODE_SUPPLIER_SEARCH,
            status="running",
            progress=30,
            message="Ищу поставщиков",
            error="",
            created_at=None,
        )

        class FakeMessage:
            class Chat:
                id = 123

            chat = Chat()
            answers: list[tuple[str, object]] = []

            async def answer(self, value: str, reply_markup=None):
                self.answers.append((value, reply_markup))
                return self

        class FakeStatusMessage:
            def __init__(self) -> None:
                self.edits: list[tuple[str, object]] = []

            async def edit_text(self, value: str, reply_markup=None):
                self.edits.append((value, reply_markup))
                return self

            async def answer(self, value: str, reply_markup=None):
                raise AssertionError(f"unexpected fallback status message: {value}")

        message = FakeMessage()
        status_message = FakeStatusMessage()
        original_load = bot_module._load_job_snapshot
        try:
            bot_module._load_job_snapshot = lambda _job_id: snapshot

            result = await watch_job_progress(
                message,
                "job-1",
                status_message=status_message,
                timeout_seconds=0,
            )
        finally:
            bot_module._load_job_snapshot = original_load

        self.assertEqual(result, snapshot)
        self.assertGreaterEqual(len(status_message.edits), 1)
        first_markup = status_message.edits[0][1]
        self.assertIsNotNone(first_markup)
        self.assertEqual(first_markup.inline_keyboard[0][0].callback_data, "cancel_job:job-1")

    async def test_cancel_job_callback_cancels_running_job_and_returns_menu(self) -> None:
        job = SimpleNamespace(
            id="job-1",
            mode=MODE_SUPPLIER_SEARCH,
            status="running",
            progress=30,
            message="Ищу поставщиков",
            error="",
            created_at=None,
            completed_at=None,
            updated_at=None,
        )
        commits: list[bool] = []
        closed: list[bool] = []
        released: list[str] = []
        cancelled: list[str] = []

        class FakeDb:
            def get(self, _model, job_id: str):
                self.last_job_id = job_id
                return job

            def commit(self) -> None:
                commits.append(True)

            def close(self) -> None:
                closed.append(True)

        class FakeChat:
            id = 123

        class FakeMessage:
            def __init__(self) -> None:
                self.chat = FakeChat()
                self.edits: list[tuple[str, object]] = []
                self.answers: list[tuple[str, object]] = []

            async def edit_text(self, value: str, reply_markup=None):
                self.edits.append((value, reply_markup))
                return self

            async def answer(self, value: str, reply_markup=None):
                self.answers.append((value, reply_markup))
                return self

        class FakeCallback:
            def __init__(self) -> None:
                self.data = "cancel_job:job-1"
                self.message = FakeMessage()
                self.from_user = SimpleNamespace(id=123)
                self.answers: list[tuple[str, bool]] = []

            async def answer(self, value: str = "", show_alert: bool = False):
                self.answers.append((value, show_alert))

        callback = FakeCallback()
        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "_callback_job_allowed": bot_module._callback_job_allowed,
            "release_job_reservation": bot_module.release_job_reservation,
            "cancel_running_job": bot_module.cancel_running_job,
        }
        original_notified = set(bot_module.BOT_CANCEL_NOTIFIED_JOBS)
        running_chats = set(bot_module.BATCH_RUNNING_CHATS)
        try:
            bot_module.BOT_CANCEL_NOTIFIED_JOBS.clear()
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.add(123)
            bot_module.SessionLocal = lambda: FakeDb()
            bot_module._callback_job_allowed = lambda _callback, _job_id: True
            bot_module.release_job_reservation = lambda _db, _job, *, note: released.append(note)
            bot_module.cancel_running_job = lambda job_id: cancelled.append(job_id)

            await bot_module.cancel_job_callback(callback)
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)
            bot_module.BOT_CANCEL_NOTIFIED_JOBS.clear()
            bot_module.BOT_CANCEL_NOTIFIED_JOBS.update(original_notified)
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.update(running_chats)

        self.assertEqual(job.status, "cancelled")
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.message, "Задача отменена в Telegram")
        self.assertEqual(released, ["Резерв возвращён: задача отменена в Telegram"])
        self.assertEqual(cancelled, ["job-1"])
        self.assertTrue(commits)
        self.assertTrue(closed)
        self.assertEqual(callback.answers, [("Задача отменена.", False)])
        self.assertIn("Задача отменена", callback.message.edits[-1][0])
        self.assertIsNone(callback.message.edits[-1][1])
        self.assertIn("можно запустить новую обработку", callback.message.answers[-1][0])
        self.assertIsNotNone(callback.message.answers[-1][1])
        self.assertNotIn(123, bot_module.BATCH_RUNNING_CHATS)

    def test_watch_job_progress_sends_main_menu_after_external_cancel(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-cancelled",
            mode=MODE_ANALYSIS_AND_SUPPLIERS,
            status="cancelled",
            progress=100,
            message="Задача отменена клиентом",
            error="",
            created_at=None,
        )

        class FakeChat:
            id = 12345

        class FakeMessage:
            def __init__(self) -> None:
                self.chat = FakeChat()
                self.answers: list[tuple[str, object]] = []

            async def answer(self, value: str, reply_markup=None):
                self.answers.append((value, reply_markup))
                return self

        class FakeStatusMessage:
            def __init__(self) -> None:
                self.edits: list[tuple[str, object]] = []

            async def edit_text(self, value: str, reply_markup=None):
                self.edits.append((value, reply_markup))
                return self

            async def answer(self, value: str, reply_markup=None):
                raise AssertionError(f"unexpected fallback status message: {value}")

        async def run_case():
            message = FakeMessage()
            status_message = FakeStatusMessage()
            original_load = bot_module._load_job_snapshot
            original_notified = set(bot_module.BOT_CANCEL_NOTIFIED_JOBS)
            try:
                bot_module.BOT_CANCEL_NOTIFIED_JOBS.clear()
                bot_module._load_job_snapshot = lambda _job_id: snapshot
                result = await watch_job_progress(message, "job-cancelled", status_message=status_message)
            finally:
                bot_module._load_job_snapshot = original_load
                bot_module.BOT_CANCEL_NOTIFIED_JOBS.clear()
                bot_module.BOT_CANCEL_NOTIFIED_JOBS.update(original_notified)
            return result, message, status_message

        result, message, status_message = asyncio.run(run_case())

        self.assertEqual(result, snapshot)
        self.assertGreaterEqual(len(status_message.edits), 1)
        self.assertIn("Задача отменена", status_message.edits[-1][0])
        self.assertEqual(len(message.answers), 1)
        self.assertIn("можно запустить новую обработку", message.answers[0][0])
        self.assertIsNotNone(message.answers[0][1])

    async def test_supplier_multi_watch_does_not_claim_file_sent_after_cancel(self) -> None:
        snapshot = JobProgressSnapshot(
            id="job-cancelled",
            mode=MODE_SUPPLIER_SEARCH,
            status="cancelled",
            progress=100,
            message="Задача отменена клиентом",
            error="",
            created_at=None,
        )

        class FakeChat:
            id = 12345

        class FakeMessage:
            chat = FakeChat()

            async def answer(self, value: str, reply_markup=None):
                raise AssertionError(f"unexpected message: {value}")

        class FakeStatusMessage:
            def __init__(self) -> None:
                self.edits: list[tuple[str, object]] = []

            async def edit_text(self, value: str, reply_markup=None):
                self.edits.append((value, reply_markup))
                return self

            async def answer(self, value: str, reply_markup=None):
                raise AssertionError(f"unexpected fallback status message: {value}")

        async def fake_watch(_message, _job_id, *, status_message=None):
            return snapshot

        async def fake_outputs(*_args, **_kwargs):
            raise AssertionError("cancelled jobs should not send outputs")

        status_message = FakeStatusMessage()
        originals = {
            "watch_job_progress": bot_module.watch_job_progress,
            "_send_job_outputs": bot_module._send_job_outputs,
        }
        try:
            bot_module.watch_job_progress = fake_watch
            bot_module._send_job_outputs = fake_outputs

            await bot_module._watch_supplier_multi_outputs(
                FakeMessage(),
                [("job-cancelled", "Запрос КП - Испытательный пресс.docx")],
                status_message=status_message,
            )
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)

        edited_text = "\n".join(text for text, _reply_markup in status_message.edits)
        self.assertIn("Обрабатываю ТЗ", edited_text)
        self.assertNotIn("Файл отправлен ниже", edited_text)
        self.assertNotIn("Файлы отправлены ниже", edited_text)

    async def test_watch_job_progress_edits_launch_message_into_partial_confirmation(self) -> None:
        snapshots = [
            JobProgressSnapshot(
                id="job-1",
                mode="supplier_search",
                status="running",
                progress=92,
                message="Расширяю поиск: подтверждено 45",
                error="",
                created_at=None,
            ),
            JobProgressSnapshot(
                id="job-1",
                mode="supplier_search",
                status="awaiting_customer_confirmation",
                progress=100,
                message="Найдено меньше поставщиков: найдено и проверено 36",
                error="",
                created_at=None,
            ),
        ]

        class FakeMessage:
            def __init__(self) -> None:
                self.answers: list[tuple[str, object]] = []

            async def answer(self, value: str, reply_markup=None):
                self.answers.append((value, reply_markup))
                return self

        class FakeStatusMessage:
            def __init__(self) -> None:
                self.edits: list[tuple[str, object]] = []

            async def edit_text(self, value: str, reply_markup=None):
                self.edits.append((value, reply_markup))
                return self

            async def answer(self, value: str, reply_markup=None):
                raise AssertionError(f"unexpected fallback status message: {value}")

        message = FakeMessage()
        status_message = FakeStatusMessage()
        original_load = bot_module._load_job_snapshot
        try:
            bot_module._load_job_snapshot = lambda _job_id: snapshots.pop(0)

            result = await watch_job_progress(message, "job-1", status_message=status_message, poll_interval=0)
        finally:
            bot_module._load_job_snapshot = original_load

        self.assertEqual(result.status, "awaiting_customer_confirmation")
        self.assertEqual(message.answers, [])
        self.assertEqual(len(status_message.edits), 2)
        self.assertIn("Расширяю поиск", status_message.edits[0][0])
        self.assertIsNotNone(status_message.edits[0][1])
        self.assertEqual(status_message.edits[0][1].inline_keyboard[0][0].callback_data, "cancel_job:job-1")
        self.assertIn("Найдено меньше поставщиков", status_message.edits[-1][0])
        self.assertIsNotNone(status_message.edits[-1][1])
        self.assertIn("Да, отправить и списать", status_message.edits[-1][1].inline_keyboard[0][0].text)

    async def test_send_job_outputs_edits_file_caption_instead_of_sending_balance_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "analysis.docx"
            output.write_bytes(b"docx")

            done_job = SimpleNamespace(
                id="job-1",
                mode=MODE_PROCUREMENT_REPORT,
                client=SimpleNamespace(id="client-1"),
            )
            charges: list[str] = []

            class FakeDb:
                def get(self, _model, job_id: str):
                    assert job_id == "job-1"
                    return done_job

                def close(self) -> None:
                    return None

            class FakeSentDocument:
                def __init__(self, caption: str, reply_markup) -> None:
                    self.caption = caption
                    self.reply_markup = reply_markup
                    self.edits: list[tuple[str, object]] = []

                async def edit_caption(self, *, caption: str, reply_markup=None):
                    self.caption = caption
                    self.reply_markup = reply_markup
                    self.edits.append((caption, reply_markup))
                    return self

            class FakeMessage:
                def __init__(self) -> None:
                    self.answers: list[tuple[str, object]] = []
                    self.documents: list[FakeSentDocument] = []

                async def answer(self, value: str, reply_markup=None):
                    self.answers.append((value, reply_markup))
                    return self

                async def answer_document(self, _document, *, caption: str, reply_markup=None):
                    sent = FakeSentDocument(caption, reply_markup)
                    self.documents.append(sent)
                    return sent

            message = FakeMessage()
            originals = {
                "SessionLocal": bot_module.SessionLocal,
                "package_job_output_files": bot_module.package_job_output_files,
                "charge_job_reservation": bot_module.charge_job_reservation,
                "_after_delivery_balance_text": bot_module._after_delivery_balance_text,
            }
            try:
                bot_module.SessionLocal = lambda: FakeDb()
                bot_module.package_job_output_files = lambda _job: [output]
                bot_module.charge_job_reservation = lambda _db, job: charges.append(job.id)
                bot_module._after_delivery_balance_text = (
                    lambda _db, _client: "✅ Результат отправлен. Баланс обновлён.\n\nВажно: проверьте первоисточники."
                )

                delivered = await _send_job_outputs(message, "job-1")
            finally:
                for name, value in originals.items():
                    setattr(bot_module, name, value)

        self.assertTrue(delivered)
        self.assertEqual(charges, ["job-1"])
        self.assertEqual(len(message.answers), 1)
        self.assertIn("Что хотите сделать дальше", message.answers[0][0])
        self.assertEqual(len(message.documents), 1)
        self.assertIn("Анализ документации во вложении.", message.documents[0].caption)
        self.assertIn("✅ Результат отправлен. Баланс обновлён.", message.documents[0].caption)
        self.assertEqual(len(message.documents[0].edits), 1)
        self.assertIsNotNone(message.documents[0].reply_markup)

    async def test_send_job_outputs_does_not_send_files_for_cancelled_job(self) -> None:
        done_job = SimpleNamespace(
            id="job-cancelled",
            mode=MODE_SUPPLIER_SEARCH,
            status="cancelled",
            evidence_path="/tmp/should-not-read.json",
            result_path="/tmp/should-not-send.xlsx",
            client=SimpleNamespace(id="client-1"),
        )
        package_calls: list[str] = []
        charges: list[str] = []

        class FakeDb:
            def get(self, _model, job_id: str):
                assert job_id == "job-cancelled"
                return done_job

            def close(self) -> None:
                return None

        class FakeMessage:
            def __init__(self) -> None:
                self.answers: list[tuple[str, object]] = []
                self.documents: list[object] = []

            async def answer(self, value: str, reply_markup=None):
                self.answers.append((value, reply_markup))
                return self

            async def answer_document(self, *_args, **_kwargs):
                self.documents.append((_args, _kwargs))
                return self

        message = FakeMessage()
        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "package_job_output_items": bot_module.package_job_output_items,
            "package_job_output_files": bot_module.package_job_output_files,
            "charge_job_reservation": bot_module.charge_job_reservation,
        }
        try:
            bot_module.SessionLocal = lambda: FakeDb()
            bot_module.package_job_output_items = lambda _job: package_calls.append(_job.id) or [
                {"kind": "suppliers", "path": "/tmp/should-not-send.xlsx"}
            ]
            bot_module.package_job_output_files = lambda _job: package_calls.append(_job.id) or [Path("/tmp/should-not-send.xlsx")]
            bot_module.charge_job_reservation = lambda _db, job: charges.append(job.id)

            delivered = await _send_job_outputs(message, "job-cancelled")
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)

        self.assertFalse(delivered)
        self.assertEqual(package_calls, [])
        self.assertEqual(charges, [])
        self.assertEqual(message.answers, [])
        self.assertEqual(message.documents, [])

    async def test_send_job_outputs_does_not_reopen_expired_registry_fallback(self) -> None:
        done_job = SimpleNamespace(
            id="job-delivery-expired",
            mode=MODE_SUPPLIER_SEARCH,
            status="delivery_expired",
            confirmation_kind="registry_fallback",
            confirmation_outcome="accepted",
            offer_delivery_outcome="expired",
            evidence_path="/tmp/should-not-read.json",
            result_path="/tmp/should-not-send.xlsx",
            client=SimpleNamespace(id="client-1"),
        )
        package_calls: list[str] = []

        class FakeDb:
            def get(self, _model, job_id: str):
                assert job_id == done_job.id
                return done_job

            def close(self) -> None:
                return None

        class FakeMessage:
            def __init__(self) -> None:
                self.documents: list[object] = []

            async def answer_document(self, *_args, **_kwargs):
                self.documents.append((_args, _kwargs))
                return self

        message = FakeMessage()
        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "package_job_output_items": bot_module.package_job_output_items,
            "package_job_output_files": bot_module.package_job_output_files,
        }
        try:
            bot_module.SessionLocal = lambda: FakeDb()
            bot_module.package_job_output_items = lambda job: package_calls.append(job.id) or []
            bot_module.package_job_output_files = lambda job: package_calls.append(job.id) or []

            delivered = await _send_job_outputs(message, done_job.id)
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)

        self.assertFalse(delivered)
        self.assertEqual(package_calls, [])
        self.assertEqual(message.documents, [])

    async def test_registry_fallback_delivery_settles_only_after_all_files_are_sent_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fallback.xlsx"
            output.write_bytes(b"xlsx")
            job = SimpleNamespace(
                id="job-registry-delivery",
                mode=MODE_SUPPLIER_SEARCH,
                confirmation_kind="registry_fallback",
                confirmation_outcome="pending",
                offer_delivery_outcome="",
                client=None,
            )
            calls: list[tuple[str, object]] = []

            class FakeDb:
                def get(self, _model, job_id: str):
                    assert job_id == job.id
                    return job

                def close(self) -> None:
                    return None

            class FakeMessage:
                def __init__(self) -> None:
                    self.documents: list[str] = []

                async def answer_document(self, document, *, caption: str, reply_markup=None):
                    self.documents.append(str(document.path))
                    return SimpleNamespace()

            def fake_accept(_db, accepted_job, *, channel: str):
                calls.append(("accept", channel))
                accepted_job.confirmation_outcome = "accepted"
                accepted_job.offer_delivery_outcome = "pending"
                return accepted_job

            def fake_complete(_db, completed_job, token: str, *, billing_kinds, channel: str, note: str):
                self.assertEqual(completed_job, job)
                self.assertEqual(token, "delivery-token")
                calls.append(("complete", (tuple(billing_kinds), channel, note)))
                completed_job.offer_delivery_outcome = "delivered"
                return True

            message = FakeMessage()
            originals = {
                "SessionLocal": bot_module.SessionLocal,
                "accept_job_result_offer": bot_module.accept_job_result_offer,
                "claim_job_result_offer_delivery": bot_module.claim_job_result_offer_delivery,
                "active_result_offer_output_items": bot_module.active_result_offer_output_items,
                "billing_kinds_for_result_delivery": bot_module.billing_kinds_for_result_delivery,
                "complete_job_result_offer_delivery": bot_module.complete_job_result_offer_delivery,
                "fail_job_result_offer_delivery": bot_module.fail_job_result_offer_delivery,
                "job_can_find_more_suppliers": bot_module.job_can_find_more_suppliers,
                "charge_job_reservation": bot_module.charge_job_reservation,
            }
            delivered_before = set(bot_module.DELIVERED_JOB_IDS)
            try:
                bot_module.DELIVERED_JOB_IDS.discard(job.id)
                bot_module.SessionLocal = lambda: FakeDb()
                bot_module.accept_job_result_offer = fake_accept
                bot_module.claim_job_result_offer_delivery = (
                    lambda _db, _job, *, channel: calls.append(("claim", channel)) or "delivery-token"
                )
                bot_module.active_result_offer_output_items = (
                    lambda _job: [{"kind": "suppliers", "path": str(output), "billing_kind": "supplier_search"}]
                )
                bot_module.billing_kinds_for_result_delivery = lambda _job: ["supplier_search"]
                bot_module.complete_job_result_offer_delivery = fake_complete
                bot_module.fail_job_result_offer_delivery = (
                    lambda *_args, **_kwargs: calls.append(("fail", None))
                )
                bot_module.job_can_find_more_suppliers = lambda _job: False
                bot_module.charge_job_reservation = lambda *_args, **_kwargs: self.fail("legacy charge must not run")

                delivered = await bot_module._send_result_offer_outputs(
                    message,
                    job.id,
                    accept_if_pending=True,
                )
                repeated = await bot_module._send_result_offer_outputs(
                    message,
                    job.id,
                    accept_if_pending=True,
                )
            finally:
                for name, value in originals.items():
                    setattr(bot_module, name, value)
                bot_module.DELIVERED_JOB_IDS.clear()
                bot_module.DELIVERED_JOB_IDS.update(delivered_before)

        self.assertTrue(delivered)
        self.assertFalse(repeated)
        self.assertEqual(len(message.documents), 1)
        self.assertEqual([name for name, _value in calls], ["accept", "claim", "complete"])

    async def test_registry_fallback_send_failure_releases_claim_without_charge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fallback.xlsx"
            output.write_bytes(b"xlsx")
            job = SimpleNamespace(
                id="job-registry-send-failure",
                mode=MODE_SUPPLIER_SEARCH,
                confirmation_kind="registry_fallback",
                confirmation_outcome="accepted",
                offer_delivery_outcome="pending",
                client=None,
            )
            failed_tokens: list[str] = []
            completed: list[str] = []

            class FakeDb:
                def get(self, _model, _job_id: str):
                    return job

                def close(self) -> None:
                    return None

            class FakeMessage:
                async def answer_document(self, *_args, **_kwargs):
                    raise RuntimeError("telegram unavailable")

            originals = {
                "SessionLocal": bot_module.SessionLocal,
                "claim_job_result_offer_delivery": bot_module.claim_job_result_offer_delivery,
                "active_result_offer_output_items": bot_module.active_result_offer_output_items,
                "complete_job_result_offer_delivery": bot_module.complete_job_result_offer_delivery,
                "fail_job_result_offer_delivery": bot_module.fail_job_result_offer_delivery,
            }
            try:
                bot_module.SessionLocal = lambda: FakeDb()
                bot_module.claim_job_result_offer_delivery = lambda *_args, **_kwargs: "failed-token"
                bot_module.active_result_offer_output_items = lambda _job: [{"kind": "suppliers", "path": str(output)}]
                bot_module.complete_job_result_offer_delivery = (
                    lambda *_args, **_kwargs: completed.append("charged") or True
                )
                bot_module.fail_job_result_offer_delivery = (
                    lambda _db, _job, token: failed_tokens.append(token)
                )

                with self.assertRaisesRegex(RuntimeError, "telegram unavailable"):
                    await bot_module._send_result_offer_outputs(
                        FakeMessage(),
                        job.id,
                        accept_if_pending=False,
                    )
            finally:
                for name, value in originals.items():
                    setattr(bot_module, name, value)

        self.assertEqual(failed_tokens, ["failed-token"])
        self.assertEqual(completed, [])

    async def test_send_job_outputs_offers_find_more_for_supplier_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "suppliers.xlsx"
            output.write_bytes(b"xlsx")

            done_job = SimpleNamespace(
                id="job-2",
                mode=MODE_SUPPLIER_SEARCH,
                client=SimpleNamespace(id="client-1"),
                verified_count=8,
                status="completed",
            )
            charges: list[str] = []

            class FakeDb:
                def get(self, _model, job_id: str):
                    assert job_id == "job-2"
                    return done_job

                def close(self) -> None:
                    return None

            class FakeSentDocument:
                def __init__(self, caption: str, reply_markup) -> None:
                    self.caption = caption
                    self.reply_markup = reply_markup
                    self.edits: list[tuple[str, object]] = []

                async def edit_caption(self, *, caption: str, reply_markup=None):
                    self.caption = caption
                    self.reply_markup = reply_markup
                    self.edits.append((caption, reply_markup))
                    return self

            class FakeMessage:
                def __init__(self) -> None:
                    self.answers: list[tuple[str, object]] = []
                    self.documents: list[FakeSentDocument] = []

                async def answer(self, value: str, reply_markup=None):
                    self.answers.append((value, reply_markup))
                    return self

                async def answer_document(self, _document, *, caption: str, reply_markup=None):
                    sent = FakeSentDocument(caption, reply_markup)
                    self.documents.append(sent)
                    return sent

            message = FakeMessage()
            originals = {
                "SessionLocal": bot_module.SessionLocal,
                "package_job_output_files": bot_module.package_job_output_files,
                "charge_job_reservation": bot_module.charge_job_reservation,
                "_after_delivery_balance_text": bot_module._after_delivery_balance_text,
            }
            try:
                bot_module.SessionLocal = lambda: FakeDb()
                bot_module.package_job_output_files = lambda _job: [output]
                bot_module.charge_job_reservation = lambda _db, job: charges.append(job.id)
                bot_module._after_delivery_balance_text = (
                    lambda _db, _client: "✅ Результат отправлен. Баланс обновлён."
                )

                delivered = await _send_job_outputs(message, "job-2")
            finally:
                for name, value in originals.items():
                    setattr(bot_module, name, value)

        self.assertTrue(delivered)
        self.assertEqual(charges, ["job-2"])
        self.assertEqual(len(message.answers), 1)
        self.assertIn("Найти ещё", message.answers[0][0])
        self.assertEqual(message.answers[0][1].inline_keyboard[0][0].callback_data, "find_more_prompt:job-2")


class SupplierTextTzHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_supplier_text_tz_is_added_to_unified_supplier_batch(self) -> None:
        text = (
            "Техническое задание\n"
            "Поставка насосов ЦНС 60-330, количество 3 шт. "
            "Нужны производители или поставщики с контактами для запроса КП."
        )

        class FakeDb:
            def close(self) -> None:
                return None

        class FakeMessage:
            def __init__(self) -> None:
                self.text = text
                self.chat = SimpleNamespace(id=444)
                self.from_user = SimpleNamespace(id=123, username="buyer", first_name="Ivan", last_name="")
                self.answers: list[tuple[str, object]] = []

            async def answer(self, value: str, reply_markup=None):
                self.answers.append((value, reply_markup))
                return self

        message = FakeMessage()
        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "get_or_create_trial_client_by_telegram_id": bot_module.get_or_create_trial_client_by_telegram_id,
            "client_access_error": bot_module.client_access_error,
            "get_or_create_settings": bot_module.get_or_create_settings,
        }
        pending_modes = dict(bot_module.PENDING_MODES)
        pending_uploads = dict(bot_module.PENDING_UPLOADS)
        upload_locks = dict(bot_module.CHAT_UPLOAD_LOCKS)
        running_chats = set(bot_module.BATCH_RUNNING_CHATS)
        try:
            bot_module.PENDING_MODES.clear()
            bot_module.PENDING_UPLOADS.clear()
            bot_module.CHAT_UPLOAD_LOCKS.clear()
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.PENDING_MODES[message.chat.id] = bot_module.SCENARIO_SUPPLIERS
            bot_module.SessionLocal = lambda: FakeDb()
            bot_module.get_or_create_trial_client_by_telegram_id = (
                lambda _db, telegram_id, username="", name="": (SimpleNamespace(id="client-1"), "")
            )
            bot_module.client_access_error = lambda *_args, **_kwargs: ""
            bot_module.get_or_create_settings = lambda _db: SimpleNamespace(max_files_per_batch=20)

            handled = await _handle_supplier_text_tz(message)
            pending = bot_module.PENDING_UPLOADS[message.chat.id]
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)
            bot_module.PENDING_MODES.clear()
            bot_module.PENDING_MODES.update(pending_modes)
            bot_module.PENDING_UPLOADS.clear()
            bot_module.PENDING_UPLOADS.update(pending_uploads)
            bot_module.CHAT_UPLOAD_LOCKS.clear()
            bot_module.CHAT_UPLOAD_LOCKS.update(upload_locks)
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.update(running_chats)

        self.assertTrue(handled)
        self.assertEqual(pending.mode, MODE_SUPPLIER_SEARCH)
        self.assertEqual(len(pending.files), 1)
        self.assertTrue(pending.files[0][0].endswith(".txt"))
        self.assertIn("Поставка насосов", pending.files[0][1].decode("utf-8"))
        self.assertIn("✅ ТЗ добавлено", message.answers[0][0])
        inline_kb = message.answers[0][1]
        labels = [button.text for row in inline_kb.inline_keyboard for button in row]
        self.assertTrue(any("Запустить" in label for label in labels))
        self.assertTrue(any("Очистить" in label for label in labels))


class TelegramButtonHandlerRegressionTests(unittest.IsolatedAsyncioTestCase):
    class FakeDb:
        def __init__(self) -> None:
            self.rolled_back = False

        def rollback(self) -> None:
            self.rolled_back = True

        def close(self) -> None:
            return None

    class FakeMessage:
        def __init__(self, chat_id: int = 991) -> None:
            self.chat = SimpleNamespace(id=chat_id)
            self.from_user = SimpleNamespace(id=123456, username="buyer", first_name="Ivan", last_name="")
            self.answers: list[tuple[str, object]] = []

        async def answer(self, value: str, reply_markup=None, **_kwargs):
            self.answers.append((value, reply_markup))
            return self

    async def test_journey_helper_unpacks_repository_contract(self) -> None:
        db = self.FakeDb()
        message = self.FakeMessage()
        recorded: list[tuple[str, str]] = []
        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "get_client_by_telegram_id": bot_module.get_client_by_telegram_id,
            "record_journey_event": bot_module.record_journey_event,
        }
        try:
            bot_module.SessionLocal = lambda: db
            bot_module.get_client_by_telegram_id = lambda _db, _telegram_id: (SimpleNamespace(id="client-1"), "")
            bot_module.record_journey_event = lambda _db, client_id, **kwargs: recorded.append((client_id, kwargs["event_name"]))

            bot_module._record_telegram_event(message, "create_opened")
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)

        self.assertEqual(recorded, [("client-1", "create_opened")])

    async def test_start_opens_scenarios_without_requesting_legal_acceptance(self) -> None:
        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return None

        class StartDb(self.FakeDb):
            def query(self, *_args, **_kwargs):
                return FakeQuery()

        message = self.FakeMessage(chat_id=9876)
        db = StartDb()
        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "get_or_create_trial_client_by_telegram_id": bot_module.get_or_create_trial_client_by_telegram_id,
            "record_journey_event": bot_module.record_journey_event,
        }
        had_accepted_helper = hasattr(bot_module, "accepted_legal_documents")
        original_accepted_helper = getattr(bot_module, "accepted_legal_documents", None)
        try:
            bot_module.SessionLocal = lambda: db
            bot_module.get_or_create_trial_client_by_telegram_id = (
                lambda *_args, **_kwargs: (SimpleNamespace(id="client-start"), "")
            )
            bot_module.accepted_legal_documents = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("/start must not query or gate on legal acceptance")
            )
            bot_module.record_journey_event = lambda *_args, **_kwargs: None

            await bot_module.start(message, SimpleNamespace(args=""))
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)
            if had_accepted_helper:
                bot_module.accepted_legal_documents = original_accepted_helper
            else:
                delattr(bot_module, "accepted_legal_documents")

        self.assertEqual(len(message.answers), 1)
        start_text, inline_kb = message.answers[0]
        self.assertIn("TenderLex", start_text)
        self.assertNotIn("подтвердите документы", start_text.lower())
        inline_labels = [button.text for row in inline_kb.inline_keyboard for button in row]
        self.assertTrue(any("Поставщики по ТЗ" in label for label in inline_labels))
        self.assertTrue(any("Анализ закупки" in label for label in inline_labels))
        self.assertTrue(any("Анализ + поиск" in label for label in inline_labels))
        self.assertTrue(any("Кабинет" in label for label in inline_labels))
        self.assertTrue(any("Задачи" in label for label in inline_labels))
        self.assertTrue(any("Тарифы" in label for label in inline_labels))
        self.assertTrue(any("Помощь" in label for label in inline_labels))
        self.assertTrue(any("Контакты" in label for label in inline_labels))

    def test_telegram_launch_acceptance_records_only_current_terms(self) -> None:
        recorded: list[dict] = []
        original = bot_module.record_legal_acceptance
        try:
            bot_module.record_legal_acceptance = lambda _db, **kwargs: recorded.append(kwargs)
            bot_module._record_telegram_terms_acceptance(object(), "123456")
        finally:
            bot_module.record_legal_acceptance = original

        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["subject_type"], "telegram")
        self.assertEqual(recorded[0]["subject_id"], "123456")
        self.assertEqual(recorded[0]["document_type"], bot_module.LEGAL_DOCUMENT_TERMS)
        self.assertEqual(recorded[0]["document_version"], bot_module.LEGAL_VERSION)
        self.assertEqual(recorded[0]["source"], "telegram_job_launch")
        self.assertNotEqual(recorded[0]["document_type"], bot_module.LEGAL_DOCUMENT_PERSONAL_DATA)

    async def test_legacy_legal_callback_does_not_accept_current_document_version(self) -> None:
        class LegacyMessage(self.FakeMessage):
            async def edit_text(self, value: str, reply_markup=None, **_kwargs):
                self.answers.append((value, reply_markup))

        class LegacyCallback:
            def __init__(self) -> None:
                self.data = "legal_accept:terms"
                self.message = LegacyMessage()
                self.from_user = self.message.from_user
                self.answers: list[str] = []

            async def answer(self, value: str, **_kwargs):
                self.answers.append(value)

        callback = LegacyCallback()
        original = bot_module.record_legal_acceptance
        try:
            bot_module.record_legal_acceptance = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("legacy callbacks must not accept the current document version")
            )
            await bot_module.legal_acceptance_callback(callback)
        finally:
            bot_module.record_legal_acceptance = original

        self.assertIn("Порядок обновлён", callback.answers[0])
        self.assertIn("Документы TenderLex", callback.message.answers[0][0])

    async def test_run_batch_records_terms_only_after_successful_launch(self) -> None:
        class LaunchDb(self.FakeDb):
            def commit(self) -> None:
                return None

        message = self.FakeMessage(chat_id=9880)
        pending = bot_module.PendingBatch(
            telegram_id="123456",
            mode=MODE_PROCUREMENT_REPORT,
            files=[("purchase.pdf", b"content")],
        )
        job = SimpleNamespace(id="job-launch", status="draft", message="")
        recorded: list[str] = []

        async def fake_watch(*_args, **_kwargs):
            return None

        async def fake_send(*_args, **_kwargs):
            return False

        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "_record_telegram_event": bot_module._record_telegram_event,
            "get_or_create_trial_client_by_telegram_id": bot_module.get_or_create_trial_client_by_telegram_id,
            "client_access_error": bot_module.client_access_error,
            "get_or_create_settings": bot_module.get_or_create_settings,
            "supplier_target_for_client": bot_module.supplier_target_for_client,
            "create_job": bot_module.create_job,
            "_reserve_created_job": bot_module._reserve_created_job,
            "_record_telegram_terms_acceptance": bot_module._record_telegram_terms_acceptance,
            "record_journey_event": bot_module.record_journey_event,
            "_job_snapshot": bot_module._job_snapshot,
            "_format_launch_progress": bot_module._format_launch_progress,
            "watch_job_progress": bot_module.watch_job_progress,
            "_send_job_outputs": bot_module._send_job_outputs,
        }
        saved_uploads = dict(bot_module.PENDING_UPLOADS)
        saved_running = set(bot_module.BATCH_RUNNING_CHATS)
        try:
            bot_module.PENDING_UPLOADS.clear()
            bot_module.PENDING_UPLOADS[message.chat.id] = pending
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.SessionLocal = LaunchDb
            bot_module._record_telegram_event = lambda *_args, **_kwargs: None
            bot_module.get_or_create_trial_client_by_telegram_id = (
                lambda *_args, **_kwargs: (SimpleNamespace(id="client-launch"), "")
            )
            bot_module.client_access_error = lambda *_args, **_kwargs: ""
            bot_module.get_or_create_settings = lambda _db: SimpleNamespace()
            bot_module.supplier_target_for_client = lambda *_args, **_kwargs: 10
            bot_module.create_job = lambda *_args, **_kwargs: job
            bot_module._reserve_created_job = lambda *_args, **_kwargs: ""
            bot_module._record_telegram_terms_acceptance = lambda _db, telegram_id: recorded.append(telegram_id)
            bot_module.record_journey_event = lambda *_args, **_kwargs: None
            bot_module._job_snapshot = lambda _job: SimpleNamespace()
            bot_module._format_launch_progress = lambda *_args, **_kwargs: "Обработка запущена"
            bot_module.watch_job_progress = fake_watch
            bot_module._send_job_outputs = fake_send

            await bot_module.run_batch_button(message)
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)
            bot_module.PENDING_UPLOADS.clear()
            bot_module.PENDING_UPLOADS.update(saved_uploads)
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.update(saved_running)

        self.assertEqual(recorded, ["123456"])
        self.assertEqual(job.status, "pending")

    async def test_run_batch_does_not_record_terms_for_empty_blocked_or_failed_launch(self) -> None:
        class LaunchDb(self.FakeDb):
            def commit(self) -> None:
                return None

        recorded: list[str] = []
        original_recorder = bot_module._record_telegram_terms_acceptance
        original_event = bot_module._record_telegram_event
        original_session = bot_module.SessionLocal
        original_get_client = bot_module.get_or_create_trial_client_by_telegram_id
        original_access = bot_module.client_access_error
        original_settings = bot_module.get_or_create_settings
        original_target = bot_module.supplier_target_for_client
        original_create = bot_module.create_job
        original_reserve = bot_module._reserve_created_job
        original_discard = bot_module._discard_unlaunched_jobs
        saved_uploads = dict(bot_module.PENDING_UPLOADS)
        saved_running = set(bot_module.BATCH_RUNNING_CHATS)
        try:
            bot_module.PENDING_UPLOADS.clear()
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module._record_telegram_terms_acceptance = lambda _db, telegram_id: recorded.append(telegram_id)
            bot_module._record_telegram_event = lambda *_args, **_kwargs: None
            bot_module.SessionLocal = LaunchDb

            await bot_module.run_batch_button(self.FakeMessage(chat_id=9881))

            blocked = self.FakeMessage(chat_id=9882)
            bot_module.PENDING_UPLOADS[blocked.chat.id] = bot_module.PendingBatch(
                telegram_id="blocked",
                mode=MODE_PROCUREMENT_REPORT,
                files=[("blocked.pdf", b"content")],
            )
            bot_module.get_or_create_trial_client_by_telegram_id = (
                lambda *_args, **_kwargs: (SimpleNamespace(id="blocked-client"), "")
            )
            bot_module.client_access_error = lambda *_args, **_kwargs: "Доступ закрыт"
            await bot_module.run_batch_button(blocked)

            failed = self.FakeMessage(chat_id=9883)
            bot_module.PENDING_UPLOADS[failed.chat.id] = bot_module.PendingBatch(
                telegram_id="failed",
                mode=MODE_PROCUREMENT_REPORT,
                files=[("failed.pdf", b"content")],
            )
            bot_module.client_access_error = lambda *_args, **_kwargs: ""
            bot_module.get_or_create_settings = lambda _db: SimpleNamespace()
            bot_module.supplier_target_for_client = lambda *_args, **_kwargs: 10
            bot_module.create_job = lambda *_args, **_kwargs: SimpleNamespace(id="failed-job")
            bot_module._reserve_created_job = lambda *_args, **_kwargs: "Недостаточно средств"
            bot_module._discard_unlaunched_jobs = lambda *_args, **_kwargs: None
            await bot_module.run_batch_button(failed)
        finally:
            bot_module._record_telegram_terms_acceptance = original_recorder
            bot_module._record_telegram_event = original_event
            bot_module.SessionLocal = original_session
            bot_module.get_or_create_trial_client_by_telegram_id = original_get_client
            bot_module.client_access_error = original_access
            bot_module.get_or_create_settings = original_settings
            bot_module.supplier_target_for_client = original_target
            bot_module.create_job = original_create
            bot_module._reserve_created_job = original_reserve
            bot_module._discard_unlaunched_jobs = original_discard
            bot_module.PENDING_UPLOADS.clear()
            bot_module.PENDING_UPLOADS.update(saved_uploads)
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.update(saved_running)

        self.assertEqual(recorded, [])

    def test_onboarding_reminder_leads_with_trial_and_supplier_scenario(self) -> None:
        text = bot_module.ONBOARDING_REMINDER_TEXT

        self.assertIn("открыт пробный доступ", text)
        self.assertIn("🔎 Поставщики по ТЗ", text)
        self.assertIn("🚀 Создать", text)
        self.assertIn("https://tenderlex.ru", text)
        self.assertIn("📞 Контакты", text)
        self.assertNotIn("http://tenderlex.ru", text)

    async def test_telemetry_failure_does_not_break_create_or_mode_buttons(self) -> None:
        originals = {
            "SessionLocal": bot_module.SessionLocal,
            "get_client_by_telegram_id": bot_module.get_client_by_telegram_id,
        }
        pending_modes = dict(bot_module.PENDING_MODES)
        pending_policies = dict(bot_module.PENDING_SUPPLIER_POLICIES)
        running_chats = set(bot_module.BATCH_RUNNING_CHATS)
        try:
            bot_module.SessionLocal = self.FakeDb
            bot_module.get_client_by_telegram_id = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("telemetry unavailable"))
            bot_module.PENDING_MODES.clear()
            bot_module.PENDING_SUPPLIER_POLICIES.clear()
            bot_module.BATCH_RUNNING_CHATS.clear()

            cases = [
                (bot_module.create_button, 1, "Выберите сценарий"),
                (bot_module.supplier_mode, 1, "Поставщики по ТЗ"),
                (bot_module.report_mode, 1, "Анализ закупки"),
                (bot_module.analysis_and_suppliers_button, 1, "Анализ + поиск"),
            ]
            for index, (handler, answer_count, expected_text) in enumerate(cases):
                message = self.FakeMessage(chat_id=991 + index)
                await handler(message)
                self.assertEqual(len(message.answers), answer_count)
                self.assertTrue(any(expected_text in answer[0] for answer in message.answers))
        finally:
            for name, value in originals.items():
                setattr(bot_module, name, value)
            bot_module.PENDING_MODES.clear()
            bot_module.PENDING_MODES.update(pending_modes)
            bot_module.PENDING_SUPPLIER_POLICIES.clear()
            bot_module.PENDING_SUPPLIER_POLICIES.update(pending_policies)
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.update(running_chats)

    async def test_unhandled_error_handler_never_leaves_message_without_feedback(self) -> None:
        message = self.FakeMessage()
        event = SimpleNamespace(
            exception=RuntimeError("unexpected"),
            update=SimpleNamespace(message=message, callback_query=None),
        )

        handled = await bot_module.unhandled_bot_error(event)

        self.assertTrue(handled)
        self.assertEqual(len(message.answers), 1)
        self.assertIn("Не удалось выполнить действие", message.answers[0][0])

    async def test_switching_scenario_clears_only_incompatible_materials(self) -> None:
        chat_id = 991
        original_uploads = dict(bot_module.PENDING_UPLOADS)
        original_modes = dict(bot_module.PENDING_MODES)
        original_policies = dict(bot_module.PENDING_SUPPLIER_POLICIES)
        try:
            bot_module.PENDING_UPLOADS.clear()
            bot_module.PENDING_MODES.clear()
            bot_module.PENDING_SUPPLIER_POLICIES.clear()
            bot_module.PENDING_UPLOADS[chat_id] = bot_module.PendingBatch(
                telegram_id="123",
                mode=MODE_SUPPLIER_SEARCH,
                files=[("tz.txt", b"one")],
            )

            self.assertFalse(bot_module._select_scenario(chat_id, bot_module.SCENARIO_SUPPLIERS))
            self.assertIn(chat_id, bot_module.PENDING_UPLOADS)
            self.assertTrue(bot_module._select_scenario(chat_id, bot_module.SCENARIO_REPORT))
            self.assertNotIn(chat_id, bot_module.PENDING_UPLOADS)
            self.assertNotIn(chat_id, bot_module.PENDING_SUPPLIER_POLICIES)
        finally:
            bot_module.PENDING_UPLOADS.clear()
            bot_module.PENDING_UPLOADS.update(original_uploads)
            bot_module.PENDING_MODES.clear()
            bot_module.PENDING_MODES.update(original_modes)
            bot_module.PENDING_SUPPLIER_POLICIES.clear()
            bot_module.PENDING_SUPPLIER_POLICIES.update(original_policies)

    async def test_menu_clear_removes_all_pending_state(self) -> None:
        message = self.FakeMessage()
        chat_id = message.chat.id
        originals = (dict(bot_module.PENDING_UPLOADS), dict(bot_module.PENDING_MODES), dict(bot_module.PENDING_SUPPLIER_POLICIES))
        try:
            bot_module.PENDING_UPLOADS[chat_id] = bot_module.PendingBatch("123", MODE_SUPPLIER_SEARCH, [("tz.txt", b"one")])
            bot_module.PENDING_MODES[chat_id] = bot_module.SCENARIO_SUPPLIERS
            bot_module.PENDING_SUPPLIER_POLICIES[chat_id] = bot_module.SUPPLIER_POLICY_MINPROM_ONLY
            await bot_module.back_main_button(message)
            self.assertNotIn(chat_id, bot_module.PENDING_UPLOADS)
            self.assertNotIn(chat_id, bot_module.PENDING_MODES)
            self.assertNotIn(chat_id, bot_module.PENDING_SUPPLIER_POLICIES)
        finally:
            for state, saved in zip(
                (bot_module.PENDING_UPLOADS, bot_module.PENDING_MODES, bot_module.PENDING_SUPPLIER_POLICIES), originals
            ):
                state.clear()
                state.update(saved)

    async def test_unsupported_and_group_messages_receive_feedback(self) -> None:
        unsupported = self.FakeMessage(chat_id=992)
        group = self.FakeMessage(chat_id=-100123)

        await bot_module.unsupported_message(unsupported)
        await bot_module.reject_group_message(group)

        self.assertIn("не поддерживается", unsupported.answers[0][0])
        self.assertIn("только в личном чате", group.answers[0][0])


if __name__ == "__main__":
    unittest.main()
