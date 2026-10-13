import pytest
from starlette.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Client, Job, SystemSettings, WebUser, BillingTransaction
from app.security import _admin_token
from app.billing import (
    KIND_PRICE_MONITORING,
    charge_price_monitoring_job,
    effective_price_kopeks,
)
from app.price_monitoring.models import (
    BatchMonitoringResult,
    ItemPriceResult,
    SupplierQuote,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_client():
    token = _admin_token()
    client = TestClient(app, headers={"x-admin-token": token})
    return client


def test_price_monitoring_admin_settings_api(admin_client):
    # Get settings
    resp = admin_client.get("/api/price-monitoring/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "default_price_rub" in data
    assert "default_price_kopeks" in data

    # Update settings
    resp = admin_client.post("/api/price-monitoring/settings", json={"default_price_rub": 45.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_price_rub"] == 45.0
    assert data["default_price_kopeks"] == 4500

    # Reset back to 50.0
    admin_client.post("/api/price-monitoring/settings", json={"default_price_rub": 50.0})


def test_price_monitoring_client_access_and_override(db_session, admin_client):
    # List clients
    resp = admin_client.get("/api/price-monitoring/clients")
    assert resp.status_code == 200
    clients_list = resp.json().get("clients", [])
    assert isinstance(clients_list, list)

    # Pick or create a test client
    test_c = db_session.query(Client).filter(Client.telegram_id == "pm_test_999").first()
    if not test_c:
        test_c = Client(
            telegram_id="pm_test_999",
            name="PM Test Client",
            money_balance_kopeks=100000,
            allowed_price_monitoring=False,
        )
        db_session.add(test_c)
        db_session.commit()
        db_session.refresh(test_c)

    # Toggle access and set override price
    resp = admin_client.post(
        f"/api/price-monitoring/clients/{test_c.id}",
        json={"allowed": True, "custom_price_rub": 35.0},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Refresh client and check
    db_session.refresh(test_c)
    assert test_c.allowed_price_monitoring is True

    # Verify effective price in billing
    eff_price = effective_price_kopeks(db_session, test_c, KIND_PRICE_MONITORING)
    assert eff_price == 3500

    # Clean up
    db_session.delete(test_c)
    db_session.commit()


def test_charge_price_monitoring_job(db_session):
    # Create test client with 10,000 kopeks balance
    test_c = Client(
        telegram_id="pm_billing_client",
        name="Billing Test Client",
        money_balance_kopeks=10000,
        allowed_price_monitoring=True,
    )
    db_session.add(test_c)
    db_session.commit()
    db_session.refresh(test_c)

    job = Job(
        client_id=test_c.id,
        mode="price_monitoring",
        status="completed",
        title="Test Spec",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Scenario 1: 0 items found -> charged 0
    charged_zero = charge_price_monitoring_job(db_session, job, found_count=0, price_per_item_kopeks=5000)
    assert charged_zero == 0
    db_session.refresh(test_c)
    assert test_c.money_balance_kopeks == 10000  # unchanged!

    # Scenario 2: 2 items found with price 5000 kopeks -> charged 10000
    charged_two = charge_price_monitoring_job(db_session, job, found_count=2, price_per_item_kopeks=5000)
    assert charged_two == 10000
    db_session.refresh(test_c)
    assert test_c.money_balance_kopeks == 0  # 10000 - 10000 = 0

    # Cleanup
    db_session.query(BillingTransaction).filter(BillingTransaction.client_id == test_c.id).delete()
    db_session.delete(job)
    db_session.delete(test_c)
    db_session.commit()
