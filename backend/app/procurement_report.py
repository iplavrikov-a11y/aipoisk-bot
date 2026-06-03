from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from .ai import call_llm, get_model_selection, parse_json_object
from .models import SystemSettings, parse_json_dict

DEFAULT_REPORT_SYSTEM_PROMPT = """Ты — Макс, экспертный тендерный аналитик.
Работай строго по документам закупки. Не придумывай факты, поставщиков, цены, URL или нормативные требования.
ATI и внешние логистические ставки отключены: не рассчитывай ATI, не пиши тарифы перевозчиков и не делай вид, что был внешний логистический запрос.
Если в исходном контексте есть блок по ссылке на закупку, ЕИС или иной электронной площадке, используй его как опубликованный источник карточечных данных: номер закупки, заказчик, НМЦК, сроки, площадка, правовой режим. Товарную таблицу бери из наиболее полного ТЗ/ООЗ: если ссылка содержит структурированное ТЗ с характеристиками, используй его; если нет — используй приложенные документы.
Для официального источника ЕИС или электронной площадки копируй карточечные поля буквально: "Способ осуществления закупки", дату/время окончания подачи заявок, дату подведения итогов, НМЦК, заказчика, ИНН/КПП и площадку. Не заменяй "Иной способ" на запрос котировок, аукцион, конкурс или другую процедуру без прямой такой формулировки в карточке. Не добавляй время к дате подведения итогов, если в источнике указана только дата без времени. Если время указано по местному времени заказчика, так и пиши; не пересчитывай его в другой часовой пояс без явной необходимости и пояснения.

Сформируй подробный Markdown-отчет в структуре EmailAgent. Отчет должен быть практичным для закупщика:

#### Общая информация
- Заказчик
- ИНН/КПП
- Номер закупки ЕИС/извещения
- НМЦК/цена с НДС и без НДС, если есть в документах
- Правовой режим: 44-ФЗ, 223-ФЗ или коммерческая закупка, если можно определить
- Способ закупки
- Электронная площадка
- Дата публикации
- Крайний срок подачи заявок с временем
- Дата рассмотрения/подведения итогов
- Город и полный адрес поставки, если есть

#### Условия закупки
- Обеспечение заявки
- Обеспечение исполнения договора/контракта
- Нацрежим с практическим выводом, требуются ли реестровые записи/выписки
- ГОЗ/сопровождение

#### Исполнение
- Срок поставки/выполнения: не путай со сроком действия договора
- Режим поставки: единоразово, партиями по графику или по заявкам
- Место поставки с полным адресом, если он есть

#### Финансы и НДС
- Аванс
- Оплата
- Обеспечение исполнения контракта
- НДС:
  - для 44-ФЗ: коротко "44-ФЗ, рисков НДС нет";
  - для 223-ФЗ/коммерческой закупки: включен ли НДС, короткая цитата формулировки из документа, риск для УСН.

### Товары и требования (Техническое задание)
Обязательная Markdown-таблица:
| № | Наименование | Характеристики | Ед.изм. | Кол-во |
|---|---|---|---|---|
Выведи все позиции из исходного ТЗ/ООЗ/спецификации. Не объединяй разные товары, размеры, цвета, сроки или партии.
Не пиши "см. спецификацию", "уточняется" или "не указано", если в документах есть таблица с данными.
Копируй товарные характеристики, единицы и количества из наиболее авторитетной таблицы: ТЗ/ООЗ с характеристиками важнее проекта договора, формы спецификации и НМЦ.
Не добавляй ОКПД2/КТРУ в таблицу как характеристики товара.
Не добавляй документы, паспорта, сертификаты, гарантию или организационные обязанности отдельными строками таблицы ТЗ, если в исходной товарной спецификации они не указаны как отдельные поставляемые позиции.

#### Логистика (Оценка)
Только оценка по документам без ATI и без ставок перевозчиков: общий вес, объем, транспорт, режим поставки, разгрузка/спецтехника, пронос/заезд, примечание.

#### Критичные требования к товару
- Дата производства
- Срок годности
- Упаковка/тара/маркировка
- Сертификаты/паспорта/регистры
- Гарантия, если она относится к товару

#### Коммерческие условия
- Штрафы/пени
- Гарантийные удержания
- Комиссии/стоимость участия, только если есть в документах

#### Что уточнить
- У заказчика
- У поставщика
- У логиста/водителя

#### Риски
#### Рекомендации
#### Рыночная разведка (OSINT)
- Если внешний web-поиск поставщиков не выполнялся, не указывай конкретных поставщиков, бренды, URL, контакты или рыночные цены.
- В этом случае укажи только товарную категорию, типы релевантных производителей/дилеров и что проверить при отдельном поиске поставщиков.

Правила:
- Начинай сразу с первого раздела, без вступления.
- Обязательные разделы не пропускай. Если данных нет, пиши "Не найдено" или "ДАННЫХ НЕДОСТАТОЧНО".
- Критичные характеристики и цифры выделяй жирным.
- Сохраняй Markdown-таблицы, списки и короткие практические формулировки.
- В OSINT не придумывай URL, контакты, конкретных поставщиков, бренды или цены. Если внешняя разведка не выполнялась, дай только товарную категорию, типы производителей/дилеров и что проверить при поиске.
- Не рекомендуй ГОСТ, ТУ, ТР ТС, реестры или иные нормативные требования, если они прямо не указаны в исходной документации.
- Все даты указывай конкретно, с годом и временем, если время найдено.
- Любая дата в отчете должна быть прямо найдена в документах. Если срок поставки определяется графиком, а график без даты или отсутствует, так и пиши; не подставляй дату из срока действия договора, календаря или предположения.
"""

