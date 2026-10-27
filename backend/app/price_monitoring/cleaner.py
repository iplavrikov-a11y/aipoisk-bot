from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any


def clean_nomenclature_name(raw_name: str) -> str:
    """Очищает строку номенклатуры от мусора 1С, ремарок 'НЕ ИСП', скобок с единицами и лишних пробелов."""
    if not raw_name:
        return ""
    text = str(raw_name).strip()

    # Убираем ведущие служебные символы 1С/ERP (#, №, *, !, ~, =)
    text = re.sub(r'^[#№*!~=\s\-_/]+', '', text)

    # Убираем служебные статусные пометки 1C/ERP: /НЕ ИСП, /СНЯТ, /АРХИВ, /УСТАР, /ДУБЛЬ, /ОШИБКА и их формы
    text = re.sub(r'[/\\_]?(?:НЕ\s*ИСП\w*|СНЯТ\w*|АРХИВ\w*|УСТАР\w*|ДУБЛ\w*|ОШИБК\w*)\b', '', text, flags=re.IGNORECASE)

    # Убираем явные дублирования единиц в скобках в конце строки, например "(кг)", "(м3)", "(т)"
    text = re.sub(r'\s*\((кг|м3|м2|шт|т|уп|компл|л)\)\s*$', '', text, flags=re.IGNORECASE)

    # Убираем лишние слэши, тире и спецсимволы на концах
    text = text.strip(" /\\-_#№*!~=")

    # Разделяем склеенные точки сокращений 1C/ERP: "оцин.D101-110" -> "оцин. D101-110", "давл.EJX" -> "давл. EJX", "вакуум.10" -> "вакуум. 10"
    # Сохраняем десятичные дроби (1.5, 0.05) и децимальные номера чертежей (059.00)
    text = re.sub(r'([а-яА-ЯёЁ]{3,}|[а-яё]{2,})\.([a-zA-Z0-9а-яА-ЯёЁ])', r'\1. \2', text)

    # Нормализуем инженерные технические формулы характеристик в естественные слова (г/п 1т -> 1т, H=3м -> 3м, L=70 -> 70мм)
    text = re.sub(r'\bг[/\\]п\s*(\d+(?:[.,]\d+)?\s*[тt])\b', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[hHвВ]\s*=\s*(\d+(?:[.,]\d+)?\s*(?:[мm]|мм|см))\b', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[lLдД]\s*=\s*(\d+(?:[.,]\d+)?\s*(?:[мm]|мм|см))\b', r'\1', text, flags=re.IGNORECASE)

    # В номенклатуре нижний регистр `д/` перед заглавенной маркировкой —
    # сокращение «для», а не часть кода. Саму маркировку сохраняем.
    text = re.sub(r'(?<![A-Za-zА-Яа-яЁё0-9])д/\s*(?=[A-ZА-ЯЁ]{2,}(?:[-_/]?\d))', '', text)

    # Схлопываем множественные пробелы
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_unit(unit: str) -> str:
    """Приводит единицу измерения к единому нормализованному виду."""
    if not unit:
        return "шт"
    u = unit.strip().lower().replace(".", "").replace(" ", "")
    mapping = {
        "м2": "м2", "квм": "м2", "квметр": "м2",
        "м3": "м3", "кубм": "м3", "куб": "м3",
        "кг": "кг", "килограмм": "кг", "к-г": "кг",
        "т": "т", "тн": "т", "тонна": "т", "тонн": "т",
        "шт": "шт", "штука": "шт", "штук": "шт", "ед": "шт",
        "уп": "уп", "упак": "уп", "упаковка": "уп", "пачка": "уп", "пач": "уп",
        "л": "л", "литр": "л", "литров": "л",
        "м": "м", "погм": "м", "погметр": "м", "метр": "м",
        "компл": "компл", "комплект": "компл", "набор": "компл",
        "рул": "рулон", "рулон": "рулон",
    }
    return mapping.get(u, u)


