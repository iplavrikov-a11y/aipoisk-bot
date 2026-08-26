# TenderLex: Project Status

Date: 2026-07-08

## Current Production State

- Public URL: `https://tenderlex.ru`.
- Admin URL used in earlier checks: `https://aipoisk.lexelence.ru`.
- Backend service: `aipoisk-api.service`, FastAPI on `127.0.0.1:8088`.
- Telegram worker: `aipoisk-bot.service`.
- Durable job worker: `aipoisk-worker.service`.
- Frontend: static Vite build served by nginx from `frontend/dist`.
- Public TenderLex site: Next.js landing page and web cabinet served by
  `tenderlex-site.service` on `127.0.0.1:3093`.
- Telegram Web Authentication & Unified Client Profile (2026-08):
  - Added seamless 1-click Telegram Login/Registration alongside Yandex ID and Email in the customer web cabinet (`site/src/app/cabinet/cabinet-client.tsx`, `backend/app/web_auth.py`, `backend/app/main.py`).
  - Unified Profiles & Balance Protection: Users who interacted with the Telegram bot are automatically linked to their existing `Client` profile upon logging into the website via Telegram without duplicate account creation or duplicate trial balance grants. Brand-new users receive a unified client account with initial trial access.
  - Implemented secure HMAC-SHA256 signature verification with SHA256 bot token secret and 24-hour expiration checks.
  - Added support for Telegram OAuth URL fragment (`#tgAuthResult=...`) and direct redirect parsing in both frontend client and backend API (`/api/customer/auth/telegram/login`, `/api/customer/auth/telegram/callback`, `/api/customer/auth/telegram/verify`).
- Admin Panel Unified Dashboard & Analytics (2026-08):
  - Merged "Сводка" and "Статистика" into a single, unified, high-density dashboard (`DashboardView` in `frontend/src/App.tsx`).
  - Removed separate "Статистика" navigation tab and eliminated static noise/boilerplate ("Рабочие правила", "Текущая конфигурация", billing disclaimers).
  - Integrated real-time 30-day bot launch dynamic chart (`daily-bars`), mode breakdown (`Поиск поставщиков`, `Анализ ТЗ`, `Анализ + поиск`), task status distribution, trial funnel conversion, and top active client leaders.
  - Smart Error Window (7 Days): Updated `/api/dashboard` and `/api/ops/system-status` in `backend/app/main.py` to filter failed tasks within a 7-day window (`Job.created_at >= now - timedelta(days=7)`). Ancient historical failures from initial testing no longer trigger permanent red alert banners.
  - Sleek Attention Banner: Attention panel only alerts on recent actionable failures, queue backlogs, or server warnings; displays green "Система работает штатно" when clear.
- Admin Panel Client Management Pagination, Search & Performance (2026-08):
  - Rebuilt `ClientsView` in `frontend/src/App.tsx` with high-performance client-side pagination (default 25 clients per page, selectable 25/50/100) preventing browser memory bloat and UI lag on large user databases.
  - Added instant multi-field search filtering across client name, web user email, Telegram username, Telegram ID, and manager notes.
  - Added fast category filter tabs: `Все`, `Web` (site cabinet users), `Telegram` (bot users), and `С балансом` (positive credit balances) with real-time count badges.
  - Added top and bottom pagination navigation controls (`Назад`, `Страница X из Y`, `Вперёд`) with smooth scrolling and total metrics (`Показано 1–25 из X`).
- Admin Panel Task Cards Streamlining & Visual Separation (2026-08):
  - Converted job cards from bulky accordion dropdowns into a single-level ultra-compact card layout with zero hidden content.
  - Relocated micro-timeline processing stages (`Создана` → `Входные` → `ИИ` → `Результат`) into the card header right beside action buttons.
  - Placed client input file download buttons (`input_files`) directly in the actions bar alongside result files, styled in a distinctive blue tone (`📄 file.docx`) to separate inputs from generated outputs.
  - Unified Yandex Search API metrics directly in the top badge row (`🔍 36 запр. · 1.44 ₽`) eliminating redundant bottom boxes.
  - Added clean status-colored left border accents (`border-left: 3.5px solid`) to clearly delimit cards visually (`green` for completed, `red` for failed, `blue` for running, `amber` for pending) without interface noise.
- Resilient Document Parser Fallbacks & Recovery (2026-08):
  - Fixed parser crash on non-standard/corrupted `.docx` files (e.g. invalid relationships such as `word/NULL` triggering `KeyError` in `python-docx`).
  - Added multi-tier extraction pipeline: primary `python-docx` parser → secondary headless `LibreOffice` text extraction fallback → tertiary direct XML parser (`word/document.xml`) extracting structured paragraphs and tables (`w:p`, `w:tbl`).
  - Added resilient fallback for `.xlsx` and `.xls` via headless `LibreOffice` to `.csv` on `openpyxl` reader failures.
  - Added unit test suite in `backend/tests/test_document_parser.py` validating corrupted relationship recovery and XML fallback (100% pass).
- Lead Generation & Outreach CRM Module (2026-08):
  - Added comprehensive B2B lead search, CRM contact management, bulk email campaigns, direct composer, and IMAP inbound reply inbox in admin panel (`frontend/src/OutreachView.tsx`, `backend/app/outreach_api.py`, `backend/app/outreach_mail.py`).
  - Database & Backend: Automatic SQLite schema migrations for `outreach_inbox` (`category`, `is_spam`) and `outreach_campaigns` (`selected_lead_ids`, `audience_type`) in `backend/app/db.py`. Enriched `/api/outreach/inbox` with company name, phone, task matching, server-side pagination (`limit`, `offset`, `total`), and safe query handling.
  - Unified B2B Lead Database: Merged multiple lead search tasks into unified verified database (1 121 active leads with validated MX records), pruned invalid error mailboxes, municipal domains, and non-commercial accounting services.
  - Follow-up Campaign Mode & Audience Routing: Added dedicated Follow-up automation button and filter (`audience_type: "unanswered"`, `"new"`, `"all"`, `"selected"`) with quick 1-click template selection for reaching non-responsive prospects.
  - Reliable SOCKS5 Outgoing SMTP Transport: Implemented robust SOCKS5 proxy routing (`127.0.0.1:1080` to `smtp.jino.ru:465`) with TLS/SSL context to bypass hosting provider outgoing SMTP port blocks, with direct SMTP fallback and safe async thread execution.
  - Campaign Worker Lifecycle & Recovery: Migrated campaign creation to async FastAPI event loop, isolated ORM session state to prevent detached instance errors, and added automatic background campaign recovery on server startup.
  - Cross-Page Contact Selection: Implemented full-task bulk selection across all pages with bulk actions (launch campaign, compose email, delete).
  - Direct CRM Picker: Added fast modal contact picker in "Написать письмо" for selecting recipients from current task database with search and 1-click insertion.
  - Minimalist & Compact UI: Completely eliminated variable chip toolbars across composer, campaign form, and template editor modal; removed screen layout toggle in favor of clean full-width vertical stacked layout (composer on top, campaign history & real-time online counter below); unified template selector into a single clean dropdown.
  - 100% Russian Localization: Converted all internal English workflow words into clean Russian labels (`Отправка`, `В очереди`, `На паузе`, `Завершена`, `Остановлена`, `Сбой`, `Новый`, `Отправлено`, `Ответил`).
  - Tab & Workspace State Persistence: Preserved selected search task ID and active subtab in `localStorage` across page reloads (F5) without losing context or resetting to general summary.
  - Inbound Reply Inbox Enhancements: Fixed viewport height containment to prevent reply form overflowing off-screen; added distinct visual indicators for unread emails (blue dot `●`, "Новое" badge, bold typography, 1-click read/unread toggle); added pagination with 50-item initial load and `[ Показать ещё 50 писем ]` load-more button; added silent background auto-synchronization every 30s; enlarged quick reply textarea (`min-height: 125px`, 6 rows) with 1-click AI reply generation.
  - Added test suite `backend/tests/test_outreach.py` with 100% pass rate.
