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


def build_commercial_search_queries(clean_name: str, unit: str, city: str = "") -> list[str]:
    """
    Генерирует поисковые запросы для широкой выдачи с ценами (розница, опт, каталоги, интернет-магазины).
    Правило 14: чисто алгоритмический общий генератор без списков категорий и ключевых слов.
    Поддерживает опциональную привязку к городу/региону доставки.
    """
    queries: list[str] = []
    norm_u = normalize_unit(unit)
    clean_city = str(city or "").strip()

    # 0. Приоритетные региональные запросы при наличии города поставки
    if clean_city:
        if norm_u and norm_u not in {"шт"}:
            queries.append(f"{clean_name} {clean_city} цена за {norm_u} купить в наличии")
        else:
            queries.append(f"{clean_name} {clean_city} купить цена в наличии")
        queries.append(f"{clean_name} {clean_city} поставщики оптовый прайс лист со склада")

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
    Корректно поддерживает несколько файлов за раз, объединяет и дедуплицирует позиции.
    """
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