def extract_package_hints(raw_name: str, target_unit: str) -> dict:
    """Extract only explicit, product-neutral packaging facts from source text."""
    hints: dict = {
        "pack_pieces": None,
        "pack_weight_kg": None,
    }
    text_lower = raw_name.lower()

    # Штук в упаковке: "100шт", "100 шт", "50шт"
    m_pcs = re.search(r'(\d+)\s*(?:шт|штук)\b', text_lower)
    if m_pcs:
        hints["pack_pieces"] = int(m_pcs.group(1))

    # Вес пачки/упаковки: "5кг", "5.5 кг"
    m_wt = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:кг)\b', text_lower)
    if m_wt:
        hints["pack_weight_kg"] = float(m_wt.group(1).replace(",", "."))

    return hints


_MEASUREMENT_UNIT = r'(?:мкм|µm|μm|um|мм|см|км|кг|мг|мл|квт|вт|ма|м?а(?:[/·⋅*]?ч)?|mah|ah|гц|hz|kw|м|т|л|шт|в|v|w)'


def _is_measurement_or_descriptor_token(token: str) -> bool:
    """Keep dimensions and count-based descriptors out of strict SKU searches."""
    compact = re.sub(r'\s+', '', str(token or '').lower())
    number = r'\d+(?:[.,]\d+)?'
    component = rf'{number}{_MEASUREMENT_UNIT}'
    if re.fullmatch(rf'{number}{_MEASUREMENT_UNIT}', compact, re.IGNORECASE):
        return True
    if re.fullmatch(rf'{component}(?:[xх*]{component}){{1,2}}', compact, re.IGNORECASE):
        return True
    # `4-рядн`, `3-полюсный` and similar tokens describe configuration,
    # whereas product identifiers begin with their model/series letters.
    return bool(re.fullmatch(r'\d+(?:[-–][а-яё]+)+', compact, re.IGNORECASE))


def extract_generic_nomenclature_codes(name: str) -> list[str]:
    """
    Универсальное извлечение артикулов, номеров чертежей, ГОСТов и буквенно-цифровых маркировок (Правило 14).
    СТРОГО без жестких списков слов, названий товаров, брендов или типов оборудования.
    """
    if not name:
        return []
    tokens = re.findall(r'\b[A-Za-zА-Яа-я0-9\-_./]{3,}\b', name)
    codes: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        t_clean = t.strip(" -_./")
        if _is_measurement_or_descriptor_token(t_clean):
            continue
        # Артикул/код должен содержать цифры или специфические разделители (чертеж/модель/серия)
        has_digit = any(c.isdigit() for c in t_clean)
        has_hyphen_code = ("-" in t_clean or "." in t_clean or "/" in t_clean) and len(t_clean) >= 4
        if (has_digit or has_hyphen_code) and len(t_clean) >= 3:
            tl = t_clean.lower()
            if tl not in seen:
                seen.add(tl)
                codes.append(t_clean)
    return codes


def is_classifier_code(token: str, full_text: str = "") -> bool:
    """
    Проверяет, является ли токен кодом классификатора (ОКПД, ОКПД2, КТРУ, ТН ВЭД)
    или названием справочника. Коды классификаторов не являются заводскими
    артикулами и не должны попадать в строгие коммерческие запросы.
    """
    clean_tok = token.strip("()[]{}<>\"'*#№!, ;")
    lower_tok = clean_tok.lower()
    if lower_tok in {"окпд", "окпд2", "okpd", "okpd2", "ктру", "ktru", "тнвэд", "тн вэд", "tnved"}:
        return True
    # Шаблоны кодов ОКПД2 / КТРУ: 31.01.12.160, 31.01.12.160-00000005, 26.51.66.120-00000001
    if re.fullmatch(r'\d{2}\.\d{2}\.\d{2}(?:\.\d{3})?(?:-\d{6,10})?', clean_tok):
        return True
    if full_text and re.search(r'\b(?:окпд2?|okpd2?|ктру|ktru|тн\s*вэд|tnved)\b\D{0,10}' + re.escape(clean_tok), full_text, re.I):
        return True
    return False


