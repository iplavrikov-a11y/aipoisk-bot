from __future__ import annotations

import re


def clean_nomenclature_name(raw_name: str) -> str:
    """Очищает строку номенклатуры от мусора 1С, ремарок 'НЕ ИСП', скобок с единицами и лишних пробелов."""
    if not raw_name:
        return ""
    text = str(raw_name).strip()

    # Убираем служебные пометки 1C: /НЕ ИСП, /НЕ_ИСП, /не исп, НЕ ИСП
    text = re.sub(r'[/\\_]?(НЕ\s*ИСП|не\s*исп|НЕ_ИСП|не_исп)\b', '', text, flags=re.IGNORECASE)

    # Убираем явные дублирования единиц в скобках в конце строки, например "(кг)", "(м3)", "(т)"
    text = re.sub(r'\s*\((кг|м3|м2|шт|т|уп|компл|л)\)\s*$', '', text, flags=re.IGNORECASE)

    # Убираем лишние слэши на концах
    text = text.strip(" /\\-")

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
    """Извлекает подсказки фасовки/объема из наименования ТМЦ (баллоны, упаковки по N шт, пачки по N кг)."""
    hints: dict = {
        "cylinder_volume_l": None,
        "pack_pieces": None,
        "pack_weight_kg": None,
        "gas_type": None,
    }
    text_lower = raw_name.lower()

    # Проверка газов и баллонов
    if "пропан" in text_lower:
        hints["gas_type"] = "propane"
    elif "кислород" in text_lower:
        hints["gas_type"] = "oxygen"
    elif "ацетилен" in text_lower:
        hints["gas_type"] = "acetylene"
    elif "углекислот" in text_lower or "углекислый" in text_lower:
        hints["gas_type"] = "co2"
    elif "аргон" in text_lower:
        hints["gas_type"] = "argon"
    elif "азот" in text_lower:
        hints["gas_type"] = "nitrogen"

    # Объем баллона: "бал.50л", "баллон 50 л", "50л"
    m_cyl = re.search(r'(?:бал[\.\s]*|баллон[\s]*)?(\d{1,3})\s*л\b', text_lower)
    if m_cyl:
        vol = int(m_cyl.group(1))
        if vol in (5, 10, 12, 20, 27, 40, 50):
            hints["cylinder_volume_l"] = vol

    # Штук в упаковке: "100шт", "100 шт", "50шт"
    m_pcs = re.search(r'(\d+)\s*(?:шт|штук)\b', text_lower)
    if m_pcs:
        hints["pack_pieces"] = int(m_pcs.group(1))

    # Вес пачки/упаковки: "5кг", "5.5 кг"
    m_wt = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:кг)\b', text_lower)
    if m_wt:
        hints["pack_weight_kg"] = float(m_wt.group(1).replace(",", "."))

    return hints


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
        # Артикул/код должен содержать цифры или специфические разделители (чертеж/модель/серия)
        has_digit = any(c.isdigit() for c in t_clean)
        has_hyphen_code = ("-" in t_clean or "." in t_clean or "/" in t_clean) and len(t_clean) >= 4
        if (has_digit or has_hyphen_code) and len(t_clean) >= 3:
            tl = t_clean.lower()
            if tl not in seen:
                seen.add(tl)
                codes.append(t_clean)
    return codes


def build_commercial_search_queries(clean_name: str, unit: str) -> list[str]:
    """
    Генерирует поисковые запросы для широкой выдачи с ценами (розница, опт, каталоги, интернет-магазины).
    Правило 14: чисто алгоритмический общий генератор без списков категорий и ключевых слов.
    """
    queries: list[str] = []
    norm_u = normalize_unit(unit)

    # 1. Прямой коммерческий запрос с единицей измерения или без
    if norm_u and norm_u not in {"шт"}:
        queries.append(f"{clean_name} цена за {norm_u} купить в наличии")
    else:
        queries.append(f"{clean_name} купить цена в наличии")

    # 2. Поставщики и прайс-листы со склада
    queries.append(f"{clean_name} прайс лист купить со склада")
    queries.append(f"{clean_name} стоимость каталог поставщики")
    queries.append(f"{clean_name} купить цена от производителя")

    # 3. Универсальное выделение артикулов и маркировок
    tokens = clean_name.split()
    noun = tokens[0] if tokens else ""
    codes = extract_generic_nomenclature_codes(clean_name)
    for art_code in codes[:2]:
        if noun and noun.lower() != art_code.lower():
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


def build_fallback_broad_queries(clean_name: str, unit: str) -> list[str]:
    """
    Алгоритмический универсальный генератор расширенных запросов для волн добора (Правило 14: без жестких списков слов).
    Используется как надежный фоллбэк при недоступности ИИ или в тестах.
    Формирует запросы на основе структуры текста, универсальных артикулов и коммерческих маркеров.
    """
    queries: list[str] = []
    norm_u = normalize_unit(unit)

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
    codes = extract_generic_nomenclature_codes(clean_name)
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


