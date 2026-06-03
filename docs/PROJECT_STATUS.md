# AI Poisk Bot: Project Status

Date: 2026-06-02

## Current Production State

- Public URL: `https://aipoisk.lexelence.ru`.
- Backend service: `aipoisk-api.service`, FastAPI on `127.0.0.1:8088`.
- Telegram worker: `aipoisk-bot.service`.
- Durable job worker: `aipoisk-worker.service`.
- Frontend: static Vite build served by nginx from `frontend/dist`.
- Database: SQLite at runtime path from `.env`; the live DB is intentionally not stored in git.
- Runtime storage: `storage/`; uploaded files, generated reports, and job outputs are intentionally not stored in git.

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

Mass supplier search contract:

- `Поставщики по одному ТЗ` creates one supplier-search job from one ТЗ/ООЗ
  file and returns one XLSX;
- `Поставщики по нескольким ТЗ` is a mass-processing mode, not a multi-document
  context mode;
- each uploaded ТЗ/ООЗ file in mass-processing mode creates its own independent
  supplier-search job with exactly that one file as context;
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

Documentation analysis is AI-required. The system must not generate a
customer DOCX report when the AI provider is missing, report generation fails,
or AI verification rejects the report without a corrected version.

Hard contract:

- source pages and uploaded documents are context for AI, not a replacement for
  AI analysis;
- no deterministic fallback report is issued to the customer when AI is
  unavailable;
- official procurement card fields are treated as authoritative facts before
  the DOCX is released;
- for EIS and other official source pages, the report must preserve literal
  card values for procurement method, submission deadline, results date, НМЦК,
  customer, ИНН/КПП, platform, and legal regime when present;
- the report must not normalize `Иной способ` into another procedure and must
  not add time to a results date when the official source contains only a date;
- if the AI draft conflicts with official card facts, the system asks AI to
  repair the report and validates the repaired report again;
- if official-card validation still fails after AI repair, the job fails
  honestly instead of publishing a misleading DOCX.

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
  multi-ТЗ supplier search collects several ТЗ/ООЗ files and the user starts
  or clears that set explicitly.
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

## Verification Snapshot

Latest verified customer UX smoke job:

- Job ID: `d345a5ca994c4c4cb3c227bbf30e2f96`.
- Created only through `create_job`; no inline `process_job` call.
- Queue before create: `0` pending/running jobs.
- Result: `completed`, `1/1`.
- Worker progress events: `0`, `28`, `42`, `50`, `66`, `74`, `100`.
- Progress stages include AI ТЗ analysis, query generation, website search, AI
  candidate filtering, and site verification.
- Result XLSX exists.
- XLSX sheet title: `Поставщики`.
- Visible XLSX headers: `Компания`, `Сайт`, `Телефоны`, `Email`, `Комментарий`.
- English/technical headers such as `Search Query`, `Evidence snippet`,
  `Product fit`, `Contact URL`, and `AI уверенность` are not present.

Fresh checks from the latest AI-required architecture pass:

- Backend tests: `PYTHONPATH=backend pytest backend/tests -q` -> `88 passed`,
  `26` subtests passed.
- Targeted source/API/bot/report/supplier tests:
  `44 passed`, `26` subtests passed.
- Python compile check on changed backend modules: OK.
- Frontend production build: OK.
- venv dependency check: `No broken requirements found`.
- `git diff --check`: OK.
- Task verdict JSON syntax: OK.
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

Detailed task evidence is stored under `.agent/tasks/aipoisk-commercial-10/`.

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

- DB-backed queue is durable for the current single-worker deployment, but a
  Redis/Postgres locked queue would be stronger for multiple concurrent workers.
- Browser rendering improves contact extraction, but anti-bot sites and unusual
  SPA flows can still require more specialized handling.
- Procurement source pages can also be blocked by anti-bot controls; the system
  records source parse status and continues with uploaded documents when present.
- The multi-domain eval suite is in place; it should be expanded with more real
  procurement categories as new customer documents appear.
- Monitoring is available in API/UI, but there is no external alert delivery
  channel yet.
