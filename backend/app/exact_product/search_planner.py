from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from ..ai import call_llm
from ..models import SystemSettings
from ..supplier_search import _search_with_yandex, _yandex_credentials
from .fetcher import fetch_batch_web_documents
from .models import ExactProductPosition, SpecParameterMatch
from .validation import _is_placeholder_brand_or_model, extract_standards_from_text

import sys

logger = logging.getLogger("tenderlex.exact_product.search_planner")


def _get_call_llm():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "call_llm"):
        return getattr(mod, "call_llm")
    from ..ai import call_llm
    return call_llm


def _get_search_with_yandex():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "_search_with_yandex"):
        return getattr(mod, "_search_with_yandex")
    from ..supplier_search import _search_with_yandex
    return _search_with_yandex


def _get_yandex_credentials():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "_yandex_credentials"):
        return getattr(mod, "_yandex_credentials")
    from ..supplier_search import _yandex_credentials
    return _yandex_credentials


def _get_fetch_batch_web_documents():
    mod = sys.modules.get("app.exact_product")
    if mod and hasattr(mod, "fetch_batch_web_documents"):
        return getattr(mod, "fetch_batch_web_documents")
    from .fetcher import fetch_batch_web_documents
    return fetch_batch_web_documents


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
   - "identified_brand": "реальный завод или бренд из найденного документа"
   - "identified_model": "точная модель/серия/марка из документа (например: ПГП-4 (Мини), СПП-4)"
   - "manufacturer": "завод-производитель (например: ООО «Прессмакс»)"
3. Если значения НЕТ в тексте:
   - "found": false
   - "product_fact": "В открытой документации не указано (требуется официальный паспорт завода)"
   - "status": "clarify"
   - "comment": "Требуется официальный паспорт завода"

Ответь СТРОГО в формате JSON:
{{
  "found": true,
  "product_fact": "...",
  "status": "match",
  "comment": "...",
  "identified_brand": "...",
  "identified_model": "...",
  "manufacturer": "..."
}}
"""

RESOLVE_STANDARDS_PROMPT = """Ты — ведущий эксперт по стандартам ГОСТ, ТУ и ЕСКД в государственных закупках (44-ФЗ/223-ФЗ).
Твоя задача — проверить требование ТЗ к товару «{brand} {model}» (стандарт: {std}) и определить нормативное значение параметра по ГОСТ/ТУ.

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
3. Класс защиты от поражения электрическим током (ГОСТ 12.2.007.0-75):
   - Класс I: рабочая изоляция + защитный заземляющий провод/зажим.
   - Класс II: двойная или усиленная изоляция без заземления.
   - Класс III: питание от источника БСНН (до 50 В).
4. Осветительные приборы (ГОСТ Р 54350-2015 / СП 52.13330):
   - Коэффициент пульсации светового потока: для наружного освещения улиц и дорог пульсация не нормируется (или < 10-15%); для рабочих мест и помещений с компьютерами < 5-10%.
   - Индекс цветопередачи (CRI): наружное освещение Ra >= 70 или Ra >= 80; теплый/нейтральный белый свет 3000-5000 К.
5. Трубы напорные полиэтиленовые (ГОСТ 18599-2001):
   - ПЭ 100 SDR 17: номинальное рабочее давление 1.0 МПа (10 бар/атм).
   - ПЭ 100 SDR 11: номинальное рабочее давление 1.6 МПа (16 бар/атм).
   - ПЭ 100 SDR 13.6: номинальное рабочее давление 1.25 МПа.
6. Показывающие манометры (ГОСТ 2405-88):
   - Стандартные классы точности: 0.4; 0.6; 1.0; 1.5; 2.5.
   - Резьба присоединительного штуцера: для диаметра корпуса 100 мм стандартно М20х1.5 (или G1/2).
7. Запорная и регулирующая арматура (ГОСТ 33259-2015, ГОСТ 12815, ГОСТ 5762):
   - Фланцы по ГОСТ 33259 на PN 1.6 МПа: тип 01 (плоские приварные) или тип 11 (воротниковые приварные встык).
8. Кабели силовые (ГОСТ 31996-2012 / ГОСТ 22483-2021):
   - Номинальное переменное напряжение: 0.66 кВ или 1.0 кВ при частоте 50 Гц.
   - Класс токопроводящих жил: 1 класс (однопроволочная жила сечением до 16 мм2) или 2 класс (многопроволочная).

Если параметр однозначно следует из стандарта:
- "found": true
- "product_fact": "конкретное нормативное значение" (например: "от -60 до +40 °С", "Класс I", "IP66", "1.0 МПа (SDR 17)")
- "status": "match" (если укладывается в требование ТЗ) или "mismatch" (если противоречит ТЗ)
- "comment": "Подтверждено требованиями ГОСТ (указать стандарт и пункт/таблицу)"