def is_drawing_or_part_code(token: str, full_text: str = "") -> bool:
    """
    Определяет, является ли токен специализированным номером заводского чертежа или артикулом детали (Правило 14).
    Отличает чертежи от геометрических размеров (3х2.5, 1000х2000) и стандартов (ГОСТ 7798-70, DIN 912).
    """
    token = token.strip("()[]{}<>\"'*#№!, ")
    if len(token) < 4:
        return False
    if is_classifier_code(token, full_text):
        return False
    if _is_measurement_or_descriptor_token(token):
        return False
    # Геометрические габариты (3х2.5, 50х150, 1000х2000) - это характеристики, а не чертежи
    if re.fullmatch(r'\d+(?:[.,]\d+)?\s*[xхXХ*]\s*\d+(?:[.,]\d+)?(?:\s*[xхXХ*]\s*\d+(?:[.,]\d+)?)?', token):
        return False
    # Инженерные геометрические параметры и диапазоны (D101-110, D21-24, L70, H=3м, DN50-100, PN10-16, ДУ100)
    if re.fullmatch(r'(?:[dDдДlLлЛhHвВwWшШ]|dn|pn|ду|ру)\s*=?\s*\d+(?:[.,]\d+)?\s*(?:[мm]|мм|см|г|кг|т|л|мл)?(?:[-–/]\d+(?:[.,]\d+)?)?', token, re.IGNORECASE):
        return False
    # Физические величины с единицами измерения (200г, 3мм, 50м, 1т, 6-5м, 50л)
    if re.fullmatch(r'\d+(?:[.,]\d+)?(?:[-–/]\d+(?:[.,]\d+)?)?\s*(?:г|кг|мг|т|л|мл|м|см|мм|км|шт|в|вт|квт|м?а(?:[/·⋅*]?ч)?|v|w|kw|hz|гц|m?ah)\b', token, re.IGNORECASE):
        return False
    # Общепринятые стандарты (ГОСТ, ОСТ, ТУ, DIN, ISO) - публичные нормативные документы, а не закрытые чертежи
    if full_text and re.search(r'\b(?:гост|ост|ту|din|iso)\s*' + re.escape(token), full_text, re.I):
        return False
    # Десятичные дроби и соотношения двух чисел (40/20, 2.5, 3/4)
    if re.fullmatch(r'\d+(?:[.,/]\d+)+', token) and not re.search(r'\d{1,4}\.\d{2,}\.\d{1,}', token):
        return False
    # Децимальный чертеж с цифрами и точками/дефисами (например 1085.05.02, 059.00.00-02, 2.607.019.435)
    if re.search(r'\d{1,4}\.\d{2,}\.\d{1,}', token) or re.search(r'\d+[.\-_/]\d+[.\-_/]\d+', token):
        return True
    # Чертеж с буквенным префиксом серии (например ЭГ.059.00.00-02, ВР30.02.000-01)
    if re.search(r'[a-zA-Zа-яА-ЯёЁ]+[.\-_/]\d+[.\-_/]', token):
        return True
    # Буквенно-цифровой артикул узла/детали (например SPGA4270-200-01, ИП43хВх10х35х7, D-08660, ЦЧ-4)
    has_letters = bool(re.search(r'[a-zA-Zа-яА-ЯёЁ]', token))
    has_digits = bool(re.search(r'\d', token))
    if has_letters and has_digits and len(token) >= 4:
        return True
    # Числовой артикул детали (5-8 цифр, например 130539, 26038)
    if re.fullmatch(r'\d{5,8}', token):
        return True
    return False


