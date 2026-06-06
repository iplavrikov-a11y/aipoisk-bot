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
    extract_national_regime_requirement_types,
    generate_procurement_report,
    normalize_national_regime_conditions,
    normalize_procurement_report_guardrails,
    normalize_vat_usn_risk,
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
            "официального источника",
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
            "Не добавляй в пользовательский отчёт служебные маркеры файлов",
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

    def test_national_regime_prompt_requires_direct_registry_answer(self) -> None:
        for phrase in (
            "Требуются ли выписки из реестра Минпромторга: **Да/Нет/Не указано**",
            "при `ПРЕИМУЩЕСТВЕ` выписки НЕ ТРЕБУЮТСЯ",
            "при `ОГРАНИЧЕНИИ` выписки НЕ ТРЕБУЮТСЯ",
            "при действующем `ЗАПРЕТЕ` выписки ТРЕБУЮТСЯ",
            "ЗАПРЕЩЕНО писать \"если применимо\"",
            "сумма оплаты не увеличивается",
            "уменьшить цену договора/оплату на сумму НДС",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DEFAULT_REPORT_SYSTEM_PROMPT + DEFAULT_VERIFICATION_PROMPT)


class ProcurementReportGuardrailTests(unittest.TestCase):
    def test_extracts_marked_223_advantage_from_notice_form(self) -> None:
        source_text = """Информация о запрете или об ограничении закупок товаров, о преимуществе в отношении товаров российского происхождения
Указывается мера, установленная Правительством РФ:

запрет закупок товаров
-

ограничение закупок товаров
-

преимущество в отношении товаров российского происхождения
установлено
"""

        self.assertEqual(extract_national_regime_requirement_types(source_text), {"advantage"})

    def test_extract_ignores_generic_application_form_measure_descriptions(self) -> None:
        source_text = """2. Предоставление национального режима при осуществлении закупок
1) если извещением установлен запрет закупок товара, не допускаются:
б) при исполнении договора замена такого товара на иностранный товар, в отношении которого установлен данный запрет;
2) если извещением установлено ограничение закупок товара, не допускаются:
б) при исполнении договора замена товара на иностранный товар, в отношении которого установлено данное ограничение;
3) если извещением установлено преимущество в отношении товара российского происхождения:
а) при рассмотрении заявок осуществляется снижение на пятнадцать процентов ценового предложения.
"""

        self.assertEqual(extract_national_regime_requirement_types(source_text), set())

    def test_normalizes_advantage_registry_contradiction(self) -> None:
        report = """#### Условия закупки
- Обеспечение заявки: Не установлено
- Нацрежим: Установлено преимущество в отношении товаров российского происхождения. Требуется подтверждение страны происхождения (реестровые записи, если применимо).
- ГОЗ/сопровождение: Не предусмотрено
"""
        source_text = """Информация о запрете или об ограничении закупок товаров, о преимуществе в отношении товаров российского происхождения
запрет закупок товаров
-
ограничение закупок товаров
-
преимущество в отношении товаров российского происхождения
установлено
"""

        result = normalize_national_regime_conditions(report, source_text)

        self.assertIn("Нацрежим: **Установлено преимущество в отношении товаров российского происхождения.**", result)
        self.assertIn("Требуются ли выписки из реестра Минпромторга: **Нет**", result)
        self.assertNotIn("если применимо", result)
        self.assertNotIn("Требуется подтверждение страны происхождения", result)

    def test_normalizes_restriction_registry_answer_to_no(self) -> None:
        report = """#### Условия закупки
- Нацрежим: **Есть (ПП РФ № 1875). Запрет действует.**
- Требуются ли выписки из реестра Минпромторга: **Да**
"""
        source_text = """На основании ПП РФ № 1875 при осуществлении данной закупки установлено:
- ограничение закупок товаров, происходящих из иностранных государств
"""

        result = normalize_national_regime_conditions(report, source_text)

        self.assertIn("Нацрежим: **Действует ограничение закупок товаров.**", result)
        self.assertIn("Требуются ли выписки из реестра Минпромторга: **Нет**", result)
        self.assertNotIn("Запрет действует", result)
        self.assertNotIn("Требуются ли выписки из реестра Минпромторга: **Да**", result)

    def test_normalizes_prohibition_registry_answer_to_yes(self) -> None:
        report = """#### Условия закупки
- Нацрежим: Не указано
- Требуются ли выписки из реестра Минпромторга: **Нет**
"""
        source_text = """Применение национального режима по ст. 14 Закона № 44-ФЗ
Объект закупки
Вид требований
Обоснование невозможности соблюдения запрета, ограничения
25.11.23.120 Металлоконструкции
Запрет закупок товаров, происходящих из иностранных государств
"""

        result = normalize_national_regime_conditions(report, source_text)

        self.assertIn("Нацрежим: **Действует запрет закупок товаров.**", result)
        self.assertIn("Требуются ли выписки из реестра Минпромторга: **Да**", result)

    def test_normalizes_vat_usn_bad_increase_wording(self) -> None:
        report = """#### Финансы и НДС
- НДС: Включен в НМЦК. Формулировка: "в том числе НДС или без НДС, если Поставщик не является его плательщиком". Риск для УСН: цена договора твердая, при отсутствии НДС у поставщика сумма оплаты не увеличивается.
"""
        source_text = """Цена договора является твердой.
Цена договора составляет, в том числе НДС или без НДС, если Поставщик не является его плательщиком.
"""

        result = normalize_vat_usn_risk(report, source_text)

        self.assertNotIn("сумма оплаты не увеличивается", result)
        self.assertIn("рисков уменьшения цены/оплаты на сумму НДС", result)


