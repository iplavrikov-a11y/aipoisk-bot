# Evidence

Date: 2026-06-02

## Target

Commercial hardening pass after the Yandex/Google search-stack fix.

## Code Changes

- `backend/app/supplier_search.py`
  - Supplier discovery now reviews ranked candidates in bounded batches.
  - Processing stops early once the requested number of verified suppliers is reached.
  - Evidence now records `review.batch_size`, `review.reviewed_count`,
    `review.candidate_count`, `review.stopped_after_candidates`, and
    `review.early_stop`.
- `backend/app/report_builder.py`
  - XLSX supplier report now includes match quality, search source, search query,
    contact URL, and evidence URL.
  - Internal match-level codes are rendered as Russian client-facing labels.
- `backend/app/main.py`
  - Empty manual jobs are rejected before DB job creation.
  - Empty upload file lists are rejected before DB access.
  - Startup recovers pending and stale running jobs.
  - Supplier API serialization now includes search audit fields:
    `match_level`, `source`, and `search_query`.
- `backend/app/jobs.py`
  - Added stale running job detection and recovery for interrupted in-process jobs.
- `backend/app/db.py` and `backend/app/models.py`
  - Added backward-compatible SQLite schema columns for supplier search audit:
    `match_level`, `source`, and `search_query`.

## Fresh Verification

- `cd backend && ./.venv/bin/python -m unittest discover -s tests -v`
  - Result: 13 tests, OK.
- `cd backend && ./.venv/bin/python -m compileall app`
  - Result: exit 0.
- Real job reprocess:
  - Job: `c01e10dd5ac64de4a9e1c0b827a668a8`
  - Result: `completed`, `15/15`, error empty.
  - Evidence review: `batch_size=30`, `reviewed_count=27`,
    `candidate_count=75`, `stopped_after_candidates=30`, `early_stop=true`.
  - Provider order: `yandex`, `google`, `tavily`, `ddgs`.
  - Provider reports: Yandex `ok` 57 returned, Google `ok` 24 returned,
    Tavily `empty`, DDGS `ok` 101 returned.
  - XLSX checked with openpyxl: new headers present, first match level is
    `точное совпадение`, first source is `yandex`.
- DB/API audit verification:
  - `init_db()` added live SQLite columns `match_level`, `source`, and
    `search_query` to `supplier_results`.
  - Reprocessed job `c01e10dd5ac64de4a9e1c0b827a668a8` after migration:
    `completed`, `15/15`, error empty.
  - First stored supplier has `match_level=exact`, `source=yandex`, and a
    non-empty `search_query`.
  - `job_to_dict(job, include_files=True)` includes all three supplier audit
    keys.
- Services:
  - Restarted `aipoisk-api.service` and `aipoisk-bot.service` after code and
    DB migration changes.
  - `systemctl is-active aipoisk-api.service aipoisk-bot.service nginx`:
    all `active`.
  - `curl https://aipoisk.lexelence.ru/api/health`: HTTP 200,
    `{"ok":true,"domain":"https://aipoisk.lexelence.ru","logistics_enabled":false}`.
  - Fresh `journalctl` scan for `traceback|error|exception|failed|critical`:
    no matches for API or bot after restart.

## Notes

- A first external health check immediately after restart returned transient
  HTTP 502 while the upstream was coming up. Recheck returned HTTP 200 and
  local `127.0.0.1:8088/api/health` was healthy.
- Tavily remains quota-limited/unreliable for this project, but it is no longer
  a blocking dependency because Yandex, Google, and DDGS are active web sources.

## Remaining Commercial Risks

- Queue execution is still in-process. Startup recovery now reduces stuck-job
  risk, but a durable external queue would still be stronger under high load.
- Browser-rendered/JS-heavy supplier sites may still hide contacts from the
  current HTTP/BeautifulSoup extractor.
- The quality gate has one real procurement job plus unit coverage. A broader
  multi-domain evaluation set is still needed before calling the system truly
  production-perfect.

## AI-First Supplier Search Follow-Up

Date: 2026-06-02

### Code Changes

- `backend/app/supplier_search.py`
  - Supplier discovery now fails immediately without an active AI provider.
  - AI extracts a procurement profile before search.
  - AI generates supplier search queries from that profile.
  - AI reranks search candidates before page collection.
  - Final verified rows require AI audit acceptance, supplier site type,
    product fit, confidence, evidence snippet, and contact snippet.
  - Deterministic matching remains only a local signal/prefilter and cannot
    override an AI rejection.
  - Fixed AI confidence normalization so both `0..1` and `0..100` scales are
    interpreted correctly.
- `backend/app/report_builder.py`
  - XLSX now includes quality score/tier plus AI audit fields.
- `docs/PROJECT_STATUS.md`
  - Updated the supplier-search architecture contract and latest live evidence.
- `backend/app/jobs.py`
  - Failed jobs now persist a diagnostic `evidence.json` even when the AI-first
    supplier pipeline fails before returning normal search evidence.
- `backend/app/main.py`
  - Admin API can read job evidence through `/api/jobs/{job_id}/evidence`.
  - Evidence reads are guarded to runtime storage paths.
  - Admin API can inspect supplier job quality through
    `/api/ops/supplier-quality`.

### Fresh Verification

- `cd backend && .venv/bin/python -m unittest tests/test_supplier_discovery_flow.py`
  - Result: 8 tests OK.
- `cd backend && .venv/bin/python -m unittest tests/test_supplier_search_sources.py`
  - Result: 31 tests OK.
- `cd backend && .venv/bin/python -m unittest discover -s tests`
  - Result: 48 tests OK.
- `cd backend && .venv/bin/python -m compileall app tests`
  - Result: exit 0.
- `git diff --check`
  - Result: exit 0.
- Live AI-required smoke on real uploaded DOCX:
  - Job: `589e8dc52d394bd4b05c1cd8ccfd5ec6`
  - Result: `completed`, `2/2`, error empty.
  - AI profile extraction: present.
  - AI candidate rerank: `input_count=60`, `sent_to_ai=36`, `kept_count=10`.
  - Final rows: both include AI confidence, site type, product fit, evidence
    snippet, and contact snippet.
- Failure-evidence integration smoke:
  - Job: `db09fd8b509642ddba7a983f919452c1`
  - Result: `failed`, `result_path=""`.
  - Evidence path exists.
  - Evidence includes `ai_required=true`, `report_generated=false`, and
    `xlsx_generated=false`.
