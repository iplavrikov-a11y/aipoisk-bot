from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import config
from app.invoice_service import notify_invoice_payment_proof, notify_admin_telegram
from app.models import Invoice


@pytest.mark.asyncio
async def test_payment_proof_telegram_sends_file_and_escapes_payer(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "bot_token", "fixture-token")
    monkeypatch.setattr(config, "owner_telegram_id", "12345")
    file = tmp_path / "proof.pdf"
    file.write_bytes(b"%PDF-fixture")
    invoice = Invoice(invoice_number="TEST-42", buyer_name="ООО А & Б", amount_rub=5000, proof_original_name="proof.pdf", proof_content_type="application/pdf")
    response = MagicMock(is_success=True, status_code=200)
    response.json.return_value = {"ok": True}
    telegram = AsyncMock()
    telegram.post.return_value = response
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = telegram
    with patch("app.invoice_service.httpx.AsyncClient", factory):
        await notify_invoice_payment_proof(invoice, str(file), _allow_in_test=True)
    request = telegram.post.call_args
    assert request.args[0].endswith("/sendDocument")
    assert request.kwargs["data"]["chat_id"] == "12345"
    assert "А &amp; Б" in request.kwargs["data"]["caption"]
    assert request.kwargs["files"]["document"][0] == "proof.pdf"


@pytest.mark.asyncio
async def test_invoice_issued_notification_escapes_customer_data(monkeypatch):
    monkeypatch.setattr(config, "bot_token", "fixture-token")
    monkeypatch.setattr(config, "owner_telegram_id", "12345")
    invoice = Invoice(invoice_number="TEST-43", buyer_name="ООО А & Б", buyer_inn="123", buyer_address="<офис>", amount_rub=5000, bonus_rub=0, total_credit_rub=5000, tariff_name="Пакет", buyer_email="test@example.invalid")
    response = MagicMock(is_success=True, status_code=200)
    response.json.return_value = {"ok": True}
    telegram = AsyncMock()
    telegram.post.return_value = response
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = telegram
    with patch("app.invoice_service.httpx.AsyncClient", factory):
        await notify_admin_telegram(invoice, _allow_in_test=True)
    sent_text = telegram.post.call_args.kwargs["json"]["text"]
    assert "А &amp; Б" in sent_text
    assert "&lt;офис&gt;" in sent_text

