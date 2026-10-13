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


def build_commercial_search_queries(clean_name: str, unit: str) -> list[str]:
    """Генерирует поисковые запросы для коммерческой выдачи с ценами."""
    queries: list[str] = []
    u = (unit or "").strip().lower()

    # Базовый коммерческий запрос
    if u and u not in {"шт", "штука", "ед"}:
        queries.append(f"{clean_name} цена за {u} купить")
    else:
        queries.append(f"{clean_name} купить цена руб")

    # Дополнительный запрос с точной фразой или наличием
    queries.append(f"{clean_name} в наличии цена прайс-лист")
    return queries
