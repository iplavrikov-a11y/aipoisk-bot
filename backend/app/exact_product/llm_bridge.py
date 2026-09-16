from __future__ import annotations

import inspect
import logging
import sys
from typing import Any, List, Optional

from ..ai import call_llm as _base_call_llm
from ..models import SystemSettings
from ..db import SessionLocal
from ..repository import get_or_create_settings

logger = logging.getLogger(__name__)


def get_settings() -> SystemSettings:
    """Возвращает текущие SystemSettings из локальной БД TenderLex."""
    with SessionLocal() as db:
        return get_or_create_settings(db)


async def call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    json_mode: bool = False,
    model_tier: str = "light",
    images: Optional[List[str]] = None,
    job_id: Optional[str] = None,
    override_model: Optional[str] = None,
    routing_key: Optional[str] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    timeout_seconds: Optional[float] = None,
    settings: Optional[SystemSettings] = None,
) -> str:
    """
    Универсальный мост к ИИ-сервису TenderLex.
    Полная сигнатурная совместимость с EmailAgent.
    """
    # Check if app.exact_product.call_llm was patched in tests
    ep_mod = sys.modules.get("app.exact_product")
    if ep_mod and hasattr(ep_mod, "call_llm"):
        ep_func = getattr(ep_mod, "call_llm")
        if ep_func is not call_llm and callable(ep_func):
            try:
                return await ep_func(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    model_tier=model_tier,
                    images=images,
                    job_id=job_id,
                    override_model=override_model,
                    routing_key=routing_key,
                    temperature=temperature,
                    seed=seed,
                    timeout_seconds=timeout_seconds,
                    settings=settings,
                )
            except TypeError:
                if settings is None:
                    settings = get_settings()
                tier = "primary" if model_tier == "primary" else "light"
                timeout = timeout_seconds if timeout_seconds is not None else (90.0 if tier == "light" else 180.0)
                return await ep_func(
                    settings,
                    prompt,
                    system_prompt=system_prompt or "",
                    tier=tier,
                    routing_key=routing_key,
                    override=override_model,
                    json_mode=json_mode,
                    timeout_seconds=timeout,
                )

    if settings is None:
        settings = get_settings()

    tier = "primary" if model_tier == "primary" else "light"
    timeout = timeout_seconds if timeout_seconds is not None else (90.0 if tier == "light" else 180.0)

    from ..ai import call_llm as active_call_llm

    return await active_call_llm(
        settings,
        prompt,
        system_prompt=system_prompt or "",
        tier=tier,
        routing_key=routing_key,
        override=override_model,
        json_mode=json_mode,
        timeout_seconds=timeout,
    )

