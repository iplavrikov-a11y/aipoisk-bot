# AI Poisk Bot: Project Status

Date: 2026-06-05

## Current Production State

- Public URL: `https://aipoisk.lexelence.ru`.
- Backend service: `aipoisk-api.service`, FastAPI on `127.0.0.1:8088`.
- Telegram worker: `aipoisk-bot.service`.
- Durable job worker: `aipoisk-worker.service`.
- Frontend: static Vite build served by nginx from `frontend/dist`.
- Database: SQLite at runtime path from `.env`; the live DB is intentionally not stored in git.
- Runtime storage: `storage/`; uploaded files, generated reports, and job outputs are intentionally not stored in git.

Current runtime note:

- the queue is durable and DB-backed;
- one `aipoisk-worker` process is currently running, so large real bursts are
  queued safely but processed at single-worker throughput unless workers are
  scaled;
- live throughput also depends on external AI/search provider rate limits and
  document sizes.

## Commercial Access And Limits

Commercial limits are customer-level, not Telegram-account-level. One customer
can have several Telegram manager accounts; all linked accounts spend the same
customer limits.

There are exactly two commercial counters:

- supplier reports;
- procurement-document analyses.

Mode accounting:

- `Поиск поставщиков` spends supplier-report units;
- mass supplier search spends one supplier-report unit per independent ТЗ;
- `Анализ документации` spends one documentation-analysis unit;
- `Анализ + поставщики` spends one supplier-report unit and one
  documentation-analysis unit.

Free-period customers can be enabled from admin settings. Trial access has
separate supplier and documentation-analysis limits. Trial customers cannot use
mass supplier processing or `Анализ + поставщики`; they must run analysis and
supplier search separately.

## Admin Console

The admin UI is owner-facing and keeps technical details behind advanced
sections where possible.

Current admin capabilities:

- collapsed customer cards by default, so long customer notes and usage blocks
  do not make the customer list unscrollable;
- customer cards show linked Telegram accounts, access state, available balance,
  reserved units, spent units, manual grants, and collapsed billing history;
- the owner can create clients by Telegram username before the real Telegram ID
  is known, edit linked Telegram accounts, grant arbitrary units by function,
  and delete extra Telegram accounts;
- customer deletion is allowed only when the customer has no jobs. If there are
  no jobs, related billing rows are removed with the customer. If jobs exist,
  deletion is blocked to preserve report and billing history, and the owner
  should use `Отключить`;
- admin API errors are shown as readable Russian messages in the top alert
  instead of looking like a silent button failure;
- service/internal jobs are hidden by default in the jobs list;
- system status shows server disk/RAM/CPU, storage usage, queue counts, and
  configured API services without inventing balances;
- supplier-search settings show Yandex and Google as primary sources, with
  Tavily as an additional reserve source;
- AI model settings show exact `modelId` values in function selectors, while
  provider `id`, `Base URL`, `API key`, and model rows live in the advanced
  provider section.

AI provider defaults currently used by the admin UI:

- `openrouter`: `https://openrouter.ai/api/v1`;
- `open-ai`: local OpenAI-compatible CLIProxyAPI endpoint from settings;
- `gemini`: Gemini proxy endpoint from settings;
- `polza`: `https://api.polza.ai/v1`.

OpenRouter and Polza Base URLs are configured in the live settings, but their
API keys are not present in saved settings. Existing OpenAI-compatible and
Gemini keys are preserved.

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

Telegram supplier input contract:

- `Поставщики по одному ТЗ` creates one supplier-search job from one ТЗ/ООЗ
  file or one plain text technical assignment / object description message and
  returns one XLSX;
- `Поставщики по нескольким ТЗ` is a mass-processing mode, not a multi-document
  context mode;
- each uploaded ТЗ/ООЗ file or accepted plain text ТЗ message in
  mass-processing mode creates its own independent supplier-search job with
  exactly that one input as context;
- each independent job extracts its own procurement profile, generates its own
  AI search queries, verifies suppliers independently, and returns its own XLSX;
- unrelated ТЗ files must never be concatenated into one supplier-search
  context, because that causes dominant items to hide other procurements.
- Telegram uploads in this mode are serialized per chat and retried on file
  download timeout, so large multi-file sends do not silently drop documents.
- after processing starts, the bot removes the `Запустить обработку` /
  `Очистить документы` keyboard until the batch finishes, preventing duplicate
  launches and making the active state clear to the customer.

## Procurement Source Links

Documentation-analysis jobs can use uploaded files, procurement source links,
or both. A source link is not limited to EIS: it can be `zakupki.gov.ru`, a
223-ФЗ platform, a commercial ETP, or a customer's published procurement page.

Plain supplier-search scenarios are different: the customer sends a technical
assignment / object description file, not a procurement link. Links are exposed
in Telegram only for `Анализ документации` and `Анализ + поставщики`.

Source-link contract:

- Telegram and admin upload flows accept source URLs together with files or as
  the only input for documentation-analysis scenarios;
- Telegram extracts procurement links from plain text messages and from file
  captions in documentation-analysis scenarios;
- plain supplier search rejects source URLs and asks for a ТЗ/ООЗ file;
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
- if the AI draft conflicts with official card facts, the system asks AI to
  repair the report and validates the repaired report again;
- if validation still finds issues after repair, the report should carry a
  concise quality warning/evidence note and the owner should be alerted, while
  engineering work focuses on fixing the root cause in prompts, validators,
  model routing, or parsers.

