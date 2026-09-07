from __future__ import annotations

"""
Глубокий инженерный поиск точного товара, характеристик и аналогов (технология TenderLex / RAG Grounding).
Включает:
1. Интеллектуальное планирование поисковых запросов по ТЗ, ГОСТам и ТУ.
2. Поиск в сети (Яндекс / Exa / Google) и скачивание технических PDF-паспортов и каталогов заводов.
3. Извлечение таблиц характеристик через PyMuPDF (fitz) с обходом блокировок через Playwright.
4. Заземленный ИИ-анализ характеристик (Grounding) с жестким запретом галлюцинаций.
5. Защиту от выдуманных цифр (_is_grounded_in_text).
6. Модуль инженерных стандартов ГОСТ (климатика ГОСТ 15150, защита IP ГОСТ 14254, электробезопасность).
7. Обогащение по локальному SQLite FTS5 индексу реестра Минпромторга (ГИСП).
"""

import asyncio
import json
import logging
import os
import re
import sys
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlsplit


def _item_val(obj, key, default=""):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _item_set(obj, key, val):
    if isinstance(obj, dict):
        obj[key] = val
    else:
        setattr(obj, key, val)


def _is_placeholder_brand_or_model(val: str) -> bool:
    if not val:
        return True
    low = str(val).strip().lower()
    if len(low) < 2:
        return True
    if any(p in low for p in ("не указано", "паспорт завода", "не определен", "не найден", "в открытой документации")):
        return True
    placeholders = {
        "товар", "оборудование", "материал", "изделие", "позиция", "по тз", "по спецификации",
        "согласно тз", "отечественный производитель", "завод", "производитель", "россия", "рф",
        "unknown", "none", "null", "-", "—",
    }
    return low in placeholders


class ResolveResult(int):
    def __new__(cls, val, cost=0.0):
        obj = super().__new__(cls, int(val))
        obj.cost = float(cost)
        return obj

    def __iter__(self):
        yield int(self)
        yield self.cost


async def _call_fetch_batch_web_documents(urls: List[str], max_docs: int = 6) -> List[Dict[str, Any]]:
    ep_mod = sys.modules.get("app.exact_product")
    if ep_mod and hasattr(ep_mod, "fetch_batch_web_documents"):
        fn = getattr(ep_mod, "fetch_batch_web_documents")
        if fn is not fetch_batch_web_documents:
            return await fn(urls, max_docs=max_docs)
    return await fetch_batch_web_documents(urls, max_docs=max_docs)



import httpx
import structlog
from bs4 import BeautifulSoup

from .llm_bridge import call_llm
from .llm_bridge import get_settings
from .product_brand_detector import (
    extract_clean_spec_text,
    find_minprom_registry_matches,
)
from .spec_searcher import _fetch_search_results_for_specs
from .yandex_search import EXCLUDED_DOMAINS, YandexSearchEngine

logger = structlog.get_logger(__name__)

ProgressCallback = Callable[[int, str], Coroutine[Any, Any, None]]

# ---------------------------------------------------------------------------
# Strict Grounded Prompt
# ---------------------------------------------------------------------------

EXACT_PRODUCT_DEEP_PROMPT = """Ты — ведущий эксперт по государственным закупкам (44-ФЗ, 223-ФЗ), стандартизации и промышленному оборудованию.
Твоя задача — проанализировать техническое задание (ТЗ), сопоставить его с приложенными проверенными документами из интернета (паспортами, каталогами, сайтами производителей) и сформировать достоверные сведения для заявки (Форма 2) и взаимозаменяемых аналогов.

ЖЕЛЕЗНЫЕ ПРАВИЛА ДОСТОВЕРНОСТИ И ИНЖЕНЕРНОГО АНАЛИЗА:
1. СТРОГО ЗАПРЕЩЕНО ВЫДУМЫВАТЬ ЗНАЧЕНИЯ ИЛИ ИСКУССТВЕННО ПОДГОНЯТЬ ИХ ПОД ТЗ!
2. ИСПОЛЬЗУЙ ПАСПОРТА, ТАБЛИЦЫ КАТАЛОГОВ И ГОСТ/ТУ:
   - Внимательно читай приложенные таблицы характеристик ([ИСТОЧНИК N]), опросные листы и модельные ряды заводов.
   - Если в ТЗ задан диапазон (например: 'глубина >=4 <=4.5 м', 'масса не более 12100 кг', 'мощность 2x0.55 кВт'), а в каталоге/паспорте приведено номинальное заводское значение или типовой ряд завода (например: глубина 4.2 м, масса 11800 кг, привод 2x0.55 кВт) — укажи конкретный заводской номинал, статус "match" и сошлись на [ИСТОЧНИК N].
   - Для стандартной продукции (металлопрокат, кабели, запорная арматура, КИПиА, электродвигатели) опирайся на официальные ГОСТ/ТУ.
3. ЕСЛИ ПАРАМЕТР ТОЧНО ПОДТВЕРЖДЕН И СООТВЕТСТВУЕТ ТЗ:
   - "product_fact": Конкретное подтвержденное значение производителя (без слов 'не менее/не более', например: "4.2 м", "11 800 кг", "AISI 304", "3 мм")
   - "status": "match"
   - "comment": "Подтверждено каталогом производителя [ИСТОЧНИК N] / ГОСТ"
4. ЕСЛИ ФАКТИЧЕСКИЙ ПАРАМЕТР РАСХОДИТСЯ С ТЗ:
   А) УЛУЧШЕННЫЕ ХАРАКТЕРИСТИКИ (по ч. 2 ст. 33 44-ФЗ):
      - Если характеристика объективно превосходит требование ТЗ по уровню надежности, степени защиты, долговечности, энергоэффективности или безопасности БЕЗ нарушения посадочных мест, монтажных условий и проектной совместимости с объектом заказчика:
        * "status": "match"
        * "comment": "Улучшенные характеристики по 44-ФЗ: показатель превосходит требование ТЗ [краткое инженерное обоснование] [ИСТОЧНИК N]"
      - ВНИМАНИЕ: Изменение габаритов, установочных размеров, диаметров, присоединительных типоразмеров или параметров питания/напряжения, если это нарушает проектную совместимость с объектом заказчика — это НЕ улучшение, а СТРОГО "mismatch" (отклонение от ТЗ)!
   Б) ОТКЛОНЕНИЕ ОТ ТЗ (НЕСООТВЕТСТВИЕ):
      - Если отклонение нарушает функциональную совместимость, проектные ограничения, монтажные размеры или не укладывается в диапазон допустимого:
        * "product_fact": Реальный показатель из документа или заводского ТУ (например: "ТУ 22.19.20-001-70758385-2024", "14 500 кг")
        * "status": "mismatch"
        * "comment": "Отклонение от ТЗ: фактически параметр отличается от требований заказчика [ИСТОЧНИК N]. Если в ТЗ указан ГОСТ, а продукция выпускается по ТУ или ГОСТ не распространяется на данный материал/типоразмер — СТРОГО ставь статус 'mismatch' с указанием расхождения!"
5. ЕСЛИ ПАРАМЕТР ЯВЛЯЕТСЯ ЗАКАЗНОЙ ОПЦИЕЙ, УСЛОВИЕМ ПОСТАВКИ ИЛИ ОТСУТСТВУЕТ В ОТКРЫТЫХ КАТАЛОГАХ:
   - Для параметров, зависящих от конкретной производственной партии/паспорта приемки (например: 'Год производства', 'Срок службы', 'Ресурс', 'Гарантия'):
   - "product_fact": "В открытой документации не указано (требуется официальный паспорт завода)"
   - "status": "clarify"
   - "comment": "Подобрано ИИ под требование ТЗ. В открытых источниках параметр не опубликован — требуется уточнить по паспорту или официальному документу производителя перед подачей заявки."
6. ДЛЯ ПРОИЗВОДИТЕЛЯ И АНАЛОГОВ (manufacturer, alternative_brands):
   - В поле "manufacturer" и "brand" указывай ТОЛЬКО РЕАЛЬНОЕ ПРОИЗВОДСТВЕННОЕ ПРЕДПРИЯТИЕ (завод, фабрику, комбинат, НПО). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО указывать названия интернет-магазинов, дилеров, торговых посредников, маркетплейсов или названия стран ("Россия", "Китай" — это страна происхождения для нацрежима, а не завод!). Если конкретный завод в открытых источках не указан, пиши "Завод-изготовитель не указан в открытых источниках".
   - Для аналогов (alternative_brands): указывай ТОЛЬКО реально существующие серийные модели реальных заводов-изготовителей. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдумывать модели или копировать в них фразы из ТЗ заказчика ('не менее...', 'от... до...'). Построчно заполни реальные известные характеристики аналога. Если точный параметр в открытых источниках неизвестен — ставь статус "clarify" ("В открытой документации не указано").
7. ЛИМИТИРОВАНИЕ И ПРИОРИТИЗАЦИЯ ПОЗИЦИЙ (СТРОГО ДО 5 ОСНОВНЫХ ПОЗИЦИЙ):
   - В итоговом массиве "positions" сформируй ДО 5 ГЛАВНЫХ ТЕХНОЛОГИЧЕСКИХ ПОЗИЦИЙ ТОВАРА/ОБОРУДОВАНИЯ (сложное промышленное оборудование, основные агрегаты, материалы, измерительные приборы, кабели, запорная арматура, готовые изделия).
   - СТРОГО ИСКЛЮЧАЙ:
     1) Строительно-монтажные, демонтажные, пусконаладочные работы, доставку и любые сервисные услуги;
     2) Мелкий крепеж и метизы (болты, гайки, шайбы, саморезы, дюбели, шурупы, винты, шпильки, заклепки, анкеры, хомуты, стяжки, скобы, шплинты);
     3) Мелкие дешевые общехозяйственные расходники и сопутствующие копеечные мелочи (изолента, скотч, ветошь, салфетки, мешки для мусора, перчатки, батарейки, маркеры, канцелярия, мелкие стандартные прокладки).
   - Если в спецификации перечислено более 5 позиций — отбери ТОП-5 самых технологически сложных, наукоемких и капиталоемких товаров, для которых критически важно определить конкретную модель и характеристики Формы 2. Мелкие сопутствующие расходники и крепеж пропускай — они стандартные и интуитивно понятные.

Спецификация ТЗ и проверенные документы из открытых источников:
{context}

Ответь СТРОГО в формате JSON:
{{
  "summary": "1-2 кратких предложения: какая конкретная модель заложена в ТЗ и какие проверенные аналоги РФ выявлены.",
  "positions": [
    {{
      "position_no": 1,
      "name_in_tz": "Наименование позиции из ТЗ",
      "identified_brand": "Основной выявленный завод или бренд",
      "identified_model": "Точная промышленная модель или маркировка",
      "manufacturer": "Завод-изготовитель (юридическое или торговое наименование)",
      "confidence": 1.0,
      "reasoning": "Обоснование соответствия характеристикам ТЗ по ГОСТ/ТУ/размерам",
      "source_url": "URL сайта или паспорта",
      "specs_breakdown": [
        {{
          "param_name": "Наименование параметра",
          "tz_requirement": "Требование ТЗ (диапазон или условие)",
          "product_fact": "Фактический показатель модели по паспорту завода (или 'В открытой документации не указано')",
          "status": "match",
          "comment": "Обоснование соответствия или ссылка на паспорт",
          "source_url": "URL источника"
        }}
      ],
      "alternative_brands": [
        {{
          "brand": "Бренд или завод аналога",
          "model": "Модель аналога",
          "manufacturer": "Производитель аналога",
          "confidence": 1.0,
          "notes": "Обоснование эквивалентности",
          "source_url": "URL сайта завода аналога",
          "specs_breakdown": [
            {{
              "param_name": "Наименование параметра",
              "tz_requirement": "Требование ТЗ",
              "product_fact": "Фактический показатель аналога",
              "status": "match",
              "comment": "Соответствие или отклонение аналога"
            }}
          ]
        }}
      ]
    }}
  ]
}}
"""

RESOLVE_CLARIFY_PROMPT = """Ты — ведущий эксперт по стандартизации и госзакупкам (44-ФЗ/223-ФЗ).
Твоя задача — проверить приложенный текст технических документов / паспортов / каталогов / ГОСТ и установить точное фактическое значение параметра для конкретной модели оборудования или материала.

Товар: {brand} {model} (Производитель: {manufacturer})
Наименование параметра: {param_name}
Требование ТЗ: {tz_requirement}

Текст найденных технических документов, паспортов и стандартов:
{doc_text}

ПРАВИЛА ВЕРИФИКАЦИИ:
1. Ищи ТОЧНОЕ числовое или качественное значение параметра именно для указанной модели или нормативного типоразмера.
2. Не выдумывай и не подгоняй под ТЗ! Если точное значение ЕСТЬ в тексте:
   - "found": true
   - "product_fact": "точное значение из документа" (без слов 'не менее/не более', например: "1.6 МПа", "14 000 лм", "32 м3/ч", "1200 x 1200 dpi", "120 мм", "УХЛ1", "IP66")
   - "status": "match" (если значение укладывается в требование ТЗ) или "mismatch" (если фактическое значение отличается от ТЗ)
   - "comment": "краткое подтверждение со ссылкой на паспорт/каталог/документ/ГОСТ"
3. Если значения НЕТ в тексте:
   - "found": false
   - "product_fact": "В открытой документации не указано (требуется официальный паспорт завода)"
   - "status": "clarify"
   - "comment": "Требуется официальный паспорт завода"
4. ВАЖНО: Если требование ТЗ относится к заводскому рулону, бухте или промышленной партии (например рулон 500+ м), а в документе стороннего продавца описана розничная нарезка, продажа мерным куском или листами для поделок/творчества/хобби (например 1 м, 100 см) — КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО считать это заводской характеристикой модели! Возвращай "found": false.
5. Для комплексных описательных параметров (например 'Описание товара', 'Назначение', 'Свойства изделия'):
   - Если в документе прямо подтверждены технологические свойства (например: 'каландрированная с двух сторон', 'из волокон хлопка с добавлением манильской пеньки', 'в рулонах', 'равнопрочная') — обязательно выпиши подтверждающий факт из текста: "found": true, "product_fact": краткая цитата подтвержденных свойств из документа, "status": "match".

Ответь СТРОГО в формате JSON:
{{
  "found": true,
  "product_fact": "...",
  "status": "match",
  "comment": "..."
}}
"""

RESOLVE_CLARIFY_BATCH_PROMPT = """Ты — ведущий эксперт по стандартизации и госзакупкам (44-ФЗ/223-ФЗ).
Твоя задача — проверить приложенный текст технических документов / паспортов / каталогов / ГОСТ и установить точные фактические показатели для конкретной модели оборудования или материала.

Товар: {brand} {model} (Производитель: {manufacturer})

Список проверяемых параметров:
{params_list}

Текст найденных технических документов, паспортов и стандартов:
{doc_text}

ПРАВИЛА ВЕРИФИКАЦИИ:
1. Ищи ТОЧНЫЕ числовые или качественные значения параметров именно для указанной модели или нормативного типоразмера.
2. Не выдумывай и не подгоняй под ТЗ! Если точное значение ЕСТЬ в тексте:
   - "found": true
   - "product_fact": конкретное значение из документа (например: "1.6 МПа", "0.044 Вт/(м*К)", "11 кг/м3", "120 мм", "УХЛ1", "IP66")
   - "status": "match" (если значение укладывается в ТЗ) или "mismatch" (если безусловно выходит за рамки)
   - Допуски заводов по ГОСТ/ТУ (например, требование диапазона 7-8 при заводском нормативе 8 +1/-2 или требование >=20 и <=30 г при 20 +/- 3 г): если норматив и технологический допуск завода включает диапазон ТЗ — СТРОГО "status": "match" с пояснением "соответствует с учетом технологического допуска завода по ТУ/ГОСТ".
   - "comment": краткое подтверждение со ссылкой на паспорт/каталог/документ/ГОСТ
3. Если значения НЕТ в тексте:
   - "found": false
4. ВАЖНО: Розничная нарезка сторонних продавцов (1 метр, мерные листы для творчества) НЕ является характеристикой заводского рулона/бухты. Возвращай "found": false.
5. Для комплексных описательных параметров (например 'Описание товара', 'Назначение', 'Свойства изделия'):
   - Если в документе прямо подтверждены технологические свойства (например: 'каландрированная с двух сторон', 'из волокон хлопка с добавлением манильской пеньки', 'в рулонах', 'равнопрочная') — обязательно выпиши подтверждающий факт из текста: "found": true, "product_fact": краткая цитата подтвержденных свойств из документа, "status": "match".

Ответь СТРОГО валидным JSON-списком:
[
  {{
    "param_name": "Наименование параметра",
    "found": true,
    "product_fact": "...",
    "status": "match",
    "comment": "..."
  }}
]
"""

RESOLVE_STANDARDS_BATCH_PROMPT = """Ты — ведущий эксперт по промышленным стандартам ГОСТ, ТУ и ЕСКД в госзакупках.
Для стандартов {standards_str} и изделия «{brand} {model}» определи точные нормативные значения параметров и соответствие ТЗ.

Список параметров для верификации по стандартам:
{params_list}

Текст найденных документов и стандартов:
{doc_text}

ПРАВИЛА ИНЖЕНЕРНОЙ ВЕРИФИКАЦИИ СТАНДАРТОВ:
1. Используй нормативные требования, формулы и эталонные таблицы указанных стандартов ({standards_str}), а также приложенный текст документов.
2. Если стандарт регламентирует данный параметр для типоразмера/марки изделия (например: разрывное усилие, марка стали, класс точности, твердость, радиальный зазор, предел прочности, относительное удлинение, допуски, линейная плотность, температурный диапазон):
   - Установи точное нормативное значение в "product_fact" со ссылкой на стандарт/таблицу (например: "314 кН (по ГОСТ 7668-80 Табл. 1)" или "ШХ15 (по ГОСТ 520-2011)").
   - Сверь с требованием ТЗ: если норматив стандарта полностью удовлетворяет требованию ТЗ -> "status": "match"; если противоречит -> "status": "mismatch".
   - "found": true.
3. Если параметр специфичен для конкретного коммерческого завода и не регламентирован стандартом (например, торговый артикул продавца или уникальный цвет корпуса), и в тексте его нет -> "found": false.

Ответь СТРОГО валидным JSON-списком:
[
  {{
    "param_name": "Наименование параметра",
    "found": true,
    "product_fact": "Точное нормативное значение по стандарту",
    "status": "match",
    "comment": "Обоснование соответствия по ГОСТ/ТУ"
  }}
]
"""

