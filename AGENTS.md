# AI Poisk Bot / TenderLex

## Project Context

- Backend: FastAPI in `backend/app`, SQLite data under `data/`, admin API guarded by admin session/token.
- Existing admin panel: React/Vite in `frontend/`.
- Public business-card website: Next.js in `site/`, served for `tenderlex.ru`.
- The public website is a landing/site-card only. Do not add a blog unless the user explicitly changes that scope.

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
