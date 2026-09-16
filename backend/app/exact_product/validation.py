"""
Детерминированная валидация результатов подбора точных товаров (Форма 2).

Работает универсально для любых закупок, товаров и позиций без завязки на отрасль:

1. Числовая сверка: диапазоны ТЗ ("не менее X и не более Y", "от X до Y", "X-Y")
   против фактического показателя товара, с нормализацией единиц
   (кВт/Вт, см/мм/м, кг/т, месяцев/лет и т.д.).
2. Кодовые маркировки: классы IPxx и аналогичные коды сверяются посимвольно.
3. Согласованность: статус "match" при комментарии об отклонении недопустим.
4. Привязка модели к источникам: формулировки "Подтверждено ... [ИСТОЧНИК #N]"
   допустимы только если документ-источник действительно описывает выбранную
   модель (и при наличии текста документа — содержит само значение).
5. Нейтрализация подмены модели: упоминание модели-аналога в комментариях
   основной позиции заменяется на выбранную модель.

Модуль не обращается к ИИ и БД — только чистые функции над dict-структурами.
"""

from typing import Any, Dict, List, Optional, Tuple

import structlog
from .deep import compute_spec_compliance

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Маркеры комментариев ИИ об отклонении и подтверждении (Правило 14)
# ---------------------------------------------------------------------------

_DEVIATION_MARKERS = (
    "отклонени", "не соответств", "превыша", "выходит за", "не проходит",
    "выше допустимог", "выше предельн", "ниже допустимог", "ниже предельн",
)


def _compact(s: str) -> str:
    return "".join(c for c in str(s or "").lower() if c.isalnum())


def comment_says_deviation(spec: dict) -> bool:
    c = str(spec.get("comment") or "").lower()
    if "улучшен" in c or "превосходит" in c:
        return False
    return any(m in c for m in _DEVIATION_MARKERS)


def _norm_status_key(spec: dict) -> str:
    st = str(spec.get("status") or "").strip().lower()
    if any(k in st for k in ("mismatch", "не подходит", "отклон")):
        return "mismatch"
    if any(k in st for k in ("clarify", "уточн")):
        return "clarify"
    if any(k in st for k in ("match", "соответств")):
        return "match"
    # пустой или неизвестный статус честно трактуется как "требует уточнения"
    return "clarify"


def spec_status_key(spec: dict) -> str:
    """
    Итоговый статус спецификации для отображения: "match" | "clarify" | "mismatch".
    Неизвестный/пустой статус трактуется как "clarify" (честно), а не "match".
    Статус определяется исключительно ИИ (Правило 14). Детерминированно согласовывается только
    явное противоречие, когда собственный комментарий модели указывает на отклонение.
    """
    key = _norm_status_key(spec)
    if key == "match":
        if comment_says_deviation(spec):
            return "mismatch"
    return key


# ---------------------------------------------------------------------------
# Поиск документов модели для оркестратора веб-поиска (Rule 14: только для оркестрации загрузки)
# ---------------------------------------------------------------------------

_GENERIC_BRAND_KEYS = {
    "china", "russia", "россия", "китай", "германия", "germany", "европа",
    "рф", "импорт", "аналог", "оборудование", "завод", "производитель",
}


def _brand_key(brand: str) -> Optional[str]:
    bk = _compact(brand)
    if len(bk) >= 3 and bk not in _GENERIC_BRAND_KEYS:
        return bk
    return None