- Lead Generation & Outreach Search Engine Upgrade (2026-08):
  - Upgraded Outreach search pipeline in `backend/app/outreach_search.py` to match the exact quality, depth, and precision of TenderLex's core client procurement engine (`supplier_search.py`).
  - Integrated Commercial B2B Query Matrix: Generates targeted product/vendor search queries with commercial markers (`завод`, `производитель`, `оптом со склада`, `дистрибьютор`, `прайс-лист`) and strict negative operators (`-"банковская гарантия" -"обучение" -"семинар" -"эцп" -"агрегатор"`).
  - Batch AI Pre-Filtering (AI Rerank): LLM evaluates search snippets in batches to immediately eliminate banks, financial guarantee brokers, training courses, news sites, and marketplaces before crawling.
  - Multi-Page Deep Crawling with Playwright: Scrapes `/contacts`, `/about`, `/rekvizity`, and `/catalog` pages with headless browser fallback for JS/SPA web applications, extracting direct phone numbers (`tel:`) and emails (`mailto:`).
  - Full-Text Parallel AI Review: LLM analyzes extracted website text in parallel, determines exact activity profiles, and assigns a strict relevance score (0–100).
  - DaData EGRUL & OKVED Validation: Connects to DaData API to disqualify liquidated or bankrupt entities and non-target OKVEDs (financial 64–66, education 85, legal brokers 69), enriching verified official company names and CEO names.
  - Session Safety: Resolved SQLAlchemy `DetachedInstanceError` via safe pre-loaded attribute caching (`get_fresh_system_settings`).
  - Inbound Mailbox Recovery & Auto-Sync Stability: Added HTML-to-text extraction in `backend/app/outreach_mail.py` to eliminate empty body messages for HTML-only emails; pinned "Живые ответы" (`replies`) as default view and ensured auto-sync preserves user filter state without leaking delivery bounce errors.
  - Verification & Benchmarks: Created unit test suite `backend/tests/test_outreach_search_quality.py` (100% pass) and side-by-side comparative benchmarking tool `backend/scripts/compare_search_engines.py` proving 0% noise and 100% verified corporate leads on industrial procurement scenarios.
- Contact Routing & UI Polish (2026-08):
  - Strictly separated voice phone calls from messaging channels:
    - Voice calls: `+7 (995) 146-00-80` (`tel:+79951460080`).
    - Messengers: WhatsApp (`https://wa.me/79210629909` for number `89210629909`), Max (`https://max.ru/...` for number `89210629909`), direct Telegram (`https://t.me/lexelence`), bot (`https://t.me/tenderlex_bot`).
    - General contact email: `info@tenderlex.ru`.
  - Simplified contact section buttons (`contact-section.tsx`) to clean single-label buttons (`+7 (995) 146-00-80`, `WhatsApp`, `Telegram`, `Max`, `Email`) with auto-wrapping flex layout and generous inner padding to prevent text overflow on all viewports.
  - Top header microbar (`site-header.tsx`) updated to include direct links for phone, WhatsApp, Telegram, email, Max, and a dedicated "Чат" button.
  - Floating online chat widget (`chat-widget.tsx`) refined into a compact dismissible pill with a close button and custom event `open_tenderlex_chat` wired to the header button.
- Yandex ID OAuth & Google Search Console Automation (2026-08):
  - Added 1-click Yandex ID login/registration for the customer cabinet (`backend/app/web_auth.py`, `site/src/app/cabinet/cabinet-client.tsx`).
  - Integrated Google Search Console API for automated performance tracking and indexing analytics (`backend/app/google_seo.py`).
  - Fixed GSC client dependency runtime (`google-api-python-client`, `google-auth` added to `requirements.txt`).
  - Activated live Google Search Console metrics (19 impressions, 12 search queries, sitemap sync).
  - Fixed cron harvester environment path in crontab (`PYTHONPATH` propagation).
  - Enhanced on-page SEO meta tags, titles, and headers for high-intent queries (*«оценка рисков закупок»*, *«минпромторг закупки»*, *«поиск товаров по тз»*) across Next.js landing pages.
  - Added unit test coverage in `backend/tests/test_google_seo.py` (100% pass).
  - Sent full 86-URL sitemap recrawl batch to Yandex Webmaster API.
- Trial Period & Limits Expansion (2026-08):
  - Increased trial balance limit for newly registered accounts from 198 ₽ (2 tasks) to 396 ₽ (4 tasks @ 99 ₽).
  - Updated defaults in `models.py`, `db.py`, and database `system_settings` (`trial_supplier_search_limit = 2`, `trial_procurement_report_limit = 2`).
  - Added clean, minimalist trial notification banner in the customer web cabinet (`cabinet-client.tsx`) informing trial users of their active test balance and directing them to contact channels below if additional limits are needed.
  - Reverted landing page copy to neutral "Бесплатный пробный доступ при регистрации" without hardcoded task counts.
- Email Verification Template & Security Hardening (2026-08):
  - Completely redesigned HTML email confirmation template in `backend/app/web_auth.py` with cross-client bulletproof centered button, fallback link box, 24-hour expiration notice, and branded TenderLex layout for Yandex.Mail, Mail.ru, Gmail, and Outlook.
  - Verified and tested single-account-per-email policy: enforced via `UNIQUE` DB constraint on `web_users.email` and `HTTP 409 Conflict` in `create_web_user` API.
  - Added automated test `test_duplicate_registration_with_same_email_is_blocked` in `backend/tests/test_customer_api.py`.
- Button Design & Interface De-Cluttering (2026-08):
  - Removed excessive arrow icons (`ArrowRight`, `→`, `ChevronRight`) across all action buttons in the web application (Hero CTAs, module cards, interactive demo, procurement calculator, regional/industry pages, SEO landing pages, knowledge base, legal pages, and cabinet pagination).
- Autonomous SEO, Webmaster & Metrika Goals Pipeline (2026-08):
  - Direct REST integration with Yandex Webmaster API and Yandex Metrika Management & Data APIs (`backend/app/yandex_seo.py`, `/api/seo-analytics`).
  - Automated background snapshot harvesting via system cron (05:00 UTC daily) with local caching in SQLite/JSON for instantaneous admin UI loading.
  - Priority recrawl queue submission for all 86 sitemap URLs (`POST /recrawl/queue`) in Yandex Webmaster.
  - Automated Striking-Distance growth point detector: highlights high-impression queries ranking on page 1 (positions 4–10) with highest conversion potential into TOP-3.
  - Dynamic goal tracking: monitors all 6 Metrika conversion goals (cabinet login, bot click, trial CTA, form submit) and calculates overall site conversion rate (currently 8.82%).
  - Automated weekly Telegram digest sent every Monday at 09:00 MSK to the owner plus on-demand 1-click dispatch from admin panel.
  - Admin Panel UI: Spacious full-width "SEO и Трафик" dashboard with clean queries table, positions, 50/50 sources vs goals grid, and AI recommendation safety lock.
- Customer Web Cabinet Notifications, Real-Time Chime & UI Polish (2026-08):
  - In-browser synthesized dual-tone Web Audio chime (`playNotificationChime`: 659.25Hz → 880Hz sine wave) triggered upon completion of background supplier search or document analysis jobs without external audio assets.
  - Header notification toggle (`Уведомления: вкл / выкл`) persisted in `localStorage`.
  - Minimalist light pill floating toast at `bottom-5 left-1/2` with quick "Смотреть" navigation and auto-scroll to the completed job card.
  - Dynamic pulsing highlights and `✨ Новая` badges on unviewed completed jobs created after feature activation (`NOTIFICATION_FEATURE_START_TS`).
  - Interaction-based view tracking: clicking any result action ("Поставщики", "Анализ", "Запрос КП", "Найти ещё") or the card immediately marks the job viewed in `localStorage` and turns off the pulsing highlight.
  - Color palette refinement: removed heavy dark elements in favor of clean light B2B styling (white toast pill with teal accents, brighter teal balance badge `from-teal-700 to-teal-800`, light amber trial badge `bg-amber-100 text-amber-800`).
- Automated 3-Step Nurturing Sequence & 1-Click Unsubscribe (Telegram + Email, 2026-08):
  - Multi-step behavioral onboarding engine (`backend/app/nurturing.py`) with strict work-hours filtering (09:00-20:00 MSK) and safe rollout windows:
    1. *Step 1 (24h after registration, 0 tasks):* Reminds user about the 396 ₽ starter balance (4 free tasks) and links to knowledge base guide on finding direct suppliers.
    2. *Step 2 (48h after first task completed, <4 tasks):* Highlights 3 core features (DOCX Request for Quotation generation, Minpromtorg Registry verification, 44-FZ/223-FZ contract risk analysis).
    3. *Step 3 (Trial completed, 4 tasks):* Summarizes test run and provides direct contact link for custom procurement limits or corporate invoices.
  - Universal 1-Click Unsubscribe:
    - Telegram inline button: `🔕 Отписаться от подсказок` (`nurturing_unsubscribe`), sets `marketing_unsubscribed = True` in DB and permanently halts all background bot messages.
    - Email 1-click link: `GET /api/customer/auth/unsubscribe?token=<hmac_token>` with secure HMAC-SHA256 signature, sets `marketing_unsubscribed = True` in DB without login and renders a branded confirmation page.
    - All background dispatch loops and queries strictly enforce `if client.marketing_unsubscribed: continue`.
  - Minified, zero-extra-newline email templates preventing whitespace rendering glitches across webmail clients (Yandex Mail, Gmail, Mail.ru).
  - Backed by unit test suite `backend/tests/test_nurturing.py` and deployed live to production.
