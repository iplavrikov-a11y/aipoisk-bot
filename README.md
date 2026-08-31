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
  concurrency is controlled by `AIPOISK_WORKER_CONCURRENCY` (set to `6` with `2` concurrent jobs per customer, and strict real-time execution without caching).
- Public TenderLex site: Next.js app in `site/`, served at `https://tenderlex.ru` by `tenderlex-site.service` on `127.0.0.1:3093`.
- Product Radar: Resident badge integrated in the public footer, launch campaign prepared for 2026-08-24.
- Contact Routing & Channels: Support channels: Telegram direct (`https://t.me/lexelence`), Telegram bot (`https://t.me/tenderlex_bot`), email `info@tenderlex.ru`, and on-site interactive chat.
- UI/UX theme: Light-emerald high-trust B2B palette with natural procurement copy across the interactive showcase (`ScrollWorldViewer`), calculator (`ProcurementCalculator`), and web cabinet (split-toolbar layout with left-aligned navigation & contact buttons and right-aligned function guide and compact notification bell toggle `[🔔]`, integrated help modal `max-w-5xl`, real-time Web Audio task completion chime, customer expense and operations history modal (`/api/customer/billing/transactions`) with itemized operations, server-side pagination, exact client override charges and clean procurement subject titles, bottom floating toast pill, pulsing badges for new jobs, dismissible live chat with header trigger, and clean decluttered button styling).
- Trial Balance & Email Verification: New registrations receive 396 ₽ trial balance (4 tasks @ 99 ₽); web cabinet displays compact test banner guiding users to direct contact channels for quota top-ups; transactional email confirmation uses a bulletproof responsive HTML template with single-account-per-email uniqueness enforcement.
- Exact-to-Supplier Search Pipeline: 1-click seamless pipeline from completed "Подбор товара и аналогов" into "Поиск поставщиков" across Web Cabinet and Telegram Bot. Generates a hybrid context combining original specification files with a structured manifest of identified equipment and confirmed equivalents from `evidence.json`, enabling instant supplier discovery with tariff quota reservation and policy controls.
- Exact Product & Analogs Safeguards & Deep Search: Robust real-time pipeline with continuous heartbeat progress streaming (`progress_callback` at 20%, 35%, 50%, 65%, 78%, 88%, 100%), extended worker stale timeout (8 minutes in `jobs.py`), multi-item position safeguards (`MAX_EXACT_POSITIONS_PER_JOB = 3`) with intelligent triaging (prioritizing capital equipment/materials and filtering out installation/dismantling services and generic screws/bolts), search query budgeting (`MAX_YANDEX_QUERIES_PER_JOB = 16`, 1-page targeted queries dropping search cost to ~0.30–0.50 ₽ and runtime to under 1 minute), semantic AI Minpromtorg/GISP compatibility validation with LRU caching, adaptive parameter sub-search (`resolve_clarify_parameters`), and full Form 2 export in DOCX and XLSX.
- Automated Nurturing Sequence & 1-Click Unsubscribe: Behavioral 3-step sequence (24h post-registration reminder, 48h post-first-task feature showcase, and trial completion summary) across Telegram and Email within work hours (09:00–20:00 MSK). Provides universal 1-click unsubscribe via Telegram button (`🔕 Отписаться от подсказок`) and HMAC-signed email link (`/api/customer/auth/unsubscribe`) that permanently disables marketing messages.
- Admin panel & Telegram client display: Real-time background polling loop for the Clients tab (instant updates without manual reload), optimized loading for clients and Minprom registry cache (FTS count and N+1 query elimination), and improved Telegram account formatting to display client name and ID when `@username` is absent.
- Public site SEO and verification wiring live in the site app and the `tenderlex-site.service.d/seo.conf` drop-in; Google Search Console uses DNS TXT, Yandex Webmaster uses the public HTML verification file, and Yandex Metrika is enabled by env.
- SEO Analytics & Automation Pipeline: Direct integration with Yandex Webmaster API, Yandex Metrika API, and Google Search Console API (`backend/app/yandex_seo.py`, `backend/app/google_seo.py`, `/api/seo-analytics`). Features real-time today search metrics harvesting (clicks, shows, avg position, and SERP query counts with day-to-day deltas), daily ranking dynamics tracking over 7/14/30 days with day trend classification (🟢 Up / 🔴 Down / ⚪ Stable) separately for Yandex and Google, query-level ranking movement tracker (who climbed, who dropped), sitemap priority recrawl queue submission, automated detection of "Striking Distance" growth points, and weekly automated Telegram digests to the owner.
- Admin Panel SEO View: Dedicated "SEO и Трафик" control view in `admin.tenderlex.ru` with real-time "⚡ Прогресс на сегодняшний день" cards, "📈 Динамика ранжирования и показов по дням" interactive chart and timeline table with engine toggles (`[Все] [Яндекс] [Google]`), "🎯 Динамика ключевых фраз", and 1-click Telegram report delivery.
- B2B Outreach & Lead Generation Engine: Dedicated system for massive B2B supplier/contractor acquisition by niche query with real-time web crawling, AI relevance scoring, negative keyword & domain filtering (excluding banks, guarantee brokers, OFD/EDS providers, tender software, and education/media), automated MX DNS domain verification, global top-level navigation layout (Search Tasks vertical list, Inbound Answers, Direct Composer, Mail Settings), task-isolated workspace architecture (CRM leads, email campaigns, AI composer), seamless jitter-free inbox synchronization (background server IMAP worker loop every 45s + silent 20s client DB polling, replicating `emailagent`), stable unread message reading (opening unread emails in the "Новые" tab preserves selection without auto-vanishing), sandboxed responsive `EmailBodyFrame` with responsive HTML table rendering and formatted fallback cards for empty bodies and opt-outs, interactive read/unread circle indicators across all inbox categories, sender avatars with hash-based color palette, dedicated **История переписки** correspondence thread modal with full chronological message timeline and inline fast AI replies (`/api/outreach/inbox/{id}/thread`, `/api/outreach/leads/{id}/thread`), multi-tier intelligent anti-spam engine with Unicode homoglyph normalization (defeating Cyrillic lookalike obfuscations like `Mаkitа`), self-learning domain/sender blacklist, 1-click permanent spammer blocklist and server-side IMAP auto-expunge, automated Bounce / NDR parser linking delivery failure notifications to leads with diagnostic rejection codes, accurate unified metrics accounting for sent, replied, and bounced leads, resilient campaign worker with safe resume handling without counter clobbering, SOCKS5 SMTP/IMAP transport with `info@tenderlex.ru`, lead parser hygiene (blocking placeholder names, test domains, and support/helpdesk ticket queues), pre-flight deliverability verification (`verify_email_deliverability` with SMTP handshake ping), Spintax randomization engine (`{...|...}`), RFC `List-Unsubscribe` headers, adaptive delay jitter, and AI Email Assistant for generating cold pitches and smart replies.
- Unified Admin Dashboard & Real-Time Analytics: Unified "Сводка" and "Статистика" into a high-density, responsive control center with 5-metric KPI row, 30-day dynamic launch chart, split 2-column breakdown for task modes/statuses and trial conversion funnel, and top active clients list. Displays instant live Yandex Search API balance in top header (`Поиск Яндекс: 401.69 ₽`).
- 7-Day Smart Error Window & 1-Click Resolution: Active error alerts are filtered to the last 7 days (`Job.created_at >= now - timedelta(days=7)`), and includes 1-click **«Отметить решёнными»** action in both the Attention Banner (`POST /api/jobs/resolve-failed`) and on individual failed job cards (`POST /api/jobs/{job_id}/resolve`), permanently resolving historical errors and keeping the status indicator in clean green ("Система работает штатно").
- Streamlined Admin Task Cards: Ultra-compact, single-level task item layout with micro-timeline stages in the card header, logical badge ordering (1. Function mode -> 2. Policy / run mode -> 3. AI provider & model -> 4. Found items count -> 5. Search API cost), left-aligned customer input file download pills with unclipped filenames and smooth tail ellipsis, and status-colored left border accents for noise-free visual separation.
- Multi-Tier Document Parser Resilience: Fault-tolerant extraction pipeline for uploaded customer specifications (`.docx`, `.xlsx`, `.pdf`, `.doc`, archives) with primary native readers, secondary headless `LibreOffice` text fallbacks, and tertiary direct XML parsing (`word/document.xml`) protecting against corrupted packaging and bad internal relationships.
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
  Telegram manager accounts and website logins under one customer.