def is_closed_factory_drawing(token: str, full_text: str = "") -> bool:
    """
    Отличает явную ссылку на чертёж и децимальную маркировку от серийного SKU.
    Эта эвристика задаёт точность поиска, но не доказывает отсутствие рыночной цены.
    """
    token = token.strip("()[]{}<>\"'*#№!, ")
    if len(token) < 5:
        return False
    if is_classifier_code(token, full_text):
        return False
    # Общепринятые стандарты (ГОСТ, ОСТ, ТУ, DIN, ISO) - публичные нормативные документы, а не чертежи
    if full_text and re.search(r'\b(?:гост|ост|ту|din|iso)\s*' + re.escape(token), full_text, re.I):
        return False
    # Кириллический префикс и числовые децимальные сегменты: 5ВК.568.007.2,
    # ЭГ.059.00.00-02. Произвольные точки/дефисы встречаются и в серийных моделях.
    if re.fullmatch(r'(?:\d+[А-ЯЁ]{1,4}|[А-ЯЁ]{1,4})\.\d{2,}(?:\.\d+)+(?:-\d+)?', token, re.I):
        return True
    # Прямое указание чертежа в тексте
    if full_text and re.search(r'\b(?:черт|по черт|чертеж|кд|сборочн)\S*\s*' + re.escape(token), full_text, re.I):
        return True
    return False


def build_commercial_search_queries(clean_name: str, unit: str, city: str = "") -> list[str]:
    """
    Генерирует поисковые запросы для широкой выдачи с ценами (розница, опт, каталоги, интернет-магазины).
    Правило 14: чисто алгоритмический общий генератор без списков категорий и ключевых слов.
    Поддерживает опциональную привязку к городу/региону доставки.
    """
    queries: list[str] = []
    norm_u = normalize_unit(unit)
    clean_city = str(city or "").strip()

    tokens = clean_name.split()
    noun = tokens[0] if tokens else ""
    codes = extract_generic_nomenclature_codes(clean_name)
    drawing_codes = [c for c in codes if is_drawing_or_part_code(c, clean_name)]
    closed_drawings = [c for c in codes if is_closed_factory_drawing(c, clean_name)]

    # 0. Строгий поиск для закрытых децимальных чертежей завода (уникальные заказные детали):
    # Требуются строгие кавычки для отсечки омонимов бытовой техники
    if closed_drawings:
        primary_code = closed_drawings[0]
        context_tokens = [
            t for t in tokens
            if t != primary_code and not is_drawing_or_part_code(t, clean_name) and len(t) >= 2
        ]
        context_words = " ".join(context_tokens[:4]) if context_tokens else noun
        if context_words:
            if clean_city:
                queries.append(f'"{primary_code}" {context_words} {clean_city} купить цена')
            queries.append(f'"{primary_code}" {context_words} купить цена')
            queries.append(f'{context_words} "{primary_code}" купить со склада')
            queries.append(f'"{primary_code}" {context_words} производитель каталог')
        queries.append(f'"{primary_code}" цена в наличии со склада')
        queries.append(f'"{primary_code}" прайс лист')
        seen = set()
        unique_queries = []
        for q in queries:
            q_cln = " ".join(q.split())
            if q_cln and q_cln.lower() not in seen:
                seen.add(q_cln.lower())
                unique_queries.append(q_cln)
        return unique_queries

    # Для коммерческих артикулов (например Makita D-08660, Bosch 2.607.019.435, СТП1-2/3000, ЦЧ-4):
    # Формируем естественные поисковые запросы БЕЗ жестких кавычек в приоритете, плюс кавычки как резерв
    if drawing_codes:
        primary_code = drawing_codes[0]
        context_tokens = [
            t for t in tokens
            if t != primary_code and not is_drawing_or_part_code(t, clean_name) and len(t) >= 2
        ]
        context_words = " ".join(context_tokens[:4]) if context_tokens else noun
        if context_words:
            if clean_city:
                queries.append(f"{context_words} {primary_code} {clean_city} купить цена")
            queries.append(f"{context_words} {primary_code} купить цена")
            queries.append(f"{primary_code} {context_words} купить со склада")
            queries.append(f'"{primary_code}" {context_words} купить цена')
        queries.append(f"{clean_name} купить цена")
        queries.append(f"{primary_code} цена в наличии")

    # 1. Приоритетные региональные запросы при наличии города поставки (для стандартных товаров)
    if clean_city:
        if norm_u and norm_u not in {"шт"}:
            queries.append(f"{clean_name} {clean_city} цена за {norm_u} купить в наличии")
        else:
            queries.append(f"{clean_name} {clean_city} купить цена в наличии")
        queries.append(f"{clean_name} {clean_city} поставщики оптовый прайс лист со склада")

    # 2. Прямой коммерческий запрос с единицей измерения или без
    if norm_u and norm_u not in {"шт"}:
        queries.append(f"{clean_name} цена за {norm_u} купить в наличии")
    else:
        queries.append(f"{clean_name} купить цена в наличии")

    # 3. Поставщики и прайс-листы со склада
    queries.append(f"{clean_name} прайс лист купить со склада")
    queries.append(f"{clean_name} стоимость каталог поставщики")
    queries.append(f"{clean_name} купить цена от производителя")

    # 4. Универсальное выделение общих артикулов и маркировок
    for art_code in codes[:2]:
        if noun and noun.lower() != art_code.lower():
            if clean_city:
                queries.append(f"{noun} {art_code} {clean_city} купить цена".strip())
            queries.append(f"{noun} {art_code} купить цена".strip())
        queries.append(f'"{art_code}" цена в наличии')

    # Убираем дубли с сохранением порядка
    seen = set()
    unique_queries = []
    for q in queries:
        q_cln = " ".join(q.split())
        if q_cln and q_cln.lower() not in seen:
            seen.add(q_cln.lower())
            unique_queries.append(q_cln)

    return unique_queries