- Extra Supplier Search Tariff (49 ₽) & Client Tariff Management (2026-08):
  - Added default global tariff package for `supplier_search_extra` (1 добор поставщиков: 49 ₽) in database seeding and runtime fallback.
  - Enabled full web admin editing in the "Тарифы" tab for "Добор поставщиков" (change price, units, title, visibility).
  - Maintained per-client individual price overrides under "Клиенты" -> "Индивидуальные цены" (Поиск, Анализ, Добор).
  - Updated web cabinet (`site/src/app/cabinet/cabinet-client.tsx`) tariff dropdown to dynamically display client-specific overrides and default 49 ₽.
- Search API Metrics & Cost Visibility Fix (2026-08):
  - Fixed Yandex Search API cost and request count extraction for combined jobs (`analysis_and_suppliers`).
  - Extended `extract_yandex_job_metrics` in `backend/app/jobs.py` to inspect nested `supplier_search` evidence dictionaries and calculate costs across primary and recovery search rounds.
  - Ensured `yandex_requests_count` and `yandex_cost_rub` are persisted to the database on all completion and offer paths.
  - Added automated unit test in `backend/tests/test_jobs_recovery.py` and updated existing production job records.
- Live Web Search & Deep Crawling Trust Architecture (2026-08):
  - Aligned website positioning with actual backend capabilities: eliminated inaccurate references to static "supplier databases" in favor of live real-time search across Yandex and Google Search APIs.
  - Implemented sleek, authentic `TrustRegistryBar` component featuring the 4 real pillars of TenderLex:
    1. *Живой поиск Яндекс & Google (Live Web Search)* — формирование поисковых запросов по ГОСТам, маркам и спецификациям без ограничений устаревшими базами.
    2. *Глубокий краулинг сайтов (Deep Crawling)* — автоматический обход страниц производителей/дилеров, парсинг контактов отделов сбыта и прайс-листов.
    3. *Реестр Минпромторга (ГИСП)* — сверка с Реестром российской промышленной продукции под ПП РФ № 616 и № 617.
    4. *ЕИС Закупки (44-ФЗ / 223-ФЗ)* — экспресс-аудит рисков контрактов, извещений и нетипичных штрафов по ПП № 1042.
  - Added high-converting, mobile-first Hero Action CTAs ("Попробовать бесплатно" / "Запустить в Telegram") with conversion trust micro-badges (1 пробный поиск/аудит при регистрации, без привязки карты).
  - Deployed live to production via `./scripts/deploy_tenderlex_live.sh`.
- Telegram Bot Navigation & UX Modernization (2026-08):
  - Removed persistent bottom reply keyboard (`ReplyKeyboardRemove`) across all bot interactions, eliminating screen crowding and mobile keypad clutter.
  - Built pure in-chat inline navigation architecture with zero dead ends: all scenario cards, confirmation prompts, and after-delivery output messages feature clean next-action buttons and return paths.
  - Scenario Isolation: entering a scenario (`Поставщики по ТЗ`, `Анализ закупки`, `Анализ + поиск`) displays only options specific to that mode plus `🏠 Главное меню`, eliminating confusing cross-mode button clutter.
  - Clear Action Prompts (CTAs): added explicit downward arrow hints (`👇`) guiding users to attach files via clip 📎 or input text/notices directly into the chat input bar below.
  - Streamlined layout: secondary views (Кабинет, Задачи, Тарифы, Помощь, Контакты) and scenario policy selectors feature spacious, single-row layouts without text truncation (Minpromtorg policy buttons no longer get clipped in multi-column grids).
  - Main menu (`/start`, `🏠 Главное меню`) acts as the unified hub with 3 prominent scenario buttons, 2 service shortcuts (Кабинет, Задачи), and 3 info buttons (Тарифы, Помощь, Контакты).
  - Verified with 144 automated unit tests, journey simulations, and deployed live to production.
- Comprehensive SEO, GEO & Universal Procurement Positioning Upgrade (2026-08):
  - Completed rigorous 7-framework audit (`claude-seo`, `open-seo`, `seomachine`, `geo-seo-claude`, `next-seo`, `ethercreative/seo`, `marketingskills`).
  - Broadened positioning across all public pages, metadata, hero copy, badges, module titles, and LLM indices: eliminated narrow 44-FZ-only phrasing to explicitly cover 44-ФЗ, 223-ФЗ, коммерческие закупки, торги и любые нестандартные ТЗ.
  - Optimized `<title>` lengths for search snippet limits: implemented `formatSeoTitle()` helper in `site/src/lib/seo.ts` and `KnowledgeArticleMeta.seoTitle`, raising non-truncated SERP title rate from 30.2% to 97.7% across all 86 sitemap URLs.
  - Streamlined `<meta description>` tags across root and landing pages to optimal 140–160 chars.
  - Expanded `site/src/app/robots.ts` with 11 modern AI search crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `YandexRenderBot`, `Google-Extended`, `Applebot-Extended`, `Diffbot`, `Bytespider`, `CCBot`, `Meta-ExternalAgent`, `cohere-ai`).
  - Generated comprehensive `site/public/llms-full.txt` (31 KB) and linked it in `site/public/llms.txt` for deep LLM retrieval and citability in ChatGPT, Claude, and Perplexity.
  - Rebuilt and verified via `./scripts/deploy_tenderlex_live.sh` on live `tenderlex-site.service` (port 3093).
- Comprehensive SEO & Metadata Optimization (2026-08):
  - Cleaned up duplicate brand suffixes across 35 page files to ensure Next.js title template compatibility (0 double branding issues across all 86 pages).
  - Configured full OpenGraph and Twitter cards (`summary_large_image` with `tenderlex-product-preview.png`) across all dynamic knowledge base articles (`/baza-znaniy/[slug]`).
  - Added Speculation Rules API in `site/src/app/layout.tsx` for instant Chromium prerender and prefetch of top transactional routes.
  - Achieved 100% Schema.org JSON-LD microdata coverage (86/86 pages) across WebSite, Organization, SoftwareApplication, Service, BreadcrumbList, and Article types.
  - Validated via 6 audit frameworks (`claude-seo`, `open-seo`, `seomachine`, `geo-seo-claude`, `next-seo`, `ethercreative/seo`) with 0 critical issues and 0 broken links.
  - Deployed live to production via `./scripts/deploy_tenderlex_live.sh`.
- Public site SEO is now wired with dedicated scenario pages, canonical
  metadata, sitemap entries, Yandex Webmaster verification, and Yandex
  Metrika env wiring.
- Public site positioning was corrected on 2026-06-26: the homepage now leads
  with supplier/contact search under a customer's specification, while
  procurement-document analysis is presented as a supporting scenario for
  tender risk review. Root metadata, Open Graph text, homepage sections,
  scenario copy, CTA copy, and the main supplier-search landing page were
  aligned with this positioning.
- The current public copy intentionally avoids making the homepage sound like a
  list of SEO clusters. Terms such as `ТЗ` and `КП` are reserved for narrow SEO
  landing intent and metadata where useful; the homepage uses buyer-facing
  language such as "спецификация", "запрос цены", "письмо поставщику", and
  "список компаний".
- Live site verification on 2026-06-26 passed
  `scripts/deploy_tenderlex_live.sh`, `scripts/check_tenderlex_seo.sh
  https://tenderlex.ru`, and direct live HTML checks for the root title,
  description, H1, and homepage stale-copy phrases.
- Yandex Webmaster SEO follow-up on 2026-06-23 fixed HTTP favicon availability
  for the `http:tenderlex.ru:80` property, added the Yandex `Host` directive to
  `robots.txt`, resent the DNS diagnostic check, and queued the homepage plus
  favicon URLs for re-crawl.
- Database: SQLite at runtime path from `.env`; the live DB is intentionally not stored in git.
- Runtime storage: `storage/`; uploaded files, generated reports, and job outputs are intentionally not stored in git.
- Minpromtorg/GISP registry search uses a local runtime snapshot under
  `data/minprom_registry/`: source XLSX, JSONL index, and SQLite FTS index. The
  current live snapshot is independent from EmailAgent storage and contains
  496,790 registry entries. This runtime data is intentionally not stored in
  git.