Если в стандарте нет этого параметра:
- "found": false
- "product_fact": "В открытой документации не указано"
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

AUTO_FILL_RECOMMENDATIONS_PROMPT = """
Ты старший инженер-технолог по подготовке заявок (Форма 2) по 44-ФЗ и 223-ФЗ.
Для товара «{brand} {model}» ({manufacturer}) следующие параметры отсутствуют в открытых паспортах завода в интернете.

Необходимо сформировать точные, конкретные значения показателей (без слов 'не менее', 'не более', 'от', 'до', без диапазонов, с обязательными единицами измерения), которые:
1. Строго удовлетворяют требованиям ТЗ заказчика.
2. Физически и технологически реалистичны для данной модели и категории товаров в РФ.
3. Готовы для включения в столбец «Конкретные показатели товара» Формы 2 первой части заявки.

Список параметров и требований ТЗ:
{params_list}

Ответь СТРОГО валидным JSON-списком объектов:
[
  {{
    "param_name": "Название параметра строго как в списке выше",
    "recommended_fact": "Конкретное значение с единицами измерения (например: 550%, 1500 об/мин, 0.02 МПа, 24 часа)",
    "comment": "Подобрано ИИ под требование ТЗ. В открытых источниках параметр не опубликован — требуется уточнить по паспорту или официальному документу производителя перед подачей заявки."
  }}
]
"""


def _parse_json_safely(raw_text: str) -> Optional[Any]:
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        return data
    except Exception:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    cleaned_no_commas = re.sub(r",\s*([\]}])", r"\1", cleaned)
    try:
        return json.loads(cleaned_no_commas)
    except Exception:
        pass

    return None


def extract_clean_spec_text(text: str) -> str:
    """Извлекает ключевой фрагмент технического задания или спецификации."""
    if not text:
        return ""
    cleaned = text.strip()
    if len(cleaned) <= 15000:
        return cleaned

    match = re.search(
        r"(?i)(?:(?:#+\s*)?(?:ТЕХНИЧЕСКОЕ\s+ЗАДАНИЕ|СПЕЦИФИКАЦИЯ|ОПИСАНИЕ\s+ОБЪЕКТА\s+ЗАКУПКИ|ТРЕБОВАНИЯ\s+К\s+ТОВАРУ|ТАБЛИЦА\s+ХАРАКТЕРИСТИК))(.+)",
        cleaned,
        re.DOTALL,
    )
    if match and len(match.group(1).strip()) > 100:
        cleaned = match.group(0).strip()

    if len(cleaned) > 35000:
        cleaned = cleaned[:35000]
    return cleaned


def extract_real_item_name(context: str, fallback_title: str = "") -> str:
    """
    Извлекает реальное наименование товара/оборудования из текста спецификации,
    игнорируя канцелярские заголовки документов вроде 'Приложение №1 Описание объекта закупки'.
    """
    if not context and not fallback_title:
        return "Оборудование / Товар по ТЗ"

    if context:
        quote_match = re.search(r'(?i)[«\"\“]\s*(?:поставка|приобретение|изготовление)\s+([^»\"\”\n\r\|]{6,120})[»\"\”]', context)
        if quote_match:
            cand = quote_match.group(1).strip()
            cand = re.sub(r'(?i)\b(для\s+нужд|в\s+соответствии|согласно|по\s+адресу)\b.*', '', cand).strip(' :—–-|«»"')
            if len(cand) >= 6:
                return cand

        patterns = [
            r"(?i)(?:наименование\s+(?:товара|изделия|оборудования|медицинского\s+изделия|объекта\s+закупки|продукции|мтр))\s*[:\|\t\.\-–—]\s*([^\n\r\|]{4,120})",
            r"(?i)(?:предмет\s+(?:закупки|договора|контракта|поставки))\s*[:\|\t\.\-–—]\s*([^\n\r\|]{4,120})",
            r"(?i)(?:на\s+поставку|поставка|приобретение)\s+([а-яА-Яa-zA-Z0-9\s\-\(\)\.,]{6,100}?)(?=\s+(?:для|по\s+адресу|в\s+соответствии|согласно|$|\n|\r))",
        ]
        for pat in patterns:
            for m in re.finditer(pat, context):
                cand = m.group(1).strip()
                cand = re.sub(r'^\s*(?:1\.1\.|1\.|№\s*\d+|\-|\•)\s*', '', cand)
                cand = re.sub(r'(?i)\b(согласно|в соответствии|техническое задание|приложение|таблица|гост|для нужд)\b.*', '', cand).strip(' :—–-|«»"_')
                alpha_count = len(re.findall(r'[а-яА-Яa-zA-Z]', cand))
                if alpha_count >= 4 and not cand.lower().startswith("приложение"):
                    return cand

    if fallback_title:
        f_clean = re.sub(r'\.(docx|pdf|xlsx|doc|txt)$', '', fallback_title, flags=re.I)
        parts = [p.strip() for p in f_clean.split('_') if len(p.strip()) >= 4]
        clean_parts = []
        for p in parts:
            if re.search(r'(?i)(roseltorg|zakupki|sberbank|млн|руб|\.ru|\.com|приложение|извещение|аэф|тз|описание\s+объекта)', p):
                continue
            if re.match(r'^\d+$', p):
                continue
            clean_parts.append(p)
        if clean_parts:
            best_part = max(clean_parts, key=lambda x: (bool(re.search(r'(?i)(здание|оборудование|товар|машина|комплекс|установка|поставка|материал|прибор|канат|станок|система)', x)), len(x)))
            if len(best_part) >= 6 and len(re.findall(r'[а-яА-Яa-zA-Z]', best_part)) >= 5:
                return best_part

    if context:
        for line in context.splitlines()[:30]:
            l_str = line.strip().strip('«»"')
            if len(l_str) < 10 or len(l_str) > 120:
                continue
            if re.search(r'(?i)(утверждаю|согласовано|приложение|телефон|инн|огрн|адрес|россия|общество|директор|заказчик|глава|описание\s+объекта)', l_str):
                continue
            if re.search(r'(?i)(поставка|комплекс|установка|станок|канат|прибор|аппарат|машина|изделие|оборудование|система|материал|шовная|состав)', l_str):
                l_clean = re.sub(r'(?i)^(?:поставка|приобретение|изготовление)\s+', '', l_str)
                l_clean = re.sub(r'(?i)\b(для\s+нужд|по\s+адресу|согласно|в\s+соответствии)\b.*', '', l_clean).strip(' :—–-|«»"')
                if len(l_clean) >= 6:
                    return l_clean

    return fallback_title or "Оборудование / Товар по ТЗ"


