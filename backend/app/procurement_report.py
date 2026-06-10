from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .ai import call_llm, get_model_selection, parse_json_object
from .models import SystemSettings, parse_json_dict

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

DEFAULT_REPORT_SYSTEM_PROMPT = """Ты — Макс, экспертный тендерный аналитик.
Работай строго по документам закупки. Не придумывай факты, поставщиков, цены, URL или нормативные требования.
ATI и внешние логистические ставки отключены: не рассчитывай ATI, не пиши тарифы перевозчиков и не делай вид, что был внешний логистический запрос.
Если в исходном контексте есть блок официального источника закупки по номеру извещения, используй его как основной опубликованный источник карточечных данных: номер закупки, заказчик, НМЦК, сроки, дата аукциона, дата итогов, площадка, правовой режим, нацрежим, разъяснения и ответы заказчика. Даты из этого блока считай московским временем, если блок явно не говорит иное.
Если в исходном контексте есть блок по ссылке на закупку, ЕИС или иной электронной площадке, используй его как опубликованный источник карточечных данных: номер закупки, заказчик, НМЦК, сроки, площадка, правовой режим. Товарную таблицу бери из наиболее полного ТЗ/ООЗ: если официальный источник, ссылка или карточка содержит структурированное ТЗ с характеристиками, используй его; если нет — используй приложенные документы.
Для официального источника по номеру извещения, ЕИС или электронной площадки копируй карточечные поля буквально: "Способ осуществления закупки", дату/время окончания подачи заявок, дату подведения итогов, НМЦК, заказчика, ИНН/КПП и площадку. Не заменяй "Иной способ" на запрос котировок, аукцион, конкурс или другую процедуру без прямой такой формулировки в карточке. Не добавляй время к дате подведения итогов, если в источнике указана только дата без времени. Если время указано по местному времени заказчика или МСК, так и пиши; не пересчитывай его в другой часовой пояс без явной необходимости и пояснения.
Если структурированный источник вернул только числовой код способа закупки (например, 22), не выводи этот код как пользовательский "Способ закупки"; найди человекочитаемый способ в извещении, документации или карточке площадки и укажи его. Если структурированный timestamp по дате итогов расходится с явной строкой извещения "рассмотрение/оценка/подведение итогов", укажи явную строку извещения и при необходимости зафиксируй расхождение в рисках.

Сформируй подробный Markdown-отчёт в структуре EmailAgent. Отчёт должен быть практичным для закупщика:

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
- Нацрежим:
  - укажи вид меры: запрет / ограничение / преимущество / не применяется / не указано;
  - отдельной строкой обязательно напиши: "Требуются ли выписки из реестра Минпромторга: **Да/Нет/Не указано**".
- ГОЗ/сопровождение

Критически важное правило по нацрежиму:
- В ЕИС и документации смотри фактический вид меры: для 44-ФЗ — раздел "Применение национального режима по ст. 14 Закона № 44-ФЗ"; для 223-ФЗ — раздел "Информация о запрете или об ограничении закупок ..., о преимуществе ..." и отмеченную строку "установлено".
- Сначала отличи `ЗАПРЕТ`, `ОГРАНИЧЕНИЕ` и `ПРЕИМУЩЕСТВО`; не делай вывод по одному упоминанию ПП РФ № 1875, Минпромторга или реестровой записи в форме заявки.
- Если запрет/ограничение указаны, но есть обоснование невозможности соблюдения запрета/ограничения, мера фактически не применяется.
- Выписка/реестровая запись Минпромторга как обязательное условие допуска нужна только при действующем `ЗАПРЕТЕ`: при действующем `ЗАПРЕТЕ` выписки ТРЕБУЮТСЯ.
- при `ОГРАНИЧЕНИИ` выписки НЕ ТРЕБУЮТСЯ.
- при `ПРЕИМУЩЕСТВЕ` выписки НЕ ТРЕБУЮТСЯ.
- Если мера фактически не применяется, выписки НЕ ТРЕБУЮТСЯ.
- ЗАПРЕЩЕНО писать "если применимо", "для подтверждения страны происхождения", "для получения преимущества 15%" или похожую неопределенную формулировку вместо прямого ответа Да/Нет.

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
  - Риск для УСН описывай только как риск, что заказчик может уменьшить цену договора/оплату на сумму НДС или удержать НДС при оплате. Если такого условия в документах нет, пиши "Рисков не найдено".
  - ЗАПРЕЩЕНО писать "сумма оплаты не увеличивается": это не практический риск для поставщика.

### Товары и требования (Техническое задание)
Обязательная Markdown-таблица:
| № | Наименование | Характеристики | Ед.изм. | Кол-во |
|---|---|---|---|---|
Выведи все позиции из исходного ТЗ/ООЗ/спецификации. Не объединяй разные товары, размеры, цвета, сроки или партии.
Не пиши "см. спецификацию", "уточняется" или "не указано", если в документах есть таблица с данными.
Копируй товарные характеристики, единицы и количества из наиболее авторитетной таблицы: ТЗ/ООЗ с характеристиками важнее проекта договора, формы спецификации и НМЦ.
Не выводи ОКПД, ОКПД2 или OKPD нигде в пользовательском отчёте: ни в таблице, ни в наименовании, ни в характеристиках, ни в рисках/рекомендациях.
ОКПД не должен попадать в отчёт даже если он есть в исходной карточке или спецификации; просто убери код и оставь название товара/работы/услуги.
Не добавляй КТРУ в таблицу как характеристику товара.
Не добавляй документы, паспорта, сертификаты, гарантию или организационные обязанности отдельными строками таблицы ТЗ, если в исходной товарной спецификации они не указаны как отдельные поставляемые позиции.

#### Логистика (Оценка)
Только оценка по документам без ATI и без ставок перевозчиков: общий вес, объём, транспорт, режим поставки, разгрузка/спецтехника, пронос/заезд, примечание.
Если есть наименование товара, количество, единицы измерения, размеры/диаметр/ГОСТ/материал или другие физические признаки, дай ориентировочную оценку веса и объёма. Не пиши "ДАННЫХ НЕДОСТАТОЧНО" в строке общего веса/объёма при наличии расчётных исходных данных; пиши "ориентировочно", итоговое число/диапазон и что уточнить у поставщика/логиста. Не расписывай длинные формулы в пользовательском отчёте.

#### Критичные требования к товару
- Дата производства
- Срок годности
- Упаковка/тара/маркировка
- Сертификаты/паспорта/регистры
- Гарантия, если она относится к товару
Не подменяй дату производства словами "товар новый", "не Б/У" или похожими базовыми требованиями. Если в документации указан год/период производства, пиши только его, например: "Дата производства: не ранее 2025 г.".

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
- Любая дата в отчёте должна быть прямо найдена в документах. Если срок поставки определяется графиком, а график без даты или отсутствует, так и пиши; не подставляй дату из срока действия договора, календаря или предположения.
"""