## Minpromtorg And GISP Registry Handling

Minpromtorg/GISP registry logic is AI-gated and applies only when the
procurement documents actually require a registry extract, registry record, or
delivery of goods from the Russian industrial products registry.

Registry contract:

- AI decides whether the requirement is mandatory, not applied, only a
  preference, or ambiguous;
- registry search is skipped when AI finds no mandatory requirement;
- when mandatory, AI generates registry-oriented queries for the procurement
  item and the worker searches GISP/Minpromtorg context;
- supplier AI verification receives registry context and must not claim the
  requirement is fulfilled without a supplier/manufacturer linkage;
- dealers and distributors may still be accepted as procurement leads, but the
  customer-facing comment must say to request registry confirmation when direct
  linkage is absent.

## Reports And Audit Fields

XLSX supplier reports include:

Visible customer-facing columns only:

- company name;
- website;
- phones;
- email;
- short comment.

Stored supplier rows also preserve `match_level`, `source`, `search_query`,
`quality_score`, `quality_tier`, `procurement_item`, `ai_confidence`,
`site_type`, `product_fit`, evidence snippets, and AI rerank metadata, so
admin/API views and `evidence.json` can explain why a supplier was accepted
without polluting the customer's XLSX report.

## Job Execution And UX

- API and Telegram bot only create durable DB-backed pending jobs.
- `aipoisk-worker.service` claims pending/stale jobs and performs processing.
- Telegram has four customer-facing scenarios: suppliers for one ТЗ, suppliers for several ТЗ, documentation analysis, and analysis plus suppliers.
- Single-ТЗ supplier search starts after one uploaded ТЗ/ООЗ file;
  it can also start from one plain text ТЗ/ООЗ message.
- Multi-ТЗ supplier search collects several ТЗ/ООЗ files and/or accepted plain
  text ТЗ messages; the user starts or clears that set explicitly.
- Documentation-analysis scenarios can collect files, archives, and/or a
  procurement source link before the user starts processing.
- `Анализ + поставщики` first uses the full documentation/source context for
  the DOCX analysis, then uses a separate AI step to extract the ТЗ/ООЗ/product
  specification context for supplier search. Supplier discovery does not search
  against the noisy full documentation bundle.
- Telegram bot edits a live progress message while the job runs: queue, AI analysis
  of the technical assignment, query generation, website search, AI candidate
  filtering, site/contact verification, and completion.
- Admin UI includes supplier quality monitoring and per-job evidence viewing.
- Admin API exposes `/api/ops/supplier-quality` and `/api/jobs/{job_id}/evidence`.
- Telegram routing-only code changes require restarting `aipoisk-bot.service`.
  The API and durable worker can keep running unless their code or settings
  contracts changed.

## Verification Snapshot

Latest task evidence: `.agent/tasks/2026-06-04-billing-telegram-ux/`.

Fresh checks from the latest Telegram text-ТЗ pass:

- Backend tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest
  backend/tests` -> `172 passed`, `2` warnings, `42` subtests passed.
- Targeted Telegram tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend
  pytest backend/tests/test_bot_progress.py -q` -> `27 passed`.
- Production `aipoisk-bot.service` restarted after routing change and returned
  `active/running` with start time `2026-06-05 12:50:58 UTC`.

Earlier billing, Telegram, and admin-button pass:

- Backend tests: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest
  backend/tests` -> `169 passed`, `2` warnings.
- Frontend production build: `cd frontend && npm run build` -> OK.
- Live admin Playwright button check on `https://aipoisk.lexelence.ru`:
  `32` checks passed, `0` failed API responses, `0` console errors, `0` page
  errors.
- Live admin button coverage included login, navigation, client create/open,
  client disable/enable, Telegram account add/save/delete, manual grant, delete
  new temporary client, confirm old `Тестовый клиент` is absent, job evidence,
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
- Playwright focused AI model check -> function dropdowns show exact `modelId`;
  OpenRouter, OpenAI, Gemini, and Polza provider rows are present; desktop and
  mobile have no horizontal overflow.
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
- AI-gated Minpromtorg/GISP registry handling is covered by supplier discovery
  flow tests and evidence payloads.
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
- Latest reprocessed failed supplier job `06532a2fc4f9442cbf6085e638720693`
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

Detailed task evidence for the latest admin UI / limits / provider-settings pass
is stored under `.agent/tasks/2026-06-03-admin-ui-10/`.

## Safe GitHub Rules

Do not commit:

- `.env` or any real secret file;
- SQLite databases and DB backups;
- `storage/` job outputs and uploaded procurement documents;
- virtual environments;
- `node_modules/`;
- frontend build output;
- runtime logs from `.omx/`.

Commit only source code, tests, deploy templates, `.env.example`, README/docs, and non-secret task evidence.

## Remaining Risks

The main architectural gaps addressed in this pass are implemented. Residual
risks are narrower:

- DB-backed queue handled the safe 1000-job simulation without duplicate
  claims, but the current live deployment still has one worker process.
  Production bursts need worker scaling and external AI/search rate-limit
  planning.
- Browser rendering improves contact extraction, but anti-bot sites and unusual
  SPA flows can still require more specialized handling.
- Procurement source pages can also be blocked by anti-bot controls; the system
  records source parse status and continues with uploaded documents when present.
- The multi-domain eval suite is in place; it should be expanded with more real
  procurement categories as new customer documents appear.
- Monitoring is available in API/UI, but there is no external alert delivery
  channel yet.
