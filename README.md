# AI Poisk Bot

Commercial Telegram bot and admin panel for procurement document processing.

Primary domain: `https://aipoisk.lexelence.ru`

## Production notes

- Runtime server: `202.71.13.57` (`HOSTKEY B.V.`, Netherlands).
- Backend: `aipoisk-api.service` on `127.0.0.1:8088`.
- Telegram polling worker: `aipoisk-bot.service`.
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
  analyses. `Анализ + поставщики` consumes one unit from each limit.
- Batch jobs for supplier search and procurement Word reports.
- Free-period settings for new Telegram accounts, with separate free supplier
  and documentation-analysis limits.
- Flexible admin settings for storage, limits, report behavior, search sources,
  and AI providers.
- Public site-card for TenderLex with no blog: feature description, pricing, contact blocks, SEO metadata, and Telegram CTAs.
- Public site data comes from `GET /api/public/site`; only active tariffs, safe contacts, trial counters, and public copy are exposed.
- Telegram links are intentionally split: `bot_telegram` is the bot used for "Попробовать бесплатно" and work CTAs, while `contact_telegram` is the owner/contact link for purchase and manual communication.
- OpenAI-compatible custom AI providers, including CLIProxyAPI-style endpoints,
  OpenRouter, Gemini, and Polza.
- ATI/logistics disabled by default.
- Document parsing for TXT/CSV/HTML/DOCX/XLSX/XLS/PDF/DOC/RTF/ODT/PPTX/images with OCR, plus ZIP/RAR/7Z archives when system tools are available.
- Procurement Word reports use the EmailAgent-style AI report structure when an AI provider is configured; otherwise a downloadable fallback draft is marked for review.
- Supplier search does not use EmailAgent discovery or the old Gemini search adapter path. It uses a multi-source web-search chain (`Yandex Search API -> Google Custom Search -> Tavily -> DDGS` by default), then verifies supplier sites, relevance, evidence pages, and contacts before writing XLSX rows.

## Current status

- Current production status and the remaining commercial hardening backlog are documented in `docs/PROJECT_STATUS.md`.
- TenderLex public-site architecture and deploy notes are documented in `docs/TENDERLEX_SITE.md`.
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

Bot worker:

```bash
cd backend
. .venv/bin/activate
python -m app.bot
```

The admin panel runs with:

```bash
cd frontend
npm run dev
```

Default local frontend URL: `http://localhost:3091/`.
