import pytest

from app import dadata_client
from app.models import SystemSettings
from app.price_monitoring import extractor
from app.price_monitoring.extractor import is_valid_domain


def _suggestion(*, company_name: str, sites: list[str]) -> dict:
    return {
        "inn": "7701234567",
        "company_name": company_name,
        "is_non_commercial": False,
        "sites": sites,
    }


@pytest.mark.asyncio
async def test_domain_enrichment_rejects_name_only_suggestion(monkeypatch):
    """A DaData name match does not prove that the registrant owns the page domain."""

    async def fake_suggest(*args, **kwargs):
        return [_suggestion(company_name='ООО "VENDOR GROUP"', sites=["vendor-group.ru"])]

    monkeypatch.setattr(dadata_client, "suggest_company_by_query", fake_suggest)

    result = await dadata_client.enrich_company_by_inn_or_query(
        domain="vendor.ru",
        query="Vendor",
    )

    assert result == {}


@pytest.mark.asyncio
async def test_domain_enrichment_accepts_explicit_site_ownership(monkeypatch):
    async def fake_suggest(*args, **kwargs):
        return [_suggestion(company_name='ООО "Поставщик"', sites=["https://www.vendor.ru/about"])]

    monkeypatch.setattr(dadata_client, "suggest_company_by_query", fake_suggest)

    result = await dadata_client.enrich_company_by_inn_or_query(
        domain="vendor.ru",
        query="Поставщик",
    )

    assert result["inn"] == "7701234567"
    assert result["company_name"] == 'ООО "Поставщик"'


@pytest.mark.parametrize(
    "url",
    [
        "https://www.b2b-center.ru/market/shajba/tender-601433/?action=positions",
        "https://supplier.example.ru/tenders/current-lot",
        "https://supplier.example.ru/procurement/notice-42",
        "https://supplier.example.ru/protocol/lot-42",
        "https://supplier.example.ru/archive/offer-42",
    ],
)
def test_procurement_and_archive_pages_are_not_current_price_sources(url):
    assert is_valid_domain(url) is False


def test_product_catalog_card_remains_a_candidate_source():
    assert is_valid_domain("https://supplier.example.ru/catalog/shajba-8bs-950-308") is True


@pytest.mark.parametrize("token", ["50um", "4-рядн", "19ммх0.15ммх20м", "1.2В", "1000мА/ч"])
def test_specification_token_does_not_become_a_conflicting_article(token):
    assert not extractor._is_complex_identifier(token)


@pytest.mark.parametrize("token", ["HR03", "WD-40", "СТП1-2/6000", "5ВК.568.007.2", "123456789012"])
def test_actual_article_stays_strict_in_page_matching(token):
    assert extractor._is_complex_identifier(token)


@pytest.mark.asyncio
async def test_no_inn_quote_keeps_page_derived_supplier_name(monkeypatch):
    async def fake_llm(*args, **kwargs):
        return '''{
            "identifier_conflict": false,
            "category_conflict": false,
            "specification_conflict": false,
            "material_conflict": false,
            "is_relevant": true,
            "is_price_found": true,
            "company_name": "Торговая витрина",
            "raw_price_rub": 200,
            "price_rub": 200,
            "site_unit": "шт"
        }'''

    async def no_verified_identity(*args, **kwargs):
        return {}

    monkeypatch.setattr(extractor, "call_llm", fake_llm)
    monkeypatch.setattr(extractor, "enrich_company_by_inn_or_query", no_verified_identity)

    quote = await extractor.extract_supplier_quote(
        SystemSettings(),
        "Шайба 8БС.950.308",
        "шт",
        "https://vendor.ru/catalog/shajba-8bs-950-308",
        "Шайба 8БС.950.308. Цена 200 руб. В наличии.",
    )

    assert quote is not None
    assert quote.inn is None
    assert quote.company_name == "Торговая витрина"