class ProcurementReportOfficialSourceContractTests(unittest.IsolatedAsyncioTestCase):
    def test_tenderplan_context_is_treated_as_official_card_facts(self) -> None:
        source_text = """=== ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ ПО НОМЕРУ ИЗВЕЩЕНИЯ (0371100005626000040) ===
Карточка закупки:
- Способ осуществления закупки: Электронный аукцион

Сроки закупки (МСК):
- Дата и время окончания срока подачи заявок (МСК): 10.06.2026 10:00 МСК
- Дата подведения итогов (МСК): 11.06.2026 13:00 МСК
"""

        self.assertEqual(
            extract_official_card_facts(source_text),
            {
                "procurement_method": "Электронный аукцион",
                "submission_deadline": "10.06.2026 10:00 МСК",
                "results_date": "11.06.2026 13:00 МСК",
            },
        )

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
            "карточечного поля официального источника/ЕИС/электронной площадки",
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

    def test_tenderplan_numeric_method_does_not_override_notice_method(self) -> None:
        document_text = """=== ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ ПО НОМЕРУ ИЗВЕЩЕНИЯ (32616063169) ===
Карточка закупки:
- Способ осуществления закупки: 22
Сроки закупки (МСК):
- Дата и время окончания срока подачи заявок (МСК): 09.06.2026 06:00 МСК
- Дата подведения итогов (МСК): 09.06.2026 20:59 МСК

=== FILE: Извещение о проведении запроса котировок ЭТ.docx ===
Способ закупки: запрос котировок в электронной форме.
Место и дата рассмотрения, оценки и подведения итогов запроса котировок | 644033, г. Омск, ул. Красный Путь, 84. «09» июня 2026 года до 07:00 (время московское).
"""

        self.assertEqual(
            extract_official_card_facts(document_text),
            {
                "procurement_method": "Запрос котировок в электронной форме",
                "submission_deadline": "09.06.2026 06:00 МСК",
                "results_date": "09.06.2026 07:00 МСК",
            },
        )

    def test_guardrails_repair_method_results_logistics_and_freshness(self) -> None:
        source_text = """=== ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ ПО НОМЕРУ ИЗВЕЩЕНИЯ (32616063169) ===
- Способ осуществления закупки: 22
- Дата подведения итогов (МСК): 09.06.2026 20:59 МСК
Способ закупки: запрос котировок в электронной форме.
Место и дата рассмотрения, оценки и подведения итогов запроса котировок | «09» июня 2026 года до 07:00 (время московское).
Канат стальной оцинкованный диам.-7,4 мм ГОСТ 3062-80 10,00 км.
Поставляемый Товар должен быть новым, произведенным не ранее 2025г.
"""
        report = """#### Общая информация
- Способ закупки: 22
- Дата рассмотрения/подведения итогов: 09.06.2026 20:59 МСК

#### Логистика (Оценка)
- Общий вес/объем: ДАННЫХ НЕДОСТАТОЧНО (требуется расчет массы 10 км стального каната 7,4 мм по ГОСТ 3062-80).
- Транспорт: Стандартный грузовой транспорт.

#### Критичные требования к товару
- Дата производства: Не ранее 2025 г. Товар должен быть новым.
- Сертификаты: **паспорт** ().
"""

        result = normalize_procurement_report_guardrails(report, source_text)

        self.assertIn("- Способ закупки: Запрос котировок в электронной форме", result)
        self.assertIn("- Дата рассмотрения/подведения итогов: 09.06.2026 07:00 МСК", result)
        self.assertIn("ориентировочно", result.lower())
        self.assertIn("~2 800 кг", result)
        self.assertNotIn("ДАННЫХ НЕДОСТАТОЧНО", result)
        self.assertIn("- Дата производства: Не ранее 2025 г.", result)
        self.assertNotIn("Товар должен быть новым", result)
        self.assertNotIn("()", result)

    def test_guardrails_hide_raw_boolean_artifacts(self) -> None:
        report = """#### Риски
- Противоречие в документах: В карточке ЕИС признак СМП/СОНО отключен (False), но есть файл СМП.
- СМП/СОНО: False
"""

        result = normalize_procurement_report_guardrails(report, "")

        self.assertIn("признак СМП/СОНО не установлен", result)
        self.assertIn("- СМП/СОНО: не установлено", result)
        self.assertNotIn("False", result)
        self.assertNotIn("(False)", result)


if __name__ == "__main__":
    unittest.main()
