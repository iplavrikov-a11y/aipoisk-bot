import pytest
from app.dadata_client import enrich_company_by_inn
from app.supplier_search import (
    _enrich_accepted_suppliers_with_dadata,
    _enrich_unmatched_registry_suppliers,
    MinpromRegistryContext,
    MinpromRegistryRequirement,
)
from app.models import SystemSettings


@pytest.mark.asyncio
async def test_dadata_enrich_by_inn_live_or_mock():
    res = await enrich_company_by_inn("7709752170")
    assert isinstance(res, dict)
    if res:
        assert res.get("inn") == "7709752170"
        assert "ЛИТТРАНССЕРВИС" in res.get("company_name", "").upper()
        assert res.get("status") == "ACTIVE"
        assert res.get("region") != ""


@pytest.mark.asyncio
async def test_enrich_accepted_suppliers_with_dadata():
    suppliers = [
        {"company_name": "Тест", "inn": "7709752170", "region": "", "contact_person": ""},
        {"company_name": "Без ИНН", "inn": "", "region": "", "contact_person": ""},
    ]
    enriched = await _enrich_accepted_suppliers_with_dadata(suppliers)
    assert len(enriched) == 2
    if enriched[0].get("region"):
        assert "Москва" in enriched[0]["region"]


@pytest.mark.asyncio
async def test_enrich_unmatched_registry_suppliers():
    settings = SystemSettings()
    req = MinpromRegistryRequirement(required=True, reason="Тест")
    ctx = MinpromRegistryContext(
        requirement=req,
        status="ok",
        entries=[
            {
                "inn": "7709752170",
                "manufacturer": "ООО ЛИТТРАНССЕРВИС",
                "product": "Установка МЕГАЛИТ",
                "registry_number": "10539920",
                "source_url": "https://gisp.gov.ru",
            }
        ],
    )
    accepted = []
    result = await _enrich_unmatched_registry_suppliers(settings, accepted, ctx)
    assert len(result) == 1
    item = result[0]
    assert item["inn"] == "7709752170"
    assert item["supplier_search_origin"] == "minprom_registry"
    assert "10539920" in item["comments"]
