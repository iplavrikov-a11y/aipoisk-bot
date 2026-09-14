from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, db_session
from app.main import app
from app.models import ApiKey, SystemSettings
from app.mcp_api import (
    McpSupplierSearchRequest,
    McpExactProductRequest,
    McpProcurementAnalyzeRequest,
    generate_api_key,
)

TEST_DB_URL = "sqlite:///./data/test_mcp_resilience.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)
        db.commit()
    db.close()
    app.dependency_overrides[db_session] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./data/test_mcp_resilience.db"):
        os.remove("./data/test_mcp_resilience.db")


client = TestClient(app)


def test_mcp_supplier_search_request_normalization():
    # Scenario 1: Codex-style structured payload
    payload1 = {
        "product_name": "Гидравлическая аэродромная силовая установка",
        "okpd2": "28.99.39.190",
        "characteristics": [
            {"name": "Тип масел", "value": "SKYDROL"},
            {"name": "Давление", "value": "до 207 бар"},
        ],
        "quantity": 2,
        "delivery_region": "Москва",
        "max_results": 15,
        "mode": "minprom_registry_priority",
    }
    req1 = McpSupplierSearchRequest(**payload1)
    assert req1.target_count == 15
    assert req1.city == "Москва"
    assert req1.search_policy == "minprom_registry_priority"
    assert "Предмет закупки / товар: Гидравлическая аэродромная силовая установка" in req1.specification
    assert "Код ОКПД2: 28.99.39.190" in req1.specification
    assert "Количество: 2" in req1.specification
    assert "• Тип масел: SKYDROL" in req1.specification
    assert "• Давление: до 207 бар" in req1.specification

    # Scenario 2: Simple query from chat harness
    payload2 = {
        "query": "Поставка СМЛ панелей негорючих",
        "limit": 8,
        "region": "Санкт-Петербург",
    }
    req2 = McpSupplierSearchRequest(**payload2)
    assert req2.target_count == 8
    assert req2.city == "Санкт-Петербург"
    assert "Поставка СМЛ панелей негорючих" in req2.specification

    # Scenario 3: Dict of specs
    payload3 = {
        "title": "Кабель ВВГнг",
        "specs": {"Сечение": "3х2.5", "ГОСТ": "ГОСТ 31996-2012"},
        "amount": 500,
    }
    req3 = McpSupplierSearchRequest(**payload3)
    assert "Предмет закупки / товар: Кабель ВВГнг" in req3.specification
    assert "• Сечение: 3х2.5" in req3.specification
    assert "• ГОСТ: ГОСТ 31996-2012" in req3.specification


def test_mcp_exact_product_request_normalization():
    # Scenario: product_name, okpd2, and characteristics list
    payload = {
        "product_name": "Гидравлическая аэродромная силовая установка",
        "okpd2": "28.99.39.190",
        "characteristics": [
            {"name": "Тип используемых гидравлических масел", "value": "HYJET IV-A, SKYDROL и НГЖ"},
            {"name": "Длина шлангов", "value": "12 м"},
            {"name": "Контур высокого давления", "value": "до 207 бар"},
        ],
        "quantity": 2,
    }
    req = McpExactProductRequest(**payload)
    assert req.procurement_title == "Гидравлическая аэродромная силовая установка"
    assert "Предмет закупки / товар: Гидравлическая аэродромная силовая установка" in req.specification
    assert "Код ОКПД2: 28.99.39.190" in req.specification
    assert "• Тип используемых гидравлических масел: HYJET IV-A, SKYDROL и НГЖ" in req.specification
    assert "• Контур высокого давления: до 207 бар" in req.specification


def test_mcp_procurement_analyze_request_normalization():
    # Various field names supported
    for key in ["doc", "text", "document", "contract_text", "tz", "content", "file_content"]:
        req = McpProcurementAnalyzeRequest(**{key: "Проект государственного контракта на поставку оборудования..."})
        assert "Проект государственного контракта" in req.document_text


def test_live_mocked_mcp_api_endpoints_with_flexible_payloads():
    # Create active admin key for test
    raw_key, key_hash, key_prefix = generate_api_key(is_admin=True)
    db = TestingSessionLocal()
    try:
        test_key = ApiKey(
            name="Resilience Test Key",
            key_hash=key_hash,
            key_prefix=key_prefix,
            secret_token=raw_key,
            is_admin=True,
            is_active=True,
            allowed_supplier_search=True,
            allowed_exact_product=True,
            allowed_procurement_report=True,
        )
        db.add(test_key)
        db.commit()
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {raw_key}"}

    # 1. Test POST /api/v1/mcp/suppliers/search with Codex-style payload
    mock_discover = AsyncMock(return_value=([{"company_name": "ООО АвиаТест", "inn": "7701234567"}], {"subject": "Гидроустановка"}))
    with patch("app.mcp_api.extract_supplier_search_context", new=AsyncMock(return_value="Гидроустановка")), \
         patch("app.mcp_api.discover_suppliers", new=mock_discover), \
         patch("app.mcp_api.build_quote_request_markdown_with_ai", new=AsyncMock(return_value="# Запрос КП")):
        resp = client.post(
            "/api/v1/mcp/suppliers/search",
            json={
                "product_name": "Гидравлическая аэродромная силовая установка",
                "okpd2": "28.99.39.190",
                "characteristics": [{"name": "Масла", "value": "Skydrol"}],
                "quantity": 2,
                "delivery_region": "Москва",
                "max_results": 10,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["target_requested"] == 10
        assert data["total_found"] == 1
        assert data["suppliers"][0]["company_name"] == "ООО АвиаТест"

    # 2. Test POST /api/v1/mcp/products/exact-analogs with Codex payload
    from app.exact_product import ExactProductReport, ExactProductPosition, SpecParameterMatch
    mock_report = ExactProductReport(
        procurement_title="Гидравлическая аэродромная силовая установка",
        total_positions=1,
        positions=[
            ExactProductPosition(
                position_no=1,
                name_in_tz="Гидравлическая аэродромная силовая установка",
                identified_brand="TEST-FUCHS",
                identified_model="HGPU25-30-2",
                manufacturer="TEST FUCHS GmbH",
                confidence=0.85,
                reasoning="Полное совпадение опций",
                specs_breakdown=[SpecParameterMatch(param_name="Масла", tz_requirement="Skydrol", product_fact="Skydrol", status="match")],
            )
        ],
        summary="Найдена установка TEST-FUCHS",
    )
    with patch("app.mcp_api.analyze_exact_product", new=AsyncMock(return_value=mock_report)), \
         patch("app.mcp_api.write_exact_product_docx", new=lambda path, rep, title: None):
        resp = client.post(
            "/api/v1/mcp/products/exact-analogs",
            json={
                "product_name": "Гидравлическая аэродромная силовая установка",
                "okpd2": "28.99.39.190",
                "characteristics": [{"name": "Масла", "value": "Skydrol"}],
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["total_positions"] == 1
        assert data["positions"][0]["identified_brand"] == "TEST-FUCHS"
        assert data["positions"][0]["identified_model"] == "HGPU25-30-2"
