from __future__ import annotations

import unittest
from types import SimpleNamespace

import app.procurement_report as procurement_report
from app.procurement_report import (
    DEFAULT_REPORT_SYSTEM_PROMPT,
    DEFAULT_VERIFICATION_PROMPT,
    ProcurementReportAIRequiredError,
    clean_markdown_report,
    extract_official_card_facts,
    generate_procurement_report,
    validate_report_against_official_card,
)


class ProcurementReportPromptTests(unittest.TestCase):
    def test_report_prompt_requires_emailagent_procurement_fields(self) -> None:
        for phrase in (
            "НМЦК",
            "Правовой режим",
            "Электронная площадка",
            "Крайний срок подачи заявок",
            "Дата рассмотрения/подведения итогов",
            "ссылке на закупку",
            "Что уточнить",
            "Рыночная разведка (OSINT)",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DEFAULT_REPORT_SYSTEM_PROMPT)

    def test_verification_prompt_rejects_missing_emailagent_sections(self) -> None:
        for phrase in (
            "Условия закупки",
            "Финансы и НДС",
            "Критичные требования к товару",
            "Коммерческие условия",
            "Что уточнить",
            "Рыночная разведка (OSINT)",
            "срок поставки перепутан со сроком действия договора",
            "Markdown-таблицу с колонками №, Наименование, Характеристики, Ед.изм., Кол-во",
            "запрещено заменять ее кратким списком позиций",
            "Не добавляй в пользовательский отчет служебные маркеры файлов",
            "документы, паспорта, сертификаты, гарантию или организационные обязанности",
            "дату, которой нет в исходных документах",
            "ГОСТ, ТУ, ТР ТС, реестры",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DEFAULT_VERIFICATION_PROMPT)

    def test_osint_contract_forbids_unsourced_supplier_and_price_invention(self) -> None:
        for phrase in (
            "не указывай конкретных поставщиков",
            "бренды, URL, контакты или рыночные цены",
            "НЕ считай ошибкой, что в OSINT нет конкретных поставщиков",
            "выдумывает конкретных поставщиков, бренды, URL, контакты или цены",
            "Не рекомендуй ГОСТ, ТУ, ТР ТС",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DEFAULT_REPORT_SYSTEM_PROMPT + DEFAULT_VERIFICATION_PROMPT)


class ProcurementReportOfficialSourceContractTests(unittest.IsolatedAsyncioTestCase):
    def test_official_source_prompt_requires_literal_card_fields(self) -> None:
        for phrase in (
            "копируй карточечные поля буквально",
            "Способ осуществления закупки",
            "Не заменяй \"Иной способ\"",
            "Не добавляй время к дате подведения итогов",
            "не пересчитывай его в другой часовой пояс",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DEFAULT_REPORT_SYSTEM_PROMPT)

    def test_verification_prompt_rejects_official_card_field_mismatch(self) -> None:
        for phrase in (
            "изменил буквальное значение официального карточечного поля",
            "нормализовал \"Иной способ\"",
            "добавил время к дате подведения итогов",
            "пересчитал местное время заказчика",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DEFAULT_VERIFICATION_PROMPT)

    async def test_report_generation_requires_ai_provider(self) -> None:
        settings = SimpleNamespace(has_active_ai_provider=False)

        with self.assertRaisesRegex(ProcurementReportAIRequiredError, "AI provider is required"):
            await generate_procurement_report(settings, "Текст закупки")

    async def test_report_generation_fails_when_ai_verification_rejects_without_correction(self) -> None:
        original_call_llm = procurement_report.call_llm
        original_get_model_selection = procurement_report.get_model_selection
        calls: list[str] = []

        async def fake_call_llm(*_args, **kwargs) -> str:
            calls.append(str(kwargs.get("routing_key") or ""))
            if kwargs.get("json_mode"):
                return '{"ok": false, "issues": ["Способ закупки не совпадает"], "corrected_report": ""}'
            return "#### Общая информация\n- Способ закупки: Запрос котировок в электронной форме"

        procurement_report.call_llm = fake_call_llm
        procurement_report.get_model_selection = lambda *_args, **_kwargs: SimpleNamespace(
            provider_name="TestAI",
            model="model",
        )
        try:
            settings = SimpleNamespace(
                has_active_ai_provider=True,
                prompt_settings_json="{}",
                report_settings_json='{"verify_report": true}',
            )

            with self.assertRaisesRegex(ProcurementReportAIRequiredError, "verification failed"):
                await generate_procurement_report(settings, "Способ осуществления закупки\nИной способ")
        finally:
            procurement_report.call_llm = original_call_llm
            procurement_report.get_model_selection = original_get_model_selection

        self.assertEqual(calls, ["procurement_document_analysis", "procurement_report_verification"])

    def test_clean_markdown_report_does_not_build_non_ai_fallback(self) -> None:
        self.assertEqual(clean_markdown_report(""), "")

    def test_official_card_validation_rejects_method_normalization_and_invented_time(self) -> None:
        document_text = """=== ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ: ЕИС ===
Сведения о закупке
Способ осуществления закупки
Иной способ
Дата и время окончания срока подачи заявок (по местному времени заказчика)
09.06.2026 09:00
Дата подведения итогов
09.06.2026
"""
        report = """#### Общая информация
- Способ закупки: Иной способ (запрос котировок в электронной форме)
- Крайний срок подачи заявок: 09.06.2026 до 06:00 (время московское)
- Дата рассмотрения/подведения итогов: 09.06.2026 до 07:00 (время московское)
"""

        facts = extract_official_card_facts(document_text)
        issues = validate_report_against_official_card(report, facts)

        self.assertEqual(
            facts,
            {
                "procurement_method": "Иной способ",
                "submission_deadline": "09.06.2026 09:00",
                "results_date": "09.06.2026",
            },
        )
        self.assertTrue(any("Способ закупки должен быть ровно" in issue for issue in issues))
        self.assertTrue(any("Срок подачи заявок должен сохранять дату и время" in issue for issue in issues))
        self.assertTrue(any("Время подведения итогов нельзя добавлять" in issue for issue in issues))

    def test_official_card_validation_accepts_exact_official_values(self) -> None:
        facts = {
            "procurement_method": "Иной способ",
            "submission_deadline": "09.06.2026 09:00",
            "results_date": "09.06.2026",
        }
        report = """#### Общая информация
- Способ закупки: Иной способ
- Крайний срок подачи заявок: 09.06.2026 09:00 (местное время заказчика)
- Дата рассмотрения/подведения итогов: 09.06.2026
"""

        self.assertEqual(validate_report_against_official_card(report, facts), [])


if __name__ == "__main__":
    unittest.main()