DEFAULT_REPORT_USER_TEMPLATE = """Анализируй закупочную документацию на дату {current_date}.
Все даты до {current_date} — прошлое, даты после — будущее.

Документы:
{document_text}

Сформируй отчет в заданной структуре."""

DEFAULT_VERIFICATION_PROMPT = """Проверь отчет против исходных документов.
Ищи только критические дефекты:
- пропущены явные позиции ТЗ;
- не скопированы количества/единицы, хотя они есть в исходнике;
- есть выдуманные факты, URL, поставщики, цены или ATI-ставки;
- отсутствуют обязательные разделы EmailAgent:
  Общая информация, Условия закупки, Исполнение, Финансы и НДС, Товары и требования, Логистика, Критичные требования к товару, Коммерческие условия, Что уточнить, Риски, Рекомендации, Рыночная разведка (OSINT);
- раздел "Товары и требования" не содержит Markdown-таблицу с колонками №, Наименование, Характеристики, Ед.изм., Кол-во;
- таблица ТЗ содержит документы, паспорта, сертификаты, гарантию или организационные обязанности как отдельные товарные позиции без прямого указания в исходной товарной спецификации;
- в исходнике есть НМЦК/цена, правовой режим, площадка, срок подачи заявок или дата итогов, но эти поля не отражены в отчете;
- отчет изменил буквальное значение официального карточечного поля ЕИС/электронной площадки: "Способ осуществления закупки", заказчик, ИНН/КПП, НМЦК, площадка, срок подачи заявок или дата итогов;
- отчет нормализовал "Иной способ" в запрос котировок, аукцион, конкурс или другую процедуру без прямой такой формулировки в официальном источнике;
- отчет добавил время к дате подведения итогов, если в официальном источнике указана только дата без времени;
- отчет пересчитал местное время заказчика в другой часовой пояс без явного пояснения и без сохранения исходного времени;
- срок поставки перепутан со сроком действия договора;
- отчет содержит дату, которой нет в исходных документах, или подставляет конкретную дату вместо отсутствующего графика поставки;
- отчет рекомендует ГОСТ, ТУ, ТР ТС, реестры или иные нормативные требования, которых нет в исходных документах.

Важное правило OSINT:
- НЕ считай ошибкой, что в OSINT нет конкретных поставщиков, URL, контактов или рыночных цен, если внешний web-поиск не выполнялся.
- Считай ошибкой, если отчет выдумывает конкретных поставщиков, бренды, URL, контакты или цены без источника в документах.

Ответ JSON:
{
  "ok": true,
  "issues": [],
  "corrected_report": ""
}

Если исправления нужны, верни полный corrected_report со всеми обязательными разделами.
В corrected_report обязательно сохрани Markdown-таблицу ТЗ; запрещено заменять ее кратким списком позиций.
Не добавляй в пользовательский отчет служебные маркеры файлов вида [001_Извещение.docx] или [003_...].
Если отчет приемлем, corrected_report оставь пустым."""

