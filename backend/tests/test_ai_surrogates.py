from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.ai import call_llm, _post_llm_request, ModelSelection
from app.document_parser import clean_surrogates


class AiSurrogateTests(unittest.IsolatedAsyncioTestCase):
    def test_clean_surrogates_prevents_httpx_unicode_encode_error(self) -> None:
        # Lone surrogate code points cause UnicodeEncodeError in httpx if uncleaned
        bad_prompt = "Тестовый промпт с \udc8e\udc8d и \ud800"
        with self.assertRaises(UnicodeEncodeError):
            bad_prompt.encode("utf-8")

        cleaned = clean_surrogates(bad_prompt)
        # Cleaned prompt must encode to UTF-8 cleanly
        encoded = cleaned.encode("utf-8")
        self.assertIsInstance(encoded, bytes)

        # httpx request with cleaned JSON must succeed serialization
        req = httpx.Request(
            "POST",
            "http://example.com",
            json={"messages": [{"role": "user", "content": cleaned}]},
        )
        self.assertIn(b"content", req.content)

    async def test_post_llm_request_cleans_surrogates_in_payload(self) -> None:
        selection = ModelSelection(
            provider_id="test",
            provider_name="TestAI",
            model="test-model",
            api_key="secret",
            base_url="http://test.local/v1/chat/completions",
        )
        bad_messages = [
            {"role": "system", "content": "Система \ud800"},
            {"role": "user", "content": "Запрос с \udc8e\udc8d суррогатами"},
        ]

        captured_payloads = []

        async def fake_post(_client_self, url, **kwargs):
            payload = kwargs.get("json")
            captured_payloads.append(payload)
            # Simulate real httpx post json encoding
            import json
            json.dumps(payload).encode("utf-8")
            response = httpx.Response(
                200,
                json={"choices": [{"message": {"content": "Ответ ИИ"}}]},
                request=httpx.Request("POST", url),
            )
            return response

        with patch.object(httpx.AsyncClient, "post", new=fake_post):
            res = await _post_llm_request(selection, bad_messages, json_mode=False, timeout_seconds=10.0)
            self.assertEqual(res, "Ответ ИИ")
            self.assertEqual(len(captured_payloads), 1)
            msgs = captured_payloads[0]["messages"]
            for m in msgs:
                self.assertFalse(any(0xD800 <= ord(c) <= 0xDFFF for c in m["content"]))


if __name__ == "__main__":
    unittest.main()
