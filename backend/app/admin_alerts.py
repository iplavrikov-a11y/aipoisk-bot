"""
System and infrastructure alert dispatcher for TenderLex administrator/owner.

Notifies the owner via Telegram (AIPOISK_OWNER_TELEGRAM_ID) when critical services fail:
- Yandex Search API (balance depleted, 403 PermissionDenied, quota errors)
- AI providers (401 invalid key, 402 payment required, 429 quota exhaustion)
- DaData / external data sources
- Unhandled customer job failures caused by external service outages

Includes intelligent throttling and deduplication so identical alerts do not spam the owner.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
import jwt

from .config import config

logger = logging.getLogger(__name__)

DEFAULT_YANDEX_BILLING_ACCOUNT_ID = "dn2i7mph462v2u6ff922"
DEFAULT_YANDEX_FOLDER_ID = "b1gmnp1u8urslual8ht8"


def get_yandex_billing_console_url(billing_account_id: str = DEFAULT_YANDEX_BILLING_ACCOUNT_ID) -> str:
    acc_id = (billing_account_id or DEFAULT_YANDEX_BILLING_ACCOUNT_ID).strip()
    return f"https://console.yandex.cloud/billing/accounts/{acc_id}"


def yandex_billing_inline_markup(
    billing_account_id: str = DEFAULT_YANDEX_BILLING_ACCOUNT_ID,
    *,
    include_folder_link: bool = False,
) -> dict[str, Any]:
    """Build Telegram Bot API InlineKeyboardMarkup dict for Yandex Cloud billing alerts."""
    rows: list[list[dict[str, str]]] = [
        [
            {
                "text": "💳 Пополнить баланс (Яндекс.Облако)",
                "url": get_yandex_billing_console_url(billing_account_id),
            }
        ],
        [
            {
                "text": "🔄 Проверить баланс сейчас",
                "callback_data": "owner_check_yc_balance",
            }
        ],
    ]
    if include_folder_link:
        rows.append(
            [
                {
                    "text": "📊 Открыть консоль каталога",
                    "url": f"https://console.yandex.cloud/folders/{DEFAULT_YANDEX_FOLDER_ID}",
                }
            ]
        )
    return {"inline_keyboard": rows}


async def query_yandex_billing_balance_live() -> dict[str, Any]:
    """
    Fetch real-time Yandex Cloud billing account balance directly via IAM + Billing API
    without any intermediate cache.
    """
    key_path = Path(__file__).resolve().parent.parent.parent / ".yandex_sa_key.json"
    if not key_path.exists():
        return {
            "balance": 0.0,
            "currency": "RUB",
            "is_active": False,
            "billing_account_id": DEFAULT_YANDEX_BILLING_ACCOUNT_ID,
            "error": "key_not_found",
        }

    try:
        with open(key_path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        service_account_id = obj.get("service_account_id")
        key_id = obj.get("id")
        private_key = obj.get("private_key")
        billing_id = obj.get("billing_account_id") or DEFAULT_YANDEX_BILLING_ACCOUNT_ID
        if not service_account_id or not key_id or not private_key:
            return {
                "balance": 0.0,
                "currency": "RUB",
                "is_active": False,
                "billing_account_id": billing_id,
                "error": "invalid_key",
            }

        now = int(time.time())
        payload = {
            "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            "iss": service_account_id,
            "iat": now,
            "exp": now + 3600,
        }
        encoded_token = jwt.encode(payload, private_key, algorithm="PS256", headers={"kid": key_id})

        async with httpx.AsyncClient(timeout=10.0) as client:
            iam_response = await client.post(
                "https://iam.api.cloud.yandex.net/iam/v1/tokens",
                json={"jwt": encoded_token},
            )
            if iam_response.status_code != 200:
                return {
                    "balance": 0.0,
                    "currency": "RUB",
                    "is_active": False,
                    "billing_account_id": billing_id,
                    "error": "iam_token_failed",
                }
            token = iam_response.json().get("iamToken")
            if not token:
                return {
                    "balance": 0.0,
                    "currency": "RUB",
                    "is_active": False,
                    "billing_account_id": billing_id,
                    "error": "iam_token_missing",
                }

            billing_response = await client.get(
                f"https://billing.api.cloud.yandex.net/billing/v1/billingAccounts/{billing_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if billing_response.status_code != 200:
                return {
                    "balance": 0.0,
                    "currency": "RUB",
                    "is_active": False,
                    "billing_account_id": billing_id,
                    "error": "billing_api_failed",
                }

            data = billing_response.json()
            balance_val = float(data.get("balance", 0.0))
            is_active_val = bool(data.get("active", False))
            return {
                "balance": balance_val,
                "currency": data.get("currency", "RUB"),
                "is_active": is_active_val,
                "billing_account_id": billing_id,
            }
    except Exception as exc:
        logger.warning("Failed to query live Yandex billing balance: %s", exc)
        return {
            "balance": 0.0,
            "currency": "RUB",
            "is_active": False,
            "billing_account_id": DEFAULT_YANDEX_BILLING_ACCOUNT_ID,
            "error": "exception",
        }

# In-memory throttle store: {deduplicate_key: timestamp_of_last_sent}
_ALERT_THROTTLE: dict[str, float] = {}

# Active incidents in memory for admin dashboard display: [{id, service, title, message, level, timestamp}]
_ACTIVE_INCIDENTS: list[dict[str, Any]] = []
_MAX_INCIDENTS = 50


def is_pytest() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def get_active_incidents(limit: int = 10) -> list[dict[str, Any]]:
    """Return recent active system incidents for the admin panel."""
    return sorted(_ACTIVE_INCIDENTS, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]


def record_incident(service: str, title: str, message: str, level: str = "critical") -> None:
    global _ACTIVE_INCIDENTS
    incident = {
        "id": f"{service}_{int(time.time())}",
        "service": service,
        "title": title,
        "message": message,
        "level": level,
        "timestamp": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    _ACTIVE_INCIDENTS.insert(0, incident)
    if len(_ACTIVE_INCIDENTS) > _MAX_INCIDENTS:
        _ACTIVE_INCIDENTS = _ACTIVE_INCIDENTS[:_MAX_INCIDENTS]


async def send_telegram_admin_alert(
    text: str,
    *,
    deduplicate_key: str = "",
    throttle_seconds: int = 900,
    reply_markup: dict[str, Any] | None = None,
) -> bool:
    """
    Send an HTML alert directly to the TenderLex owner's Telegram account.
    Returns True if sent, False if throttled, unconfigured, or in tests.
    """
    if is_pytest():
        logger.debug("Skipping admin alert in pytest: key=%s", deduplicate_key)
        return False

    bot_token = (config.bot_token or os.getenv("AIPOISK_BOT_TOKEN") or "").strip()
    owner_id = str(config.owner_telegram_id or os.getenv("AIPOISK_OWNER_TELEGRAM_ID") or "").strip()
    if not bot_token or not owner_id:
        logger.warning("Cannot send admin alert: bot_token or owner_telegram_id not configured")
        return False

    now = time.time()
    if deduplicate_key:
        last_sent = _ALERT_THROTTLE.get(deduplicate_key, 0.0)
        if (now - last_sent) < throttle_seconds:
            logger.info("Admin alert throttled (key=%s, remaining=%ds)", deduplicate_key, int(throttle_seconds - (now - last_sent)))
            return False
        _ALERT_THROTTLE[deduplicate_key] = now

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": owner_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info("Admin telegram alert sent: key=%s", deduplicate_key)
                return True
            else:
                logger.warning("Telegram alert failed: status=%s body=%s", resp.status_code, resp.text[:200])
                return False
    except Exception as exc:
        logger.warning("Error dispatching telegram alert to owner: %s", exc)
        return False


def dispatch_telegram_admin_alert(
    text: str,
    *,
    deduplicate_key: str = "",
    throttle_seconds: int = 900,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    """Non-blocking fire-and-forget alert dispatcher from synchronous or async contexts."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            send_telegram_admin_alert(
                text,
                deduplicate_key=deduplicate_key,
                throttle_seconds=throttle_seconds,
                reply_markup=reply_markup,
            )
        )
    except RuntimeError:
        # No running event loop in current thread: run synchronously in temporary loop or thread
        try:
            asyncio.run(
                send_telegram_admin_alert(
                    text,
                    deduplicate_key=deduplicate_key,
                    throttle_seconds=throttle_seconds,
                    reply_markup=reply_markup,
                )
            )
        except Exception as sync_exc:
            logger.warning("Failed sync dispatch of telegram alert: %s", sync_exc)