def extract_key_search_parameters(context: str) -> list[str]:
    """
    Извлекает числовые характеристики, производительность, мощность, габариты и ГОСТ/ОКПД2
    для формирования высокоточных поисковых запросов без галлюцинаций для любых отраслей.
    """
    params: list[str] = []
    if not context:
        return params

    okpd = re.findall(r'\b\d{2}\.\d{2}\.\d{2}(?:\.\d{3})?\b', context)
    for code in okpd[:2]:
        params.append(f"ОКПД2 {code}")

    standards = re.findall(r'\b(?:ГОСТ(?:\s*Р)?|ТУ|СТО|ОСТ)\s*[\d\.\-]+', context, re.IGNORECASE)
    for s in standards[:2]:
        clean_s = s.strip(' .,;:|')
        if clean_s and clean_s not in params:
            params.append(clean_s)

    unit_patterns = [
        r'(\b\d+(?:[\.,]\d+)?\s*(?:тестов|шт|м|м3|л|пачек|циклов|тактов|ударов|оборотов|кг|т)(?:/(?:ч|мин|с|сут)|\s*в\s*(?:час|минуту|секунду|сутки))?\b)',
        r'(\b(?:не\s*менее|не\s*более|от|до)?\s*\d+(?:[\.,]\d+)?\s*(?:кВт|МВт|Вт|кВА|МВА|ВА|об/мин|м3/ч|л/ч|л/мин|мм2|см2|м2|мкм|мм|см|м|кг|т|кН|Н|МПа|кПа|Па|бар|атм|°C|град|В|кВ|мВ|А|мА|Гц|кГц|МГц|Ом|кОм|кювет|реагентов|позиций|литров|м3|л|дБ))\b',
    ]
    for pat in unit_patterns:
        matches = re.findall(pat, context, re.IGNORECASE)
        for m in matches[:4]:
            m_clean = m.strip()
            if m_clean and len(m_clean) >= 3 and m_clean not in params:
                params.append(m_clean)

    return params[:6]


def build_universal_negative_keywords(clean_context: str) -> list[str]:
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


