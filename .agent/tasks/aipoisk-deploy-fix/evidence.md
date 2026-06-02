# Evidence

Date: 2026-06-01

## Root Cause

- `202.71.13.57` geolocates to NL (`HOSTKEY B.V.`, Lelystad) and is the current server running AI Poisk.
- Before the fix, `aipoisk.lexelence.ru` and wildcard `*.lexelence.ru` resolved through Jino DNS to `81.177.141.15` (`parking.jino.ru`, Moscow/RU).
- Existing production subdomains such as `emailagent.lexelence.ru`, `max.lexelence.ru`, `autopost.lexelence.ru`, and `vpn.lexelence.ru` resolve to `202.71.13.57`.
- Current authoritative DNS is correct: Jino authoritative nameservers return `aipoisk.lexelence.ru -> 202.71.13.57`.
- Current recursive DNS is still inconsistent. Cloudflare (`1.1.1.1`), Quad9 (`9.9.9.9`), Yandex (`77.88.8.8`), and OpenDNS (`208.67.222.222`) returned `202.71.13.57`, while Google DNS (`8.8.8.8` / `8.8.4.4`) still returned stale `81.177.141.15` after the authoritative fix.
- The stale `81.177.141.15` path does not reach this VPS and timed out on forced HTTP/HTTPS checks from this server.
- Systemic DNS finding: authoritative `*.lexelence.ru` originally pointed to `81.177.141.15`, while existing production subdomains such as `emailagent.lexelence.ru` and `vpn.lexelence.ru` had explicit records to `202.71.13.57`. `aipoisk.lexelence.ru` was created after clients/resolvers had already seen the wildcard answer, so stale recursive caches can continue serving `81.177.141.15` for this exact new name until TTL expiry.

## Verification Run

- 2026-06-01 18:43 UTC DNS/HTTPS monitor:
  - `@1.1.1.1` consistently returned `202.71.13.57`;
  - Google DNS (`@8.8.8.8`, `@8.8.4.4`) alternated between `202.71.13.57` and stale `81.177.141.15`;
  - ordinary `curl https://aipoisk.lexelence.ru/` returned `200` when it connected to `202.71.13.57` and timed out when resolution selected `81.177.141.15`.
- 2026-06-01 18:49 UTC architecture comparison:
  - `@ns1.jino.ru aipoisk.lexelence.ru A` -> `202.71.13.57`;
  - `@ns1.jino.ru *.lexelence.ru A` -> `81.177.141.15` before the user changed the wildcard;
  - `@ns1.jino.ru lexelence.ru A` -> `81.177.141.15`;
  - `@8.8.4.4 emailagent.lexelence.ru A` and `vpn.lexelence.ru A` -> `202.71.13.57`;
  - `@8.8.4.4 aipoisk.lexelence.ru A` still intermittently returned stale `81.177.141.15`;
  - no AAAA records were returned for `aipoisk.lexelence.ru`, `emailagent.lexelence.ru`, `vpn.lexelence.ru`, wildcard, or apex.
- 2026-06-01 18:50 UTC nginx architecture comparison:
  - `/etc/nginx/stream.conf` sends public `443` to `127.0.0.1:4443` by default, same path used by working HTTPS vhosts;
  - forced SNI checks against `202.71.13.57:443` returned `200` for `aipoisk.lexelence.ru`, `emailagent.lexelence.ru`, and `vpn.lexelence.ru`;
  - `openssl s_client -connect 202.71.13.57:443 -servername aipoisk.lexelence.ru` returned the Let's Encrypt certificate for `aipoisk.lexelence.ru`;
  - current nginx logs did not contain matching `aipoisk` upstream `502` errors.
- 2026-06-01 18:52 UTC Google Public DNS cache flush attempt:
  - direct POST to `https://dns.google/cache` failed with `reCAPTCHA failure`; manual/browser cache flush would be required for Google cache purge.
- 2026-06-01 18:57 UTC after the user changed wildcard DNS:
  - authoritative `@ns1.jino.ru` / `@ns2.jino.ru` / `@ns4.jino.ru` returned `aipoisk.lexelence.ru -> 202.71.13.57`;
  - authoritative `@ns1.jino.ru` / `@ns2.jino.ru` / `@ns4.jino.ru` returned `*.lexelence.ru -> 202.71.13.57`;
  - recursive `@1.1.1.1`, `@9.9.9.9`, `@77.88.8.8`, and `@208.67.222.222` returned `202.71.13.57`;
  - recursive `@8.8.8.8` and `@8.8.4.4` still returned stale `81.177.141.15` with TTL about `6733` seconds;
  - ordinary HTTPS repeated checks alternated between timeout on stale DNS and `200` on `202.71.13.57`;
  - no matching current `aipoisk` request from the user's IP appeared in nginx logs on `202.71.13.57`.
- Backend compile: `./.venv/bin/python -m compileall app` passed.
- Frontend build: `npm run build` passed.
- Regression smoke on temporary SQLite DB passed:
  - expired access blocks;
  - disabled Word access blocks;
  - monthly job/file limits block;
  - retention cleanup removes expired job DB row and storage directory.
