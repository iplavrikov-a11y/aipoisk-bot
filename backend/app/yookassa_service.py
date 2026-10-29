"""YooKassa API v3 integration for TenderLex."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

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