- Supplier quality monitoring snapshot on live DB:
  - Window: 20 recent supplier jobs.
  - Status counts: `completed=17`, `failed=2`, `partial=1`.
  - Provider statuses: Yandex `ok=18`, DDGS `ok=18`, Google `empty=18`,
    Tavily `empty=18`.
  - AI-required failures: `1`.
- Services after restart:
  - `aipoisk-api.service`: active.
  - `aipoisk-bot.service`: active.
  - `curl http://127.0.0.1:8088/api/health`: `{"ok":true,...}`.

### Runtime Defect Found And Fixed

- First live smoke job `430a18f73d79463ea3d7754012f530cb` failed before report
  generation because the AI reranker returned confidence values such as `0.98`
  and code interpreted them as `0`.
- The confidence parser now normalizes fractional AI confidence values to
  percentages before threshold checks.

## Final Systemic Architecture Pass

Date: 2026-06-02

### Code Changes

- `backend/app/jobs.py`, `backend/app/worker.py`,
  `deploy/systemd/aipoisk-worker.service`
  - API and bot now persist pending jobs only.
  - A dedicated durable worker service claims pending or stale running jobs from
    the DB and processes them.
  - Bot waits for terminal DB status instead of calling `process_job()` inline.
- `backend/app/db.py`, `backend/app/models.py`, `backend/app/main.py`
  - Live DB migration and API serialization now persist supplier AI audit
    fields: quality score/tier, procurement item, AI confidence, site type,
    product fit, evidence snippets, and AI rerank metadata.
- `backend/app/supplier_search.py`
  - Browser-rendered page extraction is used when HTTP extraction has no
    contacts.
  - Successful supplier evidence now explicitly records `ai_required=true`,
    `ai_used=true`, required AI stages, and the AI-only acceptance policy.
- `frontend/src/App.tsx`, `frontend/src/styles.css`
  - Admin UI has a supplier quality view and per-job evidence viewer.
- `backend/app/bot.py`
  - Telegram uploads now accumulate into explicit batches with run/clear
    controls.
- `backend/tests/fixtures/supplier_eval_cases.json`,
  `backend/tests/test_supplier_eval_suite.py`
  - Added a multi-domain eval suite for generic, non-sample-specific supplier
    behavior.

### Fresh Verification

- `cd backend && .venv/bin/python -m unittest discover -s tests`
  - Result: 52 tests OK.
- `cd backend && .venv/bin/python -m compileall app tests`
  - Result: exit 0.
- `cd frontend && npm run build`
  - Result: exit 0, Vite production build completed.
- `git diff --check`
  - Result: exit 0.
- `python3 -m json.tool .agent/tasks/aipoisk-commercial-10/verdict.json`
  - Result: exit 0.
- Live DB migration check:
  - All new supplier audit columns are present in live SQLite.
- Browser-rendered extraction smoke:
  - Rendered content produced both email and phone extraction.
- Live durable worker smoke before final evidence-contract patch:
  - Job: `2478e367b9e34b5f9cda7e7e4ec3850f`.
  - Queue before create: `0` pending/running.
  - Created via `create_job()` only; no inline `process_job()` call.
  - Result: `completed`, `1/1`.
  - Result XLSX exists and evidence exists.
  - Stored supplier row has AI audit fields.
- Services after restart:
  - `aipoisk-api.service`: active.
  - `aipoisk-bot.service`: active.
  - `aipoisk-worker.service`: active.
  - `curl http://127.0.0.1:8088/api/health`:
    `{"ok":true,"domain":"https://aipoisk.lexelence.ru","logistics_enabled":false}`.
- Live durable worker smoke after final evidence-contract patch:
  - Job: `fbde159fd4be40538e8c07978221bcf9`.
  - Queue before create: `0` pending/running.
  - Created via `create_job()` only; no inline `process_job()` call.
  - Result: `completed`, `1/1`.
  - Result XLSX exists and evidence exists.
  - Evidence includes `ai_required=true`, `ai_used=true`.
  - Evidence required stages:
    `supplier_procurement_profile`, `supplier_query_generation`,
    `supplier_candidate_reranker`, `supplier_candidate_verifier`.
  - First stored supplier: quality score `100`, tier `high`, AI confidence
    `100`, site type `supplier`, product fit `exact`, AI rank confidence `95`.
- Live admin HTTP checks:
  - `/api/ops/supplier-quality`: HTTP 200, window size `47`, status counts
    `completed=44`, `failed=2`, `partial=1`, provider status counts present.
  - `/api/jobs/fbde159fd4be40538e8c07978221bcf9/evidence`: HTTP 200,
    `ai_required=true`, `ai_used=true`, accepted count `1`, required AI stages
    present.

### Remaining Risks

- DB-backed worker queue is durable for the current single-worker deployment,
  but Redis/Postgres row locking would be stronger for multi-worker concurrency.
- Browser rendering improves JS-heavy contact extraction but cannot guarantee
  anti-bot or unusual SPA pages.
- Eval coverage is now multi-domain and generic; it should be expanded with
  more real categories as future customer documents appear.
- Monitoring is available in API/UI, but external alert delivery is not wired.

## Customer UX Follow-Up

Date: 2026-06-02

### Code Changes

- `backend/app/jobs.py`
  - Worker now writes user-facing progress messages at supplier-search stages:
    document extraction, AI procurement profile, AI query generation, website
    search, AI rerank/filtering, site/contact verification, and result writing.
  - The queue claim message no longer exposes internal worker host/PID details.
- `backend/app/supplier_search.py`
  - Supplier discovery accepts a progress callback and emits stage updates.
- `backend/app/bot.py`
  - After "Запустить пачку", the bot sends and edits a live status message with
    status, progress bar, current stage, elapsed time, and rough ETA.
  - `/status` now uses Russian user-facing status labels.
- `backend/app/report_builder.py`
  - Customer XLSX now has a minimal visible first sheet named `Поставщики`.
  - Visible headers are only `Компания`, `Сайт`, `Телефоны`, `Email`,
    `Комментарий`.
  - Search queries, AI/audit fields, snippets, and evidence/contact URLs remain
    in DB/evidence/admin surfaces, not in the customer's spreadsheet.
- `backend/tests/test_bot_progress.py`, `backend/tests/test_report_builder.py`
  - Added regression coverage for Telegram progress formatting and the
    customer-facing XLSX contract.

### Fresh Verification