def _extract_relevant_spec_excerpts(doc_text: str, param_name: str, max_total_chars: int = 18000) -> str:
    """
    Интеллектуальный экстрактор спецификаций из полного текста документа.
    Находит разделы со сводными таблицами характеристик и контекстные фрагменты вокруг названия параметра.
    """
    if not doc_text:
        return ""
    if len(doc_text) <= max_total_chars:
        return doc_text

    # Первые 4500 символов (общие сведения, паспортная таблица модели)
    head = doc_text[:4500]
    chunks = [head]
    current_len = len(head)

    # Поиск ключевых терминов параметра в остальном теле документа
    raw_words = [w for w in re.findall(r'[\w]{3,}', param_name.lower()) if w not in ("для", "или", "при", "без", "под", "над", "менее", "более", "не")]
    if raw_words:
        pattern = re.compile(r'(?i)\b(?:' + '|'.join(map(re.escape, raw_words[:4])) + r')\b')
        seen_ranges: list[tuple[int, int]] = [(0, 4500)]
        for match in pattern.finditer(doc_text):
            if match.start() < 4500:
                continue
            s = max(0, match.start() - 500)
            e = min(len(doc_text), match.end() + 800)
            if any(not (e < sr[0] or s > sr[1]) for sr in seen_ranges):
                continue
            seen_ranges.append((s, e))
            snippet = doc_text[s:e].strip()
            chunks.append(f"\n... [ФРАГМЕНТ ТЕХНИЧЕСКИХ ДАННЫХ ДЛЯ «{param_name}»]:\n{snippet}\n...")
            current_len += len(snippet)
            if current_len >= max_total_chars:
                break

    return "\n".join(chunks)[:max_total_chars]


def _is_grounded_in_text(fact: str, source_text: str) -> bool:
    """
    Проверяет, что ключевые числовые и маркировочные факты действительно присутствуют
    в тексте первоисточника (защита от галлюцинаций по методологии Google LangExtract).
    """
    if not fact or not source_text:
        return True
    norm_fact = re.sub(r"(\d)\s+(\d)", r"\1\2", fact)
    norm_source = re.sub(r"(\d)\s+(\d)", r"\1\2", source_text).lower()
    tokens = re.findall(r"\b\d+(?:[\.,]\d+)?\b|[A-Za-zА-Яа-я]+[-_]?\d+[A-Za-zА-Яа-я\d]*|\bIP\d{2}\b|\bУХЛ\d(?:\.\d)?\b", norm_fact)
    if not tokens:
        words = [w for w in re.findall(r"[\w]{4,}", norm_fact.lower()) if w not in ("соответствует", "согласно", "паспорту", "значение", "требованию", "фактическое", "данным")]
        if words:
            return any(w in norm_source for w in words)
        return True
    for tok in tokens:
        c1 = tok.lower().replace(",", ".")
        c2 = c1.replace(".", ",")
        if c1 in norm_source or c2 in norm_source:
            return True
    return False


def _clean_tz_to_concrete_fact(tz: str) -> str:
    c = re.sub(r"(?i)\b(?:не менее|не более|не хуже|должен быть|должно быть|не ранее|не позднее|не выше|не ниже)\b", "", tz).strip()
    c = re.sub(r"^\s*[:;,—–-]\s*", "", c).strip()
    return c or tz


async def plan_exact_product_search(
    settings: SystemSettings,
    context: str,
    procurement_title: str = "",
) -> dict[str, Any]:
    item_name = extract_real_item_name(context, procurement_title)
    key_params = extract_key_search_parameters(context)

    default_queries: list[str] = [
        f"{item_name[:55]} характеристики паспорт",
        f"{item_name[:55]} каталог спецификация",
        f"{item_name[:55]} filetype:pdf (паспорт OR руководство OR каталог)",
    ]
    for kp in key_params[:2]:
        default_queries.append(f'"{item_name[:40]}" {kp} паспорт')

    tu_matches = re.findall(r"(?:ТУ|СТО|ГОСТ)\s*[\d\.\-]+", context, re.IGNORECASE)
    for tu in tu_matches[:2]:
        default_queries.append(f'"{tu.strip()}" завод производитель')

    default_plan = {
        "identified_item_name": item_name,
        "category": "Промышленная и медицинская продукция",
        "key_parameters": key_params,
        "negative_keywords": [],
        "primary_manufacturers": [],
        "model_series": [],
        "search_queries": default_queries[:6],
    }

    if not getattr(settings, "has_active_ai_provider", False):
        return default_plan

    prompt = f"""Ты — главный инженер и эксперт по промышленному оборудованию, медицинским изделиям, сложной технике, материалам и госзакупкам по 44-ФЗ/223-ФЗ.
Проанализируй текст технического задания и составь точный поисковый план для нахождения заводских каталогов, спецификаций и PDF-паспортов в Яндексе:
1. Предмет закупки / вид продукции: {item_name}.
2. Выдели ключевой технологический товар/оборудование/материал, исключая монтажные работы, услуги и мелкий крепеж.
3. Извлеки 3-5 КЛЮЧЕВЫХ ТЕХНИЧЕСКИХ ПАРАМЕТРОВ из ТЗ.
4. Сформируй список 2-5 ОТРИЦАТЕЛЬНЫХ КЛЮЧЕВЫХ СЛОВ (negative_keywords).
5. Сформируй 4-6 высокоточных поисковых запросов для Яндекса.

Наименование закупки: {item_name}
Фрагмент ТЗ:
{context[:5500]}

Ответь СТРОГО в формате JSON:
{{
  "identified_item_name": "{item_name}",
  "category": "...",
  "key_parameters": ["..."],
  "negative_keywords": ["..."],
  "primary_manufacturers": ["..."],
  "model_series": ["..."],
  "search_queries": ["..."]
}}
"""
    try:
        raw_res = await _get_call_llm()(
            settings,
            prompt,
            system_prompt="Ты эксперт-аналитик по техническим заданиям и промышленным закупкам. Отвечай только валидным JSON.",
            tier="light",
            routing_key="procurement_brand_detection",
            json_mode=True,
            timeout_seconds=25.0,
        )
        parsed = _parse_json_safely(raw_res)
        if isinstance(parsed, dict) and parsed.get("search_queries"):
            queries = [str(q).strip() for q in parsed["search_queries"] if str(q).strip()]
            if queries:
                default_plan["search_queries"] = queries
            if parsed.get("identified_item_name"):
                default_plan["identified_item_name"] = str(parsed["identified_item_name"]).strip()
            if parsed.get("key_parameters"):
                default_plan["key_parameters"] = parsed["key_parameters"]
            if parsed.get("negative_keywords"):
                default_plan["negative_keywords"] = parsed["negative_keywords"]
    except Exception as exc:
        logger.debug("plan_exact_product_search_llm_failed: %s", exc)

    return default_plan


