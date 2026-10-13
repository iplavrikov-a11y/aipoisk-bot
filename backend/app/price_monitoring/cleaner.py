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


def build_commercial_search_queries(clean_name: str, unit: str) -> list[str]:
    """Генерирует поисковые запросы для широкой выдачи с ценами (розница, опт, каталоги, интернет-магазины)."""
    queries: list[str] = []
    norm_u = normalize_unit(unit)

    # 1. Запрос с единицей измерения
    if norm_u and norm_u not in {"шт"}:
        queries.append(f"{clean_name} цена за {norm_u} купить в наличии")
    else:
        queries.append(f"{clean_name} купить цена в наличии")

    # 2. Интернет-магазины / розница
    queries.append(f"{clean_name} купить в интернет магазине цена")

    # 3. Прайс-лист / каталог
    queries.append(f"{clean_name} стоимость каталог поставщики")

    # 4. В наличии с доставкой
    queries.append(f"{clean_name} прайс лист купить со склада")
    return queries