def build_fallback_broad_queries(clean_name: str, unit: str, city: str = "") -> list[str]:
    """
    Алгоритмический универсальный генератор расширенных запросов для волн добора (Правило 14: без жестких списков слов).
    Используется как надежный фоллбэк при недоступности ИИ или в тестах.
    Формирует запросы на основе структуры текста, универсальных артикулов и коммерческих маркеров.
    """
    queries: list[str] = []
    norm_u = normalize_unit(unit)
    clean_city = str(city or "").strip()

    codes = extract_generic_nomenclature_codes(clean_name)
    drawing_codes = [c for c in codes if is_drawing_or_part_code(c, clean_name)]

    # 0. Строгий режим для чертежей и специализированных артикулов:
    # Запросы ОБЯЗАТЕЛЬНО должны сохранять чертеж в кавычках и не деградировать до общих слов
    if drawing_codes:
        primary_code = drawing_codes[0]
        noun = clean_name.split()[0] if clean_name.split() else ""
        if noun and noun.lower() != primary_code.lower():
            if clean_city:
                queries.append(f'"{primary_code}" {noun} {clean_city} купить цена')
            queries.append(f'"{primary_code}" {noun} купить цена')
            queries.append(f'"{primary_code}" {noun} поставщики склад')
        queries.append(f'"{primary_code}" цена каталог производитель')
        queries.append(f'"{primary_code}" стоимость прайс лист')
        seen = set()
        unique_queries = []
        for q in queries:
            q_cln = " ".join(q.split())
            if q_cln and q_cln.lower() not in seen:
                seen.add(q_cln.lower())
                unique_queries.append(q_cln)
        return unique_queries

    if clean_city:
        queries.append(f"{clean_name} {clean_city} купить со склада оптом")
        queries.append(f"{clean_name} {clean_city} дилеры каталог")

    # 1. Запрос по точному очищенному названию без знаков препинания
    clean_no_punct = re.sub(r'[,;:()"\']+', ' ', clean_name).strip()
    clean_no_punct = " ".join(clean_no_punct.split())
    if clean_no_punct:
        queries.append(f"{clean_no_punct} цена руб")
        queries.append(f"{clean_no_punct} купить у поставщика")
        queries.append(f"{clean_no_punct} прайс лист в наличии")

    # 2. Выделение универсальных артикулов, чертежей и маркировок (Правило 14: без привязки к конкретным товарам)
    tokens = clean_no_punct.split()
    noun = tokens[0] if tokens else ""
    for code in codes[:3]:
        if noun and noun.lower() != code.lower():
            queries.append(f"{noun} {code} купить цена")
            queries.append(f"{noun} {code} прайс лист от производителя")
        queries.append(f'"{code}" купить цена')
        queries.append(f"{code} стоимость в наличии поставщики")

    # 3. Базовый короткий запрос по первым ключевым словам номенклатуры (для объемных названий)
    if len(tokens) >= 2:
        short_name = " ".join(tokens[:3])
        queries.append(f"{short_name} купить цена")
        queries.append(f"{short_name} прайс лист в наличии")
        queries.append(f"{short_name} поставщики склад")

    # 4. Запрос с единицей измерения
    if norm_u and norm_u not in {"шт"}:
        queries.append(f"{clean_name} купить за {norm_u} цена")

    # Убираем дубли с сохранением порядка
    seen = set()
    unique_queries = []
    for q in queries:
        q_cln = " ".join(q.split())
        if q_cln and q_cln.lower() not in seen:
            seen.add(q_cln.lower())
            unique_queries.append(q_cln)

    return unique_queries