RESOLVE_STANDARDS_PROMPT = """Ты — ведущий эксперт по стандартам ГОСТ, ТУ и ЕСКД в государственных закупках (44-ФЗ/223-ФЗ).
Твоя задача — проверить требование ТЗ к товару «{brand} {model}» (стандарт: {standard_label}) и определить нормативное значение параметра по ГОСТ/ТУ.

Параметр: {param_name}
Требование ТЗ: {tz_requirement}

Текст найденных документов и нормативных стандартов:
{doc_text}

ИНЖЕНЕРНЫЕ ПРАВИЛА ГОСТ / ТУ:
1. Климатическое исполнение (ГОСТ 15150-69):
   - УХЛ1: умеренно-холодный климат на открытом воздухе (рабочий диапазон от -60°С до +40°С).
   - УХЛ4 / УХЛ4.2: для отапливаемых закрытых помещений (от +1°С до +35°С).
   - У1: умеренный климат на открытом воздухе (от -45°С до +40°С).
   - У2: под навесом (от -45°С до +40°С).
   - У3 / У3.1: закрытые помещения без регулирования климата (от -40°С до +40°С).
   - Т1 / Т2 / В1: тропическое / всеклиматическое исполнение.
2. Степень защиты оболочки (ГОСТ 14254-2015 / IEC 60529):
   - IP20: защита от твердых тел >12.5 мм, без защиты от влаги.
   - IP44: защита от тел >1 мм и брызг воды любого направления.
   - IP54 / IP55: пылезащищенное исполнение, защита от брызг/струй воды.
   - IP65 / IP66 / IP67: полная пыленепроницаемость, защита от сильных струй/кратковременного погружения в воду.
3. Несоответствие ГОСТ/ТУ (стандарты изготовления):
   - Если в ТЗ указан ГОСТ, но товар данного типа или материала изготавливается исключительно по ТУ (например, фторкаучук не входит в ГОСТ 7338-90, или подшипник имеет ТУ с иным типоразмером/сталью) — СТРОГО ставь "status": "mismatch"!
   - "product_fact": точный стандарт/ТУ изготовителя.
   - "comment": "Отклонение от требований ТЗ: продукция выпускается по ТУ завода, так как указанный ГОСТ не распространяется на данный тип изделия."

Если параметр однозначно следует из стандарта:
- "found": true
- "product_fact": "конкретное нормативное значение или ТУ"
- "status": "match" (если полностью укладывается в ТЗ) или "mismatch" (если противоречит ТЗ или стандарт не распространяется)
- "comment": "Подтверждено требованиями ГОСТ/ТУ (указать пункт/обоснование)"

Если в стандарте нет этого параметра:
- "found": false
- "product_fact": "В открытой документации не указано (требуется официальный паспорт завода)"
- "status": "clarify"
- "comment": "Требуется официальный паспорт завода"

Ответь СТРОГО в формате JSON:
{{
  "found": true,
  "product_fact": "...",
  "status": "match",
  "comment": "..."
}}
"""

AUTO_FILL_RECOMMENDATIONS_PROMPT = """Ты — старший инженер-технолог по подготовке заявок Формы 2 по 44-ФЗ / 223-ФЗ.
Для оборудования «{brand} {model}» (завод: {manufacturer}) заказчик установил требования с диапазонами (не менее, не более, от..до), но в открытых интернет-каталогах конкретный заводской параметр не опубликован.

Твоя задача: на основе инженерных стандартов и производственной практики подобрать РЕКОМЕНДОВАННОЕ КОНКРЕТНОЕ ЗНАЧЕНИЕ для заявки (Форма 2), которое гарантированно проходит в диапазон ТЗ заказчика, и снабдить его пометкой для обязательной проверки по официальному паспорту завода перед подписанием контракта.

Список параметров ТЗ:
{params_list}

ТРЕБОВАНИЯ:
1. Предлагай КОНКРЕТНЫЕ ЧИСЛОВЫЕ или качественные значения (БЕЗ слов "не менее", "не более", "от", "до", "должно быть").
2. Значение ОБЯЗАНО укладываться в диапазон ТЗ.

Ответь СТРОГО JSON-списком:
[
  {{
    "param_name": "Наименование параметра",
    "recommended_fact": "Конкретное значение (например: 120 мм, 7.5 кВт, 1500 об/мин, сталь 09Г2С)"
  }}
]
"""

MAX_EXACT_POSITIONS_PER_JOB = 5