- Services after restart: `aipoisk-api.service`, `aipoisk-bot.service`, `nginx` all `active`.
- Local health: `http://127.0.0.1:8088/api/health` returned `{"ok":true,...,"logistics_enabled":false}`.
- Certificate issued with webroot: `/etc/letsencrypt/live/aipoisk.lexelence.ru/`, expiry `2026-08-30`.
- Certbot renewal dry-run passed: `/etc/letsencrypt/live/aipoisk.lexelence.ru/fullchain.pem (success)`.
- Forced-host HTTP check: `--resolve aipoisk.lexelence.ru:80:202.71.13.57 http://aipoisk.lexelence.ru/` returned `301` to HTTPS.
- Forced-host HTTPS check: `--resolve aipoisk.lexelence.ru:443:202.71.13.57 https://aipoisk.lexelence.ru/` returned `200 OK`.
- Forced-host HTTPS health check: `--resolve ... https://aipoisk.lexelence.ru/api/health` returned `200 OK`.
- Public HTTPS from this VPS is not stable while recursive DNS is mixed: repeated ordinary checks alternated between `200` on `202.71.13.57` and timeout when resolution selected stale `81.177.141.15`.
- AI test: `/api/ai/test` returned status `200` and response `Ок.`.
- Telegram: `getMe_ok=True`, username `tenderlex_bot`, webhook URL empty, pending updates `0`.
- Upload smoke:
  - `supplier_search` completed as `partial`, result ZIP downloaded (`5511` bytes), verified suppliers `0/15` on artificial test TZ;
  - `procurement_report` completed, Word ZIP downloaded (`37287` bytes).
- Browser UI:
  - dashboard screenshot via Playwright with forced DNS mapping passed, console errors `0`;
  - clients UI create/edit smoke passed, row visible, console errors `0`, temporary client cleaned.

## Current Status

The public browser path is working on `https://aipoisk.lexelence.ru/`. The target server returns the admin HTML, `/api/health` returns `200`, and the user confirmed the site opens in their browser. nginx still logs pre-existing `protocol options redefined for 0.0.0.0:4443` warnings from mixed HTTP/2 settings across existing vhosts, but `nginx -t` is successful and this is not blocking AI Poisk.

## 2026-06-01 19:25 UTC Follow-up Verification

- User confirmed the public site now loads in the browser.
- Public `https://aipoisk.lexelence.ru/` returned `HTTP/2 200` and the current built assets:
  - `index-Cq7h_rMM.js`
  - `index-Beis1rwg.css`
- Added admin username/password login backed by an `HttpOnly`, `Secure`, `SameSite=strict` cookie session.
- Auth checks:
  - unauthenticated `/api/dashboard` returned `401`;
  - valid `/api/auth/login` returned `200`;
  - dashboard with session cookie returned `200`;
  - invalid login returned `401`;
  - public `/api/auth/session` without cookie returned `{"ok":false}` instead of a noisy browser-console `401`.
- Browser check via Playwright:
  - login form visible before login;
  - after login, dashboard and `Выйти` are visible;
  - console errors: `0`;
  - screenshot: `/tmp/aipoisk-auth-browser-check.png`.
- Telegram bot UX changed from slash-first to button-first:
  - `🔎 Поиск поставщиков`;
  - `📄 Word-отчёт`;
  - `📊 Последние задачи`;
  - `🔐 Мой доступ`;
  - `❓ Помощь`;
  - `🆔 Мой Telegram ID`.
- Telegram menu import smoke passed and `aipoisk-bot.service` is active.
- Verification:
  - `./.venv/bin/python -m compileall app` passed;
  - `npm run build` passed;
  - `nginx -t` passed;
  - `aipoisk-api.service`, `aipoisk-bot.service`, and `nginx` are active.

## 2026-06-01 20:28 UTC Supplier Search Fix

- User correction: AI Poisk must not reuse EmailAgent supplier search; EmailAgent search is considered poor for this bot.
- Root cause confirmed in `backend/app/supplier_search.py`: supplier discovery depended on `supplier_search_adapter_*` / old `gemini-...` settings and produced `candidates: []`, so the Telegram job returned an empty report.
- Replaced active candidate discovery with real Tavily web-search flow backed by the Hermes Tavily key:
  - real web search results;
  - blocked marketplaces/directories/government/reference pages as final suppliers;
  - official-site fetch;
  - context relevance gate;
  - contact extraction;
  - AI verifier only after local relevance/contact checks.
- Updated runtime settings in `data/aipoisk.db`:
  - `supplier_search_adapter_base_url = https://api.tavily.com`;
  - `supplier_search_adapter_model = tavily`;
  - key is set; value not printed.
- SQLite backup before runtime setting update:
  - `data/aipoisk.db.backup-before-tavily-20260601T202145Z`.