- `cd backend && .venv/bin/python -m unittest discover -s tests`
  - Result: 55 tests OK.
- `cd backend && .venv/bin/python -m compileall app tests`
  - Result: exit 0.
- `cd frontend && npm run build`
  - Result: exit 0, Vite production build completed.
- `git diff --check`
  - Result: exit 0.
- Services after restart:
  - `aipoisk-api.service`: active.
  - `aipoisk-bot.service`: active.
  - `aipoisk-worker.service`: active.
  - `curl http://127.0.0.1:8088/api/health`:
    `{"ok":true,"domain":"https://aipoisk.lexelence.ru","logistics_enabled":false}`.
- Live customer UX smoke:
  - Job: `d345a5ca994c4c4cb3c227bbf30e2f96`.
  - Queue before create: `0` pending/running.
  - Created via `create_job()` only; no inline `process_job()` call.
  - Result: `completed`, `1/1`.
  - Progress events: `0`, `28`, `42`, `50`, `66`, `74`, `100`.
  - Progress stages include AI ТЗ analysis, query generation, website search,
    AI filtering, and site verification.
  - Result XLSX exists.
  - XLSX sheet title: `Поставщики`.
  - XLSX headers: `Компания`, `Сайт`, `Телефоны`, `Email`, `Комментарий`.
  - English/technical noise headers are absent.

## Telegram Customer Copy Follow-Up

Date: 2026-06-02

### Code Changes

- `backend/app/bot.py`
  - Progress card no longer shows job id, internal mode, raw status labels, or
    technical exceptions.
  - Progress bar uses visual blocks and short customer-facing stage text.
  - Failed jobs explain that the service stopped to avoid sending an
    unverified supplier list.
  - Duplicate status messages from Telegram `message is not modified` are no
    longer sent as fallback messages.
  - After completion the bot sends the file with a concise caption instead of
    repeating the raw DB message.
  - "Последние задачи" now shows user-facing entries without task ids.
- `backend/app/supplier_search.py`
  - Worker progress stage texts are customer-friendly.
  - AI candidate reranking retries once before failing.
  - Empty low-level exceptions are recorded with their exception type, so
    internal diagnostics no longer produce empty `AI candidate reranking failed:`.

### Error Diagnosis

- User-facing failed job: `ef651f2bc99a4fb4b35ffd465a57c93b`.
- The job reached supplier search and failed during candidate reranking, before
  site/contact verification.
- Stored error before this fix: `AI candidate reranking failed:`.
- Root cause from available evidence: the AI reranker call failed with an empty
  low-level exception message; the old wrapper hid the exception type, so the
  precise low-level class was not preserved.
- Systemic fix: reranker now retries once and records a non-empty diagnostic
  with exception type, while Telegram shows only a friendly explanation.

### Fresh Verification

- `cd backend && .venv/bin/python -m unittest discover -s tests`
  - Result: 57 tests OK.
- `cd backend && .venv/bin/python -m compileall app tests`
  - Result: exit 0.
- `cd frontend && npm run build`
  - Result: exit 0.
- `git diff --check`
  - Result: exit 0.
- Services after restart:
  - `aipoisk-api.service`: active.
  - `aipoisk-bot.service`: active.
  - `aipoisk-worker.service`: active.
  - `curl http://127.0.0.1:8088/api/health`:
    `{"ok":true,"domain":"https://aipoisk.lexelence.ru","logistics_enabled":false}`.
- Rendered running status sample:
  - Header: `🔎 Ищу поставщиков`.
  - Shows visual progress blocks, short current stage, elapsed time, and rough
    estimate.
  - Does not show task id or internal mode.
- Rendered failed status sample:
  - Header: `⚠️ Не удалось подготовить файл`.
  - Explains that an unverified supplier list is not sent.
  - Does not expose `AI candidate reranking`, `TimeoutError`, or other raw
    technical exception text to the customer.
- Live friendly progress smoke after service restart:
  - Job: `c7be76833eee427abc27f8520b9b54be`.
  - Result: `completed`, `1/1`.
  - Progress values: `0`, `28`, `42`, `50`, `60`, `66`, `74`, `100`.
  - Stage messages are customer-facing and do not contain `AI candidate`,
    `rerank`, or raw technical stage names.
  - Formatted Telegram status contains no job id and no `Режим:`.
  - Result XLSX headers are exactly `Компания`, `Сайт`, `Телефоны`, `Email`,
    `Комментарий`.

## Customer Report Naming And Telegram Scenarios Follow-Up

Date: 2026-06-02

### Code Changes

- `backend/app/report_builder.py`
  - Supplier XLSX first-row heading now includes the source ТЗ title and the
    AI-extracted procurement subject when available.
  - Customer comments are generated from `product_fit` as short action-oriented
    notes: exact item, possible analog, profile category, or profile supplier.
- `backend/app/jobs.py`
  - Supplier result filenames now include the source title and short
    procurement subject extracted from the AI procurement profile.
  - Added combined `analysis_and_suppliers` mode that creates documentation
    analysis plus supplier XLSX and stores both output paths in evidence.
- `backend/app/bot.py`
  - Telegram menu now separates: suppliers for one ТЗ, suppliers for several
    ТЗ, documentation analysis, and analysis plus suppliers.
  - Single-ТЗ supplier search starts immediately after one uploaded ТЗ.
  - Multi-document scenarios use customer-facing "document set" wording
    instead of "batch".
- `frontend/src/App.tsx`
  - Admin UI labels now use "analysis" / "document set" terminology and support
    combined-result downloads.

### Fresh Verification

- `cd backend && .venv/bin/python -m unittest discover -s tests`
  - Result: 66 tests OK.
- `cd backend && .venv/bin/python -m compileall app tests`
  - Result: exit 0.
- `cd frontend && npm run build`
  - Result: exit 0.
- `git diff --check`
  - Result: exit 0.
- Services after restart:
  - `aipoisk-api.service`: active.
  - `aipoisk-bot.service`: active.
  - `aipoisk-worker.service`: active.
- Current inspected customer job:
  - Job: `d90df15a4cbd4cdcb458146470a4b700`.
  - Status: `completed`, suppliers `15/15`.
  - New result filename:
    `Техническое_задание_17163454-1 - Средство для очистки поверхностей кислотный концентрат_d90df15a.xlsx`.
  - XLSX title:
    `Отчёт по ТЗ: Техническое_задание_17163454-1 - Средство для очистки поверхностей (кислотный концентрат)`.
  - XLSX headers remain exactly `Компания`, `Сайт`, `Телефоны`, `Email`,
    `Комментарий`.
  - Sample comments are short:
    `Точный товар: Битумаз-К - концентрированный кислотный очиститель промышленных загрязнений (20 л). Контакты найдены на сайте.`
    and
    `Возможный аналог: Кислотное средство очиститель бетона Неолайт-38. Уточните характеристики по ТЗ.`

