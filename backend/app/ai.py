from __future__ import annotations

import asyncio
import json
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

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

# --- LLM call robustness: retry, throttle, free-only fallback ----------------
# Transient HTTP statuses worth retrying before moving on to the next model.
_RETRIABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
# Extra attempts after the first one, per model selection.
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.5
_RETRY_MAX_DELAY = 20.0
_DEFAULT_MAX_MODEL_ATTEMPTS = 6
_DEFAULT_MAX_REQUEST_ATTEMPTS = 12
_DEFAULT_OVERALL_TIMEOUT_MULTIPLIER = 2.0
# Provider ids that cost real money and must NEVER be added as an automatic
# fallback target. The user can still pick them explicitly as the primary.
_PAID_PROVIDER_IDS = {"polza", "open-ai", "openai"}


class LLMError(RuntimeError):
    """An LLM call failure with enough context to surface a clear message."""

    def __init__(
        self,
        message: str,
        *,
        status: Any = None,
        retriable: bool = False,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(message or "LLM request failed")
        self.status = status
        self.retriable = retriable
        self.provider = provider
        self.model = model


@dataclass(frozen=True)
class ModelSelection:
    provider_id: str
    provider_name: str
    model: str
    base_url: str
    api_key: str


@dataclass
class _RequestAttemptBudget:
    remaining: int
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def consume(self) -> bool:
        with self._lock:
            if self.remaining <= 0:
                return False
            self.remaining -= 1
            return True


class _ProcessLLMLimiter:
    """Process-wide capacity guard shared by worker threads and event loops."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = 0

    def _try_acquire(self) -> bool:
        with self._lock:
            if self._active >= _llm_concurrency_limit():
                return False
            self._active += 1
            return True

    async def acquire(self) -> None:
        while not self._try_acquire():
            await asyncio.sleep(0.025)

    def release(self) -> None:
        with self._lock:
            if self._active <= 0:
                raise RuntimeError("LLM limiter released without acquire")
            self._active -= 1

    def reset_for_tests(self) -> None:
        with self._lock:
            if self._active:
                raise RuntimeError("cannot reset an active LLM limiter")
            self._active = 0


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
    configured_override = resolve_function_override(settings, routing_key)
    if explicit_override:
        value = explicit_override
    elif configured_override:
        value = configured_override
    elif routing_key in SUPPLIER_SEARCH_ROUTING_KEYS:
        # Backwards-compatible default: supplier stages share the supplier model
        # unless the operator configured a stage-specific function override.
        value = AI_ROUTING_SUPPLIER_SEARCH
    else:
        value = ""
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


def resolve_job_ai_info(job: Any, settings: SystemSettings | None = None) -> dict[str, str]:
    provider_id = str(getattr(job, "ai_provider", "") or "").strip()
    model = str(getattr(job, "ai_model", "") or "").strip()
    provider_name = ""

    # If provider/model missing on Job, try reading from evidence.json
    evidence_path = str(getattr(job, "evidence_path", "") or "").strip()
    if not model and evidence_path:
        try:
            from pathlib import Path
            p = Path(evidence_path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if data.get("ai_model"):
                        model = str(data["ai_model"]).strip()
                    elif isinstance(data.get("report"), dict) and data["report"].get("ai_model"):
                        model = str(data["report"]["ai_model"]).strip()
                    if data.get("ai_provider"):
                        provider_id = str(data["ai_provider"]).strip()
        except Exception:
            pass

    # If still missing and settings available, determine from mode
    if settings is not None:
        providers = custom_provider_map(settings)
        if not model or not provider_id:
            try:
                mode = str(getattr(job, "mode", "") or "")
                tier = "primary" if mode == "procurement_report" else "supplier_search"
                routing_key = "procurement_document_analysis" if mode == "procurement_report" else "supplier_query_generation"
                selection = get_model_selection(settings, tier=tier, routing_key=routing_key)
                if not provider_id:
                    provider_id = selection.provider_id
                if not model:
                    model = selection.model
                if not provider_name:
                    provider_name = selection.provider_name
            except Exception:
                pass

        if provider_id and not provider_name:
            p_obj = providers.get(provider_id)
            if p_obj:
                provider_name = str(p_obj.get("name") or "").strip()

    if provider_id and not provider_name:
        known = {
            "gemini": "Gemini",
            "openrouter": "OpenRouter",
            "open-ai": "OpenAI",
            "openai": "OpenAI",
            "polza": "Polza",
            "z.ai": "Z.AI",
            "opencode": "Opencode",
        }
        provider_name = known.get(provider_id.lower(), provider_id.capitalize())

    label_parts = [p for p in (provider_name or provider_id, model) if p]
    ai_label = " · ".join(label_parts)

    return {
        "ai_provider": provider_id,
        "ai_provider_name": provider_name,
        "ai_model": model,
        "ai_label": ai_label,
    }


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
    # User-configured fallbacks have priority and preserve their exact order.
    # Paid models are allowed here because this list is an explicit choice.
    for entry in _manual_fallback_entries(settings, routing_key):
        pid = str(entry.get("provider") or "").strip()
        mid = str(entry.get("modelId") or "").strip()
        if not pid or not mid:
            continue
        key = f"{pid}:{mid}"
        if key in seen:
            continue
        seen.add(key)
        try:
            attempts.append(
                get_model_selection(settings, tier=tier, routing_key=None, override=key)
            )
        except Exception:
            continue
    # Nearby same-provider aliases are a compatibility fallback after the
    # operator's ordered list, but before the optional automatic free pool.
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
    # Cross-provider automatic fallback is opt-in and free-only. A saved model
    # must be explicitly allowlisted and marked free (or use a provider's
    # unambiguous free model suffix). Unmarked saved models are never executed.
    for entry in _saved_model_entries(settings):
        pid = str(entry.get("provider") or "").strip()
        mid = str(entry.get("modelId") or "").strip()
        if not pid or not mid or not _automatic_fallback_allowed(entry, pid, mid):
            continue
        key = f"{pid}:{mid}"
        if key in seen:
            continue
        seen.add(key)
        try:
            attempts.append(
                get_model_selection(settings, tier=tier, routing_key=None, override=key)
            )
        except Exception:
            continue
    return attempts


def _extra_headers(selection: ModelSelection) -> dict[str, str]:
    """OpenRouter rewards (and some free routes require) HTTP-Referer / X-Title."""
    if selection.provider_id == "openrouter" or "openrouter.ai" in (selection.base_url or "").lower():
        return {"HTTP-Referer": "https://tenderlex.ru", "X-Title": "TenderLex"}
    return {}


def _is_paid_model(provider_id: str, model: str) -> bool:
    pid = str(provider_id or "").strip().lower()
    if pid in _PAID_PROVIDER_IDS:
        return True
    if pid == "openrouter" and ":free" not in str(model or "").lower():
        return True
    return False


def _truthy_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _automatic_fallback_allowed(entry: dict, provider_id: str, model: str) -> bool:
    if not _truthy_flag(entry.get("allowAutomaticFallback")):
        return False
    if _is_paid_model(provider_id, model):
        return False
    pid = str(provider_id or "").strip().lower()
    mid = str(model or "").strip().lower()
    billing_class = str(entry.get("billingClass") or "").strip().lower()
    explicitly_free = _truthy_flag(entry.get("isFree")) or billing_class == "free"
    provider_free_marker = (pid == "openrouter" and ":free" in mid) or (
        pid == "opencode" and mid.endswith("-free")
    )
    return explicitly_free or provider_free_marker


def _saved_model_entries(settings: SystemSettings) -> list[dict]:
    return parse_json_list(getattr(settings, "saved_models_json", "[]") or "[]")


def _manual_fallback_entries(settings: SystemSettings, routing_key: str | None) -> list[dict]:
    """User-configured ordered fallback list for the current scenario.

    Supplier-search routing keys use the supplier list; everything else (document
    analysis, primary/light tiers) uses the analysis list. Paid models are NOT
    filtered here — the user picks them explicitly.
    """
    col = (
        "ai_supplier_fallback_json"
        if routing_key in SUPPLIER_SEARCH_ROUTING_KEYS
        else "ai_analysis_fallback_json"
    )
    return parse_json_list(getattr(settings, col, "[]") or "[]")


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _llm_concurrency_limit() -> int:
    return _env_int("AIPOISK_LLM_MAX_CONCURRENCY", 3, minimum=1, maximum=32)


def _max_model_attempts() -> int:
    return _env_int(
        "AIPOISK_LLM_MAX_MODEL_ATTEMPTS",
        _DEFAULT_MAX_MODEL_ATTEMPTS,
        minimum=1,
        maximum=20,
    )


def _max_request_attempts() -> int:
    return _env_int(
        "AIPOISK_LLM_MAX_REQUEST_ATTEMPTS",
        _DEFAULT_MAX_REQUEST_ATTEMPTS,
        minimum=1,
        maximum=60,
    )


def _overall_timeout_seconds(per_model_timeout: float) -> float:
    configured = str(os.getenv("AIPOISK_LLM_OVERALL_TIMEOUT_SECONDS", "") or "").strip()
    if configured:
        try:
            return max(1.0, min(900.0, float(configured)))
        except (TypeError, ValueError):
            pass
    return max(
        per_model_timeout,
        min(300.0, per_model_timeout * _DEFAULT_OVERALL_TIMEOUT_MULTIPLIER),
    )


def _httpx_timeout(overall_seconds: float) -> httpx.Timeout:
    overall = max(1.0, float(overall_seconds))
    return httpx.Timeout(
        timeout=overall,
        connect=min(10.0, overall),
        read=min(overall, max(15.0, overall * 0.8)),
        write=min(30.0, overall),
        pool=min(10.0, overall),
    )


def _retry_after_seconds(response: httpx.Response, *, now: datetime | None = None) -> float | None:
    value = str(response.headers.get("retry-after") or "").strip()
    if not value:
        return None
    try:
        return max(0.0, min(_RETRY_MAX_DELAY, float(value)))
    except (TypeError, ValueError):
        pass
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return max(0.0, min(_RETRY_MAX_DELAY, (retry_at - current).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return None


def _retry_delay(attempt: int, response: httpx.Response | None = None) -> float:
    if response is not None:
        retry_after = _retry_after_seconds(response)
        if retry_after is not None:
            return retry_after
    base = min(_RETRY_MAX_DELAY, _RETRY_BASE_DELAY * (2 ** attempt))
    jitter = random.uniform(0.0, min(1.0, base * 0.1))
    return min(_RETRY_MAX_DELAY, base + jitter)


def _safe_error_text(exc: Exception) -> str:
    message = str(exc).strip() or type(exc).__name__
    message = re.sub(r"(?i)bearer\s+\S+", "Bearer <redacted>", message)
    message = re.sub(
        r"(?i)(api[_-]?key|authorization)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2<redacted>",
        message,
    )
    return message[:500]


_process_llm_limiter = _ProcessLLMLimiter()


async def _sleep_before_retry(delay: float, deadline_monotonic: float | None) -> None:
    bounded_delay = max(0.0, delay)
    if deadline_monotonic is not None:
        remaining = deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("LLM overall deadline exceeded")
        bounded_delay = min(bounded_delay, remaining)
    await asyncio.sleep(bounded_delay)


async def _post_llm_request(
    selection: ModelSelection,
    messages: list[dict[str, str]],
    *,
    json_mode: bool,
    timeout_seconds: float,
    attempt_budget: _RequestAttemptBudget | None = None,
    request_metadata: dict[str, Any] | None = None,
    deadline_monotonic: float | None = None,
) -> str:
    payload: dict[str, Any] = {
        "model": selection.model,
        "messages": messages,
        "temperature": 0.2,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {selection.api_key}"}
    headers.update(_extra_headers(selection))

    last_error: LLMError | None = None
    if request_metadata is not None:
        request_metadata.update({"request_attempts": 0, "retry_count": 0, "last_status": None})
    async with httpx.AsyncClient(timeout=_httpx_timeout(timeout_seconds)) as client:
        for attempt in range(_MAX_RETRIES + 1):
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                raise TimeoutError("LLM overall deadline exceeded")
            if attempt_budget is not None and not attempt_budget.consume():
                raise LLMError(
                    "LLM request attempt budget exhausted",
                    retriable=False,
                    provider=selection.provider_id,
                    model=selection.model,
                )
            if request_metadata is not None:
                request_metadata["request_attempts"] = int(request_metadata["request_attempts"]) + 1
                request_metadata["retry_count"] = attempt
            await _process_llm_limiter.acquire()
            try:
                try:
                    response = await client.post(selection.base_url, headers=headers, json=payload)
                    transport_error: Exception | None = None
                except httpx.HTTPError as exc:
                    transport_error = exc
            finally:
                _process_llm_limiter.release()

            if transport_error is not None:
                last_error = LLMError(
                    f"{selection.provider_name}:{selection.model} transport "
                    f"{type(transport_error).__name__}: {transport_error or '<no detail>'}",
                    retriable=True,
                    provider=selection.provider_id,
                    model=selection.model,
                )
                if attempt < _MAX_RETRIES:
                    await _sleep_before_retry(_retry_delay(attempt), deadline_monotonic)
                    continue
                raise last_error

            if request_metadata is not None:
                request_metadata["last_status"] = response.status_code
            if response.status_code >= 400:
                detail = response.text.strip()[:500]
                retriable = response.status_code in _RETRIABLE_STATUS
                last_error = LLMError(
                    f"{selection.provider_name}:{selection.model} HTTP {response.status_code}: "
                    f"{detail or response.reason_phrase}",
                    status=response.status_code,
                    retriable=retriable,
                    provider=selection.provider_id,
                    model=selection.model,
                )
                if retriable and attempt < _MAX_RETRIES:
                    await _sleep_before_retry(_retry_delay(attempt, response), deadline_monotonic)
                    continue
                raise last_error

            try:
                data = response.json()
            except Exception:
                last_error = LLMError(
                    f"{selection.provider_name}:{selection.model} returned non-JSON: "
                    f"{response.text.strip()[:300]}",
                    retriable=True,
                    provider=selection.provider_id,
                    model=selection.model,
                )
                if attempt < _MAX_RETRIES:
                    await _sleep_before_retry(_retry_delay(attempt), deadline_monotonic)
                    continue
                raise last_error

            # Some providers (e.g. OpenRouter upstream errors) answer HTTP 200
            # with an {"error": ...} body and no choices.
            if isinstance(data, dict) and data.get("error") and not data.get("choices"):
                err = data.get("error")
                code = err.get("code") if isinstance(err, dict) else None
                err_msg = (err.get("message") if isinstance(err, dict) else str(err)) or "upstream error"
                retriable = str(code) in {"429", "502", "503", "504"} or "rate" in str(err_msg).lower()
                last_error = LLMError(
                    f"{selection.provider_name}:{selection.model} upstream error: {err_msg} (code={code})",
                    status=code,
                    retriable=retriable,
                    provider=selection.provider_id,
                    model=selection.model,
                )
                if retriable and attempt < _MAX_RETRIES:
                    await _sleep_before_retry(_retry_delay(attempt), deadline_monotonic)
                    continue
                raise last_error

            choices = data.get("choices") if isinstance(data, dict) else None
            if not choices:
                last_error = LLMError(
                    f"{selection.provider_name}:{selection.model} returned no choices",
                    retriable=True,
                    provider=selection.provider_id,
                    model=selection.model,
                )
                if attempt < _MAX_RETRIES:
                    await _sleep_before_retry(_retry_delay(attempt), deadline_monotonic)
                    continue
                raise last_error
            return str(choices[0].get("message", {}).get("content") or "")
    raise last_error or LLMError("LLM request failed")


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
    response_validator: Callable[[str], None] | None = None,
    total_timeout_seconds: float | None = None,
) -> str:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    all_attempts = model_selection_attempts(settings, tier=tier, routing_key=routing_key, override=override)
    model_attempt_limit = _max_model_attempts()
    attempts = all_attempts[:model_attempt_limit]
    overall_timeout = max(
        1.0,
        float(total_timeout_seconds)
        if total_timeout_seconds is not None
        else _overall_timeout_seconds(timeout_seconds),
    )
    deadline = time.monotonic() + overall_timeout
    request_attempt_limit = _max_request_attempts()
    request_budget = _RequestAttemptBudget(request_attempt_limit)
    last_error: Exception | None = None
    attempted_models: list[str] = []
    trace: list[dict[str, Any]] = []
    for index, selection in enumerate(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            last_error = TimeoutError("LLM overall deadline exceeded")
            break
        attempted_models.append(f"{selection.provider_name}:{selection.model}")
        started = time.monotonic()
        request_metadata: dict[str, Any] = {}
        phase = "request"
        trace_item: dict[str, Any] = {
            "provider_id": selection.provider_id,
            "provider_name": selection.provider_name,
            "model": selection.model,
            "fallback_used": index > 0,
        }
        try:
            selection_timeout = max(0.001, min(float(timeout_seconds), remaining))
            result = await asyncio.wait_for(
                _post_llm_request(
                    selection,
                    messages,
                    json_mode=json_mode,
                    timeout_seconds=selection_timeout,
                    attempt_budget=request_budget,
                    request_metadata=request_metadata,
                    deadline_monotonic=deadline,
                ),
                timeout=selection_timeout,
            )
            phase = "validation"
            if response_validator is not None:
                response_validator(result)
            trace_item.update(
                {
                    "status": "success",
                    "error": "",
                    "latency_ms": int(round((time.monotonic() - started) * 1000)),
                    **request_metadata,
                }
            )
            trace.append(trace_item)
            if metadata is not None:
                metadata.update(
                    {
                        "provider_id": selection.provider_id,
                        "provider_name": selection.provider_name,
                        "model": selection.model,
                        "attempted_models": attempted_models.copy(),
                        "attempts": trace.copy(),
                        "fallback_used": index > 0,
                        "model_attempt_limit": model_attempt_limit,
                        "request_attempt_limit": request_attempt_limit,
                        "overall_timeout_seconds": overall_timeout,
                    }
                )
            return result
        except Exception as exc:
            last_error = exc
            if isinstance(exc, TimeoutError):
                status = "timeout"
            elif phase == "validation":
                status = "validation_error"
            elif isinstance(exc, LLMError) and "budget exhausted" in str(exc).lower():
                status = "budget_exhausted"
            else:
                status = "error"
            trace_item.update(
                {
                    "status": status,
                    "error_type": type(exc).__name__,
                    "error": _safe_error_text(exc),
                    "latency_ms": int(round((time.monotonic() - started) * 1000)),
                    **request_metadata,
                }
            )
            if isinstance(exc, LLMError) and exc.status is not None:
                trace_item["http_status"] = exc.status
            trace.append(trace_item)
            if metadata is not None:
                metadata.update(
                    {
                        "attempted_models": attempted_models.copy(),
                        "attempts": trace.copy(),
                        "fallback_used": index > 0,
                        "model_attempt_limit": model_attempt_limit,
                        "request_attempt_limit": request_attempt_limit,
                        "overall_timeout_seconds": overall_timeout,
                    }
                )
            if status == "budget_exhausted":
                break
    if metadata is not None:
        metadata.update(
            {
                "attempted_models": attempted_models.copy(),
                "attempts": trace.copy(),
                "fallback_used": len(attempted_models) > 1,
                "model_attempt_limit": model_attempt_limit,
                "request_attempt_limit": request_attempt_limit,
                "overall_timeout_seconds": overall_timeout,
            }
        )
    if last_error is None:
        raise RuntimeError("AI model selection failed")
    raise RuntimeError(
        f"{_safe_error_text(last_error)}; tried models: {', '.join(attempted_models)}"
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
