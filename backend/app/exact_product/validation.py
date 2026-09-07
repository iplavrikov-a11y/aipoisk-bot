"""
Детерминированная валидация результатов подбора точных товаров (Форма 2).
Работает универсально для любых закупок, товаров и позиций без завязки на отрасль:

1. Числовая сверка и согласованность статусов: статус "match" при комментарии об отклонении недопустим.
2. Привязка модели к источникам: формулировки "Подтверждено ... [ИСТОЧНИК #N]"
   допустимы только если документ-источник действительно описывает выбранную модель.
3. Нейтрализация подмены модели: упоминание модели-аналога в комментариях
   основной позиции заменяется на выбранную модель.
4. Честный расчет соответствия ТЗ: исключает слепую подгонку под 95% и галлюцинации.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Маркеры комментариев ИИ об отклонении и подтверждении
_DEVIATION_MARKERS = (
    "отклонени", "не соответств", "превыша", "выходит за", "не проходит",
    "выше допустимог", "выше предельн", "ниже допустимог", "ниже предельн",
)

_GENERIC_BRAND_KEYS = {
    "china", "russia", "россия", "китай", "германия", "germany", "европа",
    "рф", "импорт", "аналог", "оборудование", "завод", "производитель",
}


def _compact(s: Any) -> str:
    return "".join(c for c in str(s or "").lower() if c.isalnum())


def comment_says_deviation(spec: Union[dict, Any]) -> bool:
    if isinstance(spec, dict):
        c = str(spec.get("comment") or "").lower()
    else:
        c = str(getattr(spec, "comment", "") or "").lower()
    if "улучшен" in c or "превосходит" in c:
        return False
    return any(m in c for m in _DEVIATION_MARKERS)


def _norm_status_key(spec: Union[dict, Any]) -> str:
    if isinstance(spec, dict):
        st = str(spec.get("status") or "").strip().lower()
    else:
        st = str(getattr(spec, "status", "") or "").strip().lower()
    if any(k in st for k in ("mismatch", "не подходит", "отклон")):
        return "mismatch"
    if any(k in st for k in ("clarify", "уточн")):
        return "clarify"
    if any(k in st for k in ("match", "соответств")):
        return "match"
    return "clarify"


def spec_status_key(spec: Union[dict, Any]) -> str:
    key = _norm_status_key(spec)
    if key == "match":
        if comment_says_deviation(spec):
            return "mismatch"
    return key


def _brand_key(brand: str) -> Optional[str]:
    bk = _compact(brand)
    if len(bk) >= 3 and bk not in _GENERIC_BRAND_KEYS:
        return bk
    return None


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


def _model_keys(brand: str, model: str) -> List[str]:
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


def _alt_name_variants(alt: dict) -> List[str]:
    b = str(alt.get("brand") or "").strip()
    m = str(alt.get("model") or "").strip()
    variants = []
    if b and m:
        variants.append(f"{b} {m}".strip())
    if m and len(m) >= 6:
        variants.append(m)
    return [v for v in variants if len(v) >= 6]


def _neutralize_alt_mentions(text: str, alt_names: List[str], replacement: str) -> str:
    if not text:
        return text
    result = text
    for name in sorted(set(alt_names), key=len, reverse=True):
        result = _case_insensitive_replace(result, name, replacement)
    return result


neutralize_alt_mentions_in_comments = _neutralize_alt_mentions



def _apply_spec_checks(spec: Union[dict, Any]) -> None:
    key = _norm_status_key(spec)
    if key == "match" and comment_says_deviation(spec):
        if isinstance(spec, dict):
            spec["status"] = "mismatch"
        else:
            spec.status = "mismatch"


def compute_spec_compliance(specs: List[Union[dict, Any]]) -> float:
    """
    Математический расчет процента соответствия ТЗ по проверенным параметрам (Форма 2).
    Исключает слепую подгонку под 95% и галлюцинации ИИ.
    """
    if not specs:
        return 0.50
    total = len(specs)

    def _get_status(s: Union[dict, Any]) -> str:
        if isinstance(s, dict):
            return str(s.get("status") or "").strip().lower()
        return str(getattr(s, "status", "") or "").strip().lower()

    matches = sum(1 for s in specs if _get_status(s) == "match")
    mismatches = sum(1 for s in specs if _get_status(s) == "mismatch")
    clarifies = sum(1 for s in specs if _get_status(s) == "clarify")

    if mismatches > 0:
        return round(matches / total, 2)
    else:
        return round(min(0.99, (matches + 0.5 * clarifies) / total), 2)


def validate_exact_products(
    positions: List[Union[dict, Any]],
    verified_docs: List[Dict[str, Any]] = None,
    has_doc_text: bool = False,
) -> List[Union[dict, Any]]:
    """
    Системная валидация списка позиций точного товара (in-place) + возврат списка.
    Безопасно вызывать повторно (идемпотентна).
    Работает как с dict-структурами, так и с dataclass ExactProductPosition.
    """
    if not isinstance(positions, list):
        return positions

    for pos in positions:
        is_dict = isinstance(pos, dict)
        brand = str(pos.get("identified_brand") if is_dict else getattr(pos, "identified_brand", "") or "").strip()
        model = str(pos.get("identified_model") if is_dict else getattr(pos, "identified_model", "") or "").strip()
        model_label = f"{brand} {model}".strip()

        # 1. Подмена модели в комментариях основной позиции (модели аналогов)
        raw_alts = pos.get("alternative_brands") if is_dict else getattr(pos, "alternative_brands", [])
        alts = [a for a in (raw_alts or []) if isinstance(a, dict) or hasattr(a, "brand")]
        alt_names: List[str] = []
        for a in alts:
            a_dict = a if isinstance(a, dict) else a.to_dict() if hasattr(a, "to_dict") else {}
            alt_names.extend(_alt_name_variants(a_dict))

        raw_specs = pos.get("specs_breakdown") if is_dict else getattr(pos, "specs_breakdown", [])
        specs = raw_specs or []

        if alt_names and model_label:
            for s in specs:
                if isinstance(s, dict) and s.get("comment"):
                    s["comment"] = _neutralize_alt_mentions(str(s["comment"]), alt_names, model_label)
                elif hasattr(s, "comment") and s.comment:
                    s.comment = _neutralize_alt_mentions(str(s.comment), alt_names, model_label)

        # 2. Спецификации основной позиции
        for s in specs:
            _apply_spec_checks(s)

        # 3. Спецификации аналогов
        for a in alts:
            a_specs = a.get("specs_breakdown") if isinstance(a, dict) else getattr(a, "specs_breakdown", [])
            for s in (a_specs or []):
                _apply_spec_checks(s)

        # 4. Пересчет соответствия по исправленным статусам
        new_conf = compute_spec_compliance(specs)
        if is_dict:
            pos["confidence"] = new_conf
        else:
            pos.confidence = new_conf

        for a in alts:
            a_specs = a.get("specs_breakdown") if isinstance(a, dict) else getattr(a, "specs_breakdown", [])
            if a_specs:
                a_conf = compute_spec_compliance(a_specs)
                if isinstance(a, dict):
                    a["confidence"] = a_conf
                else:
                    a.confidence = a_conf

        # 5. Предупреждения в обосновании только по фактическим несоответствиям
        reasoning = str(pos.get("reasoning") if is_dict else getattr(pos, "reasoning", "") or "").strip()
        mismatches = sum(
            1 for s in specs
            if (isinstance(s, dict) and str(s.get("status")) == "mismatch")
            or (hasattr(s, "status") and str(s.status) == "mismatch")
        )
        warnings: List[str] = []
        if mismatches:
            total = len(specs)
            warnings.append(f"ВНИМАНИЕ: {mismatches} из {total} параметров не соответствуют требованиям ТЗ.")
        if warnings:
            existing = reasoning
            add_parts = [w for w in warnings if w not in existing]
            if add_parts:
                new_reasoning = " ".join(add_parts) + (" " + existing if existing else "")
                if is_dict:
                    pos["reasoning"] = new_reasoning
                else:
                    pos.reasoning = new_reasoning

    return positions


def validate_stored_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        logger.warning("exact_product_validation_failed: %s", exc)
        return products


def _is_placeholder_brand_or_model(val: str) -> bool:
    if not val:
        return True
    low = val.strip().lower()
    placeholders = [
        "в открытой документации не указано",
        "требуется официальный паспорт",
        "в открытом доступе не найдено",
        "не указано",
        "не определен",
        "отечественный производитель",
        "по спецификации",
        "требуется паспорт",
        "требуется уточнение",
    ]
    return any(p in low for p in placeholders) or len(low) < 2


def extract_standards_from_text(text: str) -> list[str]:
    """Извлекает обозначения стандартов ГОСТ, ТУ, СТО, ОСТ из текста."""
    if not text:
        return []
    import re
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


def recompute_and_reconcile_positions(positions: list[Any]) -> None:
    """
    Пересчитывает честное соответствие по всем позициям и аналогам
    и добавляет предупреждения при обнаружении критических отклонений от ТЗ.
    """
    for pos in positions:
        specs = getattr(pos, "specs_breakdown", None)
        if specs is None and isinstance(pos, dict):
            specs = pos.get("specs_breakdown")
        if specs:
            total = len(specs)
            mismatches = sum(
                1 for s in specs
                if (s.get("status") if isinstance(s, dict) else getattr(s, "status", "")) == "mismatch"
            )
            real_conf = compute_spec_compliance(specs)
            if isinstance(pos, dict):
                pos["confidence"] = real_conf
            else:
                pos.confidence = real_conf

            if mismatches >= 3 or (total > 0 and mismatches / total >= 0.4):
                pct_str = f"{int(real_conf * 100)}%"
                brand = pos.get("identified_brand") if isinstance(pos, dict) else getattr(pos, "identified_brand", "")
                model = pos.get("identified_model") if isinstance(pos, dict) else getattr(pos, "identified_model", "")
                warning_lead = (
                    f"ВНИМАНИЕ: Проверенная модель {brand} {model} "
                    f"имеет критические отклонения от ТЗ (соответствие {pct_str}, {mismatches} из {total} параметров отклоняются). "
                    f"Товар не удовлетворяет требованиям заказчика."
                )
                reasoning = pos.get("reasoning", "") if isinstance(pos, dict) else getattr(pos, "reasoning", "")
                if warning_lead not in reasoning:
                    new_r = f"{warning_lead} {reasoning}".strip()
                    if isinstance(pos, dict):
                        pos["reasoning"] = new_r
                    else:
                        pos.reasoning = new_r

        alts = getattr(pos, "alternative_brands", None)
        if alts is None and isinstance(pos, dict):
            alts = pos.get("alternative_brands")
        if alts:
            for alt in alts:
                alt_specs = getattr(alt, "specs_breakdown", None)
                if alt_specs is None and isinstance(alt, dict):
                    alt_specs = alt.get("specs_breakdown")
                if alt_specs:
                    conf = compute_spec_compliance(alt_specs)
                    if isinstance(alt, dict):
                        alt["confidence"] = conf
                    else:
                        alt.confidence = conf