## AI Query Generation Robustness Follow-Up

Date: 2026-06-02

### Error Diagnosis

- User-facing failed job: `06532a2fc4f9442cbf6085e638720693`.
- Uploaded file: `Техническое_задание_17127845-1.pdf`.
- PDF extraction succeeded: parsed text length was `16336` characters.
- AI procurement profile extraction succeeded:
  `Поставка многослойных сотовых поликарбонатных панелей и соединительных поликарбонатных профилей`.
- The failure happened at AI supplier query generation, before web search:
  `AI supplier query generation failed:`.
- Direct rerun of the same AI query-generation stage succeeded and produced 12
  procurement-specific search queries.
- Root cause: transient AI call failure or timeout during
  `supplier_query_generation`; the previous code had no retry for that AI
  stage and preserved an empty low-level diagnostic.

### Code Changes

- `backend/app/supplier_search.py`
  - AI supplier query generation now retries once with a longer timeout.
  - Empty low-level failures now preserve the exception type in diagnostics,
    for example `TimeoutError`.
  - AI contact placeholders such as `не найдено на главной` are not accepted as
    phone/email values.
  - When AI confirms a supplier but gives placeholder contacts, the pipeline
    uses extracted site contacts if they exist; otherwise the candidate is
    downgraded or rejected instead of polluting the customer XLSX.
- `backend/app/bot.py`
  - Telegram maps supplier query-generation failures to a concise customer
    reason and still hides raw technical exception text.

### Fresh Verification

- `cd backend && .venv/bin/python -m unittest tests/test_supplier_discovery_flow.py`
  - Result: 16 tests OK.
- `cd backend && .venv/bin/python -m unittest tests/test_bot_progress.py`
  - Result: 7 tests OK.
- `cd backend && .venv/bin/python -m unittest discover -s tests`
  - Result: 71 tests OK.
- `cd backend && .venv/bin/python -m compileall app tests`
  - Result: exit 0.
- `git diff --check`
  - Result: exit 0.
- Services after restart:
  - `aipoisk-api.service`: active.
  - `aipoisk-bot.service`: active.
  - `aipoisk-worker.service`: active.
  - Local health endpoint: HTTP 200.
- Reprocessed failed job:
  - Job: `06532a2fc4f9442cbf6085e638720693`.
  - Result: `partial`, suppliers `13/15`.
  - The DB `result_path` points to the fresh XLSX below.
  - Result file:
    `Техническое_задание_17127845-1 - Панель поликарбонатная сотовая и Профиль полимерный соединительный_06532a2f.xlsx`.
  - Evidence confirms `ai_required=true` and `ai_used=true`.
  - AI candidate rerank status: `ok`, input `75`, kept `15`.
  - AI candidate review: reviewed `15`, accepted `13`.
  - XLSX sheet: `Поставщики`.
  - XLSX visible headers: `Компания`, `Сайт`, `Телефоны`, `Email`,
    `Комментарий`.
  - Invalid AI contact placeholders are absent from the XLSX.

## Nomenclature-Breadth Supplier Search Follow-Up

Date: 2026-06-02

### Error Diagnosis

- User-facing supplier job: `4698abb96da14235b6e4b578799340b2`.
- Uploaded/source title: `Описание_объекта_закупки_Поставка_каната_стального`.
- Old result: `partial`, suppliers `8/15`.
- Root cause:
  - AI query generation over-focused on exact characteristics:
    `ЛК-РО`, `31 мм`, `ГОСТ 7668-80`, `разрывная нагрузка 517 кН`.
  - The search layer still found `88` candidate domains.
  - Local rank cutoff sent `75` candidates to AI rerank.
  - AI rerank kept only `9` candidates, so final AI verification had no
    realistic chance to fill `15` supplier rows.
- Architectural issue: for ordinary закупочный supplier discovery, the system
  must search the товарная группа / номенклатура and relevant manufacturers,
  dealers, distributors, and B2B suppliers, not only the exact line item.

### Code Changes

- `backend/app/supplier_search.py`
  - Procurement profile now stores broad `category_terms` and exact
    `exact_terms` separately.
  - AI query generation prompt now requires a mixed search strategy:
    broad category/nomenclature queries plus exact-characteristic queries.
  - If generated queries are too narrow for a target supplier count, the system
    asks AI to revise the query set instead of silently running an over-narrow
    search.
  - AI rerank is now a broad review-pool builder, not a hard bottleneck: if the
    initial AI shortlist is too small, a second AI expansion pass selects more
    category/profile supplier sites for final AI verification.
  - Phone extraction now normalizes Russian phone numbers and rejects broken
    numbers such as `8000\n1190000` instead of writing raw contact garbage to
    the customer XLSX.
- `backend/tests/test_supplier_discovery_flow.py`
  - Added regression tests for broad-category query revision, expanded AI
    rerank pools, and phone normalization.

### Fresh Verification

- `cd backend && .venv/bin/python -m unittest tests/test_supplier_discovery_flow.py`
  - Result: 19 tests OK.
- `cd backend && .venv/bin/python -m unittest tests/test_supplier_discovery_flow.py tests/test_supplier_search_sources.py tests/test_supplier_eval_suite.py`
  - Result: 51 tests OK.
- `cd backend && .venv/bin/python -m unittest discover -s tests`
  - Result: 73 tests OK.
- `cd backend && .venv/bin/python -m compileall app tests`
  - Result: exit 0.
- Reprocessed the same steel-rope job after the broad-search fix:
  - Job: `4698abb96da14235b6e4b578799340b2`.
  - Initial result after broad-search fix: `completed`, suppliers `15/15`.
  - Result file:
    `Описание_объекта_закупки_Поставка_каната_стального - Канат стальной_4698abb9.xlsx`.
  - AI-generated query count: `20`.
  - Search candidates: Yandex added `100`, DDGS added `50`, total after DDGS
    `150`.
  - AI rerank: input `75`, desired review count `75`, initial kept `36`,
    expanded kept `19`, final kept `55`.
  - AI review: reviewed `26`, candidate pool `55`, stopped after `30`,
    early_stop `true`.
  - XLSX visible headers: `Компания`, `Сайт`, `Телефоны`, `Email`,
    `Комментарий`.
  - XLSX row count: `15`.
  - Contact placeholder and phone-format checks: no bad contacts found.
  - Rows are marked honestly by fit in evidence: exact, analog, and category;
    non-exact rows do not claim full compliance.