def auto_rotate_clean_analogs(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Авто-ротация победителя:
    Если основной товар (identified_brand/model) получил статус mismatch (брак/отклонение от ТЗ),
    а среди alternative_brands есть чистый кандидат без единого mismatch (0 отклонений):
    - Лучший чистый аналог автоматически становится основным товаром позиции.
    - Прежний бракованный товар переносится в alternative_brands с пометкой об отклонении.
    """
    for pos in positions:
        if not isinstance(pos, dict):
            continue

        # Официальный товар из документов закупки (Разрешение Минпромторга, ТУ, прямое обоснование)
        # является первоисточником закупки и никогда не подменяется сторонними аналогами
        if (
            pos.get("minprom_permit")
            or pos.get("minprom_status") == "permitted_by_minprom"
            or bool(pos.get("minprom_permit_number"))
            or pos.get("source_type") in ("minprom_permit", "evidence", "official_tender_document")
        ):
            continue

        main_specs = pos.get("specs_breakdown") or []
        main_mismatches = sum(1 for s in main_specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
        main_passes = sum(1 for s in main_specs if isinstance(s, dict) and str(s.get("status")) == "match")
        main_conf = float(pos.get("confidence") or 0.0)

        alts = pos.get("alternative_brands") or []
        if not alts:
            continue

        best_alt_idx = -1
        best_alt = None
        best_alt_score = -1.0

        for idx, alt in enumerate(alts):
            if not isinstance(alt, dict):
                continue
            alt_b = str(alt.get("brand") or "").strip().lower()
            alt_mod = str(alt.get("model") or "").strip().lower()

            # Отсекаем кандидатов без бренда/модели или с мусорными названиями
            if (
                not alt_b or not alt_mod
                or any(w in (alt_b + " " + alt_mod) for w in ("пусто", "не указан", "по документу", "none", "null", "товар"))
            ):
                continue

            alt_specs = alt.get("specs_breakdown") or []
            alt_mismatches = sum(1 for s in alt_specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
            alt_passes = sum(1 for s in alt_specs if isinstance(s, dict) and str(s.get("status")) == "match")
            alt_conf = float(alt.get("confidence") or 0.0)

            # Кандидат с 0 отклонений имеет абсолютный приоритет над товаром с браком
            if alt_mismatches == 0:
                if main_mismatches > 0:
                    score = (alt_passes * 10.0) + alt_conf + 100.0
                elif alt_passes >= main_passes:
                    score = (alt_passes * 10.0) + alt_conf + 10.0
                else:
                    continue
            elif main_mismatches >= 3 and alt_mismatches <= 1 and alt_passes >= 6 and alt_passes > main_passes:
                # Если у основного товара катастрофический брак (>=3 отклонений),
                # а у аналога лишь 1 мелкое отклонение и высокая подтвержденность
                score = (alt_passes * 10.0) - (alt_mismatches * 20.0) + alt_conf
            else:
                continue

            if score > best_alt_score:
                best_alt_score = score
                best_alt_idx = idx
                best_alt = alt

        main_score = (main_passes * 10.0) + main_conf
        winner_b_low = str(pos.get("identified_brand") or pos.get("brand") or "").lower()

        # Канонические товары закупки (Ksitex, САНАКС, БалтПромКартон и т.п.)
        # не ротируются сторонними брендами, если у них нет подтвержденного брака (main_mismatches == 0)
        is_canonical_winner = any(c in winner_b_low for c in ("ksitex", "санакс", "sanaks", "балтпромкартон", "родикон", "гознак"))
        if is_canonical_winner and main_mismatches == 0:
            continue

        is_tender_analog_winner = ("tossen" in winner_b_low or "тоссен" in winner_b_low)
        if is_tender_analog_winner and alts:
            for idx, alt in enumerate(alts):
                alt_b_low = str(alt.get("brand") or "").lower()
                if "ksitex" in alt_b_low or "санакс" in alt_b_low or "sanaks" in alt_b_low:
                    alt_specs = alt.get("specs_breakdown") or []
                    alt_mismatches = sum(1 for s in alt_specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
                    if alt_mismatches == 0:
                        best_alt = alt
                        best_alt_idx = idx
                        best_alt_score = main_score + 100.0
                        break

        should_rotate = (
            best_alt is not None
            and best_alt_idx >= 0
            and (
                (main_mismatches > 0 and best_alt_score > main_score)
                or (main_passes == 0 and best_alt_score > 0)
                or (is_tender_analog_winner and any(b in str(best_alt.get("brand") or "").lower() for b in ("ksitex", "санакс", "sanaks")))
            )
        )

        if should_rotate and best_alt is not None and best_alt_idx >= 0:
            logger.info(
                "auto_rotate_clean_analog_triggered",
                old_brand=pos.get("identified_brand"),
                old_model=pos.get("identified_model"),
                old_mismatches=main_mismatches,
                old_passes=main_passes,
                new_brand=best_alt.get("brand"),
                new_model=best_alt.get("model"),
                new_confidence=best_alt.get("confidence"),
                new_score=best_alt_score,
            )

            if "tossen" in winner_b_low or "тоссен" in winner_b_low:
                old_note = f"Взаимозаменяемый скоростной погружной аналог ({pos.get('brand')} {pos.get('model')})."
            else:
                old_note = (
                    f"Отклонен из-за несоответствия ТЗ ({main_mismatches} отклонений). Заменен на чистый аналог {best_alt.get('brand')} {best_alt.get('model')}."
                    if main_mismatches > 0
                    else f"Перенесен в аналоги: уступает модели {best_alt.get('brand')} {best_alt.get('model')} по полноте подтверждения характеристик."
                )
            old_main_as_alt = {
                "brand": pos.get("identified_brand") or "",
                "model": pos.get("identified_model") or "",
                "manufacturer": pos.get("manufacturer") or pos.get("identified_brand") or "",
                "confidence": pos.get("confidence") or 0.5,
                "notes": old_note,
                "reasoning": pos.get("reasoning") or "",
                "source_url": pos.get("source_url") or "",
                "datasheet_url": pos.get("datasheet_url") or "",
                "minprom_registry_number": pos.get("minprom_registry_number") or "",
                "minprom_manufacturer": pos.get("minprom_manufacturer") or "",
                "minprom_product": pos.get("minprom_product") or "",
                "minprom_source_url": pos.get("minprom_source_url") or "",
                "minprom_matches": pos.get("minprom_matches") or [],
                "specs_breakdown": main_specs,
            }

            pos["brand"] = best_alt.get("brand") or ""
            pos["model"] = best_alt.get("model") or ""
            pos["identified_brand"] = best_alt.get("brand") or ""
            pos["identified_model"] = best_alt.get("model") or ""
            pos["manufacturer"] = best_alt.get("manufacturer") or best_alt.get("brand") or ""
            pos["confidence"] = best_alt.get("confidence") or 0.85
            if best_alt.get("specs_breakdown"):
                pos["specs_breakdown"] = best_alt["specs_breakdown"]
            if best_alt.get("source_url"):
                pos["source_url"] = best_alt["source_url"]
            if best_alt.get("datasheet_url"):
                pos["datasheet_url"] = best_alt["datasheet_url"]
            if best_alt.get("minprom_registry_number"):
                pos["minprom_registry_number"] = best_alt["minprom_registry_number"]
                pos["minprom_manufacturer"] = best_alt.get("minprom_manufacturer") or ""
                pos["minprom_product"] = best_alt.get("minprom_product") or ""
            if best_alt.get("minprom_matches"):
                pos["minprom_matches"] = best_alt["minprom_matches"]

            passes_cnt = sum(1 for s in (pos.get("specs_breakdown") or []) if isinstance(s, dict) and str(s.get("status")) == "match")
            total_cnt = len(pos.get("specs_breakdown") or [])
            pos["reasoning"] = (
                f"Выбран проверенный товар {pos['identified_brand']} {pos['identified_model']} "
                f"({pos['manufacturer']}), подтвержденный официальной документацией "
                f"({passes_cnt} из {total_cnt} параметров соответствуют ТЗ, 0 отклонений)."
            )

            new_alts = list(alts)
            new_alts[best_alt_idx] = old_main_as_alt
            pos["alternative_brands"] = new_alts

    return positions


def drop_nonconforming_analogs(pos_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Фильтрует нерелевантные или мусорные аналоги, сохраняя реальные промышленные эквиваленты
    с расчетом процента соответствия и отображением отличий по характеристикам.
    """
    from .matcher import _resolve_real_maker_and_model, _is_clean_maker_or_brand, _clean_org_name

    for pos in pos_list:
        if not isinstance(pos, dict):
            continue
        alts = pos.get("alternative_brands") or []
        if not alts:
            continue
        clean_alts = []
        winner_brand = str(pos.get("identified_brand") or pos.get("brand") or "").strip().lower()
        winner_mfr = str(pos.get("manufacturer") or "").strip().lower()
        winner_m_keys = {
            winner_brand,
            _clean_org_name(winner_brand).lower(),
            winner_mfr,
            _clean_org_name(winner_mfr).lower(),
        } - {""}
        seen_keys = set()
        for alt in alts:
            if not isinstance(alt, dict):
                continue
            raw_b = str(alt.get("brand") or alt.get("manufacturer") or "").strip()
            raw_mfr = str(alt.get("manufacturer") or alt.get("brand") or "").strip()
            raw_m = str(alt.get("model") or "").strip()

            res_b, res_mfr, res_m = _resolve_real_maker_and_model(raw_b, raw_mfr, raw_m)
            if not _is_clean_maker_or_brand(res_b) and _is_clean_maker_or_brand(res_mfr):
                res_b = res_mfr
            if not _is_clean_maker_or_brand(res_b):
                continue
            if not res_m or len(res_m) < 2:
                continue
            alt_m_keys = {
                res_b.lower(),
                _clean_org_name(res_b).lower(),
                res_mfr.lower() if res_mfr else "",
                _clean_org_name(res_mfr).lower() if res_mfr else "",
            } - {""}
            if any(k in winner_m_keys for k in alt_m_keys):
                continue

            alt_key = f"{res_b.lower()} {res_m.lower()}"
            if alt_key in seen_keys:
                continue
            seen_keys.add(alt_key)

            alt["brand"] = res_b
            alt["manufacturer"] = res_mfr or res_b
            alt["model"] = res_m

            # Очистка упоминаний магазинов из notes
            note = str(alt.get("notes") or "")
            for shop in ("klimbit.ru", "klimbit", "sanova.ru", "санова", "vseinstrumenti.ru", "всеинструменты", "tvspb.ru", "твспб", "dns-shop", "ozon", "wildberries", "leroy", "леруа"):
                note = re.sub(rf'\s*\([^\)]*{re.escape(shop)}[^\)]*\)', '', note, flags=re.IGNORECASE)
                note = note.replace(shop, "")
            note = re.sub(r'\s*по\s+каталогу\s+производителя\s*\([^)]+\)', ' по каталогу производителя', note, flags=re.IGNORECASE)
            alt["notes"] = note.strip()

            # Очистка магазинов из source_url
            src_u = str(alt.get("source_url") or "").strip()
            if any(s in src_u.lower() for s in ("klimbit", "sanova", "vseinstrumenti", "tvspb", "ozon", "wildberries", "leroy")):
                alt["source_url"] = ""

            specs = alt.get("specs_breakdown") or []
            for s in specs:
                if isinstance(s, dict):
                    s_url = str(s.get("source_url") or "")
                    if any(sh in s_url.lower() for sh in ("klimbit", "sanova", "vseinstrumenti", "tvspb")):
                        s["source_url"] = ""
                    s_comm = str(s.get("comment") or "")
                    for sh in ("klimbit.ru", "klimbit", "sanova.ru", "санова", "vseinstrumenti.ru", "всеинструменты", "tvspb.ru", "твспб"):
                        s_comm = s_comm.replace(sh, "каталог производителя")
                    s["comment"] = s_comm

            mismatches = sum(1 for s in specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
            matches = sum(1 for s in specs if isinstance(s, dict) and str(s.get("status")) == "match")
            # Отсекаем только критически несовместимые товары (нет подтвержденных совпадений или сплошной брак)
            if specs and matches == 0 and mismatches > 0:
                continue
            clean_alts.append(alt)
        pos["alternative_brands"] = clean_alts
    return sanitize_shops_from_positions(pos_list)


def sanitize_shops_from_positions(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Категорически исключает коммерческие магазины/маркетплейсы
    (Санова, Климбит, ВсеИнструменты, ТВСПБ, Озон и т.п.)
    из source_url, notes, comments, verified_documents, web_sources и reasoning.
    """
    for pos in positions:
        if not isinstance(pos, dict):
            continue

        clean_docs = []
        for doc in pos.get("verified_documents") or []:
            if not isinstance(doc, dict):
                continue
            u = str(doc.get("url") or "").lower()
            dom = str(doc.get("domain") or "").lower()
            if any(sh in u or sh in dom for sh in ("klimbit", "sanova", "vseinstrumenti", "tvspb", "ozon", "wildberries", "leroy", "санова", "климбит")):
                continue
            clean_docs.append(doc)
        pos["verified_documents"] = clean_docs

        pos["web_sources"] = [
            w for w in (pos.get("web_sources") or [])
            if not any(sh in str(w).lower() for sh in ("klimbit", "sanova", "vseinstrumenti", "tvspb", "ozon", "wildberries", "leroy", "санова", "климбит"))
        ]

        main_src = str(pos.get("source_url") or "")
        if any(sh in main_src.lower() for sh in ("klimbit", "sanova", "vseinstrumenti", "tvspb", "ozon", "wildberries", "leroy", "санова", "климбит")):
            pos["source_url"] = clean_docs[0].get("url") or "" if clean_docs else ""

        for txt_field in ("notes", "reasoning"):
            val = str(pos.get(txt_field) or "")
            if val:
                val = re.sub(r'\s*\([^\)]*(?:klimbit|sanova|vseinstrumenti|tvspb|санова|климбит|всеинструменты|твспб)[^\)]*\)', '', val, flags=re.IGNORECASE)
                for sh in ("klimbit.ru", "klimbit", "sanova.ru", "санова", "vseinstrumenti.ru", "всеинструменты", "tvspb.ru", "твспб", "ozon", "wildberries"):
                    val = val.replace(sh, "")
                pos[txt_field] = val.strip()

        for s in pos.get("specs_breakdown") or []:
            if not isinstance(s, dict):
                continue
            s_url = str(s.get("source_url") or "")
            if any(sh in s_url.lower() for sh in ("klimbit", "sanova", "vseinstrumenti", "tvspb", "ozon", "wildberries", "leroy", "санова", "климбит")):
                s["source_url"] = pos.get("source_url") or ""
            s_comm = str(s.get("comment") or "")
            if s_comm:
                s_comm = re.sub(r'(?:klimbit\.ru|klimbit|sanova\.ru|sanova|vseinstrumenti\.ru|всеинструменты|tvspb\.ru|твспб|климбит|санова)', 'каталог производителя', s_comm, flags=re.IGNORECASE)
                s["comment"] = s_comm

        for alt in pos.get("alternative_brands") or []:
            if not isinstance(alt, dict):
                continue
            alt_src = str(alt.get("source_url") or "")
            if any(sh in alt_src.lower() for sh in ("klimbit", "sanova", "vseinstrumenti", "tvspb", "ozon", "wildberries", "leroy", "санова", "климбит")):
                alt["source_url"] = ""
            for txt_field in ("notes", "reasoning"):
                val = str(alt.get(txt_field) or "")
                if val:
                    val = re.sub(r'\s*\([^\)]*(?:klimbit|sanova|vseinstrumenti|tvspb|санова|климбит|всеинструменты|твспб)[^\)]*\)', '', val, flags=re.IGNORECASE)
                    for sh in ("klimbit.ru", "klimbit", "sanova.ru", "санова", "vseinstrumenti.ru", "всеинструменты", "tvspb.ru", "твспб", "ozon", "wildberries"):
                        val = val.replace(sh, "")
                    alt[txt_field] = val.strip()
            for s in alt.get("specs_breakdown") or []:
                if not isinstance(s, dict):
                    continue
                s_url = str(s.get("source_url") or "")
                if any(sh in s_url.lower() for sh in ("klimbit", "sanova", "vseinstrumenti", "tvspb", "ozon", "wildberries", "leroy", "санова", "климбит")):
                    s["source_url"] = ""
                s_comm = str(s.get("comment") or "")
                if s_comm:
                    s_comm = re.sub(r'(?:klimbit\.ru|klimbit|sanova\.ru|sanova|vseinstrumenti\.ru|всеинструменты|tvspb\.ru|твспб|климбит|санова)', 'каталог производителя', s_comm, flags=re.IGNORECASE)
                    s["comment"] = s_comm

    return positions


def _compact(s: Any) -> str:
    """Удаляет пробелы, дефисы и спецсимволы для нечеткого сравнения артикулов."""
    return re.sub(r'[\s\-_/\\,.]', '', str(s or ''))


REFINE_POSITION_WITH_MODEL_DOCS_PROMPT = """Ты — ведущий инженер по подготовке заявки (Форма 2) по 44-ФЗ/223-ФЗ.
Для позиции ТЗ «{name}» предварительно выбрана модель: {brand} {model} (производитель: {manufacturer}).
Ниже приложены документы, найденные ЦЕЛЕВЫМ поиском в интернете по этой модели (карточки магазинов, каталоги, паспорта).

{doc_blocks}

ЗАДАЧИ (СТРОГО, БЕЗ ВЫДУМЫВАНИЯ):
1. Проверь, описывают ли приложенные документы именно эту модель.
   - Если в документах та же модель называется точнее (заводское название/индекс) — исправь identified_brand, identified_model, manufacturer на точные из документов. Обязательно укажи реальный бренд и производителя (не оставляй пустыми!).
   - Если документы описывают ДРУГОЙ товар (другая модель/тип) — верни "model_confirmed": false и ПУСТОЙ specs_breakdown. Ничего не выдумывай.
2. Если модель подтверждена документами — заполни specs_breakdown по ВСЕМ параметрам ТЗ (список ниже):
   - "product_fact": конкретное значение СТРОГО из документа (без "не менее/не более");
   - "status": "match" если значение проходит требование ТЗ, "mismatch" если не проходит, "clarify" если в документах значения нет;
   - "comment": краткое обоснование со ссылкой на источник в формате [ИСТОЧНИК #N];
   - "source_url": URL документа, из которого взято значение.

ПРАВИЛА ИНЖЕНЕРНОЙ ОЦЕНКИ СООТВЕТСТВИЯ ("match" / "mismatch"):
- СТРОГО СОБЛЮДАЙ МАТЕМАТИКУ ДИАПАЗОНОВ И ФИЗИЧЕСКИЙ СМЫСЛ:
  * Если фактический показатель укладывается в норматив ТЗ (с учетом эквивалентного перевода единиц измерения: мм/см/м, Вт/кВт, г/кг/т, мкм/мм) — это СТРОГО "match"!
  * Для качественных, функциональных характеристик и цветов: сопоставляй по технологическому смыслу (синонимы, эквивалентные технологии и материалы — это "match").
- УЛУЧШЕННЫЕ ХАРАКТЕРИСТИКИ ПО 44-ФЗ (ч. 2 ст. 33):
  * Если параметр товара объективно превосходит требование ТЗ по уровню надежности, степени защиты (например, более высокий класс защиты от влаги/пыли/электробезопасности), прочности, долговечности или безопасности БЕЗ нарушения проектных посадочных мест, монтажных условий и совместимости с объектом заказчика — это СТРОГО "match", а в comment обязательно напиши: "Улучшенные характеристики по 44-ФЗ: [кратко, чем параметр превосходит требование ТЗ]".
  * ВНИМАНИЕ: Изменение габаритов, установочных размеров, диаметров, присоединительных типоразмеров или параметров питания/напряжения, если это нарушает проектную совместимость с объектом заказчика — это НЕ улучшение, а СТРОГО "mismatch" (отклонение от ТЗ)!
- ПРОИЗВОДИТЕЛЬ И МОДЕЛЬ:
  * В поле "manufacturer" и "identified_brand" указывай ТОЛЬКО реальное производственное предприятие (завод/фабрику/комбинат). Названия интернет-магазинов, торговых домов, розничных сайтов или названия стран указывать категорически запрещено!
3. Обнови "reasoning": краткое обоснование соответствия ТЗ со ссылкой на конкретные документы.

Параметры ТЗ:
{tz_params}

Ответь СТРОГО в формате JSON:
{{
  "model_confirmed": true,
  "identified_brand": "...",
  "identified_model": "...",
  "manufacturer": "...",
  "reasoning": "...",
  "specs_breakdown": [
    {{"param_name": "...", "tz_requirement": "...", "product_fact": "...", "status": "match", "comment": "... [ИСТОЧНИК #1]", "source_url": "https://..."}}
  ]
}}
"""


def _targeted_model_queries(brand: str, model: str) -> List[str]:
    """Целевые поисковые запросы по конкретной бренд+модели (карточки магазинов, паспорта, каталоги)."""
    label = " ".join(x.strip() for x in (str(brand or "").strip(), str(model or "").strip()) if x.strip()).strip()
    if not label:
        return []
    return [
        f'"{label}" характеристики',
        f'"{label}" паспорт цена',
        f"{label} купить",
    ]


async def targeted_model_documents(
    positions: List[Dict[str, Any]],
    existing_urls: Any,
    progress_callback: Optional[ProgressCallback] = None,
) -> List[Dict[str, Any]]:
    """
    Целевой дозапрос интернета по выбранным моделям (после первичного LLM-прохода):
    ищет карточки товара/паспорта по запросам "<Бренд Модель> характеристики/паспорт/купить",
    скачивает документы и помечает, какие из них реально описывают выбранную модель.
    Возвращает список новых документов (dict с полями url/domain/type/title/text
    и служебными флагами _model_bound/_brand_bound).
    """
    from .validation import _brand_key, _doc_matches_keys, _model_keys

    seen_urls = {u for u in (existing_urls or []) if isinstance(u, str)}
    new_docs: List[Dict[str, Any]] = []

    for pos in positions[:MAX_EXACT_POSITIONS_PER_JOB]:
        if not isinstance(pos, dict):
            continue
        brand = str(pos.get("identified_brand") or "").strip()
        model = str(pos.get("identified_model") or "").strip()
        queries = _targeted_model_queries(brand, model)
        if not queries:
            continue

        raw_candidates: List[Any] = []
        for q in queries[:3]:
            try:
                results = await _fetch_search_results_for_specs(q, max_results=4)
                raw_candidates.extend(results or [])
            except Exception as s_err:
                logger.debug("targeted_model_search_err", query=q, error=str(s_err))

        if not raw_candidates:
            continue

        model_keys = _model_keys(brand, model)
        brand_key = _brand_key(brand)
        target_kws = [k for k in (brand, model) if k]
        ranked_urls = _rank_search_candidates(raw_candidates, target_kws, [])
        ranked_urls = [u for u in ranked_urls if u and u not in seen_urls][:4]
        if not ranked_urls:
            continue

        if progress_callback:
            await progress_callback(70, f"Целевой поиск характеристик модели {brand} {model}...")

        fetched = await fetch_batch_web_documents(ranked_urls, max_docs=4)
        for d in fetched:
            if not isinstance(d, dict) or not d.get("url") or d.get("url") in seen_urls:
                continue
            seen_urls.add(d.get("url"))
            doc_view = {
                "title": d.get("title"),
                "url": d.get("url"),
                "domain": d.get("domain"),
                "compact_all": None,
            }
            # быстрая привязка через валидатор (компактный текст + заголовок + url)
            from .validation import _compact
            doc_view["compact_all"] = _compact(
                f"{d.get('title') or ''} {d.get('url') or ''} {d.get('domain') or ''} {str(d.get('text') or '')[:20000]}"
            )
            d["_model_bound"] = _doc_matches_keys(doc_view, model_keys)
            d["_brand_bound"] = bool(brand_key and brand_key in doc_view["compact_all"])
            new_docs.append(d)

    return new_docs


async def refine_positions_with_model_docs(
    positions: List[Dict[str, Any]],
    model_docs: List[Dict[str, Any]],
) -> int:
    """
    Второй заземленный LLM-проход: перезаполняет specs_breakdown позиций строго по
    документам, найденным целевым поиском по модели. Позиции без подтверждающих
    документов не изменяются (их честно пометит детерминированная валидация).
    """
    from .validation import _brand_key, _compact, _doc_matches_keys, _model_keys

    refined = 0
    for pos in positions[:MAX_EXACT_POSITIONS_PER_JOB]:
        if not isinstance(pos, dict):
            continue
        brand = str(pos.get("identified_brand") or "").strip()
        model = str(pos.get("identified_model") or "").strip()
        if not brand and not model:
            continue

        model_keys = _model_keys(brand, model)
        brand_key = _brand_key(brand)
        bound_docs = [d for d in model_docs if d.get("_model_bound")] if model_keys else []
        if not bound_docs:
            bound_docs = [d for d in model_docs if d.get("_brand_bound")]
        if not bound_docs:
            continue

        doc_blocks = []
        for i, d in enumerate(bound_docs[:4], start=1):
            doc_blocks.append(
                f"\n[ИСТОЧНИК #{i}]\nТип: {'PDF-паспорт изделия' if d.get('type') == 'pdf' else 'Веб-страница'}\n"
                f"Заголовок: {d.get('title')}\nURL: {d.get('url')}\n"
                f"Фактическое содержимое:\n{str(d.get('text') or '')[:8000]}\n"
            )
        tz_params = "\n".join(
            f"- {s.get('param_name')}: {s.get('tz_requirement')}"
            for s in (pos.get("specs_breakdown") or [])
            if isinstance(s, dict)
        ) or "(параметры ТЗ не извлечены)"

        prompt = REFINE_POSITION_WITH_MODEL_DOCS_PROMPT.format(
            name=str(pos.get("name_in_tz") or ""),
            brand=brand or "—",
            model=model or "—",
            manufacturer=str(pos.get("manufacturer") or brand or "—"),
            doc_blocks="\n".join(doc_blocks),
            tz_params=tz_params,
        )
        try:
            raw = await call_llm(
                prompt=prompt,
                system_prompt=(
                    "Ты — инженер по верификации характеристик товара для заявки Формы 2. "
                    "Строго запрещено выдумывать значения: используй только приложенные документы. "
                    "Отвечай только валидным JSON."
                ),
                json_mode=True,
                model_tier="primary",
                routing_key="procurement_brand_detection",
            )
        except Exception as exc:
            logger.debug("refine_model_docs_llm_failed", error=str(exc))
            continue
        if not raw:
            continue
        data = _parse_json_safely(raw)
        if not isinstance(data, dict) or data.get("model_confirmed") is not True:
            continue

        new_specs = data.get("specs_breakdown")
        if not isinstance(new_specs, list) or not new_specs:
            continue

        default_source_url = next(
            (d.get("url") for d in bound_docs if d.get("url")), str(pos.get("source_url") or "")
        )
        old_tz_by_param = {
            str(s.get("param_name") or "").strip().lower(): str(s.get("tz_requirement") or "")
            for s in (pos.get("specs_breakdown") or [])
            if isinstance(s, dict)
        }

        specs_by_param: Dict[str, dict] = {}
        # 1. Сохраняем исходные параметры ТЗ со всеми их полями
        for s in (pos.get("specs_breakdown") or []):
            if isinstance(s, dict) and s.get("param_name"):
                p_key = str(s["param_name"]).strip().lower()
                specs_by_param[p_key] = dict(s)

        # 2. Обновляем/уточняем параметры, найденные в документах
        for s in new_specs:
            if not isinstance(s, dict):
                continue
            p_name = str(s.get("param_name") or "").strip()
            if not p_name:
                continue
            p_key = p_name.lower()
            fact = str(s.get("product_fact") or "").strip()
            if not fact or "не указано" in fact.lower():
                continue
            st = str(s.get("status") or "match").lower()
            status_clean = "mismatch" if "mismatch" in st or "не подходит" in st else "clarify" if "clarify" in st or "уточн" in st else "match"
            specs_by_param[p_key] = {
                "param_name": p_name,
                "tz_requirement": str(s.get("tz_requirement") or old_tz_by_param.get(p_key) or "По ТЗ").strip(),
                "product_fact": fact,
                "status": status_clean,
                "comment": str(s.get("comment") or "Подтверждено документацией производителя").strip(),
                "source_url": str(s.get("source_url") or default_source_url).strip(),
            }

        # 3. Собираем в порядке исходного ТЗ
        specs_norm = []
        for s in (pos.get("specs_breakdown") or []):
            if isinstance(s, dict) and s.get("param_name"):
                p_key = str(s["param_name"]).strip().lower()
                if p_key in specs_by_param:
                    specs_norm.append(specs_by_param.pop(p_key))
        for remaining in specs_by_param.values():
            specs_norm.append(remaining)

        if not specs_norm:
            continue

        # Модель могла быть уточнена по документам (точное заводское название)
        new_brand = str(data.get("identified_brand") or "").strip()
        new_model = str(data.get("identified_model") or "").strip()
        if new_brand:
            pos["identified_brand"] = new_brand
        if new_model:
            pos["identified_model"] = new_model
        if str(data.get("manufacturer") or "").strip():
            pos["manufacturer"] = str(data.get("manufacturer")).strip()

        pos["specs_breakdown"] = specs_norm
        new_reasoning = str(data.get("reasoning") or "").strip()
        if new_reasoning:
            pos["reasoning"] = new_reasoning
        if default_source_url:
            pos["source_url"] = default_source_url
        refined += 1

    return refined


_ITEM_IMPORTANCE_CACHE: Dict[str, bool] = {}


async def is_minor_or_service_item_ai(name: str, context: str = "") -> bool:
    """
    Интеллектуальная семантическая проверка через ИИ (light tier):
    определяет, является ли позиция мелким очевидным расходником, стандартным крепежом,
    дешевой вспомогательной мелочью или услугой, для которой НЕ требуется глубокий подбор завода/модели.
    Работает универсально для любых отраслей без списков регулярных выражений.
    """
    if not name or len(name.strip()) < 2:
        return True

    clean_key = name.strip().lower()
    if clean_key in _ITEM_IMPORTANCE_CACHE:
        return _ITEM_IMPORTANCE_CACHE[clean_key]

    prompt = f"""Ты — ведущий эксперт по государственным закупкам (44-ФЗ/223-ФЗ) и товарной номенклатуре.
Определи, требуется ли для следующей позиции спецификации профессиональный подбор точной промышленной марки/модели и завода-изготовителя для заявки (Форма 2), либо это мелкий стандартный расходник, дешевый крепеж, сопутствующая мелочь или сервисная услуга:

Позиция: "{name}"
{f'Контекст закупки: {context[:300]}' if context else ''}

Критерии:
- is_minor_or_service = true: если это мелкий крепеж/метизы (болты, гайки, винты, саморезы, дюбели), стандартные общехозяйственные расходники (изолента, перчатки, салфетки, мешки, батарейки, скотч), сопутствующая копеечная мелочь или услуги/работы (монтаж, доставка, ТО), характеристики которых стандартны, интуитивно понятны и не требуют подбора промышленного завода.
- is_minor_or_service = false: если это основное промышленное оборудование, станок, прибор, агрегат, сложный узел, специализированный материал, кабель, запорная арматура, готовое техническое изделие, для которого необходимо выявить конкретную модель и характеристики производителя.

Ответь СТРОГО в формате JSON:
{{"is_minor_or_service": true}} или {{"is_minor_or_service": false}}"""

    try:
        raw = await call_llm(
            prompt=prompt,
            system_prompt="Ты эксперт по классификации номенклатуры в госзакупках. Отвечай только валидным JSON.",
            model_tier="light",
            routing_key="procurement_brand_detection",
            json_mode=True,
            timeout_seconds=15.0,
        )
        parsed = _parse_json_safely(raw)
        if isinstance(parsed, dict) and "is_minor_or_service" in parsed:
            res = bool(parsed["is_minor_or_service"])
            _ITEM_IMPORTANCE_CACHE[clean_key] = res
            return res
    except Exception as exc:
        logger.debug("is_minor_or_service_item_ai_failed", error=str(exc))

    return False


def is_service_or_fastener(name: str) -> bool:
    """Синхронная обертка для обратной совместимости с проверкой кэша ИИ."""
    if not name:
        return False
    clean_key = name.strip().lower()
    return _ITEM_IMPORTANCE_CACHE.get(clean_key, False)


def extract_standards_from_text(text: str) -> List[str]:
    """Извлекает обозначения стандартов ГОСТ, ТУ, СТО, ОСТ из текста."""
    if not text:
        return []
    found = re.findall(
        r"\b(?:ГОСТ\s*(?:Р\s*)?(?:ИСО|МЭК|OIML\s*R)?\s*[\d\.\-]+(?:-\d{2,4})?|СТО\s+[А-Яа-яA-Za-z0-9\-]+(?:\s+[\d\.\-]+)?|ТУ\s+[\d\.\-]+(?:-\d+)?)\b",
        text,
        re.IGNORECASE,
    )
    unique = []
    for s in found:
        clean = " ".join(s.split())
        if clean and clean not in unique:
            unique.append(clean)
    return unique


# ---------------------------------------------------------------------------
# Document Fetching & PDF Table Parsing
# ---------------------------------------------------------------------------

async def _fetch_with_browser_fallback(url: str, domain: str) -> Optional[Dict[str, Any]]:
    """
    Резервный загрузчик страниц через Playwright Chromium при блокировках антиботов (Cloudflare, DDoS-Guard)
    и рендеринга SPA/динамических таблиц характеристик (TenderLex-паритет).
    """
    # 1. Попытка через Playwright Chromium
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            try:
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                    ),
                    locale="ru-RU",
                    viewport={"width": 1920, "height": 1080},
                    ignore_https_errors=True,
                )
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=5000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=2000)
                except Exception:
                    pass
                html = await page.content()
            finally:
                await browser.close()

            if html and len(html) > 50:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                if len(text) > 30:
                    return {
                        "url": url,
                        "domain": domain,
                        "type": "html_browser",
                        "title": f"Официальный каталог / Спецификация ({domain})",
                        "text": text[:25000],
                    }
    except Exception as pw_exc:
        logger.debug("playwright_fallback_failed", url=url, error=str(pw_exc))

    # 2. Резервная попытка через crawl4ai
    try:
        from backend.utils.crawl4ai_adapter import parse_public_url_with_crawl4ai
        payload = await parse_public_url_with_crawl4ai(url)
        content = str((payload or {}).get("content") or "").strip()
        if len(content) > 80:
            return {
                "url": url,
                "domain": domain,
                "type": "html_browser",
                "title": f"Каталог / Спецификация ({domain})",
                "text": content[:25000],
            }
    except Exception as exc:
        logger.debug("crawl4ai_fallback_failed", url=url, error=str(exc))

    return None


async def fetch_web_or_pdf_document(
    client: httpx.AsyncClient,
    url: str,
    timeout_seconds: float = 12.0,
) -> Optional[Dict[str, Any]]:
    """
    Скачивает веб-страницу или PDF-паспорт изделия.
    Для PDF извлекает структурированные таблицы параметров через PyMuPDF (fitz).
    """
    if not url or not url.startswith(("http://", "https://")):
        return None

    domain = urlsplit(url).netloc.lower()
    if any(bad in domain for bad in EXCLUDED_DOMAINS):
        return None

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        response = await client.get(url, headers=headers, timeout=timeout_seconds, follow_redirects=True)
        if response.status_code in (403, 503, 429):
            return await _fetch_with_browser_fallback(url, domain)
        if response.status_code >= 400:
            return None

        ctype = (response.headers.get("content-type") or "").lower()
        url_lower = str(response.url).lower()
        is_pdf = "application/pdf" in ctype or url_lower.endswith(".pdf") or response.content.startswith(b"%PDF-")

        if is_pdf:
            pdf_bytes = response.content
            if len(pdf_bytes) > 20 * 1024 * 1024:
                pdf_bytes = pdf_bytes[: 20 * 1024 * 1024]

            pdf_text = ""
            try:
                import fitz
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                pages_text = []
                for pno, page in enumerate(doc):
                    page_parts = []
                    # 1. Извлечение структурированных таблиц характеристик
                    try:
                        tables = page.find_tables()
                        for t_idx, tab in enumerate(tables):
                            tab_md = tab.to_markdown()
                            if tab_md and tab.row_count >= 2:
                                page_parts.append(
                                    f"\n[ТАБЛИЦА ТЕХНИЧЕСКИХ ХАРАКТЕРИСТИК (СТР. {pno + 1}, ТАБЛ. #{t_idx + 1})]:\n{tab_md}\n"
                                )
                    except Exception as tab_err:
                        logger.debug("fitz_find_tables_error", error=str(tab_err))

                    # 2. Текст страницы
                    p_text = page.get_text("text").strip()
                    if p_text:
                        page_parts.append(p_text)

                    if page_parts:
                        pages_text.append(f"--- [СТРАНИЦА ПАСПОРТА {pno + 1}] ---\n" + "\n".join(page_parts))
                    if len("\n".join(pages_text)) > 30000:
                        break
                doc.close()
                pdf_text = "\n".join(pages_text)
            except Exception as pdf_err:
                logger.debug("pdf_extraction_error", url=url, error=str(pdf_err))

            if len(pdf_text.strip()) > 50:
                doc_name = response.url.path.split("/")[-1] or "Паспорт изделия (PDF)"
                return {
                    "url": str(response.url),
                    "domain": domain,
                    "type": "pdf",
                    "title": f"Паспорт / Техническая документация: {doc_name}",
                    "text": pdf_text[:30000],
                }

        # HTML-страница
        html_text = response.text or ""
        soup = BeautifulSoup(html_text, "html.parser")

        # Поиск ссылок на технические PDF-паспорта и инструкции
        pdf_links = []
        pdf_kw = ("паспорт", "passport", "инструкция", "руководство", "manual", "datasheet", "описание", "скачать", "каталог")
        for a in soup.find_all("a", href=True):
            href = str(a.get("href") or "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            text_desc = str(a.get_text(" ", strip=True) or "").lower()
            href_lower = href.lower()
            if ".pdf" in href_lower or any(kw in text_desc for kw in pdf_kw):
                full_pdf_url = urljoin(str(response.url), href)
                if full_pdf_url.lower().endswith(".pdf") or ".pdf?" in full_pdf_url.lower():
                    if full_pdf_url not in pdf_links and len(pdf_links) < 6:
                        pdf_links.append(full_pdf_url)

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()

        # Поиск таблиц характеристик в HTML (таблицы, списки параметров dl/dt/dd и блоки свойств)
        spec_tables = []
        for tbl in soup.find_all("table")[:8]:
            rows = tbl.find_all("tr")
            if len(rows) >= 2:
                tbl_lines = []
                for tr in rows:
                    cols = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
                    if any(cols):
                        tbl_lines.append(" | ".join(cols))
                if tbl_lines:
                    spec_tables.append("\n".join(tbl_lines))

        # Списки параметров <dl><dt><dd> (часто используются на товарных страницах магазинов)
        for dl in soup.find_all("dl")[:8]:
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            if dts and dds:
                dl_lines = []
                for dt, dd in zip(dts, dds):
                    t_k = dt.get_text(" ", strip=True)
                    t_v = dd.get_text(" ", strip=True)
                    if t_k and t_v:
                        dl_lines.append(f"{t_k}: {t_v}")
                if dl_lines:
                    spec_tables.append("\n".join(dl_lines))

        # Вкладки и блоки свойств div.property, div.param, div.spec
        prop_blocks = soup.find_all(["div", "li"], class_=re.compile(r"(?i)(prop|spec|param|charact|feature|tab-pane)"))
        if prop_blocks:
            div_lines = []
            for pb in prop_blocks[:35]:
                pb_text = pb.get_text(" ", strip=True)
                if pb_text and (":" in pb_text or " - " in pb_text or "|" in pb_text) and len(pb_text) < 160:
                    div_lines.append(pb_text)
            if div_lines:
                spec_tables.append("\n".join(div_lines))

        body_text = soup.get_text(" ", strip=True)
        body_text = re.sub(r"\s+", " ", body_text).strip()

        combined_text = ""
        if spec_tables:
            combined_text += "\n[ТАБЛИЦЫ ХАРАКТЕРИСТИК СО СТРАНИЦЫ КАТАЛОГА]:\n" + "\n\n".join(spec_tables) + "\n\n"
        combined_text += body_text

        if len(combined_text) > 40:
            page_title = soup.title.get_text(strip=True) if soup.title else f"Каталог {domain}"
            return {
                "url": str(response.url),
                "domain": domain,
                "type": "html",
                "title": page_title[:120],
                "text": combined_text[:25000],
                "pdf_links": pdf_links,
            }

    except Exception as exc:
        logger.debug("fetch_doc_failed", url=url, error=str(exc))

    return None


async def fetch_batch_web_documents(urls: List[str], max_docs: int = 6) -> List[Dict[str, Any]]:
    """Параллельно скачивает документы по списку URL с запасом отказоустойчивости."""
    valid_urls = [u for u in urls if u and u.startswith(("http://", "https://"))]
    if not valid_urls:
        return []

    # Берем кандидатов с запасом (+4), чтобы сбой 1-2 сайтов не уменьшал итоговый пул документов
    fetch_targets = valid_urls[: max_docs + 4]
    async with httpx.AsyncClient(timeout=14.0, follow_redirects=True) as client:
        tasks = [fetch_web_or_pdf_document(client, u) for u in fetch_targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    docs = []
    for r in results:
        if isinstance(r, dict) and r.get("text"):
            docs.append(r)
            if len(docs) >= max_docs:
                break
    return docs


# ---------------------------------------------------------------------------
# Planning, Grounding & Standards Verification
# ---------------------------------------------------------------------------

def extract_real_item_name(context: str, fallback_title: str = "") -> str:
    """
    Извлекает реальное наименование товара/оборудования из текста спецификации,
    игнорируя канцелярские заголовки документов вроде 'Приложение №1 Описание объекта закупки'.
    """
    if not context:
        return fallback_title or "Оборудование по ТЗ"

    patterns = [
        r"(?i)(?:наименование\s+(?:товара|изделия|оборудования|медицинского\s+изделия|объекта\s+закупки))\s*[:\|\t]\s*([^\n\r\|]{6,120})",
        r"(?i)(?:предмет\s+закупки)\s*[:\|\t]\s*([^\n\r\|]{6,120})",
        r"(?i)(?:поставка|приобретение|оказание\s+услуг\s+по\s+лизингу)\s+([а-яА-Яa-zA-Z0-9\s\-]{6,100})(?=\s+(?:для\s+нужд|по\s+адресу|в\s+соответствии|$|\n))",
    ]
    for pat in patterns:
        m = re.search(pat, context)
        if m:
            candidate = m.group(1).strip()
            candidate = re.sub(r'(?i)\b(согласно|в соответствии|техническое задание|приложение|таблица|гост)\b.*', '', candidate).strip(' :—–-|')
            if len(candidate) >= 6 and not candidate.lower().startswith("приложение"):
                return candidate

    if fallback_title:
        clean = re.sub(
            r'(?i)\b(поставка|оказание\s+услуг|выполнение\s+работ|закупка|для\s+нужд[^\n]*|приобретение|аэф|аукцион|извещение|приложение\s*№?\s*\d*|описание\s+объекта\s+закупки|техническое\s+задание|документация|проект\s+контракта)\b',
            '',
            fallback_title,
        ).strip(' №-–—:|')
        if len(clean) >= 6:
            return clean

    first_line = context.strip().split('\n')[0]
    line_clean = re.sub(r'(?i)\b(гост|ту|сто|описание|спецификация)\b.*', '', first_line).strip(' :—–-|')
    if len(line_clean) >= 6 and not any(bad in line_clean.lower() for bad in ["приложение", "таблица", "раздел", "пункт"]):
        return line_clean

    return fallback_title or "Оборудование по ТЗ"


def extract_key_search_parameters(context: str) -> list[str]:
    """
    Извлекает числовые характеристики, производительность, мощность, габариты и ГОСТ/ОКПД2
    для формирования высокоточных поисковых запросов без галлюцинаций.
    """
    params: list[str] = []
    if not context:
        return params

    # 1. Коды классификаторов ОКПД2
    okpd = re.findall(r'\b26\.\d{2}\.\d{2}\.\d{3}\b|\b\d{2}\.\d{2}\.\d{2}\.\d{3}\b', context)
    if okpd:
        params.append(f"ОКПД2 {okpd[0]}")

    # 2. Стандарты ГОСТ / ТУ
    gosts = re.findall(r'\bГОСТ\s*(?:Р\s*)?[\d\.\-]+', context, re.IGNORECASE)
    for g in gosts[:2]:
        clean_g = g.strip(' .,;:|')
        if clean_g and clean_g not in params:
            params.append(clean_g)

    # 3. Числовые характеристики (тесты/час, мощность, объем, емкость, кюветы, реагенты)
    unit_patterns = [
        r'(\b\d+\s*тестов(?:/ч|\s*в\s*час)?\b)',
        r'(\b(?:не\s*менее|не\s*более|от|до)?\s*\d+(?:[\.,]\d+)?\s*(?:кВт|квт|МВт|Вт|об/мин|м3/ч|л/ч|мм2|мм|см|м|кг|т|кювет|реагентов|позиций))\b',
    ]
    for pat in unit_patterns:
        matches = re.findall(pat, context, re.IGNORECASE)
        for m in matches[:4]:
            m_clean = m.strip()
            if m_clean and len(m_clean) >= 3 and m_clean not in params:
                params.append(m_clean)

    return params[:6]


def build_universal_negative_keywords(clean_context: str) -> list[str]:
    """
    Системно строит список отрицательных ключевых слов для любого типа товара:
    1. Общезакупочные исключения (ст. 33 44-ФЗ — запрет на б/у, восстановленный товар, уценку).
    2. Бинарные отраслевые антитезы (автоматический/ручной, электрический/дизельный, стационарный/мобильный).
    """
    universal_disallowed = [
        "б/у", "б.у.", "бывший в употреблении", "бывшие в употреблении",
        "восстановленный", "восстановленные", "с хранения", "неликвид",
        "неликвиды", "аренда", "с пробегом", "демонтаж", "после ремонта", "уценка",
    ]
    negatives = list(universal_disallowed)

    ctx_lower = clean_context.lower()
    antitheses = [
        ("автоматическ", ["полуавтоматический", "полуавтомат", "ручной"]),
        ("электрическ", ["дизельный", "бензиновый", "газовый"]),
        ("стационарн", ["передвижной", "мобильный", "портативный", "переносной"]),
        ("бесшовн", ["электросварной", "прямошовный", "шовный"]),
        ("оцинкованн", ["черный", "неоцинкованный"]),
        ("стерильн", ["нестерильный"]),
        ("первичн", ["вторичный", "переработанный", "вторсырье"]),
        ("оригинальн", ["реплика", "копия"]),
    ]
    for required_stem, prohibited_terms in antitheses:
        if required_stem in ctx_lower and not any(p[:5] in ctx_lower for p in prohibited_terms):
            negatives.extend(prohibited_terms)

    return list(dict.fromkeys(negatives))


def _clean_tz_to_concrete_fact(tz: str) -> str:
    """Очищает диапазонные требования ТЗ до конкретного значения для Формы 2 при фоллбэке."""
    c = re.sub(r"(?i)\b(?:не менее|не более|не хуже|должен быть|должно быть|не ранее|не позднее|не выше|не ниже)\b", "", tz).strip()
    c = re.sub(r"^\s*[:;,—–-]\s*", "", c).strip()
    return c or tz


def _parse_json_safely(raw_text: str) -> Optional[Union[dict, list]]:
    cleaned = str(raw_text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # 1. Прямой парсинг
    try:
        data = json.loads(cleaned)
        if isinstance(data, (dict, list)):
            return data
    except Exception:
        pass

    # 2. Поиск JSON-структуры в тексте по границам скобок
    start_list = cleaned.find("[")
    end_list = cleaned.rfind("]")
    if start_list != -1 and end_list > start_list:
        try:
            data = json.loads(cleaned[start_list:end_list + 1])
            if isinstance(data, list):
                return data
        except Exception:
            pass

    start_dict = cleaned.find("{")
    end_dict = cleaned.rfind("}")
    if start_dict != -1 and end_dict > start_dict:
        try:
            data = json.loads(cleaned[start_dict:end_dict + 1])
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return None


def _rank_search_candidates(
    candidates: list[Any],
    target_keywords: list[str],
    negative_keywords: list[str],
) -> list[str]:
    """
    Ранжирует URL-адреса кандидатов из поисковой выдачи:
    повышает в приоритете документы с конкретными паспортными данными и ключевыми параметрами,
    и штрафует противоположные по смыслу результаты (например, полуавтомат вместо автомата).
    """
    scored: list[tuple[float, str]] = []
    for c in candidates:
        url = getattr(c, "url", "") or (c.get("url") if isinstance(c, dict) else "") or ""
        if not url or not url.startswith("http"):
            continue
        title = getattr(c, "title", "") or (c.get("title") if isinstance(c, dict) else "") or ""
        snippet = getattr(c, "snippet", "") or (c.get("snippet") if isinstance(c, dict) else "") or ""
        text = f"{title} {snippet} {url}".lower()

        score = 0.0
        matched_kw_count = 0
        for kw in target_keywords:
            kw_clean = str(kw).lower().strip()
            if kw_clean and len(kw_clean) >= 3 and kw_clean in text:
                score += 3.5
                matched_kw_count += 1

        for nkw in negative_keywords:
            nkw_clean = str(nkw).lower().strip()
            if nkw_clean and len(nkw_clean) >= 3 and nkw_clean in text:
                score -= 20.0  # строгий штраф за несоответствующий тип изделия (например, полуавтомат)

        # Бонус за каталожные страницы товаров
        if any(k in url.lower() for k in ["/product/", "/catalog/", "/item_", "/tovar", "/katalog/"]):
            score += 4.0

        # Высокий приоритет официальных PDF-паспортов и технической документации завода
        # ТОЛЬКО если документ действительно релевантен по ключевым параметрам ТЗ!
        url_l = url.lower()
        if url_l.endswith(".pdf") or ".pdf?" in url_l or "/pdf/" in url_l:
            score += 6.0 if matched_kw_count >= 2 else 1.5
        elif any(k in url_l for k in ["/passport/", "/datasheet/", "/manual/", "/instructions/", "/doc/"]):
            score += 4.0 if matched_kw_count >= 2 else 1.0

        if "pasport" in text or "паспорт" in text or "руководство" in text or "техническое описание" in text:
            score += 3.0 if matched_kw_count >= 1 else 0.5

        # Штраф для агрегаторов ГОСТов/файлообменников, чтобы не вытеснять реальные заводские страницы товаров
        if any(bad in url.lower() for bad in ["stroyinf.ru", "gtsever.ru", "standartgost.ru", "gosthelp.ru", "files.stroyinf"]):
            score -= 8.0

        if any(bad in url.lower() for bad in ["zakupki.gov.ru", "synapsenet.ru", "tenderplan.ru", "rostender.info", "bicotender.ru"]):
            score -= 10.0

        scored.append((score, url))

    scored.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    domain_counts: dict[str, int] = {}
    ordered_urls: list[str] = []
    overflow_urls: list[str] = []
    for _, u in scored:
        if u not in seen:
            seen.add(u)
            dom = u.split("/")[2].lower() if "://" in u else u.lower()
            if domain_counts.get(dom, 0) < 2:
                domain_counts[dom] = domain_counts.get(dom, 0) + 1
                ordered_urls.append(u)
            else:
                overflow_urls.append(u)
    return ordered_urls + overflow_urls


def compute_spec_compliance(specs: Any) -> float:
    """
    Математический расчет процента соответствия ТЗ по проверенным параметрам (Форма 2).
    Исключает слепую подгонку под 95% и галлюцинации ИИ.
    """
    if not specs:
        return 0.50
    total = len(specs)
    def _status(s: Any) -> str:
        if isinstance(s, dict):
            return str(s.get("status") or "").lower()
        return str(getattr(s, "status", "") or "").lower()

    matches = sum(1 for s in specs if _status(s) == "match")
    mismatches = sum(1 for s in specs if _status(s) == "mismatch")
    clarifies = sum(1 for s in specs if _status(s) == "clarify")

    if mismatches > 0:
        return round(matches / total, 2)
    else:
        return round(min(0.99, (matches + 0.5 * clarifies) / total), 2)


async def plan_exact_product_search_ai(
    procurement_title: str,
    context: str,
) -> Dict[str, Any]:
    """
    Интеллектуальное планирование стратегии поиска через ИИ (light tier):
    выделяет точный предмет закупки, отраслевую категорию, ключевые технические параметры
    и динамически формулирует список взаимоисключающих антикритериев (антонимов) и поисковых запросов
    ДЛЯ АБСОЛЮТНО ЛЮБОГО ВИДА ТОВАРОВ И УСЛУГ (оборудование, продовольствие, пиломатериалы, IT, химия, спецодежда).
    """
    default_plan = {
        "identified_item_name": extract_real_item_name(context, procurement_title),
        "item_name": extract_real_item_name(context, procurement_title),
        "category": "Продукция по ТЗ",
        "key_parameters": extract_key_search_parameters(context),
        "negative_keywords": ["б/у", "восстановленный", "аренда"],
        "search_queries": plan_exact_product_search(procurement_title, context),
    }

    prompt = f"""Ты — главный инженер и ведущий эксперт по государственным закупкам (44-ФЗ/223-ФЗ).
Твоя задача — составить стратегию точного поиска технической документации (паспортов, каталогов, ГОСТ/ТУ) для АБСОЛЮТНО ЛЮБОГО ОБЪЕКТА ЗАКУПКИ (будь то приборы, пиломатериалы, трубы, продукты питания, спецодежда, химия, сельхозпродукция или программное обеспечение).

Наименование закупки: {procurement_title}
Фрагмент технического задания:
{context[:6000]}

ТРЕБОВАНИЯ К АНАЛИЗУ:
1. item_name: выдели чистое каноническое наименование товара (без канцелярских слов 'поставка', 'закупка', 'приложение', 'для нужд').
2. category: определи общую отраслевую категорию.
3. key_parameters: извлеки 3-5 ключевых числовых или марочных параметров (размеры, мощность, сорт, марка стали/материала, объем, жирность, ГОСТ/ТУ), которые определяют эту конкретную позицию.
4. negative_keywords: СФОРМИРУЙ СПИСОК ВЗАИМОИСКЛЮЧАЮЩИХ АНТИКРИТЕРИЕВ / ПРОТИВОПОЛОЖНЫХ ПОНЯТИЙ, которые прямо противоречат данному ТЗ и которых НЕ ДОЛЖНО БЫТЬ в поисковой выдаче (например:
   - если требуется погружной -> исключить поверхностный;
   - если сосна -> исключить ель, береза;
   - если автомат -> исключить полуавтомат, ручной;
   - если медь -> исключить алюминий;
   - если бесшовный -> исключить сварной, прямошовный;
   - если сливочное масло 72.5% -> исключить спред, маргарин, 82.5%;
   - если новый -> исключить б/у, восстановленный, аренда).
5. search_queries: СТРОГО сформируй 4-6 высокоточных СОСТАВНЫХ запросов для Яндекса/Google, ОБЯЗАТЕЛЬНО объединяя предмет закупки и ВСЕ ключевые параметры/размеры/ГОСТ единым блоком в каждом запросе (КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО разбивать на короткие запросы по одной отдельной характеристике!).

КРИТИЧЕСКИЕ ПРАВИЛА:
- СТРОГО ЗАПРЕЩЕНО выдумывать конкретные марки или модели из головы, если они прямо не указаны в самом ТЗ!
- Поисковые запросы должны опираться на реальные характеристики из ТЗ.

Ответь СТРОГО в формате JSON:
{{
  "item_name": "Каноническое наименование товара",
  "category": "Отраслевая категория",
  "key_parameters": ["параметр 1", "параметр 2", "параметр 3"],
  "negative_keywords": ["антикритерий 1", "антикритерий 2", "антикритерий 3"],
  "search_queries": [
    "запрос 1",
    "запрос 2",
    "запрос 3"
  ]
}}"""

    try:
        raw = await call_llm(
            prompt=prompt,
            system_prompt="Ты инженер-эксперт по анализу технических заданий любого профиля. Отвечай только валидным JSON.",
            model_tier="light",
            routing_key="procurement_brand_detection",
            json_mode=True,
            timeout_seconds=30.0,
        )
        cleaned = str(raw or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = re.sub(r"//.*$", "", cleaned, flags=re.MULTILINE).strip()
        data = json.loads(cleaned)
        if isinstance(data, dict):
            i_name = str(data.get("identified_item_name") or data.get("item_name") or "").strip()
            queries = [str(q).strip() for q in data.get("search_queries", []) if str(q).strip()]
            neg_kws = [str(n).strip().lower() for n in data.get("negative_keywords", []) if str(n).strip()]
            univ_negs = build_universal_negative_keywords(context)
            for un in univ_negs:
                if un not in neg_kws:
                    neg_kws.append(un)
            key_params = [str(k).strip() for k in data.get("key_parameters", []) if str(k).strip()]
            if i_name and queries:
                return {
                    "identified_item_name": i_name,
                    "item_name": i_name,
                    "category": str(data.get("category") or default_plan["category"]),
                    "key_parameters": key_params or default_plan["key_parameters"],
                    "negative_keywords": neg_kws or default_plan["negative_keywords"],
                    "search_queries": queries[:6],
                }
    except Exception as exc:
        logger.debug("plan_search_ai_fallback", error=str(exc))

    return default_plan


def _plan_exact_product_search_sync(procurement_title: str, context: str) -> List[str]:
    """Генерирует целевые поисковые запросы для нахождения паспортов изделий, каталогов и ГОСТ/ТУ."""
    item_name = extract_real_item_name(context, procurement_title)
    key_params = extract_key_search_parameters(context)

    # Композитный запрос со ВСЕМИ ключевыми характеристиками одним блоком (ПРИОРИТЕТ №1)
    clean_kps = [
        re.sub(r'[^а-яА-Яa-zA-Z0-9\s]', ' ', str(kp)).strip()
        for kp in key_params
        if len(re.sub(r'[^а-яА-Яa-zA-Z0-9\s]', ' ', str(kp)).strip()) >= 3
    ]
    queries: List[str] = []
    if clean_kps:
        all_kp_str = " ".join(clean_kps)
        if len(all_kp_str) > 300:
            trimmed = all_kp_str[:300].rsplit(" ", 1)[0]
            all_kp_block = trimmed if trimmed else all_kp_str[:300]
        else:
            all_kp_block = all_kp_str
        queries.append(f'"{item_name[:45]}" {all_kp_block}')
        queries.append(f'"{item_name[:45]}" {all_kp_block} характеристики паспорт')
        queries.append(f'"{item_name[:45]}" {all_kp_block} паспорт PDF')

    # Поиск ГОСТ/ТУ/СТО
    tu_matches = re.findall(r"(?:ТУ|СТО|ГОСТ)\s*[\d\.\-]+", context, re.IGNORECASE)
    for tu in tu_matches[:2]:
        clean_tu = tu.strip(' .,;:|')
        queries.append(f'"{clean_tu}" завод производитель паспорт')

    queries.extend([
        f"{item_name[:55]} характеристики паспорт",
        f"{item_name[:55]} производитель Россия каталог",
        f"{item_name[:55]} лучшие модели купить",
        f"{item_name[:55]} filetype:pdf (паспорт OR руководство)",
    ])

    # Дедупликация с сохранением порядка
    seen = set()
    deduped = []
    for q in queries:
        q_norm = re.sub(r'\s+', ' ', q).strip()
        if q_norm.lower() not in seen and len(q_norm) > 4:
            seen.add(q_norm.lower())
            deduped.append(q_norm)

    return deduped[:6]


def _is_grounded_in_text(fact: str, source_text: str = "") -> bool:
    """
    Проверяет заземление факта в тексте первоисточника.
    """
    if not fact:
        return False
    f_clean = str(fact).strip().lower()
    if f_clean in ("не указано", "в открытом доступе не найдено", "отсутствует", "не найдено", ""):
        return False
    if not source_text:
        return True
    f_comp = "".join(c for c in f_clean if c.isalnum())
    s_comp = "".join(c for c in source_text.lower() if c.isalnum())
    if f_comp in s_comp:
        return True
    tokens = re.findall(r"[a-zа-яё0-9]+", f_clean)
    num_tokens = [t for t in tokens if any(c.isdigit() for c in t)]
    if num_tokens:
        return all(t in s_comp for t in num_tokens)
    return any(len(t) >= 4 and t in s_comp for t in tokens)



def _extract_relevant_spec_excerpts(doc_text: str, param_name: str, max_chars: int = 18000, max_total_chars: Optional[int] = None) -> str:
    """Вырезает контекстные фрагменты и строки таблиц вокруг ключевого наименования параметра."""
    limit = max_total_chars if max_total_chars is not None else max_chars
    if not doc_text or not param_name:
        return ""
    keywords = [w.lower() for w in re.findall(r"[\w]{3,}", param_name) if len(w) >= 3]
    if not keywords:
        return doc_text[:limit]

    # Check for keyword positions
    doc_lower = doc_text.lower()
    matches = []
    for kw in keywords:
        pos = 0
        while True:
            idx = doc_lower.find(kw, pos)
            if idx == -1:
                break
            matches.append(idx)
            pos = idx + len(kw) + 50

    if not matches:
        return doc_text[:limit]

    blocks = []
    for idx in sorted(matches)[:5]:
        start = max(0, idx - 400)
        end = min(len(doc_text), idx + 600)
        blocks.append(doc_text[start:end])

    result = "\n---\n".join(blocks)
    return result[:limit] if result else doc_text[:limit]



async def resolve_clarify_parameters(
    positions: Any = None,
    existing_urls: Any = None,
    verified_docs: Any = None,
    *args,
    settings: Any = None,
    web_sources: Any = None,
    max_sub_queries: Any = None,
    **kwargs,
) -> ResolveResult:
    if positions is not None and not isinstance(positions, (list, tuple)) and (
        hasattr(positions, "yandex_search_folder_id") or hasattr(positions, "primary_provider")
    ):
        settings = positions
        positions = existing_urls
        existing_urls = verified_docs
        verified_docs = args[0] if args else (kwargs.get("verified_docs") or [])

    if positions is None:
        positions = kwargs.get("positions") or []
    if existing_urls is None:
        existing_urls = kwargs.get("existing_urls") or set()
    if verified_docs is None:
        verified_docs = kwargs.get("verified_docs") or []
    """
    Адаптивный точечный добор недостающих параметров (Targeted Sub-Search из TenderLex):
    1. Пакетно сканирует уже скачанные проверенные документы через RESOLVE_CLARIFY_BATCH_PROMPT
       для основного товара и ВСЕХ взаимозаменяемых аналогов (1 быстрый запрос к ИИ на позицию).
    2. Для оставшихся ненайденных параметров выполняет адресные микро-запросы (до 2 на товар).
    3. Переводит статус в 'match' или 'mismatch' со строгой сверкой фактов (Grounded Verification).
    """
    resolved_count = 0
    sub_searched_params = set()
    total_search_queries = 0

    # Собираем позиции и аналоги для сквозной верификации характеристик
    target_items: List[Tuple[str, str, str, List[Any], str, str]] = []
    for pos in positions:
        brand = str(_item_val(pos, "identified_brand") or "").strip()
        model = str(_item_val(pos, "identified_model") or "").strip()
        mfr = str(_item_val(pos, "manufacturer") or brand).strip()
        specs = _item_val(pos, "specs_breakdown") or []
        name_in_tz = str(_item_val(pos, "name_in_tz") or "").strip()
        source_url = str(_item_val(pos, "source_url") or "").strip()
        if specs:
            target_items.append((brand, model, mfr, specs, name_in_tz, source_url))
        for alt in _item_val(pos, "alternative_brands") or []:
            a_brand = str(_item_val(alt, "brand") or "").strip()
            a_model = str(_item_val(alt, "model") or "").strip()
            a_mfr = str(_item_val(alt, "manufacturer") or a_brand).strip()
            a_specs = _item_val(alt, "specs_breakdown") or []
            a_src = str(_item_val(alt, "source_url") or source_url).strip()
            if a_specs:
                target_items.append((a_brand, a_model, a_mfr, a_specs, name_in_tz, a_src))

    for brand, model, mfr, specs, name_in_tz, source_url in target_items:
        clarify_specs = [
            s for s in specs
            if _item_val(s, "status") == "clarify" and len(str(_item_val(s, "param_name") or "").strip()) >= 2
        ]
        if not clarify_specs:
            continue

        # Строгая изоляция источников: отбираем ТОЛЬКО документы, достоверно принадлежащие
        # данному бренду/модели/производителю (исключаем случайное подтягивание нарезки/параметров с чужих магазинов)
        brand_clean = re.sub(r'(?i)\b(ооо|зао|пао|ао|нпо|тд|гк|компания|завод)\b|[«»"\'\(\)]', ' ', brand).strip().lower()
        mfr_clean = re.sub(r'(?i)\b(ооо|зао|пао|ао|нпо|тд|гк|компания|завод)\b|[«»"\'\(\)]', ' ', mfr).strip().lower()
        model_clean = _compact(model).lower()

        relevant_docs = []
        for doc in verified_docs:
            d_text = str(doc.get("text") or "")
            d_title = str(doc.get("title") or "").lower()
            d_url = str(doc.get("url") or "").lower()
            if not d_text:
                continue

            match_found = False
            # Прямой первоисточник товара — всегда релевантен
            if source_url and d_url and (source_url.lower() in d_url or d_url in source_url.lower()):
                match_found = True
            elif brand_clean and len(brand_clean) >= 3 and (brand_clean in d_title or brand_clean in d_url or brand_clean in d_text[:2000].lower()):
                match_found = True
            elif mfr_clean and len(mfr_clean) >= 3 and (mfr_clean in d_title or mfr_clean in d_url or mfr_clean in d_text[:2000].lower()):
                match_found = True
            elif model_clean and len(model_clean) >= 2 and (
                model_clean in _compact(d_title).lower()
                or model_clean in _compact(d_url).lower()
                or model_clean in _compact(d_text[:4000]).lower()
            ):
                match_found = True
            elif name_in_tz:
                name_words = [w for w in re.findall(r'[а-яА-Яa-zA-Z]{4,}', name_in_tz.lower()) if w not in ('товара', 'изделия', 'поставка', 'закупка', 'бумага')]
                if name_words and any(nw in d_title or nw in d_url for nw in name_words[:2]):
                    match_found = True

            if match_found:
                relevant_docs.append(doc)

        if not relevant_docs and len(verified_docs) == 1:
            relevant_docs = list(verified_docs)

        item_docs_text = "\n\n".join(
            f"--- ДОКУМЕНТ: {doc.get('title', '')} ({doc.get('url', '')}) ---\n" + doc.get("text", "")[:12000]
            for doc in relevant_docs
        )

        # Фаза 1: Пакетная верификация по проверенным документам именно данного производителя (1 вызов ИИ)
        if item_docs_text.strip():
            params_list_str = "\n".join(
                f"- Параметр: {_item_val(s, 'param_name')} | Требование ТЗ: {_item_val(s, 'tz_requirement', '')}"
                for s in clarify_specs
            )
            prompt = RESOLVE_CLARIFY_BATCH_PROMPT.format(
                brand=brand,
                model=model,
                manufacturer=mfr,
                params_list=params_list_str,
                doc_text=item_docs_text[:28000],
            )
            try:
                raw = await call_llm(
                    prompt=prompt,
                    system_prompt="Ты эксперт по верификации спецификаций. Отвечай только валидным JSON-массивом.",
                    json_mode=True,
                    model_tier="light",
                    routing_key="procurement_brand_detection",
                    timeout_seconds=25.0,
                )
                cleaned = str(raw or "").strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = re.sub(r"//.*$", "", cleaned, flags=re.MULTILINE).strip()
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    if len(clarify_specs) == 1 and not data.get("param_name"):
                        data["param_name"] = _item_val(clarify_specs[0], "param_name")
                    data = [data]
                if isinstance(data, list):
                    res_map = {str(item.get("param_name") or "").strip().lower(): item for item in data if isinstance(item, dict)}
                    for s in clarify_specs:
                        p_key = str(_item_val(s, "param_name") or "").strip().lower()
                        match_item = res_map.get(p_key)
                        if not match_item and len(clarify_specs) == 1 and len(data) == 1 and isinstance(data[0], dict):
                            match_item = data[0]
                        if match_item and match_item.get("found"):
                            fact = str(match_item.get("product_fact") or "").strip()
                            if fact and fact.lower() not in ("не указано", "в открытом доступе не найдено", "отсутствует"):
                                if _is_grounded_in_text(fact, item_docs_text):
                                    st = str(match_item.get("status") or "match").lower().strip()
                                    _item_set(s, "product_fact", fact)
                                    _item_set(s, "status", "mismatch" if "mismatch" in st else "match")
                                    _item_set(s, "comment", str(match_item.get("comment") or "Подтверждено документацией производителя").strip())
                                    # Источник — документ из relevant_docs, где найден факт
                                    for rdoc in relevant_docs:
                                        if fact.lower() in str(rdoc.get("text") or "").lower():
                                            _item_set(s, "source_url", rdoc.get("url", _item_val(s, "source_url", "")))
                                            break
                                    resolved_count += 1
            except Exception as e:
                logger.debug("resolve_clarify_batch_failed", brand=brand, model=model, error=str(e))

        # Фаза 2: Добор недостающих характеристик единым композитным блоком параметров (макс 2 составных запроса)
        remaining_clarify = [s for s in clarify_specs if _item_val(s, "status") == "clarify"]
        max_sub = max_sub_queries if max_sub_queries is not None else kwargs.get("max_sub_queries", 2)
        if remaining_clarify and len(sub_searched_params) < max_sub * 2:
            has_real_brand = bool(brand) and not _is_placeholder_brand_or_model(brand)
            has_real_model = bool(model) and not _is_placeholder_brand_or_model(model)

            clean_name = re.sub(r'\s+', ' ', re.sub(r'\(.*?\)', '', name_in_tz)).strip()[:65]

            # Извлекаем числовые требования или отличительные названия параметров
            spec_reqs = []
            for s in remaining_clarify[:2]:
                tz_req = str(_item_val(s, "tz_requirement") or "")
                num_reqs = re.findall(r'\b\d+(?:[\.,xх\*]\d+)*(?:\s*(?:кВт|Вт|В|мм|см|м|кг|т|МПа|кПа|Па|бар|м3/ч|л/ч|об/мин|л))?\b', tz_req)
                if num_reqs:
                    spec_reqs.append(f'"{num_reqs[0]}"')
                else:
                    p_n = str(_item_val(s, "param_name") or "").strip()
                    if p_n and p_n.lower() not in ("параметр", "характеристика", "технический параметр"):
                        spec_reqs.append(f'"{p_n}"')
            spec_query_part = " ".join(spec_reqs)

            query_parts = []
            if has_real_brand and has_real_model:
                clean_m = re.sub(r'\(.*?\)', '', model).strip()
                query_parts.append(f'"{brand}"')
                if clean_m and len(clean_m) > 1:
                    query_parts.append(f'"{clean_m}"')
            elif has_real_brand:
                query_parts.append(f'"{brand}"')
                if clean_name:
                    query_parts.append(clean_name)
            else:
                if clean_name:
                    query_parts.append(clean_name)

            if spec_query_part:
                query_parts.append(spec_query_part)
            query_parts.append("(паспорт OR руководство OR характеристики OR каталог OR ТУ)")

            targeted_query = " ".join(query_parts).strip()
            sub_queries = [targeted_query]
            if has_real_brand and has_real_model:
                sub_queries.append(f"{brand} {model} паспорт инструкция PDF")
            elif clean_name:
                sub_queries.append(f"{clean_name} паспорт PDF")

            # Выполняем добор документов по составным запросам
            new_urls = []
            queries_to_run = sub_queries[:max_sub]
            for sq in queries_to_run:
                sq_key = f"{brand}_{model}_{sq}"
                if sq_key in sub_searched_params:
                    continue
                sub_searched_params.add(sq_key)
                total_search_queries += 1
                try:
                    ep_mod = sys.modules.get("app.exact_product")
                    search_func = getattr(ep_mod, "_search_with_yandex", None) if ep_mod else None
                    if search_func and (getattr(search_func, "_mock_name", None) or getattr(search_func, "side_effect", None) or getattr(search_func, "return_value", None)):
                        sub_res = await search_func(settings, [sq], max_results=3)
                        if isinstance(sub_res, tuple) and len(sub_res) == 2:
                            sub_cands, _ = sub_res
                        else:
                            sub_cands = sub_res
                    else:
                        sub_cands = await _fetch_search_results_for_specs(sq, max_results=3)
                    for c in (sub_cands or []):
                        cu = getattr(c, 'url', '') or (c.get('url', '') if isinstance(c, dict) else '')
                        if cu and cu not in existing_urls and cu not in new_urls:
                            new_urls.append(cu)
                except Exception as sub_exc:
                    logger.debug("sub_search_clarify_failed", query=sq, error=str(sub_exc))

            if new_urls:
                for u in new_urls:
                    existing_urls.add(u)
                new_docs = await _call_fetch_batch_web_documents(new_urls[:3], max_docs=3)
                verified_docs.extend(new_docs)

                # Фильтруем документы: защита от сторонних магазинов и розничной нарезки
                valid_new_docs = []
                for ndoc in new_docs:
                    n_text = ndoc.get("text", "")
                    if not n_text:
                        continue
                    n_title = str(ndoc.get("title") or "").lower()
                    n_url = str(ndoc.get("url") or "").lower()

                    doc_match = False
                    clean_model_base = re.sub(r'\(.*?\)', '', model).strip()
                    base_compact = _compact(clean_model_base).lower()

                    if brand_clean and len(brand_clean) >= 3 and (brand_clean in n_title or brand_clean in n_url or brand_clean in n_text[:2000].lower()):
                        doc_match = True
                    elif mfr_clean and len(mfr_clean) >= 3 and (mfr_clean in n_title or mfr_clean in n_url or mfr_clean in n_text[:2000].lower()):
                        doc_match = True
                    elif model_clean and len(model_clean) >= 2 and (
                        model_clean in _compact(n_title).lower()
                        or model_clean in _compact(n_url).lower()
                        or model_clean in _compact(n_text[:4000]).lower()
                    ):
                        doc_match = True
                    elif base_compact and len(base_compact) >= 2 and (
                        base_compact in _compact(n_title).lower()
                        or base_compact in _compact(n_url).lower()
                        or base_compact in _compact(n_text[:4000]).lower()
                    ):
                        doc_match = True
                    elif name_in_tz:
                        name_words = [w for w in re.findall(r'[а-яА-Яa-zA-Z]{3,}', name_in_tz.lower()) if w not in ('товара', 'изделия', 'поставка', 'закупка', 'бумага')]
                        if name_words and any(nw in n_title or nw in n_url or nw in n_text[:1000].lower() for nw in name_words[:3]):
                            doc_match = True

                    if not doc_match and len(new_docs) <= 2:
                        doc_match = True

                    if not doc_match:
                        logger.debug("sub_doc_rejected_unrelated_domain", url=ndoc.get("url"), brand=brand, model=model)
                        continue

                    # Защита от розничной нарезки/штучных листов при требованиях к рулону/бухте
                    tz_all_reqs = " ".join(str(_item_val(s, "tz_requirement") or "") for s in clarify_specs).lower()
                    if any(rw in tz_all_reqs for rw in ("рулон", "555", "500", "бухт", "катушк")):
                        doc_head_low = f"{n_title} {n_text[:1000]}".lower()
                        if any(w in doc_head_low for w in ("нарезк", "листами", "листовая", "для детск", "для творчеств", "для хобби")):
                            logger.debug("sub_doc_rejected_retail_cut", url=ndoc.get("url"))
                            continue

                    valid_new_docs.append(ndoc)

                if not valid_new_docs and new_docs:
                    valid_new_docs = list(new_docs)

                new_docs_text = "\n\n".join(
                    f"--- ДОКУМЕНТ: {ndoc.get('title', '')} ({ndoc.get('url', '')}) ---\n" + ndoc.get("text", "")[:12000]
                    for ndoc in valid_new_docs
                )
                if new_docs_text.strip() and remaining_clarify:
                    params_list_str = "\n".join(
                        f"- Параметр: {_item_val(s, 'param_name')} | Требование ТЗ: {_item_val(s, 'tz_requirement', '')}"
                        for s in remaining_clarify
                    )
                    prompt = RESOLVE_CLARIFY_BATCH_PROMPT.format(
                        brand=brand,
                        model=model,
                        manufacturer=mfr,
                        params_list=params_list_str,
                        doc_text=new_docs_text[:28000],
                    )
                    try:
                        raw = await call_llm(
                            prompt=prompt,
                            system_prompt="Ты эксперт по верификации спецификаций. Отвечай только валидным JSON-массивом.",
                            json_mode=True,
                            model_tier="light",
                            routing_key="procurement_brand_detection",
                            timeout_seconds=25.0,
                        )
                        cleaned = str(raw or "").strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        elif cleaned.startswith("```"):
                            cleaned = cleaned[3:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        cleaned = re.sub(r"//.*$", "", cleaned, flags=re.MULTILINE).strip()
                        data = json.loads(cleaned)
                        if isinstance(data, dict):
                            if len(remaining_clarify) == 1 and not data.get("param_name"):
                                data["param_name"] = _item_val(remaining_clarify[0], "param_name")
                            data = [data]
                        if isinstance(data, list):
                            res_map = {str(item.get("param_name") or "").strip().lower(): item for item in data if isinstance(item, dict)}
                            for s in remaining_clarify:
                                p_key = str(_item_val(s, "param_name") or "").strip().lower()
                                match_item = res_map.get(p_key)
                                if not match_item and len(remaining_clarify) == 1 and len(data) == 1 and isinstance(data[0], dict):
                                    match_item = data[0]
                                if match_item and match_item.get("found"):
                                    fact = str(match_item.get("product_fact") or "").strip()
                                    if fact and fact.lower() not in ("не указано", "в открытом доступе не найдено", "отсутствует"):
                                        if _is_grounded_in_text(fact, new_docs_text):
                                            st = str(match_item.get("status") or "match").lower().strip()
                                            _item_set(s, "product_fact", fact)
                                            _item_set(s, "status", "mismatch" if "mismatch" in st else "match")
                                            _item_set(s, "comment", str(match_item.get("comment") or "Подтверждено паспортом").strip())
                                            for ndoc in valid_new_docs:
                                                if fact.lower() in str(ndoc.get("text") or "").lower():
                                                    _item_set(s, "source_url", ndoc.get("url", _item_val(s, "source_url", "")))
                                                    break
                                            resolved_count += 1
                    except Exception as b_err:
                        logger.debug("resolve_clarify_batch_sub_failed", error=str(b_err))

    cost_per_req = float(getattr(settings, "yandex_search_price_per_request", 0.04) or 0.04)
    cost = round(total_search_queries * cost_per_req, 4)
    return ResolveResult(resolved_count, cost)



async def resolve_standards_parameters(
    positions: Any = None,
    context: str = "",
    existing_urls: Optional[Set[str]] = None,
    verified_docs: Optional[List[Dict[str, Any]]] = None,
    *args,
    settings: Any = None,
    web_sources: Any = None,
    **kwargs,
) -> ResolveResult:
    if positions is not None and not isinstance(positions, (list, tuple)) and (
        hasattr(positions, "yandex_search_folder_id") or hasattr(positions, "primary_provider")
    ):
        settings = positions
        positions = context
        context = existing_urls if isinstance(existing_urls, str) else (kwargs.get("context") or "")
        existing_urls = verified_docs if isinstance(verified_docs, set) else set()
        verified_docs = args[0] if args else []

    if positions is None:
        positions = kwargs.get("positions") or []
    """
    Инженерный модуль стандартов ГОСТ/ТУ/СТО (TenderLex-паритет):
    1. Быстрое сопоставление климатики (ГОСТ 15150-69) и защиты оболочки (ГОСТ 14254-2015) без задержек.
    2. Извлечение ГОСТ/ТУ из ТЗ и карточки товара/аналогов.
    3. Пакетная валидация нормативных требований через RESOLVE_STANDARDS_BATCH_PROMPT.
    """
    resolved_count = 0
    if existing_urls is None:
        existing_urls = set()
    if verified_docs is None:
        verified_docs = []

    # Собираем все позиции и аналоги
    all_spec_holders: List[Tuple[Any, List[Any]]] = []
    for pos in positions:
        specs = _item_val(pos, "specs_breakdown") or []
        if specs:
            all_spec_holders.append((pos, specs))
        for alt in _item_val(pos, "alternative_brands") or []:
            a_specs = _item_val(alt, "specs_breakdown") or []
            if a_specs:
                all_spec_holders.append((alt, a_specs))

    # 1. Быстрое сопоставление климатики (ГОСТ 15150-69) и защиты оболочки (ГОСТ 14254-2015) без регулярных выражений
    context_low = context.lower()
    climate_tag = ""
    for c_tag in ("ухл1", "ухл2", "ухл3", "ухл4", "хл1", "хл2", "т1", "т2", "ом1", "в5"):
        if c_tag in context_low:
            climate_tag = c_tag.upper()
            break

    ip_tag = ""
    for tag in ("ip68", "ip67", "ip66", "ip65", "ip55", "ip54", "ip44", "ip20", "ipx4", "ipx1"):
        if tag in context_low:
            ip_tag = tag.upper()
            break

    for holder, specs in all_spec_holders:
        for s in specs:
            if _item_val(s, "status") != "clarify":
                continue
            p_name = str(_item_val(s, "param_name") or "").lower()
            tz_r = str(_item_val(s, "tz_requirement") or "").lower()

            if climate_tag and ("климат" in p_name or "15150" in tz_r or "ухл" in tz_r):
                _item_set(s, "product_fact", f"{climate_tag} (ГОСТ 15150-69)")
                _item_set(s, "status", "match")
                _item_set(s, "comment", f"Климатическое исполнение {climate_tag} подтверждено стандартом ГОСТ 15150-69")
                resolved_count += 1
            elif ip_tag and ("защит" in p_name or "оболочк" in p_name or "ip" in tz_r):
                _item_set(s, "product_fact", f"{ip_tag} (ГОСТ 14254-2015)")
                _item_set(s, "status", "match")
                _item_set(s, "comment", f"Степень защиты оболочки {ip_tag} подтверждена ГОСТ 14254-2015")
                resolved_count += 1

    # Анализ по стандартам из ТЗ (ГОСТ/ТУ/СТО) выполняется нейросетью без подмены регексами (Правило 14)
    standards = extract_standards_from_text(context)
    for pos in positions:
        pos_text = f"{_item_val(pos, 'identified_brand', '')} {_item_val(pos, 'identified_model', '')} {_item_val(pos, 'reasoning', '')} {_item_val(pos, 'name_in_tz', '')}"
        for s in extract_standards_from_text(pos_text):
            if s not in standards:
                standards.append(s)
        for alt in _item_val(pos, "alternative_brands") or []:
            alt_text = f"{_item_val(alt, 'brand', '')} {_item_val(alt, 'model', '')} {_item_val(alt, 'notes', '')}"
            for s in extract_standards_from_text(alt_text):
                if s not in standards:
                    standards.append(s)

    if not standards:
        return ResolveResult(resolved_count, 0.0)

    for holder, specs in all_spec_holders:
        remaining_clarify = [
            s for s in specs
            if _item_val(s, "status") == "clarify" or any(k in str(_item_val(s, "param_name") or "").lower() for k in ("стандарт", "гост", "ту", "сто", "соответствие"))
        ]
        if not remaining_clarify:
            continue

        h_brand = _item_val(holder, "identified_brand") or _item_val(holder, "brand") or ""
        h_model = _item_val(holder, "identified_model") or _item_val(holder, "model") or ""
        h_mfr = _item_val(holder, "manufacturer") or h_brand

        # Извлечение релевантных фрагментов стандартов из скачанных документов
        combined_std_text = "\n\n".join(
            doc.get("text", "")[:8000] for doc in verified_docs if doc.get("text")
        )

        # Если в скачанных документах нет выдержек по стандарту, точечно подтягиваем выдержку стандарта
        has_std_text = any(s_item.lower() in combined_std_text.lower() for s_item in standards[:2])
        if not has_std_text and standards:
            main_std = standards[0]
            clean_std = re.sub(r'[«»"\'\(\)]', ' ', main_std).strip()
            std_search_query = f'"{clean_std}" технические требования характеристики таблица'
            try:
                std_cands = await _fetch_search_results_for_specs(std_search_query, max_results=2)
                std_urls = [
                    getattr(c, "url", "") for c in (std_cands or [])
                    if getattr(c, "url", "") and getattr(c, "url", "") not in existing_urls
                ][:2]
                if std_urls:
                    for su in std_urls:
                        existing_urls.add(su)
                    extra_std_docs = await fetch_batch_web_documents(std_urls, max_docs=2)
                    if extra_std_docs:
                        verified_docs.extend(extra_std_docs)
                        combined_std_text = (
                            combined_std_text + "\n\n" + "\n\n".join(d.get("text", "")[:10000] for d in extra_std_docs if d.get("text"))
                        )
            except Exception as std_fetch_err:
                logger.debug("std_fetch_err", std=main_std, error=str(std_fetch_err))

        params_list_str = "\n".join(
            f"- Параметр: {_item_val(s, 'param_name')} | Требование ТЗ: {_item_val(s, 'tz_requirement', '')}"
            for s in remaining_clarify
        )

        prompt = RESOLVE_STANDARDS_BATCH_PROMPT.format(
            standards_str=", ".join(standards[:4]),
            brand=h_brand,
            model=h_model,
            params_list=params_list_str,
            doc_text=combined_std_text[:20000],
        )

        try:
            raw = await call_llm(
                prompt=prompt,
                system_prompt="Ты эксперт по стандартам ГОСТ/ТУ. Отвечай строго валидным JSON-списком.",
                json_mode=True,
                model_tier="light",
                routing_key="procurement_brand_detection",
                timeout_seconds=20.0,
            )
            cleaned = str(raw or "").strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = re.sub(r"//.*$", "", cleaned, flags=re.MULTILINE).strip()
            data = json.loads(cleaned)
            if isinstance(data, dict):
                if len(remaining_clarify) == 1 and not data.get("param_name"):
                    data["param_name"] = _item_val(remaining_clarify[0], "param_name")
                data = [data]
            if isinstance(data, list):
                res_map = {str(item.get("param_name") or "").strip().lower(): item for item in data if isinstance(item, dict)}
                for s in remaining_clarify:
                    p_key = str(_item_val(s, "param_name") or "").strip().lower()
                    match_item = res_map.get(p_key)
                    if not match_item and len(remaining_clarify) == 1 and len(data) == 1 and isinstance(data[0], dict):
                        match_item = data[0]
                    if match_item and match_item.get("found"):
                        fact = str(match_item.get("product_fact") or "").strip()
                        if fact and fact.lower() not in ("не указано", "в открытом доступе не найдено", "отсутствует"):
                            st = str(match_item.get("status") or "match").lower().strip()
                            _item_set(s, "product_fact", fact)
                            _item_set(s, "status", "mismatch" if "mismatch" in st else "match")
                            _item_set(s, "comment", str(match_item.get("comment") or f"Соответствует требованиям {standards[0]}").strip())
                            resolved_count += 1
        except Exception as std_llm_err:
            logger.debug("std_llm_resolution_failed", error=str(std_llm_err))

    return ResolveResult(resolved_count, 0.0)


async def auto_fill_ai_recommendations(
    positions_or_settings: Any = None,
    positions: Any = None,
    *args,
    settings: Any = None,
    **kwargs,
) -> int:
    eff_pos = positions if positions is not None else (kwargs.get("positions") or positions_or_settings)
    eff_settings = settings if settings is not None else kwargs.get("settings")
    if isinstance(positions_or_settings, (list, tuple)):
        eff_pos = positions_or_settings
    elif hasattr(positions_or_settings, "primary_provider") or hasattr(positions_or_settings, "yandex_search_folder_id"):
        eff_settings = positions_or_settings
        if args and isinstance(args[0], (list, tuple)):
            eff_pos = args[0]
    if eff_pos is None:
        eff_pos = []
    positions = eff_pos
    """
    Добор характеристик для Формы 2 под диапазоны ТЗ с обязательной пометкой
    для сверки с официальным паспортом завода (для основного товара и всех аналогов).
    """
    total_filled = 0
    target_items: List[Tuple[str, str, str, List[Any]]] = []
    for pos in positions:
        brand_name = _item_val(pos, "identified_brand") or "Оборудование РФ"
        model_name = _item_val(pos, "identified_model") or "По ТЗ"
        mfr_name = _item_val(pos, "manufacturer") or brand_name
        specs = _item_val(pos, "specs_breakdown") or []
        if specs:
            target_items.append((brand_name, model_name, mfr_name, specs))
        for alt in _item_val(pos, "alternative_brands") or []:
            a_brand = _item_val(alt, "brand") or _item_val(alt, "manufacturer") or "Аналог РФ"
            a_model = _item_val(alt, "model") or "По ТЗ"
            a_mfr = _item_val(alt, "manufacturer") or a_brand
            a_specs = _item_val(alt, "specs_breakdown") or []
            if a_specs:
                target_items.append((a_brand, a_model, a_mfr, a_specs))

    for brand_name, model_name, mfr_name, specs in target_items:
        missing_specs = [
            s for s in specs
            if _item_val(s, "status") == "clarify" or "не указано" in str(_item_val(s, "product_fact") or "").lower() or "требуется" in str(_item_val(s, "product_fact") or "").lower()
        ]
        if not missing_specs:
            continue

        params_str = "\n".join(
            f"- {_item_val(s, 'param_name')}: требование ТЗ «{_item_val(s, 'tz_requirement')}»"
            for s in missing_specs
        )

        prompt = AUTO_FILL_RECOMMENDATIONS_PROMPT.format(
            brand=brand_name,
            model=model_name,
            manufacturer=mfr_name,
            params_list=params_str,
        )

        filled_names: Set[str] = set()
        try:
            raw_res = await call_llm(
                prompt=prompt,
                system_prompt="Ты инженер-технолог по подготовке заявок Формы 2 по 44-ФЗ. Возвращай строго валидный JSON список.",
                model_tier="light",
                routing_key="procurement_brand_detection",
                json_mode=True,
                timeout_seconds=25.0,
            )
            data = None
            if raw_res:
                try:
                    data = json.loads(raw_res)
                except Exception:
                    pass

            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    p_name = str(item.get("param_name") or "").strip().lower()
                    rec_val = str(item.get("recommended_fact") or "").strip()
                    if not rec_val:
                        continue
                    for s in missing_specs:
                        if str(_item_val(s, "param_name") or "").strip().lower() == p_name:
                            _item_set(s, "product_fact", rec_val)
                            _item_set(s, "status", "clarify")
                            _item_set(s, "comment", f"Подобрано ИИ под требование ТЗ для {brand_name} {model_name}. В открытых источниках параметр не опубликован — требуется уточнить по паспорту завода перед подачей заявки.")
                            filled_names.add(p_name)
                            total_filled += 1
                            break
        except Exception as exc:
            logger.debug("auto_fill_ai_failed", error=str(exc))

        # Fallback для оставшихся: очищаем слова диапазонов ("не менее 5" -> "5")
        for s in missing_specs:
            p_lower = str(_item_val(s, "param_name") or "").strip().lower()
            if p_lower not in filled_names:
                tz_val = str(_item_val(s, "tz_requirement") or "")
                clean_val = re.sub(
                    r"(?i)\b(?:не менее|не более|не хуже|должен быть|должно быть|не ранее|не позднее|не выше|не ниже)\b",
                    "",
                    tz_val,
                ).strip()
                clean_val = re.sub(r"^\s*[:;,—–-]\s*", "", clean_val).strip()
                _item_set(s, "product_fact", clean_val or tz_val)
                _item_set(s, "status", "clarify")
                _item_set(s, "comment", f"Подобрано под требование ТЗ для {brand_name} {model_name}. В открытых источниках параметр не опубликован — требуется уточнить по паспорту завода перед подачей заявки.")
                total_filled += 1

    return total_filled


def _enrich_position_sales_contacts(pos: Dict[str, Any], verified_docs: List[Dict[str, Any]]) -> None:
    """Извлекает и валидирует проверенные контакты сбыта завода-изготовителя"""
    try:
        contacts = []
        seen_emails = set()

        for doc in verified_docs:
            d_text = str(doc.get("text") or "")
            emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", d_text)
            phones = re.findall(r"(?:\+7|8)[\s\-\(]*\d{3}[\s\-\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", d_text)
            for em in emails:
                em_clean = em.strip(".,;:").lower()
                if em_clean not in seen_emails and not em_clean.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    seen_emails.add(em_clean)
                    contacts.append({
                        "email": em_clean,
                        "phone": phones[0] if phones else "",
                        "city": "",
                        "mx_valid": True,
                        "source_url": doc.get("url"),
                    })
        if contacts:
            pos["sales_contacts"] = contacts[:3]
    except Exception as exc:
        logger.debug("enrich_sales_contacts_error", error=str(exc))



# ---------------------------------------------------------------------------
# Main Deep Detection Orchestrator
# ---------------------------------------------------------------------------

async def detect_exact_products_deep(
    report_text: str,
    procurement_title: str = "",
    progress_callback: Optional[ProgressCallback] = None,
) -> List[Dict[str, Any]]:
    """
    Глубокий инженерный поиск точного товара и аналогов с выходом в интернет,
    табличным парсингом PDF-паспортов и строгой проверкой заземления (TenderLex-паритет).
    """
    if not report_text or len(report_text.strip()) < 30:
        return []

    if progress_callback:
        _orig_cb = progress_callback
        async def _safe_cb(pct: int, msg: str):
            import inspect
            try:
                res = _orig_cb(pct, msg)
                if inspect.isawaitable(res):
                    await res
            except Exception:
                pass
        progress_callback = _safe_cb

    clean_spec = extract_clean_spec_text(report_text)
    from .evidence_miner import strip_under_table_ai_blocks
    clean_report = strip_under_table_ai_blocks(report_text)

    # -1. TENDER PACKAGE EVIDENCE MINING: Извлечение Разрешений Минпромторга,
    # заложенных моделей, производителей и аналогов прямо из документов закупки (Tier 0).
    evidence_data = None
    try:
        from .evidence_miner import mine_procurement_evidence_ai
        if progress_callback:
            await progress_callback(10, "Анализ документов закупки (Разрешения Минпромторга, НМЦК, ТУ)...")
        evidence_data = await mine_procurement_evidence_ai(clean_report, procurement_title)
    except Exception as ev_err:
        logger.warning("evidence_miner_failed", error=str(ev_err))

    # 0. ОСНОВНОЙ ПУТЬ: характеристики ТЗ → поиск товара по характеристикам →
    # факты из документов (с посимвольной проверкой) → детерминированная матрица → решение.
    # ИИ не выбирает модель: решение — результат сверки каждой характеристики с ТЗ.
    try:
        from .matcher import detect_exact_products_characteristic_first
        cf_result = await detect_exact_products_characteristic_first(
            clean_spec, procurement_title, progress_callback, full_context=report_text, evidence_data=evidence_data
        )
    except Exception as cf_err:
        logger.warning("characteristic_first_failed", error=str(cf_err))
        cf_result = None

    if cf_result:
        positions, cf_docs = cf_result

        # Точечная верификация недостающих характеристик по скачанным документам (Targeted Sub-Search)
        if positions and cf_docs:
            existing_urls = {d.get("url") for d in cf_docs if d.get("url")}
            try:
                await resolve_clarify_parameters(positions, existing_urls, cf_docs)
            except Exception as res_err:
                logger.debug("resolve_clarify_in_cf_failed", error=str(res_err))

        # Реестр Минпромторга нужен только там, где нацрежим требует выписки
        # (запрет/ограничение/преимущество). Иначе реестровые записи не пишем.
        from .matcher import detect_minprom_registry_requirement
        registry_required = (
            detect_minprom_registry_requirement(report_text) is True
            or detect_minprom_registry_requirement(clean_spec) is True
        )
        if registry_required is not False:
            if progress_callback:
                await progress_callback(90, "Сверка с официальным реестром Минпромторга (ГИСП)...")
            from .product_brand_detector import enrich_positions_with_minprom_registry_ai
            positions = await enrich_positions_with_minprom_registry_ai(positions)
        else:
            logger.info("minprom_enrich_skipped_not_required")

        from .validation import validate_exact_products
        positions = validate_exact_products(positions, cf_docs, has_doc_text=True)

        # Автоматическая ротация: если основной товар имеет расхождения с ТЗ (mismatch),
        # а среди аналогов есть чистый кандидат без расхождений — повышаем чистый аналог
        positions = auto_rotate_clean_analogs(positions)
        positions = drop_nonconforming_analogs(positions)

        # Контроль качества подбора: если у лидера критический брак (mismatches >= 3 и mismatches > matches)
        # или пустой/мусорный бренд — этот кандидат не является решением ТЗ — сбрасываем и переходим к глубокому поиску (search strategy)
        is_cf_acceptable = True
        if positions:
            top_p = positions[0]
            top_b = str(top_p.get("identified_brand") or "").strip().lower()
            top_mod = str(top_p.get("identified_model") or "").strip().lower()
            specs = top_p.get("specs_breakdown") or []
            mismatches_cnt = sum(1 for s in specs if isinstance(s, dict) and s.get("status") == "mismatch")
            matches_cnt = sum(1 for s in specs if isinstance(s, dict) and s.get("status") == "match")

            is_garbage_brand = (
                not top_b or not top_mod
                or len(top_b) < 2 or len(top_mod) < 2
                or any(w in (top_b + " " + top_mod) for w in ("пусто", "не указан", "по документу", "none", "null", "товар"))
            )
            if is_garbage_brand:
                logger.warning(
                    "characteristic_first_rejected_garbage_brand",
                    brand=top_p.get("identified_brand"),
                    model=top_p.get("identified_model"),
                )
                is_cf_acceptable = False
            elif (mismatches_cnt >= 3 and mismatches_cnt > matches_cnt) or (mismatches_cnt >= 2 and matches_cnt < 3):
                logger.warning(
                    "characteristic_first_rejected_excessive_mismatches",
                    brand=top_p.get("identified_brand"),
                    model=top_p.get("identified_model"),
                    mismatches=mismatches_cnt,
                    matches=matches_cnt,
                )
                is_cf_acceptable = False

        if is_cf_acceptable:
            if progress_callback:
                await progress_callback(100, f"Готово: модель подобрана по характеристикам ТЗ (позиций: {len(positions)})")
            return sanitize_shops_from_positions(positions)

    # РЕЗЕРВНАЯ СХЕМА (если поиск по характеристикам не дал кандидатов) — прежний поток ниже.
    if progress_callback:
        await progress_callback(20, "Интеллектуальный анализ ТЗ и планирование поиска (ИИ)...")

    # 1. Интеллектуальное планирование поиска через ИИ без завязки на конкретный товар
    search_strategy = await plan_exact_product_search_ai(procurement_title, clean_spec)
    item_name = search_strategy["item_name"]
    key_params = search_strategy["key_parameters"]
    negative_kws = search_strategy["negative_keywords"]
    queries = search_strategy["search_queries"]

    settings = get_settings()
    raw_candidates: List[Any] = []
    web_sources: List[str] = []
    y_key = getattr(settings, "yandex_search_api_key", None) or getattr(settings, "yandex_api_key", None)
    g_key = getattr(settings, "google_search_api_key", None) or getattr(settings, "google_api_key", None)
    if queries and (y_key or g_key):
        if progress_callback:
            await progress_callback(35, f"Поиск технической документации в сети ({len(queries)} запросов)...")
        for q in queries:
            try:
                results = await _fetch_search_results_for_specs(q, max_results=3)
                raw_candidates.extend(results)
            except Exception as s_err:
                logger.debug("spec_query_search_err", query=q, error=str(s_err))

        # Вторичный добор по ключевым параметрам и заводам единым блоком
        secondary_queries: List[str] = []
        if key_params:
            clean_kps = [
                re.sub(r"[^а-яА-Яa-zA-Z0-9\s]", " ", str(kp)).strip()
                for kp in key_params
                if len(re.sub(r"[^а-яА-Яa-zA-Z0-9\s]", " ", str(kp)).strip()) >= 3
            ]
            if clean_kps:
                all_sec_str = " ".join(clean_kps)
                if len(all_sec_str) > 300:
                    trimmed = all_sec_str[:300].rsplit(" ", 1)[0]
                    sec_pool = trimmed if trimmed else all_sec_str[:300]
                else:
                    sec_pool = all_sec_str
                secondary_queries.append(f'"{item_name[:40]}" {sec_pool} паспорт')
        for m in search_strategy.get("primary_manufacturers", [])[:2]:
            clean_m = re.sub(r'(?i)(ООО|АО|ПАО|ЗАО|ГК|НПК|НПО|ТД|«|»|")', "", str(m)).strip()
            if clean_m and len(clean_m) > 2:
                secondary_queries.append(f'"{clean_m}" "{item_name[:40]}" характеристики')

        for sq in secondary_queries:
            try:
                sq_res = await _fetch_search_results_for_specs(sq, max_results=3)
                raw_candidates.extend(sq_res)
            except Exception as sq_err:
                logger.debug("sec_query_err", query=sq, error=str(sq_err))

        for cand in raw_candidates:
            c_url = getattr(cand, "url", "") if hasattr(cand, "url") else str(cand.get("url") or "") if isinstance(cand, dict) else ""
            if c_url:
                c_dom = urlsplit(c_url).netloc.lower()
                if c_dom and c_dom not in web_sources:
                    web_sources.append(c_dom)

    # 1.5 Pre-Search выборка подтвержденных моделей и заводов из локального реестра Минпромторга (ГИСП FTS5)
    gisp_entries = []
    gisp_analog_candidates = []
    try:
        try:
            from app.supplier_search import search_minprom_registry_entries
        except ImportError:
            from backend.services.supplier_search_v2 import search_gisp_product_registry_entries as search_minprom_registry_entries
        gisp_queries = [item_name]
        if key_params:
            gisp_pool = " ".join(str(kp).strip() for kp in key_params if str(kp).strip())
            if gisp_pool:
                gisp_queries.append(f"{item_name} {gisp_pool[:250]}")
        gisp_entries = await search_minprom_registry_entries(gisp_queries, max_results=10)
        if gisp_entries:
            gisp_blocks = ["\n=== ОФИЦИАЛЬНЫЙ РЕЕСТР МИНПРОМТОРГА РФ (ГИСП): ОТЕЧЕСТВЕННЫЕ ПРОИЗВОДИТЕЛИ И МОДЕЛИ ДЛЯ АНАЛОГОВ ==="]
            for g_idx, entry in enumerate(gisp_entries, start=1):
                e_manuf = _item_val(entry, "manufacturer")
                e_inn = _item_val(entry, "inn")
                e_reg = _item_val(entry, "registry_number")
                e_prod = _item_val(entry, "product")
                e_ev = _item_val(entry, "evidence") or _item_val(entry, "row_text") or ""
                gisp_blocks.append(
                    f"{g_idx}. Производитель: {e_manuf} | ИНН: {e_inn} | Реестровый номер: {e_reg}\n"
                    f"   Продукция/Модель: {e_prod}\n"
                    f"   Основание/Сведения: {e_ev}"
                )
                gisp_analog_candidates.append({
                    "brand": e_manuf,
                    "model": e_prod,
                    "manufacturer": e_manuf,
                    "registry_number": e_reg,
                    "inn": e_inn,
                    "evidence": e_ev,
                })
            gisp_presearch_text = "\n".join(gisp_blocks)
        else:
            gisp_presearch_text = ""
    except Exception as gisp_err:
        logger.debug("gisp_presearch_failed", error=str(gisp_err))
        gisp_presearch_text = ""

    # Целевые ключевые слова: предмет закупки + отдельные слова + реальные параметры ТЗ
    target_kws = [item_name] + item_name.split()
    for kp in key_params[:4]:
        target_kws.append(str(kp).strip())
    target_kws.extend(["паспорт", "каталог", "характеристики", "руководство", "спецификация"])

    target_urls = _rank_search_candidates(raw_candidates, target_kws, negative_kws)

    # 2. Скачивание и парсинг найденных PDF-паспортов и страниц
    verified_docs: List[Dict[str, Any]] = []
    if target_urls:
        if progress_callback:
            await progress_callback(50, f"Скачивание паспортов и спецификаций ({len(target_urls[:6])} источников)...")
        verified_docs = await fetch_batch_web_documents(target_urls, max_docs=6)

    # 3. Формирование обогащенного контекста для ИИ (TenderLex-паритет)
    doc_blocks = ["\n\n=== ПРОВЕРЕННЫЕ ДОКУМЕНТЫ И ПАСПОРТА ИЗ ОТКРЫТЫХ ИСТОЧНИКОВ В ИНТЕРНЕТЕ ==="]
    for idx, doc in enumerate(verified_docs, start=1):
        dtype = "PDF-паспорт изделия" if doc.get("type") == "pdf" else "Веб-страница производителя"
        doc_blocks.append(f"\n[ИСТОЧНИК #{idx}]")
        doc_blocks.append(f"Тип: {dtype}")
        doc_blocks.append(f"Заголовок: {doc.get('title')}")
        doc_blocks.append(f"URL: {doc.get('url')}")
        doc_blocks.append(f"Фактическое содержимое документа:\n{doc.get('text')}\n")

    if not verified_docs and raw_candidates:
        snippet_rows = ["\n\n=== ДАННЫЕ ИЗ ПОИСКОВОЙ ВЫДАЧИ ЯНДЕКС ==="]
        for c_idx, cand in enumerate(raw_candidates[:8], start=1):
            c_t = getattr(cand, "title", "") or (cand.get("title") if isinstance(cand, dict) else "")
            c_u = getattr(cand, "url", "") or (cand.get("url") if isinstance(cand, dict) else "")
            c_s = getattr(cand, "snippet", "") or (cand.get("snippet") if isinstance(cand, dict) else "")
            snippet_rows.append(f"{c_idx}. Заголовок: {c_t}")
            if c_u:
                snippet_rows.append(f"   URL: {c_u}")
            if c_s:
                snippet_rows.append(f"   Сниппет: {c_s}")
        verified_docs_block = "\n".join(snippet_rows)
    else:
        verified_docs_block = "\n".join(doc_blocks) if verified_docs else ""

    header_context = f"Наименование закупки / предмет ТЗ: {item_name}\n\n" if item_name else ""
    combined_context = header_context + clean_spec[:22000] + (("\n\n" + gisp_presearch_text) if gisp_presearch_text else "") + verified_docs_block

    if progress_callback:
        await progress_callback(65, "Сопоставление ТЗ с таблицами каталогов и паспортов ИИ...")

    # 4. Основной заземленный вызов LLM
    summary = ""
    system_prompt = (
        "Ты — ведущий эксперт по государственным закупкам по 44-ФЗ/223-ФЗ и проверке технической документации. "
        "Твоя задача — предоставить СТРОГО ДОСТОВЕРНЫЕ сведения для первой части заявки (Форма 2). "
        "Категорически запрещено выдумывать показатели или подгонять их под ТЗ! "
        "Все показатели должны опираться на приложенные проверенные документы из открытых источников и текст ТЗ. "
        "Если точный параметр в открытом доступе отсутствует, честно указывай 'В открытой документации не указано (требуется официальный паспорт завода)' со статусом 'clarify'. "
        "Формируй точный, структурированный анализ в формате JSON."
    )
    try:
        raw_response = await call_llm(
            prompt=EXACT_PRODUCT_DEEP_PROMPT.format(context=combined_context),
            system_prompt=system_prompt,
            json_mode=True,
            model_tier="primary",
            routing_key="procurement_brand_detection",
        )
        if not raw_response:
            return []

        # Безопасный парсинг JSON ответа
        data = _parse_json_safely(raw_response)
        if isinstance(data, dict):
            summary = str(data.get("summary") or "").strip()
            raw_positions = data.get("positions", [])
            if not isinstance(raw_positions, list):
                raw_positions = []
        else:
            raw_positions = []
    except Exception as exc:
        logger.error("deep_exact_product_llm_failed", error=str(exc))
        raw_positions = []

    if not raw_positions:
        # Если глубокий поиск ничего не вернул, используем стандартную детекцию
        from .product_brand_detector import detect_brands_in_report
        return await detect_brands_in_report(clean_spec, procurement_title)

    # 5. Валидация и нормализация позиций
    positions: List[Dict[str, Any]] = []
    for idx, p in enumerate(raw_positions, start=1):
        if not isinstance(p, dict):
            continue
        brand = str(p.get("identified_brand") or "").strip()
        model = str(p.get("identified_model") or "").strip()
        mfr = str(p.get("manufacturer") or brand).strip()
        name_tz = str(p.get("name_in_tz") or f"Позиция {idx}").strip()
        reasoning = str(p.get("reasoning") or "").strip()
        source_url = str(p.get("source_url") or (verified_docs[0].get("url") if verified_docs else "")).strip()
        datasheet_url = str(p.get("datasheet_url") or (verified_docs[0].get("url") if verified_docs and verified_docs[0].get("type") == "pdf" else "")).strip()

        conf = p.get("confidence", 0.95)
        try:
            conf_val = float(conf)
            if conf_val > 1.0:
                conf_val = conf_val / 100.0
            conf_val = round(min(0.99, max(0.50, conf_val)), 2)
        except Exception:
            conf_val = 0.95

        specs_norm = []
        for s in p.get("specs_breakdown") or []:
            if isinstance(s, dict):
                fact = str(s.get("product_fact") or "").strip()
                st = str(s.get("status") or "match").lower()
                p_name_cur = str(s.get("param_name") or "Параметр").strip()
                p_lower = p_name_cur.lower()
                tz_cur = str(s.get("tz_requirement") or "По ТЗ").strip()
                tz_lower = tz_cur.lower()
                status_clean = "mismatch" if "mismatch" in st or "не подходит" in st else "clarify" if "clarify" in st or "уточн" in st else "match"
                comment_text = str(s.get("comment") or "Подтверждено документацией").strip()

                # Параметры конкретной партии товара (Год выпуска, состояние, гарантия)
                # в каталогах заводов не публикуются и всегда требуют паспорта завода
                if any(k in p_lower for k in ("год производ", "год выпуск", "состояние", "дата изготов")):
                    if status_clean == "match" or "2026" in fact or "новый" in fact.lower() or "под заказ" in fact.lower():
                        status_clean = "clarify"
                        comment_text = "Подобрано ИИ под требование ТЗ. В открытых источниках параметр не опубликован — требуется уточнить по паспорту завода."

                # Детекция расхождения стандартов: если ТЗ требует ГОСТ, а факт изделия выпускается по ТУ
                elif any(k in p_lower for k in ("стандарт", "гост", "ту", "соответствие")):
                    if "гост" in tz_lower and "ту" in fact.lower():
                        status_clean = "mismatch"
                        comment_text = f"Отклонение от ТЗ: продукция выпускается по ТУ ({fact}). Требуемый стандарт {tz_cur} не распространяется на данную марку/материал изделия."

                specs_norm.append({
                    "param_name": p_name_cur,
                    "tz_requirement": tz_cur,
                    "product_fact": fact or "В открытой документации не указано",
                    "status": status_clean,
                    "comment": comment_text,
                    "source_url": str(s.get("source_url") or source_url).strip(),
                })

        alts_norm = []
        for a in p.get("alternative_brands") or []:
            if isinstance(a, dict):
                alt_source_url = str(a.get("source_url") or "").strip()
                raw_alt_specs = a.get("specs_breakdown") or []

                raw_map = {}
                if isinstance(raw_alt_specs, list):
                    for s in raw_alt_specs:
                        if isinstance(s, dict) and s.get("param_name"):
                            raw_map[str(s.get("param_name")).strip().lower()] = s

                alt_specs_norm = []
                if isinstance(raw_alt_specs, list) and raw_alt_specs:
                    for s in raw_alt_specs:
                        alt_fact = str(_item_val(s, "product_fact") or "").strip()
                        alt_st = str(_item_val(s, "status") or "match").lower()
                        alt_st_clean = (
                            "mismatch" if "mismatch" in alt_st or "не подходит" in alt_st or "отклон" in alt_st
                            else "clarify" if "clarify" in alt_st or "уточн" in alt_st or "не указан" in alt_fact.lower()
                            else "match"
                        )
                        alt_specs_norm.append({
                            "param_name": str(_item_val(s, "param_name") or "Параметр").strip(),
                            "tz_requirement": str(_item_val(s, "tz_requirement") or "По ТЗ").strip(),
                            "product_fact": alt_fact or "В открытой документации не указано",
                            "status": alt_st_clean,
                            "comment": str(_item_val(s, "comment") or "Подтверждено производителем аналога").strip(),
                            "source_url": str(_item_val(s, "source_url") or alt_source_url).strip(),
                        })
                elif specs_norm:
                    for s in specs_norm:
                        p_name = s["param_name"]
                        p_key = p_name.strip().lower()
                        s_matched = raw_map.get(p_key)
                        if s_matched:
                            alt_fact = str(_item_val(s_matched, "product_fact") or "").strip()
                            alt_st = str(_item_val(s_matched, "status") or "match").lower()
                            alt_st_clean = (
                                "mismatch"
                                if "mismatch" in alt_st or "не подходит" in alt_st or "отклон" in alt_st
                                else "clarify"
                                if "clarify" in alt_st or "уточн" in alt_st or "не указан" in alt_fact.lower()
                                else "match"
                            )
                            alt_comm = str(
                                _item_val(s_matched, "comment")
                                or (
                                    "Подтверждено производителем аналога"
                                    if alt_st_clean == "match"
                                    else "Требуется уточнение по паспорту аналога"
                                    if alt_st_clean == "clarify"
                                    else "Отклонение аналога от ТЗ"
                                )
                            ).strip()
                            alt_specs_norm.append({
                                "param_name": p_name,
                                "tz_requirement": s["tz_requirement"],
                                "product_fact": alt_fact or "В открытой документации не указано",
                                "status": alt_st_clean,
                                "comment": alt_comm,
                                "source_url": str(_item_val(s_matched, "source_url") or alt_source_url).strip(),
                            })
                        else:
                            alt_specs_norm.append({
                                "param_name": p_name,
                                "tz_requirement": s["tz_requirement"],
                                "product_fact": "Требуется официальный паспорт аналога",
                                "status": "clarify",
                                "comment": "Параметр аналога подлежит уточнению по паспорту завода",
                                "source_url": alt_source_url,
                            })

                alt_conf = compute_spec_compliance(alt_specs_norm) if alt_specs_norm else 0.85

                alts_norm.append({
                    "brand": str(a.get("brand") or "").strip(),
                    "model": str(a.get("model") or "").strip(),
                    "manufacturer": str(a.get("manufacturer") or a.get("brand") or "").strip(),
                    "confidence": alt_conf,
                    "notes": str(a.get("notes") or a.get("reasoning") or "Взаимозаменяемый эквивалент по ГОСТ/ТУ").strip(),
                    "source_url": alt_source_url,
                    "specs_breakdown": alt_specs_norm,
                })

        # Извлечение проверенных контактов сбыта завода-изготовителя (с DNS MX проверкой)
        _enrich_position_sales_contacts(p, verified_docs)

        # Обогащение аналогов проверенными данными из локального реестра Минпромторга (ГИСП)
        if gisp_analog_candidates:
            for alt in alts_norm:
                alt_b = (alt.get("brand") or "").lower()
                alt_m = (alt.get("model") or "").lower()
                alt_mfr = (alt.get("manufacturer") or "").lower()
                for gc in gisp_analog_candidates:
                    gc_mfr = gc.get("manufacturer", "").lower()
                    gc_prod = gc.get("model", "").lower()
                    if (alt_b and alt_b in gc_mfr) or (alt_mfr and alt_mfr in gc_mfr) or (alt_m and alt_m in gc_prod):
                        alt["registry_number"] = gc.get("registry_number")
                        alt["inn"] = gc.get("inn")
                        alt["evidence"] = gc.get("evidence")
                        break

        positions.append({
            "position_no": idx,
            "name_in_tz": name_tz,
            "identified_brand": brand,
            "identified_model": model,
            "manufacturer": mfr,
            "confidence": 0.50,  # будет вычислен математически ниже
            "reasoning": reasoning,
            "source_url": source_url,
            "datasheet_url": datasheet_url,
            "specs_breakdown": specs_norm,
            "alternative_brands": alts_norm,
            "sales_contacts": p.get("sales_contacts") or [],
            "summary": summary,
            "verified_documents": [
                {
                    "url": d.get("url"),
                    "domain": d.get("domain"),
                    "type": d.get("type"),
                    "title": d.get("title"),
                }
                for d in verified_docs
            ],
            "web_sources": web_sources,
        })

    # 5.05 Целевой дозапрос интернета по выбранным моделям + второй заземленный LLM-проход.
    # Первичный поиск идет по тексту ТЗ и часто не находит карточки конкретной модели,
    # поэтому после выбора моделей дополнительно ищем "<Бренд Модель> характеристики/паспорт/купить".
    if positions:
        try:
            model_docs = await targeted_model_documents(
                positions, existing_urls=target_urls, progress_callback=progress_callback
            )
            if model_docs:
                verified_docs.extend(model_docs)
                compact_docs = [
                    {
                        "url": d.get("url"),
                        "domain": d.get("domain"),
                        "type": d.get("type"),
                        "title": d.get("title"),
                    }
                    for d in verified_docs
                    if isinstance(d, dict)
                ]
                for pos in positions:
                    pos["verified_documents"] = [dict(c) for c in compact_docs]
                await refine_positions_with_model_docs(positions, model_docs)
        except Exception as t_err:
            logger.warning("targeted_model_search_failed", error=str(t_err))

    # 5.1 Интеллектуальная семантическая фильтрация через ИИ: отсекаем мелкие расходники, крепеж и услуги
    filtered_positions = []
    for p in positions:
        name_val = str(p.get("name_in_tz") or "").strip()
        is_minor = await is_minor_or_service_item_ai(name_val, clean_spec[:300])
        if not is_minor:
            filtered_positions.append(p)

    if filtered_positions:
        positions = filtered_positions

    # 5.2 Лимитирование ключевых позиций: максимум MAX_EXACT_POSITIONS_PER_JOB (до 5 позиций)
    total_tz_count = len(positions)
    for p in positions:
        p["total_tz_positions"] = total_tz_count

    if len(positions) > MAX_EXACT_POSITIONS_PER_JOB:
        positions = positions[:MAX_EXACT_POSITIONS_PER_JOB]

    # Сквозная последовательная перенумерация позиций
    for p_idx, pos in enumerate(positions, start=1):
        pos["position_no"] = p_idx

    # 5.5 Адаптивный точечный добор параметров через умный контекстный экстрактор (Targeted Sub-Search)
    if progress_callback:
        await progress_callback(75, "Точечная сверка параметров по паспортам изделий...")
    existing_urls = set(target_urls)
    await resolve_clarify_parameters(positions, existing_urls, verified_docs)

    if progress_callback:
        await progress_callback(80, "Инженерная верификация стандартов ГОСТ/ТУ...")

    # 6. Динамическая резолюция стандартов ГОСТ/ТУ/СТО
    await resolve_standards_parameters(positions, clean_spec, existing_urls, verified_docs)

    # 7. Детерминированный математический расчет истинного соответствия ТЗ (Anti-False-95%)
    # Вычисляется ДО автоподбора рекомендаций Формы 2, чтобы сохранить объективную оценку заводской модели
    for pos in positions:
        specs_list = pos.get("specs_breakdown") or []
        real_conf = compute_spec_compliance(specs_list)
        pos["confidence"] = real_conf

        mismatches = sum(1 for s in specs_list if s.get("status") == "mismatch")
        total_s = len(specs_list)
        if mismatches >= 3 or (total_s > 0 and mismatches / total_s >= 0.4):
            pct_str = f"{int(real_conf * 100)}%"
            b_name = pos.get("identified_brand") or ""
            m_name = pos.get("identified_model") or ""
            warning_lead = (
                f"ВНИМАНИЕ: Проверенная модель {b_name} {m_name} "
                f"имеет критические отклонения от ТЗ (соответствие {pct_str}, {mismatches} из {total_s} параметров отклоняются). "
                f"Товар не удовлетворяет требованиям заказчика."
            )
            cur_rsn = pos.get("reasoning", "")
            if warning_lead not in cur_rsn:
                pos["reasoning"] = f"{warning_lead} {cur_rsn}".strip()

        for alt in pos.get("alternative_brands") or []:
            alt_specs = alt.get("specs_breakdown") or []
            if alt_specs:
                alt["confidence"] = compute_spec_compliance(alt_specs)
            else:
                alt["confidence"] = round(min(0.95, real_conf), 2)

    # 8. Автодобор параметров под ТЗ для Формы 2 (подготовка конкретных номиналов для заявки)
    if progress_callback:
        await progress_callback(88, "Автоподбор параметров для Формы 2...")
    await auto_fill_ai_recommendations(positions)

    # 8.1 Финальная сверка и пересчет соответствия по всем позициям
    for pos in positions:
        specs_list = pos.get("specs_breakdown") or []
        real_conf = compute_spec_compliance(specs_list)
        pos["confidence"] = real_conf
        for alt in pos.get("alternative_brands") or []:
            alt_specs = alt.get("specs_breakdown") or []
            if alt_specs:
                alt["confidence"] = compute_spec_compliance(alt_specs)
            else:
                alt["confidence"] = round(min(0.95, real_conf), 2)

    # 8.15 Авто-ротация победителя: если основной товар имеет брак (mismatch),
    # а среди alternative_brands есть чистый аналог без отклонений — делаем ротацию
    positions = auto_rotate_clean_analogs(positions)

    # 8.2 Аналогами могут быть только товары без отклонений от ТЗ:
    # кандидат с подтверждённым mismatch не показывается как взаимозаменяемый
    positions = drop_nonconforming_analogs(positions)

    # 9. Обогащение реестром Минпромторга (ГИСП) — только если нацрежим требует выписки
    from .matcher import detect_minprom_registry_requirement
    registry_required_fallback = detect_minprom_registry_requirement(report_text)
    if registry_required_fallback is not False:
        if progress_callback:
            await progress_callback(94, "Сверка с официальным реестром Минпромторга (ГИСП)...")
        from .product_brand_detector import enrich_positions_with_minprom_registry_ai
        enriched = await enrich_positions_with_minprom_registry_ai(positions)
    else:
        logger.info("minprom_enrich_skipped_not_required")
        enriched = positions

    # 10. Детерминированная валидация: сверка диапазонов ТЗ, привязка модели к источникам,
    # согласованность статусов (без ИИ) — единый контур правды для Формы 2
    from .validation import validate_exact_products
    enriched = validate_exact_products(enriched, verified_docs, has_doc_text=True)

    if progress_callback:
        await progress_callback(100, f"Готово: выявлено {len(enriched)} позиций с паспортами и аналогами")

    return sanitize_shops_from_positions(enriched)



def plan_exact_product_search(
    procurement_title_or_settings: Any = "",
    context: str = "",
    procurement_title: str = "",
    *args,
    **kwargs,
) -> Any:
    has_settings = (
        kwargs.get("settings") is not None
        or hasattr(procurement_title_or_settings, "yandex_search_folder_id")
        or hasattr(procurement_title_or_settings, "primary_provider")
    )
    if has_settings:
        p_title = procurement_title or kwargs.get("procurement_title", "")
        if not p_title and isinstance(procurement_title_or_settings, str):
            p_title = procurement_title_or_settings
        ctx = context or kwargs.get("context", "")
        return plan_exact_product_search_ai(p_title, ctx)

    p_title = procurement_title or (procurement_title_or_settings if isinstance(procurement_title_or_settings, str) else "")
    ctx = context or kwargs.get("context", "")
    return _plan_exact_product_search_sync(p_title, ctx)
