#!/usr/bin/env python3
"""Register the consent-based TenderLex events without modifying existing goals."""
import argparse
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
GOALS = {
    "cabinet_click": "TenderLex: переход в кабинет",
    "telegram_click": "TenderLex: переход в Telegram",
    "whatsapp_click": "TenderLex: переход в WhatsApp",
    "max_click": "TenderLex: переход в MAX",
    "phone_click": "TenderLex: звонок",
    "email_click": "TenderLex: письмо",
    "registration_success": "TenderLex: успешная регистрация",
    "login_success": "TenderLex: успешный вход",
    "email_verified": "TenderLex: подтверждение email",
    "task_started": "TenderLex: задача принята",
    "result_downloaded": "TenderLex: результат скачан",
}

def existing_action_ids(goals):
    return {condition["url"]: goal["id"] for goal in goals if goal.get("type") == "action"
            for condition in goal.get("conditions", []) if condition.get("type") == "exact" and condition.get("url") in GOALS}

def read_config():
    values = {}
    for line in (ROOT / ".env").read_text().splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key in {"YANDEX_METRIKA_TOKEN", "YANDEX_METRIKA_COUNTER_ID"}:
            values[key] = value.strip().strip("\"'")
    for key in {"YANDEX_METRIKA_TOKEN", "YANDEX_METRIKA_COUNTER_ID"}:
        if os.environ.get(key): values[key] = os.environ[key]
    return values

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create missing goals; otherwise report only")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    config = read_config()
    token = config.get("YANDEX_METRIKA_TOKEN")
    counter = config.get("YANDEX_METRIKA_COUNTER_ID", "109753178")
    if not token or not counter.isdigit(): raise SystemExit("Metrika credentials/counter unavailable")
    endpoint = f"https://api-metrika.yandex.net/management/v1/counter/{counter}/goals"
    def request(payload=None):
        body = json.dumps(payload).encode() if payload else None
        req = urllib.request.Request(endpoint, data=body,
                headers={"Authorization": f"OAuth {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as response: return json.load(response)
    before = request()
    ids = existing_action_ids(before.get("goals", []))
    if args.evidence_dir:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence = args.evidence_dir / "metrika-goals-before.json"
        if not evidence.exists(): evidence.write_text(json.dumps(before, ensure_ascii=False, indent=2))
    created = []
    for event, label in GOALS.items():
        if event in ids or not args.apply: continue
        data = request({"goal": {"name": label, "type": "action",
                         "conditions": [{"type": "exact", "url": event}]}})
        ids[event] = data["goal"]["id"]
        created.append(event)
    after = request() if args.apply else before
    verified = existing_action_ids(after.get("goals", []))
    result = {"counter_id": counter, "created": created, "goal_ids": verified,
              "missing": sorted(set(GOALS) - set(verified)), "primary_goal_id": verified.get("registration_success")}
    if args.evidence_dir:
        (args.evidence_dir / "metrika-goals-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__": main()
