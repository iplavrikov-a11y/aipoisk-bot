# TenderLex Bot

TenderLex Telegram bot and admin panel for procurement document analysis and
supplier search.

Public product domain: `https://tenderlex.ru`
Admin/internal domain: `https://aipoisk.lexelence.ru`

## Production notes

- Runtime server: `202.71.13.57` (`HOSTKEY B.V.`, Netherlands).
- Backend: `aipoisk-api.service` on `127.0.0.1:8088`.
- Telegram polling worker: `aipoisk-bot.service`.
- Durable queue worker: `aipoisk-worker.service`; current production
  concurrency is controlled by `AIPOISK_WORKER_CONCURRENCY`.
- Public TenderLex site: Next.js app in `site/`, served at `https://tenderlex.ru` by `tenderlex-site.service` on `127.0.0.1:3093`.
- Public site SEO and verification wiring live in the site app and the `tenderlex-site.service.d/seo.conf` drop-in; Google Search Console uses DNS TXT, Yandex Webmaster uses the public HTML verification file, and Yandex Metrika is enabled by env.
- Nginx redirects HTTP to HTTPS, serves `aipoisk.lexelence.ru` from `/root/projects/aipoisk-bot/frontend/dist`, and proxies `/api/` to `127.0.0.1:8088`.
- Minpromtorg/GISP registry runtime cache lives under
  `data/minprom_registry/` as XLSX, JSONL, and SQLite FTS files. It is used for
  manual registry supplier modes and is intentionally not stored in git.
- TenderLex deploy files are in `deploy/nginx/tenderlex.ru.conf`, `deploy/nginx/tenderlex.ru.http-only.conf`, and `deploy/systemd/tenderlex-site.service`.
- HTTPS follows this server's existing stream layout: public `443` is routed by nginx `stream` to HTTP SSL vhosts on `4443`.
- DNS must contain an explicit `A` record for `aipoisk.lexelence.ru -> 202.71.13.57`. The wildcard/apex Jino parking record (`81.177.141.15`) is not the production server.
- DNS for `tenderlex.ru` and `www.tenderlex.ru` should point to `202.71.13.57`.
- Let's Encrypt certificate: `/etc/letsencrypt/live/aipoisk.lexelence.ru/`, expires `2026-08-30`.
- After DNS changes, Jino authoritative nameservers may be correct before recursive caches such as Google DNS stop returning the previous parking IP.

## MVP scope

- Manual customer access management from the admin panel, including several
  Telegram manager accounts under one customer.
- Shared customer limits for all linked Telegram accounts.
- Customer access is based on a money balance. Each function has an effective
  price: supplier search, procurement-document analysis, and additional
  supplier search (`Найти ещё` / добор поставщиков). `📄🔎 Анализ + поиск`
  reserves and charges the supplier-search and analysis prices together.
- Batch jobs for supplier search and procurement Word reports.
- Telegram supplier search accepts either a ТЗ/ООЗ file or a plain text
  technical assignment/object description message; the text is stored as a
  `.txt` job input and processed by the same AI-first supplier pipeline.
- Documentation analysis can start from a procurement notice number: the bot
  resolves it through the configured structured procurement source, loads the
  published procurement card and available documents, and keeps manual upload
  and source-link flows available.
- Notice numbers and procurement links are intentionally not accepted as plain
  supplier-search input, because documentation analysis and supplier search have
  separate access rules and limits.
- Free-period settings for new Telegram accounts, with separate free supplier
  and documentation-analysis limits.
- Flexible admin settings for storage, limits, report behavior, search sources,
  and AI providers.
- Admin statistics for the Telegram bot funnel: customer count, linked
  Telegram accounts, active users, task usage, trial follow-up candidates, top
  customers, and manual top-up indicators.
- AI settings separate documentation-analysis models from one cheaper/faster
  supplier-search model used by the whole supplier-search flow.
- Online checkout is not enabled. Customers top up through the manager, and the
  owner credits only a money amount in the admin client card. Legacy YooKassa
  fields remain in the backend schema for a future integration, but they are
  not the active payment workflow.
- Public TenderLex site with no blog: supplier-search-led landing page,
  pricing, contact blocks, Telegram CTAs, SEO scenario pages, and authenticated
  customer cabinet at `/cabinet`.
- Public homepage positioning is supplier/contact search under a customer's
  specification. Procurement-document analysis is still available, but it is
  framed as an optional supporting check for complex tender work rather than
  the dominant first-screen message.
- Website cabinet users are separate from Telegram users. Web clients sign in by email/password; internal `web:<id>` markers must stay hidden from the owner-facing Telegram-account UI. Telegram payments/access stay tied to real Telegram accounts.
- Website cabinet exposes the same customer work scenarios as the bot:
  supplier search by ТЗ, procurement analysis, and combined analysis plus
  supplier search.
- Completed supplier-search, procurement-analysis, and combined jobs can expose
  a `Запрос КП` document generated from the original customer materials and
  available analysis data. The customer can preview/copy it and download DOCX
  from the website cabinet; Telegram receives it as an additional job output
  when available.
- Public site data comes from `GET /api/public/site`; only active tariffs,
  safe contacts, free-period settings, and public copy are exposed.
