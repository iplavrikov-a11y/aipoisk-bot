from __future__ import annotations

import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import app.ai as ai
from app.ai import ModelSelection, model_selection_attempts


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        custom_ai_providers_json='[{"id":"gemini","name":"Gemini","baseUrl":"https://proxy.example/v1","apiKey":"key"}]',
        primary_provider="gemini",
        primary_model="gemini-3.1-pro-preview",
        light_provider="gemini",
        light_model="gemini-3.1-flash-lite-preview",
        supplier_ai_provider="gemini",
        supplier_ai_model="gemini-3.1-flash-lite",
        ai_function_models_json='{"procurement_document_analysis":"gemini:gemini-3.1-pro-preview","supplier_query_generation":"gemini:gemini-3.1-pro-preview"}',
    )


class AiModelFallbackTests(unittest.TestCase):
    def test_function_model_adds_nearby_gemini_fallbacks(self) -> None:
        attempts = model_selection_attempts(
            _settings(),
            tier="primary",
            routing_key="procurement_document_analysis",
        )

        self.assertEqual(
            [item.model for item in attempts],
            ["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-2.5-flash"],
        )

    def test_known_unavailable_flash_alias_falls_back_to_preview_models(self) -> None:
        settings = _settings()
        settings.ai_function_models_json = "{}"
        attempts = model_selection_attempts(
            settings,
            tier="light",
            routing_key="supplier_query_generation",
        )

        self.assertEqual(
            [item.model for item in attempts],
            ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview", "gemini-3-flash-preview", "gemini-2.5-flash-lite"],
        )

    def test_supplier_routing_respects_function_override(self) -> None:
        selection = ai.get_model_selection(
            _settings(),
            tier="primary",
            routing_key="supplier_query_generation",
        )

        self.assertEqual(selection.model, "gemini-3.1-pro-preview")

    def test_supplier_routing_defaults_to_shared_supplier_model_without_override(self) -> None:
        settings = _settings()
        settings.ai_function_models_json = "{}"

        selection = ai.get_model_selection(
            settings,
            tier="primary",
            routing_key="supplier_query_generation",
        )

        self.assertEqual(selection.model, "gemini-3.1-flash-lite")

    def test_explicit_override_is_tested_without_hidden_fallbacks(self) -> None:
        attempts = model_selection_attempts(
            _settings(),
            tier="primary",
            override="gemini:gemini-3.5-flash",
        )

        self.assertEqual([item.model for item in attempts], ["gemini-3.5-flash"])


class AiCallFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_post_llm_request_includes_http_error_body(self) -> None:
        original_client = ai.httpx.AsyncClient

        class FakeResponse:
            status_code = 400
            text = '{"error":{"message":"Модель не найдена"}}'
            reason_phrase = "Bad Request"

            def json(self):
                return {}

        class FakeClient:
            def __init__(self, *_args, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def post(self, *_args, **_kwargs):
                return FakeResponse()

        ai.httpx.AsyncClient = FakeClient
        try:
            with self.assertRaisesRegex(RuntimeError, "Модель не найдена"):
                await ai._post_llm_request(
                    ModelSelection(
                        provider_id="polza",
                        provider_name="Polza",
                        model="bad-model",
                        base_url="https://api.example/v1/chat/completions",
                        api_key="key",
                    ),
                    [{"role": "user", "content": "ok"}],
                    json_mode=False,
                    timeout_seconds=1,
                )
        finally:
            ai.httpx.AsyncClient = original_client

    async def test_call_llm_records_model_that_answered_after_fallback(self) -> None:
        original_post = ai._post_llm_request
        calls: list[str] = []

        async def fake_post(selection, *_args, **_kwargs) -> str:
            calls.append(selection.model)
            if len(calls) == 1:
                raise RuntimeError("temporary model timeout")
            return "ok"

        ai._post_llm_request = fake_post
        try:
            metadata: dict = {}
            result = await ai.call_llm(
                _settings(),
                "prompt",
                tier="primary",
                routing_key="procurement_document_analysis",
                metadata=metadata,
            )
        finally:
            ai._post_llm_request = original_post

        self.assertEqual(result, "ok")
        self.assertEqual(calls, ["gemini-3.1-pro-preview", "gemini-3-pro-preview"])
        self.assertEqual(metadata["model"], "gemini-3-pro-preview")
        self.assertEqual(
            metadata["attempted_models"],
            ["Gemini:gemini-3.1-pro-preview", "Gemini:gemini-3-pro-preview"],
        )
        self.assertTrue(metadata["fallback_used"])
        self.assertEqual([item["status"] for item in metadata["attempts"]], ["error", "success"])
        self.assertEqual(metadata["attempts"][0]["model"], "gemini-3.1-pro-preview")
        self.assertIn("latency_ms", metadata["attempts"][0])

    async def test_call_llm_falls_back_when_response_validator_rejects_content(self) -> None:
        original_post = ai._post_llm_request
        calls: list[str] = []

        async def fake_post(selection, *_args, **_kwargs) -> str:
            calls.append(selection.model)
            return "bad" if len(calls) == 1 else "ok"

        def validator(raw: str) -> None:
            if raw != "ok":
                raise RuntimeError("model returned unusable content")

        ai._post_llm_request = fake_post
        try:
            metadata: dict = {}
            result = await ai.call_llm(
                _settings(),
                "prompt",
                tier="primary",
                routing_key="procurement_document_analysis",
                metadata=metadata,
                response_validator=validator,
            )
        finally:
            ai._post_llm_request = original_post

        self.assertEqual(result, "ok")
        self.assertEqual(calls, ["gemini-3.1-pro-preview", "gemini-3-pro-preview"])
        self.assertEqual(metadata["model"], "gemini-3-pro-preview")
        self.assertEqual(metadata["attempts"][0]["status"], "validation_error")

    async def test_call_llm_falls_back_after_hard_model_timeout(self) -> None:
        original_post = ai._post_llm_request
        calls: list[str] = []

        async def fake_post(selection, *_args, **_kwargs) -> str:
            calls.append(selection.model)
            if len(calls) == 1:
                await ai.asyncio.sleep(0.05)
            return "ok"

        ai._post_llm_request = fake_post
        try:
            metadata: dict = {}
            result = await ai.call_llm(
                _settings(),
                "prompt",
                tier="primary",
                routing_key="procurement_document_analysis",
                metadata=metadata,
                timeout_seconds=0.01,
            )
        finally:
            ai._post_llm_request = original_post

        self.assertEqual(result, "ok")
        self.assertEqual(calls, ["gemini-3.1-pro-preview", "gemini-3-pro-preview"])
        self.assertEqual(metadata["model"], "gemini-3-pro-preview")
        self.assertEqual(metadata["attempts"][0]["status"], "timeout")


class AiCallBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_call_llm_caps_model_attempts_and_records_redacted_trace(self) -> None:
        original_post = ai._post_llm_request
        calls: list[str] = []

        async def failing_post(selection, *_args, **_kwargs) -> str:
            calls.append(selection.model)
            raise RuntimeError("Authorization: super-secret")

        ai._post_llm_request = failing_post
        metadata: dict = {}
        try:
            with patch.dict(ai.os.environ, {"AIPOISK_LLM_MAX_MODEL_ATTEMPTS": "2"}):
                with self.assertRaisesRegex(RuntimeError, "tried models"):
                    await ai.call_llm(
                        _settings(),
                        "prompt",
                        tier="primary",
                        routing_key="procurement_document_analysis",
                        metadata=metadata,
                    )
        finally:
            ai._post_llm_request = original_post

        self.assertEqual(calls, ["gemini-3.1-pro-preview", "gemini-3-pro-preview"])
        self.assertEqual(len(metadata["attempts"]), 2)
        self.assertNotIn("super-secret", metadata["attempts"][0]["error"])
        self.assertIn("<redacted>", metadata["attempts"][0]["error"])

    async def test_call_llm_caps_total_http_request_attempts(self) -> None:
        original_client = ai.httpx.AsyncClient
        original_sleep = ai.asyncio.sleep
        calls = 0

        class Resp:
            status_code = 429
            reason_phrase = "Too Many Requests"
            headers = {}
            text = '{"error":{"message":"rate limited","code":429}}'

            def json(self):
                return json.loads(self.text)

        class Client:
            def __init__(self, *_args, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def post(self, *_args, **_kwargs):
                nonlocal calls
                calls += 1
                return Resp()

        async def noop_sleep(*_args, **_kwargs):
            return None

        ai.httpx.AsyncClient = Client
        ai.asyncio.sleep = noop_sleep
        metadata: dict = {}
        try:
            with patch.dict(ai.os.environ, {"AIPOISK_LLM_MAX_REQUEST_ATTEMPTS": "2"}):
                with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
                    await ai.call_llm(
                        _settings(),
                        "prompt",
                        tier="primary",
                        routing_key="procurement_document_analysis",
                        metadata=metadata,
                    )
        finally:
            ai.httpx.AsyncClient = original_client
            ai.asyncio.sleep = original_sleep

        self.assertEqual(calls, 2)
        self.assertEqual(metadata["attempts"][-1]["status"], "budget_exhausted")


def _settings_with_free_pool() -> SimpleNamespace:
    s = _settings()
    s.custom_ai_providers_json = json.dumps(
        [
            {"id": "gemini", "name": "Gemini", "baseUrl": "https://proxy.example/v1", "apiKey": "k"},
            {"id": "openrouter", "name": "OpenRouter", "baseUrl": "https://openrouter.ai/api/v1", "apiKey": "k"},
            {"id": "polza", "name": "Polza", "baseUrl": "https://api.polza.ai/v1", "apiKey": "k"},
            {"id": "z.ai", "name": "Z.AI", "baseUrl": "https://api.z.ai/api/coding/paas/v4", "apiKey": "k"},
            {"id": "open-ai", "name": "OpenAI", "baseUrl": "https://api.openai.example/v1", "apiKey": "k"},
        ]
    )
    s.saved_models_json = json.dumps(
        [
            {
                "provider": "openrouter",
                "modelId": "openai/gpt-oss-120b:free",
                "allowAutomaticFallback": True,
            },
            {
                "provider": "polza",
                "modelId": "google/gemini-3.5-flash",
                "allowAutomaticFallback": True,
                "isFree": True,
            },
            {
                "provider": "openrouter",
                "modelId": "anthropic/claude-haiku",
                "allowAutomaticFallback": True,
                "isFree": True,
            },
            {
                "provider": "gemini",
                "modelId": "gemini-2.5-flash-lite",
                "allowAutomaticFallback": True,
                "billingClass": "free",
            },
            {
                "provider": "z.ai",
                "modelId": "glm-4.6",
                "allowAutomaticFallback": True,
                "isFree": True,
            },
            {
                "provider": "open-ai",
                "modelId": "gpt-5.5",
                "allowAutomaticFallback": True,
                "isFree": True,
            },
        ]
    )
    return s


class AiFreeFallbackTests(unittest.TestCase):
    def test_free_fallback_skips_paid_providers_and_models(self) -> None:
        attempts = model_selection_attempts(
            _settings_with_free_pool(),
            tier="primary",
            routing_key="procurement_document_analysis",
        )
        models = [f"{a.provider_id}:{a.model}" for a in attempts]

        self.assertEqual(models[0], "gemini:gemini-3.1-pro-preview")
        # free providers/models are reachable as fallback
        self.assertIn("openrouter:openai/gpt-oss-120b:free", models)
        self.assertIn("gemini:gemini-2.5-flash-lite", models)
        self.assertIn("z.ai:glm-4.6", models)
        # paid never auto-added
        self.assertNotIn("polza:google/gemini-3.5-flash", models)
        self.assertNotIn("openrouter:anthropic/claude-haiku", models)
        self.assertNotIn("open-ai:gpt-5.5", models)

    def test_automatic_fallback_requires_explicit_allowlist_and_free_marker(self) -> None:
        settings = _settings_with_free_pool()
        entries = json.loads(settings.saved_models_json)
        entries.extend(
            [
                {"provider": "gemini", "modelId": "unmarked-model", "isFree": True},
                {
                    "provider": "gemini",
                    "modelId": "allowlisted-but-unclassified",
                    "allowAutomaticFallback": True,
                },
            ]
        )
        settings.saved_models_json = json.dumps(entries)

        models = [
            f"{item.provider_id}:{item.model}"
            for item in model_selection_attempts(
                settings,
                tier="primary",
                routing_key="procurement_document_analysis",
            )
        ]

        self.assertNotIn("gemini:unmarked-model", models)
        self.assertNotIn("gemini:allowlisted-but-unclassified", models)


class AiRetryTests(unittest.IsolatedAsyncioTestCase):
    def test_retry_after_clamps_negative_seconds_and_parses_http_date(self) -> None:
        now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        negative = SimpleNamespace(headers={"retry-after": "-5"})
        dated = SimpleNamespace(
            headers={
                "retry-after": (now + timedelta(seconds=12)).strftime("%a, %d %b %Y %H:%M:%S GMT")
            }
        )

        self.assertEqual(ai._retry_after_seconds(negative, now=now), 0.0)
        self.assertEqual(ai._retry_after_seconds(dated, now=now), 12.0)

    def test_http_timeout_separates_connect_read_write_and_pool_budgets(self) -> None:
        timeout = ai._httpx_timeout(90)

        self.assertEqual(timeout.connect, 10.0)
        self.assertEqual(timeout.read, 72.0)
        self.assertEqual(timeout.write, 30.0)
        self.assertEqual(timeout.pool, 10.0)

    async def test_retries_on_429_then_succeeds(self) -> None:
        original_client = ai.httpx.AsyncClient
        original_sleep = ai.asyncio.sleep
        calls = {"n": 0}

        class Resp:
            def __init__(self, status: int, content: str | None = None) -> None:
                self.status_code = status
                self.reason_phrase = "x"
                self.headers = {}
                if content is not None:
                    self.text = json.dumps({"choices": [{"message": {"content": content}}]})
                else:
                    self.text = json.dumps({"error": {"message": "rate limited", "code": status}})

            def json(self):
                return json.loads(self.text)

        class Client:
            def __init__(self, *_a, **_k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return None

            async def post(self, *_a, **_k):
                calls["n"] += 1
                return Resp(429) if calls["n"] < 3 else Resp(200, content="ok")

        async def noop_sleep(*_a, **_k):
            return None

        ai.httpx.AsyncClient = Client
        ai.asyncio.sleep = noop_sleep
        try:
            result = await ai._post_llm_request(
                ModelSelection("openrouter", "OpenRouter", "openai/gpt-oss-120b:free",
                               "https://openrouter.ai/api/v1/chat/completions", "k"),
                [{"role": "user", "content": "ok"}],
                json_mode=True,
                timeout_seconds=5,
            )
        finally:
            ai.httpx.AsyncClient = original_client
            ai.asyncio.sleep = original_sleep

        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)  # initial + 2 retries

    async def test_terminal_404_raises_clear_error_without_retry(self) -> None:
        original_client = ai.httpx.AsyncClient
        calls = {"n": 0}

        class Resp:
            status_code = 404
            reason_phrase = "Not Found"
            headers = {}
            text = '{"error":{"message":"No endpoints found","code":404}}'

            def json(self):
                return json.loads(self.text)

        class Client:
            def __init__(self, *_a, **_k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return None

            async def post(self, *_a, **_k):
                calls["n"] += 1
                return Resp()

        ai.httpx.AsyncClient = Client
        try:
            with self.assertRaisesRegex(RuntimeError, "No endpoints found"):
                await ai._post_llm_request(
                    ModelSelection("openrouter", "OpenRouter", "deepseek/deepseek-r1:free",
                                   "https://openrouter.ai/api/v1/chat/completions", "k"),
                    [{"role": "user", "content": "ok"}],
                    json_mode=False,
                    timeout_seconds=5,
                )
        finally:
            ai.httpx.AsyncClient = original_client
        self.assertEqual(calls["n"], 1)  # non-retriable: no retry

    async def test_transport_error_retried_then_clear_message(self) -> None:
        original_client = ai.httpx.AsyncClient
        original_sleep = ai.asyncio.sleep
        calls = {"n": 0}

        class Client:
            def __init__(self, *_a, **_k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return None

            async def post(self, *_a, **_k):
                calls["n"] += 1
                raise ai.httpx.ReadError("")  # empty message, like the prod failure

        async def noop_sleep(*_a, **_k):
            return None

        ai.httpx.AsyncClient = Client
        ai.asyncio.sleep = noop_sleep
        try:
            with self.assertRaisesRegex(RuntimeError, "transport ReadError"):
                await ai._post_llm_request(
                    ModelSelection("z.ai", "Z.AI", "glm-4.6", "https://api.z.ai/x", "k"),
                    [{"role": "user", "content": "ok"}],
                    json_mode=False,
                    timeout_seconds=5,
                )
        finally:
            ai.httpx.AsyncClient = original_client
            ai.asyncio.sleep = original_sleep
        self.assertEqual(calls["n"], 3)  # retried up to the limit


class AiProcessLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_limiter_is_shared_across_event_loops(self) -> None:
        active = 0
        max_active = 0
        state_lock = threading.Lock()

        async def worker() -> None:
            nonlocal active, max_active
            await ai._process_llm_limiter.acquire()
            try:
                with state_lock:
                    active += 1
                    max_active = max(max_active, active)
                await ai.asyncio.sleep(0.02)
                with state_lock:
                    active -= 1
            finally:
                ai._process_llm_limiter.release()

        ai._process_llm_limiter.reset_for_tests()
        try:
            with patch.dict(ai.os.environ, {"AIPOISK_LLM_MAX_CONCURRENCY": "1"}):
                await ai.asyncio.gather(
                    ai.asyncio.to_thread(ai.asyncio.run, worker()),
                    ai.asyncio.to_thread(ai.asyncio.run, worker()),
                )
        finally:
            ai._process_llm_limiter.reset_for_tests()

        self.assertEqual(max_active, 1)


def _settings_with_manual_fallback() -> SimpleNamespace:
    s = _settings_with_free_pool()
    # markers deliberately NOT present in saved_models, so their presence/absence
    # proves which manual list (analysis vs supplier) was used.
    s.ai_analysis_fallback_json = json.dumps(
        [
            {"provider": "z.ai", "modelId": "glm-5.2"},
            {"provider": "polza", "modelId": "google/gemini-3.5-flash"},  # paid, allowed in manual
        ]
    )
    s.ai_supplier_fallback_json = json.dumps(
        [{"provider": "openrouter", "modelId": "meta-llama/llama-3.3-70b-instruct:free"}]
    )
    return s


class AiManualFallbackTests(unittest.TestCase):
    def test_manual_list_tried_before_auto_pool_and_allows_paid(self) -> None:
        attempts = model_selection_attempts(
            _settings_with_manual_fallback(),
            tier="primary",
            routing_key="procurement_document_analysis",
        )
        models = [f"{a.provider_id}:{a.model}" for a in attempts]

        self.assertEqual(models[0], "gemini:gemini-3.1-pro-preview")
        # manual entries present (paid polza allowed in the manual list)
        self.assertIn("z.ai:glm-5.2", models)
        self.assertIn("polza:google/gemini-3.5-flash", models)
        # manual order preserved, and manual runs before the auto free pool
        self.assertLess(models.index("z.ai:glm-5.2"), models.index("polza:google/gemini-3.5-flash"))
        self.assertLess(models.index("polza:google/gemini-3.5-flash"), models.index("gemini:gemini-3-pro-preview"))
        self.assertLess(models.index("z.ai:glm-5.2"), models.index("gemini:gemini-2.5-flash-lite"))
        # auto pool still excludes paid models that are NOT in the manual list
        self.assertNotIn("openrouter:anthropic/claude-haiku", models)

    def test_supplier_routing_uses_supplier_manual_list(self) -> None:
        attempts = model_selection_attempts(
            _settings_with_manual_fallback(),
            tier="light",
            routing_key="supplier_query_generation",
        )
        models = [f"{a.provider_id}:{a.model}" for a in attempts]

        # supplier manual entry is used
        self.assertIn("openrouter:meta-llama/llama-3.3-70b-instruct:free", models)
        # analysis-only manual marker is NOT used for the supplier scenario
        self.assertNotIn("z.ai:glm-5.2", models)

    def test_empty_manual_keeps_free_only_autopool(self) -> None:
        attempts = model_selection_attempts(
            _settings_with_free_pool(),
            tier="primary",
            routing_key="procurement_document_analysis",
        )
        models = [f"{a.provider_id}:{a.model}" for a in attempts]
        self.assertNotIn("polza:google/gemini-3.5-flash", models)
        self.assertIn("openrouter:openai/gpt-oss-120b:free", models)


if __name__ == "__main__":
    unittest.main()
