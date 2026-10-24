"""Regression tests for source-grounded, product-neutral Rule 14 conversion."""
from unittest.mock import AsyncMock, patch

import pytest
from app.position_selection import build_selection_snapshot
from app.price_monitoring.extractor import (
    compute_deterministic_normalized_price,
    reconcile_quote_unit,
)
from app.price_monitoring.models import SupplierQuote


def test_explicit_matching_site_unit_is_never_overwritten_by_item_name():
    """A listed price per target unit must survive regardless of product semantics."""
    cases = [
        ("Пропан газ", "кг", 500.0),
        ("Пропанол-2 химически чистый", "кг", 1200.0),
        ("Кислород технический", "м3", 1260.0),
        ("Кислота азотная", "м3", 12000.0),
    ]
    for name, unit, price in cases:
        quote = SupplierQuote(
            company_name="Проверенный поставщик",
            price_rub=price,
            raw_price_rub=price,
            site_unit=unit,
            unit=unit,
        )
        actual = reconcile_quote_unit(quote, name, unit)
        assert actual.price_rub == price
        assert actual.unit == unit


def test_explicit_package_facts_allow_neutral_cylinder_math():
    price, unit, comment = compute_deterministic_normalized_price(
        raw_price=2100.0,
        site_unit="баллон 50 л",
        target_unit="кг",
        pack_quantity=21.0,
        pack_base_unit="кг",
        is_price_for_whole_pack=True,
    )
    assert (price, unit) == (100.0, "кг")
    assert "21.0 кг" in (comment or "")


def test_pack_quantity_without_a_source_base_unit_never_changes_price():
    """Quantity alone cannot prove what a purchasable pack contains."""
    price, unit, comment = compute_deterministic_normalized_price(
        raw_price=2100.0,
        site_unit="упаковка",
        target_unit="кг",
        pack_quantity=21.0,
        pack_base_unit=None,
        is_price_for_whole_pack=True,
    )
    assert (price, unit, comment) == (2100.0, "кг", None)


@pytest.mark.asyncio
async def test_pair_unit_needs_explicit_source_backed_piece_count():
    """A pair may be any product; only an evidenced 2-piece pack can convert it."""
    from app.price_monitoring.extractor import extract_supplier_quote

    parsed = {
        "is_relevant": True,
        "is_price_found": True,
        "raw_price_rub": 500.0,
        "price_rub": 500.0,
        "site_unit": "пар",
        "company_name": "ООО Поставщик",
    }
    with patch("app.price_monitoring.extractor.call_llm", new=AsyncMock(return_value="{}")), \
         patch("app.price_monitoring.extractor.parse_json_object", return_value=parsed), \
         patch("app.price_monitoring.extractor.enrich_company_by_inn_or_query", new=AsyncMock(return_value=None)):
        quote = await extract_supplier_quote(
            settings=object(),
            target_item_name="Клемма соединительная",
            target_unit="шт",
            url="https://supplier.example/product",
            page_text="Цена: 500 ₽ за пару клемм",
        )
    assert quote is None


@pytest.mark.asyncio
async def test_pair_of_non_wearable_goods_converts_when_page_proves_piece_count():
    """No product-name allowlist is needed for legitimate non-wearable pairs."""
    from app.price_monitoring.extractor import extract_supplier_quote

    parsed = {
        "is_relevant": True,
        "is_price_found": True,
        "raw_price_rub": 500.0,
        "price_rub": 500.0,
        "site_unit": "пара",
        "pack_quantity": 2.0,
        "pack_base_unit": "шт",
        "is_price_for_whole_pack": True,
        "company_name": "ООО Поставщик",
    }
    with patch("app.price_monitoring.extractor.call_llm", new=AsyncMock(return_value="{}")), \
         patch("app.price_monitoring.extractor.parse_json_object", return_value=parsed), \
         patch("app.price_monitoring.extractor.enrich_company_by_inn_or_query", new=AsyncMock(return_value=None)):
        quote = await extract_supplier_quote(
            settings=object(),
            target_item_name="Клемма соединительная",
            target_unit="шт",
            url="https://supplier.example/product",
            page_text="Цена: 500 ₽ за пару клемм (2 шт.)",
        )
    assert quote is not None
    assert quote.price_rub == 250.0
    assert quote.unit == "шт"


def test_selection_groups_are_source_neutral_and_preserve_source_category():
    snapshot = build_selection_snapshot([
        {"name": "Панель строительная"},
        {"name": "Саморез оцинкованный"},
        {"name": "Реагент лабораторный", "category": "Лабораторные материалы"},
    ], price_kopeks=100, mode="exact_product")
    import json
    items = json.loads(snapshot)["items"]
    assert [item["category"] for item in items] == [
        "Позиции спецификации",
        "Позиции спецификации",
        "Лабораторные материалы",
    ]


@pytest.mark.asyncio
async def test_extractor_preserves_explicit_matching_unit_through_full_caller():
    """No LLM, HTTP, or DaData call: the parsed page fact is supplied locally."""
    parsed = {
        "is_relevant": True,
        "is_price_found": True,
        "raw_price_rub": 500.0,
        "price_rub": 500.0,
        "site_unit": "кг",
        "company_name": "ООО Поставщик",
    }
    with patch("app.price_monitoring.extractor.call_llm", new=AsyncMock(return_value="{}")), \
         patch("app.price_monitoring.extractor.parse_json_object", return_value=parsed), \
         patch("app.price_monitoring.extractor.enrich_company_by_inn_or_query", new=AsyncMock(return_value=None)):
        from app.price_monitoring.extractor import extract_supplier_quote
        quote = await extract_supplier_quote(
            settings=object(),
            target_item_name="Пропан газ",
            target_unit="кг",
            url="https://supplier.example/product",
            page_text="Пропан газ. Цена 500 ₽ за кг.",
        )
    assert quote is not None
    assert quote.raw_price_rub == quote.price_rub == 500.0
    assert quote.unit == "кг"


@pytest.mark.asyncio
async def test_extractor_uses_explicit_package_facts_through_full_caller():
    parsed = {
        "is_relevant": True,
        "is_price_found": True,
        "raw_price_rub": 2100.0,
        "price_rub": 2100.0,
        "site_unit": "баллон 50 л",
        "pack_quantity": 21.0,
        "pack_base_unit": "кг",
        "is_price_for_whole_pack": True,
        "company_name": "ООО Поставщик",
    }
    with patch("app.price_monitoring.extractor.call_llm", new=AsyncMock(return_value="{}")), \
         patch("app.price_monitoring.extractor.parse_json_object", return_value=parsed), \
         patch("app.price_monitoring.extractor.enrich_company_by_inn_or_query", new=AsyncMock(return_value=None)):
        from app.price_monitoring.extractor import extract_supplier_quote
        quote = await extract_supplier_quote(
            settings=object(),
            target_item_name="Любой товар",
            target_unit="кг",
            url="https://supplier.example/product",
            page_text="Цена 2 100 ₽ за баллон. Масса продукта 21 кг.",
        )
    assert quote is not None
    assert quote.price_rub == 100.0
    assert quote.unit == "кг"
