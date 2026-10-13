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


def build_fallback_broad_queries(clean_name: str, unit: str) -> list[str]:
    """
    Генерирует расширенные адаптивные запросы для 2-й волны поиска,
    когда по жестким первоначальным запросам найдено < 3 подтвержденных цен.
    Снимает жесткие ограничения и добавляет отраслевой контекст (дробилки, сальники, бумага, муфты).
    """
    queries: list[str] = []
    text_lower = clean_name.lower()

    # 1. Диаграммная бумага и ленты (Р-1763, 0-100, 120мм)
    if "диаграммн" in text_lower:
        r_num = re.search(r'(?:р|r)[\s\-]?(\d{3,4})\b', text_lower)
        if r_num:
            queries.append(f"Лента диаграммная Р{r_num.group(1)} купить цена")
            queries.append(f"Диаграммная бумага Р-{r_num.group(1)} прайс лист")
        else:
            queries.append("Лента диаграммная реестровая купить цена")

    # 2. Сальниковые набивки и уплотнения (ВАТИ, АГИ, АФТ, ХБП)
    elif "набивк" in text_lower:
        v_match = re.search(r'(вати[\s\-]?\d+|аги|афт|графитекс|герморум)', text_lower)
        dim_match = re.search(r'(\d+[хx]\d+)', text_lower)
        if v_match:
            base_q = f"Набивка сальниковая {v_match.group(1).upper()}"
            if dim_match:
                queries.append(f"{base_q} {dim_match.group(1)} купить цена")
            queries.append(f"{base_q} цена за кг в наличии")
        else:
            queries.append("Набивка сальниковая купить цена за кг")

    # 3. Дробильно-размольное оборудование (Било, Билодержатель, Броня, Футеровка)
    elif any(w in text_lower for w in ("било", "билодержател", "броня", "футеровк")):
        art_match = re.search(r'([а-яa-z]?[\s\-]?\d+[\.\-\/]\d+[\.\-\/]?\d*)', text_lower)
        art_str = art_match.group(1).replace(" ", "") if art_match else ""
        if "билодержател" in text_lower:
            queries.append(f"Билодержатель {art_str} дробилка купить цена".strip())
            queries.append(f"Билодержатель молотковой дробилки {art_str} производитель".strip())
        elif "било" in text_lower:
            queries.append(f"Било молотковой дробилки {art_str} купить цена".strip())
            queries.append(f"Било {art_str} запасные части мельниц цена".strip())
        elif "броня" in text_lower or "футеровк" in text_lower:
            queries.append(f"Броня радиальная {art_str} бетоносмеситель купить цена".strip())
            queries.append(f"Броня {art_str} литье запчасти цена".strip())

    # 4. Крановые и муфтовые детали (Палец, втулка, полумуфта)
    elif "палец" in text_lower and not any(w in text_lower for w in ("поршн", "двс", "авто")):
        art_match = re.search(r'([а-яa-z]?[\s\-]?\d+[\.\-\/]\d+[\.\-\/]?\d*)', text_lower)
        art_str = art_match.group(1).replace(" ", "") if art_match else ""
        queries.append(f"Палец {art_str} крановый муфта купить цена".strip())
        queries.append(f"Палец муфты МУВП {art_str} цена в наличии".strip())

    # 5. Сложные датчики и контроллеры (Rosemount, GT13E2, Danfoss, Wika)
    elif any(b in text_lower for b in ("rosemount", "gt13e2", "danfoss", "wika", "endress", "siemens")):
        words = clean_name.split()
        brand = words[0]
        model_part = words[1][:10] if len(words) > 1 else ""
        queries.append(f"Датчик {brand} {model_part} купить цена")
        queries.append(f"{brand} {model_part} стоимость в наличии поставщики")

    # 6. Общее упрощение: берем главное существительное + марку/ГОСТ без лишних параметров
    tokens = clean_name.split()
    if len(tokens) > 3:
        # Укороченный запрос из первых 3-4 ключевых слов
        short_name = " ".join(tokens[:4])
        queries.append(f"{short_name} купить цена")
        queries.append(f"{short_name} прайс лист в наличии")

    # Убираем дубли
    seen = set()
    unique_queries = []
    for q in queries:
        q_cln = " ".join(q.split())
        if q_cln and q_cln.lower() not in seen:
            seen.add(q_cln.lower())
            unique_queries.append(q_cln)

    return unique_queries

