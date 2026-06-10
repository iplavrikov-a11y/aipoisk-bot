# TenderLex / aipoisk-bot

## Project Context

- Backend: FastAPI in `backend/app`, SQLite data under `data/`, admin API guarded by admin session/token.
- Existing admin panel: React/Vite in `frontend/`.
- Public TenderLex website and customer cabinet: Next.js in `site/`, served for `tenderlex.ru`.
- The public website scope is landing page plus authenticated customer cabinet. Do not add a blog or public admin panel unless the user explicitly changes that scope.
- Customer-facing product name is `TenderLex` for the Telegram bot, public site, reports, filenames, and admin-visible branding. `AI Poisk`/`aipoisk-bot` is only a repository/service identifier and must not appear in customer-facing copy.
- Tenderplan/API procurement access is an internal data source. Do not expose the Tenderplan name in customer-facing Telegram messages, DOCX/XLSX titles, output filenames, report text, or customer-visible errors. Name output files and report headings by the procurement subject/product when it is available.
- Public website and cabinet copy must speak in client-result language: what the user can do and what decision/result they get. Do not sell with file-format labels like DOCX/XLSX, technical account details like "web balance" or "protected session", or exact free-run counters. If examples are needed, use professional procurement scenarios close to real work, not random artificial company names.

## Public Site Contract

- Tariffs and contacts are managed from the existing admin panel and exposed to the site through a safe public backend endpoint.
- Do not expose admin-only endpoints, client data, secrets, AI provider keys, jobs, or billing history to the public site.
- Public domain canonical URL: `https://tenderlex.ru`.
- `www.tenderlex.ru` should redirect to `https://tenderlex.ru`.

## Working Commands

- Backend tests from repo root: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest backend/tests -q`
- Admin build: `cd frontend && npm run build`
- Site dev: `cd site && npm run dev`
- Site build: `cd site && npm run build`
- Site typecheck: `cd site && npm run typecheck`

## Deployment Notes

- Runtime server: `202.71.13.57`.
- Existing backend listens on `127.0.0.1:8088`.
- TenderLex site should listen on `127.0.0.1:3093` and fetch public site data from `http://127.0.0.1:8088/api/public/site`.
- After changing site, cabinet, admin, or backend behavior that must be visible to users, do not stop at code edits or local builds. Run `./scripts/deploy_tenderlex_live.sh` and verify the live local service URLs (`127.0.0.1:8088` for API, `127.0.0.1:3093` for site) before reporting the change as deployed.