Current runtime note:

- the queue is durable and DB-backed;
- one `aipoisk-worker` process is currently running with
  `AIPOISK_WORKER_CONCURRENCY=2`, so two jobs can be processed in parallel;
- queue claiming is fair by customer: if a customer already has an active
  running job, that customer's next pending jobs do not block jobs from other
  customers;
- SQLite runtime connections use WAL mode and a 30-second busy timeout to make
  the current DB-backed queue safer under modest concurrent worker load;
- live deploys use `scripts/deploy_tenderlex_live.sh`; before restarts it checks
  for pending or fresh running jobs and skips API/worker/bot restarts when
  active jobs exist. This prevents deploys from interrupting supplier searches.
  Use `AIPOISK_FORCE_JOB_SERVICE_RESTART=1` only for an intentional interruption;
- job cancellation is DB-authoritative across Telegram, website, API, and
  worker processes. The worker must re-read job status from SQLite before
  progress writes and must not overwrite a customer/admin `cancelled` status
  back to `running`;
- live throughput also depends on external AI/search provider rate limits and
  document sizes.
- customer-selected Minprom registry modes require the local registry cache to
  be ready before a supplier-search job is created. If the XLSX/JSONL/SQLite
  cache is missing or stale, the job is rejected early with an admin-actionable
  error instead of creating a pending job or charging/reserving funds.
- Minprom registry search treats raw FTS hits as candidates. Registry context
  reaches `ok` only after AI confirms that candidate entries match the extracted
  procurement profile; otherwise priority mode falls back to ordinary supplier
  search with an explicit XLSX comment.

## Commercial Access And Billing

Commercial access is customer-level, not Telegram-account-level. One customer
can have several Telegram manager accounts; all linked accounts spend the same
customer money balance and job history.

Website cabinet users are intentionally separate from Telegram users. Web users
sign in by email/password and appear in admin flows by website email. Internal
`web:<id>` markers may exist in job/account metadata, but the owner-facing admin
UI must not show those markers as Telegram accounts or Telegram IDs. Telegram
access remains tied to real Telegram accounts unless the owner explicitly
changes the account model.

The admin panel provides full visibility into multi-login registrations and AI execution:
- **Clients view**: Displays the customer system registration date in the card header, registration/linking timestamps for every linked Telegram account, and registration + last login timestamps for each web-cabinet user.
- **Tasks view**: Displays the AI provider and model used for each task (`ai_provider`, `ai_model`, `ai_label`), resolved from job execution metadata, audit records (`evidence.json`), or current routing, with search filter support by model and provider name.

The active paid model is money balance plus effective per-function prices:

- supplier search;
- procurement-document analysis;
- additional supplier search (`Найти ещё` / добор поставщиков).

Additional supplier search has its own effective price. If the owner configures
an active global `Добор поставщиков` package or a per-customer `Добор` override,
that explicit price is used. Otherwise the default additional-search price is
50% of the customer's effective supplier-search price. For legacy customers
without separate additional-search grants, dobор availability is displayed from
the supplier-search access balance while dobор reservations and charges remain
separate billing rows.

Mode accounting:

- `🔎 Поставщики по ТЗ` reserves and charges the supplier-search price per
  independent ТЗ;
- when several supplier-search inputs are collected before launch, each
  independent ТЗ reserves and charges its own supplier-search price;
- `📄 Анализ закупки` reserves and charges the documentation-analysis price;
- `📄🔎 Анализ + поиск` reserves and charges both the supplier-search and
  documentation-analysis prices;
- `Найти ещё` after a completed supplier search reserves and charges the
  additional-supplier-search price and excludes already found companies.

Free-period customers can be enabled from admin settings. Trial access has
separate supplier and documentation-analysis limits. Trial customers cannot use
mass supplier processing or `📄🔎 Анализ + поиск`; they must run analysis and
supplier search separately when both functions are available. Trial setup grants
money according to the current base prices for the configured free supplier and
analysis runs.

Online checkout is not enabled. Website cabinet and Telegram access are managed
manually from the admin customer card after external payment or approval. The
owner can credit or debit only a money amount; subsequent job reservations and
charges use the customer's effective prices. Money shown as "in processing" is
temporarily reserved for running jobs and is hidden from the owner UI when it is
zero.

## Admin Console

The admin UI is owner-facing and keeps technical details behind advanced
sections where possible.

Current admin capabilities:

- collapsed customer cards by default, so long customer notes and usage blocks
  do not make the customer list unscrollable;
- customer cards show a compact summary with separate Web and Telegram access
  counts, money balance, and a low-emphasis actions menu for destructive client
  operations;
- expanded customer cards are split into `Доступы`, `Финансы`, and `Настройки
  клиента`: Web logins and Telegram accounts are managed separately, balance
  credit/debit operations sit next to collapsed billing history, and advanced
  per-client prices plus duplicate-merge tools stay collapsed until needed;
- website-cabinet service markers such as `web:<id>` and website-trial notes are
  hidden from the owner-facing client card;
- the owner can create clients by Telegram username before the real Telegram ID
  is known, edit linked Telegram accounts, remove a website-cabinet login from
  a customer without deleting the customer, set per-client prices, credit or
  debit the customer's money balance, tune the supplier count for that customer,
  merge duplicate customers, and delete extra Telegram accounts;
- old manual unit debit support remains in the backend for compatibility, but
  the current owner UI intentionally does not expose action/type/package fields:
  the owner adjusts money only, and jobs debit money according to tariffs;
- if a manager first used the bot as a separate trial customer, the owner can
  move that existing Telegram account into the correct customer card after
  explicit confirmation. A single-account trial customer is merged with its job
  and billing history; regular multi-account customers remain in place and keep
  their remaining Telegram account as primary;
- customer deletion is allowed only when the customer has no jobs. If there are
  no jobs, related billing rows are removed with the customer. If jobs exist,
  deletion is blocked to preserve report and billing history, and the owner
  should use `Отключить`;
- admin API errors are shown as readable Russian messages in the top alert
  instead of looking like a silent button failure;
- service/internal jobs are hidden by default in the jobs list;
- admin and cabinet task lists use pagination so long job histories do not turn
  into unbounded vertical pages;
- admin task details focus on practical owner actions: download customer input
  files and finished result files. Raw evidence, supplier debug lists, and
  report-control dashboards are not shown in the main owner workflow;
- system status shows server disk/RAM/CPU, storage usage, queue counts, and
  configured API services without inventing balances;
- statistics show the Telegram-bot business funnel for the last 30 days:
  clients, Telegram accounts, active users, task volume, trial usage,
  conversion to paid/manual top-ups, top customers, and trial users who used the
  bot but have not received paid/manual top-ups yet;
- supplier-search settings show Yandex and Google as primary sources, with
  Tavily as an additional reserve source;
- supplier-search settings also show the local Minpromtorg registry cache
  status and allow the owner to upload a fresh XLSX snapshot. Upload builds the
  JSONL and SQLite indexes atomically before replacing the active cache;
- AI model settings are compact and split into section-scoped saves.
  Documentation analysis has an owner-selected primary model and fast model.
  Supplier search has one separate owner-selected model for the whole supplier
  flow, so supplier query generation, profile extraction, reranking,
  Minprom-registry checks, and candidate verification are not exposed as
  separate UI groups. Documentation-analysis routing still offers only two
  roles, `Основная` or `Быстрая`, and stores backend routing tokens instead of
  exact provider/model pairs. Visible model selectors show provider name plus
  exact model identifier and are checked independently from the icon next to
  each selector. Provider rows and available model rows can be added, deleted,
  and moved up/down; empty model rows are ignored on save. Free-form model
  comments and API-key status hints are not shown in selectors.
- Tariff settings keep global prices and active packages for the customer
  cabinet. The main owner settings screen exposes contacts and manual top-up
  instructions. Legacy YooKassa fields still exist in the backend schema for a
  future checkout integration, but they are not the active owner workflow and
  do not create payment links.

AI provider defaults currently used by the admin UI:

- `openrouter`: `https://openrouter.ai/api/v1`;
- `open-ai`: local OpenAI-compatible CLIProxyAPI endpoint from settings;
- `gemini`: Gemini proxy endpoint from settings;
- `polza`: `https://api.polza.ai/v1`.

OpenRouter, OpenAI-compatible, Gemini, and Polza provider rows are configured in
the live settings. API keys are runtime secrets stored in settings/DB only and
must not be copied into git, docs, logs, or customer-facing output.