logger = logging.getLogger(__name__)


def parse_items_from_text(text: str) -> list[tuple[str, str]]:
    """
    Универсальный парсер позиций номенклатуры из произвольного текста (списки, вставки из таблиц, Word, PDF, markdown).
    Возвращает список кортежей (очищенное_наименование, единица_измерения).
    """
    if not text:
        return []

    multi_units = r'(?:шт\.?|штук[а-я]*|компл\.?|комплект[а-я]*|набор[а-я]*|м3|куб\.?\s*м\.?|м2|кв\.?\s*м\.?|пог\.?\s*м\.?|п\.?\s*м\.?|метр[а-я]*|кг|килограмм[а-я]*|тонн[а-я]*|литр[а-я]*|упак\.?|упаков[а-я]*|пач\.?|пач[а-я]*|рулон[а-я]*|пара|пар[а-я]*|усл\.?\s*ед\.?|ед\.?)'
    single_units = r'(?:[мтл]\.?|шт\.?)'

    items: list[tuple[str, str]] = []
    lines = text.strip().splitlines()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Пропускаем разделители таблиц и явные технические заголовки
        if line.startswith("===") or line.startswith("---") or line.startswith("|---"):
            continue
        if re.match(r"^(?:№|п/п|номер|номенклатура|наименование|товар|позиция|спецификация)\b", line, re.IGNORECASE):
            continue

        # Если строка скопирована из markdown-таблицы: | 1 | Позиция | шт |
        if line.startswith("|") and line.endswith("|"):
            line = line.strip("|").strip()

        # Отрезаем ведущие номера списков: "1.", "1)", "1 -", "#1", "-", "*", "•"
        line = re.sub(r"^(?:#?\d+(?:[\.\)]|\s*[\-\–\—])\s*|[\-\*\•\–\—]\s*)", "", line).strip()
        if not line:
            continue

        # 1. Проверяем разделители колонок: табуляция, пайп, точка с запятой
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t") if p.strip()]
        elif "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
        elif ";" in line:
            parts = [p.strip() for p in line.split(";") if p.strip()]
        else:
            parts = None

        if parts and len(parts) >= 2:
            nom = ""
            unit = "шт"
            # Отфильтровываем чисто числовые ячейки (номера строк, количества)
            text_parts = [p for p in parts if not re.match(r"^\d+(?:[.,]\d+)?$", p)]
            if text_parts:
                unit = "шт"
                nom_parts = []
                for p in text_parts:
                    if re.match(rf"^(?:{multi_units}|{single_units})$", p, re.IGNORECASE):
                        unit = p
                    else:
                        nom_parts.append(p)
                if nom_parts:
                    nom = " ".join(nom_parts)
                    clean_n = clean_nomenclature_name(nom)
                    if clean_n and len(clean_n) >= 2:
                        items.append((clean_n, normalize_unit(unit)))
                        continue

        # 2. Выделение единицы измерения в конце через запятую, дефис или скобки (например "Кислород, м3" или "Подшипник - шт")
        m = re.search(rf"^(.*?)(?:[,\-]\s*|\s*\()\s*({multi_units}|{single_units})\s*\)?$", line, re.IGNORECASE)
        if m:
            nom = m.group(1).strip(" ,-\t")
            unit = m.group(2).strip()
            clean_n = clean_nomenclature_name(nom)
            if clean_n and len(clean_n) >= 2:
                items.append((clean_n, normalize_unit(unit)))
                continue

        # 3. Выделение многобуквенной единицы в конце без запятой (например "Сталь листовая 10мм пог.м")
        m2 = re.search(rf"^(.*?)\s+({multi_units})$", line, re.IGNORECASE)
        if m2:
            nom = m2.group(1).strip(" ,-\t")
            unit = m2.group(2).strip()
            clean_n = clean_nomenclature_name(nom)
            if clean_n and len(clean_n) >= 2:
                items.append((clean_n, normalize_unit(unit)))
                continue

        # 4. Если разделителей единиц нет, но строка похожа на осмысленное наименование товара (2 - 250 символов)
        clean_n = clean_nomenclature_name(line)
        if clean_n and 2 <= len(clean_n) <= 250:
            if not re.search(r"\b(просим|настоящим|договор|оплата|поставка|гарантия)\b", clean_n, re.IGNORECASE):
                items.append((clean_n, "шт"))

    return items