- Shared customer limits for all linked Telegram accounts.
- Customer access is based on a money balance. Each function has an effective
  price: supplier search, procurement-document analysis, additional
  supplier search (`Найти ещё` / добор поставщиков), and exact product detection
  (`🎯 Точный товар и аналоги по ТЗ` — 99 ₽). `📄🔎 Анализ + поиск`
  reserves and charges the supplier-search and analysis prices together.
- Exact Product & Analogs Public Landing Page & SEO Hub:
  - Commercial landing page `/podbor-tovara-i-analogov-po-tz` with structured Schema.org (`Service`, `FAQPage`, `HowTo`, `BreadcrumbList`), interactive Form 2 specification preview, Deep Search benefits, and direct 1-click supplier transition.
  - Three-module core platform grid on homepage `/` (1. Поиск поставщиков, 2. Подбор товара и аналогов по ТЗ, 3. Экспресс-аудит документации 44/223-ФЗ).
  - Extended SEO Knowledge Hub with targeted articles: `kak-zapolnit-formu-2-dlya-zayavki-44-fz-konkretnye-pokazateli`, `kak-opredelit-skrytogo-proizvoditelya-po-tz-44-fz`, and enriched `podbor-analogov-i-ekvivalentov-oborudovaniya-44-fz`.
  - Full sitemap integration and header/footer navigation links.
  Additional supplier search defaults to 49 ₽ (configured via global `Добор поставщиков`
  tariff package in the admin panel) with automatic fallback, and per-customer
  `Добор` prices remain editable in the admin client card. Additional supplier search
  utilizes candidate pool caching (`unreviewed_candidates`), cached procurement profile,
  wave-based query generation with domain negative keywords, and optional custom criteria
  (`additional_prompt`), saving up to 70–85% on search API costs and execution time.
  Reserved funds are settled immediately upon job completion (`status == completed`),
  and runs finding 20 or more verified suppliers complete automatically without
  requiring partial-result confirmation.
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
- Admin tasks list displays the exact AI provider and model used for every task
  (e.g., `Gemini · gemini-3.1-flash-lite`, `OpenRouter · claude-3.5-sonnet`), with
  search and filter support by AI model and provider name.
