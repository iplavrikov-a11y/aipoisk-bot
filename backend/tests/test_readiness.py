from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import Response

import app.main as main_module
import app.readiness as readiness


class FakeHttpResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True}

    def json(self) -> dict:
        return self._payload


class FakeHttpClient:
    def __init__(self, calls: list[str], response: FakeHttpResponse) -> None:
        self.calls = calls
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def get(self, url: str):
        self.calls.append(url)
        return self.response


class ReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        readiness.clear_readiness_cache()

    def test_tender_source_probe_is_cached_for_fifteen_seconds(self) -> None:
        calls: list[str] = []
        fake_client = FakeHttpClient(calls, FakeHttpResponse())

        with (
            patch.object(readiness.config, "tender_source_service_url", "http://127.0.0.1:8096"),
            patch("app.readiness.httpx.Client", return_value=fake_client),
        ):
            first = readiness.tender_source_readiness()
            second = readiness.tender_source_readiness()

        self.assertTrue(first["ok"])
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(calls, ["http://127.0.0.1:8096/ready"])

    def test_configured_tender_source_outage_fails_closed(self) -> None:
        with (
            patch.object(readiness.config, "tender_source_service_url", "http://127.0.0.1:8096"),
            patch.object(readiness.config, "tenderplan_api_token", "direct-token"),
            patch("app.readiness.httpx.Client", side_effect=RuntimeError("down")),
            patch("app.readiness.database_queue_readiness", return_value={
                "database": {"ok": True},
                "queue": {"ok": True, "pending": 0, "running": 0, "stale_running": 0},
            }),
        ):
            payload = readiness.build_readiness(SimpleNamespace())

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["tender_source"]["configured"])
        self.assertEqual(payload["tender_source"]["error"], "source_unavailable")

    def test_direct_source_is_valid_only_when_shared_service_is_not_configured(self) -> None:
        with (
            patch.object(readiness.config, "tender_source_service_url", ""),
            patch.object(readiness.config, "tenderplan_api_token", "direct-token"),
        ):
            source = readiness.tender_source_readiness()

        self.assertTrue(source["ok"])
        self.assertFalse(source["configured"])
        self.assertTrue(source["direct_configured"])

    def test_readiness_endpoint_returns_503_when_dependency_is_unready(self) -> None:
        response = Response()
        payload = {"ok": False, "database": {"ok": True}}

        with patch.object(main_module, "build_readiness", return_value=payload):
            result = main_module.readiness(response=response, db=SimpleNamespace())

        self.assertEqual(result, payload)
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