def extract_items_from_files_or_text(
    file_paths: list[Any],
    context: str = "",
    settings: Any = None,
) -> list[tuple[str, str]]:
    """
    Извлекает перечень номенклатурных позиций (номенклатура, единица_измерения) из переданных файлов
    (.xlsx, .xls, .docx, .pdf, .txt, .csv) и/или текстового контекста.
    Структурированные таблицы сохраняют каждую исходную строку; свободные списки
    используют прежний текстовый разбор при отсутствии достоверной структуры.
    """
    from ..product_inventory import extract_structured_product_inventory
    structured = extract_structured_product_inventory(file_paths, context=context)
    if structured is not None:
        # Distinct physical source rows must not collapse by name alone.
        return [(clean_nomenclature_name(row["name"]), normalize_unit(row.get("unit") or "шт")) for row in structured]

    items: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add_item(nom: str, unit: str) -> None:
        nom_clean = clean_nomenclature_name(nom)
        if not nom_clean or len(nom_clean) < 2:
            return
        key = nom_clean.lower()
        if key not in seen:
            seen.add(key)
            norm_u = normalize_unit(unit)
            items.append((nom_clean, norm_u or "шт"))

    # 1. Сканируем файлы (.xlsx, .xls, .csv, .tsv, .txt, .md)
    for p_obj in file_paths:
        p = Path(p_obj)
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            try:
                fb = p.read_bytes()
                from .pipeline import parse_input_excel
                parsed = parse_input_excel(fb)
                for nom, unit in parsed:
                    _add_item(nom, unit)
            except Exception as exc:
                logger.warning("Failed to parse Excel file %s: %s", p, exc)
        elif suffix in {".csv", ".tsv"}:
            try:
                import csv
                raw = p.read_text(encoding="utf-8", errors="ignore")
                delim = "\t" if suffix == ".tsv" or "\t" in raw else ","
                reader = csv.reader(raw.splitlines(), delimiter=delim)
                for row in reader:
                    if not row:
                        continue
                    if len(row) >= 2:
                        _add_item(row[0], row[1])
                    elif len(row) == 1:
                        _add_item(row[0], "шт")
            except Exception as exc:
                logger.warning("Failed to parse CSV file %s: %s", p, exc)
        elif suffix in {".txt", ".md"}:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                for nom, unit in parse_items_from_text(txt):
                    _add_item(nom, unit)
            except Exception as exc:
                logger.warning("Failed to parse text file %s: %s", p, exc)

    # 2. Если из структурированных файлов позиций не получено, разбираем контекст (текст ТЗ из DOCX/PDF или введенный пользователем)
    if not items and context:
        parsed_text = parse_items_from_text(context)
        for nom, unit in parsed_text:
            _add_item(nom, unit)

    return items