- Telegram links are intentionally split: `bot_telegram` is the bot used for Telegram work CTAs, while `contact_telegram` is the owner/contact link for purchase and manual communication.
- OpenAI-compatible custom AI providers, including CLIProxyAPI-style endpoints,
  OpenRouter, Gemini, and Polza.
- ATI/logistics disabled by default.
- Document parsing for TXT/CSV/HTML/DOCX/XLSX/XLS/PDF/DOC/RTF/ODT/PPTX/images with OCR, plus ZIP/RAR/7Z archives when system tools are available.
- Procurement Word reports use the EmailAgent-style AI report structure when an AI provider is configured; otherwise a downloadable fallback draft is marked for review.
- Procurement Word reports suppress noncritical same-day differences in the
  hour of results review, but keep customer-facing warnings for different
  dates, bid-submission deadlines, auction/trading starts, and other critical
  timing conflicts.
- Supplier search does not use EmailAgent discovery or the old Gemini search adapter path. It uses a multi-source web-search chain (`Yandex Search API -> Google Custom Search -> Tavily -> DDGS` by default), then verifies supplier sites, relevance, evidence pages, and contacts before writing XLSX rows.
- Supplier search supports three registry modes selected by the customer before
  launch in the site cabinet and Telegram bot:
  `Обычный поиск`, `Только реестр`, and `Реестр в приоритете`.
  `Только реестр` is for strict prohibition cases where suppliers must have a
  Minpromtorg/GISP registry record. `Реестр в приоритете` searches registry
  candidates first, then continues with the ordinary supplier search. In
  ordinary mode the AI can still detect a mandatory registry requirement from
  the procurement context, but customer-selected registry modes do not require
  the system to infer the legal regime from uploaded supplier documents.
- Registry lookup for those modes uses the local Minpromtorg/GISP cache, not
  Playwright. Admin settings expose cache status and XLSX upload. If the local
  cache is not ready, manual registry modes are rejected before job creation
  and before balance reservation.

## Telegram customer UX

- The bot presents compact reply-keyboard navigation under the TenderLex brand:
  `🚀 Создать`, `🕘 Задачи`, `📊 Кабинет`, `💳 Тарифы`, `❓ Помощь`,
  and `📞 Контакты`.
- `🚀 Создать` opens the work scenarios: `🔎 Поставщики по ТЗ`,
  `📄 Анализ закупки`, and `📄🔎 Анализ + поиск`.
- `🔎 Поставщики по ТЗ` accepts only a ТЗ/ООЗ file, archive, or plain text
  description of the procurement object. If the customer sends a notice number
  or procurement link in these modes, the bot must show a clear warning instead
  of silently starting analysis.
- `🔎 Поставщики по ТЗ` and `📄🔎 Анализ + поиск` let the customer choose the
  supplier registry mode before launch: ordinary search, registry-only, or
  registry-priority.
- `📄 Анализ закупки` and `📄🔎 Анализ + поиск` accept uploaded files, archives,
  procurement links, and notice numbers.
- While any job is pending or running for the chat, the bot shows only
  `⏳ В работе`, `🕘 Задачи`, and `⛔ Отменить`; new scenario/start buttons are
  hidden until the active processing finishes.
- Every Telegram progress message for a pending/running job must also include a
  visible inline button `⛔ Отменить задачу`. Pressing it cancels only the
  matching customer job, releases the reservation, removes the inline cancel
  button from the progress message, and returns the customer to the main menu.
- Internal source/vendor names, service booleans, task IDs, and diagnostic
  counters must not appear in Telegram messages, generated filenames, report
  titles, or public site copy.

## Current status

- Current production status and the remaining commercial hardening backlog are documented in `docs/PROJECT_STATUS.md`.
- TenderLex site/cabinet architecture and deploy notes are documented in `docs/TENDERLEX_SITE.md`.
- Website cabinet operations, manual top-up, password recovery, and product smoke checks are documented in `docs/TENDERLEX_WEB_CABINET_RUNBOOK.md`.
- For public-site copy changes, verify both positive copy and stale-copy
  checks from `docs/TENDERLEX_SITE.md` before reporting the site as live.
- Earlier billing, Telegram UX, admin client deletion, tariff/payment, and
  button-check evidence is in `.agent/tasks/2026-06-04-billing-telegram-ux/`.
- Runtime secrets, uploaded files, generated reports, SQLite DB files, virtualenvs, dependencies, build output, and `.omx` logs are intentionally excluded from git.

## Local development

Backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8088
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Public site:

```bash
cd site
npm install
npm run dev
```

Telegram bot worker:

```bash
cd backend
. .venv/bin/activate
python -m app.bot
```

Durable queue worker:

```bash
cd backend
. .venv/bin/activate
AIPOISK_WORKER_CONCURRENCY=1 python -m app.worker
```

Production bot code changes require restarting only `aipoisk-bot.service`;
the durable queue worker and FastAPI backend do not need a restart for
Telegram routing-only changes.
If `scripts/deploy_tenderlex_live.sh` skips API/worker/bot restarts because
active jobs exist, wait for active pending/running jobs to finish and rerun the
deploy before reporting Telegram bot behavior as live.

Queue worker code or `AIPOISK_WORKER_CONCURRENCY` changes require restarting
only `aipoisk-worker.service`.

The admin panel runs with:

```bash
cd frontend
npm run dev
```

Default local frontend URL: `http://localhost:3091/`.
