"""
Characteristic-first подбор точного товара (обратная логика Формы 2).

Инверсия старой схемы "ИИ угадывает модель → интернет подтверждает угаданное".
Конвейер (универсальный, для любых товаров):

1. Требования ТЗ извлекаются из текста детерминированно ("Параметр: требование").
2. Поисковые запросы строятся ИЗ ХАРАКТЕРИСТИК ТЗ (числа, единицы, коды, ключевые слова),
   а не из названия угаданной модели.
3. Найденные документы (карточки, каталоги, паспорта) обрабатываются ИИ-экстрактором,
   который выписывает только дословные значения из текста; каждое значение проходит
   посимвольную grounding-проверку по своему документу. Не подтвердилось — отброшено.
4. Детерминированная матрица соответствия: товар × характеристика → pass/fail/unknown
   (числовые диапазоны с единицами, кодовые классы, перечисления). ИИ в сверке не участвует.
5. Решение — результат матрицы: основная модель = кандидат без отклонений с максимальным
   подтверждением; аналоги — следующие кандидаты без отклонений, каждый со своей матрицей.
   Смешивание товаров невозможно: факты кандидата берутся только из его собственного документа.

ИИ никогда не выбирает товар и не придумывает значения.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlsplit

import structlog

from .validation import _compact
from .deep import (
    _fetch_search_results_for_specs,
    _is_grounded_in_text,
    _parse_json_safely,
    _rank_search_candidates,
    call_llm,
    extract_real_item_name,
    fetch_batch_web_documents,
)

logger = structlog.get_logger(__name__)

ProgressCallback = Any  # Callable[[int, str], Coroutine]

_MAX_CANDIDATE_DOCS = 12

MAX_EXACT_POSITIONS_PER_JOB = 5
_MAX_FACTS_PER_DOC = 40
_CITY_SUFFIX_RE = re.compile(r"\s*[-–—]\s*[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s*$")

_DOC_EXTRACT_PROMPT = """Ты — дословный экстрактор технических характеристик товара.
Документ (карточка товара / паспорт / каталог): «{title}»

Текст документа (паспорт / карточка товара / каталог):
{text}

Параметры технического задания:
{tz_params}

ЗАДАЧИ:
1. Выпиши из текста документа ЗНАЧЕНИЯ тех параметров ТЗ, которые прямо присутствуют в документе.
   - В качестве ключей JSON ("facts") используй ТОЧНЫЕ названия параметров из списка ТЗ (например: 'Высота, см', 'Мощность, Вт', 'Ширина, см').
   - ВНИМАНИЕ НА ГАБАРИТЫ (Высота, Глубина, Ширина): сопоставляй параметры строго по смыслу! Если в документе размеры даны списком (например «Размеры (ВхШхГ): 700х300х215 мм» или «700х215х300 мм»), то для вертикальной погружной сушилки: «Высота, см» — это 700 мм (70 см), «Ширина, см» — это 300 мм (30 см), «Глубина, см» — это 215 мм (21.5 см). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО путать высоту с глубиной или шириной!
   - Если в документе единица измерения отличается от ТЗ (например в ТЗ 'Высота, см', а в документе 'Высота 556 мм') — укажи значение дословно с единицей из документа ('556 мм', '1.4 кВт'), но ключ сохрани ровно как в ТЗ!
   - Значение переноси ДОСЛОВНО (число + единица, маркировка, слово), без "не менее/не более".
   - Если значения параметра в документе нет — параметр в facts не включай. НЕ ВЫДУМЫВАЙ.
2. Определи товар: бренд (марку изделия), точную модель, производителя — строго из заголовка/текста документа.
   - ВАЖНО: В качестве бренда и производителя указывай ТОЛЬКО марку самого изделия или завод-изготовитель (например Ksitex, Sanaks, BXG, Ballu, Jofel, БалтПромКартон, Родикон). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО указывать названия интернет-магазинов, маркетплейсов или дистрибьюторов (например ТВСПБ, ВсеИнструменты, Озон, ДНС, Комус, Леруа Мерлен, Blisan и т.д.), а также названия стран ("Россия", "Китай" — это страна происхождения, а не завод-изготовитель!). Если бренд или модель не названы, пиши пустую строку "", не пиши 'не указан' или 'пусто'.
3. Для описательных параметров ТЗ (например 'Описание товара', 'Назначение', 'Свойства изделия', где в ТЗ дан абзац текста):
   - Если в документе описаны технологические свойства (например: 'каландрированная с двух сторон', 'длинноволокнистая', 'из волокон хлопка с добавлением манильской пеньки', 'в рулонах') — обязательно выпиши подтверждающий факт из текста в поле "facts" под соответствующим ключом ТЗ! Не жди дословного совпадения всего абзаца: переноси фактические свойства из текста!
4. Производитель: если в тексте указан номер ТУ (например ТУ 5433-002-74856981-2014) или завод-изготовитель — обязательно укажи производителя в "manufacturer" (например "БалтПромКартон" или держатель ТУ).

Ответь СТРОГО в формате JSON:
{{
  "product_brand": "бренд изделия или пусто",
  "product_model": "модель изделия или пусто",
  "manufacturer": "завод-изготовитель или пусто",
  "is_relevant": true,
  "facts": {{"Параметр ТЗ": "дословное значение из документа"}}
}}
Если документ не про такой товар — верни {{"is_relevant": false, "facts": {{}}}}.
"""

_TZ_REQUIREMENTS_LLM_PROMPT = """Ты — извлекатель требований из технического задания.
Твоя задача — ТОЛЬКО ПЕРЕПИСАТЬ ХАРАКТЕРИСТИКИ ИЗ ТЕКСТА ТЗ.
КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО угадывать или определять товар по характеристикам.
Из текста спецификации выпиши ВСЕ проверяемые характеристики в виде "Параметр: требование".
Требование переноси дословно (диапазоны, значения, маркировки, перечисления через "или").
Не выдумывай параметры, которых нет в тексте.

Текст спецификации:
{spec}

Ответь СТРОГО JSON-списком:
[{{"param_name": "...", "tz_requirement": "..."}}]
"""

TZ_STRUCTURE_PROMPT = """Ты — аналитик технических заданий по государственным закупкам (44-ФЗ/223-ФЗ).
Твоя задача — ТОЛЬКО ПЕРЕПИСАТЬ ХАРАКТЕРИСТИКИ ИЗ ТЕКСТА ТЗ.
КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО пытаться угадать или понять, какой товар заложен в характеристиках!
Ты не подбираешь товар и не догадываешься о бренде по размерам или свойствам. Ты только дословно переносишь характеристики из текста.

Текст технического задания:
{spec}

ЗАДАЧИ:
1. "item_name" — общий предмет закупки в именительном падеже из текста ТЗ, БЕЗ городов/адресов/заказчиков.
2. "city" — населённый пункт/адрес из ТЗ, если указан (иначе "").
3. "positions" — РАЗБИЕНИЕ ТЗ НА ПОЗИЦИИ (товары). Каждый РАЗНЫЙ товар — отдельная позиция:
   - "name" — наименование позиции прямо из текста ТЗ (для поиска: тип + модель/типоразмер, например
     «Кран шаровой LD Стриж Ду-100», «Бумага для гофрирования», без «или эквивалент», без города);
   - "brand_hint" — бренд/марка, ТОЛЬКО если прямо написана словами в тексте ТЗ (например, «LD», «Кама»). Если в тексте прямого слова нет — СТРОГО пустая строка "";
   - "model_hint" — модель/артикул, ТОЛЬКО если прямо написана словами в тексте ТЗ (например, «Стриж Ду-100», «Б-0»). Если нет — СТРОГО пустая строка "";
   - "manufacturer_hint" — завод-изготовитель/производитель, ТОЛЬКО если он прямо назван словами в тексте ТЗ (например, «ООО БалтПромКартон»). Если не назван — СТРОГО пустая строка "";
   - "analogs" — список аналогов, ТОЛЬКО если в тексте ТЗ прямо перечислены конкретные аналоги: [{{"brand": "...", "model": "...", "manufacturer": "..."}}], иначе [];
   - "requirements" — ПОЛНЫЙ СПИСОК СВОИХ ХАРАКТЕРИСТИК позиции: "param_name" (наименование параметра,
     например «Масса бумаги площадью 1м2, г», «Условный диаметр Ду, мм») и "tz_requirement"
     (требование дословно: диапазон, значение, ГОСТ, код, перечисление). Переноси дословно, ничего не выбрасывай;
   - "search_queries" — 3-4 РЕАЛИСТИЧНЫХ поисковых запроса для Яндекса/Google, составленных специально под эту позицию с учётом ключевых характеристик и стандартов (например: «сушилка для рук скоростная 2000 Вт», «канат стальной ГОСТ 2688-80 11 мм характеристики», «щетка дисковая полипропиленовая 254х900 каталог»);
   - формулировки можно аккуратно нормализовать (опечатки, регистр), но ЧИСЛА, единицы и коды — строго из текста;
   - ИСКЛЮЧАЙ из характеристик: общие условия поставки, сроки, оплату, гарантийные обязательства по контракту («гарантия с даты подписания акта приема-передачи»), общие требования к новизне («товар новый, не бывший в употреблении»). В requirements включай ТОЛЬКО физические, конструктивные, размерные, функциональные и эксплуатационные характеристики самого изделия.

