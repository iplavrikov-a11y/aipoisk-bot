"""Configured delivery surcharge must agree across billing and client displays."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.billing import (
    KIND_PRICE_MONITORING,
    KIND_SUPPLIER_SEARCH,
    KIND_SUPPLIER_SEARCH_EXTRA,
    _reservable_amount_for_kind,
    reserve_additional_job_units,
)
from app.db import Base
from app.main import customer_user_to_dict, public_site_payload
from app.models import BillingTransaction, Client, ClientTariffOverride, Job, SystemSettings, WebUser


@pytest.fixture
def geo_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        settings = SystemSettings(geo_radius_search_enabled_global=True)
        client = Client(telegram_id="geo-contract", money_balance_kopeks=100_000)
        db.add_all([settings, client])
        db.commit()
        yield db, settings, client
    engine.dispose()


@pytest.mark.parametrize("percentage,expected", [(0, 10_000), (10, 11_000), (30, 13_000)])
@pytest.mark.parametrize("kind", [KIND_SUPPLIER_SEARCH, KIND_SUPPLIER_SEARCH_EXTRA, KIND_PRICE_MONITORING])
def test_configured_surcharge_is_used_in_reservation(geo_db, percentage, expected, kind):
    db, settings, client = geo_db
    settings.geo_radius_surcharge_pct = percentage
    db.add(ClientTariffOverride(client_id=client.id, kind=kind, price_kopeks=10_000))
    db.commit()
    job = Job(client_id=client.id, mode=KIND_SUPPLIER_SEARCH if kind == KIND_SUPPLIER_SEARCH_EXTRA else kind, geo_radius_km=300, delivery_city="Казань")

    assert _reservable_amount_for_kind(db, client, kind, 1, job=job) == expected
    assert _reservable_amount_for_kind(db, client, kind, 1) == 10_000


@pytest.mark.parametrize("percentage", [0, 10, 30])
def test_surcharge_agrees_in_admin_public_and_customer_views(geo_db, percentage):
    db, settings, client = geo_db
    settings.geo_radius_surcharge_pct = percentage
    user = WebUser(email="geo@example.invalid", password_hash="fixture", client_id=client.id)
    db.add(user)
    db.commit()

    assert settings.to_dict()["geo_radius_surcharge_pct"] == percentage
    assert public_site_payload(db)["geo_radius"]["surcharge_pct"] == percentage
    assert customer_user_to_dict(db, user)["geo_radius_surcharge_pct"] == percentage


@pytest.mark.parametrize("percentage,expected", [(0, 10_000), (10, 11_000), (30, 13_000)])
def test_additional_supplier_units_reserve_actual_geo_price(geo_db, percentage, expected):
    db, settings, client = geo_db
    settings.geo_radius_surcharge_pct = percentage
    db.add(ClientTariffOverride(client_id=client.id, kind=KIND_SUPPLIER_SEARCH, price_kopeks=10_000))
    job = Job(client_id=client.id, mode=KIND_SUPPLIER_SEARCH, geo_radius_km=300, delivery_city="Казань")
    db.add(job)
    db.commit()
    reserve_additional_job_units(db, client, job, additional_units=2)
    transaction = db.query(BillingTransaction).filter_by(job_id=job.id, operation="reserve").one()
    assert transaction.amount_kopeks == 2 * expected
    assert client.money_reserved_kopeks == 2 * expected


@pytest.mark.parametrize("percentage,radius,expected", [(0, 300, 10_000), (10, 300, 11_000), (30, 300, 13_000), (30, None, 10_000)])
def test_monitoring_worker_charge_and_evidence_use_geo_price(geo_db, monkeypatch, tmp_path, percentage, radius, expected):
    import json
    from app import jobs
    from app.price_monitoring import cleaner
    from app.price_monitoring.models import BatchMonitoringResult, ItemPriceResult, SupplierQuote

    db, settings, client = geo_db
    settings.geo_radius_surcharge_pct = percentage
    db.add(ClientTariffOverride(client_id=client.id, kind=KIND_PRICE_MONITORING, price_kopeks=10_000))
    job = Job(client_id=client.id, mode=KIND_PRICE_MONITORING, geo_radius_km=radius, delivery_city="Казань" if radius else "", status="running", title="Тест")
    db.add(job)
    db.commit()
    monkeypatch.setattr(jobs, "job_dir", lambda _id: tmp_path)
    monkeypatch.setattr(jobs, "_check_cancelled", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(jobs, "_populate_job_ai_metadata", lambda *_args: None)
    from unittest.mock import AsyncMock
    from app.position_selection import read_selection, confirm_position_selection
    monkeypatch.setattr(jobs, "prepare_job_product_positions", AsyncMock(return_value=[{"position_no": 1, "name": "Товар", "unit": "шт"}]))

    async def fake_pipeline(**kwargs):
        assert kwargs["price_per_position_rub"] == expected / 100
        item = ItemPriceResult(1, "Товар", "Товар", "шт", quotes=[SupplierQuote(company_name="Тест", price_rub=100, url="https://example.invalid/item")], status="found")
        return BatchMonitoringResult(job_id=job.id, items=[item], total_positions=1, found_positions=1, not_found_positions=0, price_per_position_rub=expected / 100, total_charged_rub=expected / 100)

    monkeypatch.setattr(jobs, "run_price_monitoring_pipeline", fake_pipeline)
    jobs._process_price_monitoring(db, job, settings, "Товар")
    assert job.status == "awaiting_position_selection"
    preview = read_selection(job)
    assert preview["price_kopeks"] == expected
    assert db.query(BillingTransaction).filter_by(job_id=job.id).count() == 0
    confirm_position_selection(db, job, preview["revision"], [preview["items"][0]["id"]])
    job.status = "running"
    db.commit()
    jobs._process_price_monitoring(db, job, settings, "Товар")
    transaction = db.query(BillingTransaction).filter_by(job_id=job.id, operation="charge").one()
    evidence = json.loads((tmp_path / "output/evidence.json").read_text())
    assert job.status == "completed"
    assert transaction.amount_kopeks == expected
    assert client.money_balance_kopeks == 100_000 - expected
    assert evidence["price_per_position_rub"] == expected / 100
    assert evidence["charged_rub"] == expected / 100
