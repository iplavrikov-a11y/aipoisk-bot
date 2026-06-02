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
  a blocking dependency because Yandex, Google, and DDGS are active fallbacks.

## Remaining Commercial Risks

- Queue execution is still in-process. Startup recovery now reduces stuck-job
  risk, but a durable external queue would still be stronger under high load.
- Browser-rendered/JS-heavy supplier sites may still hide contacts from the
  current HTTP/BeautifulSoup extractor.
- The quality gate has one real procurement job plus unit coverage. A broader
  multi-domain evaluation set is still needed before calling the system truly
  production-perfect.