DEFAULT_OFFICIAL_CARD_REPAIR_PROMPT = """Исправь отчет по официальной карточке закупки.
Это не творческая редактура: нужно исправить только перечисленные расхождения по карточечным полям официального источника.
Для полей "Способ закупки", срок подачи заявок и дата подведения итогов копируй значения официального источника буквально.
Если в официальном источнике указана только дата без времени, не добавляй время.
Верни полный Markdown-отчет без служебных комментариев."""

OFFICIAL_CARD_FIELD_LABELS = {
    "procurement_method": "Способ осуществления закупки",
    "submission_deadline": "Дата и время окончания срока подачи заявок (по местному времени заказчика)",
    "results_date": "Дата подведения итогов",
}

REPORT_FIELD_ALIASES = {
    "procurement_method": ("Способ закупки", "Способ осуществления закупки"),
    "submission_deadline": (
        "Крайний срок подачи заявок",
        "Дата и время окончания срока подачи заявок",
        "Окончание подачи заявок",
    ),
    "results_date": (
        "Дата рассмотрения/подведения итогов",
        "Дата подведения итогов",
        "Дата рассмотрения",
    ),
}


@dataclass(frozen=True)
class ReportGenerationResult:
    report: str
    ai_used: bool
    ai_model: str = ""
    warning: str = ""
    verification: dict | None = None


class ProcurementReportAIRequiredError(RuntimeError):
    """Raised when an AI-required procurement report cannot be generated safely."""


async def generate_procurement_report(settings: SystemSettings, document_text: str) -> ReportGenerationResult:
    if not settings.has_active_ai_provider:
        raise ProcurementReportAIRequiredError("AI provider is required for procurement documentation analysis")

    prompt_settings = parse_json_dict(settings.prompt_settings_json)
    report_settings = parse_json_dict(settings.report_settings_json)
    max_chars = int(report_settings.get("analysis_max_chars") or 800000)
    current_date = dt.datetime.now(dt.timezone.utc).strftime("%d.%m.%Y")
    user_template = str(
        prompt_settings.get("procurement_report_user_template")
        or DEFAULT_REPORT_USER_TEMPLATE
    )
    system_prompt = str(
        prompt_settings.get("procurement_report_system_prompt")
        or DEFAULT_REPORT_SYSTEM_PROMPT
    )
    user_prompt = user_template.format_map(
        _SafeFormatDict(
            current_date=current_date,
            document_text=document_text[:max_chars],
        )
    )
    ai_model = ""
    try:
        selection = get_model_selection(settings, tier="primary", routing_key="procurement_document_analysis")
        ai_model = f"{selection.provider_name} | {selection.model}"
    except Exception as exc:
        raise ProcurementReportAIRequiredError(f"AI model selection failed: {exc}") from exc
    try:
        raw = await call_llm(
            settings,
            user_prompt,
            system_prompt=system_prompt,
            tier="primary",
            routing_key="procurement_document_analysis",
            timeout_seconds=float(report_settings.get("analysis_timeout_seconds") or 240),
        )
    except Exception as exc:
        raise ProcurementReportAIRequiredError(f"AI report generation failed: {exc}") from exc

    report = clean_markdown_report(raw)
    if not report:
        raise ProcurementReportAIRequiredError("AI report generation returned an empty report")
    verification: dict | None = None
    if report_settings.get("verify_report", True):
        verification = await verify_report(settings, report, document_text, report_settings)
        corrected = clean_markdown_report(str(verification.get("corrected_report") or ""))
        if corrected and not verification.get("ok"):
            report = corrected
        elif not verification.get("ok"):
            issues = verification.get("issues") or ["AI verification rejected the report"]
            raise ProcurementReportAIRequiredError(f"AI report verification failed: {issues}")
    official_facts = extract_official_card_facts(document_text)
    official_issues = validate_report_against_official_card(report, official_facts)
    if official_issues:
        report = await repair_report_official_card_fields(settings, report, document_text, official_issues, report_settings)
        official_issues = validate_report_against_official_card(report, official_facts)
        if official_issues:
            raise ProcurementReportAIRequiredError(f"Official source card validation failed: {official_issues}")
    if verification is not None:
        verification["official_card_validation"] = {
            "ok": not official_issues,
            "issues": official_issues,
            "facts": official_facts,
        }
    return ReportGenerationResult(report=report, ai_used=True, ai_model=ai_model, verification=verification)