### Minimum Target Follow-Up

- The configured supplier target is now treated as the minimum, not a hard cap.
- The worker still stops early after the minimum is reached, so it does not run
  extra paid search/AI batches just to overfill the report.
- If the already-paid AI verification batch confirms extra suppliers, those
  extra rows remain in the customer XLSX.
- Reprocessed steel-rope job after the minimum-target fix:
  - Job: `4698abb96da14235b6e4b578799340b2`.
  - Result: `completed`, suppliers `19/15`.
  - Job message:
    `Готово: найдено и проверено 19, минимум по настройкам 15`.
  - XLSX summary:
    `Найдено и проверено: 19. Минимум по настройкам: 15.`
  - XLSX row count: `19`.
  - AI query count: `21`.
  - AI rerank: input `75`, desired review count `75`, initial kept `39`,
    expanded kept `4`, final kept `43`.
  - AI review: reviewed `28`, candidate pool `43`, stopped after `30`,
    early_stop `true`.
  - Contact placeholder and phone-format checks: no bad contacts found.

## Procurement Source Links And Minprom/GISP Follow-Up

Date: 2026-06-02

### Code Changes

- `backend/app/procurement_sources.py`
  - Added source URL extraction, normalization, EIS vs generic procurement page
    classification, HTTP page extraction, browser-rendered extraction, and
    source context blocks for AI analysis.
- `backend/app/models.py`, `backend/app/db.py`
  - Added `job_sources` for procurement links and a schema guard so existing
    live DBs create the table on startup.
- `backend/app/main.py`
  - `/api/upload` now accepts `source_urls` for documentation-analysis modes
    and can create a source-only analysis job without uploaded files.
  - Plain supplier search rejects source URLs and requires a ТЗ/ООЗ file.
- `backend/app/bot.py`
  - Telegram now exposes procurement links only in `Анализ документации` and
    `Анализ + поставщики`.
  - Plain supplier-search modes ask for ТЗ/ООЗ files and reject source links
    with a customer-facing explanation.
- `backend/app/jobs.py`
  - Worker fetches source pages before file parsing, stores source context under
    job input storage, and passes source blocks into report/supplier AI context.
- `backend/app/procurement_report.py`
  - AI report prompt now treats procurement links as source data for notice
    number, customer, НМЦК, deadlines, platform, legal regime, and source-page
    facts.
- `backend/app/supplier_search.py`
  - AI now decides whether Минпромторг/ГИСП registry evidence is mandatory.
  - Registry search runs only for mandatory requirements.
  - Supplier AI verification receives registry context and may not claim a
    registry requirement is fulfilled without linkage.

### Fresh Verification

- `PYTHONPATH=backend pytest backend/tests/test_procurement_sources.py backend/tests/test_api_guards.py backend/tests/test_bot_progress.py backend/tests/test_procurement_report.py backend/tests/test_supplier_discovery_flow.py -q`
  - Result: `44 passed`, `26` subtests passed, `2` FastAPI deprecation warnings.
- `PYTHONPATH=backend pytest backend/tests -q`
  - Result: `88 passed`, `26` subtests passed, `2` FastAPI deprecation warnings.
- `python3 -m py_compile backend/app/procurement_sources.py backend/app/models.py backend/app/db.py backend/app/jobs.py backend/app/main.py backend/app/bot.py backend/app/supplier_search.py backend/app/procurement_report.py backend/app/worker.py`
  - Result: exit `0`.
- `cd frontend && npm run build`
  - Result: exit `0`, Vite production build completed.
- `backend/.venv/bin/python -m pip check`
  - Result: `No broken requirements found.`
- Live DB schema check:
  - `job_sources`: present.
  - Supplier AI/audit columns present:
    `quality_score`, `quality_tier`, `procurement_item_id`,
    `procurement_item`, `ai_confidence`, `site_type`, `product_fit`,
    `evidence_snippet`, `contact_evidence_snippet`, `ai_rank_confidence`,
    `ai_rank_reason`.
- Services restarted at `2026-06-02T20:47:14Z`:
  - `aipoisk-api.service`: active.
  - `aipoisk-bot.service`: active.
  - `aipoisk-worker.service`: active.
- `curl -fsS http://127.0.0.1:8088/api/health`
  - Result:
    `{"ok":true,"domain":"https://aipoisk.lexelence.ru","logistics_enabled":false}`.
- Fresh systemd logs after restart:
  - API startup complete.
  - No tracebacks or startup errors observed in API, bot, or worker logs.

### Customer Copy Note

- Customer-facing supplier completion text no longer exposes
  `минимум по настройкам`.
- Overfilled XLSX summaries now show only `Найдено и проверено: <count>` plus
  a short explanation that the file contains contacts and concise comments.
- Bot copy now says that links are for documentation analysis, not for plain
  supplier search by ТЗ.

## Documentation Analysis EIS Link Incident

Date: 2026-06-02

### Root Cause

- User-facing report job: `186d6788fd3244f995fbaab9061386cc`.
- Telegram input: zip file `0317400001026000049 _1_.zip` with EIS URL in the
  document caption.
- DB evidence before fix:
  - mode: `procurement_report`;
  - files: `1`;
  - sources: `0`;
  - result: `0317400001026000049 _1_анализ_186d6788.docx`.
- Therefore the EIS URL was never passed to the worker or AI context. The
  report could not extract EIS-only fields and wrote `ДАННЫХ НЕДОСТАТОЧНО`.

### EmailAgent Comparison

- EmailAgent persists `source_url` and runs `UniversalProcurementParser` for
  EIS/source links.
- It adds an official-source context block with direct priority for dates,
  НМЦК, source card fields, and ТЗ/ООЗ data when present.
- EmailAgent also follows EIS print-form/organization pages and has a proxy
  setting in DB. AI Poisk initially had neither caption source capture nor an
  active EIS proxy setting.

### Code And Runtime Changes

- `backend/app/bot.py`
  - Extracts procurement links from document captions for `Анализ документации`
    and `Анализ + поставщики`.
  - Rejects procurement links in plain supplier-search modes with a customer
    explanation that supplier search needs a ТЗ/ООЗ file.