## Supplier Search Architecture

Supplier search is AI-required. The AI layer is the primary decision-maker, not an optional fallback and not a token-saving feature.

Hard contract:

- no supplier-search report is generated without an active AI provider;
- AI generates the procurement-specific search queries from the technical assignment;
- deterministic code may only clean, prefilter, rank, or gather candidates;
- deterministic code must not mark a supplier as verified when AI is configured;
- every final XLSX row must pass AI audit for product fit, supplier/site type, evidence page, and published contact;
- if AI query generation or AI candidate audit fails, the job must fail or underfill honestly instead of producing a fallback report.

The web discovery layer is multi-source:

- Yandex Search API
- Google Custom Search
- Tavily
- DDGS web source

The default provider order is `yandex,google,tavily,ddgs`. Tavily can exhaust its free quota quickly, so it must remain non-blocking. Yandex and Google are currently the stronger primary sources for this project.

Minpromtorg/GISP registry lookup is local-first and does not use Playwright.
The backend reads the runtime XLSX snapshot only to build indexes, then serves
searches from SQLite FTS. JSONL is a build/fallback artifact, not the normal
query path. When SQLite is ready, an empty SQLite result remains empty and must
not trigger a full JSONL scan.

Supplier candidates are verified before they reach the final report:

- AI extracts a procurement profile from the technical assignment before search;
- AI generates procurement-specific supplier search queries;
- AI reranks collected candidates before page collection and supports confidence in both `0..1` and `0..100` scales;
- if the first AI-verified search round underfills the supplier target, AI
  generates a second recovery query set from the procurement profile, rejected
  candidates, and accepted suppliers; the worker then searches and verifies an
  additional pool instead of stopping after the first narrow result set;
- official website is reachable and available for evidence extraction;
- browser-rendered extraction is available for JavaScript-heavy pages when static HTTP extraction misses contacts;
- AI confirms the site is a manufacturer, dealer, distributor, supplier, or relevant service company;
- AI rejects marketplaces, aggregators, tender pages, registries, directories, articles, videos, forums, education/government pages, and profession pages;
- AI confirms product fit against the technical assignment;
- AI confirms a published phone or email contact;
- evidence URL and contact URL are preserved;
- duplicate domains and companies are filtered;
- the configured supplier target is treated as a minimum; the review stops early
  once that minimum is reached, but any extra suppliers already AI-verified in
  the same paid review batch remain in the customer XLSX.
- customer-facing messages and XLSX summaries show only the actual number
  found and verified; they do not show the configured internal target/minimum.

Telegram supplier input and navigation contract:

- Main customer navigation is a compact two-column reply keyboard:
  `🚀 Создать`, `🕘 Задачи`, `📊 Кабинет`, `💳 Тарифы`, `❓ Помощь`, and
  `📞 Контакты`.
- `🚀 Создать` opens the scenario keyboard: `🔎 Поставщики по ТЗ`,
  `📄 Анализ закупки`, `📄🔎 Анализ + поиск`, and `⬅️ Меню`.
- `🔎 Поставщики по ТЗ` accepts a ТЗ/ООЗ file, archive, or plain text technical
  assignment / object description message and returns supplier-search output;
- when several ТЗ/ООЗ files are collected before launch, each accepted input
  creates its own independent supplier-search job with exactly that one input
  as context;
- each independent job extracts its own procurement profile, generates its own
  AI search queries, verifies suppliers independently, and returns its own XLSX;
- unrelated ТЗ files must never be concatenated into one supplier-search
  context, because that causes dominant items to hide other procurements.
- Telegram uploads in this mode are serialized per chat and retried on file
  download timeout, so large multi-file sends do not silently drop documents.
- before processing starts, collected multi-file and documentation scenarios
  show only `▶️ Запустить`, `🗑 Очистить`, and `⬅️ Меню`.
- while any job is pending or running for the chat, the bot shows only
  `⏳ В работе`, `🕘 Задачи`, and `⛔ Отменить`; it hides `🚀 Создать`,
  `▶️ Запустить`, and all scenario buttons, preventing duplicate launches and
  making the active state clear to the customer.
- each pending/running Telegram progress message also has an inline
  `⛔ Отменить задачу` button. It cancels only the matching customer's job,
  releases the reservation, removes the inline button from the progress
  message, and returns the chat to the main menu. `/cancel` and the reply
  keyboard `⛔ Отменить` remain fallback cancellation paths for the chat's
  active pending/running jobs.
- customer-facing Telegram copy must use the TenderLex brand only. It must not
  show internal provider names, raw service booleans such as `True`/`False`,
  task IDs, or diagnostic counters unless the user explicitly asks for status
  details that require them.
- partial supplier-search results use a single customer-facing confirmation
  message. The bot edits the running progress message into the confirmation with
  send-and-charge / decline buttons. It must not also send a separate progress
  warning or owner diagnostic message into the customer chat.
- internal owner diagnostic alerts are reserved for failed or needs-review jobs.
  The `awaiting_customer_confirmation` state is a normal customer decision point,
  not an owner-alert state.
- after a completed or accepted supplier-search result, Telegram can offer
  `Найти ещё`. Starting that additional search requires explicit confirmation
  that the additional-supplier-search price will be charged and already found
  companies will be excluded.
- completed supplier-search, procurement-analysis, and combined analysis jobs
  can include an additional `Запрос КП` output. It is built from the original
  customer materials plus available AI analysis/procurement profile data and is
  intended for supplier-facing requests to issue an invoice or commercial
  proposal.

## Procurement Source Links

Documentation-analysis jobs can use uploaded files, procurement source links,
or both. A source link is not limited to EIS: it can be `zakupki.gov.ru`, a
223-ФЗ platform, a commercial ETP, or a customer's published procurement page.

Plain supplier-search scenarios are different: the customer sends a technical
assignment / object description file, not a procurement link. Links are exposed
in Telegram only for `📄 Анализ закупки` and `📄🔎 Анализ + поиск`.

## Structured Procurement Source API Contract

Tenderplan API is the primary structured source when a customer starts
documentation analysis by procurement notice number. The API token is a runtime
secret and must stay only in environment/configuration, never in docs, commits,
logs, public site copy, Telegram messages, report filenames, report titles, or
task evidence.

Current safe source priority:

- for `📄 Анализ закупки` and `📄🔎 Анализ + поиск`, a raw notice number is
  stored as a `tenderplan_notice` source and resolved through Tenderplan;
- Tenderplan card data is used as the main published source for notice number,
  customer, НМЦК, deadlines, bidding/results dates, platform, legal regime,
  national-regime signals, document list, and explanations when the API returns
  them;
- `placingWay` and `status` are decoded through official Tenderplan tool
  dictionaries (`/api/tools/placingways/list`, `/api/tools/statuses/list`) before
  local fallback tables or text inference. Raw numeric codes must not be shown
  as the user-facing procurement method. Code `0` is the generic official value
  `Иной способ`; do not guess a more specific subtype without evidence from the
  notice, documentation, or platform;
- Tenderplan timestamps are rendered as Moscow time in source context, so the
  report should not recalculate them through the VPS timezone;
- Tenderplan attachments and explanation attachments are downloaded into the
  normal job input flow and parsed with the same document pipeline as manually
  uploaded files;
- the shared local Tender Source Service adds `document_type` metadata for
  downloaded files (`technical_spec`, `contract`, `nmck`, `notice`,
  `clarification`, `application_requirements`, `other`) and exposes download
  host diagnostics for allowlist/proxy troubleshooting;
- shared bundle schema `2.1` also carries `document_type_source`,
  `document_type_confidence`, `content_document_types`, `warnings`, and
  `document_hints.primary_technical_spec`. Content-aware classification is
  currently lightweight: DOCX/XLSX/PPTX/XML/text, PDF text layers, bounded ZIP
  inspection, and RAR/7z filename listing can confirm strong document markers,
  while OCR for scanned PDFs still belongs to the normal document parsing
  pipeline;
- the shared service response keeps raw `tender` data on a whitelist of
  pre-award card fields only. Full Tenderplan `json`, protocols, participants,
  contracts, sent/signed contracts, and unknown post-award fields must not be
  exposed to consumers;
- for 223-ФЗ legacy EIS `download.html?id=...` document links, the downloader
  resolves the current EIS documents page and uses matched `file.html?uid=...`
  links when available;
- EIS/source-page parsing remains available as a control and legacy path, and
  manual file upload remains fully supported;