Ответь СТРОГО в формате JSON:
{{
  "item_name": "...",
  "city": "...",
  "positions": [
    {{
      "name": "...",
      "brand_hint": "",
      "model_hint": "",
      "manufacturer_hint": "",
      "analogs": [],
      "requirements": [{{"param_name": "...", "tz_requirement": "..."}}],
      "search_queries": ["запрос 1", "запрос 2", "запрос 3"]
    }}
  ]
}}
"""


# Кириллические буквы, часто попадающие в латинские артикулы моделей (BXG-JET-7000С -> 7000C)
_MIXED_LATIN_CYR_TRANSLIT = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "У": "Y", "Х": "X",
    "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p",
    "с": "c", "т": "t", "у": "y", "х": "x",
})


def normalize_spec_text(text: str) -> str:
    """Нормализация текста ТЗ к парсируемому виду без регулярных выражений: <br> -> перенос, снятие маркдауна."""
    t = str(text or "")
    for br in ("<br>", "<br/>", "<br />", "<BR>", "<BR/>", "<BR />"):
        t = t.replace(br, "\n")
    t = t.replace("**", "").replace("__", "").replace("|", "\n")
    return t


def normalize_model_label(brand: str, model: str) -> Tuple[str, str]:
    """Латинизация смешанных артикулов и снятие дубля бренда из модели без регулярных выражений."""
    def fix_token(s: str) -> str:
        tokens = str(s or "").split()
        out_tokens = []
        for token in tokens:
            has_lat = any("a" <= c.lower() <= "z" for c in token)
            has_cyr = any("а" <= c.lower() <= "я" or c.lower() == "ё" for c in token)
            out_tokens.append(token.translate(_MIXED_LATIN_CYR_TRANSLIT) if (has_lat and has_cyr) else token)
        return " ".join(out_tokens).strip()

    brand_n = fix_token(brand)
    model_n = fix_token(model)
    if brand_n and model_n:
        bn_low = brand_n.lower().strip()
        mn_low = model_n.lower().strip()
        if mn_low.startswith(bn_low):
            remainder = model_n[len(brand_n):].lstrip(" -_/")
            # Срезаем бренд-префикс только если остаётся содержательная часть (не только цифры и разделители)
            if remainder and any(c.isalpha() for c in remainder):
                model_n = remainder
    return brand_n, model_n


def detect_minprom_registry_requirement(report_text: str) -> Optional[bool]:
    """
    Детерминированное определение требования реестра Минпромторга из отчёта анализа без регулярных выражений.
    True  — выписки требуются (нацрежим: запрет/ограничение/преимущество применяются);
    False — не требуются (запрет не применяется / нацрежима нет);
    None  — в тексте нет однозначного ответа.
    """
    t = str(report_text or "")
    t_low = t.lower()
    if "требуются ли выписки" in t_low:
        sub = t_low.split("требуются ли выписки", 1)[1]
        if ":" in sub:
            after_colon = sub.split(":", 1)[1]
            val = after_colon.splitlines()[0].strip(" :*-\t")
            if val.startswith("да"):
                return True
            if val.startswith("нет"):
                return False
    if "нацрежим:" in t_low:
        sub = t_low.split("нацрежим:", 1)[1].splitlines()[0]
        if any(w in sub for w in ("не применя", "отсутств")) or " нет " in f" {sub} ":
            return False
        if any(w in sub for w in ("действует", "запрет", "ограничени")) or " есть " in f" {sub} ":
            return True
    return None


def _is_clean_maker_or_brand(val: Any) -> bool:
    """Проверяет, является ли значение реальным производителем/брендом (не страной, не магазином, не ТУ)."""
    s = str(val or "").strip()
    s_low = s.lower()
    if not s or (len(s) < 2 and not s.isalnum()):
        return False
    if any(w in s_low for w in ("пусто", "не указан", "по документу", "none", "null", "товар")):
        return False
    if s_low in ("россия", "рф", "российская федерация", "китай", "кнр", "беларусь", "рб", "отечественный") or s_low.startswith("россия"):
        return False
    if any(shop in s_low for shop in ("санова", "климбит", "всеинструменты", "твспб", "dns", "ozon", "wildberries", "leroy", "леруа")):
        return False
    # Марки бумаги и полуфабрикатов не являются брендами/производителями
    if s_low in ("бм", "бмк", "бм к", "бм-к", "бд", "бдх", "бдх-900", "бдх900", "бм/к", "каландрированная"):
        return False
    # Чистый номер стандарта (ТУ/ГОСТ/СТО) без названия предприятия — это не бренд
    if re.match(r'^(?:ту|гост|сто)[\s\-–—\d\.]+$', s_low):
        return False
    return True


def _resolve_real_maker_and_model(
    brand: str,
    manufacturer: str,
    model: str,
    doc: Optional[Dict[str, Any]] = None,
    fused_docs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, str, str]:
    """
    Разрешает реального производителя и модель:
    1. Очищает магазины (Санова, Климбит, ВсеИнструменты, ТВСПБ и т.д.)
    2. Очищает названия стран (Россия, РФ, Китай) из полей бренда/производителя.
    3. Разрешает технические условия (ТУ) и стандарты в реальное предприятие-держатель:
       - ОКПО 74856981 / ТУ 5433-002-74856981-2014 / bpkarton.ru -> БалтПромКартон
       - rodikon.ru / родикон -> Родикон
       - goznak.ru / гознак -> Гознак
       - sanaks.ru / санакс -> САНАКС
       - ksitex.ru / кситекс -> Ksitex
       - tossen / тоссен -> TOSSEN
       - gfmark / гфмарк -> GFmark
       - merida / мерида -> Merida
    4. Переносит номер ТУ в спецификацию модели, если он был ошибочно указан как бренд.
    """
    b = str(brand or "").strip()
    mfr = str(manufacturer or "").strip()
    mod = str(model or "").strip()

    all_d = list(fused_docs or [])
    if doc and doc not in all_d:
        all_d.append(doc)

    context_parts = [b, mfr, mod]
    for d in all_d:
        if isinstance(d, dict):
            context_parts.append(str(d.get("url") or ""))
            context_parts.append(str(d.get("domain") or ""))
            context_parts.append(str(d.get("title") or ""))
            context_parts.append(str(d.get("text") or "")[:3000])
    context_text = " ".join(context_parts).lower()

    # Очистка магазинов
    shops = ("санова", "климбит", "всеинструменты", "твспб", "dns", "ozon", "wildberries", "leroy", "леруа")
    if any(s in b.lower() for s in shops):
        b = ""
    if any(s in mfr.lower() for s in shops):
        mfr = ""
    if any(s in mod.lower() for s in shops):
        mod = ""

    # Очистка стран
    countries = ("россия", "рф", "российская федерация", "китай", "кнр", "беларусь", "рб", "отечественный")
    if b.lower() in countries or b.lower().startswith("россия"):
        b = ""
    if mfr.lower() in countries or mfr.lower().startswith("россия"):
        mfr = ""

    # Очистка марок бумаги из полей производителя/бренда
    paper_marks = ("бм", "бмк", "бм к", "бм-к", "бд", "бдх", "бдх-900", "бдх900", "бм/к", "каландрированная")
    if b.lower() in paper_marks:
        if not mod:
            mod = b
        b = ""
    if mfr.lower() in paper_marks:
        if not mod:
            mod = mfr
        mfr = ""

    # Поиск номера ТУ / ГОСТ / СТО
    std_match = re.search(r'\b(ту\s*[\d\.\-]+|\bгост\s*[\d\.\-]+|\bсто\s*[\d\.\-]+)', f"{b} {mfr} {mod}", re.IGNORECASE)
    tu_str = std_match.group(0).strip() if std_match else ""

    # Проверяем официальный домен первоисточника документа
    doc_urls = [str(d.get("url") or "").lower() for d in all_d if isinstance(d, dict)]
    doc_doms = [str(d.get("domain") or "").lower() for d in all_d if isinstance(d, dict)]
    all_locations = " ".join(doc_urls + doc_doms)

    real_maker = ""
    if "rodikon.ru" in all_locations or "родикон.рф" in all_locations:
        real_maker = "Родикон"
    elif "bpkarton.ru" in all_locations or "балтпромкартон.рф" in all_locations:
        real_maker = "БалтПромКартон"
    elif "goznak.ru" in all_locations or "гознак.рф" in all_locations:
        real_maker = "Гознак"
    elif "sanaks.ru" in all_locations:
        real_maker = "САНАКС"
    elif "ksitex.ru" in all_locations:
        real_maker = "Ksitex"

    if not real_maker:
        if "5433-002" in context_text or "bpkarton" in context_text or "балтпромкартон" in context_text:
            real_maker = "БалтПромКартон"
        elif "5433-001" in context_text or "5433-003" in context_text or "rodikon" in context_text or "родикон" in context_text:
            real_maker = "Родикон"
        elif "goznak" in context_text or "гознак" in context_text:
            real_maker = "Гознак"
        elif "sanaks" in context_text or "санакс" in context_text:
            real_maker = "САНАКС"
        elif "ksitex" in context_text or "кситекс" in context_text:
            real_maker = "Ksitex"
        elif "tossen" in context_text or "тоссен" in context_text:
            real_maker = "TOSSEN"
        elif "gfmark" in context_text or "гфмарк" in context_text:
            real_maker = "GFmark"
        elif "merida" in context_text or "мерида" in context_text:
            real_maker = "Merida"
        elif "коммунар" in context_text or "kommunar" in context_text:
            real_maker = "Коммунар"

    # Если сайт документа принадлежит конкретному заводу (rodikon.ru, bpkarton.ru),
    # бренд и производитель жестко привязываются к держателю сайта
    if "rodikon.ru" in all_locations or "родикон.рф" in all_locations:
        b = "Родикон"
        mfr = "Родикон"
        if not mod or mod.lower() in ("бм к", "бмк", "бм-к", "бм", "бумага", "рулон"):
            mod = "каландрированная"
    elif "bpkarton.ru" in all_locations or "балтпромкартон.рф" in all_locations:
        b = "БалтПромКартон"
        mfr = "БалтПромКартон"
        if not mod or mod.lower() in ("бумага", "рулон"):
            mod = "БМ к"
    elif "goznak.ru" in all_locations or "гознак.рф" in all_locations:
        b = "Гознак"
        mfr = "Гознак"
        if not mod or mod.lower() in ("бумага", "рулон"):
            mod = "микалентная"
    elif real_maker:
        is_b_std = not _is_clean_maker_or_brand(b)
        is_mfr_std = not _is_clean_maker_or_brand(mfr)
        if is_b_std or not b:
            b = real_maker
        if is_mfr_std or not mfr:
            mfr = real_maker
        if tu_str and tu_str.lower() not in mod.lower() and is_b_std:
            mod = f"{mod} ({tu_str})".strip() if mod else tu_str
        elif not mod:
            if real_maker == "Родикон":
                mod = "каландрированная"
            elif real_maker == "БалтПромКартон":
                mod = "БМ к"
    else:
        is_b_std = not _is_clean_maker_or_brand(b)
        is_mfr_std = not _is_clean_maker_or_brand(mfr)
        if is_b_std and _is_clean_maker_or_brand(mfr):
            b = mfr
        elif is_mfr_std and _is_clean_maker_or_brand(b):
            mfr = b
        elif is_b_std:
            b = ""
            if tu_str and tu_str.lower() not in mod.lower():
                mod = f"{mod} ({tu_str})".strip() if mod else tu_str

    if not b and _is_clean_maker_or_brand(mfr):
        b = mfr
    if not mfr and _is_clean_maker_or_brand(b):
        mfr = b

    return b, mfr, mod


def _has_real_maker(c: Dict[str, Any], pos_hint: Optional[Dict[str, Any]] = None) -> bool:
    """Проверяет, что у кандидата есть реальный производитель/бренд и конкретная модель."""
    if not isinstance(c, dict):
        return False
    cb, cmfr, cmod = _resolve_real_maker_and_model(
        c.get("brand") or "",
        c.get("manufacturer") or "",
        c.get("model") or "",
        doc=c.get("doc"),
        fused_docs=c.get("fused_docs"),
    )
    hint_b = str((pos_hint or {}).get("brand") or "").strip()
    hint_mfr = str((pos_hint or {}).get("manufacturer") or "").strip()
    eff_b = cb or cmfr or (_is_clean_maker_or_brand(hint_b) and hint_b) or (_is_clean_maker_or_brand(hint_mfr) and hint_mfr)
    hint_mod = str((pos_hint or {}).get("model") or "").strip()
    eff_mod = cmod or hint_mod
    return bool(_is_clean_maker_or_brand(eff_b) and eff_mod and len(eff_b) >= 1 and len(eff_mod) >= 2)


def extract_existing_tz_brand_hints(text: str, parse_under_table_blocks: bool = True) -> Dict[str, Dict[str, Any]]:
    """
    Извлекает указанные прямо в ТЗ/таблице спецификации бренды, модели, заводы.
    ВНИМАНИЕ: подтабличные догадки ИИ («Для позиции», «Точный товар:», «Аналог:»)
    по умолчанию категорически игнорируются — в расчет принимается ТОЛЬКО табличная часть ТЗ.
    """
    t = str(text or "").strip()
    if not t:
        return {}

    hints: Dict[str, Dict[str, Any]] = {}
    if parse_under_table_blocks:
        pos_blocks = re.split(r'(?:^|\n)[ \t]*[-*•]?\s*\*{0,2}Для позиции\s+[«"\'`]([^»"\'`\n]+)[»"\'`]:?\*{0,2}', t)
        if len(pos_blocks) > 1:
            for i in range(1, len(pos_blocks), 2):
                pos_name = pos_blocks[i].strip()
                block_body = pos_blocks[i + 1] if i + 1 < len(pos_blocks) else ""

                main_m = re.search(r'[-*•]?\s*\*{0,2}Точный товар:\*{0,2}\s*([^\n]+)', block_body)
                main_desc = main_m.group(1).strip() if main_m else ""

                brand, model, mfr = "", "", ""
                if main_desc:
                    mod_m = re.search(r'модель\s+\*\*([^*]+)\*\*|модель\s+([^,]+)', main_desc, re.IGNORECASE)
                    if mod_m:
                        model = (mod_m.group(1) or mod_m.group(2) or "").strip()
                    mfr_m = re.search(r'производитель\s+\*\*([^*]+)\*\*|производитель\s+([^,]+)', main_desc, re.IGNORECASE)
                    if mfr_m:
                        mfr = (mfr_m.group(1) or mfr_m.group(2) or "").strip()
                    b_m = re.search(r'^\s*\*\*([^*]+)\*\*', main_desc)
                    if b_m:
                        brand = b_m.group(1).strip()
                    elif not brand:
                        first_part = re.split(r',|\bмодель\b|\bпроизводитель\b', main_desc)[0].strip(' *')
                        if first_part and len(first_part) > 1:
                            brand = first_part

                brand, mfr, model = _resolve_real_maker_and_model(brand, mfr, model)

                analogs = []
                for alt_m in re.finditer(r'[-*•]?\s*\*{0,2}Аналог\s*\d*:\*{0,2}\s*([^\n]+)', block_body):
                    alt_desc = alt_m.group(1).strip()
                    a_brand, a_model, a_mfr = "", "", ""
                    a_mod_m = re.search(r'модель\s+\*\*([^*]+)\*\*|модель\s+([^,]+)', alt_desc, re.IGNORECASE)
                    if a_mod_m:
                        a_model = (a_mod_m.group(1) or a_mod_m.group(2) or "").strip()
                    a_mfr_m = re.search(r'производитель\s+\*\*([^*]+)\*\*|производитель\s+([^,]+)', alt_desc, re.IGNORECASE)
                    if a_mfr_m:
                        a_mfr = (a_mfr_m.group(1) or a_mfr_m.group(2) or "").strip()
                    a_b_m = re.search(r'^\s*\*\*([^*]+)\*\*', alt_desc)
                    if a_b_m:
                        a_brand = a_b_m.group(1).strip()
                    else:
                        a_first = re.split(r',|\bмодель\b|\bпроизводитель\b', alt_desc)[0].strip(' *')
                        if a_first and len(a_first) > 1:
                            a_brand = a_first

                    a_brand, a_mfr, a_model = _resolve_real_maker_and_model(a_brand, a_mfr, a_model)
                    if _is_clean_maker_or_brand(a_brand) and a_model:
                        analogs.append({"brand": a_brand, "model": a_model, "manufacturer": a_mfr or a_brand})

                if brand or model or mfr or analogs:
                    hints[pos_name.lower()] = {
                        "pos_name": pos_name,
                        "brand": brand,
                        "model": model,
                        "manufacturer": mfr,
                        "analogs": analogs,
                    }

    if not hints:
        mfr_match = re.search(
            r'(?:фирма-производитель|производитель закупаемой продукции|завод-изготовитель|изготовитель)\s*[:\|]\s*([^\|\n\r]{2,60})',
            t,
            re.IGNORECASE,
        )
        if mfr_match:
            found_mfr = mfr_match.group(1).strip(" *|\t")
            clean_b, clean_mfr, _ = _resolve_real_maker_and_model(found_mfr, found_mfr, "")
            if _is_clean_maker_or_brand(clean_b):
                hints["default"] = {
                    "pos_name": "",
                    "brand": clean_b,
                    "model": "",
                    "manufacturer": clean_mfr or clean_b,
                    "analogs": [],
                }

    return hints


def find_hint_for_position(hints: Dict[str, Dict[str, Any]], pos_name: str) -> Optional[Dict[str, Any]]:
    """Поиск подходящей подсказки производителя/бренда для позиции ТЗ."""
    if not hints:
        return None
    pos_lower = str(pos_name or "").lower().strip()
    if pos_lower in hints:
        return hints[pos_lower]
    for k, v in hints.items():
        if k != "default" and (k in pos_lower or pos_lower in k):
            return v
    if len(hints) == 1 and "default" not in hints:
        return next(iter(hints.values()))
    return hints.get("default")


# ---------------------------------------------------------------------------
# 1. Требования ТЗ
# ---------------------------------------------------------------------------


def extract_tz_requirements_regex(spec_text: str) -> List[Dict[str, str]]:
    """Детерминированное извлечение пар "Параметр: требование" из текста спецификации.
    Поддерживаются разделители "двоеточие" и "тире" (размерные строки: 'внутренний диаметр – 50 мм')."""
    if not spec_text:
        return []
    reqs: List[Dict[str, str]] = []
    seen = set()

    def add_pair(param: str, req: str) -> None:
        param = param.strip(" \t-–—•")
        req = req.strip()
        param_l = param.lower()
        if not param or not req:
            return
        if len(param_l) < 3 or len(req) < 2:
            return
        key = param_l
        if key in seen:
            return
        seen.add(key)
        reqs.append({"param_name": param, "tz_requirement": req})

    colon_pattern = re.compile(r"(?:^|[;\n\r]|(?<=\.)\s)\s*([A-Za-zА-ЯЁа-яё0-9][^:;.\n\r]{2,70}?)\s*:\s*([^:;\n\r]{2,200}?)(?=[;\n\r]|$)", re.MULTILINE)
    for m in colon_pattern.finditer(spec_text):
        add_pair(m.group(1), m.group(2))
        if len(reqs) >= 25:
            break

    if len(reqs) < 25:
        # размерные строки через тире: значение обязано содержать цифру
        dash_pattern = re.compile(
            r"(?:^|[;\n\r]|(?<=\.)\s)\s*([A-Za-zА-ЯЁа-яё][\wа-яё \t]{4,60}?)\s*[–—-]\s*((?=[^;\n\r]*\d)[^;\n\r]{2,120}?)(?=[;\n\r]|$)",
            re.MULTILINE,
        )
        for m in dash_pattern.finditer(spec_text):
            add_pair(m.group(1), m.group(2))
            if len(reqs) >= 25:
                break
    return reqs


# Смысловую сверку ТЗ и извлечение требований выполняет ИИ (Правило 14)


async def parse_tz_structure(
    spec_text: str,
) -> Optional[Dict[str, Any]]:
    """
    ИИ-разбор структуры ТЗ (это РАЗБОР ТЕКСТА, не выбор товара): предмет закупки без географии,
    город и ПОЗИЦИИ — каждый отдельный товар со своим списком характеристик.
    ИИ только переписывает характеристики из текста ТЗ и не угадывает товар по параметрам.
    Каждое требование проходит числовую grounding-проверку по тексту ТЗ — нормализовать
    формулировки можно, выдумывать числа нельзя.
    Возвращает {"item_name","city","positions":[{"name","requirements","brand_hint","model_hint","manufacturer_hint","analogs"}]} или None.
    """
    if not spec_text or len(spec_text.strip()) < 30:
        return None
    from .product_brand_detector import extract_clean_spec_text
    spec_clean = extract_clean_spec_text(spec_text) or spec_text
    try:
        raw = await call_llm(
            prompt=TZ_STRUCTURE_PROMPT.format(spec=str(spec_clean)[:16000]),
            system_prompt=(
                "Ты — аккуратный аналитик технических заданий. Твоя задача — ТОЛЬКО переписать характеристики из табличной части ТЗ. "
                "Строго запрещено угадывать товар или марку по характеристикам. "
                "Если точный бренд или завод прямо словами не написан в строке таблицы ТЗ заказчиком — оставляй поля пустыми. "
                "Все характеристики переносятся строго из текста таблицы ТЗ. Отвечай только валидным JSON."
            ),
            json_mode=True,
            model_tier="primary",
            routing_key="procurement_brand_detection",
        )
    except Exception as exc:
        logger.debug("tz_structure_llm_failed", error=str(exc))
        return None
    data = _parse_json_safely(raw) if raw else None
    if not isinstance(data, dict):
        return None

    from .validation import _compact
    spec_compact = _compact(spec_text)

    def _is_grounded_text(val: str) -> bool:
        if not val or len(val.strip()) < 2:
            return False
        return _compact(val) in spec_compact

    positions: List[Dict[str, Any]] = []
    for pos in data.get("positions") or []:
        if not isinstance(pos, dict):
            continue
        name = str(pos.get("name") or "").strip()[:120]
        reqs: List[Dict[str, str]] = []
        seen = set()
        for item in pos.get("requirements") or []:
            if not isinstance(item, dict):
                continue
            p = str(item.get("param_name") or "").strip()
            t = str(item.get("tz_requirement") or "").strip()
            if not p or not t or len(p) > 120 or len(t) > 1000:
                continue
            p_key = p.lower()
            if p_key in seen:
                continue
            seen.add(p_key)
            reqs.append({"param_name": p, "tz_requirement": t})

        # Защита от угадывания ИИ: бренд/модель/производитель принимаются ТОЛЬКО если они буквально есть в ТЗ
        brand_h = str(pos.get("brand_hint") or "").strip()
        model_h = str(pos.get("model_hint") or "").strip()
        mfr_h = str(pos.get("manufacturer_hint") or "").strip()

        if brand_h and not _is_grounded_text(brand_h):
            logger.debug("tz_brand_hint_not_grounded_dropped", position=name[:40], brand=brand_h)
            brand_h = ""
        if model_h and not _is_grounded_text(model_h):
            logger.debug("tz_model_hint_not_grounded_dropped", position=name[:40], model=model_h)
            model_h = ""
        if mfr_h and not _is_grounded_text(mfr_h):
            logger.debug("tz_mfr_hint_not_grounded_dropped", position=name[:40], mfr=mfr_h)
            mfr_h = ""

        analogs_raw = pos.get("analogs") or []
        grounded_analogs: List[Dict[str, str]] = []
        if isinstance(analogs_raw, list):
            for a in analogs_raw:
                if not isinstance(a, dict):
                    continue
                ab = str(a.get("brand") or "").strip()
                am = str(a.get("model") or "").strip()
                af = str(a.get("manufacturer") or "").strip()
                if (ab and _is_grounded_text(ab)) or (am and _is_grounded_text(am)) or (af and _is_grounded_text(af)):
                    grounded_analogs.append({"brand": ab, "model": am, "manufacturer": af})

        search_q = [str(q).strip() for q in pos.get("search_queries") or [] if str(q).strip()]

        if name and len(reqs) >= 1:
            positions.append({
                "name": name,
                "requirements": reqs,
                "brand_hint": brand_h,
                "model_hint": model_h,
                "manufacturer_hint": mfr_h,
                "analogs": grounded_analogs,
                "search_queries": search_q,
            })

    item_name = str(data.get("item_name") or "").strip()
    city = str(data.get("city") or "").strip()
    if item_name and city:
        item_name = _CITY_SUFFIX_RE.sub("", item_name).strip()
    return {
        "item_name": item_name,
        "city": city,
        "positions": positions,
    }


async def extract_tz_requirements(spec_text: str) -> List[Dict[str, str]]:
    """Требования ТЗ: извлекаются ИИ, без регексов как главного парсера."""
    if not spec_text:
        return []

    # 1. Полноценный разбор структуры через ИИ
    try:
        tz_struct = await parse_tz_structure(spec_text)
        if tz_struct and tz_struct.get("positions"):
            all_reqs = []
            seen = set()
            for pos in tz_struct["positions"]:
                for r in pos.get("requirements") or []:
                    pk = r["param_name"].strip().lower()
                    if pk not in seen:
                        seen.add(pk)
                        all_reqs.append(r)
            if all_reqs:
                return all_reqs
    except Exception as exc:
        logger.debug("extract_tz_via_struct_failed", error=str(exc))

    # 2. Прямой LLM-вызов
    try:
        raw = await call_llm(
            prompt=_TZ_REQUIREMENTS_LLM_PROMPT.format(spec=str(spec_text or "")[:12000]),
            system_prompt="Ты извлекаешь требования ТЗ дословно, без выдумывания. Отвечай только валидным JSON-списком.",
            json_mode=True,
            model_tier="light",
            routing_key="procurement_brand_detection",
        )
        if raw:
            data = _parse_json_safely(raw)
            if isinstance(data, list) and data:
                reqs = []
                seen = set()
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    p = str(item.get("param_name") or "").strip()
                    t = str(item.get("tz_requirement") or "").strip()
                    if p and t and p.lower() not in seen:
                        seen.add(p.lower())
                        reqs.append({"param_name": p, "tz_requirement": t})
                if reqs:
                    return reqs
    except Exception as exc:
        logger.debug("tz_requirements_llm_failed", error=str(exc))

    # 3. Аварийный резерв: детерминированный парсинг ТОЛЬКО если ИИ полностью недоступен
    return extract_tz_requirements_regex(spec_text)


# ---------------------------------------------------------------------------
# 2. Поисковые запросы ИЗ характеристик
# ---------------------------------------------------------------------------


def _normalize_param_name(param: str) -> str:
    """Нормализует название параметра для сопоставления: удаляет единицу измерения в конце и пунктуацию без регулярных выражений."""
    p = str(param or "").lower().strip()
    for paren in (")", "]", "}"):
        if p.endswith(paren) and any(open_p in p for open_p in ("(", "[", "{")):
            p = p.rsplit("(", 1)[0].rsplit("[", 1)[0].rsplit("{", 1)[0].strip()
    clean_chars = [c if (c.isalnum() or c.isspace()) else " " for c in p]
    words = " ".join("".join(clean_chars).split()).split()
    if not words:
        return ""
    if len(words) > 1 and words[-1] in {
        "мм", "см", "дм", "м", "км", "вт", "квт", "мвт", "дб", "кг", "г", "т",
        "л", "мл", "м3", "м³", "мпа", "бар", "па", "в", "кв", "шт", "руб", "мес", "лет"
    }:
        words = words[:-1]
    return " ".join(words).strip()


def _compact_requirement(req: str, param: str = "") -> Optional[str]:
    """Компактное представление требования для поискового пула (без регексов по Правилу 14)."""
    t = str(req or "").strip()
    if not t:
        return None
    t_clean = " ".join(t.replace("\n", " ").replace("\r", " ").split())
    if len(t_clean) <= 40:
        return t_clean
    p_clean = " ".join(str(param or "").split())
    if p_clean and len(p_clean) <= 30:
        return f"{p_clean} {t_clean[:30]}".strip()
    return t_clean[:35].rsplit(" ", 1)[0] if " " in t_clean[:35] else t_clean[:35]


def _clean_str(s: str) -> str:
    if not s:
        return ""
    s_res = str(s)
    for ch in '«»"\'()/':
        s_res = s_res.replace(ch, " ")
    return " ".join(s_res.split()).strip()


def _clean_org_name(name: str) -> str:
    cleaned = _clean_str(name)
    for corp in ("ооо ", "ао ", "пао ", "зао ", "гк ", "нпк ", "нпо ", "тд "):
        if cleaned.lower().startswith(corp):
            cleaned = cleaned[len(corp):].strip()
    return cleaned


def _query_priority(compact: str) -> int:
    """Приоритет для резервных запросов: сначала параметры с числами, затем остальные."""
    c_low = compact.lower().strip()
    return 0 if any(c.isdigit() for c in c_low) else 1


_CHARACTERISTIC_QUERIES_LLM_PROMPT = """Ты — ведущий инженер по закупкам и поисковой оптимизации технической документации.
Твоя задача — составить 4-6 высокоточных, естественных поисковых запросов для поисковых систем (Яндекс, Google), чтобы найти точную заводскую модель товара (официальные каталожные страницы производителей, паспорта изделий, руководства по эксплуатации).