DEFAULT_REPORT_USER_TEMPLATE = """Анализируй закупочную документацию на дату {current_date}.
Все даты до {current_date} — прошлое, даты после — будущее.

Документы:
{document_text}

Сформируй отчёт в заданной структуре."""

DEFAULT_VERIFICATION_PROMPT = """Проверь отчёт против исходных документов.
Ищи только критические дефекты:
- пропущены явные позиции ТЗ;
- не скопированы количества/единицы, хотя они есть в исходнике;
- есть выдуманные факты, URL, поставщики, цены или ATI-ставки;
- отсутствуют обязательные разделы EmailAgent:
  Общая информация, Условия закупки, Исполнение, Финансы и НДС, Товары и требования, Логистика, Критичные требования к товару, Коммерческие условия, Что уточнить, Риски, Рекомендации, Рыночная разведка (OSINT);
- раздел "Товары и требования" не содержит Markdown-таблицу с колонками №, Наименование, Характеристики, Ед.изм., Кол-во;
- таблица ТЗ содержит документы, паспорта, сертификаты, гарантию или организационные обязанности как отдельные товарные позиции без прямого указания в исходной товарной спецификации;
- в исходнике есть НМЦК/цена, правовой режим, площадка, срок подачи заявок или дата итогов, но эти поля не отражены в отчёте;
- отчёт изменил буквальное значение карточечного поля официального источника/ЕИС/электронной площадки: "Способ осуществления закупки", заказчик, ИНН/КПП, НМЦК, площадка, срок подачи заявок или дата итогов;
- отчёт нормализовал "Иной способ" в запрос котировок, аукцион, конкурс или другую процедуру без прямой такой формулировки в официальном источнике;
- отчёт добавил время к дате подведения итогов, если в официальном источнике указана только дата без времени;
- отчёт пересчитал местное время заказчика в другой часовой пояс без явного пояснения и без сохранения исходного времени;
- отчёт содержит ОКПД, ОКПД2, OKPD или код ОКПД в любом разделе, таблице, наименовании, характеристиках, рисках или рекомендациях;
- отчёт вывел числовой код источника как "Способ закупки", хотя в извещении/документации есть человекочитаемый способ закупки;
- отчёт взял технический timestamp структурированного источника по итогам, хотя в извещении есть явная дата/время рассмотрения, оценки и подведения итогов;
- срок поставки перепутан со сроком действия договора;
- отчёт содержит дату, которой нет в исходных документах, или подставляет конкретную дату вместо отсутствующего графика поставки;
- отчёт рекомендует ГОСТ, ТУ, ТР ТС, реестры или иные нормативные требования, которых нет в исходных документах.
- в логистике отчёт пишет "ДАННЫХ НЕДОСТАТОЧНО" по общему весу/объёму, хотя в исходнике есть товар, количество и физические параметры для ориентировочной оценки;
- в критичных требованиях отчёт добавляет "товар должен быть новым" вместо того, чтобы отдельно указать найденный год/дату производства.
- по нацрежиму отчёт пишет "преимущество", "ограничение" или "мера не применяется", но одновременно требует выписку/реестровую запись Минпромторга;
- по нацрежиму отчёт оставляет неопределённость "если применимо" вместо прямой строки "Требуются ли выписки из реестра Минпромторга: **Да/Нет/Не указано**";
- по НДС отчёт пишет "сумма оплаты не увеличивается" или иначе подменяет риск УСН: нужно проверять только риск уменьшения цены договора/оплаты на сумму НДС или удержания НДС при оплате.

Важное правило OSINT:
- НЕ считай ошибкой, что в OSINT нет конкретных поставщиков, URL, контактов или рыночных цен, если внешний web-поиск не выполнялся.
- Считай ошибкой, если отчёт выдумывает конкретных поставщиков, бренды, URL, контакты или цены без источника в документах.

Ответ JSON:
{
  "ok": true,
  "issues": [],
  "corrected_report": ""
}

Если исправления нужны, верни полный corrected_report со всеми обязательными разделами.
В corrected_report обязательно сохрани Markdown-таблицу ТЗ; запрещено заменять ее кратким списком позиций.
Не добавляй в пользовательский отчёт служебные маркеры файлов вида [001_Извещение.docx] или [003_...].
Если отчёт приемлем, corrected_report оставь пустым."""

