import pytest
from app.bot import _tariffs_text, _cabinet_text, _exact_product_scenario_text
from app.db import SessionLocal
from app.models import Client, SystemSettings, TariffPackage
from app.repository import get_or_create_settings


def test_tariffs_text_includes_exact_product():
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        text = _tariffs_text(db, settings)
        assert "🎯 Подбор товара и аналогов:" in text
        assert "99 ₽" in text
    finally:
        db.close()


def test_cabinet_text_includes_exact_product():
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        client = db.query(Client).first()
        if not client:
            client = Client(id="test_client_id", telegram_id="123456", is_active=True)
            db.add(client)
            db.commit()
        text = _cabinet_text(db, client, settings)
        assert "Подбор точного товара" in text or "Подбор товара" in text or "Товар" in text
    finally:
        db.close()


def test_exact_product_scenario_text():
    text = _exact_product_scenario_text()
    assert "🎯 Подбор товара и аналогов" in text
    assert "Минпромторга" in text
