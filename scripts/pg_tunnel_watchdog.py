#!/usr/bin/env python3
"""TenderLex PostgreSQL Tunnel Health Check & Watchdog.

Runs periodically (via systemd timer every 60s).
Checks database connectivity through the local SSH tunnel port (127.0.0.1:5433).
If connection fails or hangs:
  1. Retries once after 2 seconds to avoid false positives on transient network jitter.
  2. If still failing, automatically restarts tenderlex-pg-tunnel.service.
  3. Tests again to verify recovery.
  4. Sends instant Telegram notifications to the owner.
  5. Throttles repeated failure notifications (at most once every 15 minutes) if the remote server is down.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Paths & state files
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
STATE_DIR = Path("/run/tenderlex")
OUTAGE_FLAG = STATE_DIR / "pg_outage.flag"
LAST_ALERT_FILE = STATE_DIR / "last_alert.timestamp"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] tenderlex-pg-watchdog: %(message)s",
)
logger = logging.getLogger("pg-watchdog")


def load_env_credentials() -> tuple[str, str, str]:
    """Extract DB URL, BOT_TOKEN, and OWNER_ID from .env."""
    bot_token = ""
    owner_id = ""
    db_url = ""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k == "AIPOISK_BOT_TOKEN":
                    bot_token = v
                elif k == "AIPOISK_OWNER_TELEGRAM_ID":
                    owner_id = v
                elif k == "AIPOISK_DATABASE_URL":
                    db_url = v
    return db_url, bot_token, owner_id


def send_telegram_alert(bot_token: str, owner_id: str, message: str) -> bool:
    """Send alert via Telegram Bot API."""
    if not bot_token or not owner_id:
        logger.warning("Telegram credentials not configured; skipping alert")
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = urllib.parse.urlencode({"chat_id": owner_id, "text": message, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.error("Failed to send Telegram alert: %s", exc)
        return False


def test_postgres_connection(db_url: str, timeout_sec: int = 5) -> bool:
    """Try establishing a fresh connection and running SELECT 1."""
    if not db_url.startswith("postgresql"):
        return True  # Not postgres, skip check
    try:
        import psycopg2
        from sqlalchemy.engine import make_url
        u = make_url(db_url)
        conn = psycopg2.connect(
            host=u.host,
            port=u.port,
            user=u.username,
            password=u.password,
            dbname=u.database,
            connect_timeout=timeout_sec,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        return True
    except Exception as exc:
        logger.warning("PostgreSQL ping failed: %s", exc)
        return False


def restart_tunnel() -> None:
    """Restart systemd service for the SSH tunnel."""
    logger.info("Restarting tenderlex-pg-tunnel.service...")
    subprocess.run(["systemctl", "restart", "tenderlex-pg-tunnel.service"], check=False)


def should_send_critical_alert() -> bool:
    """Rate limit critical failure alerts to once per 15 minutes."""
    now = time.time()
    try:
        if LAST_ALERT_FILE.exists():
            last_time = float(LAST_ALERT_FILE.read_text().strip())
            if now - last_time < 900:  # 15 minutes
                return False
    except Exception:
        pass
    try:
        LAST_ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_ALERT_FILE.write_text(str(now))
    except Exception:
        pass
    return True


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    db_url, bot_token, owner_id = load_env_credentials()

    # Step 1: First test
    if test_postgres_connection(db_url, timeout_sec=5):
        # Connection healthy
        if OUTAGE_FLAG.exists():
            # We recovered from a prior outage!
            logger.info("Connection restored after previous incident.")
            try:
                OUTAGE_FLAG.unlink(missing_ok=True)
            except Exception:
                pass
            send_telegram_alert(
                bot_token,
                owner_id,
                "✅ <b>[TenderLex Watchdog]</b>\n"
                "Связь с базой данных PostgreSQL в Москве полностью восстановлена и работает стабильно."
            )
        return 0

    # Step 2: Connection failed. Retry once after 2 seconds to absorb transient network jitter
    logger.info("Initial connection test failed. Retrying in 2 seconds...")
    time.sleep(2)
    if test_postgres_connection(db_url, timeout_sec=5):
        logger.info("Retry succeeded; transient jitter ignored.")
        return 0

    # Step 3: Both attempts failed. Connection is genuinely down/stalled.
    logger.error("Connection failed twice. Triggering tunnel restart...")
    OUTAGE_FLAG.touch(exist_ok=True)
    restart_tunnel()

    # Step 4: Allow tunnel 3 seconds to establish socket, then test recovery
    time.sleep(3)
    if test_postgres_connection(db_url, timeout_sec=5):
        logger.info("Tunnel restart succeeded. Database connection recovered!")
        OUTAGE_FLAG.unlink(missing_ok=True)
        send_telegram_alert(
            bot_token,
            owner_id,
            "⚠️ <b>[TenderLex Watchdog]</b>\n"
            "Зафиксирован сбой связи с базой данных в Москве.\n"
            "SSH-туннель был автоматически перезапущен.\n"
            "<b>Статус: связь успешно восстановлена!</b>"
        )
        return 0

    # Step 5: Still failing after restart
    logger.critical("Connection still failing after tunnel restart!")
    if should_send_critical_alert():
        send_telegram_alert(
            bot_token,
            owner_id,
            "🚨 <b>[TenderLex КРИТИЧЕСКИЙ СБОЙ]</b>\n"
            "База данных в Москве (79.133.182.215) недоступна.\n"
            "Автоматический перезапуск туннеля не помог.\n"
            "Возможна проблема с сетью дата-центра или сервером."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())