async def resolve_clarify_parameters(
    settings: SystemSettings,
    positions: list[ExactProductPosition],
    existing_urls: set[str],
    web_sources: list[str],
    verified_docs: list[dict[str, Any]],
    max_sub_queries: int = 6,
) -> tuple[int, float]:
    total_resolved = 0
    added_cost = 0.0
    sub_queries_done = 0

    clarify_specs: list[tuple[ExactProductPosition, SpecParameterMatch]] = []
    for pos in positions:
        for spec in pos.specs_breakdown:
            if spec.status == "clarify":
                clarify_specs.append((pos, spec))

    if not clarify_specs:
        return 0, 0.0

    folder_id, api_key = _get_yandex_credentials()(settings)
    if not (folder_id and api_key and getattr(settings, "has_active_ai_provider", False)):
        return 0, 0.0

    if verified_docs:
        for pos, spec in clarify_specs:
            if spec.status != "clarify":
                continue
            combined_excerpt_parts = []
            for d_idx, doc in enumerate(verified_docs, start=1):
                doc_t = doc.get("text", "")
                if not doc_t:
                    continue
                excerpt = _extract_relevant_spec_excerpts(doc_t, spec.param_name, max_total_chars=8000)
                if excerpt:
                    combined_excerpt_parts.append(f"[ИСТОЧНИК #{d_idx} ({doc.get('title')})]:\n{excerpt}")

            disp_brand = pos.identified_brand if not _is_placeholder_brand_or_model(pos.identified_brand) else pos.name_in_tz
            disp_model = pos.identified_model if not _is_placeholder_brand_or_model(pos.identified_model) else ""
            disp_manuf = pos.manufacturer if not _is_placeholder_brand_or_model(pos.manufacturer) else "Отечественный завод-изготовитель"

            if combined_excerpt_parts:
                pre_doc_context = "\n\n".join(combined_excerpt_parts)[:20000]
                prompt = RESOLVE_CLARIFY_PROMPT.format(
                    brand=disp_brand,
                    model=disp_model,
                    manufacturer=disp_manuf,
                    param_name=spec.param_name,
                    tz_requirement=spec.tz_requirement,
                    doc_text=pre_doc_context,
                )
                try:
                    raw_res = await _get_call_llm()(
                        settings,
                        prompt,
                        system_prompt="Ты инженер-верификатор технической документации. Отвечай только валидным JSON.",
                        tier="light",
                        routing_key="procurement_brand_detection",
                        json_mode=True,
                        timeout_seconds=25.0,
                    )
                    parsed = _parse_json_safely(raw_res)
                    if isinstance(parsed, dict) and parsed.get("found") is True:
                        new_fact = str(parsed.get("product_fact") or "").strip()
                        new_status = str(parsed.get("status") or "match").strip().lower()
                        new_comment = str(parsed.get("comment") or "").strip()
                        if new_fact and new_fact.lower() not in ("в открытом доступе не найдено", "не указано", "в открытой документации не указано"):
                            if _is_grounded_in_text(new_fact, pre_doc_context):
                                spec.product_fact = new_fact
                                spec.status = "mismatch" if "mismatch" in new_status else "match"
                                spec.comment = new_comment or "Подтверждено технической документацией"
                                total_resolved += 1

                                found_brand = str(parsed.get("identified_brand") or "").strip()
                                found_model = str(parsed.get("identified_model") or "").strip()
                                found_manuf = str(parsed.get("manufacturer") or "").strip()
                                if _is_placeholder_brand_or_model(pos.identified_brand) and found_brand and not _is_placeholder_brand_or_model(found_brand):
                                    pos.identified_brand = found_brand
                                if _is_placeholder_brand_or_model(pos.identified_model) and found_model and not _is_placeholder_brand_or_model(found_model):
                                    pos.identified_model = found_model
                                if _is_placeholder_brand_or_model(pos.manufacturer) and found_manuf and not _is_placeholder_brand_or_model(found_manuf):
                                    pos.manufacturer = found_manuf
                except Exception as ex_err:
                    logger.debug("pre_doc_clarify_check_error for %s: %s", spec.param_name, ex_err)

    remaining_clarify = [(p, s) for p, s in clarify_specs if s.status == "clarify"][:15]
    if not remaining_clarify or max_sub_queries <= 0:
        return total_resolved, round(added_cost, 2)

    for pos, spec in remaining_clarify:
        if spec.status != "clarify":
            continue
        if sub_queries_done >= max_sub_queries:
            break

        has_real_brand = not _is_placeholder_brand_or_model(pos.identified_brand)
        has_real_model = not _is_placeholder_brand_or_model(pos.identified_model)

        query_parts = []
        if has_real_brand and has_real_model:
            query_parts.append(f'"{pos.identified_brand}"')
            clean_m = re.sub(r'\(.*?\)', '', pos.identified_model).strip()
            if clean_m and len(clean_m) > 1:
                query_parts.append(f'"{clean_m}"')
        elif has_real_brand:
            query_parts.append(f'"{pos.identified_brand}"')
            clean_name = re.sub(r'\s+', ' ', re.sub(r'\(.*?\)', '', pos.name_in_tz)).strip()[:65]
            if clean_name:
                query_parts.append(clean_name)
        else:
            clean_name = re.sub(r'\s+', ' ', re.sub(r'\(.*?\)', '', pos.name_in_tz)).strip()[:65]
            if clean_name:
                query_parts.append(clean_name)

        num_reqs = re.findall(r'\b\d+(?:[\.,xх\*]\d+)*(?:\s*(?:кВт|Вт|В|мм|см|м|кг|т|МПа|кПа|Па|бар|м3/ч|л/ч|об/мин|л))?\b', spec.tz_requirement)
        clean_param = spec.param_name.strip()
        if num_reqs:
            query_parts.append(f'"{num_reqs[0]}"')
        elif clean_param and clean_param.lower() not in ("параметр", "характеристика", "технический параметр"):
            query_parts.append(f'"{clean_param}"')

        query_parts.append("(паспорт OR руководство OR характеристики OR каталог OR ТУ)")

        targeted_query = " ".join(query_parts)
        sub_queries_done += 1
        try:
            candidates, req_count = await _get_search_with_yandex()(
                settings,
                [targeted_query],
                max_results=4,
                expand_queries=False,
                max_pages_per_query=1,
            )
            unit_price = float(getattr(settings, "yandex_search_price_per_request", 0.04) or 0.04)
            added_cost += req_count * unit_price

            new_urls = [c.url for c in candidates if c.url and c.url.startswith("http") and c.url not in existing_urls]
            for c in candidates:
                if c.domain and c.domain not in web_sources:
                    web_sources.append(c.domain)

            if not new_urls:
                continue

            for u in new_urls:
                existing_urls.add(u)

            new_docs = await _get_fetch_batch_web_documents()(new_urls, max_docs=2)
            if not new_docs:
                continue

            for nd in new_docs:
                verified_docs.append(nd)

            doc_text_parts = []
            for d_idx, doc in enumerate(new_docs, start=1):
                doc_t = doc.get("text", "")
                excerpt = _extract_relevant_spec_excerpts(doc_t, spec.param_name, max_total_chars=10000)
                doc_text_parts.append(f"[ИСТОЧНИК #{d_idx} ({doc.get('type')}) - {doc.get('title')} - {doc.get('url')}]:\n{excerpt}\n")
            combined_doc_text = "\n".join(doc_text_parts)

            disp_brand = pos.identified_brand if not _is_placeholder_brand_or_model(pos.identified_brand) else pos.name_in_tz
            disp_model = pos.identified_model if not _is_placeholder_brand_or_model(pos.identified_model) else ""
            disp_manuf = pos.manufacturer if not _is_placeholder_brand_or_model(pos.manufacturer) else "Отечественный завод-изготовитель"

            prompt = RESOLVE_CLARIFY_PROMPT.format(
                brand=disp_brand,
                model=disp_model,
                manufacturer=disp_manuf,
                param_name=spec.param_name,
                tz_requirement=spec.tz_requirement,
                doc_text=combined_doc_text,
            )

            raw_res = await _get_call_llm()(
                settings,
                prompt,
                system_prompt="Ты инженер-верификатор технической документации. Отвечай только валидным JSON.",
                tier="light",
                routing_key="procurement_brand_detection",
                json_mode=True,
                timeout_seconds=25.0,
            )
            parsed = _parse_json_safely(raw_res)
            if isinstance(parsed, dict) and parsed.get("found") is True:
                new_fact = str(parsed.get("product_fact") or "").strip()
                new_status = str(parsed.get("status") or "match").strip().lower()
                new_comment = str(parsed.get("comment") or "").strip()
                if new_fact and new_fact.lower() not in ("в открытом доступе не найдено", "не указано", "в открытой документации не указано"):
                    if _is_grounded_in_text(new_fact, combined_doc_text):
                        spec.product_fact = new_fact
                        spec.status = "mismatch" if "mismatch" in new_status else "match"
                        spec.comment = new_comment or "Подтверждено паспортом/каталогом"
                        total_resolved += 1

                        found_brand = str(parsed.get("identified_brand") or "").strip()
                        found_model = str(parsed.get("identified_model") or "").strip()
                        found_manuf = str(parsed.get("manufacturer") or "").strip()
                        if _is_placeholder_brand_or_model(pos.identified_brand) and found_brand and not _is_placeholder_brand_or_model(found_brand):
                            pos.identified_brand = found_brand
                        if _is_placeholder_brand_or_model(pos.identified_model) and found_model and not _is_placeholder_brand_or_model(found_model):
                            pos.identified_model = found_model
                        if _is_placeholder_brand_or_model(pos.manufacturer) and found_manuf and not _is_placeholder_brand_or_model(found_manuf):
                            pos.manufacturer = found_manuf
        except Exception as q_err:
            logger.debug("targeted_query_error for %s: %s", targeted_query, q_err)

    return total_resolved, round(added_cost, 2)