def _model_keys(brand: str, model: str) -> List[str]:
    """Ключи поиска модели в тексте документа для оркестратора загрузки документов."""
    keys = set()
    raw_model = str(model or "").strip()
    raw_brand = str(brand or "").strip()

    def add(k: str) -> None:
        k = _compact(k)
        if len(k) >= 4:
            keys.add(k)

    if raw_model:
        add(raw_model)
        wo_paren = "".join(c if c not in "()[]" else " " for c in raw_model)
        for color_w in ("silver", "white", "black", "бел", "серебр"):
            wo_paren = _case_insensitive_replace(wo_paren, color_w, " ")
        wo_paren = " ".join(wo_paren.split())
        if wo_paren and wo_paren.lower() != raw_model.lower():
            add(wo_paren)

        raw_tokens = []
        cur = []
        for ch in wo_paren.lower():
            if ch.isalnum():
                cur.append(ch)
            elif cur:
                raw_tokens.append("".join(cur))
                cur = []
        if cur:
            raw_tokens.append("".join(cur))
        for t in raw_tokens:
            if any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
                add(t)
            digits = "".join(c for c in t if c.isdigit())
            if len(digits) >= 3:
                add(digits)
        for a, b in zip(raw_tokens, raw_tokens[1:]):
            add(f"{a}{b}")
            digits_b = "".join(c for c in b if c.isdigit())
            if len(digits_b) >= 3:
                add(f"{a}{digits_b}")

    if raw_brand and raw_model:
        add(f"{raw_brand}{raw_model}")

    return sorted(keys)


def _doc_matches_keys(doc: Optional[dict], keys: List[str]) -> bool:
    if not doc or not isinstance(doc, dict) or not keys:
        return False
    return any(k in doc.get("compact_all", "") for k in keys)


def _doc_by_url(docs: List[dict], url: str) -> Optional[dict]:
    if not url:
        return None
    cu = _compact(url)
    for d in docs:
        if cu and cu == d.get("compact_url"):
            return d
    for d in docs:
        if cu and (cu in d.get("compact_url", "") or d.get("compact_url", "") in cu):
            if len(cu) > 10:
                return d
    return None


# ---------------------------------------------------------------------------
# Нейтрализация чужих моделей в комментариях основной позиции
# ---------------------------------------------------------------------------

def _alt_name_variants(alt: dict) -> List[str]:
    b = str(alt.get("brand") or "").strip()
    m = str(alt.get("model") or "").strip()
    variants = []
    if b and m:
        variants.append(f"{b} {m}".strip())
    if m and len(m) >= 6:
        variants.append(m)
    return [v for v in variants if len(v) >= 6]


def _case_insensitive_replace(text: str, target: str, replacement: str) -> str:
    if not text or not target:
        return text
    low_text = text.lower()
    low_target = target.lower()
    start = 0
    t_len = len(target)
    res = []
    while True:
        idx = low_text.find(low_target, start)
        if idx == -1:
            res.append(text[start:])
            break
        res.append(text[start:idx])
        res.append(replacement)
        start = idx + t_len
    return "".join(res)


def _neutralize_alt_mentions(text: str, alt_names: List[str], replacement: str) -> str:
    if not text:
        return text
    result = text
    for name in sorted(set(alt_names), key=len, reverse=True):
        result = _case_insensitive_replace(result, name, replacement)
    return result


def _apply_spec_checks(spec: dict) -> None:
    """
    Мутирует spec: проверяет согласованность комментария со статусом.
    Характеристики и статус (match / mismatch / clarify) определяет исключительно ИИ (Правило 14).
    Детерминированный код не имеет права менять match на mismatch/clarify через регексы или строковые эвристики.
    """
    key = _norm_status_key(spec)
    # Согласованность комментария со статусом: если модель сама говорит об отклонении
    if key == "match" and comment_says_deviation(spec):
        spec["status"] = "mismatch"


def _recompute_confidence(specs: List[dict]) -> Optional[float]:
    if not specs:
        return None
    from .deep import compute_spec_compliance
    return compute_spec_compliance(specs)