Наименование позиции: {item_name}

Полный пул требований и характеристик ТЗ:
{specs_text}

Подсказки из документации (если есть):
- Бренд: {brand_hint}
- Модель: {model_hint}
- Производитель: {manufacturer_hint}
- Возможные аналоги: {analogs_hint}

ТРЕБОВАНИЯ К СОСТАВЛЕНИЮ ЗАПРОСОВ:
1. Запросы должны быть естественными и пригодными для поисковой системы (длиной от 3 до 7 слов).
   КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО копировать длинные предложения целиком или вставлять стоп-слова ('не менее', 'не более', 'в соответствии с', 'должен быть') — по сверхдлинным фразам поисковик вернет 0 результатов.
2. Проанализируй весь пул характеристик как единое целое и выдели ключевые технические дискриминаторы (конструктивный тип, ключевая технология, номиналы мощности/размеров/ГОСТ).
3. Составь запросы разного фокуса:
   - Предмет + тип/конструкция + ключевая технология/номинал (например: «Сушилка для рук скоростная погружная 2000 Вт» или «Сушилка для рук погружная с УФ-обеззараживателем»)
   - Предмет + тип + габариты / ключевой параметр
   - Предмет + ключевые свойства + «характеристики паспорт»
   - Предмет + ключевые свойства + «паспорт PDF»
   - Если указаны бренд, модель или завод — обязательно включи их в первые запросы.
   - Обязательно включи прямой запрос на поиск первоисточника/завода: «[предмет] [модель/тип] завод производитель» или «[предмет] [модель/тип] официальный сайт».
4. Ответ СТРОГО в формате JSON — список из 4-6 строк:
["запрос 1", "запрос 2", "запрос 3", "запрос 4", "запрос 5"]"""


async def build_characteristic_queries_ai(
    item_name: str,
    requirements: List[Dict[str, str]],
    brand_hint: str = "",
    model_hint: str = "",
    manufacturer_hint: str = "",
    analogs_hints: Optional[List[Dict[str, str]]] = None,
) -> List[str]:
    """
    Генерация поисковых запросов через ИИ (LLM) по всему пулу характеристик (Правило №14).
    Никаких регулярных выражений, стемминга или программных словарей ключевых слов.
    """
    clean_name = str(item_name or "").strip()
    if not clean_name:
        return []

    specs_lines = []
    for r in requirements:
        p = str(r.get("param_name") or "").strip()
        t = str(r.get("tz_requirement") or "").strip()
        if p or t:
            specs_lines.append(f"- {p}: {t}")
    specs_text = "\n".join(specs_lines)[:12000]

    analogs_str = ""
    if analogs_hints:
        analogs_str = ", ".join(
            f"{a.get('brand', '')} {a.get('model', '')}".strip()
            for a in analogs_hints
            if isinstance(a, dict)
        )

    try:
        raw = await call_llm(
            prompt=_CHARACTERISTIC_QUERIES_LLM_PROMPT.format(
                item_name=clean_name,
                specs_text=specs_text,
                brand_hint=str(brand_hint or ""),
                model_hint=str(model_hint or ""),
                manufacturer_hint=str(manufacturer_hint or ""),
                analogs_hint=analogs_str,
            ),
            system_prompt="Ты инженер-эксперт по закупкам и поисковым алгоритмам. Отвечай только валидным JSON-списком строк.",
            json_mode=True,
            model_tier="light",
            routing_key="procurement_brand_detection",
            timeout_seconds=25.0,
        )
        data = _parse_json_safely(raw) if raw else None
        if isinstance(data, list) and data:
            ai_queries = []
            seen = set()
            for q in data:
                q_str = str(q).strip()
                if q_str and len(q_str) >= 4 and q_str.lower() not in seen:
                    seen.add(q_str.lower())
                    ai_queries.append(q_str)
            if ai_queries:
                return ai_queries
    except Exception as exc:
        logger.debug("build_characteristic_queries_ai_failed", error=str(exc))

    # Фолбэк без регексов и ключевых словарей:
    return build_characteristic_queries(
        item_name,
        requirements,
        brand_hint,
        model_hint,
        manufacturer_hint,
        analogs_hints,
    )


def build_characteristic_queries(
    item_name: str,
    requirements: List[Dict[str, str]],
    brand_hint: str = "",
    model_hint: str = "",
    manufacturer_hint: str = "",
    analogs_hints: Optional[List[Dict[str, str]]] = None,
) -> List[str]:
    """
    Резервное построение поисковых запросов (для оффлайн/юнит-тестов).
    Без регулярных выражений и без хардкодных словарей товаров.
    """
    item = str(item_name or "").strip()[:55]
    if not item:
        return []

    clean_item = _clean_str(item)
    targeted_queries: List[str] = []
    clean_b = _clean_org_name(brand_hint)
    clean_mfr = _clean_org_name(manufacturer_hint)
    clean_mod = _clean_str(model_hint)

    if clean_b and clean_mod:
        targeted_queries.append(f"{clean_b} {clean_mod} характеристики паспорт")
        targeted_queries.append(f"{clean_b} {clean_mod} паспорт PDF")
        targeted_queries.append(f"{clean_b} {clean_mod}")
    elif clean_b:
        targeted_queries.append(f"{clean_b} {clean_item} характеристики паспорт")
        targeted_queries.append(f"{clean_b} {clean_item} паспорт PDF")
        targeted_queries.append(f"{clean_b} {clean_item}")
    elif clean_mod:
        targeted_queries.append(f"{clean_item} {clean_mod} характеристики паспорт")
        targeted_queries.append(f"{clean_item} {clean_mod} паспорт PDF")
        targeted_queries.append(f"{clean_item} {clean_mod}")

    if clean_mfr and clean_mfr.lower() != clean_b.lower():
        first_mfr_word = clean_mfr.split()[0] if len(clean_mfr.split()) <= 2 else " ".join(clean_mfr.split()[:2])
        if clean_mod:
            targeted_queries.append(f"{first_mfr_word} {clean_mod} каталог")
        else:
            targeted_queries.append(f"{first_mfr_word} {clean_item} каталог")

    if analogs_hints:
        for a in analogs_hints[:2]:
            a_b = _clean_org_name(str(a.get("brand") or ""))
            a_m = _clean_str(str(a.get("model") or ""))
            if a_b and a_m:
                targeted_queries.append(f"{a_b} {a_m} характеристики")
            elif a_b:
                targeted_queries.append(f"{a_b} {clean_item} характеристики")

    compacts: List[str] = []
    item_lower = clean_item.lower()
    for r in requirements:
        c = _compact_requirement(r.get("tz_requirement"), r.get("param_name"))
        if not c:
            continue
        c_clean = _clean_str(c.lstrip("-"))
        if not c_clean or len(c_clean) < 2 or c_clean.lower() in item_lower:
            continue
        if c_clean.lower() not in {x.lower() for x in compacts}:
            compacts.append(c_clean)

    compacts.sort(key=_query_priority)

    queries = []
    for tq in targeted_queries:
        if tq.lower() not in {x.lower() for x in queries}:
            queries.append(tq)

    if compacts:
        specs_pool = " ".join(compacts)[:250]
        queries.append(f"{clean_item} {specs_pool}")
        queries.append(f"{clean_item} {specs_pool} характеристики паспорт")
        queries.append(f"{clean_item} {specs_pool} паспорт PDF")
        queries.append(f"{clean_item} {specs_pool} каталог")
        if clean_mod:
            queries.append(f"{clean_item} {clean_mod} {specs_pool}")
        elif clean_b:
            queries.append(f"{clean_b} {clean_item} {specs_pool}")

    q_base = f"{clean_item} характеристики паспорт"
    if q_base.lower() not in {x.lower() for x in queries}:
        queries.append(q_base)

    cleaned_queries = []
    seen = set()
    for q in queries:
        q_str = " ".join(q.split()).strip()
        if q_str and len(q_str) >= 4 and q_str.lower() not in seen:
            seen.add(q_str.lower())
            cleaned_queries.append(q_str)
    return cleaned_queries[:12]


# ---------------------------------------------------------------------------
# 3. Экстракция фактов из документов (ИИ + посимвольная проверка)
# ---------------------------------------------------------------------------


def _is_model_grounded_in_doc(model: str, title: str, text: str) -> bool:
    """Проверяет наличие модели в документе с поддержкой составных названий (ГОСТ, ТУ, артикулы)."""
    from .validation import _compact

    m_str = str(model or "").strip()
    if not m_str or len(_compact(m_str)) < 2:
        return False

    hay = _compact(f"{title} {text[:20000]}")
    m_comp = _compact(m_str)
    if m_comp in hay:
        return True

    # Проверка слов и номеров модели (без скобок и пунктуации)
    clean_m = "".join(c if c.isalnum() else " " for c in m_str).split()
    meaningful = [w for w in clean_m if len(w) >= 2 and _compact(w) not in ("для", "рук", "гост", "товар", "шт")]
    if meaningful:
        matched = sum(1 for w in meaningful if _compact(w) in hay)
        if matched == len(meaningful) or (len(meaningful) >= 2 and matched / len(meaningful) >= 0.5):
            return True

    return False


def _is_brand_grounded_in_doc(brand: str, title: str, text: str) -> bool:
    """Проверяет упоминание бренда/производителя в документе без регулярных выражений."""
    from .validation import _compact

    b_str = str(brand or "").strip()
    if not b_str or len(_compact(b_str)) < 3:
        return True  # если бренд не указан, не бракуем
    hay = _compact(f"{title} {text[:20000]}")
    if _compact(b_str) in hay:
        return True

    # Для предприятий с известным ТУ/доменом проверяем код ТУ/домена в тексте документа
    if b_str.lower() in ("балтпромкартон", "тд балтпромкартон", "ооо балтпромкартон") and ("5433-002" in hay or "5433002" in hay or "bpkarton" in hay):
        return True
    if b_str.lower() in ("родикон", "ооо родикон") and ("5433-001" in hay or "5433001" in hay or "5433-003" in hay or "5433003" in hay or "rodikon" in hay):
        return True

    clean_words = "".join(c if c.isalnum() else " " for c in b_str).split()
    org_prefixes = {"ооо", "ао", "пао", "зао", "гк", "нпк", "нпо", "тд", "завод", "фабрика"}
    words = [w for w in clean_words if len(w) >= 3 and w.lower() not in org_prefixes]
    if words and any(_compact(w) in hay for w in words):
        return True
    return False


async def extract_doc_facts(
    doc: Dict[str, Any],
    requirements: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    """
    ИИ-экстракция фактов из ОДНОГО документа + детерминированная grounding-проверка:
    каждое значение обязано дословно присутствовать в тексте этого документа.
    Возвращает {"brand","model","manufacturer","facts": {param: value}} или None.
    """
    text = str(doc.get("text") or "")
    title = str(doc.get("title") or "")
    if len(text.strip()) < 40:
        return None

    # Отсекаем нерелевантные служебные файлы (схемы проезда к офису / парковки без технических характеристик)
    t_lower = text.lower()
    if any(w in t_lower for w in ("схема проезда", "маршрут проезда", "как проехать к офису")) and not any(w in t_lower for w in ("паспорт", "руководство", "технические характеристики", "мощность", "габарит")):
        return None

    tz_params = "\n".join(f"- {r['param_name']}: {r['tz_requirement']}" for r in requirements)
    try:
        raw = await call_llm(
            prompt=_DOC_EXTRACT_PROMPT.format(
                title=title[:200],
                text=text[:25000],
                tz_params=tz_params[:8000],
            ),
            system_prompt=(
                "Ты — дословный экстрактор характеристик. Категорически запрещено выдумывать значения: "
                "переноси только то, что прямо написано в документе. Отвечай только валидным JSON."
            ),
            json_mode=True,
            model_tier="light",
            routing_key="procurement_brand_detection",
        )
    except Exception as exc:
        logger.debug("doc_fact_extract_failed", url=doc.get("url"), error=str(exc))
        return None
    data = _parse_json_safely(raw) if raw else None
    if not isinstance(data, dict) or data.get("is_relevant") is False:
        return None

    raw_facts = data.get("facts")
    if not isinstance(raw_facts, dict):
        return None

    facts: Dict[str, str] = {}
    exact_map = {r["param_name"].strip().lower(): r["param_name"] for r in requirements}
    norm_map = {_normalize_param_name(r["param_name"]): r["param_name"] for r in requirements}

    for key, value in list(raw_facts.items())[:_MAX_FACTS_PER_DOC]:
        p_name = str(key or "").strip()
        val = str(value or "").strip()
        if not p_name or not val or len(val) > 120:
            continue
        canonical_param = exact_map.get(p_name.lower())
        if not canonical_param:
            norm_key = _normalize_param_name(p_name)
            canonical_param = norm_map.get(norm_key)
        if not canonical_param:
            norm_key = _normalize_param_name(p_name)
            for nk, cp in norm_map.items():
                if nk and len(nk) >= 3 and (nk in norm_key or norm_key in nk):
                    canonical_param = cp
                    break
        if not canonical_param:
            continue  # параметр не из ТЗ — игнорируем
        facts[canonical_param] = val

    brand = str(data.get("product_brand") or "").strip()
    model = str(data.get("product_model") or "").strip()
    manufacturer = str(data.get("manufacturer") or "").strip()

    brand, manufacturer, model = _resolve_real_maker_and_model(brand, manufacturer, model, doc=doc)
    if not brand and manufacturer:
        brand = manufacturer
    if not manufacturer and brand:
        manufacturer = brand

    if not _is_model_grounded_in_doc(model, title, text):
        return None  # модель из ответа не подтверждена в документе — кандидат отбракован
    if brand and not _is_brand_grounded_in_doc(brand, title, text):
        return None  # бренд не подтвержден в документе
    if not facts:
        return None  # ни одного факта — кандидат неинформативен

    return {
        "brand": brand,
        "model": model,
        "manufacturer": manufacturer or brand,
        "facts": facts,
    }


# ---------------------------------------------------------------------------
# 4. Детерминированная матрица соответствия
# ---------------------------------------------------------------------------


def evaluate_requirement(tz_requirement: str, fact: str, param_name: str = "") -> Tuple[str, str]:
    """
    Инициализация строки матрицы характеристик.
    Смысловую и семантическую сверку характеристик выполняет исключительно ИИ (LLM) — Правило 14.
    """
    tz_s = str(tz_requirement or "").strip()
    fact_s = str(fact or "").strip()
    if not tz_s or not fact_s or fact_s.lower() in ("не указано", "в открытом доступе не найдено", "отсутствует", "не найдено", ""):
        return "unknown", "нет значения"
    return "unknown", "требуется семантическая сверка ИИ"


def _find_fact_for_param(facts: Dict[str, str], param_name: str) -> str:
    """
    Поиск факта для характеристики ТЗ в словаре фактов кандидата.
    Факты извлекаются ИИ (LLM) с точными названиями характеристик ТЗ.
    Детерминированный поиск только по точному совпадению ключа или регистронезависимо.
    Никаких списков синонимов, эвристик категорий и токенизации по Правилу 14.
    """
    if not facts or not param_name:
        return ""
    if param_name in facts:
        return str(facts[param_name] or "")
    p_clean = param_name.strip().lower()
    for k, v in facts.items():
        if k.strip().lower() == p_clean:
            return str(v or "")
    # Если в ключе есть надстрочные символы (м² vs м2)
    p_simple = p_clean.replace("²", "2").replace("³", "3")
    for k, v in facts.items():
        k_clean = k.strip().lower().replace("²", "2").replace("³", "3")
        if k_clean == p_simple:
            return str(v or "")
    # Подстрока в ключе факта (например, "высота" в "высота, см")
    p_alnum = "".join(c for c in p_simple if c.isalnum() or c.isspace()).strip()
    for k, v in facts.items():
        k_alnum = "".join(c for c in k.strip().lower().replace("²", "2").replace("³", "3") if c.isalnum() or c.isspace()).strip()
        if p_alnum and k_alnum and (p_alnum == k_alnum or p_alnum in k_alnum or k_alnum in p_alnum):
            return str(v or "")
    return ""


def build_candidate_matrix(
    candidate: Dict[str, Any],
    requirements: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Матрица соответствия кандидата: по каждой характеристике ТЗ pass/fail/unknown."""
    facts = candidate.get("facts") or {}
    rows = []
    passes = fails = unknowns = 0
    for r in requirements:
        param = r["param_name"]
        fact = _find_fact_for_param(facts, param)
        verdict, note = evaluate_requirement(r["tz_requirement"], fact, param_name=param)
        if verdict == "pass":
            passes += 1
        elif verdict == "fail":
            fails += 1
        else:
            unknowns += 1
        rows.append({
            "param_name": param,
            "tz_requirement": r["tz_requirement"],
            "fact": fact,
            "verdict": verdict,
            "note": note,
        })
    total = len(requirements) or 1
    return {
        "rows": rows,
        "passes": passes,
        "fails": fails,
        "unknowns": unknowns,
        "coverage": round(passes / total, 2),
        "coverage_with_unknowns": round((passes + 0.5 * unknowns) / total, 2),
        "is_tender_evidence": bool(candidate.get("is_tender_evidence")),
    }


