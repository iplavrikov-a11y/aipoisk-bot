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


@pytest.mark.asyncio
async def test_handle_document_in_exact_product_scenario(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from app.bot import handle_document, PENDING_MODES, PENDING_UPLOADS, SCENARIO_EXACT_PRODUCT, MODE_EXACT_PRODUCT

    chat_id = 999888777
    PENDING_MODES[chat_id] = SCENARIO_EXACT_PRODUCT
    PENDING_UPLOADS.pop(chat_id, None)

    message = MagicMock()
    message.chat.id = chat_id
    message.from_user.id = chat_id
    message.from_user.username = "testuser"
    message.from_user.full_name = "Test User"
    message.caption = None
    message.document.file_name = "tz.docx"
    message.document.file_id = "doc123"
    message.document.file_size = 15000
    message.answer = AsyncMock()

    bot = MagicMock()

    async def fake_download(*args, **kwargs):
        return "tz.docx", b"fake docx binary content"

    monkeypatch.setattr("app.bot._download_document_content", fake_download)

    # Ensure client has balance
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.telegram_id == str(chat_id)).first()
        if not client:
            client = Client(id=f"test_client_{chat_id}", telegram_id=str(chat_id), is_active=True, money_balance_kopeks=10000)
            db.add(client)
            db.commit()
    finally:
        db.close()

    await handle_document(message, bot)

    assert message.answer.called
    pending = PENDING_UPLOADS.get(chat_id)
    assert pending is not None
    assert pending.mode == MODE_EXACT_PRODUCT
    assert len(pending.files) == 1
    assert pending.files[0][0] == "tz.docx"

