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
- Nginx redirects HTTP to HTTPS, serves `aipoisk.lexelence.ru` from `/root/projects/aipoisk-bot/frontend/dist`, and proxies `/api/` to `127.0.0.1:8088`.
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
- Separate commercial limits for supplier reports and procurement-document
  analyses. `📄🔎 Анализ + поиск` consumes one unit from each limit.
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
  customers, and payment-readiness indicators.
- AI settings separate documentation-analysis models from one cheaper/faster
  supplier-search model used by the whole supplier-search flow.
- YooKassa settings foundation is present for future checkout integration, but
  payments are still handled manually until the cashier account is connected.
- Public TenderLex site with no blog: SEO landing page, pricing, contact blocks, Telegram CTAs, and authenticated customer cabinet at `/cabinet`.
- Website cabinet users are separate from Telegram users. Web clients sign in by email/password and appear in admin data as `web:<id>`; Telegram payments/access stay tied to Telegram accounts.
- Website cabinet exposes the same customer work scenarios as the bot: `Одно ТЗ`, `Несколько ТЗ`, `Анализ закупки`, and `Анализ + поиск`.
- Public site data comes from `GET /api/public/site`; only active tariffs, safe contacts, trial counters, and public copy are exposed.
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
- Supplier search automatically checks whether the procurement context requires
  a Minpromtorg/GISP registry extract. It searches the registry only when the
  documents indicate an active prohibition or another mandatory registry
  requirement; restrictions, preferences, non-application, or generic mentions
  do not trigger registry lookup.

## Telegram customer UX

- The bot presents compact reply-keyboard navigation under the TenderLex brand:
  `🚀 Создать`, `🕘 Задачи`, `📊 Кабинет`, `💳 Тарифы`, `❓ Помощь`,
  and `📞 Контакты`.
- `🚀 Создать` opens four work scenarios: `🔎 Одно ТЗ`, `🗂 Несколько ТЗ`,
  `📄 Анализ закупки`, and `📄🔎 Анализ + поиск`.
- `🔎 Одно ТЗ` and `🗂 Несколько ТЗ` accept only a ТЗ/ООЗ file or a plain text
  description of the procurement object. If the customer sends a notice number
  or procurement link in these modes, the bot must show a clear warning instead
  of silently starting analysis.
- `📄 Анализ закупки` and `📄🔎 Анализ + поиск` accept uploaded files, archives,
  procurement links, and notice numbers.
- While any job is pending or running for the chat, the bot shows only
  `⏳ В работе` and `🕘 Задачи`; new scenario/start buttons are hidden until the
  active processing finishes.
- Internal source/vendor names, service booleans, task IDs, and diagnostic
  counters must not appear in Telegram messages, generated filenames, report
  titles, or public site copy.

## Current status

- Current production status and the remaining commercial hardening backlog are documented in `docs/PROJECT_STATUS.md`.
- TenderLex site/cabinet architecture and deploy notes are documented in `docs/TENDERLEX_SITE.md`.
- Website cabinet operations, manual top-up, password recovery, and product smoke checks are documented in `docs/TENDERLEX_WEB_CABINET_RUNBOOK.md`.
- Latest billing, Telegram UX, admin client deletion, tariff/payment, and button-check evidence is in `.agent/tasks/2026-06-04-billing-telegram-ux/`.
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

Queue worker code or `AIPOISK_WORKER_CONCURRENCY` changes require restarting
only `aipoisk-worker.service`.

The admin panel runs with:

```bash
cd frontend
npm run dev
```

Default local frontend URL: `http://localhost:3091/`.
