from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest

import app.bot as bot_module
from app.bot import (
    AI_HELP_NOTE,
    BOT_DESCRIPTION,
    BOT_SHORT_DESCRIPTION,
    BRAND_NAME,
    BUTTON_ANALYSIS_AND_SUPPLIERS,
    BUTTON_ACCESS,
    BUTTON_CANCEL_BATCH,
    BUTTON_CONTACTS,
    BUTTON_CREATE,
    BUTTON_HELP,
    BUTTON_PROCESSING_STATUS,
    BUTTON_REPORT,
    BUTTON_RUN_BATCH,
    BUTTON_STATUS,
    BUTTON_SUPPLIERS,
    BUTTON_TARIFFS,
    JobProgressSnapshot,
    PendingBatch,
    _add_pending_sources,
    _contacts_text,
    _edit_or_send_status,
    _format_job_progress,
    _job_eta_text,
    _job_mode_for_scenario,
    _handle_source_text,
    _handle_supplier_text_tz,
    _looks_like_supplier_text_tz,
    _mode_label,
    _owner_problem_alert_text,
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
    _menu_for_chat,
    _supplier_multi_intro_text,
    _supplier_multi_job_specs,
    _supplier_text_tz_payload,
    _tariffs_text,
    batch_menu,
    configure_bot_profile,
    create_menu,
    main_menu,
    processing_menu,
    watch_job_progress,
)
from app.jobs import MODE_ANALYSIS_AND_SUPPLIERS, MODE_PROCUREMENT_REPORT, MODE_SUPPLIER_SEARCH
from app.models import SystemSettings, TariffPackage


class BotProgressFormattingTests(unittest.TestCase):
    def test_progress_bar_uses_ten_stable_segments(self) -> None:
        self.assertEqual(_progress_bar(0), "⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜")
        self.assertEqual(_progress_bar(37), "🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜")
        self.assertEqual(_progress_bar(100), "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩")

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
        self.assertIn("будет списана генерация", text)
        self.assertIn("только подтверждённые компании", text)
        self.assertNotIn("target", text.lower())

    def test_contacts_text_includes_site_when_configured(self) -> None:
        settings = SystemSettings(
            id=1,
            contact_telegram="@owner",
            contact_email="owner@example.ru",
            contact_website="https://aipoisk.example",
        )

        text = _contacts_text(settings, telegram_id="123")

        self.assertIn("Telegram: @owner", text)
        self.assertIn("Email: owner@example.ru", text)
        self.assertIn("Сайт: https://aipoisk.example", text)
        self.assertIn("Ваш Telegram ID: 123", text)

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
        self.assertIn("После подтверждения оплаты генерации будут начислены вручную", text)
        self.assertIn(AI_HELP_NOTE, text)
        self.assertNotIn("Как купить пакет:\n🧾 Чтобы купить пакет:", text)

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
        keyboard = main_menu().keyboard
        rows = [[button.text for button in row] for row in keyboard]
        labels = [text for row in rows for text in row]

        self.assertEqual(
            rows,
            [
                [BUTTON_CREATE, BUTTON_STATUS],
                [BUTTON_ACCESS, BUTTON_TARIFFS],
                [BUTTON_HELP, BUTTON_CONTACTS],
            ],
        )
        self.assertNotIn("🆔 Мой Telegram ID", labels)
        self.assertNotIn("/start", " ".join(labels))

    def test_create_menu_is_compact_two_column_layout(self) -> None:
        keyboard = create_menu().keyboard
        rows = [[button.text for button in row] for row in keyboard]

        self.assertEqual(
            rows[:2],
            [
                [BUTTON_SUPPLIERS, BUTTON_REPORT],
                [BUTTON_ANALYSIS_AND_SUPPLIERS],
            ],
        )
        self.assertLessEqual(max(len(label) for row in rows for label in row), 20)

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
        keyboard = batch_menu().keyboard
        rows = [[button.text for button in row] for row in keyboard]

        self.assertIn([BUTTON_RUN_BATCH, BUTTON_CANCEL_BATCH], rows)
        self.assertNotIn([BUTTON_SUPPLIERS], rows)
        self.assertNotIn([BUTTON_REPORT], rows)
        self.assertNotIn([BUTTON_ANALYSIS_AND_SUPPLIERS], rows)
        self.assertLessEqual(max(len(label) for row in rows for label in row), 13)

    def test_processing_menu_hides_new_start_actions(self) -> None:
        keyboard = processing_menu().keyboard
        rows = [[button.text for button in row] for row in keyboard]
        labels = [text for row in rows for text in row]

        self.assertIn([BUTTON_PROCESSING_STATUS, BUTTON_STATUS], rows)
        self.assertNotIn(BUTTON_CREATE, labels)
        self.assertNotIn(BUTTON_RUN_BATCH, labels)
        self.assertNotIn(BUTTON_SUPPLIERS, labels)
        self.assertNotIn(BUTTON_REPORT, labels)
        self.assertNotIn(BUTTON_ANALYSIS_AND_SUPPLIERS, labels)

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
            labels = [button.text for row in _menu_for_chat(777).keyboard for button in row]
        finally:
            bot_module.SessionLocal = original_session
            bot_module.BATCH_RUNNING_CHATS.clear()
            bot_module.BATCH_RUNNING_CHATS.update(running_chats)

        self.assertTrue(fake_db.closed)
        self.assertIn(BUTTON_PROCESSING_STATUS, labels)
        self.assertNotIn(BUTTON_CREATE, labels)

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

        self.assertIn("ТЗ файлом или текстом", text)
        self.assertIn("отдельный поиск поставщиков", text)
        self.assertIn("Проверьте количество добавленных ТЗ", text)
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
        self.assertIn(f"нажмите «{BUTTON_RUN_BATCH}»", text)

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
        self.assertIn(BUTTON_RUN_BATCH, text)
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

            async def edit_text(self, value: str):
                raise TelegramBadRequest(method=None, message="Bad Request: message can't be edited")

            async def answer(self, value: str):
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
                self.edits: list[str] = []

            async def edit_text(self, value: str):
                self.edits.append(value)
                return self

            async def answer(self, value: str):
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
        self.assertEqual(len(status_message.edits), 1)
        self.assertIn("анализ документации готов", status_message.edits[-1])

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
        self.assertEqual(message.answers, [])
        self.assertEqual(len(message.documents), 1)
        self.assertIn("Анализ документации во вложении.", message.documents[0].caption)
        self.assertIn("✅ Результат отправлен. Баланс обновлён.", message.documents[0].caption)
        self.assertEqual(len(message.documents[0].edits), 1)
        self.assertIsNotNone(message.documents[0].reply_markup)


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
        rows = [[button.text for button in row] for row in message.answers[0][1].keyboard]
        labels = [text for row in rows for text in row]
        self.assertIn(BUTTON_RUN_BATCH, labels)
        self.assertNotIn(BUTTON_CREATE, labels)


if __name__ == "__main__":
    unittest.main()