async def verify_report(
    settings: SystemSettings,
    report: str,
    document_text: str,
    report_settings: dict,
) -> dict:
    prompt = str(report_settings.get("verification_prompt") or DEFAULT_VERIFICATION_PROMPT)
    user_prompt = f"ИСХОДНЫЕ ДОКУМЕНТЫ:\n{document_text[:250000]}\n\nОТЧЕТ:\n{report[:120000]}"
    try:
        raw = await call_llm(
            settings,
            user_prompt,
            system_prompt=prompt,
            tier="primary",
            routing_key="procurement_report_verification",
            json_mode=True,
            timeout_seconds=float(report_settings.get("verification_timeout_seconds") or 180),
        )
        parsed = parse_json_object(raw)
        return parsed if parsed else {"ok": False, "issues": ["empty_verification_response"]}
    except Exception as exc:
        return {"ok": False, "issues": [f"verification_failed: {exc}"]}


async def repair_report_official_card_fields(
    settings: SystemSettings,
    report: str,
    document_text: str,
    issues: list[str],
    report_settings: dict,
) -> str:
    official_facts = extract_official_card_facts(document_text)
    prompt = str(report_settings.get("official_card_repair_prompt") or DEFAULT_OFFICIAL_CARD_REPAIR_PROMPT)
    user_prompt = (
        "ОФИЦИАЛЬНЫЕ КАРТОЧНЫЕ ФАКТЫ:\n"
        f"{official_facts}\n\n"
        "РАСХОЖДЕНИЯ, КОТОРЫЕ НУЖНО ИСПРАВИТЬ:\n"
        + "\n".join(f"- {issue}" for issue in issues)
        + "\n\nИСХОДНЫЕ ДОКУМЕНТЫ:\n"
        f"{document_text[:120000]}\n\nОТЧЕТ ДЛЯ ИСПРАВЛЕНИЯ:\n{report[:120000]}"
    )
    try:
        raw = await call_llm(
            settings,
            user_prompt,
            system_prompt=prompt,
            tier="primary",
            routing_key="procurement_report_official_card_repair",
            timeout_seconds=float(report_settings.get("verification_timeout_seconds") or 180),
        )
    except Exception as exc:
        raise ProcurementReportAIRequiredError(f"AI official-card repair failed: {exc}") from exc
    corrected = clean_markdown_report(raw)
    if not corrected:
        raise ProcurementReportAIRequiredError("AI official-card repair returned an empty report")
    return corrected


def extract_official_card_facts(document_text: str) -> dict[str, str]:
    text = str(document_text or "")
    if "ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ" not in text and "ЕИС" not in text:
        return {}
    facts: dict[str, str] = {}
    for key, label in OFFICIAL_CARD_FIELD_LABELS.items():
        value = _extract_following_line(text, label)
        if value:
            facts[key] = value
    return facts


