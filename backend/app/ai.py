from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .models import SystemSettings, parse_json_dict, parse_json_list

AI_ROUTING_FALLBACK_PRIMARY = "__primary__"
AI_ROUTING_FALLBACK_LIGHT = "__light__"
AI_ROUTING_SUPPLIER_SEARCH = "__supplier_search__"
SUPPLIER_SEARCH_ROUTING_KEYS = {
    "minprom_registry_requirement",
    "minprom_registry_query_generation",
    "supplier_procurement_profile",
    "supplier_query_generation",
    "supplier_tz_context_extraction",
    "supplier_candidate_reranker",
    "supplier_candidate_verifier",
}
DEFAULT_MODEL_FALLBACKS: dict[str, tuple[str, ...]] = {
    "gemini-3.1-pro-preview": ("gemini-3-pro-preview", "gemini-2.5-flash"),
    "gemini-3-pro-preview": ("gemini-3.1-pro-preview", "gemini-2.5-flash"),
    "gemini-3-flash-preview": ("gemini-3.1-flash-lite-preview", "gemini-2.5-flash"),
    "gemini-3.1-flash-lite-preview": ("gemini-3-flash-preview", "gemini-2.5-flash-lite"),
    "gemini-3.5-flash": ("gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-2.5-flash"),
    "gemini-3.1-flash-lite": ("gemini-3.1-flash-lite-preview", "gemini-3-flash-preview", "gemini-2.5-flash-lite"),
}


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
    if provider_id == getattr(settings, "supplier_ai_provider", "") and tier == "supplier_search":
        return getattr(settings, "supplier_ai_model", "")
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
    if tier == "supplier_search":
        selected_provider = str(getattr(settings, "supplier_ai_provider", "") or settings.light_provider or "").strip()
        selected_model = str(getattr(settings, "supplier_ai_model", "") or settings.light_model or "").strip()

    explicit_override = str(override or "").strip()
    if routing_key in SUPPLIER_SEARCH_ROUTING_KEYS and not explicit_override:
        value = AI_ROUTING_SUPPLIER_SEARCH
    else:
        value = explicit_override or resolve_function_override(settings, routing_key)
    if routing_key in SUPPLIER_SEARCH_ROUTING_KEYS and value == AI_ROUTING_SUPPLIER_SEARCH:
        selected_tier = "supplier_search"
        selected_provider = str(getattr(settings, "supplier_ai_provider", "") or settings.light_provider or "").strip()
        selected_model = str(getattr(settings, "supplier_ai_model", "") or settings.light_model or "").strip()
    elif value == AI_ROUTING_SUPPLIER_SEARCH:
        selected_tier = "supplier_search"
        selected_provider = str(getattr(settings, "supplier_ai_provider", "") or settings.light_provider or "").strip()
        selected_model = str(getattr(settings, "supplier_ai_model", "") or settings.light_model or "").strip()
    elif value == AI_ROUTING_FALLBACK_PRIMARY:
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


def model_fallbacks_for(model: str) -> tuple[str, ...]:
    return DEFAULT_MODEL_FALLBACKS.get(str(model or "").strip(), ())


def model_selection_attempts(
    settings: SystemSettings,
    *,
    tier: str = "light",
    routing_key: str | None = None,
    override: str | None = None,
) -> list[ModelSelection]:
    first = get_model_selection(settings, tier=tier, routing_key=routing_key, override=override)
    attempts = [first]
    seen = {f"{first.provider_id}:{first.model}"}
    if override:
        return attempts
    for model in model_fallbacks_for(first.model):
        key = f"{first.provider_id}:{model}"
        if key in seen:
            continue
        seen.add(key)
        try:
            attempts.append(
                get_model_selection(
                    settings,
                    tier=tier,
                    routing_key=None,
                    override=key,
                )
            )
        except Exception:
            continue
    return attempts


async def _post_llm_request(
    selection: ModelSelection,
    messages: list[dict[str, str]],
    *,
    json_mode: bool,
    timeout_seconds: float,
) -> str:
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
        if response.status_code >= 400:
            detail = response.text.strip()[:500]
            raise RuntimeError(f"HTTP {response.status_code}: {detail or response.reason_phrase}")
        data = response.json()
    return str(data["choices"][0]["message"]["content"] or "")


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
    metadata: dict[str, Any] | None = None,
) -> str:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    attempts = model_selection_attempts(settings, tier=tier, routing_key=routing_key, override=override)
    last_error: Exception | None = None
    attempted_models: list[str] = []
    for selection in attempts:
        attempted_models.append(f"{selection.provider_name}:{selection.model}")
        try:
            result = await _post_llm_request(
                selection,
                messages,
                json_mode=json_mode,
                timeout_seconds=timeout_seconds,
            )
            if metadata is not None:
                metadata.update(
                    {
                        "provider_id": selection.provider_id,
                        "provider_name": selection.provider_name,
                        "model": selection.model,
                        "attempted_models": attempted_models.copy(),
                    }
                )
            return result
        except Exception as exc:
            last_error = exc
    if metadata is not None:
        metadata["attempted_models"] = attempted_models.copy()
    if last_error is None:
        raise RuntimeError("AI model selection failed")
    raise RuntimeError(
        f"{last_error}; tried models: {', '.join(attempted_models)}"
    ) from last_error


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
