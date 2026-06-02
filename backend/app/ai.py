from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .models import SystemSettings, parse_json_dict, parse_json_list

AI_ROUTING_FALLBACK_PRIMARY = "__primary__"
AI_ROUTING_FALLBACK_LIGHT = "__light__"


@dataclass(frozen=True)
class ModelSelection:
    provider_id: str
    provider_name: str
    model: str
    base_url: str
    api_key: str


def normalize_chat_endpoint(base_url: str) -> str:
    value = str(base_url or "").strip().rstrip("/")
    if not value:
        return ""
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return f"{value}/chat/completions"
    return f"{value}/chat/completions"


def custom_provider_map(settings: SystemSettings) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in parse_json_list(settings.custom_ai_providers_json):
        provider_id = str(item.get("id") or "").strip()
        if provider_id:
            result[provider_id] = item
    return result


def resolve_function_override(settings: SystemSettings, routing_key: str | None) -> str:
    if not routing_key:
        return ""
    mapping = parse_json_dict(settings.ai_function_models_json)
    value = mapping.get(routing_key)
    return str(value or "").strip()


def resolve_model(settings: SystemSettings, provider_id: str, tier: str) -> str:
    providers = custom_provider_map(settings)
    provider = providers.get(provider_id) or {}
    direct = (
        str(provider.get("primaryModel" if tier == "primary" else "lightModel") or "").strip()
        or str(provider.get("model") or "").strip()
    )
    if direct:
        return direct
    if provider_id == settings.primary_provider and tier == "primary":
        return settings.primary_model
    if provider_id == settings.light_provider and tier == "light":
        return settings.light_model
    return ""


def get_model_selection(
    settings: SystemSettings,
    *,
    tier: str = "light",
    routing_key: str | None = None,
    override: str | None = None,
) -> ModelSelection:
    providers = custom_provider_map(settings)
    selected_tier = tier
    selected_provider = settings.primary_provider if tier == "primary" else settings.light_provider
    selected_model = settings.primary_model if tier == "primary" else settings.light_model

    value = str(override or "").strip() or resolve_function_override(settings, routing_key)
    if value == AI_ROUTING_FALLBACK_PRIMARY:
        selected_tier = "primary"
        selected_provider = settings.primary_provider
        selected_model = settings.primary_model
    elif value == AI_ROUTING_FALLBACK_LIGHT:
        selected_tier = "light"
        selected_provider = settings.light_provider
        selected_model = settings.light_model
    elif ":" in value:
        selected_provider, selected_model = value.split(":", 1)

    provider = providers.get(selected_provider)
    if not provider:
        raise ValueError("AI provider is not configured")

    base_url = normalize_chat_endpoint(str(provider.get("baseUrl") or ""))
    api_key = str(provider.get("apiKey") or "").strip()
    model = str(selected_model or "").strip() or resolve_model(settings, selected_provider, selected_tier)
    if not base_url or not api_key or not model:
        raise ValueError("AI provider requires baseUrl, apiKey and model")

    return ModelSelection(
        provider_id=selected_provider,
        provider_name=str(provider.get("name") or selected_provider).strip(),
        model=model,
        base_url=base_url,
        api_key=api_key,
    )


async def call_llm(
    settings: SystemSettings,
    prompt: str,
    *,
    system_prompt: str = "",
    tier: str = "light",
    routing_key: str | None = None,
    override: str | None = None,
    json_mode: bool = False,
    timeout_seconds: float = 90.0,
) -> str:
    selection = get_model_selection(settings, tier=tier, routing_key=routing_key, override=override)
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload: dict[str, Any] = {
        "model": selection.model,
        "messages": messages,
        "temperature": 0.2,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            selection.base_url,
            headers={"Authorization": f"Bearer {selection.api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return str(data["choices"][0]["message"]["content"] or "")


def parse_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return {}
    return {}