def notify_yandex_search_error(
    status_code: int,
    error_text: str,
    *,
    query: str = "",
    job_info: str = "",
    billing_account_id: str = DEFAULT_YANDEX_BILLING_ACCOUNT_ID,
) -> None:
    """Triggered when Yandex Search API returns an auth/billing/quota failure."""
    is_balance_or_perm = (
        status_code in (401, 402, 403)
        or "PermissionDenied" in error_text
        or "billing" in error_text.lower()
        or "payment" in error_text.lower()
    )

    if not is_balance_or_perm and status_code != 429:
        return

    title = "🚨 <b>TenderLex: Критический сбой Яндекс.Поиск API!</b>"
    reason = "Каталог заблокирован / Закончились деньги на балансе Яндекс.Облака" if is_balance_or_perm else "Превышен лимит запросов (Rate Limit 429)"

    msg_lines = [
        title,
        "",
        f"<b>Причина:</b> {reason}",
        f"<b>Статус:</b> <code>HTTP {status_code}</code>",
    ]
    if error_text:
        safe_err = html.escape(error_text[:250].replace("\n", " "))
        msg_lines.append(f"<b>Ошибка Яндекса:</b> <code>{safe_err}</code>")
    if job_info:
        msg_lines.append(f"<b>Контекст задачи:</b> {html.escape(job_info)}")
    if query:
        msg_lines.append(f"<b>Поисковый запрос:</b> <code>{html.escape(query[:90])}</code>")

    msg_lines.append("")
    if is_balance_or_perm:
        msg_lines.append("👉 <b>Действие:</b> Срочно пополните баланс в Яндекс.Облаке (каталог <code>b1gmnp1u8urslual8ht8</code>), иначе клиенты не смогут найти поставщиков!")
    else:
        msg_lines.append("👉 <b>Действие:</b> Проверьте квоты и нагрузку в консоли Яндекс.Облака.")

    full_text = "\n".join(msg_lines)
    key = "yandex_search_permission_denied" if is_balance_or_perm else "yandex_search_429"
    record_incident("yandex_search", reason, error_text[:200], level="critical" if is_balance_or_perm else "warning")
    markup = yandex_billing_inline_markup(
        billing_account_id,
        include_folder_link=True,
    )
    dispatch_telegram_admin_alert(
        full_text,
        deduplicate_key=key,
        throttle_seconds=900,
        reply_markup=markup,
    )