- `backend/app/main.py`
  - API rejects `supplier_search` source URLs without a ТЗ/ООЗ file.
- `backend/app/procurement_sources.py`
  - EIS source context explicitly prioritizes customer, ИНН/КПП, submission
    deadlines, dates, НМЦК, platform, law regime, and notice-card fields.
  - HTTP and browser source fetches are bounded and concurrent.
  - EIS fetch uses `AIPOISK_PROXY_URL`/`PROXY_URL` when configured.
  - EIS follow-up URLs include print forms and customer organization pages.
- Runtime `.env`
  - Added `AIPOISK_PROXY_URL` from the existing EmailAgent DB proxy setting.
  - A backup of `.env` was created before the change.

### Fresh Verification

- `PYTHONPATH=backend pytest backend/tests/test_bot_progress.py backend/tests/test_api_guards.py backend/tests/test_procurement_sources.py backend/tests/test_procurement_report.py -q`
  - Result: `27 passed`, `26` subtests passed, `2` FastAPI deprecation warnings.
- `PYTHONPATH=backend pytest backend/tests -q`
  - Result: `95 passed`, `26` subtests passed, `2` FastAPI deprecation warnings.
- `python3 -m py_compile backend/app/bot.py backend/app/main.py backend/app/procurement_sources.py`
  - Result: exit `0`.
- Real EIS fetch smoke with source URL
  `https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0317400001026000049`:
  - before proxy/follow-up: `fetch_failed`;
  - after fix: `ok=True`, status `ok`, context `37280` chars;
  - extracted context contains:
    - customer `БАРНАУЛЬСКИЙ РАЙОН ВОДНЫХ ПУТЕЙ И СУДОХОДСТВА ...`;
    - `ИНН 5504002648`;
    - `КПП 222543001`;
    - application deadline `08.06.2026`;
    - initial price `448 960,00 ₽`;
    - procurement object `Поставка грунтовки антикоррозийной и растворителя`.
- Real queued report rerun:
  - Job: `4102f6bc5d1045f2a302737ceb238538`.
  - Input: same zip as failed report plus the same EIS source URL.
  - Result: `completed`.
  - Source status: `ok`, extracted `37280` chars.
  - DOCX path:
    `storage/jobs/4102f6bc5d1045f2a302737ceb238538/output/0317400001026000049 _1_ повтор с ЕИС_анализ_4102f6bc.docx`.
  - DOCX contains:
    - customer `БАРНАУЛЬСКИЙ РАЙОН ВОДНЫХ ПУТЕЙ И СУДОХОДСТВА ...`;
    - `ИНН/КПП: 5504002648 / 222543001`;
    - `НМЦК: 448 960,00 руб.`;
    - `Электронная площадка: РТС-тендер`;
    - `Крайний срок подачи заявок: 08.06.2026 12:00 (МСК+4)`;
    - `Дата подведения итогов: 10.06.2026`.
  - DOCX no longer contains old failures:
    - `Заказчик: ДАННЫХ НЕДОСТАТОЧНО`;
    - `ИНН/КПП: ДАННЫХ НЕДОСТАТОЧНО`;
    - `Срок подачи заявок: ДАННЫХ НЕДОСТАТОЧНО`.

## Documentation Analysis Official Card Guard

Date: 2026-06-02

### Finding

- Latest user-triggered job: `8a34a04b82d34ddbab2ce504be16de6d`.
- Input: `32616063169.zip` plus EIS source URL
  `https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32616063169`.
- The bot correctly stored one file and one source link.
- EIS source parsing succeeded:
  - status: `ok`;
  - extracted chars: `9967`;
  - context path:
    `storage/jobs/8a34a04b82d34ddbab2ce504be16de6d/input/sources/01_official_eis.txt`.
- The generated DOCX included customer, ИНН/КПП, НМЦК, platform, and товарная
  table, but had official-card accuracy defects:
  - EIS source: `Способ осуществления закупки: Иной способ`;
  - DOCX: `Способ закупки: Запрос котировок в электронной форме`;
  - EIS source: `Дата подведения итогов: 09.06.2026`;
  - DOCX added invented time: `09.06.2026 до 07:00 (время московское)`.

### Root Cause

- The source link capture and EIS parsing layers were working.
- The issue was in the AI report quality gate:
  - the AI draft changed official card fields;
  - the AI verifier returned `ok: true` and did not catch the mismatch.

### Code Changes

- `backend/app/procurement_report.py`
  - Report generation now raises an AI-required error instead of issuing a
    deterministic fallback report when AI is unavailable or generation fails.
  - Empty AI output is treated as a failure, not converted into a placeholder
    report.
  - Verification failure without a corrected report fails the job.
  - Official card facts are extracted from official-source context:
    `Способ осуществления закупки`, `Дата и время окончания срока подачи заявок`,
    and `Дата подведения итогов`.
  - The final report is validated against those facts before DOCX release.
  - If the AI draft conflicts with official card facts, AI receives a focused
    repair prompt; the repaired report is validated again.
  - If the repaired report still conflicts with official facts, the job fails
    instead of publishing a misleading DOCX.
- `backend/tests/test_procurement_report.py`
  - Added regression coverage for:
    - rejecting `Иной способ (запрос котировок...)`;
    - rejecting deadline time conversion from `09:00` to `06:00`;
    - rejecting invented results time when the source has only a date;
    - requiring AI provider for report generation;
    - preventing empty-output fallback report generation.
- `docs/PROJECT_STATUS.md`
  - Added the procurement documentation analysis AI-required and official-card
    guard contract.

### Fresh Verification

- `PYTHONPATH=backend pytest backend/tests/test_procurement_report.py -q`
  - Result: `10 passed`, `35` subtests passed.
- `PYTHONPATH=backend pytest backend/tests -q`
  - Result: `102 passed`, `35` subtests passed, `2` FastAPI deprecation warnings.
- `python3 -m py_compile backend/app/procurement_report.py backend/app/jobs.py`
  - Result: exit `0`.
- `git diff --check`
  - Result: exit `0`.
- Services restarted:
  - `aipoisk-api.service`: active;
  - `aipoisk-bot.service`: active;
  - `aipoisk-worker.service`: active.
- `curl -fsS http://127.0.0.1:8000/api/health`
  - Result: status `ok`, database `ok`, AI configured.

## AI Supplier Search Architecture Pass

