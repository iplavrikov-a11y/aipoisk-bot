from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from .ai import call_llm, get_model_selection, parse_json_object
from .models import SystemSettings, parse_json_dict

DEFAULT_REPORT_SYSTEM_PROMPT = """Ты — Макс, экспертный тендерный аналитик.
Работай строго по документам закупки. Не придумывай факты, поставщиков, цены, URL или нормативные требования.
ATI и внешние логистические ставки отключены: не рассчитывай ATI, не пиши тарифы перевозчиков и не делай вид, что был внешний логистический запрос.

Сформируй подробный Markdown-отчет в структуре EmailAgent:

#### Общая информация
- Заказчик
- ИНН
- Номер закупки ЕИС
- Город поставки

#### Условия
- Обеспечение
- Нацрежим
- ГОЗ/сопровождение

#### Исполнение
- Срок поставки/выполнения
- Место поставки с полным адресом, если он есть

#### Финансы и НДС
- Аванс
- Оплата
- Обеспечение исполнения контракта
- НДС и риски для УСН

### Товары и требования (Техническое задание)
Обязательная Markdown-таблица:
| № | Наименование | Характеристики | Ед.изм. | Кол-во |
|---|---|---|---|---|
Выведи все позиции из исходного ТЗ. Не объединяй разные товары. Не пиши "см. спецификацию", если в документах есть данные.

#### Логистика (Оценка)
Только оценка по документам без ATI и без ставок перевозчиков: вес, объем, транспорт, режим поставки, разгрузка, пронос/заезд, примечание.

#### Критичные требования к товару
- Дата производства
- Срок годности
- Упаковка/тара/маркировка
- Сертификаты/паспорта/регистры

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

Правила:
- Начинай сразу с первого раздела, без вступления.
- Если данных нет, пиши "Не найдено" или "ДАННЫХ НЕДОСТАТОЧНО".
- Критичные характеристики и цифры выделяй жирным.
- Сохраняй Markdown-таблицы, списки и короткие практические формулировки.
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
- отсутствуют обязательные разделы.

Ответ JSON:
{
  "ok": true,
  "issues": [],
  "corrected_report": ""
}

Если исправления нужны, верни полный corrected_report. Если отчет приемлем, corrected_report оставь пустым."""


@dataclass(frozen=True)
class ReportGenerationResult:
    report: str
    ai_used: bool
    ai_model: str = ""
    warning: str = ""
    verification: dict | None = None


async def generate_procurement_report(settings: SystemSettings, document_text: str) -> ReportGenerationResult:
    if not settings.has_active_ai_provider:
        return ReportGenerationResult(
            report=build_fallback_report(document_text),
            ai_used=False,
            warning="AI provider is not configured; deterministic fallback report was generated.",
        )

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
    except Exception:
        ai_model = ""
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
        return ReportGenerationResult(
            report=build_fallback_report(document_text),
            ai_used=False,
            warning=f"AI report generation failed: {exc}",
        )

    report = clean_markdown_report(raw)
    verification: dict | None = None
    if report_settings.get("verify_report", True):
        verification = await verify_report(settings, report, document_text, report_settings)
        corrected = clean_markdown_report(str(verification.get("corrected_report") or ""))
        if corrected and not verification.get("ok"):
            report = corrected
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
    return text.strip() or build_fallback_report("")


def build_fallback_report(document_text: str) -> str:
    excerpt = (document_text or "").strip()[:16000] or "Текст документов не извлечен."
    return f"""#### Общая информация
- Заказчик: **ДАННЫХ НЕДОСТАТОЧНО**
- ИНН: **ДАННЫХ НЕДОСТАТОЧНО**
- Номер закупки ЕИС: **ДАННЫХ НЕДОСТАТОЧНО**
- Город поставки: **ДАННЫХ НЕДОСТАТОЧНО**

#### Условия
- ДАННЫХ НЕДОСТАТОЧНО

#### Исполнение
- Срок поставки/выполнения: **ДАННЫХ НЕДОСТАТОЧНО**
- Место поставки: **ДАННЫХ НЕДОСТАТОЧНО**

#### Финансы и НДС
- ДАННЫХ НЕДОСТАТОЧНО

### Товары и требования (Техническое задание)
| № | Наименование | Характеристики | Ед.изм. | Кол-во |
|---|---|---|---|---|
| 1 | Требуется ручная проверка | AI-провайдер не настроен или не ответил; ниже сохранен извлеченный контекст |  |  |

#### Логистика (Оценка)
- ATI/внешние логистические ставки: **отключены**
- ДАННЫХ НЕДОСТАТОЧНО

#### Критичные требования к товару
- ДАННЫХ НЕДОСТАТОЧНО

#### Коммерческие условия
- ДАННЫХ НЕДОСТАТОЧНО

#### Что уточнить
- У заказчика: **проверить исходные документы вручную**
- У поставщика: **уточнить соответствие ТЗ**

#### Риски
- Отчет создан как fallback без AI-анализа.

#### Рекомендации
- Настроить AI-провайдера в админке и перезапустить задачу.

#### Рыночная разведка (OSINT)
- Не выполнялась.

### Извлеченный контекст
{excerpt}
"""


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ""
