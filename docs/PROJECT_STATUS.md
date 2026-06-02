# AI Poisk Bot: Project Status

Date: 2026-06-02

## Current Production State

- Public URL: `https://aipoisk.lexelence.ru`.
- Backend service: `aipoisk-api.service`, FastAPI on `127.0.0.1:8088`.
- Telegram worker: `aipoisk-bot.service`.
- Frontend: static Vite build served by nginx from `frontend/dist`.
- Database: SQLite at runtime path from `.env`; the live DB is intentionally not stored in git.
- Runtime storage: `storage/`; uploaded files, generated reports, and job outputs are intentionally not stored in git.

## Supplier Search Stack

The supplier-search flow is now multi-source:

- Yandex Search API
- Google Custom Search
- Tavily
- DDGS fallback

The default provider order is `yandex,google,tavily,ddgs`. Tavily can exhaust its free quota quickly, so it must remain non-blocking. Yandex and Google are currently the stronger primary sources for this project.

Supplier candidates are verified before they reach the final report:

- official website is reachable;
- page content is relevant to the procurement object or adjacent supplier profile;
- contact page, phone, or email is found;
- evidence URL and contact URL are preserved;
- duplicate domains and companies are filtered;
- the review stops early once the target number of verified suppliers is reached.

## Reports And Audit Fields

XLSX supplier reports include:

- company name;
- region and status;
- match quality;
- product/category;
- phone and email;
- website;
- search source;
- search query;
- comments;
- contact URL;
- evidence URL.

Stored supplier rows also preserve `match_level`, `source`, and `search_query`, so admin/API views can explain where a supplier came from.

## Verification Snapshot

Latest verified control job:

- Job ID: `c01e10dd5ac64de4a9e1c0b827a668a8`.
- Result: `completed`, `15/15`.
- Search providers verified in evidence: Yandex, Google, Tavily, DDGS.
- Early stop evidence: enough suppliers found before reviewing the full candidate pool.

Fresh checks from the latest hardening pass:

- Backend unit tests: `13` tests OK.
- Python compile check: OK.
- Public health endpoint: HTTP 200.
- API, bot, and nginx services: active.

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

## Remaining Work Toward 10/10

The current system is much stronger, but the honest remaining commercial gap is:

- move job execution from in-process tasks to a durable queue such as Redis plus RQ, ARQ, or Celery;
- add browser-based contact extraction fallback for JavaScript-heavy supplier websites;
- build a multi-domain evaluation suite across different procurement categories;
- improve Telegram batch UX for multi-file procurements;
- add operational monitoring for search-provider failures, job duration, and report quality.