DEFAULT_OFFICIAL_CARD_REPAIR_PROMPT = """Исправь отчёт по официальной карточке закупки / ЕИС / электронной площадки.
Это не творческая редактура: нужно исправить только перечисленные расхождения по карточечным полям официального источника.
Для полей "Способ закупки", срок подачи заявок и дата подведения итогов копируй значения официального источника буквально.
Если в официальном источнике указана только дата без времени, не добавляй время.
Верни полный Markdown-отчёт без служебных комментариев."""

OFFICIAL_CARD_FIELD_LABELS = {
    "procurement_method": ("Способ осуществления закупки", "Способ/код размещения", "Способ закупки"),
    "submission_deadline": (
        "Дата и время окончания срока подачи заявок (по местному времени заказчика)",
        "Дата и время окончания срока подачи заявок (МСК)",
        "Окончание подачи заявок",
    ),
    "results_date": ("Дата подведения итогов", "Дата подведения итогов (МСК)", "Подведение итогов"),
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

RUSSIAN_MONTHS = {
    "января": "01",
    "февраля": "02",
    "марта": "03",
    "апреля": "04",
    "мая": "05",
    "июня": "06",
    "июля": "07",
    "августа": "08",
    "сентября": "09",
    "октября": "10",
    "ноября": "11",
    "декабря": "12",
}

NATIONAL_REGIME_LINES = {
    "advantage": (
        "- Нацрежим: **Установлено преимущество в отношении товаров российского происхождения.**",
        "- Требуются ли выписки из реестра Минпромторга: **Нет**",
    ),
    "restriction": (
        "- Нацрежим: **Действует ограничение закупок товаров.**",
        "- Требуются ли выписки из реестра Минпромторга: **Нет**",
    ),
    "prohibition": (
        "- Нацрежим: **Действует запрет закупок товаров.**",
        "- Требуются ли выписки из реестра Минпромторга: **Да**",
    ),
    "not_applied": (
        "- Нацрежим: **Запрет/ограничение указан, но не применяется по обоснованию невозможности соблюдения.**",
        "- Требуются ли выписки из реестра Минпромторга: **Нет**",
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
    current_date = dt.datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y")
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
        call_metadata: dict = {}
        raw = await call_llm(
            settings,
            user_prompt,
            system_prompt=system_prompt,
            tier="primary",
            routing_key="procurement_document_analysis",
            timeout_seconds=float(report_settings.get("analysis_timeout_seconds") or 240),
            metadata=call_metadata,
        )
        if call_metadata.get("provider_name") and call_metadata.get("model"):
            ai_model = f"{call_metadata['provider_name']} | {call_metadata['model']}"
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
    if official_facts:
        report = normalize_official_card_report_fields(report, document_text)
    official_issues = validate_report_against_official_card(report, official_facts)
    if official_issues:
        report = await repair_report_official_card_fields(settings, report, document_text, official_issues, report_settings)
        report = normalize_official_card_report_fields(report, document_text)
        official_issues = validate_report_against_official_card(report, official_facts)
        if official_issues:
            raise ProcurementReportAIRequiredError(f"Official source card validation failed: {official_issues}")
    normalized_report = normalize_procurement_report_guardrails(report, document_text)
    if normalized_report != report:
        report = normalized_report
        if verification is not None:
            if verification.get("corrected_report"):
                verification["corrected_report"] = report
            verification["postprocessing"] = {
                "ok": True,
                "national_regime_types": sorted(extract_national_regime_requirement_types(document_text)),
                "normalized": True,
            }
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
    attempts = max(1, int(report_settings.get("verification_attempts") or 2))
    last_issue = "empty_verification_response"
    for _attempt in range(attempts):
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
            if parsed:
                return parsed
            last_issue = "empty_verification_response"
        except Exception as exc:
            last_issue = f"verification_failed: {exc}"
    return {"ok": False, "issues": [last_issue]}


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
    if (
        "ОФИЦИАЛЬНЫЙ ИСТОЧНИК ЗАКУПКИ" not in text
        and "СТРУКТУРИРОВАННЫЙ ИСТОЧНИК ЗАКУПКИ" not in text
        and "TENDERPLAN" not in text
        and "ЕИС" not in text
    ):
        return {}
    facts: dict[str, str] = {}
    procurement_method = _extract_procurement_method_fact(text)
    if procurement_method:
        facts["procurement_method"] = procurement_method
    for key, labels in OFFICIAL_CARD_FIELD_LABELS.items():
        if key == "procurement_method":
            continue
        if key == "results_date":
            results_date = _extract_results_date_fact(text)
            if results_date:
                facts[key] = results_date
                continue
        for label in labels:
            value = _extract_labeled_value(text, label)
            if value:
                facts[key] = value
                break
    return facts


def validate_report_against_official_card(report: str, facts: dict[str, str]) -> list[str]:
    if not facts:
        return []
    issues: list[str] = []
    method = facts.get("procurement_method", "")
    if method:
        report_method = _report_field_value(report, REPORT_FIELD_ALIASES["procurement_method"])
        if not report_method:
            issues.append(f"В отчёте нет поля 'Способ закупки', хотя в официальном источнике указано: {method}")
        elif _normalize_fact(report_method) != _normalize_fact(method):
            issues.append(f"Способ закупки должен быть ровно '{method}', в отчёте указано: '{report_method}'")

    submission_deadline = facts.get("submission_deadline", "")
    if submission_deadline:
        report_deadline = _report_field_value(report, REPORT_FIELD_ALIASES["submission_deadline"])
        if not report_deadline:
            issues.append(
                "В отчёте нет срока подачи заявок, хотя в официальном источнике указано: "
                f"{submission_deadline}"
            )
        elif not _contains_date_and_time_from_source(report_deadline, submission_deadline):
            issues.append(
                "Срок подачи заявок должен сохранять дату и время официального источника "
                f"'{submission_deadline}', в отчёте указано: '{report_deadline}'"
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
                "В отчёте нет даты подведения итогов, хотя в официальном источнике указано: "
                f"{results_date}"
            )
        elif not _contains_date_from_source(report_results, results_date):
            issues.append(
                "Дата подведения итогов должна сохранять дату официального источника "
                f"'{results_date}', в отчёте указано: '{report_results}'"
            )
        elif not _extract_time(results_date) and _extract_time(report_results):
            issues.append(
                "Время подведения итогов нельзя добавлять: официальный источник содержит только дату "
                f"'{results_date}', в отчёте указано: '{report_results}'"
            )
    return issues


def normalize_procurement_report_guardrails(report: str, document_text: str) -> str:
    value = normalize_official_card_report_fields(report, document_text)
    value = remove_okpd_codes(value)
    value = normalize_customer_boolean_artifacts(value)
    value = normalize_source_conflict_wording(value)
    value = normalize_logistics_estimate(value, document_text)
    value = normalize_product_freshness_wording(value)
    value = normalize_national_regime_conditions(value, document_text)
    value = normalize_vat_usn_risk(value, document_text)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def remove_okpd_codes(report: str) -> str:
    value = str(report or "")
    if not value:
        return value
    okpd_name = r"(?:ОКПД\s*2?|OKPD\s*2?)"
    value = re.sub(
        rf"\s*[\(\[]\s*(?:код\s+)?{okpd_name}\s*[:№#Nn\-–—]?\s*[\d.\s/-]+[\)\]]",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        rf"(?:код\s+)?{okpd_name}\s*[:№#Nn\-–—]?\s*\d+(?:\.\d+){{1,6}}\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b\d{2}\.\d{2}\.\d{2}(?:\.\d{1,3}){0,3}\b", "", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    value = re.sub(r"\(\s*\)", "", value)
    value = re.sub(r"\[\s*\]", "", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    return value.strip()


def normalize_customer_boolean_artifacts(report: str) -> str:
    value = str(report or "")
    value = re.sub(
        r"(?i)(признак\s+СМП/СОНО\s+)отключ[её]н\s*\(\s*false\s*\)",
        r"\1не установлен",
        value,
    )
    value = re.sub(
        r"(?i)(признак\s+СМП/СОНО\s+)включ[её]н\s*\(\s*true\s*\)",
        r"\1установлен",
        value,
    )
    value = re.sub(r"(?i)(СМП/СОНО\s*:\s*)false\b", r"\1не установлено", value)
    value = re.sub(r"(?i)(СМП/СОНО\s*:\s*)true\b", r"\1установлено", value)
    value = re.sub(r"(?i)\s*\(\s*(?:false|true)\s*\)", "", value)
    value = re.sub(r"(?i)(?<![A-Za-zА-Яа-я])false(?![A-Za-zА-Яа-я])", "нет", value)
    value = re.sub(r"(?i)(?<![A-Za-zА-Яа-я])true(?![A-Za-zА-Яа-я])", "да", value)
    return value


def normalize_source_conflict_wording(report: str) -> str:
    value = _remove_noncritical_results_time_conflicts(str(report or ""))
    value = re.sub(
        r"(?i)Расхождение\s+сроков:\s*В\s+извещении\s+указано\s+время\s+подведения\s+итогов",
        "Расхождение в дате подведения итогов: В файле извещения указано время подведения итогов",
        value,
    )
    value = re.sub(
        r"(?i)в\s+структурированных\s+данных\s+площадки\s*[—-]\s*(.+?)\.\s*"
        r"Необходимо\s+ориентироваться\s+на\s+более\s+ранний\s+срок\.",
        (
            r"в структурированной карточке источника — \1. "
            "В отчёте использовано явное время из извещения; перед подачей заявки проверьте карточку закупки и площадку."
        ),
        value,
    )
    value = re.sub(
        r"(?i)в\s+структурированных\s+данных\s+площадки\s*[—-]\s*",
        "в структурированной карточке источника — ",
        value,
    )
    return value


def _remove_noncritical_results_time_conflicts(report: str) -> str:
    lines = str(report or "").splitlines()
    changed = False
    kept: list[str] = []
    for line in lines:
        if _is_noncritical_results_time_conflict(line):
            changed = True
            continue
        kept.append(line)
    if not changed:
        return report
    return _renumber_ordered_markdown_lists("\n".join(kept))


def _is_noncritical_results_time_conflict(line: str) -> bool:
    normalized = _normalize_fact(line)
    if "расхожд" not in normalized or "подвед" not in normalized or "итог" not in normalized:
        return False
    if any(token in normalized for token in ("аукцион", "торг", "подач", "заяв")):
        return False
    times = re.findall(r"\b\d{1,2}:\d{2}\b", str(line or ""))
    if len(set(times)) < 2:
        return False
    dates = re.findall(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", str(line or ""))
    return len(set(dates)) <= 1


def _renumber_ordered_markdown_lists(report: str) -> str:
    lines = str(report or "").splitlines()
    next_number = 1
    in_list = False
    result: list[str] = []
    for line in lines:
        match = re.match(r"^(\s*)(\d+)([.)])(\s+)(.*)$", line)
        if not match:
            in_list = False
            next_number = 1
            result.append(line)
            continue
        if not in_list:
            next_number = 1
            in_list = True
        result.append(f"{match.group(1)}{next_number}{match.group(3)}{match.group(4)}{match.group(5)}")
        next_number += 1
    return "\n".join(result)


def normalize_official_card_report_fields(report: str, document_text: str) -> str:
    facts = extract_official_card_facts(document_text)
    value = str(report or "")
    method = facts.get("procurement_method")
    if method and not _is_numeric_procurement_method(method):
        value = _replace_report_field(value, REPORT_FIELD_ALIASES["procurement_method"], "Способ закупки", method)
    submission_deadline = facts.get("submission_deadline")
    if submission_deadline:
        value = _replace_report_field(
            value,
            REPORT_FIELD_ALIASES["submission_deadline"],
            "Крайний срок подачи заявок",
            submission_deadline,
        )
    results_date = facts.get("results_date")
    if results_date:
        value = _replace_report_field(
            value,
            REPORT_FIELD_ALIASES["results_date"],
            "Дата рассмотрения/подведения итогов",
            results_date,
        )
    return value


def normalize_product_freshness_wording(report: str) -> str:
    value = str(report or "")
    value = re.sub(
        r"(?i)\b(?:поставляемый\s+)?товар\s+должен\s+быть\s+новым,\s*",
        "",
        value,
    )
    value = re.sub(r"(?i)\s*\bтовар\s+должен\s+быть\s+новым\.?", "", value)
    value = re.sub(r"\s*\(\s*\)\s*\.?", "", value)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    return value


def normalize_logistics_estimate(report: str, document_text: str) -> str:
    estimate = _known_logistics_estimate(document_text)
    if not estimate:
        return report
    lines = str(report or "").splitlines()
    for index, line in enumerate(lines):
        normalized = _normalize_fact(line)
        if "данных недостаточно" not in normalized:
            continue
        if "общий вес" not in normalized and "вес/объем" not in normalized and "вес/обьем" not in normalized:
            continue
        prefix = _line_prefix(line)
        lines[index] = f"{prefix}Общий вес/объём: {estimate}"
        return "\n".join(lines)
    return report


def _known_logistics_estimate(document_text: str) -> str:
    text = str(document_text or "")
    normalized = _normalize_fact(text)
    if "канат" not in normalized or "гост 3062-80" not in normalized:
        return ""
    diameter = _extract_rope_diameter_mm(text)
    quantity_km = _extract_quantity_km(text)
    if not diameter or not quantity_km:
        return ""
    kg_per_km = 5.12 * diameter * diameter
    total_kg = kg_per_km * quantity_km
    rounded_kg = _round_logistics_kg(total_kg)
    diameter_text = _format_decimal(diameter)
    quantity_text = _format_decimal(quantity_km)
    kg_text = _format_integer(rounded_kg)
    return (
        f"ориентировочно **~{kg_text} кг нетто** для {quantity_text} км стального каната "
        f"{diameter_text} мм; транспортный объём зависит от барабанов/бухт, для логистики "
        "принять **~2-4 м³** и уточнить упаковку у поставщика."
    )


def extract_national_regime_requirement_types(document_text: str) -> set[str]:
    text = str(document_text or "").replace("\\n", "\n")
    if not text.strip():
        return set()

    marked_types = _extract_marked_national_regime_requirement_types(text)
    if marked_types:
        return marked_types

    targeted_types = _extract_targeted_national_regime_requirement_types(text)
    if targeted_types:
        return targeted_types

    section = _extract_national_regime_section(text)
    if not section:
        return set()
    if _section_has_impossibility_reason(section):
        return {"not_applied"}

    section_types = _extract_requirement_types_from_text(section)
    return section_types if 0 < len(section_types) < 3 else set()


def normalize_national_regime_conditions(report: str, source_text: str = "") -> str:
    value = str(report or "")
    if not value.strip():
        return value

    requirement_types = extract_national_regime_requirement_types(source_text)
    regime_type = _single_national_regime_type(requirement_types)
    if not regime_type:
        regime_type = _extract_report_national_regime_type(value)
    if regime_type not in NATIONAL_REGIME_LINES:
        return value

    natregime_line, statement_line = NATIONAL_REGIME_LINES[regime_type]
    return _replace_national_regime_conditions_block(value, natregime_line, statement_line)


def normalize_vat_usn_risk(report: str, source_text: str = "") -> str:
    value = str(report or "")
    if not value.strip():
        return value

    risk_text = _vat_usn_risk_text(source_text)
    lines: list[str] = []
    for line in value.splitlines():
        normalized = _normalize_fact(line)
        if _has_bad_vat_usn_wording(normalized):
            line = _replace_vat_usn_risk_in_line(line, risk_text)
        lines.append(line)
    return "\n".join(lines).strip()


def _extract_marked_national_regime_requirement_types(text: str) -> set[str]:
    lines = [line.strip() for line in str(text or "").splitlines()]
    result: set[str] = set()
    for index, line in enumerate(lines):
        measure_type = _national_regime_type_from_line(line)
        if not measure_type:
            continue
        marker = _next_non_empty_line(lines, index + 1, limit=5)
        normalized_marker = _normalize_fact(marker)
        if normalized_marker in {"", "-", "—", "–", "нет", "не установлено", "не применяется"}:
            continue
        if re.fullmatch(r"(?:установлено|применяется|есть|да)[\s.;:-]*", normalized_marker):
            result.add(measure_type)
    return result if 0 < len(result) < 3 else set()


def _extract_targeted_national_regime_requirement_types(text: str) -> set[str]:
    blocks: list[str] = []
    for match in re.finditer(
        r"при\s+осуществлении\s+(?:данной\s+)?закупк[^\n]{0,500}?установлено\s*[:：]\s*([\s\S]{0,1200})",
        text,
        flags=re.IGNORECASE,
    ):
        blocks.append(match.group(1))
    for match in re.finditer(
        r"установлено\s*[:：]\s*[-–—•\s]*(запрет|ограничени(?:е|я|й)|преимуществ)[^\n]{0,1200}",
        text,
        flags=re.IGNORECASE,
    ):
        blocks.append(match.group(0))

    result: set[str] = set()
    for block in blocks:
        block_types = _extract_requirement_types_from_text(block)
        if 0 < len(block_types) < 3:
            result.update(block_types)
    return result if 0 < len(result) < 3 else set()


def _extract_national_regime_section(text: str) -> str:
    patterns = (
        r"Применение национального режима по ст\.?\s*14 Закона №\s*44-ФЗ([\s\S]*?)(?=\n(?:Обеспечение заявки|Условия контракта|Преимущества|Требуется обеспечение заявки|Порядок подачи заявок)|\Z)",
        r"Информация о запрете или об ограничении закупок[\s\S]{0,500}?о преимуществе[\s\S]*?(?=\n\d+\s*$|\nВнесение изменений|\nПорядок подведения|\Z)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def _extract_requirement_types_from_text(text: str) -> set[str]:
    result: set[str] = set()
    for raw_line in str(text or "").splitlines():
        measure_type = _national_regime_type_from_line(raw_line)
        if measure_type:
            result.add(measure_type)
    return result


def _national_regime_type_from_line(line: str) -> str:
    normalized = _normalize_fact(line)
    if not normalized:
        return ""
    if (
        "объект закупки" in normalized
        or "вид требований" in normalized
        or "обоснование невозможности соблюдения" in normalized
    ):
        return ""
    if re.search(r"\bзапрет(?:а|ов)?\s+закуп", normalized):
        return "prohibition"
    if re.search(r"\bограничени(?:е|я|й)\s+закуп", normalized):
        return "restriction"
    if "преимуществ" in normalized:
        return "advantage"
    return ""


def _section_has_impossibility_reason(section: str) -> bool:
    header = "обоснование невозможности соблюдения запрета, ограничения"
    normalized = _normalize_fact(section)
    if "не применяется" in normalized or "невозможно соблюсти" in normalized:
        return True
    if header not in normalized:
        return False
    for raw_line in str(section or "").splitlines():
        clean = _normalize_fact(raw_line)
        if not clean or clean == header:
            continue
        if "обоснование невозможности соблюдения" in clean:
            return True
    return normalized.count(header) > 1


def _single_national_regime_type(types: set[str]) -> str:
    if "not_applied" in types:
        return "not_applied"
    if len(types) == 1:
        return next(iter(types))
    return ""


def _extract_report_national_regime_type(report: str) -> str:
    for line in str(report or "").splitlines():
        normalized = _normalize_fact(line)
        if not any(token in normalized for token in ("нацрежим", "националь", "минпромторг", "реестров")):
            continue
        if "не применяется" in normalized:
            return "not_applied"
        measure_type = _national_regime_type_from_line(line)
        if measure_type:
            return measure_type
        if "преимуществ" in normalized:
            return "advantage"
        if "ограничени" in normalized:
            return "restriction"
        if "запрет" in normalized:
            return "prohibition"
    return ""


def _replace_national_regime_conditions_block(report: str, natregime_line: str, statement_line: str) -> str:
    lines = str(report or "").splitlines()
    section_bounds = _find_report_section(lines, "условия")
    if not section_bounds:
        return _replace_national_regime_lines_globally(report, natregime_line, statement_line)

    start, end = section_bounds
    body = lines[start + 1 : end]
    next_body: list[str] = []
    inserted = False
    for line in body:
        if _is_national_regime_report_noise(line):
            if not inserted:
                next_body.extend([natregime_line, statement_line])
                inserted = True
            continue
        next_body.append(line)

    if not inserted:
        insert_at = 0
        while insert_at < len(next_body) and not next_body[insert_at].strip():
            insert_at += 1
        next_body[insert_at:insert_at] = [natregime_line, statement_line]

    next_lines = lines[: start + 1] + next_body + lines[end:]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(next_lines)).strip()


def _replace_national_regime_lines_globally(report: str, natregime_line: str, statement_line: str) -> str:
    lines: list[str] = []
    inserted = False
    for line in str(report or "").splitlines():
        if _is_national_regime_report_noise(line):
            if not inserted:
                lines.extend([natregime_line, statement_line])
                inserted = True
            continue
        lines.append(line)
    if not inserted:
        lines.extend([natregime_line, statement_line])
    return "\n".join(lines).strip()


def _find_report_section(lines: list[str], section_prefix: str) -> tuple[int, int] | None:
    start = -1
    for index, line in enumerate(lines):
        if not re.match(r"^\s*#{2,6}\s+", line):
            continue
        heading = _normalize_heading(line)
        if heading.startswith(section_prefix):
            start = index
            break
    if start < 0:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^\s*#{2,6}\s+", lines[index]):
            end = index
            break
    return start, end


def _normalize_heading(line: str) -> str:
    value = re.sub(r"^\s*#{2,6}\s*", "", str(line or "")).strip().lower()
    value = re.sub(r"^[^\wа-яё]+", "", value, flags=re.IGNORECASE)
    return value.replace("ё", "е")


def _is_national_regime_report_noise(line: str) -> bool:
    normalized = _normalize_fact(line)
    if not normalized:
        return False
    if normalized.startswith("нацрежим:") or normalized.startswith("- нацрежим:"):
        return True
    if "требуются ли выписки из реестра минпромторга" in normalized:
        return True
    if "выписки из реестра минпромторга" in normalized:
        return True
    if "номера реестровых записей" in normalized and any(
        token in normalized for token in ("минпром", "страны происхождения", "преимуществ")
    ):
        return True
    if "реестровые записи" in normalized and any(
        token in normalized for token in ("если применимо", "страны происхождения", "получения преимущества")
    ):
        return True
    if re.match(r"^\d+[\).]\s+", normalized) and any(
        token in normalized for token in ("постановление", "националь", "преимуществ", "запрет", "огранич", "выписк", "реестров")
    ):
        return True
    if "действует фактически" in normalized and any(
        token in normalized for token in ("преимуществ", "запрет", "огранич", "националь")
    ):
        return True
    return False


def _has_bad_vat_usn_wording(normalized_line: str) -> bool:
    return (
        "сумма оплаты не увеличивается" in normalized_line
        or ("риск для усн:" in normalized_line and "увелич" in normalized_line)
        or ("риски участия на усн:" in normalized_line and "увелич" in normalized_line)
    )


def _replace_vat_usn_risk_in_line(line: str, risk_text: str) -> str:
    pattern = re.compile(r"(Риск(?:и участия)?\s+(?:для|на)\s+УСН\s*:\s*)[^\n]*", flags=re.IGNORECASE)
    if pattern.search(line):
        return pattern.sub(lambda match: f"{match.group(1)}{risk_text}", line)
    return f"{line.rstrip()} Риск для УСН: {risk_text}"


def _vat_usn_risk_text(source_text: str) -> str:
    if _source_has_vat_reduction_or_withholding_risk(source_text):
        return (
            "найдено условие, которое может позволить уменьшить цену/оплату на сумму НДС "
            "или удержать НДС при оплате; проверьте формулировку договора перед подачей."
        )
    return "рисков уменьшения цены/оплаты на сумму НДС в найденной формулировке не выявлено."


def _source_has_vat_reduction_or_withholding_risk(source_text: str) -> bool:
    normalized = _normalize_fact(source_text)
    for match in re.finditer("ндс", normalized):
        window = normalized[max(0, match.start() - 300) : match.end() + 300]
        if any(token in window for token in ("уменьш", "сниж", "удерж", "за вычетом", "вычет")):
            return True
    return False


def _next_non_empty_line(lines: list[str], start: int, *, limit: int) -> str:
    for line in lines[start : start + limit]:
        if line.strip():
            return line.strip()
    return ""


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


def _extract_labeled_value(text: str, label: str) -> str:
    inline = re.compile(rf"(?m)^\s*[-*]?[ \t]*{re.escape(label)}[ \t]*:[ \t]*([^\n]*)")
    match = inline.search(text)
    if match:
        return _clean_inline_text(match.group(1))
    return _extract_following_line(text, label)


def _extract_labeled_values(text: str, labels: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for label in labels:
        inline = re.compile(rf"(?m)^\s*[-*]?[ \t]*{re.escape(label)}[ \t]*:[ \t]*([^\n]*)")
        for match in inline.finditer(text):
            value = _clean_inline_text(match.group(1))
            if value:
                values.append(value)
        following = _extract_following_line(text, label)
        if following:
            values.append(following)
    return values


def _extract_procurement_method_fact(text: str) -> str:
    candidates = _extract_labeled_values(text, REPORT_FIELD_ALIASES["procurement_method"])
    numeric_candidate = ""
    for candidate in candidates:
        cleaned = _clean_procurement_method_value(candidate)
        if not cleaned:
            continue
        if _is_numeric_procurement_method(cleaned):
            numeric_candidate = numeric_candidate or cleaned
            continue
        return _sentence_case(cleaned)
    return numeric_candidate


def _clean_procurement_method_value(value: str) -> str:
    text = _clean_inline_text(value)
    text = re.split(
        r"\s+(?:Предмет закупки|Дата публикации|Дата и время|Начальная|НМЦК|Данная процедура|Запрос\s+\w+\s+проводится)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    text = text.split("|", 1)[0].strip(" .;")
    return text


def _is_numeric_procurement_method(value: str) -> bool:
    text = _normalize_fact(value)
    return bool(re.fullmatch(r"(?:код\s+tenderplan\s*)?\d{1,4}", text))


def _extract_results_date_fact(text: str) -> str:
    document_value = _extract_document_results_date(text)
    labeled_value = ""
    for label in OFFICIAL_CARD_FIELD_LABELS["results_date"]:
        labeled_value = _extract_labeled_value(text, label)
        if labeled_value:
            break
    if document_value:
        return document_value
    return labeled_value


def _extract_document_results_date(text: str) -> str:
    patterns = (
        r"Место\s+и\s+дата\s+рассмотрения,\s*оценки\s+и\s+подведения\s+итогов[^\n]{0,900}",
        r"Дата\s+рассмотрения,\s*оценки\s+и\s+подведения\s+итогов[^\n]{0,900}",
        r"Дата\s+подведения\s+итогов[^\n]{0,500}",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = _extract_russian_date_time(match.group(0))
            if value:
                return value
    return ""


def _extract_russian_date_time(value: str) -> str:
    match = re.search(
        r"[«\"“]?(\d{1,2})[»\"”]?\s+([А-Яа-яЁё]+)\s+(\d{4})\s*г(?:ода)?\.?(?:\s*(?:до|в)\s*(\d{1,2})[:.](\d{2}))?",
        str(value or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    month = RUSSIAN_MONTHS.get(match.group(2).lower().replace("ё", "е"))
    if not month:
        return ""
    date = f"{int(match.group(1)):02d}.{month}.{match.group(3)}"
    if match.group(4) and match.group(5):
        return f"{date} {int(match.group(4)):02d}:{match.group(5)} МСК"
    return date


def _replace_report_field(report: str, aliases: tuple[str, ...], output_label: str, value: str) -> str:
    lines = str(report or "").splitlines()
    for index, line in enumerate(lines):
        clean = _clean_inline_text(line).lstrip("-* ").strip()
        if not any(clean.lower().startswith(f"{alias.lower()}:") for alias in aliases):
            continue
        prefix = _line_prefix(line)
        lines[index] = f"{prefix}{output_label}: {value}"
        return "\n".join(lines)

    bounds = _find_report_section(lines, "общая")
    if bounds:
        insert_at = bounds[0] + 1
        lines.insert(insert_at, f"- {output_label}: {value}")
        return "\n".join(lines)
    return f"- {output_label}: {value}\n{report}".strip()


def _line_prefix(line: str) -> str:
    indent = re.match(r"^\s*", str(line or "")).group(0)
    stripped = str(line or "").lstrip()
    if stripped.startswith("-"):
        return f"{indent}- "
    if stripped.startswith("*"):
        return f"{indent}* "
    return indent


def _sentence_case(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:1].upper() + text[1:]


def _extract_rope_diameter_mm(text: str) -> float:
    patterns = (
        r"(?:диам(?:етр)?\.?\s*-?\s*)(\d+(?:[,.]\d+)?)\s*мм",
        r"(\d+(?:[,.]\d+)?)\s*мм[^\n]{0,120}\bканат",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _parse_decimal(match.group(1))
    return 0.0


def _extract_quantity_km(text: str) -> float:
    matches = list(re.finditer(r"(\d+(?:[,.]\d+)?)\s*км\.?", text, flags=re.IGNORECASE))
    for match in matches:
        window = text[max(0, match.start() - 220) : match.end() + 80]
        if re.search(r"канат|ГОСТ\s*3062-80", window, flags=re.IGNORECASE):
            return _parse_decimal(match.group(1))
    return _parse_decimal(matches[0].group(1)) if matches else 0.0


def _parse_decimal(value: str) -> float:
    try:
        return float(str(value or "").replace(",", "."))
    except ValueError:
        return 0.0


def _round_logistics_kg(value: float) -> int:
    if value >= 1000:
        return int(round(value / 100.0) * 100)
    if value >= 100:
        return int(round(value / 10.0) * 10)
    return int(round(value))


def _format_decimal(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}".replace(".", ",")


def _format_integer(value: int) -> str:
    return f"{int(value):,}".replace(",", " ")


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
