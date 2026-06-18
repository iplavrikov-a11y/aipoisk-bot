from __future__ import annotations

import unittest
from types import SimpleNamespace

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
        attempts = model_selection_attempts(
            _settings(),
            tier="light",
            routing_key="supplier_query_generation",
        )

        self.assertEqual(
            [item.model for item in attempts],
            ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview", "gemini-3-flash-preview", "gemini-2.5-flash-lite"],
        )

    def test_supplier_routing_uses_supplier_model_not_function_override(self) -> None:
        selection = ai.get_model_selection(
            _settings(),
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


if __name__ == "__main__":
    unittest.main()