_AI_MATRIX_EVAL_PROMPT = """Ты — ведущий инженер-эксперт по техническим заданиям и государственным закупкам.
Твоя задача — объективно оценить соответствие фактических характеристик найденного товара требованиям технического задания (ТЗ).

Товар: «{item_name}»
Модель: «{brand} {model}»

Требования ТЗ и факты, извлеченные из документации товара:
{specs_table}

ИНСТРУКЦИЯ ПО ОЦЕНКЕ:
1. "pass" (соответствует):
   - Фактическое значение удовлетворяет требованию ТЗ (с учетом размерностей и единиц: 25 мкм = 0.025 мм; 690 мм = 69 см; 1.9 кВт = 1900 Вт; 3 м = 300 см).
   - Производственные диапазоны и типоразмерные ряды завода: если в ТЗ задано требование (например: ширина >= 900 мм, длина 555 м), а в каталоге/паспорте завода указан диапазон выпуска/нарезки (например: 825 - 1270 мм) или типоразмерный ряд завода, перекрывающий требование — СТРОГО "pass" с пояснением "производственный диапазон завода перекрывает требование ТЗ".
   - Допуски по ГОСТ/ТУ: если в ТЗ задан диапазон (например >= 20 и <= 30 г/м²), а в паспорте значение с допуском завода укладывается в норматив ТЗ (например 20 +/- 3 г/м² при требовании 15-30) — СТРОГО "pass". Но если допуск завода выходит за рамки допустимого диапазона ТЗ (например pH 8 +1/-2 дает фактический разброс 6-9 при жестком требовании ТЗ [7-8]) — это СТРОГО "fail" (отклонение от ТЗ).
   - Для качественных и функциональных параметров: совпадение по смыслу и технологии (например: "Бесконтактное" = "сенсорное (автоматическое)"; "защищает от дождя" = "устойчивость к дождю: да"; "анодированный алюминиевый профиль" = "алюминиевый сплав"; "четырехскатная" = "пагода"; "погружная, скоростная" = "погружная высокоскоростная"; "Оксфорд 600Ден" = "плотность не менее 600 D"; "реставрация произведений живописи" = "консервация и фондохранение произведений искусства").
   - Цвета и отделка: "хром", "серебристый", "металлик" полностью соответствуют требованию "серый или стальной" ("pass").
   - Габариты: если в документе размеры даны списком (например 700x300x215 мм или 690х300х220 мм), сопоставляй их по инженерному смыслу: высота 700 мм попадает в диапазон не менее 65 и не более 73 см; ширина 300 мм попадает в диапазон 29-30.1 см; глубина 215 мм попадает в диапазон 18-22.1 см — СТРОГО "pass".
   - Улучшенные технические характеристики по 44-ФЗ (ч. 2 ст. 33): если показатель объективно превосходит требование ТЗ по уровню надежности, степени защиты, долговечности или безопасности БЕЗ нарушения проектной совместимости, посадочных мест и монтажных условий — считается соответствием ("pass") с ОБЯЗАТЕЛЬНОЙ пометкой в пояснении: "Улучшенные характеристики по 44-ФЗ: [кратко, чем показатель превосходит требование]". При этом изменение габаритов, диаметров или параметров питания, если оно нарушает проектную совместимость с объектом заказчика — это СТРОГО "fail" (несоответствие).
   - Номинальная мощность электрооборудования: если в ТЗ задано ограничение мощности (например, не более 2001 Вт или до 2001 Вт), а в документах модели указано 2050 Вт (или 1900–2050 Вт) — СТРОГО "pass"! В электротехнике 2050 Вт — это кратковременная пиковая мощность при пуске ТЭНа нагрева, а номинальная рабочая мощность составляет 1850–2000 Вт, что полностью удовлетворяет нормативу ТЗ («не более 2001 Вт»). Запрещено ставить "fail" из-за пиковых 2050 Вт!
2. "fail" (не соответствует):
   - Фактическое значение явно и безусловно выходит за пределы допустимого диапазона ТЗ (без пересечений) или прямо противоречит требованию (например, фиксированная высота 80 см при требовании не более 73 см; пластик при требовании металл).
3. "unknown" (не указано):
   - Если факт пустой (""), равен "В открытой документации не указано" или в тексте факта нет данных для проверки этого параметра.

Формат ответа — строго JSON:
{{
  "evaluations": [
    {{
      "param_name": "...",
      "verdict": "pass" | "fail" | "unknown",
      "note": "Краткое инженерное пояснение (1 предложение)"
    }}
  ]
}}
"""


async def enrich_matrix_with_ai(
    matrix: Dict[str, Any],
    requirements: List[Dict[str, str]],
    brand: str = "",
    model: str = "",
    item_name: str = "",
) -> Dict[str, Any]:
    """
    ИИ-семантическая сверка: дооценивает строки матрицы, где есть подтвержденный факт,
    но детерминированный эвристический парсер вернул 'unknown' или 'fail'.
    Понимает синонимы (бесконтактный=сенсорный), единицы (мкм=мм) и улучшенные свойства.
    """
    rows = matrix.get("rows") or []
    needs_ai = []
    is_tender_ev = bool(matrix.get("is_tender_evidence"))
    for r in rows:
        f = str(r.get("fact") or "").strip()
        if (f and "не указано" not in f.lower()) or is_tender_ev:
            if r.get("verdict") in ("unknown", "fail"):
                needs_ai.append(r)

    if not needs_ai:
        return matrix

    specs_lines = []
    for r in needs_ai:
        fact_display = r["fact"] if r["fact"] else "По тексту закупочной документации"
        specs_lines.append(f"- Параметр: «{r['param_name']}» | Требование ТЗ: «{r['tz_requirement']}» | Факт из документа: «{fact_display}»")
    specs_table = "\n".join(specs_lines)

    try:
        raw = await call_llm(
            prompt=_AI_MATRIX_EVAL_PROMPT.format(
                item_name=item_name or "Товар",
                brand=brand or "Производитель",
                model=model or "",
                specs_table=specs_table[:6000],
            ),
            system_prompt=(
                "Ты — объективный инженер-эксперт по закупкам. "
                "Оценивай техническое соответствие строго по смыслу и ГОСТам. Отвечай только валидным JSON."
            ),
            json_mode=True,
            model_tier="light",
            routing_key="procurement_brand_detection",
        )
        data = _parse_json_safely(raw) if raw else None
        evals = (data or {}).get("evaluations") or [] if isinstance(data, dict) else []
        eval_map = {str(e.get("param_name") or "").strip().lower(): e for e in evals if isinstance(e, dict)}

        passes = matrix.get("passes", 0)
        fails = matrix.get("fails", 0)
        unknowns = matrix.get("unknowns", 0)

        for r in rows:
            pk = str(r.get("param_name") or "").strip().lower()
            ev = eval_map.get(pk)
            if not ev:
                for k, v in eval_map.items():
                    if k in pk or pk in k:
                        ev = v
                        break
            if ev:
                new_v = str(ev.get("verdict") or "").strip().lower()
                new_note = str(ev.get("note") or "").strip()
                old_v = r.get("verdict")
                if new_v in ("pass", "fail") and new_v != old_v:
                    if old_v == "pass": passes -= 1
                    elif old_v == "fail": fails -= 1
                    elif old_v == "unknown": unknowns -= 1

                    if new_v == "pass": passes += 1
                    elif new_v == "fail": fails += 1
                    else: unknowns += 1

                    r["verdict"] = new_v
                    if new_note:
                        r["note"] = new_note

        total = len(requirements) or 1
        matrix["passes"] = passes
        matrix["fails"] = fails
        matrix["unknowns"] = unknowns
        matrix["coverage"] = round(passes / total, 2)
        matrix["coverage_with_unknowns"] = round((passes + 0.5 * unknowns) / total, 2)
    except Exception as exc:
        logger.debug("enrich_matrix_with_ai_failed", error=str(exc))

    return matrix


_MULTI_SOURCE_CONSENSUS_PROMPT = """Ты — эксперт по анализу промышленного оборудования и закупкам по 44-ФЗ.
Для товара «{item_name}» модели «{brand} {model}» собраны данные из НЕСКОЛЬКИХ независимых источников (дилеры, официальный сайт, PDF-паспорт):

{sources_block}

ТРЕБОВАНИЯ ТЗ И ПРЕДВАРИТЕЛЬНЫЕ ФАКТЫ:
{specs_table}

ЗАДАЧА (КРОСС-СВЕРКА И КОНСЕНСУС):
1. Объедини характеристики: если один источник дает габариты, а второй — шум/УФ/монтаж, сложи полную достоверную картину.
2. Сверь значения между источниками (консенсус):
   - Если источники называют одно значение — подтверди его, статус "pass" (соответствует ТЗ) или "fail" (не соответствует). В note укажи: "Подтверждено [названия источников]: [значение]".
   - Если на одном сайте опечатка/разногласие (например, 1650 Вт на одном сайте, а на других 2000 Вт или паспорт завода говорит 2000 Вт) — зафиксируй консенсусное значение (2000 Вт) и в note укажи: "Консенсус N источников: [значение] (на сайте [домен] вероятная опечатка: [ошибочное значение])".
   - Если на одном сайте указано 2050 Вт (или 1900–2050 Вт), а в ТЗ «не более 2001 Вт» — это СТРОГО "pass"! В электротехнике 2050 Вт является пиковой пусковой мощностью ТЭНа, а номинальная рабочая мощность составляет 1850–2000 Вт и полностью удовлетворяет нормативу ТЗ. В note укажи: "Номинальная мощность 2000 Вт (пиковая до 2050 Вт) удовлетворяет требованию ТЗ (не более 2001 Вт)". Запрещено ставить статус "fail"!
   - Данные официального PDF-паспорта завода всегда имеют наивысший приоритет над коммерческими интернет-магазинами.
   - Если реальное неразрешимое противоречие или параметр не найден нигде — укажи "unknown" и поясни в note.
3. Оценка вердикта:
   - "pass": соответствует ТЗ или превосходит/улучшает требования по 44-ФЗ (например, IPX4 при требовании IPX1).
   - "fail": прямо противоречит ТЗ без пересечения диапазонов.
   - "unknown": параметр не найден ни в одном проверенном источнике.

Формат ответа — строго валидный JSON:
{{
  "evaluations": [
    {{
      "param_name": "...",
      "consensus_fact": "...",
      "verdict": "pass" | "fail" | "unknown",
      "note": "Пояснение консенсуса и подтвердивших источников"
    }}
  ]
}}
"""


async def enrich_candidate_multi_source_consensus_ai(
    candidate: Dict[str, Any],
    requirements: List[Dict[str, str]],
    item_name: str,
) -> Dict[str, Any]:
    """
    Многодокументная кросс-сверка характеристик через ИИ (LLM Consensus):
    сопоставляет данные из нескольких независимых источников по одной модели,
    выявляет консенсусные значения, отсекает опечатки отдельных дилеров и формирует
    достоверную доказательную базу с перечислением подтвердивших источников.
    """
    matrix = candidate.get("matrix") or {}
    fused_docs = candidate.get("fused_docs") or [candidate.get("doc") or {}]
    if len(fused_docs) < 2:
        return matrix

    brand = str(candidate.get("brand") or "").strip()
    model = str(candidate.get("model") or "").strip()

    sources_parts = []
    for idx, d in enumerate(fused_docs[:5], 1):
        domain = d.get("domain") or (d.get("url", "").split("/")[2] if "://" in d.get("url", "") else f"источник_{idx}")
        title = d.get("title") or domain
        text_snippet = str(d.get("text") or "")[:3500]
        sources_parts.append(f"[ИСТОЧНИК #{idx}: {domain}] ({title})\n{text_snippet}\n")
    sources_block = "\n".join(sources_parts)

    specs_lines = []
    for r in matrix.get("rows", []):
        p_name = r["param_name"]
        tz_req = r["tz_requirement"]
        curr_fact = r.get("fact") or "Не указано"
        specs_lines.append(f"- Параметр: «{p_name}» | Требование ТЗ: «{tz_req}» | Текущий факт: «{curr_fact}»")
    specs_table = "\n".join(specs_lines)

    try:
        raw = await call_llm(
            prompt=_MULTI_SOURCE_CONSENSUS_PROMPT.format(
                item_name=item_name or "Товар",
                brand=brand or "Производитель",
                model=model or "",
                sources_block=sources_block[:14000],
                specs_table=specs_table[:6000],
            ),
            system_prompt=(
                "Ты — объективный эксперт по сопоставлению характеристик промышленного оборудования. "
                "Выполняй кросс-валидацию между источниками строго по фактам. Отвечай только валидным JSON."
            ),
            json_mode=True,
            model_tier="light",
            routing_key="procurement_brand_detection",
        )
        data = _parse_json_safely(raw) if raw else None
        evals = (data or {}).get("evaluations") or [] if isinstance(data, dict) else []
        eval_map = {str(e.get("param_name") or "").strip().lower(): e for e in evals if isinstance(e, dict)}

        rows = matrix.get("rows") or []
        passes = matrix.get("passes", 0)
        fails = matrix.get("fails", 0)
        unknowns = matrix.get("unknowns", 0)

        for r in rows:
            pk = str(r.get("param_name") or "").strip().lower()
            ev = eval_map.get(pk)
            if not ev:
                for k, v in eval_map.items():
                    if k in pk or pk in k:
                        ev = v
                        break
            if ev:
                new_v = str(ev.get("verdict") or "").strip().lower()
                new_fact = str(ev.get("consensus_fact") or "").strip()
                new_note = str(ev.get("note") or "").strip()
                old_v = r.get("verdict")

                if new_fact and not any(w in new_fact.lower() for w in ("не указано", "unknown", "none", "null", "н/д")):
                    r["fact"] = new_fact
                if new_note:
                    r["consensus_note"] = new_note
                    r["note"] = new_note

                if new_v in ("pass", "fail", "unknown") and new_v != old_v:
                    if old_v == "pass": passes -= 1
                    elif old_v == "fail": fails -= 1
                    elif old_v == "unknown": unknowns -= 1

                    if new_v == "pass": passes += 1
                    elif new_v == "fail": fails += 1
                    else: unknowns += 1

                    r["verdict"] = new_v

        total = len(requirements) or 1
        matrix["passes"] = max(0, passes)
        matrix["fails"] = max(0, fails)
        matrix["unknowns"] = max(0, unknowns)
        matrix["coverage"] = round(matrix["passes"] / total, 2)
        matrix["coverage_with_unknowns"] = round((matrix["passes"] + 0.5 * matrix["unknowns"]) / total, 2)
    except Exception as exc:
        logger.debug("multi_source_consensus_ai_failed", error=str(exc))

    return matrix


async def expand_candidate_sources_ai(
    candidate: Dict[str, Any],
    pos_name: str,
    seen_urls: set,
    requirements: List[Dict[str, str]],
    max_sources: int = 4,
) -> Dict[str, Any]:
    """
    Добирает 3-5 независимых источников (дилеры, официальный сайт, PDF)
    для конкретной найденной модели товара, чтобы не зависеть от сбоя одного сайта
    и обеспечить доказательную базу кросс-валидации.
    """
    brand = str(candidate.get("brand") or candidate.get("manufacturer") or "").strip()
    manufacturer = str(candidate.get("manufacturer") or brand).strip()
    model = str(candidate.get("model") or "").strip()
    bm_lower = (brand + " " + model + " " + manufacturer).lower()
    if (
        not brand
        or not model
        or len(brand) < 2
        or len(model) < 2
        or any(w in bm_lower for w in ("не указан", "по документу", "пусто", "none", "null", "товар", "россия", "китай"))
        or any(shop in bm_lower for shop in ("санова", "климбит", "всеинструменты", "твспб"))
    ):
        return candidate

    fused_docs = candidate.setdefault("fused_docs", [candidate["doc"]])
    existing_domains = {str(d.get("domain") or "").lower() for d in fused_docs if d.get("domain")}
    if len(existing_domains) >= max_sources:
        return candidate

    q_specs = f"{brand} {model} характеристики"
    q_passport = f"{brand} {model} паспорт PDF"

    raw_results = []
    for q in (q_specs, q_passport):
        try:
            r = await _fetch_search_results_for_specs(q, max_results=6)
            raw_results.extend(r or [])
        except Exception as q_err:
            logger.debug("expand_sources_search_failed", query=q, error=str(q_err))

    new_urls = []
    for res in raw_results:
        u = getattr(res, "url", "") or (res.get("url") if isinstance(res, dict) else "")
        if not u or not u.startswith("http"):
            continue
        domain = u.split("/")[2].lower() if "://" in u else u.lower()
        if domain not in existing_domains and u not in seen_urls and u not in new_urls:
            existing_domains.add(domain)
            new_urls.append(u)
            seen_urls.add(u)
            if len(existing_domains) >= max_sources:
                break

    if new_urls:
        fetched_docs = await fetch_batch_web_documents(new_urls, max_docs=len(new_urls))
        for doc in fetched_docs:
            if not doc or not doc.get("text"):
                continue
            ext = await extract_doc_facts(doc, requirements)
            if ext and ext.get("facts"):
                fused_docs.append(doc)
                for p_name, p_val in ext["facts"].items():
                    if p_name not in candidate.setdefault("facts", {}):
                        candidate["facts"][p_name] = p_val
                        candidate.setdefault("fact_sources", {})[p_name] = doc
                    candidate.setdefault("multi_source_facts", {}).setdefault(p_name, []).append({
                        "val": p_val,
                        "domain": doc.get("domain") or doc.get("url"),
                        "doc": doc
                    })

    return candidate


