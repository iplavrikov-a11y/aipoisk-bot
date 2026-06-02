# AI Poisk Deploy Fix

Date: 2026-06-01

## Goal

Make `aipoisk.lexelence.ru` run on the Netherlands server, finish missing access/report controls, and verify the bot/admin pipeline with evidence.

## Acceptance Criteria

- Nginx/FastAPI on `202.71.13.57` serve the admin UI and `/api/health`.
- `aipoisk-api.service`, `aipoisk-bot.service`, and `nginx` are active after rollout.
- DNS root cause is identified with concrete target and current bad value.
- Admin panel supports manual access controls: active flag, feature flags, expiry date, monthly job/file limits, notes.
- Runtime enforces active/expiry/feature/monthly access rules.
- Telegram bot supports both supplier search and Word report mode.
- Retention settings remove expired completed/failed job storage.
- Verification covers build, Python compile, API, AI test, Telegram token/webhook state, upload jobs, and browser UI.
