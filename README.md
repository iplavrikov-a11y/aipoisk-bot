# TenderLex Bot

SEO: [текущий статус](docs/PROJECT_STATUS.md), [свежие даты и часовой сбор — 4 октября](docs/SEO_DAILY_COVERAGE_2026-10-04.md), [история ревизий](docs/SEO_AUDIT_LEDGER.md). Панель показывает 30 календарных дней каждого источника, предварительные данные Google отмечены, решения выполняются с агентом без ручных согласований. Оценка функциональности — **9/10**; рост поисковых позиций пока не доказан.

Проверки последнего этапа: 799 backend-тестов и 54 подтеста, затем 44 целевых теста с фиксированной календарной датой; сборка админки успешна. Источники и ограничения проверки GitHub указаны в отчёте. [Первоначальное исправление панели 4 октября](docs/SEO_ADMIN_REPAIR_2026-10-04.md) и [отчёт 2 октября](docs/SEO_FOLLOWUP_REPORT_2026-10-02.md) сохраняют историю своих этапов. Исходные снимки 1–2 октября используются по [протоколу сравнения](docs/SEO_WEEKLY_COMPARISON.md).

TenderLex Telegram bot and admin panel for procurement document analysis and
supplier search.

Public product domain: `https://tenderlex.ru`
Admin/internal domain: `https://admin.tenderlex.ru`

## Production notes

- Runtime server: `202.71.13.57` (`HOSTKEY B.V.`, Netherlands), path: `/root/projects/tenderlex`.
- Backend: `tenderlex-api.service` on `127.0.0.1:8088`.
- Deposit Packages Bonus Restoration, Direct Purchase Buttons & Multi-Tab Billing Redesign (2026-10-18):
  - Fixed deposit package bonus zeroing for clients with custom task prices in `backend/app/main.py` and `cabinet-client.tsx`. Deposit tiers faithfully award +17% (3 000 ₽ -> 3 500 ₽), +30% (5 000 ₽ -> 6 500 ₽), +40% (10 000 ₽ -> 14 000 ₽), and +50% (25 000 ₽ -> 37 500 ₽).
  - Added direct `[ Купить ]` buttons inside the cabinet tariffs dropdown for one-click modal opening with selected tier.
  - Redesigned cabinet top-up modal with 3 tabs: `Оплата картой` (direct card transfer + Telegram crediting with pre-filled payload), `Счёт для юрлиц` (B2B invoice stub with UPD/EDO notice and instant Telegram/Email request triggers), and `СБП` (payment gateway stub with card fallback).
  - Connected the header `Чат` button directly to the live bottom-right `ChatWidget` via `open_tenderlex_chat` event, completely eliminating the obsolete development stub modal.
  - Verified with 904 backend tests passing, clean Next.js typecheck/build, and live deploy on `202.71.13.57`.
- Compare-then-Match Entity Resolution, Order 567 Variation Clustering & Custom Source Filters (2026-10-16):
  - Zero-Shot Compare-then-Match (`extractor.py`): inspired by SOTA GitHub implementations (ComEM, MatchGPT), LLM extracts structured `target_identifiers`, `site_identifiers`, and detects `identifier_conflict` and `material_conflict` to strictly reject homonyms and partial matches without hardcoded brand/model dictionaries (Strict Rule 14 compliance).
  - Physical Grounding Check (`extractor.py`): `is_price_grounded_in_text` verifies that numeric prices extracted by LLMs are physically present in the underlying HTML or snippet text, preventing synthetic price hallucinations.
  - Foreign & Marketplace Filtering (`extractor.py`): `is_foreign_source`, `is_listing_url`, and configurable `EXCLUDED_MARKETPLACES` eliminate cross-border platforms (AliExpress, Taobao, eBay), forwarding agents, and non-commercial catalog/listing aggregations.
  - Order 567 (44-FZ) Price Variation Clustering & Dynamic 5-Supplier Quota (`pipeline.py`): calculates coefficient of variation $V = (\sigma / \bar{p}) \times 100\%$ and uses combinatorial subset search to select the largest homogeneous cluster of up to 5 suppliers with $V \le 33\%$. Eliminates forced single-quote fallbacks; custom or blueprint items with no valid market quotes are honestly marked as `В открытых источниках цена отсутствует (заказная позиция / по чертежу)`.
  - Guaranteed 5-Supplier Quota with Legal Entity Deduplication (`pipeline.py`): extraction loop dynamically monitors verified cluster members (`_get_consensus_count() >= target_suppliers`) instead of raw/outlier pages, expands LLM extraction budget to 20 calls, and employs INN (`seen_inns`) and root-domain (`_get_base_domain`) deduplication to guarantee 5 distinct, independent legal entities without duplicate branches or mirror domains.
  - Dynamic 5-Supplier Excel Reports (`excel_report.py`): dynamic columns for 1 to 5 verified suppliers, dynamic Excel formulas for sample variation coefficient (`STDEV.S / AVERAGE * 100`), and formatted indicators for blueprint-only items.
  - Three-Tier Configuration Hierarchy (`models.py`, `db.py`, `jobs.py`, `main.py`, `PriceMonitoringView.tsx`): supports master system settings (`SystemSettings`), client-level profile overrides (`Client`), and job-level parameters (`Job`) for marketplace filtering, foreign source filtering, supplier counts, and max variation percentage.
  - Verified with 900 backend tests passing (including 30 price monitoring tests in `test_price_monitoring*`), frontend built, and live deploy on `202.71.13.57`.
- Unpopulated Form Templates & Participant Instructions Defense (2026-10-15):
  - Pre-flight Heuristic Form Template Filter (`document_parser.py`): extended `is_substantive_tz_text` with blank form and participant instruction markers (`STRONG_TEMPLATE_TRIGGERS`, `FORM_TEMPLATE_INSTRUCTION_PATTERNS`). Documents containing only tender instructions and unpopulated table cells («Указать наименование товара...», «Например: «длина товара: составляет ___ см»») are rejected before external AI calls and search.
  - Strict Rule 14 AI Procurement Profile Extraction (`supplier_search.py`): updated `build_procurement_profile` prompt to return empty `items: []` when no physical commodities exist in document, removed forced item generation on retries, and added generic names («Товары по техническому заданию», «Техническое предложение», «Материальные ресурсы») to undefined/placeholder filter lists.
  - Worker Execution Gate & Automatic Balance Refund (`jobs.py`): halts pipeline before supplier discovery if specification yields 0 items, triggers `release_job_reservation` (0 ₽ charge, preserves customer generation quota), and marks job failed with informative message `В файле нет позиций для поиска`.
  - Customer Guidance in Telegram Bot (`bot.py`): renders clear advisory card explaining that an unfilled form/template was detected, balance was not charged, and prompting to attach a specification with concrete goods or send text items.
  - Verified with 12 unit and worker tests in `backend/tests/test_tz_validation.py` including regression check against real file from job #889 (`Приложение №1.3.docx`), 865 backend tests passing (100%), and live deploy verified on `202.71.13.57`.