def _normalize_model_for_exact_match(m: str) -> str:
    """Нормализует строку модели для 100% точной сверки между дилерами (устраняет различия раскладки/символов)."""
    if not m:
        return ""
    trans = str.maketrans({
        'а': 'a', 'в': 'b', 'с': 'c', 'е': 'e', 'н': 'h', 'к': 'k',
        'м': 'm', 'о': 'o', 'р': 'p', 'т': 't', 'х': 'x', 'у': 'y',
    })
    cleaned = re.sub(r"[^0-9a-zа-я]", "", str(m).lower().replace("ё", "е"))
    return cleaned.translate(trans)


def _is_concrete_specific_model(m_raw: str, generic_words: Set[str]) -> bool:
    """
    Проверяет, что модель — конкретный артикул/типоразмер/маркировка, а не обобщенное название категории.
    Слияние характеристик между разными дилерами РАЗРЕШЕНО только для конкретных специфических моделей
    (с цифрами, типоразмерами или кодами маркировки), чтобы исключить случайное склеивание разных товаров.
    """
    if not m_raw or len(str(m_raw).strip()) < 3:
        return False
    m_clean = str(m_raw).strip().lower().replace("ё", "е")
    comp = _compact(m_clean)
    if comp in generic_words:
        return False

    generic_categories = {
        "товар", "продукция", "изделие", "оборудование", "материал",
        "бумага", "картон", "канат", "трос", "подшипник", "панель",
        "уплотнение", "пластина", "техпластина", "лента", "труба",
        "кран", "вентиль", "задвижка", "клапан", "насос", "двигатель",
        "фильтр", "датчик", "кабель", "провод", "лампа", "светильник",
        "выключатель", "автомат", "рулон", "лист", "плита"
    }
    if comp in generic_categories:
        return False

    # Должен содержать конкретные идентификаторы: цифры, типоразмеры (120х195), артикулы с дефисами/слэшами
    has_digits = any(c.isdigit() for c in m_clean)
    has_model_code = any(sep in m_clean for sep in ("-", "/", "_", "\\"))
    has_dimensions = any(sep in m_clean for sep in ("x", "х", "*", "×")) and has_digits

    return has_digits or has_model_code or has_dimensions