def extract_engineering_spec_tokens(text: str) -> dict[str, set[str]]:
    """
    Извлекает ключевые инженерные размерности и параметры для защиты от пересорта (Правило 14).
    Детерминированный разбор: диаметры (Ду/DN), давления (Ру/PN), напряжения, сечения кабеля, резьбы и мощности.
    """
    specs: dict[str, set[str]] = {}
    if not text:
        return specs
    t = text.lower().replace(",", ".")

    # 1. Номинальный диаметр (Ду / DN)
    m_dn = re.findall(r"\b(?:ду|dn)\s*[-:=]?\s*(\d+)\b", t)
    if m_dn:
        specs["dn"] = set(m_dn)

    # 2. Номинальное давление (Ру / PN)
    m_pn = re.findall(r"\b(?:ру|pn)\s*[-:=]?\s*(\d+)\b", t)
    if m_pn:
        specs["pn"] = set(m_pn)

    # 3. Напряжение питания (12, 24, 36, 48, 110, 220, 380, 660, 1000)
    m_volt = re.findall(r"\b(12|24|36|48|110|220|380|660|1000|10000)\s*(?:в|v|вольт)\b", t)
    if m_volt:
        specs["volt"] = set(m_volt)

    # 4. Кабельное сечение (3х2.5, 4х16, 5х4.0)
    m_cable = re.findall(r"\b(\d+)\s*[xх*]\s*(\d+(?:\.\d+)?)\b", t)
    if m_cable:
        specs["cable"] = {f"{c[0]}x{float(c[1]):g}" for c in m_cable}

    # 5. Метрическая резьба / диаметр крепежа (М16, М20, М8)
    m_thread = re.findall(r"\bм(\d+)(?=[xх*]|\b)", t)
    if m_thread:
        specs["thread"] = set(m_thread)

    # 6. Мощность электродвигателя (15 кВт, 2.2 кВт)
    m_power = re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:квт|kw)\b", t)
    if m_power:
        specs["power"] = {f"{float(p):g}" for p in m_power}

    return specs


def check_engineering_spec_conflict(target_name: str, candidate_text: str) -> tuple[bool, str]:
    """
    Детерминированная проверка размерностей и характеристик оборудования (Compare-then-Match, Правило 14).
    Предотвращает ошибочное подтверждение товаров с несовпадающим диаметром, давлением, напряжением или сечением.
    """
    t_specs = extract_engineering_spec_tokens(target_name)
    if not t_specs:
        return False, ""
    c_specs = extract_engineering_spec_tokens(candidate_text)
    for key, t_vals in t_specs.items():
        if key in c_specs:
            c_vals = c_specs[key]
            if not (t_vals & c_vals):
                return True, f"Несоответствие параметра {key.upper()}: требуется {t_vals}, найдено {c_vals}"
    return False, ""