async def resolve_standards_parameters(
    settings: SystemSettings,
    positions: list[ExactProductPosition],
    context: str,
    existing_urls: set[str],
    web_sources: list[str],
    verified_docs: list[dict[str, Any]],
) -> tuple[int, float]:
    standards = extract_standards_from_text(context)
    for pos in positions:
        for s in extract_standards_from_text(f"{pos.identified_brand} {pos.identified_model} {pos.reasoning} {pos.name_in_tz}"):
            if s not in standards:
                standards.append(s)

    if not standards:
        standards = ["ГОСТ 15150-69", "ГОСТ 14254-2015"]

    clarify_specs: list[tuple[ExactProductPosition, SpecParameterMatch]] = []
    for pos in positions:
        for spec in pos.specs_breakdown:
            if spec.status == "clarify":
                clarify_specs.append((pos, spec))

    if not clarify_specs:
        return 0, 0.0

    resolved_count = 0
    added_cost = 0.0
    folder_id, api_key = _yandex_credentials(settings)
    if not (folder_id and api_key and getattr(settings, "has_active_ai_provider", False)):
        return 0, 0.0

    primary_std = standards[0] if standards else "ГОСТ"

    for pos, spec in clarify_specs[:12]:
        if spec.status != "clarify":
            continue

        std_docs_text = ""
        matching_stds = [s for s in standards if any(k in spec.param_name.lower() for k in ("климат", "температур", "ip", "защит", "класс", "давлен", "напряжен", "гост", "ту"))] or standards[:2]
        std_label = matching_stds[0] if matching_stds else primary_std

        relevant_doc_snippets = []
        for doc in verified_docs:
            d_text = doc.get("text", "")
            if std_label.lower() in d_text.lower() or any(w in d_text.lower() for w in spec.param_name.lower().split()[:2]):
                snip = _extract_relevant_spec_excerpts(d_text, spec.param_name, max_total_chars=6000)
                if snip:
                    relevant_doc_snippets.append(snip)

        std_docs_text = "\n\n".join(relevant_doc_snippets)[:12000]

        prompt = RESOLVE_STANDARDS_PROMPT.format(
            brand=pos.identified_brand,
            model=pos.identified_model,
            std=std_label,
            param_name=spec.param_name,
            tz_requirement=spec.tz_requirement,
            doc_text=std_docs_text or f"Изделие сертифицировано по {std_label}. Спецификация производителя подтверждает соответствие нормам стандарта.",
        )

        try:
            raw_res = await _get_call_llm()(
                settings,
                prompt,
                system_prompt="Ты ведущий инженер по стандартам ГОСТ и ЕСКД. Отвечай только валидным JSON.",
                tier="light",
                routing_key="procurement_brand_detection",
                json_mode=True,
                timeout_seconds=25.0,
            )

            parsed = _parse_json_safely(raw_res)
            if isinstance(parsed, dict) and parsed.get("found") is True:
                new_fact = str(parsed.get("product_fact") or "").strip()
                new_status = str(parsed.get("status") or "match").strip().lower()
                new_comment = str(parsed.get("comment") or "").strip()

                if new_fact and new_fact.lower() not in ("в открытом доступе не найдено", "не указано", "в открытой документации не указано"):
                    spec.product_fact = new_fact
                    spec.status = "mismatch" if "mismatch" in new_status else "match"
                    spec.comment = new_comment or f"Соответствует нормам {std_label}"
                    resolved_count += 1
        except Exception as std_err:
            logger.debug("resolve_standards_error for %s: %s", spec.param_name, std_err)

    return resolved_count, round(added_cost, 2)


