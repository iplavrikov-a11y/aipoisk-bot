#!/usr/bin/env python3
"""Official Yandex Direct API (v5 / v501, JSON) client for TenderLex.

Safety defaults:
- Reads credentials strictly from environment or /root/projects/tenderlex/.env.
- Never prints or logs OAuth tokens.
- Read-only commands run safely anytime; write commands require explicit --apply.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

API_V5_BASE = "https://api.direct.yandex.com/json/v5"
API_V501_BASE = "https://api.direct.yandex.com/json/v501"
REPORTS_URL = "https://api.direct.yandex.com/json/v5/reports"


def load_direct_config() -> Dict[str, str]:
    """Load Yandex Direct credentials without echoing secrets."""
    values: Dict[str, str] = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key in {"YANDEX_DIRECT_TOKEN", "YANDEX_DIRECT_CLIENT_ID", "YANDEX_DIRECT_LOGIN"}:
                values[key] = val.strip().strip("\"'")
    for key in ("YANDEX_DIRECT_TOKEN", "YANDEX_DIRECT_CLIENT_ID", "YANDEX_DIRECT_LOGIN"):
        if os.environ.get(key):
            values[key] = os.environ[key].strip()
    return values


class YandexDirectClient:
    """Thin, transparent wrapper over official Yandex Direct JSON API v5 / v501."""

    def __init__(self, token: str, client_login: str = "") -> None:
        if not token:
            raise ValueError("YANDEX_DIRECT_TOKEN is not configured")
        self._token = token
        self._client_login = client_login

    def call(
        self,
        service: str,
        method: str,
        params: Dict[str, Any],
        *,
        version: str = "v5",
        timeout: int = 20,
    ) -> Dict[str, Any]:
        base = API_V501_BASE if version == "v501" else API_V5_BASE
        url = f"{base}/{service}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept-Language": "ru",
            "Content-Type": "application/json; charset=utf-8",
        }
        if self._client_login:
            headers["Client-Login"] = self._client_login
        body = json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "ok": "error" not in data,
                    "http_status": resp.status,
                    "units": resp.headers.get("Units"),
                    "request_id": resp.headers.get("RequestId"),
                    "data": data,
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = {"raw": raw[:500]}
            return {
                "ok": False,
                "http_status": exc.code,
                "units": exc.headers.get("Units") if exc.headers else None,
                "request_id": exc.headers.get("RequestId") if exc.headers else None,
                "data": parsed,
            }

    def check_access(self) -> Dict[str, Any]:
        """Verify whether Yandex Direct API full access has been approved."""
        res = self.call(
            "campaigns",
            "get",
            {"SelectionCriteria": {}, "FieldNames": ["Id", "Name", "Status", "State", "Type"]},
            version="v5",
        )
        err = res["data"].get("error") if isinstance(res["data"], dict) else None
        if err:
            code = err.get("error_code")
            return {
                "approved": False,
                "error_code": code,
                "error_string": err.get("error_string"),
                "error_detail": err.get("error_detail"),
                "waiting_moderation": code == 58,
            }
        campaigns = res["data"].get("result", {}).get("Campaigns", [])
        return {
            "approved": True,
            "units": res.get("units"),
            "campaigns_count": len(campaigns),
            "campaigns": campaigns,
        }

    def list_campaigns(self) -> Dict[str, Any]:
        return self.call(
            "campaigns",
            "get",
            {
                "SelectionCriteria": {},
                "FieldNames": ["Id", "Name", "Status", "State", "Type", "StartDate", "DailyBudget"],
            },
            version="v501",
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="TenderLex Yandex Direct API v5/v501 CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-access", help="Check whether API application is approved and list campaigns")
    sub.add_parser("campaigns", help="List campaigns via API v501")

    args = parser.parse_args(argv)
    cfg = load_direct_config()
    if not cfg.get("YANDEX_DIRECT_TOKEN"):
        print(json.dumps({"ok": False, "error": "YANDEX_DIRECT_TOKEN missing in .env"}, ensure_ascii=False))
        return 1

    # For a direct advertiser using their own login's OAuth token, Client-Login header is not needed.
    client = YandexDirectClient(token=cfg["YANDEX_DIRECT_TOKEN"])
    if args.command == "check-access":
        result = client.check_access()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("approved") else 2
    if args.command == "campaigns":
        result = client.list_campaigns()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
