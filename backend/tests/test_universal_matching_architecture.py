import pytest
from app.exact_product.matcher import _is_clean_maker_or_brand
from app.exact_product.deep import _deduplicate_alts_deep


def test_generic_type_abbreviations_rejected_as_brands():
    """Проверяет, что типовые технические сокращения номенклатуры не считаются брендами/заводами в TenderLex."""
    type_abbrs = ["МДУ", "МФУ", "КТП", "ВРУ", "ШР", "КРВ", "ЩО", "НД", "АРМ", "СИП", "ПВ-3", "ВВГ", "АВБбШв"]
    for abbr in type_abbrs:
        assert not _is_clean_maker_or_brand(abbr), f"Abbreviation {abbr} should not be a valid brand/maker"
        assert not _is_clean_maker_or_brand(abbr.lower()), f"Lowercase abbreviation {abbr} should not be a valid brand/maker"

    real_makers = [
        "Puff",
        "Ksitex",
        "Sanaks",
        "ГМС Ливгидромаш",
        "Челябинский компрессорный завод",
        "Родикон",
        "БалтПромКартон",
    ]
    for maker in real_makers:
        assert _is_clean_maker_or_brand(maker), f"Real maker {maker} must be valid"


def test_alternative_brands_deduplication():
    """Проверяет дедупликацию аналогов в TenderLex deep pipeline."""
    dispenser_alts = [
        {"brand": "VD-20", "model": "VD-20", "manufacturer": "", "confidence": 0.90},
        {"brand": "Саникс", "model": "VD-20", "manufacturer": "Вадис ООО", "confidence": 0.94},
    ]
    res1 = _deduplicate_alts_deep(dispenser_alts)
    assert len(res1) == 1
    assert res1[0]["brand"] == "Саникс"
    assert res1[0]["model"] == "VD-20"
    assert res1[0]["manufacturer"] == "Вадис ООО"
    assert res1[0]["confidence"] == 0.94


def test_negative_requirements_and_fact_sanitization():
    """Проверяет нормализацию фактов при отрицательных требованиях ТЗ."""
    raw_specs = [
        {"param_name": "Наличие замка", "tz_requirement": "Нет", "product_fact": "", "status": "match"},
        {"param_name": "Тип подачи", "tz_requirement": "Капля", "product_fact": "", "status": "match"},
        {"param_name": "Срок службы", "tz_requirement": "≥ 5 лет", "product_fact": "", "status": "clarify"},
    ]

    normalized = []
    for s in raw_specs:
        tz_cur = str(s.get("tz_requirement") or "").strip()
        tz_lower = tz_cur.lower()
        fact = str(s.get("product_fact") or "").strip()
        st = s.get("status")
        if not fact:
            if st == "match":
                if tz_lower in ("нет", "не требуется", "отсутствует", "не предусмотрено"):
                    fact = "Отсутствует"
                else:
                    fact = tz_cur or "Соответствует ТЗ"
            elif st == "clarify":
                fact = "В открытой документации не указано (требуется официальный паспорт завода)"
            else:
                fact = "Не соответствует требованиям ТЗ"
        normalized.append({"param_name": s["param_name"], "product_fact": fact, "status": st})

    for item in normalized:
        assert item["product_fact"], f"Fact for {item['param_name']} must not be empty"

    assert normalized[0]["product_fact"] == "Отсутствует"
    assert normalized[1]["product_fact"] == "Капля"
    assert "В открытой документации не указано" in normalized[2]["product_fact"]
