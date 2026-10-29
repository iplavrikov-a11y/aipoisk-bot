from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import CallbackQuery
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.models import Client, Invoice, SystemSettings, TariffPackage, YooKassaPayment, new_id
from app.repository import get_or_create_settings
from app.bot import (
    PENDING_B2B_CUSTOM_AMOUNT,
    PENDING_B2B_INN,
    PENDING_B2B_NAME,
    PENDING_CUSTOM_TOPUP,
    _clear_pending_state,
    _generate_and_send_b2b_invoice,
    _initiate_yookassa_checkout,
    _tariffs_text,
    cabinet_inline_keyboard,
    check_yk_callback,
    low_balance_inline_keyboard,
    status_inline_keyboard,
    tariffs_inline_keyboard,
    topup_b2b_keyboard,
    topup_b2b_pkg_callback,
    topup_online_keyboard,
    topup_yk_pkg_callback,
)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_bot_keyboards_include_yookassa_and_b2b(setup_database: Session):
    db = setup_database
    # Tariffs keyboard
    kb_tariffs = tariffs_inline_keyboard("https://tenderlex.ru/cabinet")
    cb_tariffs = [btn.callback_data for row in kb_tariffs.inline_keyboard for btn in row if btn.callback_data]
    urls_tariffs = [btn.url for row in kb_tariffs.inline_keyboard for btn in row if btn.url]
    assert "topup_online_menu" in cb_tariffs
    assert "topup_b2b_menu" in cb_tariffs
    assert "https://tenderlex.ru/cabinet" in urls_tariffs

    # Cabinet keyboard
    kb_cabinet = cabinet_inline_keyboard("https://tenderlex.ru/cabinet")
    cb_cabinet = [btn.callback_data for row in kb_cabinet.inline_keyboard for btn in row if btn.callback_data]
    assert "topup_online_menu" in cb_cabinet
    assert "topup_b2b_menu" in cb_cabinet

    # Status keyboard
    kb_status = status_inline_keyboard()
    cb_status = [btn.callback_data for row in kb_status.inline_keyboard for btn in row if btn.callback_data]
    assert "topup_online_menu" in cb_status
    assert "topup_b2b_menu" in cb_status

    # Low balance keyboard
    settings = db.query(SystemSettings).first() or SystemSettings(id="default")
    kb_low = low_balance_inline_keyboard(settings)
    cb_low = [btn.callback_data for row in kb_low.inline_keyboard for btn in row if btn.callback_data]
    assert "topup_online_menu" in cb_low
    assert "topup_b2b_menu" in cb_low


def test_topup_package_keyboards(setup_database: Session):
    db = setup_database
    packages = [
        TariffPackage(id="pkg_start", name="Старт", price_kopeks=100000, bonus_kopeks=0, kind="deposit"),
        TariffPackage(id="pkg_pro", name="Про", price_kopeks=500000, bonus_kopeks=150000, badge="popular", kind="deposit"),
    ]

    kb_online = topup_online_keyboard(packages)
    callbacks_online = [btn.callback_data for row in kb_online.inline_keyboard for btn in row if btn.callback_data]
    assert "topup_yk_pkg_pkg_start" in callbacks_online
    assert "topup_yk_pkg_pkg_pro" in callbacks_online
    assert "topup_yk_custom" in callbacks_online
    assert "topup_b2b_menu" in callbacks_online

    kb_b2b = topup_b2b_keyboard(packages)
    callbacks_b2b = [btn.callback_data for row in kb_b2b.inline_keyboard for btn in row if btn.callback_data]
    assert "topup_b2b_pkg_pkg_start" in callbacks_b2b
    assert "topup_b2b_pkg_pkg_pro" in callbacks_b2b
    assert "topup_b2b_custom" in callbacks_b2b
    assert "topup_online_menu" in callbacks_b2b