- if Tenderplan and another published source disagree, the report context must
  preserve a short conflict note instead of silently mixing versions;
- source fetch status, downloaded file counts, and failed download counts are
  diagnostic evidence, not customer-facing noise unless a failure affects the
  result.

Mode boundary:

- `Поиск поставщиков` must not auto-start procurement analysis from a notice
  number or procurement link, because analysis has separate access and limits;
- if a customer sends a notice number/link while in supplier-search mode, the
  bot must answer with a clear warning and ask for a ТЗ/ООЗ file or text, or for
  switching to `📄 Анализ закупки` / `📄🔎 Анализ + поиск`;
- the lower-level `create_job()` guard also rejects procurement sources for
  `supplier_search`, so another API path cannot silently bypass the mode
  boundary;
- supplier search after `📄🔎 Анализ + поиск` must use a separate extracted
  ТЗ/ООЗ/product-specification context, not the entire noisy procurement bundle.

Source-link contract:

- Telegram and admin upload flows accept source URLs together with files or as
  the only input for documentation-analysis scenarios;
- Telegram extracts procurement links from plain text messages and from file
  captions in documentation-analysis scenarios;
- plain supplier search rejects procurement links and notice numbers with an
  explicit explanation, and asks for a ТЗ/ООЗ file or text;
- EIS links are marked as an official procurement source;
- other procurement links are marked as procurement platform/source pages;
- the worker fetches readable page text, with bounded HTTP and browser
  rendering for JavaScript-heavy pages;
- EIS parsing uses `AIPOISK_PROXY_URL`/`PROXY_URL` when present and follows
  official links to print forms and the customer organization page, so fields
  such as customer, ИНН/КПП, НМЦК, and application deadlines are present in
  AI context when available on EIS;
- source context is prepended to document context before AI analysis;
- AI report generation uses source pages for procurement card fields: notice
  number, customer, НМЦК, deadlines, platform, legal regime, and source-page
  facts;
- when a Tenderplan block exists, it is prepended before source-page and file
  context and is the main card/deadline/national-regime source;
- attached ТЗ/ООЗ remains the primary source for the product table when it is
  more complete than the web page;
- source parsing status and extracted character counts are stored in
  `job_sources` and evidence, but are not exposed as customer XLSX noise.

## Procurement Documentation Analysis

Documentation analysis is AI-required, but the paid product policy is to give
the customer a useful report whenever the system can produce one. Quality work
must focus on root-cause prevention: better model routing, stronger checks,
repairs, owner alerts, and clearer customer disclaimers. Do not make "do not
issue the report/result" the primary quality strategy unless the user explicitly
asks for that policy.

Hard contract:

- source pages and uploaded documents are context for AI, not a replacement for
  AI analysis;
- if AI is unavailable or the draft cannot be produced at all, the user-facing
  message should be soft and commercial: explain that the AI analysis service is
  temporarily unavailable and that billing stays fair;
- AI-generated customer reports should include a soft disclaimer: the report is
  an AI-assisted procurement analysis, useful for preliminary/business review,
  but critical legal, financial, technical, deadline, and submission decisions
  should be checked against the official documents; the service owner does not
  accept responsibility for decisions made solely from the AI report;
- official procurement card fields are treated as authoritative facts before
  the DOCX is generated/repaired;
- for EIS and other official source pages, the report must preserve literal
  card values for procurement method, submission deadline, results date, НМЦК,
  customer, ИНН/КПП, platform, and legal regime when present;
- the report must not normalize `Иной способ` into another procedure and must
  not add time to a results date when the official source contains only a date;
- same-day differences only in the hour of results review / подведение итогов
  are not customer-critical and should not be shown as a separate risk. The
  report should still use the explicit notice/document value for the visible
  card field;
- the report must keep customer-facing warnings for genuinely critical timing
  conflicts: different calendar dates, bid-submission deadline conflicts,
  auction/trading start conflicts, and any other discrepancy that can affect
  whether the customer can submit or participate on time;
- if the AI draft conflicts with official card facts, the system asks AI to
  repair the report and validates the repaired report again;
- if validation still finds issues after repair, the report should carry a
  concise quality warning/evidence note and the owner should be alerted, while
  engineering work focuses on fixing the root cause in prompts, validators,
  model routing, or parsers.

## Minpromtorg And GISP Registry Handling

Minpromtorg/GISP registry logic can be selected manually by the customer before
supplier search starts. The same mode is available in the website cabinet and
Telegram bot for standalone supplier search and combined analysis plus search.

Supplier registry modes:

- `Обычный поиск`: ordinary supplier search. The AI can still detect a
  mandatory registry requirement from the procurement context.
- `Только реестр`: strict mode for prohibition cases. The search prioritizes
  registry-derived queries and final supplier rows must have registry linkage
  evidence when registry data is available.
- `Реестр в приоритете`: restriction/priority mode. Registry-derived suppliers
  are searched first, then the ordinary supplier search continues to avoid
  underfilling the report.

In ordinary mode, AI-gated registry logic applies only when the procurement
documents actually require a registry extract, registry record, or delivery of
goods from the Russian industrial products registry.

Registry contract:

- AI decides whether the requirement is mandatory, not applied, only a
  preference, or ambiguous;
- customer-selected strict/priority modes override the need to infer the legal
  regime from attached documents before registry-aware supplier search starts;
- registry search is skipped when AI finds no mandatory requirement;
- when mandatory, AI generates registry-oriented queries for the procurement
  item and the worker searches GISP/Minpromtorg context;
- raw registry hits are filtered by AI against the extracted procurement
  profile before they are treated as usable registry evidence;
- supplier AI verification receives registry context and must not claim the
  requirement is fulfilled without a supplier/manufacturer linkage;
- dealers and distributors may still be accepted as procurement leads, but the
  customer-facing comment must say to request registry confirmation when direct
  linkage is absent. In priority mode, if no relevant registry entry survives
  filtering, the comment must say that no relevant registry record was found
  and the supplier was found by ordinary search.
- In strict mode, a trustworthy zero result (`empty` or `ok` with no supplier
  linkage) preserves already verified pre-filter suppliers as an immutable
  alternative. TenderLex offers that report in Telegram and the website with
  explicit no-registry wording, charges only after successful delivery, and
  releases the supplier reservation on decline or expiry. Registry status
  `error` remains a technical/no-charge outcome and cannot be presented as an
  empty registry.
- Result-offer decisions and deliveries are separate DB-backed states. Offers
  have a 24-hour decision window; accepted but undelivered results have a new
  24-hour delivery window. Combined analysis-plus-search jobs can fall back to
  an analysis-only manifest without exposing the stale supplier archive.

## Reports And Audit Fields

XLSX supplier reports include:

Visible customer-facing columns only:

- company name;
- website;
- phones;
- email;
- short comment.

The visible comment column is also the registry audit surface for customers:
accepted registry matches include the registry record number and manufacturer
in that same comment, and priority-mode fallbacks include a compact note that
the relevant registry record was not found. The report must not add separate
registry columns for this routine supplier-search output.

Stored supplier rows also preserve `match_level`, `source`, `search_query`,
`quality_score`, `quality_tier`, `procurement_item`, `ai_confidence`,
`site_type`, `product_fit`, evidence snippets, and AI rerank metadata, so
admin/API views and `evidence.json` can explain why a supplier was accepted
without polluting the customer's XLSX report.

## Job Execution And UX

- API and Telegram bot only create durable DB-backed pending jobs.
- `aipoisk-worker.service` claims pending/stale jobs and performs processing.
- The worker supports in-process concurrency through
  `AIPOISK_WORKER_CONCURRENCY`; production is intentionally set to `2` first,
  not higher, until real AI/search and memory pressure are observed.
- Claiming keeps one active non-stale job per customer at a time, while still
  allowing different customers and anonymous/system jobs to be claimed.
- Telegram has three customer-facing creation scenarios: `🔎 Поставщики по ТЗ`,
  `📄 Анализ закупки`, and `📄🔎 Анализ + поиск`.
- Website cabinet mirrors those scenarios without Telegram-only emoji:
  `Одно ТЗ`, `Несколько ТЗ`, `Анализ закупки`, and `Анализ + поиск`.
- Website `Одно ТЗ` starts one supplier-search job from one uploaded file or
  one text description.
- Website `Несколько ТЗ` sends several ТЗ files to the same supplier-search
  backend mode, where each file becomes a separate independent supplier-search
  job.
- Website `Анализ закупки` and `Анализ + поиск` accept notice numbers, links,
  files, and archives. The customer does not choose supplier count and does not
  fill extra invented "what to check" fields; those are intentionally absent.