- Changed zero-result behavior:
  - if confirmed suppliers are `0`, the job is marked `failed`;
  - no empty XLSX is generated or sent.
- Reprocessed user job `c01e10dd5ac64de4a9e1c0b827a668a8` from the same DOCX:
  - status `partial`;
  - message `Частично готово: подтверждено 3/15`;
  - supplier rows in DB: `3`;
  - result path is `.xlsx`, not ZIP.
- Confirmed suppliers in XLSX:
  - АО "Кемеровский Экспериментальный завод средств безопасности" / `kezsb.ru`;
  - СИЗПрофи / `siz-profi.com`;
  - Завод «Озон» ГС и ПО / `ozongspo.com`.
- Download endpoint verification:
  - `/api/jobs/c01e10dd5ac64de4a9e1c0b827a668a8/download` returned `HTTP 200`;
  - content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`;
  - filename ended with `.xlsx`;
  - downloaded file opened with `openpyxl`, `rows=6`, `cols=10`.
- Frontend/admin verification:
  - `npm run build` passed;
  - public build assets are `index-DSkhVolT.js` and `index-ibYNjTQi.css`;
  - new label present: `Веб-поиск поставщиков`;
  - old label absent: `Поисковый адаптер поставщиков`;
  - `Tavily API URL` label present.
- Follow-up admin download fix:
  - frontend no longer forces downloaded job files to `aipoisk-*.zip`;
  - filename is now taken from `Content-Disposition`, with `.xlsx` fallback for supplier search and `.docx` fallback for Word reports;
  - rebuilt bundle no longer contains the old `.zip` fallback.
- Service verification after restart:
  - `aipoisk-api.service`: active;
  - `aipoisk-bot.service`: active;
  - `nginx`: active;
  - `http://127.0.0.1:8088/api/health` returned `{"ok":true,...,"logistics_enabled":false}`;
  - recent journal showed clean stop/start and Uvicorn startup, no current traceback.
- Known limitation:
  - this exact obscure item produced only `3/15` confirmed official suppliers. The bot now returns a partial XLSX with evidence instead of an empty archive.

## 2026-06-01 23:17 UTC Supplier Search Quality Fix

- User correction: `3/15` is not acceptable; supplier search must seek at least 15 real заводы/поставщики/дилеры where possible, and must not use EmailAgent search or the old Gemini adapter path.
- Root cause confirmed:
  - Tavily search originally found candidates, but the verifier was too strict: it rejected profile suppliers/dilers when the exact SKU was not shown or when email was public (`mail.ru`/`yandex.ru`);
  - Tavily later returned HTTP `432` plan usage limit, so depending only on Tavily made the bot return zero candidates after the quota was exhausted.
- Implemented:
  - deterministic procurement queries now run before AI-generated queries;
  - query families include exact product/code, горноспасательное оборудование, пожарные рукава, соединительная арматура, ГМ-70, дилеры/поставщики;
  - Tavily search is concurrent but bounded;
  - DDGS fallback is installed and used when Tavily returns no usable candidates;
  - final acceptance supports `exact`, `adjacent`, and `profile` supplier leads, but still requires opened pages and contacts;
  - blocked more marketplaces, тендеры, справочники, directories, foreign marketplaces, news/articles/info pages, and misleading `ГМ-70` radio-lamp results;
  - successful supplier jobs clear stale `job.error`;
  - XLSX summary changed to `Найдено и проверено`.
- Dependency:
  - added `ddgs>=9.14.0` to `backend/requirements.txt`;
  - installed `ddgs 9.14.4` in the production venv.
- Backup:
  - `data/aipoisk.db.backup-before-supplier-quality-20260601T224755Z`.
- Reprocessed user job `c01e10dd5ac64de4a9e1c0b827a668a8`:
  - status `completed`;
  - message `Готово: найдено и проверено 15/15`;
  - supplier rows in DB: `15`;
  - XLSX path: `storage/jobs/c01e10dd5ac64de4a9e1c0b827a668a8/output/Приспособление_для_промежуточного_подсоединения_пожарных_рукавов_c01e10dd.xlsx`.
- XLSX verification:
  - `openpyxl` opened the file;
  - worksheet rows `18`, data rows `15`, columns `10`;
  - summary row: `Найдено и проверено: 15/15. В XLSX включены сайты с открытой страницей-доказательством и контактами.`
- Download verification:
  - authenticated local `/api/jobs/c01e10dd5ac64de4a9e1c0b827a668a8/download` returned `HTTP 200`;
  - content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`;
  - filename ended with `.xlsx`;
  - downloaded file opened with `openpyxl`, data rows `15`.
- Service verification:
  - `./.venv/bin/python -m compileall app` passed;
  - `aipoisk-api.service`, `aipoisk-bot.service`, and `nginx` are active;
  - `http://127.0.0.1:8088/api/health` returned `{"ok":true,"domain":"https://aipoisk.lexelence.ru","logistics_enabled":false}`;
  - recent journal shows clean restart and Uvicorn startup, no traceback.
