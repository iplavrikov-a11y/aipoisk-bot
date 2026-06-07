# Evidence

## Backend

- `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest backend/tests/test_customer_api.py -q`
  - Result: `7 passed`
- `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest backend/tests/test_api_guards.py backend/tests/test_access_limits.py backend/tests/test_customer_api.py -q`
  - Result: `54 passed`
- `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest backend/tests -q`
  - Result: `240 passed, 43 subtests passed`

## Frontend

- `cd site && npm run typecheck`
  - Result: passed
- `cd site && npm run build`
  - Result: passed; routes include `/`, `/cabinet`, `/terms`, `/privacy`, `/personal-data`, `/robots.txt`, `/sitemap.xml`
- `cd frontend && npm run build`
  - Result: passed

## Browser Smoke

Dev server:

- `cd site && npx next dev --hostname 127.0.0.1 --port 3094`

Playwright:

- `TARGET_URL=http://127.0.0.1:3094 node run.js /tmp/playwright-test-tenderlex-cabinet.js`
  - Landing H1: `Анализ закупок и поиск поставщиков на сайте и в Telegram`
  - Cabinet H1: `Личный кабинет TenderLex`
  - Screenshots:
    - `.agent/tasks/2026-06-07-web-cabinet/raw/site-home-desktop.png`
    - `.agent/tasks/2026-06-07-web-cabinet/raw/cabinet-desktop.png`
    - `.agent/tasks/2026-06-07-web-cabinet/raw/cabinet-mobile.png`

## Production Deploy Smoke

- Added `AIPOISK_CUSTOMER_SESSION_HOURS=168` to `.env.example`.
- Stopped temporary Next dev server on `127.0.0.1:3094`.
- `systemctl restart aipoisk-api.service aipoisk-worker.service tenderlex-site.service`
  - Result: command exited with code `0`.
- `systemctl --no-pager --full status aipoisk-api.service aipoisk-worker.service tenderlex-site.service`
  - Result: all three services active since `2026-06-07 17:03:56 UTC`.
- `curl -fsS http://127.0.0.1:8088/api/health`
  - Result: `{"ok":true,"domain":"https://tenderlex.ru","logistics_enabled":false}`
- `curl -i -s http://127.0.0.1:8088/api/customer/auth/session`
  - Result: `HTTP/1.1 200 OK`, `{"authenticated":false}`
- `curl -i -s https://tenderlex.ru/api/customer/auth/session`
  - Result: `HTTP/2 200`, `{"authenticated":false}`
- `curl -fsS https://tenderlex.ru/robots.txt`
  - Result: includes `Disallow: /api/` and `Disallow: /cabinet`.
- `curl -fsS https://tenderlex.ru/`
  - Result: includes landing CTA text `Личный кабинет`, `Попробовать на сайте`, `Открыть Telegram`.
- `curl -fsS https://tenderlex.ru/cabinet`
  - Result: includes `Личный кабинет TenderLex`, `noindex, nofollow`, `отдельный web-баланс`.
- Playwright production desktop smoke on `https://tenderlex.ru`
  - Landing H1: `Анализ закупок и поиск поставщиков на сайте и в Telegram`
  - Cabinet H1: `Личный кабинет TenderLex`
  - Visible controls: cabinet CTA, login button, registration tab, email field
  - Screenshots:
    - `.agent/tasks/2026-06-07-web-cabinet/raw/prod-home-desktop.png`
    - `.agent/tasks/2026-06-07-web-cabinet/raw/prod-cabinet-desktop.png`
- Playwright production mobile smoke on `https://tenderlex.ru/cabinet`
  - Cabinet H1: `Личный кабинет TenderLex`
  - Visible controls: login button, email field
  - Screenshot:
    - `.agent/tasks/2026-06-07-web-cabinet/raw/prod-cabinet-mobile.png`

## Product UX and Access Recovery Update

- Replaced guest-cabinet technical copy:
  - Removed `отдельный web-баланс`, `DOCX и XLSX файлы`, `защищённая сессия`.
  - Added user-facing tasks: `Разобрать закупку`, `Найти поставщиков`, `Вернуться к результатам`.
- Added customer password recovery request:
  - `POST /api/customer/auth/password-reset/request`
  - Public response is neutral and does not reveal whether the email exists.
- Added admin password reset flow:
  - `GET /api/web-password-resets?status=open`
  - `POST /api/web-password-resets/{id}/complete`
  - `POST /api/web-password-resets/{id}/ignore`
  - Completing a reset revokes existing website sessions.
- Added legal pages:
  - `/terms`
  - `/privacy`
  - `/personal-data`
- Added operations runbook:
  - `docs/TENDERLEX_WEB_CABINET_RUNBOOK.md`
- Fixed production session bug:
  - SQLite can return naive datetimes for `web_sessions.expires_at`; `get_web_session_by_token` now normalizes to UTC before comparing with `now_utc()`.
- Updated verification:
  - `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest backend/tests/test_customer_api.py -q`
    - Result: `7 passed`
  - `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest backend/tests -q`
    - Result: `240 passed, 43 subtests passed`
  - `cd site && npm run typecheck`
    - Result: passed after restoring `site/next-env.d.ts` from dev-server output.
  - `cd site && npm run build`
    - Result: passed; routes include legal pages.
  - `cd frontend && npm run build`
    - Result: passed.
  - `git diff --check`
    - Result: clean.
- Production restart after fix:
  - `systemctl restart aipoisk-api.service aipoisk-worker.service tenderlex-site.service`
  - Result: services active since `2026-06-07 18:59:16 UTC`, then restarted again after session fix.
- Production curl checks:
  - `https://tenderlex.ru/cabinet` includes `Работайте с закупками прямо на сайте`, `Разобрать закупку`, `Найти поставщиков`, `Не помню пароль`.
  - `https://tenderlex.ru/cabinet` no longer includes `web-баланс`, `защищённая сессия`, `DOCX и XLSX файлы`.
  - `https://tenderlex.ru/terms`, `/privacy`, `/personal-data` return expected H1 text.
  - `https://tenderlex.ru/sitemap.xml` includes `/terms`, `/privacy`, `/personal-data`.
- Playwright production smoke:
  - `TARGET_URL=https://tenderlex.ru node run.js /tmp/playwright-test-tenderlex-copy.js`
  - Result: passed for cabinet copy, password reset UI, legal pages, desktop and mobile.
- Live product smoke:
  - Registered temporary web user `smoke-web-20260607190610@example.invalid`.
  - Verified authenticated session, empty jobs list, and reset request.
  - Cleaned up all `smoke-web-%@example.invalid` web users, sessions, reset requests, billing rows, and clients with zero jobs.
  - Verification after cleanup: smoke user count `0`.

## Notes

- Before deployment, local production backend on `127.0.0.1:8088` was still running the previous code and `/api/customer/*` returned `404`.
- After deployment/restart, `/api/customer/auth/session` returns `200` with `{"authenticated":false}` locally and through `https://tenderlex.ru/api/customer/auth/session`.
- Cabinet guest session handling was adjusted so a missing customer session endpoint does not display a raw technical `Not Found` message on the login screen.
- A temporary production web user was created for live registration/session/reset smoke and then removed with a strict `smoke-web-%@example.invalid` guard. No smoke users remain.
