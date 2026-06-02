# Evidence

Date: 2026-06-02

## Investigation

- Tavily direct API check returned HTTP 432: current plan usage limit exceeded.
- EmailAgent Yandex Search settings are present and the live API returned
  useful Russian B2B domains for control supplier queries.
- EmailAgent Google Custom Search settings are present and the live API returned
  results, but with more noisy government/reference/general domains.
- SearXNG is running, but control search produced aggregator-heavy results.
- OpenSERP is healthy on `/health`, but ordinary `/search` is not its endpoint.
- Gemini Search Adapter is healthy, but it is a grounded chat adapter, not a
  deterministic search-result source.

## Implementation

- Added AI Poisk-owned search settings:
  - `supplier_search_provider_order`
  - `yandex_search_folder_id`
  - `yandex_search_api_key`
  - `google_search_api_key`
  - `google_search_cse_id`
- Imported working Yandex/Google search credentials from EmailAgent settings
  into AI Poisk's own SQLite settings row. Secrets were not printed.
- Added a multi-source search chain: `Yandex -> Google -> Tavily -> DDGS`.
- Candidate evidence now records `source` and `search_query`.
- Search evidence now records provider reports and source counts.
- Fixed query expansion so short/base queries are sent before long variants.
- Expanded the block-list for obvious search pages, tender portals, directories,
  marketplaces, media/reference domains observed in live supplier tests.

## Verification

- `python -m unittest tests.test_supplier_search_sources -v` passed: 7 tests.
- `python -m compileall app` passed.
- AI Poisk candidate search on the real control job returned 40 Yandex
  candidates after the query-order fix.
- Full live supplier-discovery smoke on job
  `c01e10dd5ac64de4a9e1c0b827a668a8` returned:
  - accepted: `15/15`
  - accepted sources: `yandex=13`, `google=1`, `ddgs=1`
  - candidate source counts after ranking: `yandex=39`, `google=12`,
    `ddgs=24`
  - provider reports: Yandex ok, Google ok, Tavily empty due current quota
    state, DDGS ok
  - blocked test domains absent from accepted results
- Reprocessed saved job `c01e10dd5ac64de4a9e1c0b827a668a8` through the new
  production path:
  - job status: `completed`
  - verified suppliers: `15/15`
  - evidence accepted source counts: `yandex=12`, `google=1`, `ddgs=2`
  - evidence candidate source counts after ranking: `yandex=41`,
    `google=11`, `ddgs=23`
  - XLSX opened with `openpyxl`: 18 rows, 10 columns
  - authenticated download endpoint returned HTTP 200 and XLSX content type
- Runtime verification after restart:
  - `aipoisk-api.service`: active
  - `aipoisk-bot.service`: active
  - `nginx`: active
  - local `/api/health`: ok
  - public `https://aipoisk.lexelence.ru/api/health`: HTTP 200
  - recent service journals contained no fresh traceback/error/exception lines

## Remaining Risks

- Supplier verification still waits for the full candidate-review pool; add
  early-stop/time-budget logic for faster commercial UX.
- Queue execution is still in-process/in-memory; durable Redis/ARQ/RQ/Celery
  style job execution is still needed before heavier paid usage.
- Telegram currently handles one uploaded file per message; batch UX is still a
  product gap.
- `/api/jobs/manual` still has no document/text payload path and should be
  redesigned or blocked explicitly.
- The project is still untracked under the shared `/root/projects` git root;
  create a clean repo/history before formal commercial release.
