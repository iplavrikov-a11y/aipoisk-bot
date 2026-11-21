from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.price_monitoring.cleaner import (
    extract_engineering_spec_tokens,
    check_engineering_spec_conflict,
)
from app.price_monitoring.extractor import extract_schema_org_product_data
from app.price_monitoring.excel_report import _missing_price_status_and_note
from app.price_monitoring.models import ItemPriceResult


def test_engineering_spec_tokens_extraction():
    tokens = extract_engineering_spec_tokens("Кран 11с67п Ду 50 Ру 16 380В кабель 3х2,5 болт М16х60 дв. 15кВт")
    assert tokens["dn"] == {"50"}
    assert tokens["pn"] == {"16"}
    assert tokens["volt"] == {"380"}
    assert tokens["cable"] == {"3x2.5"}
    assert tokens["thread"] == {"16"}
    assert tokens["power"] == {"15"}


def test_engineering_spec_conflict_detection():
    # Matching sizing
    conflict, reason = check_engineering_spec_conflict(
        "Кран шаровый фланцевый 11с67п Ду 50 Ру 16",
        "Кран 11с67п Ду 50 Ру 16 фланцевый стальной",
    )
    assert not conflict
    assert reason == ""

    # Conflicting diameter
    conflict, reason = check_engineering_spec_conflict(
        "Кран шаровый фланцевый 11с67п Ду 50 Ру 16",
        "Кран 11с67п Ду 15 Ру 16 фланцевый",
    )
    assert conflict
    assert "DN" in reason

    # Conflicting pressure
    conflict, reason = check_engineering_spec_conflict(
        "Кран шаровый фланцевый 11с67п Ду 50 Ру 16",
        "Кран 11с67п Ду 50 Ру 40 фланцевый",
    )
    assert conflict
    assert "PN" in reason

    # Cable section conflict
    conflict, reason = check_engineering_spec_conflict(
        "Кабель силовой ВВГнг(А)-LS 3х2.5",
        "Кабель силовой ВВГнг-LS 3х1,5 ГОСТ",
    )
    assert conflict
    assert "CABLE" in reason

    # Cable section match
    conflict, reason = check_engineering_spec_conflict(
        "Кабель силовой ВВГнг(А)-LS 3х2.5",
        "Кабель силовой ВВГнг-LS 3х2,5 ГОСТ",
    )
    assert not conflict

    # Multi-size overview page allows match
    conflict, reason = check_engineering_spec_conflict(
        "Кран шаровый 11с67п Ду 50",
        "Краны 11с67п в наличии: Ду 15, Ду 25, Ду 50, Ду 100",
    )
    assert not conflict


def test_schema_org_brand_and_sku_extraction():
    html = """
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Насос К 80-50-200",
        "sku": "К80-50-200-УХЛ4",
        "brand": {
            "@type": "Brand",
            "name": "Катайский насосный завод"
        },
        "offers": {
            "@type": "Offer",
            "price": "45000.00",
            "priceCurrency": "RUB",
            "availability": "https://schema.org/InStock"
        }
    }
    </script>
    """
    soup = BeautifulSoup(html, "html.parser")
    product_data, is_oos = extract_schema_org_product_data(soup)
    assert product_data is not None
    assert product_data["name"] == "Насос К 80-50-200"
    assert product_data["sku"] == "К80-50-200-УХЛ4"
    assert product_data["brand"] == "Катайский насосный завод"
    assert product_data["price"] == 45000.0
    assert not is_oos


def test_minprom_gisp_fallback_in_excel_notes():
    item = ItemPriceResult(
        row_number=1,
        raw_name="Кран шаровый стальной",
        clean_name="Кран шаровый стальной",
        unit="шт",
        status="not_found",
        search_diagnostics={
            "minprom_match": {
                "registry_number": "10858465",
                "manufacturer": "ООО Завод ПромАрматура",
            }
        },
    )
    status_str, note_str = _missing_price_status_and_note(item)
    assert "Реестре Минпромторга" in status_str
    assert "ООО Завод ПромАрматура" in note_str
    assert "10858465" in note_str