def test_clear_pending_state_resets_payment_flags():
    chat_id = 999123
    PENDING_CUSTOM_TOPUP.add(chat_id)
    PENDING_B2B_CUSTOM_AMOUNT.add(chat_id)
    PENDING_B2B_INN[chat_id] = {"amount_rub": 5000}
    PENDING_B2B_NAME[chat_id] = {"buyer_inn": "7707083893"}

    had_state = _clear_pending_state(chat_id)
    assert had_state is True
    assert chat_id not in PENDING_CUSTOM_TOPUP
    assert chat_id not in PENDING_B2B_CUSTOM_AMOUNT
    assert chat_id not in PENDING_B2B_INN
    assert chat_id not in PENDING_B2B_NAME


def test_tariffs_text_renders_clean_payment_instructions(setup_database: Session):
    db = setup_database
    settings = db.query(SystemSettings).first() or SystemSettings(id="default")
    text = _tariffs_text(db, settings)
    assert "Онлайн через ЮKassa" in text
    assert "банковские карты" in text
    assert "По безналичному расчёту" in text
    assert "напишите владельцу в Telegram" not in text


@pytest.mark.asyncio
async def test_topup_yk_pkg_callback_executes_cleanly(setup_database: Session):
    db = setup_database
    settings = get_or_create_settings(db)
    settings.payment_provider = "yookassa"
    settings.yookassa_shop_id = "1509607"
    settings.yookassa_secret_key = "test_key"
    db.commit()

    pkg_id = new_id()
    pkg = TariffPackage(id=pkg_id, name="Оптимальный", price_kopeks=300000, bonus_kopeks=50000, kind="deposit")
    db.add(pkg)
    db.commit()

    user = MagicMock()
    user.id = 555444
    user.username = "payer"
    user.full_name = "Payer Full"

    mock_msg = AsyncMock()
    mock_msg.edit_text = AsyncMock()

    callback = AsyncMock(spec=CallbackQuery)
    callback.data = f"topup_yk_pkg_{pkg_id}"
    callback.from_user = user
    callback.message = mock_msg
    callback.bot = AsyncMock()
    callback.bot.get_me.return_value = MagicMock(username="tenderlex_bot")
    callback.answer = AsyncMock()

    mock_pid = f"test_payment_id_{new_id()}"
    mock_payment_data = {
        "id": mock_pid,
        "status": "pending",
        "amount": {"value": "3000.00", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=test1234",
        },
    }

    with patch("app.bot.create_yookassa_payment", return_value=mock_payment_data), \
         patch("app.bot.notify_admin_payment_attempt"):

        await topup_yk_pkg_callback(callback)

        fresh_db = SessionLocal()
        yk = fresh_db.query(YooKassaPayment).filter(YooKassaPayment.payment_id == mock_pid).first()
        fresh_db.close()
        assert yk is not None
        assert yk.amount_rub == 3000
        assert yk.bonus_rub == 500
        assert yk.total_credit_rub == 3500
        mock_msg.edit_text.assert_called_once()
        sent_text = mock_msg.edit_text.call_args[0][0]
        assert "Счёт на оплату через ЮKassa готов!" in sent_text
        assert "3 000 ₽" in sent_text


@pytest.mark.asyncio
async def test_topup_b2b_pkg_callback_executes_cleanly(setup_database: Session):
    db = setup_database
    pkg_id = new_id()
    pkg = TariffPackage(id=pkg_id, name="Про", price_kopeks=500000, bonus_kopeks=150000, kind="deposit")
    db.add(pkg)
    db.commit()

    user = MagicMock()
    user.id = 555444
    user.username = "payer"
    user.full_name = "Payer Full"

    mock_msg = AsyncMock()
    mock_msg.chat.id = 555444
    mock_msg.edit_text = AsyncMock()

    callback = AsyncMock()
    callback.data = f"topup_b2b_pkg_{pkg_id}"
    callback.from_user = user
    callback.message = mock_msg
    callback.answer = AsyncMock()

    await topup_b2b_pkg_callback(callback)

    assert 555444 in PENDING_B2B_INN
    assert PENDING_B2B_INN[555444]["amount_rub"] == 5000
    assert PENDING_B2B_INN[555444]["credit_rub"] == 6500

    callback.answer.assert_called_once()
    mock_msg.edit_text.assert_called_once()
    sent_text = mock_msg.edit_text.call_args[0][0]
    assert "Счёт на сумму 5 000 ₽" in sent_text
    assert "ИНН вашей организации или ИП" in sent_text