- Multi-Source Price Monitoring, City-Aware Pricing & Geo-Ranking Calibration (2026-10-15):
  - Fixed ZIP Container Error on Text Input (`jobs.py`, `pipeline.py`, `cleaner.py`): eliminated `File is not a zip file` error when users enter nomenclature via raw text or lists (Job #903 «Печь для бани Атмосфера М»). Heuristic text parser `parse_items_from_text` intelligently parses numbered lists, delimiters (`\t`, `|`, `;`), model suffixes, and trailing units, generating a valid in-memory Excel workbook for pipeline ingestion.
  - Multi-File Support for Price Monitoring (`cabinet-client.tsx`, `cleaner.py`): unlocked multi-file upload (`multipleFiles: true`) in cabinet form. Clients can upload 1, 2, or 3 specification files simultaneously (XLSX, XLS, DOCX, PDF, CSV, TXT) combined with optional text items.
  - City & Regional Delivery Targeting for Price Monitoring (`cabinet-client.tsx`, `cleaner.py`, `pipeline.py`, `excel_report.py`, `jobs.py`):
    * Enabled «📍 Поиск в радиусе доставки» checkbox for price monitoring in authenticated cabinet.
    * Integrated `delivery_city` and `geo_radius_km` into price search pipeline (`build_commercial_search_queries`, `generate_monitoring_queries_ai`), prioritizing local suppliers and warehouses (e.g. `«Печь для бани Атмосфера М Вологда купить цена в наличии»`).
    * Annotated output Excel report cell A1 with delivery location and search radius note.
  - Regional Capital Mapping & Geo-Ranking Calibration for Job #902 (`supplier_locations.py`, `supplier_search.py`, `report_builder.py`):
    * Added `RUSSIAN_REGION_CAPITALS` dictionary for automatic geocoding when suppliers provide region names without explicit cities (e.g., «Вологодская область» -> «Вологда»).
    * Enforced strict ascending distance priority for suppliers inside specified radius (`within_radius=True`) before national fallback.
    * Excel reports clearly summarize suppliers found inside radius vs national fallback count.
  - Clean Customer Progress Language (`jobs.py`): eliminated billing amount suffixes (`Списано: X.X ₽`) from price monitoring completion statuses to adhere to client-result language principles and keep financial details strictly in operations history; historical tasks in SQLite backfilled.
  - Test Suite & Deployment: created `backend/tests/test_price_monitoring_multisource.py` with 5 comprehensive tests across 12 diverse industrial commodities; 861 backend tests passing (100%), site typecheck and Next.js build passing, live production deployment verified on `202.71.13.57`.
- Geo-Radius Supplier Search & Logistics Regional Optimization (2026-10-15):
  - Geo Distance Engine & Nationwide City Database (`supplier_locations.py`, `city_coordinates.json`): Haversine distance algorithm with 1.15 road curvature factor covering 1,208 Russian cities and industrial centers (all 1,117+ official cities of Russia from Moscow to Kamensk-Shakhtinsky, Shakhty, Novoshakhtinsk, Zverevo, Gukovo, Belaya Kalitva, Millerovo, Krasny Sulin, Sysert, etc.).
  - 28x Algorithmic Speedup: token n-grams O(1) set lookup in `extract_city_from_text` replaces sequential regex checks, reducing candidate processing time from 420 ms to 0.23 ms.
  - DaData Address Geocoding Fallback: on-the-fly geocoding via DaData Address Suggestions API for unlisted rural settlements, stanitsas, or worker villages (e.g., Malokamensky, Veshenskaya).
  - Flexible Numeric Radius Input (`cabinet-client.tsx`): replaced fixed dropdown presets with an interactive `<input type="number">` allowing users to freely specify any search radius in kilometers (e.g., 50, 250, 400 km).
  - Prominent Final Report Visibility (`report_builder.py`, `jobs.py`, `quote_request.py`):
    * Excel Subtitle (Row 2): `Локация / доставка: г. {Город} (в радиусе до {Радиус} км)`.
    * Excel Summary / KPI (Row 3): `Логистический фильтр: отбор поставщиков в радиусе до {Радиус} км от г. {Город}.`
    * Excel Supplier Rows (Comment column): enriched with confirmed city and actual road distance (e.g., `Локация: Шахты (~78 км)`).
    * Word Quote Request (DOCX): automatically includes `Город поставки: г. {Город}` in procurement delivery conditions.
  - Flexible Rollout Architecture (`models.py`, `schemas.py`, `main.py`):
    * Per-client activation via `Client.allowed_geo_radius` (active for admin account `edeefa9da6e44803a6b264c250e91251`).
    * Platform-wide master toggle via `SystemSettings.geo_radius_search_enabled_global`.
  - 855 backend tests passing (100%), site typecheck and Next.js/Vite builds passing, live deploy verified on `202.71.13.57`.
- Yandex Search API Cost Tracking, Zero-Cost AI Analysis Badges & Admin Usability (2026-10-14):
  - Yandex Search API Cost Accounting (`yandex_search.py`, `pipeline.py`, `jobs.py`, `models.py`): integrated dynamic request counter `total_requests` across synchronous and asynchronous Yandex Cloud Search API v1/v2 query builders. Added `yandex_requests_count` and `yandex_cost_rub` tracking to batch price monitoring data structures, durable job rows, and `evidence.json` artifacts at the standard rate of 0.04 ₽ per request.
  - Checkpoint Durability: checkpoints save cumulative Yandex requests, preventing counter resets when resuming interrupted tasks.
  - Historical DB Backfill: retroactively backfilled all completed price monitoring jobs in SQLite with actual search request volumes and ruble costs.
  - Admin Panel Clarity (`App.tsx`, `PriceMonitoringView.tsx`):
    * Job task strip displays accurate Yandex cost badges (`🔍 X запр. · Y.YY ₽`) for price monitoring tasks, included in the header search expenditure aggregate.
    * Documentation analysis (`procurement_report`) displays an explicit `⚡ 0.00 ₽ (ИИ)` badge explaining that analysis is performed solely by LLMs without paid external search requests.
    * Fixed nomenclature count label on price monitoring cards to display positions (`N поз.`) instead of incorrect suppliers (`N пост.`).
    * Price monitoring management table shows actual Yandex API expenses beneath the customer charged sum.
  - WAF Cookies Management (`CookiesView.tsx`): dedicated interface for controlling session cookies across e-commerce and wholesale platforms.
  - Verified with 845 passing backend tests and 54 subtests (100%), full Next.js/Vite builds, and safe live deploy on `202.71.13.57`.
- Custom Price Monitoring Module: Consensus Clustering, Outlier Pruning, Pagination & Live Verification (2026-10-13):
  - Consensus Clustering Algorithm (`pipeline.py`, `excel_report.py`): sliding-window density clustering identifies the dominant consensus cluster within `cluster_ratio` (default $\le 2.2x$). Quotes outside the consensus cluster are pruned as outliers (`is_outlier = True`), completely excluded from Excel report columns and `=MIN`/`=AVERAGE` formulas. If all quotes diverge without consensus, cells are marked «разброс цен» with an explanatory tooltip to safeguard procurement.
  - Quorum Guarantee (>= 3 Sources per Item): adaptive 2-wave search architecture. Wave 1 queries commercial wholesale and retail sources; if valid quotes $< 3$, Wave 2 fires industry-specific broad queries across up to 45 candidate URLs. Snippet harvesting ensures price extraction even when vendor sites block automated crawlers (HTTP 401/403/444/503).
  - Admin Panel Usability & Pagination (`PriceMonitoringView.tsx`): full client and job history pagination (5 / 10 / 20 items per page) with page position counters, compact Prev/Next controls, quick filter tabs («Все», «С доступом», «С индив. ценой»), and settings grid (base price, 3/4/5 suppliers, position limit, concurrency, cluster ratio, marketplace exclusion toggle).
  - Fresh Live Verification on 4 New Industrial Goods (`scripts/test_live_new_products.py`):
    * Манометр МП3-У 0-1.0 МПа [ШТ]: 4 consensus sources [600, 725, 725, 929] ₽ (spread 1.55x, 2306 ₽ outlier pruned).
    * Кран шаровой 1/2" [ШТ]: 4 consensus sources [284, 353, 482, 482] ₽ (spread 1.70x, 851 ₽ outlier pruned).
    * Автоматический выключатель ВА47-29 16А [ШТ]: 5 consensus sources [136, 140, 155, 193, 240] ₽ (spread 1.76x).
    * Перчатки х/б с ПВХ 4 нити [ПАР]: 5 consensus sources [13.13, 14.5, 20.75, 22, 23] ₽ (spread 1.75x).
    * 100% quorum achieved ($\ge 3$ sources per item), tight pricing consensus, zero wild price spreads in report columns.
  - Full test suite passing: 840 backend tests and 54 subtests (100%), verified production deployment on `202.71.13.57`.
- Large Specification Scaling & Anti-Hang Guardrails for 1,000+ Items (2026-10-11):
  - Linear Excel matching optimization (`backend/app/report_builder.py`): eliminated $O(N^2 \times M)$ nested matching hang, reducing 1,000-item Excel generation time to 4.7s (2.2ms match step) via dictionary lookup.
  - Excel cell character limit protection: capped cell A3 summary breakdown to top 20 items + explicit continuation counter, strictly preventing 32,767 OpenXML corruption in Microsoft Excel.
  - AI prompt & normalization guardrails (`backend/app/supplier_search.py`): Rule 6 clusters large specifications and estimates into 25–35 market pools; `MAX_PROFILE_ITEMS = 50` caps profile size and absorbs overflow into sub-items.
  - Customer guidance banners: added helpful intake advice in web cabinet launcher, task cards, strategy modal, and Telegram bot recommending file splitting for mixed-trade specifications or balanced search.
  - Strict Rule 14 compliance: zero hardcoded product names, synonyms, or regex heuristics; semantic understanding and clustering performed strictly by AI.
  - Verified with 828 passing backend tests, Next.js build, and live production deployment.
- Usability of Multi-Item Excel Reports: Adaptive Row-Group Collapsing & Clear On-Sheet Guidance (2026-10-11):
  - Adaptive initial outline state (`backend/app/report_builder.py`): $\le 4$ items open expanded (`hidden=False`) for instant visibility of contacts; $> 4$ items (5–35+ positions/estimates) open collapsed (`hidden=True`) to prevent 500+ row overload.
  - Interactive on-sheet guidance: cell A3 provides clear instructions on operating outline buttons `[+]` / `[-]` or levels `[1]` / `[2]`. Category banner rows include intuitive symbols and action hints (`▼` / `▶` / `▷` + `нажмите [-] слева для сворачивания` / `нажмите [+] слева для раскрытия`).
  - Unit tests: verified with `test_supplier_xlsx_multi_item_adaptive_collapse_for_many_items`, 826 backend tests passing, clean site build, and production deployment.
- Unified Single-Sheet Excel with Collapsible Row Outline Grouping & Client Copy Alignment (2026-10-10):
  - Replaced fragmented multi-tab Excel reports with a unified single sheet `Сводный реестр` featuring native Excel row grouping (`outlineLevel = 1`).
  - Synchronized all customer-facing copy in web cabinet, modal dialogues, and Telegram bot from "отдельные вкладки" to "сворачиваемая структура (+ / -) на едином листе".
- Client-Facing Language Audit & Anglicism Removal Across Web & API Documentation (2026-10-10):
  - Replaced technical jargon and English borrowings across landing page, web cabinet, knowledge base articles, and MCP API client with professional procurement terminology.
- Supply-Chain Category Clustering, Selective Category Picking & Crash-Test on 50 Complex Procurements (2026-10-10):
  - Supply-chain market clustering: AI profile builder (`build_procurement_profile`) groups items by vendor capability pools instead of blind per-line item splitting. Auxiliary items (fasteners, hangers, cables, brackets, consumables) are absorbed into core systems (`included_sub_items`) to prevent wasteful supplier searches for minor hardware.
  - Core vs Auxiliary classification: positions are classified with `is_core`, `is_auxiliary`, `cost_tier`, and full sub-item transparency.
  - Web Cabinet category picker: interactive modal allows users to select exact categories with checkboxes («Выбрать все», «Только основные»), displaying dynamic cost calculation in real time.
  - Dynamic incremental billing reservation: `reserve_additional_job_units` safely increments existing reservations under the `uq_billing_transaction_job_kind_operation` unique constraint.
  - Comprehensive crash-test on 50 independent complex specifications across 10 industries (`scripts/crash_test_50_complex_procurements.py`): scored 9.92 / 10.0 with 100% pass rate, 0% fastener leakage, and 100% sub-item disclosure.
- Dynamic Multi-Item Specification Detection & Dynamic Quota Strategy Selection (2026-10-10):
  - Intake form UX improvement: eliminated premature mode selection («Сбалансированный» vs «Попозиционный») at launch before specification documents are parsed.
  - Intelligent specification decision gate: single-item specifications run immediately with zero interruptions; multi-item specifications pause in `awaiting_customer_confirmation` (`confirmation_kind="multi_item_strategy"`), displaying the detected positions list and offering a clear choice between Balanced (1 task unit, dynamic quota shared across items) and Per-item (deep search per item, N task units).
  - Re-profiling caching: procurement profile is cached in `dobor_context`, consuming zero additional AI calls when resuming after strategy selection.
  - Dynamic quotas: removed hardcoded counts ("70", "40–50") from all customer modals, help texts, and Telegram bot copy in favor of dynamic system settings (`default_supplier_target`).
  - Web cabinet & Admin panel: added strategy confirmation modal with item tags, action buttons on job cards, and admin job badges.
  - Verified with 816 passing backend tests and live server deployment.
- Multi-Item Specification Balancing, Round-Robin Quota Allocation & Multi-Tab XLSX Reports (2026-10-09):
  - Solved item-1 supplier skew in complex multi-item specifications (analyzed 552 database jobs: 35.8% multi-item, 53.7% heavily skewed to item 1): replaced legacy single-item `break` loop with round-robin fair quota allocation (`per_item_quota = (target + K - 1) // K`) and waterfall overflow fallback in `backend/app/supplier_search.py`.
  - Balanced search query generation: updated initial and refinement prompts (`build_supplier_queries`) to guarantee proportional coverage (>=3-5 queries per item) across disparate procurement categories.
  - Multi-tab Excel reports (`backend/app/report_builder.py`): multi-item jobs now generate dedicated tabs for each procurement item (`Позиция 1 - ...`, `Позиция 2 - ...`) alongside the unified `Поставщики` sheet with explicit `Позиция: {item}` prefixes in client comments. Single-item jobs maintain strict 100% backward compatibility with single-sheet format.
  - Partial supply disclaimer in RFQ documents (`QUOTE_REQUEST_INTRO`): added explicit note welcoming partial/item-by-item bids to eliminate vendor refusals when specifications combine disparate product lines.
  - Verified with comprehensive test suite (`backend/tests/test_multi_item_suppliers.py`, 6 tests covering balance, overflow, E2E pipeline, and reports) and 811 total passing backend tests.
- Yandex SearchAPI v2 Async Timeout Fix, 429 Rate Limit Backoff & E2E Pipelines (2026-10-09):
  - Fixed hardcoded 19.3s polling cutoff in `_poll_yandex_operation`: expanded polling window to ~58s across `supplier_search.py`, `exact_product/yandex_search.py`, and `outreach_search.py`, allowing complex multi-term B2B queries (which take 25–35s in Yandex Cloud queues) to successfully return candidate results instead of dropping to empty lists.
  - Added HTTP 429 rate limit backoff and error logging to prevent silent zero-supplier drops.
  - End-to-end verified on live inputs: Job #844 (ultrasonic wire bonder) confirmed 9 suppliers, Job #843 (digital cinema projector) confirmed 6 suppliers. 805 backend tests passing.
- Production Unified Wallet, Deposit Bonus Tiers, Manual Card Top-up & CI/CD Pipelines (2026-10-07):
  - Unified Wallet & Flat Function Pricing: Reworked tariffs from segregated feature packages into a single unified wallet balance (`money_balance_kopeks`) with flat pay-as-you-go task execution (Поиск поставщиков — 99 ₽, Добор — 49 ₽, Подбор товара и аналогов — 99 ₽, Анализ документации — 99 ₽, Анализ + поиск — 198 ₽).
  - Progressive Deposit Bonuses & Custom Tariff Exclusions: Increasing deposit bonuses reward larger top-ups: «Старт» (1 000 ₽ → 1 000 ₽), «Оптимальный» (3 000 ₽ → 3 500 ₽, +500 ₽), «Про» (5 000 ₽ → 6 500 ₽, +1 500 ₽, «Хит»), «Бизнес» (10 000 ₽ → 14 000 ₽, +4 000 ₽), «Корпоративный» (25 000 ₽ → 37 500 ₽, +12 500 ₽ / +50%). Clients with configured individual tariff overrides (`ClientTariffOverride`) are strictly excluded from deposit bonuses — top-ups credit strictly the exact payment 1:1 with zero bonus.
  - Manual Card Top-Up Flow & Cabinet Toolbar Polish: Direct transfer to owner's card/account with instant Telegram notification and manual admin crediting (self-service payment gateway deferred for future phase). Added modal with live calculator, transfer instructions, and 1-click Telegram notification with prefilled details. Replaced standalone top-up button with interactive `[Баланс]` toolbar button (`+` indicator, `h-[30px]`), keeping the top header strictly on 1 non-wrapping row.
  - Landing Pricing Card UI/UX Architecture: Titles placed on dedicated lines to permanently eliminate text truncation/ellipses («Оптимальный»), bonus percentages (`+17%`, `+30%`, `+40%`) aligned directly within price rows on 1 line without wrapping, and clean balance credit containers («НА БАЛАНС: 1 000 ₽ / 3 500 ₽ / 6 500 ₽ / 14 000 ₽»).
  - Admin Panel Live Bonus Calculator & Custom Tariffs Logic: Rapid top-up chips and automatic bonus tier calculation on custom ruble amounts. Automatically switches to clean round amounts and zero bonus for clients with individual rates.
  - CI/CD Pipelines (`.github/workflows/ci.yml`): Parallel GitHub Actions workflows for backend pytest suite (Python 3.12), admin frontend build (Vite), and Next.js site & cabinet build.
  - Playwright E2E Suite (`scripts/test_tariffs_e2e.py`): Full headless browser verification of landing pricing, cabinet top-up modal, interactive reactivity, and screenshot evidence (`output/playwright/`).
- Production B2B API Public Launch, Two-Phase Billing & Enterprise 1C/MCP Integration (2026-10-07):
  - Backend Two-Phase Reservation (`backend/app/mcp_api.py`): Replaced pre-billing risk with ACID two-phase reservation (`OP_RESERVE` on launch, `OP_CHARGE` on success, `OP_RELEASE` on exceptions or zero results). Customer balance is 100% protected against timeouts or unfulfilled searches.
  - Standalone MCP Client (`site/public/scripts/tenderlex_mcp.py`): Eliminated missing npm package 404s by publishing standalone, zero-dependency Python script for Claude Desktop, Cursor, and enterprise agents with 1-click download in web cabinet.
  - Dedicated Public Landing (`site/src/app/api-integracii/page.tsx`): High-converting SEO & GEO landing page targeting procurement queries («API закупок», «поиск поставщиков 1С», «интеграция закупок MCP») with schema.org JSON-LD (`SoftwareApplication`, `BreadcrumbList`, `FAQPage`), interactive code switcher (cURL, Python, Node.js, 1С:Предприятие 8.3 BSL).
  - Main Page B2B API Showcase (`site/src/app/page.tsx`), Site Header & Footer navigation, dynamic sitemap registration (`sitemap.ts`).
  - Knowledge Base Article (`site/src/data/knowledge-base.ts`: `avtomatizaciya-zakupok-cherez-api-1c`).
  - GEO LLM Knowledge (`site/public/llms.txt`, `site/public/llms-full.txt`): Full API reference and endpoints exposed to search crawlers and AI answer engines.
  - Nginx 301 Exact Route (`/etc/nginx/sites-enabled/tenderlex.ru.conf`): Clean redirect from `/api` to `/api-integracii` avoiding conflicts with backend reverse proxy `/api/`.
  - Autonomous Multi-Engine Search Indexing (`scripts/reindex_all_search_engines.py`): Programmatically submitted priority URLs to Yandex.Webmaster recrawl queue (`/recrawl/queue`, quota 150/150), broadcasted 91 sitemap URLs via IndexNow API (Yandex/Bing HTTP 200/202), and submitted `sitemap.xml` to Google Search Console API.
  - Comprehensive Verification: 804 passing backend tests (including 10 MCP suite tests), clean Next.js static build (106 routes), deployed live on production server.
- Cabinet Task Launcher & Help Workflow Reordering (2026-10-06):
  - In customer web cabinet (`cabinet-client.tsx`), reordered task launching tabs:
    1. «Анализ документации» (`procurement_report`) — set as default on load.
    2. «Поиск поставщиков» (`supplier_search`)
    3. «Анализ + поиск» (`analysis_and_suppliers`)
    4. «Подбор товара и аналогов» (`exact_product`)
  - Cabinet job filter dropdown (`jobModeFilter`) aligned to match the exact same order.
  - Help Modal («Справочник функций и алгоритм работы TenderLex») updated: navigation tabs and Step 1/2/3 cards in «Маршрут работы» reordered (Step 1: Анализ документации, Step 2: Поиск поставщиков, Step 3: Подбор товара и аналогов; «Комплексный запуск» combines Step 1 and Step 2).
  - Telegram bot help command (`/help`) synchronized with new workflow order.
  - Verified with 802 passing backend tests, clean TypeScript check, Next.js build, and live server deployment.
- B2B API & CRM Integration with Unified Ruble Balance & Key Auto-Substitution (2026-10-05):
  - Unified client money balance (`money_balance_kopeks`) debiting for external API keys: removed isolated per-service quota limits in favor of single ruble balance debiting.
  - Automatic pricing resolution via `effective_price_kopeks(db, client, service)` accounting for individual client tariff overrides (`ClientTariffOverride`), writing standard `BillingTransaction(operation="charge")`, and pausing requests when money balance is exhausted.
  - Customer Cabinet Self-Service API & Vibe-Coding Hub: added `[🔑 API]` button in cabinet toolbar, streamlined toolbar buttons (`Тарифы`, `Чат`), and launched a 4-tab integration modal (Key & Balance, API Methods & cURL, Ready-to-copy AI & CRM Vibe-Coding Prompt, and Claude Desktop MCP config).
  - Seamless Key Auto-Substitution: all curl commands, AI prompts, and Claude Desktop MCP configurations in the web cabinet automatically pre-populate the client's actual active API key, eliminating manual copy-pasting into configuration files.
  - Persistent Key Security & Reveal: active API keys can be unmasked and copied in full directly within Tab 1 at any time; full keys are securely stored in `ApiKey.secret_token` and served exclusively over authenticated customer sessions.
  - Central Job Table Audit & Admin Panel Visibility: all API operations now write directly to `Job` table with `created_by_telegram_id="api:<prefix>"`, displaying a distinctive purple `🔑 API: <prefix>` badge in admin tasks view with full tracking of search parameters, results, and execution metrics.
  - Admin Panel CRM & Clients Integration: added `🔑 API` filter tab in client list, `🔑 API` badge next to client names, detailed API keys subsection inside expanded client cards with total call statistics, and redesigned `MCP & API` key creation/edit modal displaying the client's live ruble balance and module access toggles.
- Admin Panel UI/UX: Task Action Buttons & Unclipped Filename Overlap Fix (2026-10-03):
  - Solved button overlap and layout distortion in admin panel (`admin.tenderlex.ru`, tasks section): long input filenames (e.g. `Приложение № 1 Описание предмета закупки новая редакция.docx`) previously lacked CSS text clipping, causing the filename string to draw directly over adjacent action buttons (`💬+`, `▶`) and overflow the card container.
  - Implemented strict CSS ellipsis truncation (`max-width: 170px`) for `.btn-files-dropdown`, `.btn-primary-download`, and `.pill-filename`, added `title` tooltips, aligned icon buttons to `26×26px`, added `margin-left: auto` to `.job-actions-strip` to stay right-aligned on wrap, and enabled word-wrapping on long procurement titles.
- Telegram Low-Balance Client Notifications & Owner Telegram Alerts (2026-10-02, updated 2026-10-17):
  - Proactive early detection when a client's balance drops to 100 ₽ or less (`money_balance_kopeks <= 10_000`) after job delivery or before tasks, preventing blocked workflows.
  - Client UX & B2B Outreach Offer: personalized AI pitch tailored to client task and uploaded specification, strictly aligned with TenderLex's cold outreach model (100% automated 2–3 min processing, direct manufacturer contacts, RFQ .docx, analogues, contract risk analysis). Direct call to action to top up balance in web cabinet (`tenderlex.ru/cabinet`), request legal entity invoices with УПД/ЭДО, or configure custom corporate volume tariffs.
  - Owner Telegram Alerts: actionable Telegram notification to the owner containing client name, `@username`, client number, remaining balance, exact operation tariff from `effective_price_to_dict` (base vs custom client override), attempted task file, and 1-click button `💳 Пополнить баланс на {X} ₽`.
  - Dual status handling: early reminder at ≤ 100 ₽ (`хватит не более чем на 1 задачу`) and zero-balance alert at 0 ₽.
  - Throttling & Test Isolation: anti-spam throttling (1 alert per hour per client, automatically reset upon balance top-up) and strict test-environment isolation. 15 comprehensive unit tests in `backend/tests/test_low_balance_notifications.py` + 904 backend tests passing.
- Multi-File Semantic Document Ordering & Rule 14 Ingestion (2026-09-26):
  - Solved multi-file procurement truncation (task #758): when multiple customer files are attached (e.g. contract draft, specification, NMCK, tender notice), files were previously sorted alphabetically, causing large contract drafts (`ПР_4`) to consume context and truncate specification tables (`ПР_1`).
  - Implemented semantic AI-based document classification in `backend/app/document_parser.py` (`organize_procurement_documents_ai`, `organize_procurement_documents`) following Rule 14, dynamically prioritizing technical specifications over contract drafts and extracting real procurement subjects.
  - Expanded context window slices: `matcher.py` prompt context up to 120,000 characters, `supplier_search.py` up to 120,000 characters, and `evidence_miner.py` up to 75,000 characters.
  - Verified live on admin rerun #760: accurately identified 2 of 2 medical mattress positions with 12 characteristics each, matching domestic manufacturer ООО МК «АСК» (М.20.8 and М.20.9) and verified equivalents with exact Form 2 parameters for tender submission.
  - End-to-end multi-module verification (`scripts/test_all_three_functions.py`) verified full pipelines across all 3 functions: `Поиск поставщиков` (9.5/10), `Подбор товара и аналогов` (9.0/10), `Анализ документации` (10/10); 699 unit tests passing with zero regressions.
- DOCX Parser Nested Tables & EIS Form 2 Specification Support (2026-09-24):
  - Solved specification loss in official EIS DOCX files where product parameters and technical requirements are placed in nested tables within container cells (`Table 0 -> Cell (0, 0) -> Nested Table 0`).
  - Added recursive nested table extraction, body-level document-order traversal (`<w:p>`, `<w:tbl>`, `<w:sdt>`), and merged cell deduplication in `backend/app/document_parser.py`.
  - Added empty table marker detection to trigger LibreOffice and enhanced recursive XML fallbacks when table rows are unpopulated.
  - Verified on live customer procurement #719, recovering all 87 specification rows (text increased from 1,060 to 6,609 chars) and matching targeted measuring complex, high-speed camera, and spectrum analyzer suppliers.
  - End-to-end quality audit of live admin rerun #753 (75 suppliers) verified 100% targeted manufacturer/distributor matches (Evercam, Micran, Phantom, Meratest) with complete direct contacts and clean DOCX RFQ delivery terms.
- Supplier Search Acceleration & Headless Browser Optimization (2026-09-14):
  - Accelerated supplier search candidate verification from 18s per site down to 1.5–2.5s (nearly 3x overall task speedup, verified live on task #712 dropping duration from 40m 04s to 14m 23s).
  - Switched page loading from `networkidle` to `domcontentloaded` (timeout=7000) with 1.5s soft network idle settle.
  - Enabled `ignore_https_errors=True` in Playwright context to support Russian industrial and state sites with domestic/self-signed certificates.
  - Added non-HTML extension filtering (`.pdf`, `.docx`, etc.) to prevent Playwright download dialogue stalls.
  - Expanded browser concurrency semaphore to 5 tabs per job.
- Complete Elimination of Legacy Paths & Symlinks (2026-09-14):
  - Permanently removed legacy symlink `/root/projects/aipoisk-bot`.
  - Sanitized database paths with 0 matches for old directory across all SQLite tables.
  - Migrated systemd services to native `tenderlex-*` units (`tenderlex-api`, `tenderlex-worker`, `tenderlex-bot`, `tenderlex-site`).
- Comprehensive SEO Optimization, High-CTR SERP Snippets & IndexNow Pipeline (2026-09-12):
  - Solved zero CTR on Page 1 Google & Yandex search rankings (positions 4–8) by shortening titles to 53–56 chars with template compatibility and crafting concise 140–152 char descriptions with clear commercial triggers.
  - Added interactive product quick-check form in `/podbor-tovara-i-analogov-po-tz` with popular equipment pills and automatic intent pre-filling in web cabinet (`?scenario=exact_product&text=...`).
  - Embedded interactive `ProcurementCalculator` in `/analiz-rynka-44-fz` targeting high-intent Google striking-distance queries (*«калькулятор нмцк»*).
  - Integrated dual submission to Yandex Webmaster recrawl queue and IndexNow Open API (Yandex, Bing, Seznam) in `backend/app/yandex_seo.py`.
  - Updated LLM search indexes (`llms.txt` and `llms-full.txt`) with exact product & equivalents engine for ChatGPT, Perplexity, and Claude.
- Weekly Recurring SEO Audit & Self-Reflection Protocol (2026-09-12):
  - Established formal recurring audit protocol documented in `docs/WEEKLY_SEO_AUDIT_PROTOCOL.md` and historical tracking ledger in `docs/SEO_AUDIT_LEDGER.md`.
  - 2-Phase operational model: Phase 1 provides zero-mutation diagnostic report with 5-expert panel scoring (baseline 8.6/10) and week-over-week deltas against historical metrics; Phase 2 autonomously implements, tests, deploys live, and pings IndexNow/Webmaster upon confirmation.
- Security Hardening, Zero-Caching Compliance & Chat Reliability (2026-09-12):
  - Stripped hardcoded fallback secrets (DaData API key, Telegram bot tokens) from code and Next.js routes.
  - Whitelisted allowed upload extensions (`.docx`, `.doc`, `.pdf`, `.xlsx`, `.xls`, `.rtf`, `.odt`, `.zip`, `.rar`, `.7z`, `.txt`) in `/api/customer/tasks` to prevent binary/executable uploads.
  - Enforced zero-caching rule in exact product AI evaluation routines (`minprom.py`, `deep.py`) ensuring 100% fresh market checks.
  - Purged internal `(Форма 2)` references from client cabinet, tariff cards, and bot messages in favor of customer-facing copy (`Подбор аналогов`).
  - Implemented atomic file writes and HTML escaping in on-site support chat (`chat_sessions.json`), eliminating Telegram 400 Bad Request errors.
  - 691 pytest tests passing, live deploy verified across API (8088), Site (3093), worker and bot.
- Telegram Bot Live Audit & Userbot Validation (2026-09-10): Comprehensive end-to-end automated audit via Telegram MTProto userbot (`agent-audit`), resolving edge cases across navigation (keyboard preservation on fallback messages, text aliases `кабинет`, `создать`, `баланс` etc.), short product query acceptance in specification mode, document extension whitelist (`.docx`, `.pdf`, `.xlsx`, archives), module ordering, and 19-digit procurement notice formatting guidance. 0 open defects, full revision ledger and reports in `docs/audits/`.
- Public TenderLex site: Next.js app in `site/`, served at `https://tenderlex.ru` by `tenderlex-site.service` on `127.0.0.1:3093`.
- Product Radar: Resident badge integrated in the public footer, launch campaign prepared for 2026-08-24.
- Contact Routing & Channels: Support channels: Telegram direct (`https://t.me/lexelence`), Telegram bot (`https://t.me/tenderlex_bot`), email `info@tenderlex.ru`, and on-site interactive chat.
- UI/UX theme: Light-emerald high-trust B2B palette with natural procurement copy across the interactive showcase (`ScrollWorldViewer`), calculator (`ProcurementCalculator`), and web cabinet (split-toolbar layout with left-aligned navigation & contact buttons and right-aligned function guide and compact notification bell toggle `[🔔]`, integrated help modal `max-w-5xl`, real-time Web Audio task completion chime, customer expense and operations history modal (`/api/customer/billing/transactions`) with itemized operations, server-side pagination, exact client override charges and clean procurement subject titles, bottom floating toast pill, pulsing badges for new jobs, dismissible live chat with header trigger, and clean decluttered button styling).
- Trial Balance & Email Verification: New registrations receive 495 ₽ trial balance (5 tasks @ 99 ₽); web cabinet displays compact test banner guiding users to direct contact channels for quota top-ups; transactional email confirmation uses a bulletproof responsive HTML template with single-account-per-email uniqueness enforcement.
- Referral Program & Anti-Abuse System: Deposit-matched referral rewards (+1 000 ₽ bonus for invitees on their first qualifying balance top-up >= 1 000 ₽, and +1 000 ₽ reward for inviters upon the invitee's first qualifying payment). Free trial runs NEVER grant referral rewards, fully neutralizing throwaway multi-accounting abuse. Includes multi-layer anti-abuse safeguards: automated self-referral detection and unearned bonus deduction on account merge, cross-channel linkage validation (ID/Telegram/cookie), cycle prevention, disposable burner email blacklisting, IP rate-limiting, and payment idempotency. Client UX is integrated via an in-cabinet modal window (`ReferralModal`) without separate pages: compact zero-scroll layout, 1-click personal links, real-time counters, strict module ordering, cleaned Russian copy without file formats or Anglicisms, and Telegram bot deep linking (`t.me/tenderlex_bot?start=ref_<id>`) with pre-filled chat sharing. Cabinet toolbar button is finalized with design 5.4C (neutral slate button `bg-slate-100`, single amber gift icon, and high-contrast 10px emerald badge `+1 000 ₽`). Dedicated design showcase page available at `/demo-buttons`. Backend architecture includes future-ready data structures for partner payouts.
- High-Efficiency Supplier Search & 95% Search API Budget Optimization: Overhauled the web candidate discovery engine to eliminate search request inflation and lower procurement search cost from 5.50+ ₽ down to 0.29 ₽ while strictly preserving deep organic coverage up to page 7:
  - Corrected Yandex Search API v2 XML parameterization from `groupBy` to `groupSpec` with `groupsOnPage: 70`, fetching 70 organic results in a single 0.04 ₽ request instead of 3–7 pagination calls.
  - Fast-Path candidate pool reuse: when initial review falls short of target by 1–2 items, the recovery pass re-evaluates unreviewed candidates from the initial discovery pool before initiating any network searches, dropping secondary API expenses to 0 ₽ in ~80% of runs.
  - Adaptive recovery query dispatch: scales recovery query count strictly to the actual deficit (`min(8, max(3, gap // 2))`) instead of firing 24 static queries.
  - Chunked execution with early stopping: queries run in chunks of 4 with immediate cancellation of pending requests once candidate target floors are met.
  - Suffix and query hygiene: eliminated noisy commercial suffixes (`купить`, `контакты`) in favor of high-yield manufacturer intent queries (`производитель завод`, `каталог продукция`, `официальный сайт`).
  - Cross-project synchronization with `emailagent`: deployed identical `groupSpec` and 70-result depth optimizations to `emailagent` (`core/yandex_search.py` and `backend/services/supplier_discovery/service.py`).
- Search Architecture Modernization & Factory Snippet Mining (2026-09-10):
  - Raised Yandex Search XML depth (`groupsOnPage: 70`) across exact product module (`backend/app/exact_product/yandex_search.py`).
  - Strict query hygiene in supplier search (`backend/app/supplier_search.py`): eliminated placeholder phrases (`отечественный производитель`, `согласно ТЗ`, `паспорт завода`, `по спецификации заказчика`) from query planning and profile normalization, achieving 0 junk queries and lowering search API load by ~40%.
  - Aggregator snippet mining: automated extraction of real manufacturer entities from Russian B2B aggregators with targeted queries for official factory sites.
  - Smart PDF technical content and table extraction (`backend/app/document_parser.py`): table detection via PyMuPDF (`find_tables().to_markdown()`) with technical scoring across passports and catalogs up to 80 pages.
  - Fully validated across 15 real customer procurement jobs with 690 regression tests passed and live deployment verified on server.
- Exact-to-Supplier Search Pipeline: 1-click seamless pipeline from completed "Подбор товара и аналогов" into "Поиск поставщиков" across Web Cabinet and Telegram Bot. Generates a hybrid context combining original specification files with a structured manifest of identified equipment and confirmed equivalents from `evidence.json`, enabling instant supplier discovery with tariff quota reservation and policy controls.
- Exact Product & Analogs Engine v2 (EmailAgent Parity, Whole-Document Analysis & Characteristic-First Matching): Complete architectural overhaul of the exact product matching engine (`backend/app/exact_product/`) achieving full architectural parity with `emailagent` while adapting to TenderLex direct-upload workflows:
  - **Whole-Document Customer TZ Analysis (`product_brand_detector.py`)**: Tailored for TenderLex direct client file uploads (`.docx`, `.xlsx`, `.pdf`). Unlike EmailAgent (which aggressively isolates tables from noisy multi-message email threads), TenderLex preserves and analyzes the customer's uploaded Technical Assignment **100% in its entirety**, retaining customer header hints, delivery conditions, and full table specifications.
  - **Modular Package Architecture & Worker Runtime Resilience**: Decomposed monolithic logic into dedicated modules (`models.py`, `evidence_miner.py`, `matcher.py`, `fetcher.py`, `search_planner.py`, `validation.py`, `minprom.py`, `pipeline.py`, `docx_report.py`, `xlsx_report.py`) with package-relative imports and safe fallback wrappers for `aipoisk-worker` systemd execution.
  - **Tier-0 Evidence Mining & Hint Extraction (`evidence_miner.py`, `matcher.py`)**: Mines hard facts directly from attached tender documentation before initiating external searches. Flexible hint parser extracts unbulleted plain-text brand, model, and analog hints from uploaded Word documents without requiring markdown formatting.
  - **Characteristic-First Matching (`matcher.py`)**: Selects models strictly based on parameter coverage rather than hallucinated brand names, with strict text grounding (`_is_model_grounded_in_doc`), matrix scoring, multi-document fact fusion, second-round targeted factory document search, and adaptive analog backfilling (`fails <= 5`).
  - **Deep Web & PDF Extraction (`fetcher.py`, `spec_searcher.py`)**: High-fidelity extraction of technical tables via PyMuPDF (`fitz.find_tables().to_markdown()`), HTML property block parsing, link-crawling for manufacturer PDF datasheets, domain sanitization, environment-aware Yandex Search credentials, and seamless Playwright browser fallback.
  - **Deterministic Validation & Auto-Rotation (`pipeline.py`, `validation.py`)**: Strict compliance checking, auto-rotation of conforming equivalents into prime analog slots, automatic rejection of non-conforming items, dealer/shop noise elimination (e.g. `Санова`, `Климбит`), and neutral phrasing in Form 2 comments.
  - **Substantive Specification Validation & Empty Document Rejection (`document_parser.py`, `jobs.py`, `bot.py`)**: Strict pre-flight validation preventing unpopulated template documents (e.g. `Введите текст технического задания...`, placeholder brackets, empty Word/PDF files) from triggering spurious hallucinated searches (such as office stationery). Automatically fails fast with friendly advice, releases client tariff reservations with 0 ₽ charge, and ensures 100% Rule 14 parity on real multi-position technical specifications.
  - **Budget Safeguards & DOCX Exclusivity**: Capped at `MAX_EXACT_POSITIONS_PER_JOB = 5` and `MAX_YANDEX_QUERIES_PER_JOB = 20`, live progress streaming callbacks, and full Form 2 export exclusively in Word DOCX.
- Automated Omnichannel Nurturing Sequence & 1-Click Unsubscribe: Behavioral 5-step sequence (24h post-registration, 14d final prompt, 48h post-first-task, trial completion, and 10+ days reengagement) across Telegram and Email within work hours (09:00–20:00 MSK). Features smart channel prioritization based on user activity (Web cabinet vs Telegram bot) to eliminate cross-channel spam, high-converting card-based HTML email templates matching `hh-agent` styling with scaled 1.5x typography, verified outbound relay deliverability (OpenDKIM selector `relay`, root SPF `v=spf1 ip4:79.133.182.215 include:_spf.jino.ru ~all`, and `_dmarc` policy on `tenderlex.ru`), automated test runner relay isolation (`suppress_real_email_relay_in_tests` preventing test-induced bounces), and universal 1-click unsubscribe via Telegram button (`🔕 Отписаться от подсказок`) and HMAC-signed email link (`/api/customer/auth/unsubscribe`) that permanently disables marketing messages.
- Admin Panel Clients Dynamic Live Sync & Smart Polling: Zero-reload real-time client tracking powered by a dedicated lightweight sync-check endpoint (`/api/clients/sync-check`, <1ms response, 0% CPU) with 3.5s background interval, eliminating heavy full-table queries. Features instant Toast notifications with Web Audio API chime on new registrations (showing client number, name, and contact details with 1-click navigation), `[Новый]` badge and emerald pulse highlight for recently registered clients, and a `🟢 Live` status indicator with relative sync timer and manual `🔄 Обновить` button in the toolbar.
- Public site SEO and verification wiring live in the site app and the `tenderlex-site.service.d/seo.conf` drop-in; Google Search Console uses DNS TXT, Yandex Webmaster uses the public HTML verification file, and Yandex Metrika is enabled by env.
- SEO Analytics Pipeline: Yandex Webmaster, Yandex Metrika and Google Search Console integrations (`backend/app/yandex_seo.py`, `backend/app/google_seo.py`, `/api/seo-analytics`) expose collected snapshots with explicit source periods. Google resource totals and visible query samples are separate; missing metrics remain unknown. Snapshot freshness follows collection time, with concurrent expired reads serialized across API and collector processes; a dedicated hourly admin timer updates the shared snapshot. Existing recrawl and digest endpoints remain available separately.
- Admin Panel SEO View: Dedicated «SEO и Трафик» dashboard with bounded automatic checks every two minutes while visible, separate Yandex and Google charts/tables, traffic sources, page metrics and confirmed registration visits for their measurement period. Decisions are handled with the agent; no approval/reject or SEO action buttons. Russian status messages, timeout/recovery handling and responsive tables are verified in authenticated Chrome. Changing sample average positions is not labeled as proven ranking growth.
- B2B Outreach & Lead Generation Engine: Dedicated system for massive B2B supplier/contractor acquisition by niche query with real-time web crawling, AI relevance scoring, negative keyword & domain filtering (excluding banks, guarantee brokers, OFD/EDS providers, tender software, and education/media), automated MX DNS domain verification, global top-level navigation layout (Search Tasks vertical list, Inbound Answers, Direct Composer, Mail Settings), task-isolated workspace architecture (CRM leads, email campaigns, AI composer), seamless jitter-free inbox synchronization (background server IMAP worker loop every 45s + silent 20s client DB polling, replicating `emailagent`), stable unread message reading (opening unread emails in the "Новые" tab preserves selection without auto-vanishing), sandboxed responsive `EmailBodyFrame` with responsive HTML table rendering and formatted fallback cards for empty bodies and opt-outs, interactive read/unread circle indicators across all inbox categories, sender avatars with hash-based color palette, dedicated **История переписки** correspondence thread modal with full chronological message timeline and inline fast AI replies (`/api/outreach/inbox/{id}/thread`, `/api/outreach/leads/{id}/thread`), 1-click instant email unsubscribe & permanent stop-list integration directly within incoming email view with confirmation guard, visual feedback, dynamic state transitions (`[Удалить из рассылки]` -> `[✓ Отписан]`), automated lead status sync (`status="unsubscribed"`, `mx_valid=False`), multi-tier intelligent anti-spam engine with Unicode homoglyph normalization (defeating Cyrillic lookalike obfuscations like `Mаkitа`), self-learning domain/sender blacklist, 1-click permanent spammer blocklist and server-side IMAP auto-expunge, automated Bounce / NDR parser linking delivery failure notifications to leads with diagnostic rejection codes, relay-level Postfix NDR discard (`transport_maps` with `tenderlex.ru discard:` on `79.133.182.215`), immediate server-side IMAP expunge of system bounce/NDR notifications to prevent mailbox clutter while preserving delivery failure diagnostics on leads, accurate unified metrics accounting for sent, replied, and bounced leads, resilient campaign worker with safe resume handling without counter clobbering and campaign-level stop-list shielding, SOCKS5 SMTP/IMAP transport with `info@tenderlex.ru`, lead parser hygiene (blocking placeholder names, test domains, and support/helpdesk ticket queues), pre-flight deliverability verification (`verify_email_deliverability` with SMTP handshake ping), Spintax randomization engine (`{...|...}`), RFC `List-Unsubscribe` headers, adaptive delay jitter, and AI Email Assistant for generating cold pitches and smart replies.
- Commercial delivery controls (2026-10-15): TenderLex outreach consults the shared bot-suite suppression registry before every commercial send and fails closed when it cannot be read. Public unsubscribe links are recipient-bound and signed; confirmation is a non-mutating `GET`, while the opt-out is recorded only by `POST`. The registry covers commercial outreach only: account/authentication and customer-nurturing messages retain their existing controls. Delivery metrics cover the shared Postfix relay’s SMTP response, not inbox placement, and direct Jino SMTP is outside that ledger. Operational contract, configuration, recovery, and verified limits: [docs/OUTREACH_DELIVERY.md](docs/OUTREACH_DELIVERY.md).
- Model Context Protocol (MCP) & Public REST API: Full-featured integration layer allowing external AI assistants (Claude Desktop, Cursor, VS Code, ChatGPT Codex, Windsurf, Zed, custom backend agents) to directly leverage all TenderLex core engines in real time. Features:
  - Cryptographically secure API keys with 256-bit entropy (`tl_live_...`, `tl_admin_...`), SHA-256 one-way hashing in database (`ApiKey` model), sliding-window in-memory rate limiting, and granular per-service quotas (supplier search, exact product & analogs, procurement documentation audit).
  - Full Master Admin Key lifecycle with persistent `secret_token` retrieval for authenticated admins, 1-click token copying, and automatic token pre-filling in all AI assistant config snippets.
  - Public REST endpoints (`/api/v1/mcp/suppliers/search`, `/api/v1/mcp/products/exact-analogs`, `/api/v1/mcp/procurements/analyze`, `/api/v1/mcp/balance`) and secure sandboxed report downloads (`/api/v1/mcp/downloads/{filename}`).
  - Flexible AI-Ready Payload Normalization: Built-in `@model_validator` handlers automatically accept natural, non-strict inputs from external AI agents and chat harnesses (supporting `product_name`, `title`, `okpd2`, `characteristics` arrays/dicts, `query`, `doc`, `delivery_region`, `max_results`), assembling complete technical specifications and preventing `422 Unprocessable Entity` schema errors.
  - Multi-policy supplier search parameter `search_policy`: supports `'normal'` (open Russian market), `'minprom_registry_priority'` (prioritizes Russian manufacturers from GISP / Minpromtorg registry with market fallback), and `'minprom_registry_only'` (strictly filters for confirmed domestic manufacturers with Minpromtorg registry entries for 44-FZ / 223-FZ national regime compliance).
  - Dedicated standalone stdio MCP server (`mcp_server/server.py` and `scripts/tenderlex_mcp.py`) implementing the official JSON-RPC 2.0 stdio protocol with 4 structured tools (`tenderlex_find_suppliers`, `tenderlex_find_exact_and_analogs`, `tenderlex_analyze_procurement`, `tenderlex_check_balance`).
  - Admin Panel **«MCP & API»** view: Clean light-theme 2-column layout, Master Admin Key management with toggleable eye visibility, 1-click config snippet generators for Claude / Cursor / ChatGPT / Python, client key creation with quota controls, and interactive real-time Live Tester console with policy selector.
- Admin AI Models & High-Performance Settings: Fast, non-blocking model testing in `/api/ai/test` with bounded 10s per-call timeout, 12s hard deadline, 0 retries, and 5s concurrency limiter timeout (`limiter_timeout_seconds=5.0`), preventing dead or slow models from exhausting system-wide LLM concurrency slots. Instant, atomic settings updates via direct `PATCH /api/settings` response synchronization (10ms) without triggering heavy full-system reloads (`loadAll()`) or resetting uncommitted input fields, with active button state locks (`savingSection`) and client-side 12s `AbortController` timeouts on test requests.
- Light-Theme Admin Panel & Refined Layout: Unified light high-trust B2B theme across the entire admin panel (`admin.tenderlex.ru`), featuring crisp white sidebar navigation with emerald accents, normalized standard checkbox inputs, dense information architecture, and distraction-free workspace.
- Unified Admin Dashboard & Real-Time Analytics: Unified "Сводка" and "Статистика" into a high-density, responsive control center with 5-metric KPI row, 30-day dynamic launch chart, split 2-column breakdown for task modes/statuses and trial conversion funnel, and top active clients list. Displays instant live Yandex Search API balance in top header (`Поиск Яндекс: 401.69 ₽`).
- 7-Day Smart Error Window & 1-Click Resolution: Active error alerts are filtered to the last 7 days (`Job.created_at >= now - timedelta(days=7)`), and includes 1-click **«Отметить решёнными»** action in both the Attention Banner (`POST /api/jobs/resolve-failed`) and on individual failed job cards (`POST /api/jobs/{job_id}/resolve`), permanently resolving historical errors and keeping the status indicator in clean green ("Система работает штатно").
- Streamlined Admin Task Cards & Internal Task Numbering: Ultra-compact, single-level task item layout with micro-timeline stages in the card header, logical badge ordering (1. Function mode -> 2. Policy / run mode -> 3. AI provider & model -> 4. Found items count -> 5. Search API cost), left-aligned customer input file download pills with unclipped filenames and smooth tail ellipsis, and status-colored left border accents for noise-free visual separation. Features an administrator-only monotonic task numbering system (`#656`) with automatic DB trigger generation, search filter by task number, and dual UUID/number routing across all admin endpoints. Includes seamless expert admin re-run embedding: child re-runs are automatically deduplicated from top-level feed cards, embedding real-time progress bars, supplier counts, Yandex cost metrics, and download pills directly inside the parent customer task card.
- Multi-Tier Document Parser Resilience & Scanned DOCX/DOC Media OCR: Fault-tolerant extraction pipeline for uploaded customer specifications (`.docx`, `.xlsx`, `.pdf`, `.doc`, archives) with primary native readers, secondary headless `LibreOffice` text fallbacks, tertiary direct XML parsing (`word/document.xml`), and automated embedded raster image OCR (`word/media/*` via Tesseract `rus+eng` with LibreOffice PDF fallback and UTF-8 BOM sanitization) enabling seamless processing of scanned tables pasted into Word documents.
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
- Exact Product & Analogs Engine (100% Architecture & Code Parity with EmailAgent Rule 14):
  - Deep multi-source engineering pipeline ported 1-to-1 from EmailAgent (`detect_exact_products_deep`, `evidence_miner`, `matcher`, `deep`): zero product-specific regexes or hardcoded keywords, strictly generic AI prompts with Rule 14 procurement evidence mining.
  - Multi-tier matching workflow: Tier-0 procurement evidence mining -> characteristic-first candidate discovery -> multi-query Yandex search and targeted PDF passport downloads -> multi-source model fusion -> AI matrix parameter evaluation (`BUILD_EVALUATION_MATRIX_PROMPT`) -> grounded document verification (`_is_grounded_in_text`) -> standards resolution (GOST/TU/STO) -> anti-false-95% deterministic scoring.
  - Automatic candidate rotation (`auto_rotate_clean_analogs`) prioritizes conforming candidates with 0 mismatches over defective originals, preserving strict Form 2 comparison tables and generating verified Word (`.docx`) reports exclusively.
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

Production bot code changes require restarting only `tenderlex-bot.service`;
the durable queue worker and FastAPI backend do not need a restart for
Telegram routing-only changes.
If `scripts/deploy_tenderlex_live.sh` skips API/worker/bot restarts because
active jobs exist, wait for active pending/running jobs to finish and rerun the
deploy before reporting Telegram bot behavior as live.

Queue worker code or `AIPOISK_WORKER_CONCURRENCY` changes require restarting
only `tenderlex-worker.service`.

The admin panel runs with:

```bash
cd frontend
npm run dev
```

Default local frontend URL: `http://localhost:3091/`.