- Website job rows expose `Отменить` while a job is pending/running. Completed
  jobs can expose `Запрос КП` as a preview/copy/download action when the backend
  produced that output file.
- The website job list and customer session requests are served/fetched with
  `no-store`; while active jobs exist, the cabinet polls more frequently so
  Telegram-side cancellation is reflected in the website without a manual page
  reload.
- Single-ТЗ supplier search starts after one uploaded ТЗ/ООЗ file;
  it can also start from one plain text ТЗ/ООЗ message.
- Multi-ТЗ supplier search collects several ТЗ/ООЗ files and/or accepted plain
  text ТЗ messages; the user starts or clears that set explicitly.
- Documentation-analysis scenarios can collect files, archives, procurement
  source links, and notice numbers before the user starts processing.
- `📄🔎 Анализ + поиск` first uses the full documentation/source context for
  the DOCX analysis, then uses a separate AI step to extract the ТЗ/ООЗ/product
  specification context for supplier search. Supplier discovery does not search
  against the noisy full documentation bundle.
- Supplier discovery receives the customer-selected supplier registry mode.
  In ordinary mode it classifies the extracted context for Minpromtorg/GISP
  requirements before ordinary supplier query generation and searches the GISP
  registry only when the context indicates an active prohibition or another
  mandatory registry/extract requirement. In strict/priority modes it performs
  registry-aware supplier search without requiring that automatic legal-regime
  inference first. The registry context records raw candidate count separately
  from AI-filtered entries, so broad text matches do not become accepted
  registry evidence. The final `evidence.json` records the supplier search
  policy, `minprom_registry` decision, registry queries, raw candidate count,
  accepted entries count, status, registry-search/filter errors, and whether an
  unavailable registry caused a no-charge strict search.
- In `📄🔎 Анализ + поиск`, the supplier-context extraction step must preserve
  Minpromtorg/GISP/registry-record requirements from the procurement
  documentation so the later supplier-discovery step can make that decision on
  the same basis as standalone supplier search.
- Telegram bot edits a live progress message while the job runs: queue, AI analysis
  of the technical assignment, query generation, website search, AI candidate
  filtering, site/contact verification, and completion.
- If a chat already has a pending/running job, Telegram answers with a concise
  active-processing message and the `⏳ В работе` / `🕘 Задачи` keyboard instead
  of offering new actions.
- Admin UI includes supplier quality monitoring and per-job evidence viewing.
- Admin API exposes `/api/ops/supplier-quality` and `/api/jobs/{job_id}/evidence`.
- Telegram routing-only code changes require restarting `aipoisk-bot.service`.
  The API and durable worker can keep running unless their code or settings
  contracts changed.
- Worker queue code or `AIPOISK_WORKER_CONCURRENCY` changes require restarting
  `aipoisk-worker.service`; the API, bot, and site do not need a restart for
  those changes.

## Verification Snapshot

Fresh checks from the money-balance billing, supplier registry modes,
additional-search pricing, and admin cleanup pass:

- Full backend tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest
  backend/tests -q` -> `348 passed`, `2` warnings, `46` subtests passed.
- Frontend production build: `cd frontend && npm run build` -> OK.
- Site typecheck/build and live deploy were completed through
  `./scripts/deploy_tenderlex_live.sh`; API, worker, bot, and site services
  were active after deployment.
- Live behavior verified the current admin owner model: top up money only,
  per-customer function prices, no visible run counters for customers, and no
  zero-value reserve line in normal balance display.
- Customer cabinet and Telegram supplier workflows carry the selected registry
  mode through search and analysis-plus-search.

Earlier checks from the website cabinet parity and landing-copy pass:

- Site typecheck: `cd site && npm run typecheck` -> OK.
- Site production build: `cd site && npm run build` -> OK.
- Local Playwright smoke against `127.0.0.1:3094` covered cabinet
  registration, four function cards, `Несколько ТЗ`, absence of invented
  analysis fields, and desktop/mobile screenshots.
- Local Playwright smoke against `127.0.0.1:3094` covered the landing page and
  checked that old repetitive/material-format copy was not visible.
- Production service `tenderlex-site.service` was restarted and active on
  `127.0.0.1:3093`.
- Live domain checks returned HTTP 200 for `https://tenderlex.ru/` and
  `https://tenderlex.ru/cabinet`.
- Live Playwright smoke signed into a website QA account, confirmed all four
  cabinet functions, and confirmed no invented analysis fields or file-format
  marketing labels were visible.

Earlier task evidence: AI-settings/statistics/legacy YooKassa-settings pass in
git history, plus `.agent/tasks/2026-06-04-billing-telegram-ux/` for the earlier
Telegram UX and admin-button pass.

Earlier checks from the AI model separation, bot statistics, and legacy
YooKassa-settings pass:

- Targeted backend tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest
  backend/tests/test_ai.py backend/tests/test_access_limits.py
  backend/tests/test_api_guards.py -q` -> `54 passed`, `2` warnings.
- Full backend tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest
  backend/tests -q` -> `233 passed`, `2` warnings, `43` subtests passed.
- Frontend production build: `cd frontend && npm run build` -> OK.
- `git diff --check` -> OK.
- Local health endpoint: `curl -fsS http://127.0.0.1:8088/api/health` ->
  `ok=true`, `domain=https://tenderlex.ru`, `logistics_enabled=false`.

Earlier checks from the Telegram keyboard, source-input, and
procurement-report guardrail pass:

- Backend tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest
  backend/tests -q` -> `222 passed`, `2` warnings, `43` subtests passed.
- Targeted Telegram tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend
  pytest backend/tests/test_bot_progress.py -q` -> `38 passed`.
- Targeted procurement-report tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend
  pytest backend/tests/test_procurement_report.py -q` -> `22 passed`, `43`
  subtests passed.
- Production `aipoisk-api.service`, `aipoisk-worker.service`, and
  `aipoisk-bot.service` were active after restart; local health returned
  `ok=true`.
- Telegram text guardrails covered by tests: no legacy brand names in customer
  text, no internal source-provider name in source-input status, no raw `False`
  booleans in customer-facing output, and processing keyboards hide new start
  actions while a job is active.
- Procurement-report guardrails covered by tests: same-day differences only in
  the hour of results review are removed from `Риски`, while different dates
  remain visible and source-card timestamps are not incorrectly attributed to
  an electronic trading platform.

Earlier billing, Telegram, and admin-button pass:

- Backend tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest
  backend/tests` -> `169 passed`, `2` warnings.
- Frontend production build: `cd frontend && npm run build` -> OK.
- Live admin Playwright button check on admin URL `https://aipoisk.lexelence.ru`:
  `32` checks passed, `0` failed API responses, `0` console errors, `0` page
  errors.
- Live admin button coverage included login, navigation, client create/open,
  client disable/enable, Telegram account add/save/delete, the then-current
  manual balance action, delete new temporary client, confirm old
  `Тестовый клиент` is absent, job evidence,
  job download, job retry on a temporary job, tariff create/edit/toggle/delete,
  contact save, settings save, AI model check/save, and refresh.
- Production services after verification: `aipoisk-api.service`,
  `aipoisk-worker.service`, and `aipoisk-bot.service` were active; local health
  returned `ok=true`.
- Smoke cleanup check: temporary UI clients, tariffs, and test jobs were absent
  after the Playwright run; old `Тестовый клиент` / Telegram ID `123456789` was
  absent after deletion.

Earlier admin UI / limits / provider-settings evidence:

- Backend tests: `cd backend && PYTHONPATH=. pytest -q` -> `129 passed`,
  `2` warnings, `35` subtests passed.
- Frontend production build: `cd frontend && npm run build` -> OK.
- Playwright focused AI model check -> function dropdowns route to only
  `Основная` / `Быстрая`; OpenRouter, OpenAI, Gemini, and Polza provider rows
  are present; desktop and mobile have no horizontal overflow.
- UI text scan -> no old AI model aliases such as `Сильная модель`, `Быстрая
  модель`, or `по умолчанию`.
- Safe load simulation -> 100 customers, 10 jobs each, mixed modes, 1000 jobs
  created, 40 concurrent claim workers, 1000 claimed, `0` duplicate claims.
- `git diff --check`: OK.
- Task verdict JSON syntax: OK.

Load-test boundary:

- the 1000-job simulation validates customer creation, two-counter limit
  accounting, queue insertion, concurrent claiming, and duplicate prevention in
  an isolated temporary SQLite DB;
- it deliberately does not call live AI/search APIs or spend provider balances;
- real production throughput still requires worker scaling and external
  provider rate-limit planning.