Date: 2026-06-03

### Root Cause Focus

- Customer-facing outputs still exposed the configured supplier target in
  underfilled states as `count/target`.
- `analysis_and_suppliers` searched suppliers against the full documentation
  context, which can include contract terms, source-card data, forms, and other
  non-TZ noise.
- Supplier discovery had no second AI-directed search pass after the first
  verified review underfilled the target.

### Code Changes

- `backend/app/report_builder.py`
  - XLSX supplier summaries now show only the actual verified supplier count,
    including underfilled reports.
- `backend/app/jobs.py`
  - Job messages now show only the actual verified supplier count.
  - `analysis_and_suppliers` now runs AI supplier-context extraction before
    supplier discovery, so the supplier search receives the ТЗ/ООЗ/product
    specification context instead of the full noisy documentation bundle.
- `backend/app/supplier_search.py`
  - Added AI-required supplier-context extraction.
  - Added an AI recovery search round when the first AI-verified supplier round
    underfills the configured target.
  - Recovery queries are generated from the procurement profile, initial
    queries, rejected candidates, and accepted suppliers; no deterministic
    fallback is used.
- `backend/tests/test_report_builder.py`
  - Added underfilled XLSX count regression.
- `backend/tests/test_jobs_recovery.py`
  - Added underfilled job-message regression.
  - Combined-mode test now verifies supplier search receives AI-extracted ТЗ
    context.
- `backend/tests/test_supplier_discovery_flow.py`
  - Added regression proving AI recovery search runs when the first round
    underfills.
- `docs/PROJECT_STATUS.md` and `.omx/project-memory.json`
  - Recorded the durable architecture contract.

### Fresh Verification

- Red phase:
  `PYTHONPATH=backend pytest backend/tests/test_report_builder.py::ReportBuilderTests::test_supplier_xlsx_hides_internal_target_when_underfilled backend/tests/test_jobs_recovery.py::JobRecoveryTests::test_supplier_count_message_hides_internal_target_when_underfilled backend/tests/test_supplier_discovery_flow.py::SupplierDiscoveryFlowTests::test_discover_suppliers_runs_ai_recovery_search_when_first_round_underfills -q`
  - Result before implementation: `3 failed`.
- Green phase for the same regressions:
  - Result after implementation: `3 passed`.
- Combined-mode red/green:
  - Before implementation:
    `test_combined_mode_writes_analysis_and_supplier_files` failed with
    missing `extract_supplier_search_context`.
  - After implementation:
    `1 passed`.
- Expanded targeted suite:
  `PYTHONPATH=backend pytest backend/tests/test_bot_progress.py backend/tests/test_api_guards.py backend/tests/test_jobs_recovery.py backend/tests/test_report_builder.py backend/tests/test_supplier_discovery_flow.py backend/tests/test_supplier_search_sources.py backend/tests/test_procurement_report.py backend/tests/test_procurement_sources.py -q`
  - Result: `110 passed`, `35` subtests passed, `2` FastAPI deprecation
    warnings.
- Full backend suite:
  `PYTHONPATH=backend pytest backend/tests -q`
  - Result: `113 passed`, `35` subtests passed, `2` FastAPI deprecation
    warnings.
- Compile:
  `PYTHONPATH=backend python3 -m compileall backend/app backend/tests`
  - Result: exit `0`.
- Frontend build:
  `cd frontend && npm run build`
  - Result: exit `0`.
- JSON checks:
  `python3 -m json.tool .omx/project-memory.json` and
  `python3 -m json.tool .agent/tasks/aipoisk-commercial-10/verdict.json`
  - Result: exit `0`.
- Diff whitespace:
  `git diff --check`
  - Result: exit `0`.
- Live restart:
  `systemctl restart aipoisk-api.service aipoisk-bot.service aipoisk-worker.service`
  - Result: services restarted; immediate health curl raced startup once.
- Post-restart health:
  `curl -fsS http://127.0.0.1:8088/api/health`
  - Result: `{"ok":true,"domain":"https://aipoisk.lexelence.ru","logistics_enabled":false}`.
- Post-restart service status:
  `systemctl is-active aipoisk-api.service aipoisk-bot.service aipoisk-worker.service`
  - Result: `active`, `active`, `active`.
- Post-restart log scan:
  `journalctl ... --since '2026-06-03 14:53:07 UTC' | rg -i 'traceback|exception|error|failed'`
  - Result: no matches.

## Mass Supplier Batch Recovery Follow-Up

Date: 2026-06-03

### Root Cause

- The split multi-TZ batch worked architecturally: jobs were created one file
  per `supplier_search` task.
- 8 jobs failed after AI search had already saved supplier rows because output
  XLSX filenames exceeded the filesystem component limit with long Cyrillic
  source titles and AI-derived subjects.
- 1 `.doc` job failed before AI search because the installed `antiword`
  executable raised `OSError: Exec format error`; the parser did not continue
  to LibreOffice fallback.

### Code Changes

- `backend/app/document_parser.py`
  - `sanitize_filename` now truncates by UTF-8 bytes, not character count.
  - `.doc` extraction catches broken `antiword` executions and continues to
    LibreOffice conversion.
- `backend/app/jobs.py`
  - Result stems are capped by UTF-8 bytes so generated XLSX/DOCX/ZIP names
    remain below filesystem limits for Cyrillic names.
- `backend/tests/test_document_parser.py`
  - Added regression test for broken `antiword` fallback.
- `backend/tests/test_jobs_recovery.py`
  - Added regression test for long Cyrillic result filenames.

### Fresh Verification

- Red tests before fix:
  - long Cyrillic XLSX filename was `300` bytes and failed the `<=255` check;
  - `_extract_doc` propagated `OSError: Exec format error`.
- Targeted tests after fix:
  - `PYTHONPATH=backend pytest backend/tests/test_jobs_recovery.py::JobRecoveryTests::test_result_stem_keeps_cyrillic_output_filename_under_filesystem_limit backend/tests/test_document_parser.py::DocumentParserTests::test_doc_extraction_falls_back_to_libreoffice_when_antiword_is_broken -q`
  - Result: `2 passed`.
- Full backend suite:
  - `PYTHONPATH=backend pytest backend/tests -q`
  - Result: `110 passed`, `35` subtests passed, `2` FastAPI deprecation warnings.
