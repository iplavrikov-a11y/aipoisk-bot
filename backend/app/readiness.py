from __future__ import annotations

import threading
import time
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import config
from .jobs import STALE_RUNNING_AFTER
from .models import Job, now_utc


_PROBE_CACHE_TTL_SECONDS = 15.0
_probe_cache_lock = threading.Lock()
_probe_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def clear_readiness_cache() -> None:
    with _probe_cache_lock:
        _probe_cache.clear()


def database_queue_readiness(db: Session) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        pending = db.query(Job).filter(Job.status == "pending").count()
        running = db.query(Job).filter(Job.status == "running").count()
        stale_running = (
            db.query(Job)
            .filter(
                Job.status == "running",
                Job.updated_at < now_utc() - STALE_RUNNING_AFTER,
            )
            .count()
        )
    except Exception:
        return {
            "database": {"ok": False, "error": "database_unavailable"},
            "queue": {
                "ok": False,
                "pending": 0,
                "running": 0,
                "stale_running": 0,
            },
        }
    return {
        "database": {"ok": True},
        "queue": {
            "ok": True,
            "pending": pending,
            "running": running,
            "stale_running": stale_running,
        },
    }


def tender_source_readiness() -> dict[str, Any]:
    base_url = str(config.tender_source_service_url or "").strip().rstrip("/")
    if not base_url:
        direct_configured = bool(str(config.tenderplan_api_token or "").strip())
        return {
            "configured": False,
            "direct_configured": direct_configured,
            "ok": direct_configured,
            "cached": False,
            **({} if direct_configured else {"error": "source_not_configured"}),
        }

    now = time.monotonic()
    with _probe_cache_lock:
        cached = _probe_cache.get(base_url)
        if cached and now - cached[0] < _PROBE_CACHE_TTL_SECONDS:
            return {**cached[1], "cached": True}

    started = time.monotonic()
    try:
        timeout = httpx.Timeout(2.0, connect=1.0)
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(f"{base_url}/ready")
            payload = response.json()
        ok = response.status_code == 200 and payload.get("ok") is True
        result = {
            "configured": True,
            "ok": ok,
            "status_code": response.status_code,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "cached": False,
            **({} if ok else {"error": "source_unavailable"}),
        }
    except Exception:
        result = {
            "configured": True,
            "ok": False,
            "status_code": 0,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "cached": False,
            "error": "source_unavailable",
        }

    with _probe_cache_lock:
        _probe_cache[base_url] = (time.monotonic(), dict(result))
    return result


def build_readiness(db: Session) -> dict[str, Any]:
    local = database_queue_readiness(db)
    source = tender_source_readiness()
    return {
        "ok": bool(local["database"]["ok"] and source["ok"]),
        **local,
        "tender_source": source,
    }
