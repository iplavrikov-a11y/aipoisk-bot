from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.bot import (
    BUTTON_ANALYSIS_AND_SUPPLIERS,
    BUTTON_CANCEL_BATCH,
    BUTTON_REPORT,
    BUTTON_RUN_BATCH,
    BUTTON_SUPPLIERS_MULTI,
    BUTTON_SUPPLIERS_SINGLE,
    JobProgressSnapshot,
    PendingBatch,
    _add_pending_sources,
    _format_job_progress,
    _job_eta_text,
    _job_mode_for_scenario,
    _mode_label,
    _pending_input_count,
    _progress_bar,
    _scenario_accepts_source_links,
    _source_link_rejection_text,
    _source_payloads_for_scenario,
    _status_label,
    _batch_running_text,
    _pending_added_text,
    _supplier_multi_intro_text,
    _supplier_multi_job_specs,
)
from app.jobs import MODE_ANALYSIS_AND_SUPPLIERS, MODE_PROCUREMENT_REPORT, MODE_SUPPLIER_SEARCH


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
        self.assertIn("Сейчас: ищу сайты компаний", text)
        self.assertIn("Прошло: 10 мин", text)
        self.assertIn("Ориентир: около", text)

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

    def test_customer_buttons_use_procurement_language(self) -> None:
        labels = [
            BUTTON_SUPPLIERS_SINGLE,
            BUTTON_SUPPLIERS_MULTI,
            BUTTON_REPORT,
            BUTTON_ANALYSIS_AND_SUPPLIERS,
            BUTTON_RUN_BATCH,
            BUTTON_CANCEL_BATCH,
        ]
        joined = " ".join(labels)

        self.assertIn("Поставщики по одному ТЗ", joined)
        self.assertIn("Поставщики по нескольким ТЗ", joined)
        self.assertIn("Анализ документации", joined)
        self.assertIn("Анализ + поставщики", joined)
        self.assertNotIn("Word", joined)
        self.assertNotIn("пач", joined.lower())

    def test_supplier_multi_intro_explains_mass_processing_contract(self) -> None:
        text = _supplier_multi_intro_text()

        self.assertIn("Каждый файл считается отдельным ТЗ", text)
        self.assertIn("отдельный Excel-файл", text)
        self.assertIn("Дождитесь сообщений", text)
        self.assertIn("Запустить обработку", text)

    def test_supplier_multi_added_text_explains_next_step(self) -> None:
        pending = PendingBatch(
            telegram_id="123",
            mode=MODE_SUPPLIER_SEARCH,
            files=[("one.docx", b"1"), ("two.docx", b"2")],
        )

        text = _pending_added_text(pending, max_files=20)

        self.assertIn("ТЗ добавлено: 2/20", text)
        self.assertIn("Можно отправить ещё ТЗ", text)
        self.assertIn("нажать «Запустить обработку»", text)
        self.assertIn("по каждому ТЗ будет отдельный Excel-файл", text)

    def test_batch_running_text_hides_add_document_buttons_intent(self) -> None:
        text = _batch_running_text()

        self.assertIn("Обработка уже запущена", text)
        self.assertIn("Кнопки добавления документов временно скрыты", text)
        self.assertIn("пришлю файлы", text)

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
        self.assertFalse(_scenario_accepts_source_links("suppliers_single"))
        self.assertFalse(_scenario_accepts_source_links("suppliers_multi"))
        self.assertTrue(_scenario_accepts_source_links("report"))
        self.assertTrue(_scenario_accepts_source_links("analysis_and_suppliers"))

        text = _source_link_rejection_text()

        self.assertIn("файл ТЗ", text)
        self.assertIn("Анализ документации", text)
        self.assertIn("Анализ + поставщики", text)

    def test_document_caption_source_link_is_captured_only_for_analysis(self) -> None:
        caption = "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0317400001026000049"

        report_sources = _source_payloads_for_scenario("report", caption)
        supplier_sources = _source_payloads_for_scenario("suppliers_single", caption)

        self.assertEqual(len(report_sources), 1)
        self.assertEqual(report_sources[0]["value"], caption)
        self.assertEqual(supplier_sources, [])

    def test_add_pending_sources_deduplicates_caption_and_text_links(self) -> None:
        pending = PendingBatch(telegram_id="123", mode=MODE_PROCUREMENT_REPORT, files=[])
        sources = [
            {"kind": "official_eis", "value": "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=123"},
            {"kind": "official_eis", "value": "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=123"},
        ]

        added = _add_pending_sources(pending, sources)

        self.assertEqual(added, 1)
        self.assertEqual(_pending_input_count(pending), 1)

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


if __name__ == "__main__":
    unittest.main()