@pytest.mark.asyncio
async def test_initiate_yookassa_checkout_in_bot(setup_database: Session):
    db = setup_database
    settings = get_or_create_settings(db)
    settings.payment_provider = "yookassa"
    settings.yookassa_shop_id = "1509607"
    settings.yookassa_secret_key = "test_key"
    db.commit()

    c_id = new_id()
    client = Client(id=c_id, telegram_id="999888", name="Bot Buyer", money_balance_kopeks=0)
    db.add(client)
    db.commit()

    user = MagicMock()
    user.id = 999888
    user.username = "botuser"
    user.full_name = "Bot User"

    target = AsyncMock()
    target.bot.get_me.return_value = MagicMock(username="tenderlex_bot")
    target.answer = AsyncMock()
    target.message = None

    mock_payment_data = {
        "id": "2d89b142-000f-5000-8000-1c0b39be82ee",
        "status": "pending",
        "amount": {"value": "5000.00", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=test",
        },
    }

    with patch("app.bot.create_yookassa_payment", return_value=mock_payment_data), \
         patch("app.bot.notify_admin_payment_attempt") as mock_notify:

        await _initiate_yookassa_checkout(
            target=target,
            db=db,
            settings=settings,
            client=client,
            user=user,
            amount_rub=5000,
            bonus_rub=1500,
            credit_rub=6500,
            package_name="Тариф Про",
        )

        rec = db.query(YooKassaPayment).filter(YooKassaPayment.payment_id == "2d89b142-000f-5000-8000-1c0b39be82ee").first()
        assert rec is not None
        assert rec.amount_rub == 5000
        assert rec.bonus_rub == 1500
        assert rec.total_credit_rub == 6500
        assert rec.status == "pending"
        assert rec.client_id == client.id
        mock_notify.assert_called_once()


@pytest.mark.asyncio
async def test_generate_and_send_b2b_invoice_in_bot(setup_database: Session):
    db = setup_database
    c_id = new_id()
    client = Client(id=c_id, telegram_id="777666", name="B2B Org", money_balance_kopeks=0)
    db.add(client)
    db.commit()

    user = MagicMock()
    user.id = 777666
    user.username = "b2b_leader"
    user.full_name = "B2B Leader"

    message = AsyncMock()
    message.answer = AsyncMock()
    message.answer_document = AsyncMock()

    ctx = {
        "amount_rub": 10000,
        "bonus_rub": 4000,
        "credit_rub": 14000,
        "package_name": "Тариф Бизнес",
    }

    with patch("app.bot.generate_invoice_pdf", return_value=""), \
         patch("app.bot.generate_invoice_xlsx", return_value=""), \
         patch("app.bot.notify_admin_invoice_telegram", new_callable=AsyncMock) as mock_alert:

        await _generate_and_send_b2b_invoice(
            message=message,
            db=db,
            user=user,
            ctx=ctx,
            buyer_inn="7707083893",
            buyer_name="ПАО СБЕРБАНК",
            buyer_kpp="773601001",
            buyer_address="г Москва, ул Вавилова, д 19",
        )

        inv = db.query(Invoice).filter(Invoice.buyer_inn == "7707083893").first()
        assert inv is not None
        assert inv.amount_rub == 10000
        assert inv.bonus_rub == 4000
        assert inv.total_credit_rub == 14000
        assert inv.buyer_name == "ПАО СБЕРБАНК"
        assert inv.client_id == client.id

        message.answer.assert_called_once()
        sent_text = message.answer.call_args[0][0]
        assert "Счёт на оплату №" in sent_text
        assert "ПАО СБЕРБАНК" in sent_text
        assert "7707083893" in sent_text
        assert "10 000 ₽" in sent_text
        assert "14 000 ₽" in sent_text
        assert "АЛЬФА-БАНК" in sent_text
        mock_alert.assert_called_once()
