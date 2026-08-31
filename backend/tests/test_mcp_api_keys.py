from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, db_session
from app.main import app
from app.models import ApiKey, SystemSettings
from app.mcp_api import generate_api_key, hash_api_key

TEST_DB_URL = "sqlite:///./data/test_mcp.db"
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
    if os.path.exists("./data/test_mcp.db"):
        os.remove("./data/test_mcp.db")


def test_api_key_generation_and_hashing():
    raw_key, key_hash, key_prefix = generate_api_key(is_admin=False)
    assert raw_key.startswith("tl_live_")
    assert len(raw_key) > 30
    assert hash_api_key(raw_key) == key_hash
    assert key_prefix.startswith("tl_live_")

    admin_raw, admin_hash, admin_prefix = generate_api_key(is_admin=True)
    assert admin_raw.startswith("tl_admin_")
    assert hash_api_key(admin_raw) == admin_hash


def test_mcp_unauthorized():
    client = TestClient(app)
    # Missing key
    resp = client.get("/api/v1/mcp/balance")
    assert resp.status_code == 401

    # Invalid key
    resp = client.get("/api/v1/mcp/balance", headers={"Authorization": "Bearer invalid_key_123"})
    assert resp.status_code == 401


def test_mcp_balance_and_quota_consumption():
    client = TestClient(app)
    db = TestingSessionLocal()

    raw_key, key_hash, key_prefix = generate_api_key(is_admin=False)
    key_obj = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="Test Client Key",
        is_admin=False,
        is_active=True,
        allowed_supplier_search=True,
        allowed_exact_product=True,
        allowed_procurement_report=False,
        quota_supplier_search=5,
        quota_exact_product=2,
        quota_procurement_report=0,
        spent_supplier_search=0,
        spent_exact_product=0,
        spent_procurement_report=0,
    )
    db.add(key_obj)
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {raw_key}"}
    resp = client.get("/api/v1/mcp/balance", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["key_name"] == "Test Client Key"
    assert data["supplier_search"]["quota"] == 5
    assert data["supplier_search"]["remaining"] == 5
    assert data["procurement_report"]["allowed"] is False


def test_mcp_disabled_service_forbidden():
    client = TestClient(app)
    db = TestingSessionLocal()

    raw_key, key_hash, key_prefix = generate_api_key(is_admin=False)
    key_obj = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name="Restricted Key",
        is_admin=False,
        is_active=True,
        allowed_supplier_search=False,  # Not allowed
        allowed_exact_product=True,
        allowed_procurement_report=False,
        quota_supplier_search=10,
    )
    db.add(key_obj)
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {raw_key}"}
    resp = client.post(
        "/api/v1/mcp/suppliers/search",
        json={"specification": "Тестовая поставка оборудования"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "not permitted" in resp.json()["detail"]


def test_admin_api_keys_management():
    from app.security import _admin_token
    client = TestClient(app)
    # Require admin token
    admin_token = _admin_token()
    admin_headers = {"X-Admin-Token": admin_token}

    # 1. Create key
    create_resp = client.post(
        "/api/admin/api-keys",
        json={
            "name": "Integration Partner",
            "is_admin": False,
            "allowed_supplier_search": True,
            "allowed_exact_product": True,
            "allowed_procurement_report": True,
            "quota_supplier_search": 25,
            "quota_exact_product": 10,
            "quota_procurement_report": 15,
            "rate_limit_per_minute": 60,
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 200
    created_data = create_resp.json()
    assert created_data["ok"] is True
    assert "raw_api_key" in created_data
    raw_partner_key = created_data["raw_api_key"]
    key_id = created_data["item"]["id"]

    # 2. Verify key works in MCP balance
    mcp_resp = client.get("/api/v1/mcp/balance", headers={"Authorization": f"Bearer {raw_partner_key}"})
    assert mcp_resp.status_code == 200
    assert mcp_resp.json()["supplier_search"]["quota"] == 25

    # 3. List keys in admin
    list_resp = client.get("/api/admin/api-keys", headers=admin_headers)
    assert list_resp.status_code == 200
    keys_list = list_resp.json()
    assert any(k["id"] == key_id for k in keys_list)

    # 4. Patch key (disable)
    patch_resp = client.patch(
        f"/api/admin/api-keys/{key_id}",
        json={"is_active": False, "quota_supplier_search": 50},
        headers=admin_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False
    assert patch_resp.json()["quota_supplier_search"] == 50

    # 5. Verify disabled key is rejected by MCP
    blocked_resp = client.get("/api/v1/mcp/balance", headers={"Authorization": f"Bearer {raw_partner_key}"})
    assert blocked_resp.status_code == 403

    # 6. Regenerate key
    regen_resp = client.post(f"/api/admin/api-keys/{key_id}/regenerate", headers=admin_headers)
    assert regen_resp.status_code == 200
    new_raw_key = regen_resp.json()["raw_api_key"]
    assert new_raw_key != raw_partner_key

    # 7. Delete key
    del_resp = client.delete(f"/api/admin/api-keys/{key_id}", headers=admin_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True


def test_admin_api_test_endpoint():
    from unittest.mock import AsyncMock, patch
    from app.security import _admin_token
    client = TestClient(app)
    admin_token = _admin_token()
    admin_headers = {"X-Admin-Token": admin_token}

    mock_discover = AsyncMock(return_value=([{"company_name": "ООО СМЛ Тест", "inn": "7701234567"}], {}))
    with patch("app.mcp_api.extract_supplier_search_context", new=AsyncMock(return_value="СМЛ панели")), \
         patch("app.mcp_api.discover_suppliers", new=mock_discover):
        resp = client.post(
            "/api/admin/api-keys/test",
            json={"tool": "supplier_search", "query": "смл панели, стекломагниевые панели"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["tool"] == "supplier_search"
        assert data["total_found"] == 1
        assert data["suppliers"][0]["company_name"] == "ООО СМЛ Тест"
        mock_discover.assert_awaited_once()
        _, kwargs = mock_discover.call_args
        assert kwargs.get("context") == "СМЛ панели"
        assert kwargs.get("target") == 3