def notify_low_yandex_balance(
    balance_rub: float,
    is_active: bool,
    *,
    billing_account_id: str = DEFAULT_YANDEX_BILLING_ACCOUNT_ID,
) -> None:
    """Triggered when Yandex Cloud billing balance drops below safety threshold (e.g. 150 ₽)."""
    status_label = "активен" if is_active else "заблокирован"
    title = "⚠️ <b>TenderLex: Заканчивается баланс Яндекс.Облака!</b>"
    text = (
        f"{title}\n\n"
        f"<b>Текущий остаток:</b> <code>{balance_rub:.2f} ₽</code>\n"
        f"<b>Статус аккаунта:</b> {status_label}\n\n"
        f"👉 <i>Пополните счёт в Яндекс.Облаке во избежание сбоев в поиске поставщиков.</i>"
    )
    record_incident(
        "yandex_billing",
        f"Низкий баланс Яндекс.Облака ({balance_rub:.2f} ₽)",
        f"Статус аккаунта: {status_label}",
        level="warning" if is_active else "critical",
    )
    markup = yandex_billing_inline_markup(billing_account_id)
    # Throttle to once every 4 hours so owner isn't spammed while balance stays low
    dispatch_telegram_admin_alert(
        text,
        deduplicate_key="yandex_balance_low",
        throttle_seconds=14400,
        reply_markup=markup,
    )


def notify_ai_provider_error(
    provider: str,
    model: str,
    status_code: int,
    error_text: str,
    *,
    job_info: str = "",
) -> None:
    """Triggered when an AI provider returns 401, 402, 429, or quota error."""
    is_critical = status_code in (401, 402) or "quota" in error_text.lower() or "insufficient" in error_text.lower()
    if not is_critical and status_code != 429:
        return

    title = "🚨 <b>TenderLex: Сбой AI-провайдера!</b>" if is_critical else "⚠️ <b>TenderLex: Лимит запросов к AI!</b>"
    reason = "Закончился баланс / Неверный API-ключ" if is_critical else "Превышен лимит запросов (Rate Limit)"

    msg_lines = [
        title,
        "",
        f"<b>Провайдер:</b> <code>{html.escape(provider)}</code> ({html.escape(model)})",
        f"<b>Причина:</b> {reason}",
        f"<b>Статус:</b> <code>HTTP {status_code}</code>",
    ]
    if error_text:
        safe_err = html.escape(error_text[:250].replace("\n", " "))
        msg_lines.append(f"<b>Ошибка:</b> <code>{safe_err}</code>")
    if job_info:
        msg_lines.append(f"<b>Задача:</b> {html.escape(job_info)}")

    msg_lines.append("")
    msg_lines.append(f"👉 <i>Проверьте баланс и API-ключ провайдера {html.escape(provider)} в настройках админки.</i>")

    full_text = "\n".join(msg_lines)
    key = f"ai_provider_fail_{provider}"
    record_incident(f"ai_{provider}", f"Сбой {provider} ({reason})", error_text[:200], level="critical" if is_critical else "warning")
    dispatch_telegram_admin_alert(full_text, deduplicate_key=key, throttle_seconds=1800)


def notify_job_infrastructure_failure(
    job_number: int,
    client_name: str,
    mode: str,
    error_text: str,
) -> None:
    """Triggered when a customer job terminates with an infrastructure/external API failure."""
    title = f"🚨 <b>TenderLex: Ошибка задачи #{job_number}!</b>"
    text = (
        f"{title}\n\n"
        f"<b>Клиент:</b> {html.escape(client_name)}\n"
        f"<b>Режим:</b> <code>{html.escape(mode)}</code>\n"
        f"<b>Ошибка:</b> <code>{html.escape(error_text[:250])}</code>\n\n"
        f"👉 <i>Проверьте задачу в админке: https://admin.tenderlex.ru</i>"
    )
    key = f"job_infra_fail_{job_number}"
    record_incident("job_failure", f"Задача #{job_number} ({client_name}) упала", error_text[:200], level="warning")
    dispatch_telegram_admin_alert(text, deduplicate_key=key, throttle_seconds=3600)