- Static checks:
  - `PYTHONPATH=backend python3 -m compileall -q backend/app backend/tests`
    exited `0`.
  - `git diff --check -- backend/app/document_parser.py backend/app/jobs.py backend/tests/test_document_parser.py backend/tests/test_jobs_recovery.py`
    exited `0`.
- Live parser check:
  - Previously failed `.doc` extracted with status `ok` and `101351` chars.
- Recovery:
  - SQLite backup created:
    `data/aipoisk.db.backup-before-report-recovery-20260603T061856Z`.
  - Recovered 8 failed jobs from already saved supplier rows without rerunning
    paid search; generated XLSX filename components were `192-194` bytes.
  - Reran the `.doc` job end-to-end; result `completed`, `20` suppliers.
  - Reran the remaining partial job; result `completed`, `16` suppliers.
- Final batch check:
  - `19/19` latest split supplier jobs are `completed`.
  - Total suppliers across those reports: `399`.
  - Minimum suppliers in any report: `16`.
  - Max XLSX filename component length: `230` bytes.
  - XLSX headers in every checked report:
    `Компания`, `Сайт`, `Телефоны`, `Email`, `Комментарий`.
  - `failed_with_rows=0`.
- Services:
  - Restarted `aipoisk-api.service`, `aipoisk-bot.service`,
    `aipoisk-worker.service`.
  - All three services are `active`.
  - `curl -fsS http://127.0.0.1:8088/api/health` returned
    `{"ok":true,...}`.

### Real Rerun

- Job: `43386d9cf7224a8b9795818936751f0a`.
- Input: same `32616063169.zip` plus the same EIS source URL.
- Result: `completed`.
- Output:
  `storage/jobs/43386d9cf7224a8b9795818936751f0a/output/32616063169_анализ_43386d9c.docx`.
- Evidence:
  `storage/jobs/43386d9cf7224a8b9795818936751f0a/output/evidence.json`.
- Evidence:
  - `ai_used=true`;
  - model: `Gemini | gemini-3.1-flash-lite-preview`;
  - source parse status: `ok`;
  - `official_card_validation.ok=true`;
  - official facts:
    - `procurement_method: Иной способ`;
    - `submission_deadline: 09.06.2026 09:00`;
    - `results_date: 09.06.2026`.
- DOCX now contains:
  - `Способ закупки: Иной способ`;
  - `Крайний срок подачи заявок: 09.06.2026 09:00`;
  - `Дата рассмотрения/подведения итогов: 09.06.2026`;
  - товарная table row:
    `Канат стальной оцинкованный | ГОСТ 3062-80, диаметр 7,4 мм | км | 10,00`.
- Local validation command:
  `validate_report_against_official_card(...)`
  - facts:
    `{'procurement_method': 'Иной способ', 'submission_deadline': '09.06.2026 09:00', 'results_date': '09.06.2026'}`;
  - issues: `[]`.

## Multi-TZ Supplier Batch Routing Incident

Date: 2026-06-02

### Finding

- Observed user-triggered Telegram job:
  `3ab9bef87f2e4e9eb9416ea8e08dda49`.
- Mode: `supplier_search`.
- Input: `19` files through `Поставщики по нескольким ТЗ`.
- Result: `completed`, `24/15` suppliers.
- Evidence showed the AI procurement profile contained only `5` items:
  - `Система оповещения и управления эвакуацией людей (СОУЭ)`;
  - `Провизионные кладовые (камеры)`;
  - `Циркуляционный насос охлаждения`;
  - `Пластинчатый теплообменник`;
  - `Система обнаружения утечек хладагента`.
- Supplier distribution:
  - СОУЭ: `12`;
  - провизионные камеры: `4`;
  - пластинчатый теплообменник: `4`;
  - циркуляционный насос: `2`;
  - система обнаружения утечек хладагента: `2`.
- Other uploaded ТЗ files were effectively not represented in the final XLSX.
- One `.doc` file also failed text extraction:
  `ТЗ_ПРИТОЧНО_ВЫТЯЖНЫХ_ВЕНТИЛЯЦИОННЫХ_УСТАНОВОК_Рита.doc`
  with `antiword` exec-format error.

### Root Cause

- The Telegram button `Поставщики по нескольким ТЗ` created one
  `supplier_search` job containing all uploaded files.
- The worker concatenated all extracted texts into one context.
- AI then generated one procurement profile from the combined context, so a few
  dominant items hid unrelated technical assignments.
- This was a routing/architecture bug in mass processing, not a supplier-search
  quality issue for one ТЗ.

### Code Changes

- `backend/app/bot.py`
  - Added `_supplier_multi_job_specs`.
  - `Поставщики по нескольким ТЗ` now creates one independent
    `supplier_search` job per uploaded ТЗ file.
  - Each created job receives exactly one file and no shared source context.
  - The bot watches each created job and sends a separate XLSX output per ТЗ.
- `backend/app/main.py`
  - Admin/API `supplier_search` upload with multiple files now returns a batch
    response and creates one job per file.
  - Single-file `supplier_search`, documentation analysis, and combined
    analysis+suppliers behavior remain unchanged.
- `backend/tests/test_bot_progress.py`
  - Added regression coverage proving multi-TZ supplier specs split files into
    separate one-file job payloads.
- `backend/tests/test_api_guards.py`
  - Added regression coverage proving multi-file API supplier upload creates
    separate jobs and enqueues each one.
- `docs/PROJECT_STATUS.md`
  - Added the mass supplier search contract.

### Fresh Verification

- `PYTHONPATH=backend pytest backend/tests/test_bot_progress.py backend/tests/test_api_guards.py backend/tests/test_jobs_recovery.py -q`
  - Result: `27 passed`, `2` FastAPI deprecation warnings.
- `PYTHONPATH=backend pytest backend/tests -q`
  - Result: `105 passed`, `35` subtests passed, `2` FastAPI deprecation
    warnings.
- `python3 -m py_compile backend/app/bot.py backend/app/main.py`
  - Result: exit `0`.
- `git diff --check`
  - Result: exit `0`.
- Helper smoke:
  - `_supplier_multi_job_specs(PendingBatch(... files=[a.docx, b.docx]))`
    returned:
    `[('a', [('a.docx', b'a')]), ('b', [('b.docx', b'b')])]`.
- Services restarted:
  - `aipoisk-api.service`: active;
  - `aipoisk-bot.service`: active;
  - `aipoisk-worker.service`: active.
- `curl -fsS http://127.0.0.1:8000/api/health`
  - Result: status `ok`, database `ok`, AI configured.
