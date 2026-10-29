"""YooKassa API v3 integration for TenderLex."""

from __future__ import annotations

import asyncio
from html import escape as html_escape
import logging
import os
import threading
import uuid
from typing import Any

import httpx

from .config import config

logger = logging.getLogger("tenderlex.yookassa")

YOOKASSA_API_BASE = "https://api.yookassa.ru/v3"
DEFAULT_TIMEOUT_SECONDS = 20.0


class YooKassaError(Exception):
    """Base error for YooKassa integration."""


def create_yookassa_payment(
    *,
    shop_id: str,
    secret_key: str,
    amount_rub: int,
    return_url: str,
    description: str,
    metadata: dict[str, Any] | None = None,
    customer_email: str | None = None,
    send_receipt: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Create a new payment session in YooKassa v3.

    Returns the parsed payment response containing id, status, and confirmation.confirmation_url.
    """
    clean_shop_id = str(shop_id or "").strip()
    clean_secret_key = str(secret_key or "").strip()
    if not clean_shop_id or not clean_secret_key:
        raise YooKassaError("Shop ID или Секретный ключ ЮKassa не настроены")

    safe_amount = max(1, int(amount_rub))
    clean_desc = str(description or "Пополнение баланса TenderLex").strip()[:128]
    clean_return_url = str(return_url or "https://tenderlex.ru/cabinet").strip()
    safe_metadata = {str(k): str(v) for k, v in (metadata or {}).items()}

    def _build_payload(with_receipt: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "amount": {
                "value": f"{safe_amount:.2f}",
                "currency": "RUB",
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": clean_return_url,
            },
            "description": clean_desc,
            "metadata": safe_metadata,
        }
        if with_receipt and customer_email and "@" in customer_email:
            body["receipt"] = {
                "customer": {
                    "email": customer_email.strip(),
                },
                "items": [
                    {
                        "description": clean_desc,
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{safe_amount:.2f}",
                            "currency": "RUB",
                        },
                        "vat_code": 1,  # 1 = без НДС (УСН/ПСН)
                        "payment_mode": "full_payment",
                        "payment_subject": "service",
                    }
                ],
            }
        return body

    idempotency_key = str(uuid.uuid4())
    headers = {
        "Idempotence-Key": idempotency_key,
        "Content-Type": "application/json",
    }
    auth = httpx.BasicAuth(clean_shop_id, clean_secret_key)
    url = f"{YOOKASSA_API_BASE}/payments"

    payload = _build_payload(with_receipt=bool(send_receipt and customer_email))

    with httpx.Client(timeout=timeout_seconds) as client:
        try:
            resp = client.post(url, json=payload, headers=headers, auth=auth)
        except httpx.RequestError as exc:
            logger.error("YooKassa network error during create_payment: %s", exc)
            raise YooKassaError(f"Ошибка сети при обращении к ЮKassa: {exc}") from exc

        # Handle receipt fallback: if receipt was required or rejected by YooKassa
        if resp.status_code == 400:
            try:
                err_json = resp.json()
            except Exception:
                err_json = {}
            err_code = str(err_json.get("code") or "")
            err_desc = str(err_json.get("description") or "").lower()

            # If receipt is required by shop but wasn't sent, retry with receipt
            if not payload.get("receipt") and ("receipt" in err_desc or "чек" in err_desc) and customer_email:
                logger.info("YooKassa requires receipt, retrying with receipt data...")
                payload_with_receipt = _build_payload(with_receipt=True)
                retry_key = str(uuid.uuid4())
                headers["Idempotence-Key"] = retry_key
                try:
                    resp = client.post(url, json=payload_with_receipt, headers=headers, auth=auth)
                except httpx.RequestError as exc:
                    raise YooKassaError(f"Ошибка сети при повторе к ЮKassa: {exc}") from exc

            # Or if receipt was sent but shop has no fiscalization enabled, retry without receipt
            elif payload.get("receipt") and ("receipt" in err_desc or "fiscalization" in err_desc):
                logger.info("YooKassa rejected receipt, retrying without receipt data...")
                payload_no_receipt = _build_payload(with_receipt=False)
                retry_key = str(uuid.uuid4())
                headers["Idempotence-Key"] = retry_key
                try:
                    resp = client.post(url, json=payload_no_receipt, headers=headers, auth=auth)
                except httpx.RequestError as exc:
                    raise YooKassaError(f"Ошибка сети при повторе к ЮKassa: {exc}") from exc

        if resp.status_code not in (200, 201):
            try:
                err_json = resp.json()
                err_msg = err_json.get("description") or err_json.get("code") or resp.text
            except Exception:
                err_msg = resp.text
            logger.error("YooKassa create_payment failed [%s]: %s", resp.status_code, err_msg)
            raise YooKassaError(f"ЮKassa вернула ошибку [{resp.status_code}]: {err_msg}")

        data = resp.json()
        return data


def fetch_yookassa_payment(
    *,
    shop_id: str,
    secret_key: str,
    payment_id: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any] | None:
    """Fetch live payment details from YooKassa v3 by payment_id."""
    clean_shop_id = str(shop_id or "").strip()
    clean_secret_key = str(secret_key or "").strip()
    clean_payment_id = str(payment_id or "").strip()
    if not clean_shop_id or not clean_secret_key or not clean_payment_id:
        return None

    auth = httpx.BasicAuth(clean_shop_id, clean_secret_key)
    url = f"{YOOKASSA_API_BASE}/payments/{clean_payment_id}"

    with httpx.Client(timeout=timeout_seconds) as client:
        try:
            resp = client.get(url, auth=auth)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
            logger.warning("YooKassa fetch_payment returned status %s for %s", resp.status_code, clean_payment_id)
            return None
        except httpx.RequestError as exc:
            logger.error("YooKassa network error during fetch_payment: %s", exc)
            return None


def verify_yookassa_credentials(
    *,
    shop_id: str,
    secret_key: str,
    timeout_seconds: float = 10.0,
) -> tuple[bool, str]:
    """Test if Shop ID and Secret Key are valid by making a lightweight query."""
    clean_shop_id = str(shop_id or "").strip()
    clean_secret_key = str(secret_key or "").strip()
    if not clean_shop_id or not clean_secret_key:
        return False, "Не заполнены Shop ID или Секретный ключ"

    auth = httpx.BasicAuth(clean_shop_id, clean_secret_key)
    url = f"{YOOKASSA_API_BASE}/me"

    with httpx.Client(timeout=timeout_seconds) as client:
        try:
            resp = client.get(url, auth=auth)
            if resp.status_code == 200:
                return True, "Подключение к ЮKassa успешно проверено"
            if resp.status_code in (401, 403):
                return False, "Неверный Shop ID или Секретный ключ ЮKassa"
            return False, f"ЮKassa вернула статус {resp.status_code}"
        except httpx.RequestError as exc:
            return False, f"Ошибка сети при проверке ЮKassa: {exc}"


def format_payment_method_type(pm_type: str | None) -> str:
    mapping = {
        "bank_card": "💳 Банковская карта",
        "sbp": "⚡ СБП (Система быстрых платежей)",
        "sber_pay": "🟢 SberPay",
        "sber_b2b": "🟢 SberPay B2B",
        "tinkoff_bank": "🟡 T-Pay",
        "mir_pay": "🇷🇺 Mir Pay",
        "yoo_money": "🟣 ЮMoney",
    }
    return mapping.get(str(pm_type or "").lower(), "Онлайн-оплата (ЮKassa)")


async def _send_yookassa_telegram_alert(text: str) -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    bot_token = config.bot_token
    owner_id = str(config.owner_telegram_id or "").strip()
    if not bot_token or not owner_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": owner_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(url, json=payload)
    except Exception as exc:
        logger.warning("Failed to send telegram yookassa alert: %s", exc)


def dispatch_yookassa_telegram_alert(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()
    except Exception:
        pass


def notify_admin_payment_attempt(
    *,
    payment_id: str,
    amount_rub: int,
    bonus_rub: int,
    total_credit_rub: int,
    package_name: str,
    user_email: str,
    client_name: str = "",
) -> None:
    bonus_str = f" (+{bonus_rub:,} ₽ бонус)" if bonus_rub else ""
    client_info = f" ({html_escape(client_name)})" if client_name and client_name != user_email else ""
    text = (
        f"💳 <b>Новая попытка онлайн-оплаты (ЮKassa)</b>\n\n"
        f"<b>Пользователь:</b> {html_escape(user_email)}{client_info}\n"
        f"<b>Сумма к оплате:</b> <b>{amount_rub:,} ₽</b>\n"
        f"<b>Поступит на баланс:</b> {total_credit_rub:,} ₽{bonus_str}\n"
        f"<b>Тариф:</b> {html_escape(package_name)}\n"
        f"<b>ID платежа:</b> <code>{html_escape(payment_id)}</code>\n\n"
        f"<i>Клиент перешел на страницу оплаты. Ожидаем подтверждения...</i>"
    )
    dispatch_yookassa_telegram_alert(_send_yookassa_telegram_alert(text))


def notify_admin_payment_success(
    *,
    payment_id: str,
    amount_rub: int,
    bonus_rub: int,
    total_credit_rub: int,
    package_name: str,
    user_email: str,
    client_name: str = "",
    payment_method_type: str = "",
) -> None:
    bonus_str = f" (+{bonus_rub:,} ₽ бонус)" if bonus_rub else ""
    client_info = f" ({html_escape(client_name)})" if client_name and client_name != user_email else ""
    pm_name = format_payment_method_type(payment_method_type)
    text = (
        f"🎉 <b>Успешная оплата через ЮKassa!</b>\n\n"
        f"<b>Пользователь:</b> {html_escape(user_email)}{client_info}\n"
        f"<b>Сумма оплаты:</b> <b>{amount_rub:,} ₽</b>\n"
        f"<b>Зачислено на баланс:</b> <b>{total_credit_rub:,} ₽</b>{bonus_str}\n"
        f"<b>Способ:</b> {pm_name}\n"
        f"<b>Тариф:</b> {html_escape(package_name)}\n"
        f"<b>ID платежа:</b> <code>{html_escape(payment_id)}</code>\n\n"
        f"✅ <i>Баланс клиента моментально пополнен. Чек 54-ФЗ отправлен.</i>"
    )
    dispatch_yookassa_telegram_alert(_send_yookassa_telegram_alert(text))


def notify_admin_payment_canceled(
    *,
    payment_id: str,
    amount_rub: int,
    package_name: str,
    user_email: str,
    client_name: str = "",
    reason: str = "",
) -> None:
    client_info = f" ({html_escape(client_name)})" if client_name and client_name != user_email else ""
    reason_line = f"<b>Причина:</b> {html_escape(reason)}\n" if reason else ""
    text = (
        f"⚠️ <b>Оплата ЮKassa не завершена / отменена</b>\n\n"
        f"<b>Пользователь:</b> {html_escape(user_email)}{client_info}\n"
        f"<b>Сумма:</b> {amount_rub:,} ₽\n"
        f"<b>Тариф:</b> {html_escape(package_name)}\n"
        f"{reason_line}"
        f"<b>ID платежа:</b> <code>{html_escape(payment_id)}</code>"
    )
    dispatch_yookassa_telegram_alert(_send_yookassa_telegram_alert(text))