- Admin customer cards display exact registration dates for each client in the
  card header, per-account registration/linking dates for Telegram accounts, and
  both registration and last login dates for web-cabinet users.
- Online checkout is not enabled. Customers top up through the manager, and the
  owner credits or debits only a money amount in the admin client card. Legacy
  YooKassa fields remain in the backend schema for a future integration, but
  they are not the active payment workflow.
- Public TenderLex site with no blog: supplier-search-led landing page,
  pricing, contact blocks, Telegram CTAs, SEO scenario pages, and authenticated
  customer cabinet at `/cabinet`.
- Public homepage positioning is supplier/contact search under a customer's
  specification. Procurement-document analysis is still available, but it is
  framed as an optional supporting check for complex tender work rather than
  the dominant first-screen message.
- Website cabinet users are separate from Telegram users. Web clients sign in by
  email/password; internal `web:<id>` markers must stay hidden from the
  owner-facing account UI. Admin client cards show Web and Telegram access
  separately, and a web login can be removed without deleting the customer,
  balance, jobs, or Telegram accounts.
- Website cabinet exposes the same customer work scenarios as the bot:
  supplier search by ТЗ, procurement document analysis («Анализ документации»),
  and combined analysis plus supplier search. The task launch form uses a compact
  layout with a horizontal full-width file upload bar and action submit buttons
  aligned to the right of text/source input fields.
- Completed supplier-search, procurement-analysis, and combined jobs expose
  a structured `Запрос КП` document generated from the customer materials and
  AI extraction. It is delivered exclusively as a Word (`.docx`) file with
  multiline bulleted characteristics, while Excel exports focus strictly on
  verified supplier contacts. The customer can preview/copy the RFQ text
  and download DOCX from the website cabinet and Telegram bot.
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
  `Обычный поиск`, `Только реестр (Минпромторг)`, and `Реестр в приоритете (Минпромторг)`.
  `Только реестр (Минпромторг)` is for strict prohibition cases where suppliers must have a
  Minpromtorg/GISP registry record. `Реестр в приоритете` searches registry
  candidates first, then continues with the ordinary supplier search. In
  ordinary mode the AI can still detect a mandatory registry requirement from
  the procurement context, but customer-selected registry modes do not require
  the system to infer the legal regime from uploaded supplier documents.
- Registry lookup for those modes uses the local Minpromtorg/GISP cache, not
  Playwright. Admin settings expose cache status and XLSX upload. If the local
  cache is not ready, manual registry modes are rejected before job creation
  and before balance reservation.
- Raw registry hits are treated only as candidates. The worker applies an AI
  relevance filter against the extracted procurement profile before the
  registry status becomes accepted. Supplier XLSX files keep one customer-facing
  `Комментарий` column: matched rows include the registry record number and
  manufacturer there, while priority-mode fallbacks say that no relevant
  registry record was found and the supplier came from ordinary search.
- If strict `Только реестр (Минпромторг)` produces zero registry-linked suppliers but the same
  run already verified ordinary suppliers, the job becomes a paid alternative
  offer instead of a generic failure. Telegram and the website show the number
  of verified alternatives and the exact reserved charge; the customer can
  accept delivery or decline without a supplier-search charge. The alternative
  report carries a prominent no-registry-confirmation warning and is built
  without another AI/search run. A registry technical error never activates
  this offer.

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