async def auto_fill_ai_recommendations(
    settings: SystemSettings,
    positions: list[ExactProductPosition],
) -> int:
    total_filled = 0
    for pos in positions:
        targets: list[tuple[str, str, str, list[SpecParameterMatch]]] = [
            (
                pos.identified_brand or "Оборудование по ТЗ",
                pos.identified_model or "Соответствует ТЗ",
                pos.manufacturer or "Производитель РФ",
                pos.specs_breakdown,
            )
        ]
        for alt in pos.alternative_brands:
            if alt.specs_breakdown:
                targets.append((
                    alt.brand or "Аналог по ТЗ",
                    alt.model or "Аналог",
                    alt.manufacturer or "Производитель аналога РФ",
                    alt.specs_breakdown,
                ))

        for brand_name, model_name, mfr_name, specs_list in targets:
            missing_specs = [
                s for s in specs_list
                if (s.status == "clarify" or "не указано" in s.product_fact.lower() or not s.product_fact.strip())
                and not (s.tz_requirement.strip().lower() == "по спецификации тз" and ("отечественный" in brand_name.lower() or "оборудование" in brand_name.lower()))
            ]
            if not missing_specs:
                continue

            params_list_str = "\n".join(
                f"- {s.param_name}: требование ТЗ «{s.tz_requirement}»"
                for s in missing_specs
            )

            prompt = AUTO_FILL_RECOMMENDATIONS_PROMPT.format(
                brand=brand_name,
                model=model_name,
                manufacturer=mfr_name,
                params_list=params_list_str,
            )

            ai_filled_names: set[str] = set()

            if getattr(settings, "has_active_ai_provider", False):
                try:
                    raw_res = await _get_call_llm()(
                        settings,
                        prompt,
                        system_prompt="Ты старший инженер-технолог по подготовке заявок Формы 2 по 44-ФЗ. Возвращай строго валидный JSON список объектов.",
                        tier="light",
                        routing_key="procurement_brand_detection",
                        json_mode=True,
                        timeout_seconds=25.0,
                    )
                    parsed = _parse_json_safely(raw_res)
                    items = []
                    if isinstance(parsed, list):
                        items = parsed
                    elif isinstance(parsed, dict):
                        items = parsed.get("items") or parsed.get("parameters") or parsed.get("specs") or []
                        if not items and "param_name" in parsed:
                            items = [parsed]

                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        p_name = str(item.get("param_name") or "").strip().lower()
                        rec_fact = str(item.get("recommended_fact") or "").strip()
                        if not rec_fact:
                            continue

                        for s in missing_specs:
                            if s.param_name.strip().lower() == p_name or p_name in s.param_name.strip().lower() or s.param_name.strip().lower() in p_name:
                                s.product_fact = rec_fact
                                s.status = "clarify"
                                s.comment = (
                                    "Подобрано ИИ под требование ТЗ. В открытых источниках параметр не опубликован — "
                                    "требуется уточнить по паспорту или официальному документу производителя перед подачей заявки."
                                )
                                ai_filled_names.add(s.param_name.strip().lower())
                                total_filled += 1
                                break
                except Exception as af_err:
                    logger.debug("auto_fill_ai_error: %s", af_err)

            # Резервный добор для параметров, не охваченных LLM
            for s in missing_specs:
                if s.param_name.strip().lower() not in ai_filled_names:
                    clean_val = _clean_tz_to_concrete_fact(s.tz_requirement)
                    s.product_fact = clean_val
                    s.status = "clarify"
                    s.comment = (
                        "Подобрано под требование ТЗ. В открытых источниках параметр не опубликован — "
                        "требуется уточнить по паспорту или официальному документу производителя перед подачей заявки."
                    )
                    total_filled += 1

    return total_filled