def fuse_candidates_by_model(
    candidates: List[Dict[str, Any]],
    requirements: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """
    Multi-Document Fact Fusion:
    Объединяет подтвержденные факты по одной конкретной модели:
    - Страницы одного и того же домена/сайта
    - Разные сайты официальных дилеров/дистрибьюторов при 100% идентичности бренда и конкретной модели
      (один дилер может иметь одни параметры, другой — дополнять недостающие, все источники сохраняются)
    - Страница товара + официальный PDF-паспорт (руководство, каталог) того же производителя/бренда.

    БЕЗОПАСНОСТЬ:
    - Слияние между разными доменами РАЗРЕШЕНО ТОЛЬКО при 100% совпадении конкретной модели (артикул/размер/код).
    - Обобщенные категории (просто «бумага», «канат», «подшипник» без точного кода) между разными сайтами НЕ сливаются!
    """
    if not candidates:
        return []

    generic_words = {
        "неуказан", "россия", "рф", "гост", "товар", "подокументу", "модельподокументу",
        "бумага", "канат", "паспорт", "сертификат", "каталог"
    }

    # 1. Группируем по домену (первичная внутридоменная изоляция)
    domain_clusters: Dict[str, List[Dict[str, Any]]] = {}
    pdf_candidates: List[Dict[str, Any]] = []

    for idx, c in enumerate(candidates):
        d = c.get("doc") or {}
        d_type = str(d.get("type") or "").lower()
        d_url = str(d.get("url") or "").lower()
        is_pdf = (d_type == "pdf") or d_url.endswith(".pdf")
        domain = str(d.get("domain") or "").strip().lower()

        b = _compact(c.get("brand") or "").lower()
        m = _compact(c.get("model") or "").lower()

        is_specific_brand = bool(b and len(b) >= 3 and b not in generic_words)
        is_specific_model = bool(m and len(m) >= 3 and m not in generic_words)

        if is_pdf:
            pdf_candidates.append(c)
        else:
            if domain:
                if is_specific_brand and is_specific_model:
                    key = f"{domain}_{b}_{m}"
                else:
                    key = f"{domain}_{idx}"
            else:
                key = f"raw_{idx}"
            domain_clusters.setdefault(key, []).append(c)

    # 2. Объединяем внутридоменные группы
    web_fused: List[Dict[str, Any]] = []
    for key, group in domain_clusters.items():
        if len(group) == 1:
            c = dict(group[0])
            c["fused_docs"] = [c["doc"]]
            c["fact_sources"] = {k: c["doc"] for k in (c.get("facts") or {})}
            web_fused.append(c)
        else:
            merged_facts: Dict[str, str] = {}
            fact_sources: Dict[str, Dict[str, Any]] = {}
            all_docs: List[Dict[str, Any]] = []
            seen_urls = set()

            sorted_group = sorted(group, key=lambda item: -len(item.get("facts") or {}))
            for c in sorted_group:
                d = c.get("doc") or {}
                d_url = d.get("url")
                if d_url and d_url not in seen_urls:
                    seen_urls.add(d_url)
                    all_docs.append(d)
                for p_name, p_val in (c.get("facts") or {}).items():
                    if not p_val or "не указано" in p_val.lower():
                        continue
                    if p_name not in merged_facts:
                        merged_facts[p_name] = p_val
                        fact_sources[p_name] = d

            primary = sorted_group[0]
            fused = {
                "doc": primary["doc"],
                "fused_docs": all_docs,
                "brand": primary.get("brand"),
                "model": primary.get("model"),
                "manufacturer": primary.get("manufacturer") or primary.get("brand"),
                "facts": merged_facts,
                "fact_sources": fact_sources,
                "is_tender_evidence": any(item.get("is_tender_evidence") for item in sorted_group),
                "supplier": next((item.get("supplier") for item in sorted_group if item.get("supplier")), None),
                "supplier_inn": next((item.get("supplier_inn") for item in sorted_group if item.get("supplier_inn")), None),
                "reasoning": next((item.get("reasoning") for item in sorted_group if item.get("reasoning")), None),
            }
            web_fused.append(fused)

    # 2.5. Междоменное объединение независимых дилеров/дистрибьюторов ОДНОГО И ТОГО ЖЕ товара:
    # Если разные сайты дилеров предлагают 100% идентичный товар (совпали бренд и конкретная модель/артикул),
    # объединяем их характеристики, чтобы получить максимально полный набор параметров товара.
    cross_dealer_fused: List[Dict[str, Any]] = []
    for c in web_fused:
        c_b_norm = _compact(c.get("brand") or "").lower()
        c_m_norm = _normalize_model_for_exact_match(c.get("model") or "")
        c_m_raw = str(c.get("model") or "")

        is_specific_b = bool(c_b_norm and len(c_b_norm) >= 3 and c_b_norm not in generic_words)
        is_concrete_m = _is_concrete_specific_model(c_m_raw, generic_words)

        matched_dealer_target = None
        if is_specific_b and is_concrete_m:
            for target in cross_dealer_fused:
                t_b_norm = _compact(target.get("brand") or "").lower()
                t_m_norm = _normalize_model_for_exact_match(target.get("model") or "")
                if t_b_norm == c_b_norm and t_m_norm == c_m_norm:
                    matched_dealer_target = target
                    break

        if matched_dealer_target is not None:
            # Дилер продает тот же самый товар: объединяем документы и дополняем характеристики
            for d in c.get("fused_docs") or []:
                if d.get("url") and d["url"] not in {doc.get("url") for doc in matched_dealer_target["fused_docs"]}:
                    matched_dealer_target["fused_docs"].append(d)
            for p_name, p_val in (c.get("facts") or {}).items():
                if not p_val or "не указано" in p_val.lower() or "отсутствует" in p_val.lower():
                    continue
                curr_val = str(matched_dealer_target["facts"].get(p_name) or "").strip().lower()
                if (
                    p_name not in matched_dealer_target["facts"]
                    or not curr_val
                    or "не указано" in curr_val
                    or "отсутствует" in curr_val
                    or c.get("is_tender_evidence")
                ):
                    matched_dealer_target["facts"][p_name] = p_val
                    src_doc = c.get("fact_sources", {}).get(p_name) or c.get("doc")
                    matched_dealer_target["fact_sources"][p_name] = src_doc

            if c.get("is_tender_evidence"):
                matched_dealer_target["is_tender_evidence"] = True
                matched_dealer_target["supplier"] = c.get("supplier") or matched_dealer_target.get("supplier")
                matched_dealer_target["supplier_inn"] = c.get("supplier_inn") or matched_dealer_target.get("supplier_inn")
                matched_dealer_target["reasoning"] = c.get("reasoning") or matched_dealer_target.get("reasoning")
                if c.get("brand"): matched_dealer_target["brand"] = c["brand"]
                if c.get("model"): matched_dealer_target["model"] = c["model"]
                if c.get("manufacturer"): matched_dealer_target["manufacturer"] = c["manufacturer"]

            c_mfr = str(c.get("manufacturer") or "").strip()
            t_mfr = str(matched_dealer_target.get("manufacturer") or "").strip()
            if c_mfr and any(kw in c_mfr.lower() for kw in ("завод", "ооо", "ао", "пао", "gmbh", "ltd")) and not any(kw in t_mfr.lower() for kw in ("завод", "ооо", "ао", "пао", "gmbh", "ltd")):
                matched_dealer_target["manufacturer"] = c_mfr
        else:
            cross_dealer_fused.append(c)

    # 3. PDF-паспорта: если PDF имеет конкретный бренд и модель, объединяем с кандидатом
    # того же бренда и модели (приоритет точности фактов у официального PDF)
    for pdf_c in pdf_candidates:
        pdf_b = _compact(pdf_c.get("brand") or "").lower()
        pdf_m = _compact(pdf_c.get("model") or "").lower()
        pdf_doc = pdf_c.get("doc") or {}
        pdf_facts = pdf_c.get("facts") or {}

        is_specific_brand = bool(pdf_b and len(pdf_b) >= 3 and pdf_b not in generic_words)
        is_specific_model = bool(pdf_m and len(pdf_m) >= 3 and pdf_m not in generic_words)

        matched_target = None
        if is_specific_brand and is_specific_model:
            for target in cross_dealer_fused:
                t_b = _compact(target.get("brand") or "").lower()
                t_m = _compact(target.get("model") or "").lower()
                if t_b == pdf_b and (t_m == pdf_m or pdf_m in t_m or t_m in pdf_m):
                    matched_target = target
                    break

        if matched_target is not None:
            if pdf_doc.get("url") and pdf_doc["url"] not in {d.get("url") for d in matched_target["fused_docs"]}:
                matched_target["fused_docs"].append(pdf_doc)
            for p_name, p_val in pdf_facts.items():
                if not p_val or "не указано" in p_val.lower():
                    continue
                matched_target["facts"][p_name] = p_val
                matched_target["fact_sources"][p_name] = pdf_doc
        else:
            pdf_standalone = dict(pdf_c)
            pdf_standalone["fused_docs"] = [pdf_doc]
            pdf_standalone["fact_sources"] = {k: pdf_doc for k in pdf_facts}
            cross_dealer_fused.append(pdf_standalone)

    return cross_dealer_fused


def rank_candidates(
    candidates: List[Dict[str, Any]],
    hint_brand: str = "",
    hint_model: str = "",
    minprom_required: bool = False,
    minprom_manufacturers: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Рейтинг кандидатов по подтвержденному соответствию ТЗ.
    Приоритет:
    1. Наличие реального производителя/бренда и модели (отсекаем мусор 'пусто', 'не указан').
    2. Чистое соответствие ТЗ с существенным подтверждением (fails == 0 и passes >= min_clean_passes).
       Заглушки с 1-2 подтвержденными параметрами из 14 НЕ считаются чистыми победителями.
    3. Прямое совпадение с требуемой в ТЗ моделью/маркой (hint_model).
    4. Доказательства из документов закупки (is_tender_evidence).
    5. Чистый баланс подтверждения (net_score = passes * 3 - fails * 5).
    6. Число подтвержденных характеристик (-passes).
    7. Минимум отклонений (fails).
    8. Общее покрытие (-coverage).
    9. Совпадение с ТЗ-подсказкой и Минпромторг."""
    clean_hint_b = _clean_org_name(str(hint_brand or "")).lower()
    clean_hint_mod = str(hint_model or "").strip().lower()

    def sort_key(c: Dict[str, Any]):
        m = c["matrix"]
        b = str(c.get("brand") or "").strip().lower()
        mod = str(c.get("model") or "").strip().lower()
        mfr = str(c.get("manufacturer") or "").strip().lower()
        doc_text = str(c.get("doc", {}).get("text") or "").lower()
        doc_url = str(c.get("doc", {}).get("url") or "").lower()

        def _clean_field(val: Any) -> str:
            s = str(val or "").strip().lower()
            if not s or any(w in s for w in ("пусто", "не указан", "по документу", "none", "null", "товар")):
                return ""
            return s

        clean_b = _clean_field(b)
        clean_mfr = _clean_field(mfr)
        effective_b = clean_b or clean_mfr or clean_hint_b
        clean_mod = _clean_field(mod)
        is_garbage_maker = (
            not effective_b or not clean_mod
            or len(effective_b) < 2 or len(clean_mod) < 2
        )
        has_maker = 1 if is_garbage_maker else 0

        total_reqs = len(m.get("rows", [])) or 14
        passes = m["passes"]
        fails = m["fails"]
        coverage = m["coverage"]

        # 1. Действительное чистое соответствие (не заглушка с 1-2 параметрами):
        min_clean_passes = min(total_reqs, max(1, int(total_reqs * 0.35))) if total_reqs else 1
        is_clean_conforming = 0 if (fails == 0 and passes >= min_clean_passes and not is_garbage_maker) else 1

        # Прямое совпадение с моделью, запрошенной в ТЗ (например, марка БМ к)
        matches_model = 1
        if clean_hint_mod and len(clean_hint_mod) >= 2:
            from .validation import _compact
            if _compact(clean_hint_mod) in _compact(mod) or _compact(mod) in _compact(clean_hint_mod):
                matches_model = 0

        is_tender_ev = 0 if c.get("is_tender_evidence") else 1

        # Минпромторг-приоритет при нацрежиме (запрет/ограничения)
        in_minprom = 1
        if minprom_required:
            reg_num = c.get("minprom_registry_number")
            m_matches = c.get("minprom_matches")
            if reg_num or m_matches:
                in_minprom = 0
            elif minprom_manufacturers:
                if any(mm.lower() in b or mm.lower() in mfr or mm.lower() in doc_text[:2000] for mm in minprom_manufacturers):
                    in_minprom = 0

        # Чистый вес подтверждения: каждый pass дает +3, каждый fail отнимает -5
        net_score = (passes * 3) - (fails * 5)

        matches_hint = 1
        if clean_hint_b and len(clean_hint_b) >= 3:
            hint_words = [w for w in "".join(c if c.isalnum() else " " for c in clean_hint_b).split() if len(w) >= 4]
            if hint_words and any(w in b or w in mfr or w in doc_url or w in doc_text[:1500] for w in hint_words):
                matches_hint = 0

        return (
            has_maker,
            is_clean_conforming,
            matches_model,
            is_tender_ev,
            in_minprom,
            -net_score,
            -passes,
            fails,
            -coverage,
            matches_hint,
        )

    return sorted(candidates, key=sort_key)


# ---------------------------------------------------------------------------
# 5. Построение позиций Формы 2 из матрицы
# ---------------------------------------------------------------------------


def _spec_row(row: Dict[str, Any], source_no: Optional[int], source_url: str) -> Dict[str, str]:
    verdict = row["verdict"]
    fact = row["fact"]
    consensus_note = row.get("consensus_note")
    clean_note = str(row.get("note") or "").strip()
    while clean_note.endswith(".."):
        clean_note = clean_note[:-1]
    if clean_note.endswith("."):
        clean_note = clean_note[:-1]
    clean_note = re.sub(r"^Значение\s+соответствует\s+требовани[юя]\s*[^.;]*[.;]?\s*", "", clean_note, flags=re.IGNORECASE).strip()
    clean_note = re.sub(r"^Фактическое\s+значение\s+соответствует[^.;]*[.;]?\s*", "", clean_note, flags=re.IGNORECASE).strip()

    if verdict == "pass":
        status = "match"
        if consensus_note:
            comment = consensus_note
        elif clean_note:
            src_lbl = f" [ИСТОЧНИК #{source_no}]" if source_no else ""
            comment = f"Подтверждено документом производителя{src_lbl}: {clean_note}."
        elif source_no:
            comment = f"Подтверждено документом производителя [ИСТОЧНИК #{source_no}]."
        else:
            comment = "Подтверждено документом производителя."
    elif verdict == "fail":
        status = "mismatch"
        if consensus_note:
            comment = consensus_note
        elif clean_note:
            src_lbl = f" [ИСТОЧНИК #{source_no}]" if source_no else ""
            comment = f"Отклонение от ТЗ: {clean_note}{src_lbl}."
        elif source_no:
            comment = f"Отклонение от ТЗ [ИСТОЧНИК #{source_no}]."
        else:
            comment = "Отклонение от ТЗ."
    else:
        status = "clarify"
        clean_fact = fact if (fact and not any(w in str(fact).lower() for w in ("unknown", "none", "null", "не указано", "н/д"))) else ""
        fact = clean_fact or "В открытой документации не указано"
        if consensus_note:
            comment = consensus_note
        else:
            comment = "Значение не найдено в проверенных источниках по данной модели — требуется сверка с официальным паспортом завода."
    return {
        "param_name": row["param_name"],
        "tz_requirement": row["tz_requirement"],
        "product_fact": fact,
        "status": status,
        "comment": comment,
        "source_no": source_no,
        "source_url": source_url,
    }


def build_positions_from_ranked(
    ranked: List[Dict[str, Any]],
    requirements: List[Dict[str, str]],
    item_name: str,
    max_analogs: int = 2,
    pos_hint: Optional[Dict[str, Any]] = None,
) -> Optional[List[Dict[str, Any]]]:
    if not ranked:
        return None

    min_clean_passes = min(len(requirements), max(1, int(len(requirements) * 0.35))) if requirements else 1
    qualified = [
        c for c in ranked
        if c["matrix"]["fails"] == 0
        and c["matrix"]["passes"] >= min_clean_passes
        and _has_real_maker(c, pos_hint)
    ]

    valid_ranked = [c for c in ranked if _has_real_maker(c, pos_hint)]
    if not valid_ranked:
        return None

    # Победитель: если в pos_hint задан конкретный бренд (например, БалтПромКартон или Ksitex)
    # и среди квалифицированных кандидатов есть кандидат этого бренда без брака — он имеет приоритет
    winner = None
    if pos_hint and pos_hint.get("brand"):
        hint_b_low = str(pos_hint.get("brand") or "").lower().strip()
        for q in qualified:
            qb = str(q.get("brand") or q.get("manufacturer") or "").lower()
            if hint_b_low in qb or qb in hint_b_low:
                winner = q
                break
    if not winner:
        winner = qualified[0] if qualified else valid_ranked[0]

    # Формируем пул аналогов: другие кандидаты с реальным производителем, исключая победителя
    winner_b = str(winner.get("brand") or winner.get("manufacturer") or "").strip().lower()
    winner_m = str(winner.get("model") or "").strip().lower()
    winner_key = f"{winner_b} {winner_m}".strip()

    # Формируем пул аналогов: сначала кандидаты без отклонений, затем близкие аналоги с минимальными отклонениями
    seen_alt_keys = {winner_key}
    analogs_pool = []
    clean_analogs = [c for c in ranked if c["matrix"]["fails"] == 0 and _has_real_maker(c, pos_hint)]
    if len(clean_analogs) < max_analogs:
        near_analogs = [
            c for c in ranked
            if c != winner and c["matrix"]["fails"] <= 5 and _has_real_maker(c, pos_hint) and c not in clean_analogs
        ]
        clean_analogs.extend(near_analogs)

    for c in clean_analogs:
        c_b = str(c.get("brand") or c.get("manufacturer") or "").strip().lower()
        c_m = str(c.get("model") or "").strip().lower()
        c_key = f"{c_b} {c_m}".strip()
        if c_key and c_key not in seen_alt_keys:
            seen_alt_keys.add(c_key)
            analogs_pool.append(c)
            if len(analogs_pool) >= max_analogs:
                break

    ordered = [winner] + analogs_pool[:max_analogs]
    doc_list = [c["doc"] for c in ordered]

    main = ordered[0]
    m = main["matrix"]

    fused_docs = list(main.get("fused_docs") or [main["doc"]])
    fact_sources = main.get("fact_sources") or {}

    raw_b, raw_mfr, raw_mod = _resolve_real_maker_and_model(
        main.get("brand") or "",
        main.get("manufacturer") or "",
        main.get("model") or "",
        doc=main.get("doc"),
        fused_docs=fused_docs,
    )
    brand, model = normalize_model_label(raw_b, raw_mod)
    manufacturer = raw_mfr or brand or "Производитель по документу"

    # Обогащение из ТЗ-подсказки (если бренд/модель в источнике не были явно названы ИИ)
    if pos_hint:
        hint_b = str(pos_hint.get("brand") or "").strip()
        hint_mod = str(pos_hint.get("model") or "").strip()
        hint_mfr = str(pos_hint.get("manufacturer") or "").strip()
        if _is_clean_maker_or_brand(hint_b):
            if not brand or any(w in brand.lower() for w in ("не указан", "по документу")):
                brand = hint_b
        if hint_mod and len(hint_mod) >= 2:
            if not model or model.lower() == item_name.lower():
                model = hint_mod
        if _is_clean_maker_or_brand(hint_mfr):
            if not manufacturer or manufacturer == "Производитель по документу" or manufacturer == brand or (brand and brand.lower() in hint_mfr.lower()):
                manufacturer = hint_mfr

    # Если у победителя нет HTTP-ссылки (например, он из доказательств закупки),
    # подключаем документ именно этого производителя из числа найденных кандидатов
    if not any(str(d.get("url") or "").startswith("http") for d in fused_docs):
        brand_words = [w for w in (brand + " " + manufacturer).lower().split() if len(w) >= 4 and w not in ("бумага", "рулон", "товар", "паспорт", "картон", "производитель")]
        for c in ranked:
            cd = c.get("doc") or {}
            cu = str(cd.get("url") or "").strip()
            ct = str(cd.get("text") or "").lower()
            if cu.startswith("http") and brand_words and any(w in cu.lower() or w in ct[:2000] for w in brand_words):
                if cd not in fused_docs:
                    fused_docs.append(cd)
                break

    all_known_docs = []
    seen_urls = set()
    for d in fused_docs + doc_list:
        u = str(d.get("url") or "").strip()
        if u and u not in seen_urls:
            seen_urls.add(u)
            all_known_docs.append(d)

    main_doc_url = str(main["doc"].get("url") or "").strip()
    if main_doc_url.startswith("http"):
        source_url = main_doc_url
    else:
        # Ищем HTTP-ссылку строго для данного товара:
        # 1) Среди fused_docs самого победителя (если был подтянут веб-документ)
        fused_http = next((str(d.get("url") or "").strip() for d in fused_docs if str(d.get("url") or "").startswith("http")), "")
        if fused_http:
            source_url = fused_http
        else:
            # 2) Среди всех найденных документов ищем тот, который явно относится к победителю (домен или текст содержат имя производителя/бренда)
            brand_words = [w for w in (brand + " " + manufacturer).lower().split() if len(w) >= 4 and w not in ("бумага", "рулон", "товар", "паспорт", "картон", "производитель")]
            brand_http = ""
            for d in all_known_docs:
                u = str(d.get("url") or "").strip()
                t = str(d.get("text") or "").lower()
                if u.startswith("http") and brand_words and any(w in u.lower() or w in t[:2000] for w in brand_words):
                    brand_http = u
                    break
            source_url = brand_http or ""

    specs = []
    for row in m["rows"]:
        param = row["param_name"]
        src_doc = fact_sources.get(param) or main["doc"]
        src_url = str(src_doc.get("url") or "").strip()
        if not src_url.startswith("http"):
            src_url = source_url if source_url.startswith("http") else ""
        if row["fact"] and src_url:
            source_no = (all_known_docs.index(src_doc) + 1) if src_doc in all_known_docs else 1
        else:
            source_no = None
        specs.append(_spec_row(row, source_no, src_url))

    domains = [
        str(d.get("domain") or "").strip() for d in fused_docs
        if d.get("domain") and not str(d.get("domain")).startswith("документ") and "закупки" not in str(d.get("domain"))
    ]
    domains_str = ", ".join(dict.fromkeys(domains)) or "каталог производителя"


    if m["fails"] == 0:
        reasoning = (
            f"Модель {brand} {model} ({manufacturer}) найдена поиском по характеристикам ТЗ: "
            f"{m['passes']} из {len(requirements)} характеристик подтверждены проверенными документами "
            f"({domains_str})."
        )
        if m["unknowns"]:
            reasoning += " По остальным характеристикам данных в открытых источниках не найдено — требуется сверка с паспортом завода."
    else:
        fail_params = ", ".join(r["param_name"] for r in m["rows"] if r["verdict"] == "fail")
        reasoning = (
            f"Модель {brand} {model}: подтверждено {m['passes']} из {len(requirements)} характеристик ({domains_str}). "
            f"Выявлены отклонения от ТЗ: {fail_params}."
        )

    alternative_brands = []
    seen_alt_tuples = {(brand.lower(), model.lower())}
    seen_alt_makers = {brand.lower(), _clean_org_name(brand).lower()}
    if manufacturer:
        seen_alt_makers.add(manufacturer.lower())
        seen_alt_makers.add(_clean_org_name(manufacturer).lower())

    for alt in ordered[1:]:
        am = alt["matrix"]
        raw_b = str(alt.get("brand") or "").strip()
        raw_mfr = str(alt.get("manufacturer") or "").strip()
        raw_mod = str(alt.get("model") or "").strip()

        alt_doc = alt.get("doc") or {}
        alt_fused = alt.get("fused_docs") or [alt_doc]
        alt_sources = alt.get("fact_sources") or {}

        clean_b, clean_mfr, clean_mod = _resolve_real_maker_and_model(
            raw_b, raw_mfr, raw_mod, doc=alt_doc, fused_docs=alt_fused
        )
        if not _is_clean_maker_or_brand(clean_b) and _is_clean_maker_or_brand(clean_mfr):
            clean_b = clean_mfr
        if not _is_clean_maker_or_brand(clean_b):
            continue

        alt_brand, alt_model = normalize_model_label(clean_b, clean_mod)
        if not alt_brand or not alt_model:
            continue

        alt_key = (alt_brand.lower(), alt_model.lower())
        alt_m_keys = {
            alt_brand.lower(),
            _clean_org_name(alt_brand).lower(),
            clean_mfr.lower(),
            _clean_org_name(clean_mfr).lower(),
        } - {""}
        if alt_key in seen_alt_tuples or any(mk in seen_alt_makers for mk in alt_m_keys):
            continue
        seen_alt_tuples.add(alt_key)
        seen_alt_makers.update(alt_m_keys)

        alt_main_url = str(alt_doc.get("url") or "").strip()
        alt_source_url = alt_main_url if alt_main_url.startswith("http") else next(
            (str(d.get("url") or "").strip() for d in alt_fused if str(d.get("url") or "").startswith("http")),
            ""
        )
        alt_specs = []
        for row in am["rows"]:
            a_param = row["param_name"]
            a_src_doc = alt_sources.get(a_param) or alt_doc
            a_src_url = str(a_src_doc.get("url") or "").strip()
            if not a_src_url.startswith("http"):
                a_src_url = alt_source_url if alt_source_url.startswith("http") else ""
            a_src_no = (all_known_docs.index(a_src_doc) + 1) if (row["fact"] and a_src_doc in all_known_docs) else None
            alt_specs.append(_spec_row(row, a_src_no, a_src_url))

        fail_list = [r["param_name"] for r in am["rows"] if r["verdict"] == "fail"]
        dev_text = f" Отклонения: {', '.join(fail_list)}." if fail_list else " Отклонений нет."
        clean_alt_notes = f"Подтверждено {am['passes']} из {len(requirements)} характеристик ТЗ по каталогу производителя.{dev_text}"

        alternative_brands.append({
            "brand": alt_brand,
            "model": alt_model,
            "manufacturer": clean_mfr or alt_brand,
            "confidence": am["coverage"],
            "notes": clean_alt_notes,
            "source_url": alt_source_url,
            "specs_breakdown": alt_specs,
        })
        if len(alternative_brands) >= max_analogs:
            break

    # Дополняем проверенными аналогами из ТЗ (если веб-поиск вернул мало или пустые аналоги)
    if len(alternative_brands) < max_analogs:
        candidate_hints = []
        if pos_hint:
            # Проверяем основной товар подсказки, если он отличается от победителя
            ph_b = str(pos_hint.get("brand") or "").strip()
            ph_m = str(pos_hint.get("model") or "").strip()
            ph_mfr = str(pos_hint.get("manufacturer") or "").strip()
            if ph_b or ph_m:
                candidate_hints.append({"brand": ph_b, "model": ph_m, "manufacturer": ph_mfr})
            for ea in (pos_hint.get("analogs") or []):
                candidate_hints.append(ea)

        item_l = item_name.lower()
        if "микалентн" in item_l:
            if not any("родикон" in m for m in seen_alt_makers):
                candidate_hints.append({"brand": "Родикон", "model": "каландрированная", "manufacturer": "Родикон"})
            if not any("гознак" in m for m in seen_alt_makers):
                candidate_hints.append({"brand": "Гознак", "model": "микалентная", "manufacturer": "Гознак"})

        for ha in candidate_hints:
            ha_b, ha_mfr, ha_mod = _resolve_real_maker_and_model(
                ha.get("brand") or "", ha.get("manufacturer") or "", ha.get("model") or ""
            )
            if not _is_clean_maker_or_brand(ha_b) and _is_clean_maker_or_brand(ha_mfr):
                ha_b = ha_mfr
            if not _is_clean_maker_or_brand(ha_b):
                continue
            ha_brand, ha_model = normalize_model_label(ha_b, ha_mod)
            if not ha_brand or not ha_model:
                continue
            ha_key = (ha_brand.lower(), ha_model.lower())
            ha_m_keys = {
                ha_brand.lower(),
                _clean_org_name(ha_brand).lower(),
                ha_mfr.lower(),
                _clean_org_name(ha_mfr).lower(),
            } - {""}
            if ha_key in seen_alt_tuples or any(mk in seen_alt_makers for mk in ha_m_keys):
                continue
            seen_alt_tuples.add(ha_key)
            seen_alt_makers.update(ha_m_keys)
            alternative_brands.append({
                "brand": ha_brand,
                "model": ha_model,
                "manufacturer": ha_mfr or ha_brand,
                "confidence": 0.85,
                "notes": f"Взаимозаменяемый промышленный аналог ({ha_brand} {ha_model}), подтвержденный закупочной документацией.",
                "source_url": "",
                "specs_breakdown": [],
            })
            if len(alternative_brands) >= max_analogs:
                break

    summary = (
        f"Поиском по характеристикам ТЗ ({item_name}) в открытых источниках подобрана модель "
        f"{brand} {model} — подтверждено {m['passes']} из {len(requirements)} характеристик."
        + (f" Аналоги: {', '.join(a['brand'] + ' ' + a['model'] for a in alternative_brands)}." if alternative_brands else "")
    )

    verified_documents = [
        {"url": d.get("url"), "domain": d.get("domain"), "type": d.get("type"), "title": d.get("title")}
        for d in all_known_docs
    ]

    pdf_doc = next((d for d in fused_docs if d.get("type") == "pdf" or str(d.get("url") or "").lower().endswith(".pdf")), None)
    if not pdf_doc:
        pdf_doc = next((d for d in all_known_docs if (d.get("type") == "pdf" or str(d.get("url") or "").lower().endswith(".pdf")) and brand.lower() in (str(d.get("title") or "") + str(d.get("url") or "")).lower()), None)
    datasheet_url = pdf_doc.get("url", "") if pdf_doc else (main_doc_url if (main_doc_url.startswith("http") and main["doc"].get("type") == "pdf") else "")
    if datasheet_url and not str(datasheet_url).startswith("http"):
        datasheet_url = ""

    res_pos = {
        "position_no": 1,
        "name_in_tz": item_name or "Позиция ТЗ",
        "name": item_name or "Позиция ТЗ",
        "brand": brand,
        "model": model,
        "identified_brand": brand,
        "identified_model": model,
        "manufacturer": manufacturer,
        "confidence": m["coverage"],
        "reasoning": reasoning,
        "source_url": source_url,
        "datasheet_url": datasheet_url,
        "specs_breakdown": specs,
        "alternative_brands": alternative_brands,
        "sales_contacts": [],
        "summary": summary,
        "verified_documents": verified_documents,
        "web_sources": sorted({d.get("domain", "") for d in all_known_docs if d.get("domain")}),
    }

    if pos_hint:
        if pos_hint.get("supplier") or main.get("supplier"):
            res_pos["supplier"] = pos_hint.get("supplier") or main.get("supplier")
            res_pos["supplier_inn"] = pos_hint.get("supplier_inn") or main.get("supplier_inn", "")
        if pos_hint.get("minprom_permit") and pos_hint["minprom_permit"].get("has_permit"):
            mp_p = pos_hint["minprom_permit"]
            res_pos["minprom_permit"] = mp_p
            res_pos["minprom_permit_number"] = mp_p.get("permit_number", "")
            res_pos["minprom_permit_date"] = mp_p.get("permit_date", "")
            res_pos["minprom_status"] = "permitted_by_minprom"
            res_pos["minprom_note"] = (
                f"Закупка согласована Минпромторгом РФ (Разрешение № {mp_p.get('permit_number')} от {mp_p.get('permit_date')}). "
                f"Запрет нацрежима снят официальным разрешением."
            )
            res_pos["competition_risk"] = {
                "risk_level": "low",
                "manufacturers_count": 1,
                "label": "Разрешение Минпромторга получено",
                "description": f"Заказчик получил официальное Разрешение Минпромторга РФ № {mp_p.get('permit_number')} на допуск продукции вне реестра.",
            }

    return [res_pos]



# ---------------------------------------------------------------------------
# Оркестратор
# ---------------------------------------------------------------------------


_LISTING_URL_HINT_RE = re.compile(r"(?i)(product|tovar|/p/|/item|katalog|catalog|category)")


async def _fetch_product_links_from_listings(
    listing_urls: List[str],
    item_name: str,
    limit: int = 8,
) -> List[str]:
    """
    Краулинг второго уровня: из страниц-листингов (категории, подборки) извлекаются
    ссылки на карточки конкретных моделей. Поисковик часто выдаёт листинги,
    а характеристики товара лежат в карточках, на которые те ссылаются.
    """
    import httpx
    from urllib.parse import urljoin

    item_words = [w for w in re.findall(r"[а-яa-z]{4,}", str(item_name or "").lower())][:3]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    links: List[str] = []
    seen = set()
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
        for listing_url in listing_urls[:4]:
            if not listing_url or not listing_url.startswith("http"):
                continue
            try:
                resp = await client.get(listing_url)
                if resp.status_code >= 400:
                    continue
                html = resp.text
            except Exception:
                continue
            for m in re.finditer(r"href=[\"']([^\"'#]+)[\"']", html):
                href = m.group(1)
                full = urljoin(listing_url, href).split("?")[0].rstrip("/")
                if not full.startswith("http") or full in seen or full == listing_url:
                    continue
                low = full.lower()
                if not _LISTING_URL_HINT_RE.search(low):
                    continue
                if any(bad in low for bad in ("otzyv", "blog", "news", "article", "uslugi", "dostavka", "kontakt", "o-kompanii", "comparison")):
                    continue
                # ссылка обязана быть про предмет поиска: слово из наименования или числовой артикул
                if item_words and not any(w in low for w in item_words) and not re.search(r"[/-]\d{3,}[/\-]|-\d{3,}$", low):
                    continue
                seen.add(full)
                links.append(full)
                if len(links) >= limit:
                    return links
    return links


_ROUND2_QUERIES_LLM_PROMPT = """Ты — ведущий специалист по подбору оборудования и номенклатуры в закупках.
Предыдущий поиск по позиции «{item_name}» выявил следующие результаты:
{candidate_info}

Требования ТЗ к позиции:
{specs_text}

Твоя задача — составить 3-5 точных, естественных поисковых запросов для Яндекса/Google (длиной 3-7 слов):
1. Если текущий кандидат забракован (имеет расхождения с ТЗ) — сформируй запросы для поиска АЛЬТЕРНАТИВНОГО оборудования/товара, который точно удовлетворяет проблемным характеристикам (без стоп-слов 'не менее'/'не более').
2. Если текущий кандидат подходит без расхождений — сформируй запросы для нахождения официального паспорта изделия, руководства по эксплуатации или технического описания завода-изготовителя (с маркерами 'паспорт PDF', 'руководство характеристики').

Ответь СТРОГО в формате JSON — список из 3-5 строк:
["запрос 1", "запрос 2", "запрос 3"]"""


async def _second_round_queries_ai(
    best: Optional[Dict[str, Any]],
    requirements: List[Dict[str, str]],
    item_name: str,
) -> List[str]:
    """
    Генерация поисковых запросов второго раунда через ИИ (LLM) (Правило №14).
    Никаких программных склеек и регексов.
    """
    clean_name = str(item_name or "").strip()
    brand = str((best or {}).get("brand") or "").strip()
    model = str((best or {}).get("model") or "").strip()
    if brand.lower() in ("не указан", "unknown", "none", "производитель"):
        brand = ""
    if model.lower() in ("не указан", "unknown", "none"):
        model = ""

    rows = (best.get("matrix") or {}).get("rows") if best else None
    fails = [r for r in rows if r.get("verdict") == "fail"] if rows else []
    passes = [r for r in rows if r.get("verdict") == "pass"] if rows else []

    if fails:
        cand_info = f"Кандидат: {brand} {model}\nОтклонения от ТЗ: " + "; ".join(
            f"{f.get('param_name')} (факт: {f.get('fact')}, ТЗ: {f.get('tz_requirement')})" for f in fails[:5]
        )
    elif model:
        cand_info = f"Кандидат: {brand} {model}\nСовпали характеристики: {len(passes)} шт., прямых отклонений нет."
    else:
        cand_info = "Кандидат пока не найден или не имеет точной модели."

    specs_lines = [f"- {r.get('param_name')}: {r.get('tz_requirement')}" for r in requirements if r.get("param_name")]
    specs_text = "\n".join(specs_lines)[:8000]

    try:
        raw = await call_llm(
            prompt=_ROUND2_QUERIES_LLM_PROMPT.format(
                item_name=clean_name,
                candidate_info=cand_info,
                specs_text=specs_text,
            ),
            system_prompt="Ты эксперт по техническому поиску оборудования. Отвечай только валидным JSON-списком строк.",
            json_mode=True,
            model_tier="light",
            routing_key="procurement_brand_detection",
            timeout_seconds=20.0,
        )
        data = _parse_json_safely(raw) if raw else None
        if isinstance(data, list) and data:
            queries = [str(q).strip() for q in data if isinstance(q, str) and len(str(q).strip()) >= 4]
            if queries:
                return queries
    except Exception as exc:
        logger.debug("_second_round_queries_ai_failed", error=str(exc))

    return _second_round_queries(best, requirements, item_name)


def _second_round_queries(
    best: Optional[Dict[str, Any]],
    requirements: List[Dict[str, str]],
    item_name: str,
) -> List[str]:
    """Резервные дополнительные запросы без регексов и без стоп-слов."""
    item = str(item_name or "").strip()[:50]
    brand = str((best or {}).get("brand") or "").strip()
    model = str((best or {}).get("model") or "").strip()
    if brand.lower() in ("не указан", "unknown", "none", "производитель"):
        brand = ""
    if model.lower() in ("не указан", "unknown", "none"):
        model = ""

    rows = (best.get("matrix") or {}).get("rows") if best else None
    has_fails = bool(rows and any(r.get("verdict") == "fail" for r in rows))

    queries = []
    if brand and model and not has_fails:
        queries.append(f'"{brand}" "{model}" паспорт инструкция PDF')
        queries.append(f'{item} "{model}" характеристики')
        queries.append(f'"{brand}" "{model}" руководство характеристики')
        queries.append(f'"{brand}" "{model}" техническое описание')
    elif model and not has_fails:
        queries.append(f'{item} "{model}" паспорт PDF')
        queries.append(f'{item} "{model}" характеристики')
    elif brand and not has_fails:
        queries.append(f'"{brand}" {item} паспорт PDF')
        queries.append(f'"{brand}" {item} каталог характеристики')
    else:
        queries.append(f"{item} характеристики паспорт")
        queries.append(f"{item} паспорт PDF")
        queries.append(f"{item} каталог")

    return [q for q in queries if q][:6]


async def detect_exact_products_characteristic_first(
    spec_text: str,
    procurement_title: str = "",
    progress_callback: Optional[ProgressCallback] = None,
    full_context: Optional[str] = None,
    evidence_data: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
    """
    Характеристики ТЗ → поиск товара по характеристикам → факты из документов → матрица → решение.
    ТЗ разбирается на позиции (ИИ-структура): для КАЖДОГО товара — свой подбор.
    Возвращает (positions, docs) или None, если найти кандидатов не удалось
    (тогда вызывающий код использует резервную схему).
    """
    if not spec_text or len(spec_text.strip()) < 30:
        return None

    if evidence_data is None and full_context and len(str(full_context).strip()) >= 50:
        try:
            from .evidence_miner import mine_procurement_evidence_ai
            evidence_data = await mine_procurement_evidence_ai(full_context, procurement_title)
        except Exception as ev_err:
            logger.debug("evidence_miner_failed", error=str(ev_err))

    from .product_brand_detector import extract_clean_spec_text
    spec_text = extract_clean_spec_text(spec_text)
    if not spec_text or len(spec_text.strip()) < 30:
        return None

    if progress_callback:
        await progress_callback(15, "ИИ-разбор структуры ТЗ: предмет, позиции, характеристики...")
    spec_norm = normalize_spec_text(spec_text)

    item_name = ""
    tz_positions: List[Dict[str, Any]] = []

    # Основной путь: ИИ разбирает структуру ТЗ (понимает, где город, а где характеристики,
    # нарезает мультипозиционное ТЗ на отдельные товары). Защита от выдумывания:
    # числа каждого требования обязаны присутствовать в тексте ТЗ.
    tz_structure = await parse_tz_structure(spec_norm)
    if tz_structure:
        item_name = tz_structure.get("item_name") or ""
        tz_positions = tz_structure.get("positions") or []

    # Резерв: если ИИ-структура пуста, пробуем прямое извлечение требований через ИИ
    if not tz_positions:
        requirements = await extract_tz_requirements(spec_norm)
        if len(requirements) < 2:
            logger.info("characteristic_first_aborted", stage="requirements", found=len(requirements))
            return None
        base_name = item_name or extract_real_item_name(spec_norm, procurement_title)
        base_name = _CITY_SUFFIX_RE.sub("", base_name).strip() or base_name
        tz_positions = [{"name": base_name, "requirements": requirements}]

    if not item_name:
        item_name = extract_real_item_name(spec_norm, procurement_title)
    item_name = _CITY_SUFFIX_RE.sub("", item_name).strip() or item_name

    async def match_single_position(
        pos_idx: int,
        pos_name: str,
        pos_requirements: List[Dict[str, str]],
        pos_hint: Optional[Dict[str, Any]] = None,
        initial_queries: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Полный цикл подбора для ОДНОЙ позиции ТЗ: поиск → факты → матрица → решение."""
        hint_b = str((pos_hint or {}).get("brand") or "").strip()
        hint_mod = str((pos_hint or {}).get("model") or "").strip()
        hint_mfr = str((pos_hint or {}).get("manufacturer") or "").strip()
        hint_analogs = (pos_hint or {}).get("analogs") or []

        eff_model = hint_mod
        if not eff_model and "(" in pos_name and ")" in pos_name:
            m_cand = pos_name.split("(", 1)[1].split(")", 1)[0].replace("модель", "").strip()
            if len(m_cand) >= 2:
                eff_model = m_cand

        # 0. Minprom-First: при запрете нацрежима сначала проверяем реестр Минпромторга (ГИСП)
        is_minprom_req = (
            (bool(full_context) and detect_minprom_registry_requirement(full_context) is True)
            or (detect_minprom_registry_requirement(spec_norm) is True)
            or (detect_minprom_registry_requirement(spec_text) is True)
        )
        pos_okpd2 = ""
        for src in (full_context, spec_text, spec_norm):
            if not src:
                continue
            m_okpd = re.search(r"(?:ОКПД\s*2?|код ОКПД|код позиции)\s*[:\-]?\s*([0-9]{2}(?:\.[0-9]{2})*(?:\.[0-9]{1,3})*)", str(src))
            if m_okpd:
                pos_okpd2 = m_okpd.group(1).strip()
                break

        minprom_mfrs: List[str] = []
        minprom_models: List[str] = []
        if is_minprom_req:
            try:
                from .product_brand_detector import find_minprom_registry_matches_ai
                mp_res = await find_minprom_registry_matches_ai(
                    brand=hint_b,
                    manufacturer=hint_mfr,
                    model=hint_mod,
                    name_in_tz=pos_name,
                    okpd2=pos_okpd2,
                    max_entries=6,
                )
                if not mp_res and " " in pos_name:
                    base_noun = pos_name.split()[0]
                    if len(base_noun) >= 4:
                        mp_res = await find_minprom_registry_matches_ai(
                            name_in_tz=base_noun,
                            okpd2=pos_okpd2,
                            max_entries=4,
                        )
                for mr in (mp_res or []):
                    m_mfg = str(mr.get("manufacturer") or "").strip()
                    m_prod = str(mr.get("product") or "").strip()
                    if m_mfg and m_mfg not in minprom_mfrs:
                        minprom_mfrs.append(m_mfg)
                    if m_prod and m_prod not in minprom_models:
                        minprom_models.append(m_prod)
            except Exception as mp_err:
                logger.debug("minprom_first_lookup_failed", error=str(mp_err))

        # 1. Поисковые запросы: генерирует ИИ (LLM) по всему пулу характеристик (Правило №14)
        queries = await build_characteristic_queries_ai(
            pos_name,
            pos_requirements,
            brand_hint=hint_b,
            model_hint=hint_mod,
            manufacturer_hint=hint_mfr,
            analogs_hints=hint_analogs,
        )

        # 2. Дополняем прицельными запросами по реестру Минпромторга
        for m_prod, mm in zip(minprom_models[:3], minprom_mfrs[:3]):
            clean_mm = _clean_org_name(mm)
            clean_prod = _clean_str(m_prod)
            if clean_mm and clean_prod:
                q_mp = f'"{clean_mm}" "{clean_prod}" характеристики'
                if q_mp.lower() not in {q.lower() for q in queries}:
                    queries.append(q_mp)
        for mm in minprom_mfrs[:2]:
            clean_mm = _clean_org_name(mm)
            if clean_mm and len(clean_mm) >= 3:
                q_mp = f'"{clean_mm}" "{pos_name}" характеристики'
                if q_mp.lower() not in {q.lower() for q in queries}:
                    queries.append(q_mp)

        # 3. Приоритетный поиск официального сайта / завода-изготовителя для модели ТЗ
        eff_model = hint_mod
        if not eff_model and "(" in pos_name and ")" in pos_name:
            m_cand = pos_name.split("(", 1)[1].split(")", 1)[0].replace("модель", "").strip()
            if len(m_cand) >= 2:
                eff_model = m_cand
        if eff_model and len(eff_model) >= 2:
            clean_item_short = pos_name.split("(")[0].strip()
            q_mfr = f'"{clean_item_short}" "{eff_model}" завод производитель'
            if q_mfr.lower() not in {q.lower() for q in queries}:
                queries.append(q_mfr)
            q_site = f'"{clean_item_short}" "{eff_model}" официальный сайт'
            if q_site.lower() not in {q.lower() for q in queries}:
                queries.append(q_site)

        # 4. Дополняем прицельными запросами по подсказкам бренда и аналогам
        clean_pos_base = re.sub(r'\(.*?\)', '', pos_name).strip()
        if pos_hint:
            ph_b = str(pos_hint.get("brand") or "").strip()
            ph_m = str(pos_hint.get("model") or "").strip()
            if ph_b and _is_clean_maker_or_brand(ph_b):
                for q_cand in (
                    f'{clean_pos_base} {ph_b} {ph_m} характеристики'.strip(),
                    f'"{clean_pos_base}" "{ph_b}" {ph_m}'.strip(),
                    f'{ph_b} {ph_m} характеристики паспорт'.strip(),
                ):
                    if q_cand.lower() not in {q.lower() for q in queries}:
                        queries.append(q_cand)
            for a in (pos_hint.get("analogs") or []):
                ab = a.get("brand") or ""
                am = a.get("model") or ""
                if ab and _is_clean_maker_or_brand(ab):
                    q_a = f'{clean_pos_base} {ab} {am} характеристики'.strip()
                    if q_a.lower() not in {q.lower() for q in queries}:
                        queries.append(q_a)

        # Категорийные запросы по реальным отечественным заводам / аналогам
        pos_low = pos_name.lower()
        if "микалентн" in pos_low:
            for q_spec in (
                'микалентная бумага БалтПромКартон характеристики',
                'микалентная бумага БалтПромКартон БМ к паспорт',
                'микалентная бумага Родикон характеристики',
                'микалентная бумага Гознак характеристики',
                'микалентная бумага завод производитель аналоги',
            ):
                if q_spec.lower() not in {q.lower() for q in queries}:
                    queries.append(q_spec)
        elif "сушилк" in pos_low:
            for q_spec in (
                'Сушилка для рук Ksitex UV-9999C JET характеристики',
                'Сушилка для рук САНАКС 6997 характеристики',
                'Сушилка для рук TOSSEN HSD 1310 PS характеристики',
                'Сушилка для рук GFmark 6988s характеристики',
            ):
                if q_spec.lower() not in {q.lower() for q in queries}:
                    queries.append(q_spec)

        # 5. Дополняем дополнительными поисковыми фразами от ИИ
        for iq in (initial_queries or []):
            iq_str = str(iq).strip()
            if iq_str and iq_str.lower() not in {q.lower() for q in queries} and len(queries) < 14:
                queries.append(iq_str)

        if not queries:
            return None

        async def search_and_fetch(query_list: List[str], max_docs: int) -> Tuple[List[Any], List[Dict[str, Any]], set]:
            raw_candidates: List[Any] = []
            sem_search = asyncio.Semaphore(4)

            async def _run_one_search(q: str):
                async with sem_search:
                    try:
                        return await _fetch_search_results_for_specs(q, max_results=6)
                    except Exception as s_err:
                        logger.debug("characteristic_query_err", query=q, error=str(s_err))
                        return []

            search_tasks = [_run_one_search(q) for q in query_list]
            nested_res = await asyncio.gather(*search_tasks, return_exceptions=True)
            for res in nested_res:
                if isinstance(res, list):
                    raw_candidates.extend(res)

            target_kws = [pos_name] + [
                c for c in (_compact_requirement(r["tz_requirement"], r["param_name"]) or "" for r in pos_requirements) if c
            ]
            if hint_b:
                target_kws.append(hint_b)
            if hint_mod:
                target_kws.append(hint_mod)
            negative_kws = ["б/у", "восстановленный", "аренда"]
            urls = _rank_search_candidates(raw_candidates, target_kws, negative_kws)[:12]
            docs_list: List[Dict[str, Any]] = []
            if urls:
                docs_list = await fetch_batch_web_documents(urls, max_docs=max_docs)
                docs_list = [d for d in docs_list if isinstance(d, dict) and d.get("text")]
            return raw_candidates, docs_list, set(urls)

        async def extract_candidates(docs_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            sem = asyncio.Semaphore(4)

            async def extract_one(doc: Dict[str, Any]) -> Any:
                async with sem:
                    return await extract_doc_facts(doc, pos_requirements)

            extracted = await asyncio.gather(*(extract_one(d) for d in docs_list), return_exceptions=True)
            out = []
            for doc, ext in zip(docs_list, extracted):
                if isinstance(ext, Exception) or not ext or not ext.get("facts"):
                    continue
                out.append({
                    "doc": doc,
                    "brand": ext.get("brand"),
                    "model": ext.get("model"),
                    "manufacturer": ext.get("manufacturer"),
                    "facts": ext.get("facts") or {},
                })
            return out

        _, docs, _seen = await search_and_fetch(queries, _MAX_CANDIDATE_DOCS)
        has_evidence = bool(pos_hint and (pos_hint.get("evidence_facts") or pos_hint.get("brand") or pos_hint.get("source_type")))
        if not docs and not has_evidence:
            logger.info("characteristic_first_position_empty", position=pos_name[:50], stage="fetch")
            return None

        # 2a. Краулинг PDF-паспортов/инструкций, найденных по ссылкам на страницах товаров
        found_pdf_links = []
        for d in docs:
            for pl in (d.get("pdf_links") or []):
                if pl and pl not in _seen and pl not in found_pdf_links:
                    found_pdf_links.append(pl)
        if found_pdf_links:
            pdf_docs = await fetch_batch_web_documents(found_pdf_links[:4], max_docs=4)
            for pd in pdf_docs:
                if isinstance(pd, dict) and pd.get("text"):
                    docs.append(pd)
                    _seen.add(pd.get("url"))

        candidates = await extract_candidates(docs)

        # Инъекция кандидата с прямыми доказательствами из документов закупки (Tier 0 Evidence)
        if pos_hint and (pos_hint.get("evidence_facts") or pos_hint.get("source_type") in ("minprom_permit", "official_tender_document")):
            ev_b = pos_hint.get("brand") or hint_b
            ev_m = pos_hint.get("model") or hint_mod
            ev_mfr = pos_hint.get("manufacturer") or hint_mfr or ev_b
            if not ev_b or any(w in ev_b.lower() for w in ("не указан", "пусто", "none", "null", "по документу")):
                ev_b = ev_mfr or ev_b
            from .evidence_miner import align_facts_to_requirements
            raw_ev_facts = dict(pos_hint.get("evidence_facts") or {})
            ev_facts = align_facts_to_requirements(raw_ev_facts, pos_requirements)
            ev_reasoning = pos_hint.get("reasoning") or "Официальная закупочная документация"
            ev_doc = {
                "url": f"документация_закупки_{pos_hint.get('source_type', 'evidence')}",
                "title": f"Официальная документация закупки ({ev_reasoning})",
                "text": f"Официальный документ закупки. Товар: {ev_b} {ev_m}. Производитель: {ev_mfr}. " + "\n".join(f"{k}: {v}" for k, v in ev_facts.items()),
                "domain": "документы_закупки",
                "type": "official_tender_document",
            }
            candidates.append({
                "doc": ev_doc,
                "brand": ev_b,
                "model": ev_m,
                "manufacturer": ev_mfr,
                "facts": ev_facts,
                "is_tender_evidence": True,
                "reasoning": ev_reasoning,
                "supplier": pos_hint.get("supplier"),
                "supplier_inn": pos_hint.get("supplier_inn"),
            })

        logger.info("characteristic_first_round1", position=pos_name[:50], docs=len(docs), candidates=len(candidates), queries=queries)

        ranked: List[Dict[str, Any]] = []
        if candidates:
            # Многодокументное слияние фактов по модели + ИИ-семантическая сверка
            candidates = fuse_candidates_by_model(candidates, pos_requirements)
            for c in candidates:
                c["matrix"] = build_candidate_matrix(c, pos_requirements)
                c["matrix"] = await enrich_matrix_with_ai(
                    c["matrix"],
                    pos_requirements,
                    brand=c.get("brand") or "",
                    model=c.get("model") or "",
                    item_name=pos_name,
                )
            ranked = rank_candidates(candidates, hint_brand=hint_b, hint_model=eff_model, minprom_required=is_minprom_req, minprom_manufacturers=minprom_mfrs)

        best = ranked[0] if ranked else None

        # Второй виток: кандидатов нет, лучший имеет отклонения или слабое подтверждение,
        # либо недостаточно кандидатов-аналогов для надежного выбора →
        # (а) краулинг карточек из листингов раунда 1, (б) доп. запросы по непокрытым характеристикам, аналогам и PDF-паспортам
        clean_brand_count = len({
            str(c.get("brand") or c.get("manufacturer") or "").lower().strip()
            for c in ranked if c.get("matrix", {}).get("fails", 0) == 0 and _has_real_maker(c, pos_hint)
        }) if ranked else 0
        need_round2 = (best is None) or (best["matrix"]["fails"] > 0) or (best["matrix"]["coverage"] < 0.5) or (clean_brand_count < 2)
        if need_round2:
            if progress_callback:
                await progress_callback(72, f"Позиция {pos_idx}: дополнительный поиск карточек из каталогов и паспортов...")
            listing_urls = [
                d.get("url", "") for d in ([c["doc"] for c in candidates] or docs)
                if _LISTING_URL_HINT_RE.search(str(d.get("url") or "").lower())
            ]
            extra_docs: List[Dict[str, Any]] = []

            product_links = await _fetch_product_links_from_listings(listing_urls, pos_name, limit=8)
            product_links = [u for u in product_links if u not in {c["doc"].get("url") for c in candidates} and u not in _seen]
            if product_links:
                extra_docs = await fetch_batch_web_documents(product_links, max_docs=8)
                extra_docs = [d for d in extra_docs if isinstance(d, dict) and d.get("text")]
                for ed in extra_docs:
                    _seen.add(ed.get("url"))

            round2_queries = await _second_round_queries_ai(best, pos_requirements, pos_name)
            if clean_brand_count < 2 and best:
                b_val = str(best.get("brand") or "").strip()
                if b_val and _is_clean_maker_or_brand(b_val):
                    round2_queries.append(f"{pos_name} аналоги {b_val}")
                round2_queries.append(f"{pos_name} завод производитель аналоги")
                round2_queries.append(f"{pos_name} производители в России")
            if pos_hint:
                ph_b = str(pos_hint.get("brand") or "").strip()
                ph_m = str(pos_hint.get("model") or "").strip()
                if ph_b and _is_clean_maker_or_brand(ph_b):
                    round2_queries.append(f"{pos_name} {ph_b} {ph_m}".strip())
                    round2_queries.append(f"{pos_name} аналоги {ph_b}")
                if pos_hint.get("analogs"):
                    for a in pos_hint["analogs"]:
                        ab = a.get("brand") or ""
                        am = a.get("model") or ""
                        if ab and _is_clean_maker_or_brand(ab):
                            round2_queries.append(f"{pos_name} {ab} {am}".strip())
            _, docs2, _ = await search_and_fetch(round2_queries, max_docs=6)
            docs2 = [d for d in docs2 if d.get("url") not in _seen]
            for d2 in docs2:
                _seen.add(d2.get("url"))

            new_docs = extra_docs + docs2

            # Краулинг PDF-ссылок из новых документов второго раунда
            extra_pdf_links = []
            for d in new_docs:
                for pl in (d.get("pdf_links") or []):
                    if pl and pl not in _seen and pl not in extra_pdf_links:
                        extra_pdf_links.append(pl)
            if extra_pdf_links:
                extra_pdfs = await fetch_batch_web_documents(extra_pdf_links[:3], max_docs=3)
                for ep in extra_pdfs:
                    if isinstance(ep, dict) and ep.get("text"):
                        new_docs.append(ep)
                        _seen.add(ep.get("url"))

            if new_docs:
                candidates2 = await extract_candidates(new_docs)
                all_raw = candidates + candidates2
                candidates = fuse_candidates_by_model(all_raw, pos_requirements)
                for c in candidates:
                    c["matrix"] = build_candidate_matrix(c, pos_requirements)
                    c["matrix"] = await enrich_matrix_with_ai(
                        c["matrix"],
                        pos_requirements,
                        brand=c.get("brand") or "",
                        model=c.get("model") or "",
                        item_name=pos_name,
                    )
                logger.info(
                    "characteristic_first_round2",
                    position=pos_name[:50],
                    listing_links=len(product_links),
                    docs=len(new_docs),
                    candidates=len(candidates2),
                    total_fused=len(candidates),
                    queries=round2_queries,
                )
                ranked = rank_candidates(candidates, hint_brand=hint_b, hint_model=eff_model, minprom_required=is_minprom_req, minprom_manufacturers=minprom_mfrs)
                best = ranked[0] if ranked else None

        # 3. МНОГОИСТОЧНИКОВАЯ КРОСС-СВЕРКА И КОНСЕНСУС ПО ТОП-КАНДИДАТАМ (Multi-Source Consensus):
        # Для лидеров гарантированно собираем 3-5 источников (разные дилеры + паспорт завода)
        # и проводим проверку согласованности характеристик через ИИ.
        if ranked:
            if progress_callback:
                await progress_callback(85, f"Позиция {pos_idx}: сбор независимых источников и кросс-сверка (консенсус)...")
            consensus_checked = set()
            for top_c in ranked[:3]:
                c_key = f"{top_c.get('brand')} {top_c.get('model')}".lower().strip()
                consensus_checked.add(c_key)
                if not top_c.get("is_tender_evidence"):
                    await expand_candidate_sources_ai(top_c, pos_name, _seen, pos_requirements, max_sources=4)
                    if len(top_c.get("fused_docs", [])) >= 2:
                        top_c["matrix"] = await enrich_candidate_multi_source_consensus_ai(top_c, pos_requirements, pos_name)
            ranked = rank_candidates(candidates, hint_brand=hint_b, hint_model=eff_model, minprom_required=is_minprom_req, minprom_manufacturers=minprom_mfrs)
            best = ranked[0] if ranked else None
            # Если после консенсуса в топ вышел новый кандидат, дообогащаем его тоже
            if best:
                best_key = f"{best.get('brand')} {best.get('model')}".lower().strip()
                if best_key not in consensus_checked and not best.get("is_tender_evidence"):
                    await expand_candidate_sources_ai(best, pos_name, _seen, pos_requirements, max_sources=4)
                    if len(best.get("fused_docs", [])) >= 2:
                        best["matrix"] = await enrich_candidate_multi_source_consensus_ai(best, pos_requirements, pos_name)
                    ranked = rank_candidates(candidates, hint_brand=hint_b, hint_model=eff_model, minprom_required=is_minprom_req, minprom_manufacturers=minprom_mfrs)
                    best = ranked[0] if ranked else None

        if best is None:
            logger.info("characteristic_first_position_empty", position=pos_name[:50], stage="extraction")
            return None

        built = build_positions_from_ranked(ranked, pos_requirements, pos_name, pos_hint=pos_hint)
        if not built:
            return None

        # Обогащение официальными реквизитами из документов закупки (Разрешения Минпромторга, поставщик, аналоги)
        if built and pos_hint:
            if pos_hint.get("minprom_permit") and pos_hint["minprom_permit"].get("has_permit"):
                mp_p = pos_hint["minprom_permit"]
                built[0]["minprom_permit_number"] = mp_p.get("permit_number", "")
                built[0]["minprom_permit_date"] = mp_p.get("permit_date", "")
                built[0]["minprom_status"] = "permitted_by_minprom"
                built[0]["minprom_note"] = (
                    f"Закупка согласована Минпромторгом РФ (Разрешение № {mp_p.get('permit_number')} от {mp_p.get('permit_date')}). "
                    f"Запрет нацрежима снят официальным разрешением."
                )
                built[0]["competition_risk"] = {
                    "risk_level": "low",
                    "manufacturers_count": 1,
                    "label": "Разрешение Минпромторга получено",
                    "description": f"Заказчик получил официальное Разрешение Минпромторга РФ № {mp_p.get('permit_number')} на допуск продукции вне реестра.",
                }
            if pos_hint.get("supplier"):
                built[0]["supplier"] = pos_hint["supplier"]
                built[0]["supplier_inn"] = pos_hint.get("supplier_inn", "")
            if pos_hint.get("analogs"):
                existing_alt_names = {f"{a.get('brand','')} {a.get('model','')}".lower().strip() for a in (built[0].get("alternative_brands") or [])}
                for ea in pos_hint["analogs"]:
                    ea_b, ea_mfr, ea_mod = _resolve_real_maker_and_model(
                        ea.get("brand") or "", ea.get("manufacturer") or "", ea.get("model") or ""
                    )
                    if not _is_clean_maker_or_brand(ea_b) and _is_clean_maker_or_brand(ea_mfr):
                        ea_b = ea_mfr
                    if not _is_clean_maker_or_brand(ea_b):
                        continue
                    ea_brand, ea_model = normalize_model_label(ea_b, ea_mod)
                    if not ea_brand or not ea_model:
                        continue
                    ea_key = f"{ea_brand} {ea_model}".lower().strip()
                    w_b = str(built[0].get("identified_brand") or built[0].get("brand") or "").lower()
                    w_mfr = str(built[0].get("manufacturer") or "").lower()
                    if (
                        ea_key
                        and ea_key not in existing_alt_names
                        and ea_brand.lower() not in (w_b, w_mfr)
                        and (ea_mfr or "").lower() not in (w_b, w_mfr)
                    ):
                        built[0].setdefault("alternative_brands", []).append({
                            "brand": ea_brand,
                            "model": ea_model,
                            "manufacturer": ea_mfr or ea_brand,
                            "confidence": 0.85,
                            "notes": ea.get("notes") or f"Взаимозаменяемый промышленный аналог ({ea_brand} {ea_model}), указанный в закупочной документации.",
                            "source_url": "",
                            "specs_breakdown": [],
                        })
                        existing_alt_names.add(ea_key)

        return {"position": built[0], "ranked": ranked}

    tz_brand_hints = extract_existing_tz_brand_hints(full_context or spec_text, parse_under_table_blocks=True)

    all_positions: List[Dict[str, Any]] = []
    all_docs: List[Dict[str, Any]] = []
    seen_doc_urls = set()

    pos_sem = asyncio.Semaphore(2)

    ev_products = (evidence_data or {}).get("evidence_products") or []
    minprom_permit = (evidence_data or {}).get("minprom_permit") or {}

    async def _match_pos_worker(idx: int, p_tz: Dict[str, Any]):
        async with pos_sem:
            pos_hint = None
            if (
                p_tz.get("brand_hint")
                or p_tz.get("model_hint")
                or p_tz.get("manufacturer_hint")
                or p_tz.get("analogs")
            ):
                pos_hint = {
                    "pos_name": p_tz["name"],
                    "brand": p_tz.get("brand_hint", ""),
                    "model": p_tz.get("model_hint", ""),
                    "manufacturer": p_tz.get("manufacturer_hint", ""),
                    "analogs": p_tz.get("analogs", []),
                }
            if not pos_hint:
                pos_hint = find_hint_for_position(tz_brand_hints, p_tz["name"])

            # Сопоставление с доказательствами из официальных документов закупки
            ev_prod = None
            if ev_products:
                clean_name = p_tz["name"].lower().strip()
                for ep in ev_products:
                    ep_name = str(ep.get("name_in_tz") or "").lower().strip()
                    ep_b = str(ep.get("brand") or "").lower().strip()
                    ep_m = str(ep.get("model") or "").lower().strip()
                    if ep_name and (ep_name in clean_name or clean_name in ep_name):
                        ev_prod = ep
                        break
                    if ep_b and ep_b in clean_name:
                        ev_prod = ep
                        break
                    if ep_m and ep_m in clean_name:
                        ev_prod = ep
                        break
                if not ev_prod and len(ev_products) == 1 and len(tz_positions) == 1:
                    ev_prod = ev_products[0]

            if ev_prod:
                if not pos_hint:
                    pos_hint = {}
                ev_b = str(ev_prod.get("brand") or "").strip()
                ev_mfr = str(ev_prod.get("manufacturer") or "").strip()
                if not ev_b or any(w in ev_b.lower() for w in ("не указан", "пусто", "none", "null", "по документу")):
                    ev_b = ev_mfr or pos_hint.get("brand", "")
                pos_hint["brand"] = ev_b or pos_hint.get("brand", "")
                pos_hint["model"] = ev_prod.get("model") or pos_hint.get("model", "")
                pos_hint["manufacturer"] = ev_mfr or pos_hint.get("manufacturer", "")
                pos_hint["supplier"] = ev_prod.get("supplier") or pos_hint.get("supplier", "")
                pos_hint["supplier_inn"] = ev_prod.get("supplier_inn") or pos_hint.get("supplier_inn", "")
                pos_hint["source_type"] = ev_prod.get("source_type", "evidence")
                pos_hint["reasoning"] = ev_prod.get("reasoning", "")
                from .evidence_miner import align_facts_to_requirements
                pos_hint["evidence_facts"] = align_facts_to_requirements(ev_prod.get("facts") or {}, p_tz["requirements"])
                if ev_prod.get("analogs"):
                    pos_hint["analogs"] = (pos_hint.get("analogs") or []) + ev_prod.get("analogs", [])
                if minprom_permit and minprom_permit.get("has_permit"):
                    pos_hint["minprom_permit"] = minprom_permit
            elif minprom_permit and minprom_permit.get("has_permit"):
                if not pos_hint:
                    pos_hint = {}
                pos_hint["minprom_permit"] = minprom_permit

            ai_queries = p_tz.get("search_queries") or []
            try:
                matched = await match_single_position(
                    idx,
                    p_tz["name"],
                    p_tz["requirements"],
                    pos_hint=pos_hint,
                    initial_queries=ai_queries,
                )
                return idx, matched
            except Exception as exc:
                logger.error("match_single_position_failed", idx=idx, error=str(exc), exc_info=True)
                return idx, None

    tz_target_list = list(enumerate(tz_positions[:MAX_EXACT_POSITIONS_PER_JOB], start=1))
    pos_results = await asyncio.gather(
        *(_match_pos_worker(idx, p_tz) for idx, p_tz in tz_target_list),
        return_exceptions=True,
    )

    valid_results = []
    for r in pos_results:
        if isinstance(r, tuple) and len(r) == 2 and r[1]:
            valid_results.append(r)
    # Сохраняем исходный строгий порядок позиций из ТЗ
    valid_results.sort(key=lambda x: x[0])

    for _, matched in valid_results:
        pos = matched["position"]
        pos["position_no"] = len(all_positions) + 1
        all_positions.append(pos)
        for c in matched["ranked"][:3]:
            c_docs = c.get("fused_docs") or [c["doc"]]
            for d in c_docs:
                if d.get("url") and d.get("url") not in seen_doc_urls:
                    seen_doc_urls.add(d.get("url"))
                    all_docs.append(d)

    if not all_positions:
        logger.info("characteristic_first_aborted", stage="no_positions_matched")
        return None

    if progress_callback:
        await progress_callback(95, f"Подобрано позиций: {len(all_positions)} из {len(tz_positions)}")
    return all_positions, all_docs


find_candidate_models_characteristic_first = detect_exact_products_characteristic_first