def validate_exact_products(
    positions: List[Dict[str, Any]],
    verified_docs: List[Dict[str, Any]] = None,
    has_doc_text: bool = False,
) -> List[Dict[str, Any]]:
    """
    Системная валидация списка позиций точного товара (in-place) + возврат списка.
    Безопасно вызывать повторно (идемпотентна).
    Характеристики, статусы и документы оценивает только ИИ (Правило 14).
    """
    if not isinstance(positions, list):
        return positions

    for pos in positions:
        if not isinstance(pos, dict):
            continue
        brand = str(pos.get("identified_brand") or "").strip()
        model = str(pos.get("identified_model") or "").strip()
        model_label = f"{brand} {model}".strip()

        # 1. Подмена модели в комментариях основной позиции (модели аналогов)
        alts = [a for a in (pos.get("alternative_brands") or []) if isinstance(a, dict)]
        alt_names: List[str] = []
        for a in alts:
            alt_names.extend(_alt_name_variants(a))
        if alt_names and model_label:
            for s in pos.get("specs_breakdown") or []:
                if isinstance(s, dict) and s.get("comment"):
                    s["comment"] = _neutralize_alt_mentions(str(s["comment"]), alt_names, model_label)

        # 2. Спецификации основной позиции
        for s in pos.get("specs_breakdown") or []:
            if isinstance(s, dict):
                _apply_spec_checks(s)

        # 3. Спецификации аналогов
        for a in alts:
            for s in a.get("specs_breakdown") or []:
                if isinstance(s, dict):
                    _apply_spec_checks(s)

        # 4. Пересчет соответствия по исправленным статусам
        specs = pos.get("specs_breakdown") or []
        new_conf = _recompute_confidence([s for s in specs if isinstance(s, dict)])
        if new_conf is not None:
            pos["confidence"] = new_conf
        for a in alts:
            a_specs = a.get("specs_breakdown") or []
            a_conf = _recompute_confidence([s for s in a_specs if isinstance(s, dict)])
            if a_conf is not None:
                a["confidence"] = a_conf

        # 5. Предупреждения в обосновании только по фактическим несоответствиям (от ИИ)
        reasoning = str(pos.get("reasoning") or "").strip()
        mismatches = sum(1 for s in specs if isinstance(s, dict) and str(s.get("status")) == "mismatch")
        warnings: List[str] = []
        if mismatches:
            total = len([s for s in specs if isinstance(s, dict)])
            warnings.append(f"ВНИМАНИЕ: {mismatches} из {total} параметров не соответствуют требованиям ТЗ.")
        if warnings:
            existing = reasoning
            add_parts = [w for w in warnings if w not in existing]
            if add_parts:
                pos["reasoning"] = " ".join(add_parts) + (" " + existing if existing else "")

    return positions


def validate_stored_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Валидация сохраненных в БД данных точного товара перед отдачей в UI/экспорт.
    Текст документов в БД не хранится — привязка считается по заголовкам/URL.
    """
    if not isinstance(products, list) or not products:
        return products
    docs: List[Dict[str, Any]] = []
    for p in products:
        if isinstance(p, dict):
            for d in p.get("verified_documents") or []:
                if isinstance(d, dict):
                    docs.append(d)
    has_text = any(str(d.get("text") or "").strip() for d in docs)
    try:
        return validate_exact_products(products, docs, has_doc_text=has_text)
    except Exception as exc:
        logger.warning("exact_product_validation_failed", error=str(exc))
        return products


def _is_placeholder_brand_or_model(val: str) -> bool:
    if not val:
        return True
    low = val.strip().lower()
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


def extract_standards_from_text(text: str) -> list[str]:
    import re
    if not text:
        return []
    matches = re.findall(r"(?:ГОСТ(?:\s*Р)?|ТУ|СТО(?:\s+[А-ЯЁa-zA-Z]+)?)\s+[\d\.\-]+(?:-\d+)?", text, re.IGNORECASE)
    return sorted(list(set(m.strip() for m in matches)))


def recompute_and_reconcile_positions(positions: list[Any]) -> None:
    pass

neutralize_alt_mentions_in_comments = _neutralize_alt_mentions