- Queue fairness/concurrency pass, 2026-06-09:
  `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest backend/tests -q` ->
  `280 passed`, `46` subtests passed, `2` existing FastAPI deprecation
  warnings. Live worker was active after restart, and backend SQLite connection
  reported `journal_mode=wal`, `busy_timeout=30000`, `synchronous=1`.
- Local health endpoint: HTTP 200.
- API, bot, and worker services: active after restart.
- Live DB has `job_sources`.
- Live DB has the supplier AI/audit columns:
  `quality_score`, `quality_tier`, `procurement_item_id`,
  `procurement_item`, `ai_confidence`, `site_type`, `product_fit`,
  `evidence_snippet`, `contact_evidence_snippet`, `ai_rank_confidence`,
  `ai_rank_reason`.
- Browser extraction smoke: email and phone extracted from rendered content.
- Multi-domain supplier eval suite: present and covered by tests.
- Failed supplier-search jobs persist `evidence.json` instead of creating a report without AI verification.
- Admin API can read job evidence through `/api/jobs/{job_id}/evidence`.
- Admin API exposes supplier quality monitoring through `/api/ops/supplier-quality`.
- Source links can create source-only documentation-analysis jobs, are stored
  in `job_sources`, and are included in source context for AI report/combined
  analysis.
- Generic procurement links are supported alongside EIS links.
- Manual and AI-gated Minpromtorg/GISP registry handling is covered by supplier
  discovery flow tests and evidence payloads.
- Regression from job `186d6788fd3244f995fbaab9061386cc` was diagnosed:
  Telegram had accepted a zip with an EIS link in the caption, but saved
  `sources=0`; after the fix, caption links are collected for documentation
  analysis. The same EIS link now fetches `37280` chars of official context,
  including customer, `ИНН 5504002648`, `КПП 222543001`, application deadline
  `08.06.2026`, and initial price `448 960,00 ₽`.
- Supplier XLSX filenames and first-row headings include the source ТЗ title plus the AI-extracted short procurement subject.
- Supplier XLSX comments are short customer-facing notes based on product fit: exact item, possible analog, category, or profile supplier.
- AI supplier query generation retries transient failures and records non-empty
  diagnostics; Telegram still shows only a concise customer-facing reason.
- AI contact placeholders are blocked from customer reports; extracted site
  contacts are used when available, otherwise the supplier is downgraded or
  rejected.
- Reprocessed failed supplier job `06532a2fc4f9442cbf6085e638720693`
  finished as `partial`, `13/15`, with `ai_required=true`, `ai_used=true`, and
  no invalid contact placeholders in the XLSX.
- Supplier search now separates broad товарная группа / номенклатура from exact
  ТЗ characteristics. For a steel-rope job that previously returned `8/15`,
  the reprocessed result is `15/15`: AI generated broad category queries,
  expanded the rerank review pool from `36` to `55` candidates, and the XLSX
  has no bad contact placeholders or broken phone formats.
- The supplier target is a minimum, not a hard cap. The same steel-rope job now
  returns `19` verified suppliers with a configured minimum of `15`; no extra
  paid batch is run after the minimum is reached, but already AI-verified extra
  rows from the active batch stay in the XLSX.
- **DaData & Registry Manufacturer Enrichment (2026-08-14)**:
  - Integrated asynchronous DaData client (`backend/app/dadata_client.py`) with caching by INN for legal entity data extraction (status, full legal name, standardized legal address, region, CEO name/position, OGRN, KPP).
  - Upgraded registry fallback pipeline: unmatched GISP/Minpromtorg manufacturers are no longer injected as empty stubs. The system automatically launches targeted web searches (`"{ИНН}" официальный сайт` + `"{Наименование}" контакты`), filters directory/aggregator domains, crawls official websites, and extracts direct phones and emails (>90% contact discovery rate across 10 real test procurements).
  - Added DaData auto-enrichment for all accepted suppliers with valid INN to ensure uniform region and contact person population.
- **Safe Cascading Client Deletion (2026-08-14)**:
  - Fixed `_force_delete_client` in `backend/app/main.py` to safely delete all cascading dependencies of a specific client in correct foreign key dependency order (`WebSession`, `WebPasswordResetRequest`, `WebEmailVerificationToken`, `AccountLinkToken`, `WebUser`, `ClientTelegramAccount`, `UserJourneyEvent`, `OnboardingReminder`, `ClientTariffOverride`, `SupplierResult`, `JobFile`, `JobSource`, `BillingTransaction`, `Job` and on-disk job folders).
  - Prevents SQLite IntegrityError/500 failures and ensures 100% isolation from other clients or global system state.
- **Admin Clients Tab Real-Time Polling & Instant Refresh (2026-08-26)**:
  - Integrated dedicated background polling loop for `/api/clients` and `/api/dashboard` (8s on active Clients tab, 25s on other tabs, and instant refresh on window focus / tab visibility / view change), so new customer registrations appear immediately without manual page reload.
- **B2B Outreach Email Bounce / NDR Diagnostics & Auto-Categorization (2026-08-26)**:
  - Added dedicated Bounce / Non-Delivery Report parser (`parse_bounce_info`, `sync_imap_inbox`) recognizing `MAILER-DAEMON`, `postmaster`, `ksmg`, and antispam failure notices.
  - Extracts failed recipient email, links incoming failure message to its `OutreachLead`, marks lead status as `bounced` with exact diagnostic failure reason (e.g. `550 Access Denied`), and updates task bounce statistics.
  - Implemented retroactive backfill linking existing bounce records in the database.
  - Added filter tabs in Admin Outreach View: `Все`, `Живые ответы`, `Ошибки доставки (Bounce)`, `Новые`, `Спам` with visual badges and diagnostic reason cards.
- **Outreach Search Negative ICP & Domain Filtering (2026-08-26)**:
  - Expanded `EXTENDED_BLOCKED_DOMAINS` and added semantic negative keyword filters in `outreach_search.py` (`crawl_site_for_contact`) to exclude non-target entities (banks, OFD/EDS providers, tender aggregators/consultants, training centers, media holdings, and `.gov.ru`/`.edu.ru` state domains).
  - Automatically filters out irrelevant contacts from B2B supplier search tasks.

Detailed task evidence for an earlier admin UI / limits / provider-settings pass
is stored under `.agent/tasks/2026-06-03-admin-ui-10/`.

## Safe GitHub Rules

Do not commit:

- `.env` or any real secret file;
- real API tokens, bot tokens, provider keys, cookies, bearer headers, or
  copied terminal output that contains them;
- SQLite databases and DB backups;
- `storage/` job outputs and uploaded procurement documents;
- real procurement documentation, customer documents, customer personal data,
  report outputs, screenshots with private Telegram/admin data, or raw API
  responses from live customer work;
- virtual environments;
- `node_modules/`;
- frontend build output;
- runtime logs from `.omx/`.

Commit only source code, tests, deploy templates, `.env.example`, README/docs,
and task evidence that has been checked for secrets, private documents, customer
data, and internal vendor diagnostics that should not be public.

## Remaining Risks

The main architectural gaps addressed in this pass are implemented. Residual
risks are narrower:

- DB-backed queue now runs with two in-process worker slots and per-customer
  fair claiming, but higher production throughput still needs gradual scaling
  and external AI/search rate-limit planning based on real workload.
- Browser rendering improves contact extraction, but anti-bot sites and unusual
  SPA flows can still require more specialized handling.
- Procurement source pages can also be blocked by anti-bot controls; the system
  records source parse status and continues with uploaded documents when present.
- The multi-domain eval suite is in place; it should be expanded with more real
  procurement categories as new customer documents appear.
- Monitoring is available in API/UI, but there is no external alert delivery
  channel yet.

## Supplier Search & Discovery Architecture Optimization (2026)

- **AI Semantic & Morphological Query Expansion**: Multi-tiered prompt generation covering category broad terms, grammatical forms, industrial synonyms, and normalized registry queries.
- **Fast Asynchronous DNS Pre-Check**: Integrated `candidate_domain_resolves_fast()` with LRU caching (5,000 entries) to bypass dead domains in <32 ms before launching Playwright or HTTP crawls.
- **DNS MX Mailbox Verification**: Integrated `email_has_valid_mx()` via `dnspython` to filter out non-existent mail exchange servers (~3.5 ms per lookup).
- **Minpromtorg Registry FTS5 Parity**: High-speed full-text search indexing across 470,000+ entries with verified multi-round benchmarks across 45+ real industrial procurement items.