def validate_report_against_official_card(report: str, facts: dict[str, str]) -> list[str]:
    if not facts:
        return []
    issues: list[str] = []
    method = facts.get("procurement_method", "")
    if method:
        report_method = _report_field_value(report, REPORT_FIELD_ALIASES["procurement_method"])
        if not report_method:
            issues.append(f"В отчете нет поля 'Способ закупки', хотя в официальном источнике указано: {method}")
        elif _normalize_fact(report_method) != _normalize_fact(method):
            issues.append(f"Способ закупки должен быть ровно '{method}', в отчете указано: '{report_method}'")

    submission_deadline = facts.get("submission_deadline", "")
    if submission_deadline:
        report_deadline = _report_field_value(report, REPORT_FIELD_ALIASES["submission_deadline"])
        if not report_deadline:
            issues.append(
                "В отчете нет срока подачи заявок, хотя в официальном источнике указано: "
                f"{submission_deadline}"
            )
        elif not _contains_date_and_time_from_source(report_deadline, submission_deadline):
            issues.append(
                "Срок подачи заявок должен сохранять дату и время официального источника "
                f"'{submission_deadline}', в отчете указано: '{report_deadline}'"
            )
        elif "московск" in report_deadline.lower() and "московск" not in submission_deadline.lower():
            issues.append(
                "Срок подачи заявок указан как московское время, хотя официальный источник дает "
                f"местное время заказчика: '{submission_deadline}'"
            )

    results_date = facts.get("results_date", "")
    if results_date:
        report_results = _report_field_value(report, REPORT_FIELD_ALIASES["results_date"])
        if not report_results:
            issues.append(
                "В отчете нет даты подведения итогов, хотя в официальном источнике указано: "
                f"{results_date}"
            )
        elif not _contains_date_from_source(report_results, results_date):
            issues.append(
                "Дата подведения итогов должна сохранять дату официального источника "
                f"'{results_date}', в отчете указано: '{report_results}'"
            )
        elif not _extract_time(results_date) and _extract_time(report_results):
            issues.append(
                "Время подведения итогов нельзя добавлять: официальный источник содержит только дату "
                f"'{results_date}', в отчете указано: '{report_results}'"
            )
    return issues


def clean_markdown_report(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(
        r"(?i)\bATI\b[^\n]*(?:ставк|тариф|расчет)[^\n]*",
        "ATI/внешние логистические ставки: отключены.",
        text,
    )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_following_line(text: str, label: str) -> str:
    pattern = re.compile(rf"(?m)^\s*{re.escape(label)}\s*\n\s*([^\n]+)")
    match = pattern.search(text)
    if not match:
        return ""
    return _clean_inline_text(match.group(1))


def _report_field_value(report: str, aliases: tuple[str, ...]) -> str:
    for line in str(report or "").splitlines():
        clean = _clean_inline_text(line).lstrip("-* ").strip()
        for alias in aliases:
            if clean.lower().startswith(f"{alias.lower()}:"):
                return _clean_inline_text(clean.split(":", 1)[1])
    return ""


def _clean_inline_text(value: str) -> str:
    text = re.sub(r"[*_`]+", "", str(value or ""))
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip(" .")


def _normalize_fact(value: str) -> str:
    text = _clean_inline_text(value).lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .")


def _extract_date(value: str) -> str:
    match = re.search(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", str(value or ""))
    return match.group(0) if match else ""


def _extract_time(value: str) -> str:
    match = re.search(r"\b\d{1,2}:\d{2}\b", str(value or ""))
    return match.group(0) if match else ""


def _contains_date_from_source(report_value: str, source_value: str) -> bool:
    date = _extract_date(source_value)
    return bool(date and date in report_value)


def _contains_date_and_time_from_source(report_value: str, source_value: str) -> bool:
    date = _extract_date(source_value)
    time = _extract_time(source_value)
    return bool(date and time and date in report_value and time in report_value)


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ""
