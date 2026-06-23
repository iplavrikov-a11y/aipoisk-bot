# TenderLex Public Site And Web Cabinet

The public site is a standalone Next.js app in `site/`. It serves the TenderLex
landing page and the authenticated customer cabinet at `https://tenderlex.ru`.

## Scope

- SEO landing page plus customer cabinet.
- Dedicated scenario pages for procurement-document analysis, supplier search, and Minpromtorg-related registry context.
- No blog, no CMS, no public admin panel.
- Contacts and active tariffs come from the existing FastAPI backend through `GET /api/public/site`.
- The first screen must sell two equal product scenarios: procurement-document analysis and supplier/contact search.
- Public copy should offer both entry points: work on the site and work in Telegram.
- Customer-facing copy must explain the business result, not implementation details such as file formats, internal balances, protected sessions, or exact free-run counters.
- The cabinet must mirror the bot scenarios: `Одно ТЗ`, `Несколько ТЗ`, `Анализ закупки`, and `Анализ + поиск`.
- `Анализ закупки` and `Анализ + поиск` accept a notice number, link, or uploaded procurement materials; they must not expose extra invented fields such as "what to check".
- `Несколько ТЗ` is mass supplier search: each uploaded ТЗ is processed as a separate supplier-search job.
- The cabinet task list is paginated at 15 tasks per page and shows timestamps
  in Moscow time. The backend continues to store timestamps in UTC.
- The cabinet and Telegram bot can show the same job when the same customer has
  linked website and Telegram accounts. This is shared customer history, not a
  duplicate launch.
- Yandex Metrika must not render on `/cabinet`; it is limited to public SEO
  pages.

## Public Data Contract

- `GET /api/public/site` is the only public backend endpoint used by the site.
- It exposes safe site metadata, active tariffs, grouped tariff lists, trial counters, public contact links, and the Telegram bot link.
- It must not expose admin endpoints, customers, jobs, billing history, uploaded files, report files, AI provider keys, or other secrets.
- `bot.telegram_url` is used for the Telegram work CTA such as "Попробовать в Telegram".
- `contacts.telegram_url` is used for owner/contact and purchase CTAs such as "Выбрать пакет".
- Current production values are `@tenderlex_bot` for bot use and `@lexelence` for owner contact.

## SEO And Verification

- `site/src/app/layout.tsx` owns the public metadata, canonical URLs, Open Graph tags, and optional verification/analytics wiring.
- `TENDERLEX_YANDEX_METRIKA_ID` enables the Yandex Metrika component.
- `TENDERLEX_YANDEX_VERIFICATION` injects the `yandex-verification` meta tag for Yandex Webmaster.
- `TENDERLEX_GOOGLE_SITE_VERIFICATION` is available for meta-based verification, but the current Google Search Console setup uses DNS TXT verification for the domain property.
- `site/public/yandex_b3b74a829ce4a7c6.html` is the Yandex Webmaster HTML verification file.
- `site/src/app/sitemap.ts` includes the public SEO pages so Search Console and Yandex can discover them from the canonical sitemap.
- `robots.txt` allows public pages, keeps `/cabinet` out of indexing, and declares `Host: https://tenderlex.ru` for Yandex.
- `site/src/app/favicon.ico`, `site/public/favicon.png`, `site/src/app/icon.png`, and `site/src/app/apple-icon.png` are the public icon set. The Yandex-facing favicon paths must include a `120x120` asset.
- Yandex Webmaster has both `http:tenderlex.ru:80` and `https:tenderlex.ru:443` properties. Keep the HTTP favicon paths returning `200 OK` instead of only redirecting, because the HTTP property can diagnose `http://tenderlex.ru/favicon.ico` and `http://tenderlex.ru/favicon.png` directly.
- On 2026-06-23 the Yandex Webmaster DNS check was resent and the following URLs were queued for re-crawl: `http://tenderlex.ru/`, `http://tenderlex.ru/favicon.ico`, `http://tenderlex.ru/favicon.png`, and `https://tenderlex.ru/` in the HTTPS property.
- Production SEO envs are loaded from `/etc/systemd/system/tenderlex-site.service.d/seo.conf` so the live site can pick them up without touching backend or bot services.

## Customer API Contract

- The web cabinet uses `/api/customer/*` routes behind cookie session and CSRF protection.
- Web users are separate from Telegram users. They sign in by email/password and are represented in job/client metadata with `web:<id>`.
- Customer job creation sends the same backend modes used by the bot: `supplier_search`, `procurement_report`, and `analysis_and_suppliers`.
- The frontend hides `target_suppliers`; the backend uses the configured default supplier target.
- `GET /api/customer/jobs` supports pagination for the cabinet. The current UI
  page size is 15 tasks.
- Supplier-search results that can be extended expose an additional action for
  finding more suppliers. The customer must confirm the paid extra run before
  the backend creates the additional supplier-search job.
- Online checkout is intentionally disabled until YooKassa checkout creation, webhooks, idempotency, and payment history are implemented.

## Admin-Managed Fields

The existing admin panel controls public business data without giving customers
access to the admin panel.

- Tariffs are managed from the tariff/package section.
- `bot_telegram` is labelled "Telegram-бот для пробного запуска и работы".
- `contact_telegram` is labelled "Telegram для связи и оплаты".
- `contact_max`, `contact_max_link`, `contact_email`, `contact_website`, and
  payment instructions remain existing contact/payment settings.
- Trial counters come from existing free-period settings: supplier search limit, procurement report limit, and file limit.
- Website access is topped up manually from the admin customer card until online payment is enabled.
- Password recovery requests from `/cabinet` are handled by the admin customer tools; public responses must not reveal whether an email exists.

## Frontend Structure

- `site/src/app/page.tsx` renders the landing sections, CTA routing, examples, and pricing tables.
- `site/src/app/cabinet/page.tsx` and `site/src/app/cabinet/cabinet-client.tsx` render the login/register/reset flow and customer work surface.
- `site/src/app/terms`, `site/src/app/privacy`, and `site/src/app/personal-data` provide legal-page templates for pre-payment launch.
- `site/src/app/layout.tsx` owns public SEO metadata.
- `site/src/lib/site-data.ts` defines the public payload type and safe fallback data.
- `site/src/components/ui/button.tsx` contains the local button primitive.
- `site/public/tenderlex-logo.png` is the provided logo used by the page. The favicon metadata points to the dedicated icon files listed in the SEO section.

## Local Commands

```bash
cd site
npm install
npm run dev
```

Default local URL: `http://localhost:3093`.

The site fetches public data from:

```bash
AIPOISK_SITE_API_BASE_URL=http://127.0.0.1:8088
```

If the backend is unavailable, the page renders a safe fallback using current public contacts and starter tariffs.

## Verification Commands

- Site typecheck: `cd site && npm run typecheck`
- Site production build: `cd site && npm run build`
- Admin production build, when public settings UI changes: `cd frontend && npm run build`
- Targeted backend tests for the public/customer API contract: `PYTHONPATH=/root/projects/aipoisk-bot/backend pytest backend/tests/test_customer_api.py backend/tests/test_api_guards.py backend/tests/test_access_limits.py -q`
- Production smoke: `curl -fsS http://127.0.0.1:8088/api/public/site | jq '{bot, contacts, trial}'`
- Production positive copy check: `curl -fsS https://tenderlex.ru/ | rg 'Попробовать на сайте|Попробовать в Telegram'`
- Production stale-copy check: `curl -fsS https://tenderlex.ru/ | rg 'сотовый поликарбонат|XLSX|DOCX'` should return no matches.
- SEO smoke: `curl -fsS --resolve tenderlex.ru:443:127.0.0.1 https://tenderlex.ru/sitemap.xml | rg 'analiz-zakupochnoi-dokumentacii|poisk-postavshchikov-po-tz|reestr-minpromtorga-v-zakupkah'`
- Verification smoke: `curl -fsS --resolve tenderlex.ru:443:127.0.0.1 https://tenderlex.ru/yandex_b3b74a829ce4a7c6.html`
- Yandex favicon smoke: `curl -sS -D - -o /tmp/tenderlex-favicon.ico http://tenderlex.ru/favicon.ico | sed -n '1,12p'` should show `200 OK`, and `identify -format '%wx%h %m\n' /tmp/tenderlex-favicon.ico` should show `120x120`.
- Yandex PNG favicon smoke: `curl -sS -D - -o /tmp/tenderlex-favicon.png http://tenderlex.ru/favicon.png | sed -n '1,12p'` should show `200 OK`, and `identify -format '%wx%h %m\n' /tmp/tenderlex-favicon.png` should show `120x120`.
- Cabinet Metrika smoke: `curl -fsS http://127.0.0.1:3093/cabinet | rg 'mc\.yandex\.ru|yandex-metrika|metrika'` should return no matches.

## Production Wiring

Deployment files:

- `deploy/systemd/tenderlex-site.service`
- `deploy/nginx/tenderlex.ru.conf`
- `deploy/nginx/tenderlex.ru.http-only.conf`

Production assumptions:

- FastAPI backend is on `127.0.0.1:8088`.
- Next.js site listens on `127.0.0.1:3093`.
- Canonical public URL is `https://tenderlex.ru`.
- `www.tenderlex.ru` redirects to `https://tenderlex.ru`.
- The plain HTTP vhost still redirects normal traffic to HTTPS, but it proxies `/favicon.ico`, `/favicon.png`, and `/icon.png` to the site service so Yandex Webmaster can fetch those icon URLs with `200 OK`.
- `npm run build` copies `.next/static` and `public/` into the standalone bundle before `npm run start`.
- Public `443` on this server is routed through the existing nginx stream layout to HTTPS vhosts listening on `4443`.
- The live site service can be updated with `systemctl restart tenderlex-site.service` after site-only SEO/content changes; backend and bot services do not need a restart for those changes.
- Use `scripts/deploy_tenderlex_live.sh` for ordinary live deploys. It skips
  API/worker/bot restarts when active jobs are present, because worker and bot
  units are tied to the API unit with `PartOf=aipoisk-api.service`.

Manual server activation, after build:

```bash
cp deploy/systemd/tenderlex-site.service /etc/systemd/system/tenderlex-site.service
systemctl daemon-reload
systemctl enable --now tenderlex-site.service

mkdir -p /var/www/letsencrypt
cp deploy/nginx/tenderlex.ru.conf /etc/nginx/sites-available/tenderlex.ru.conf
ln -sf /etc/nginx/sites-available/tenderlex.ru.conf /etc/nginx/sites-enabled/tenderlex.ru.conf
nginx -t
certbot certonly --webroot -w /var/www/letsencrypt -d tenderlex.ru -d www.tenderlex.ru
nginx -t
systemctl reload nginx
```

Routine redeploy after code changes:

```bash
cd /root/projects/aipoisk-bot/site
npm run build
systemctl restart tenderlex-site.service
systemctl is-active tenderlex-site.service
```

Restart `aipoisk-api.service` too when `GET /api/public/site`, customer cabinet
API, authentication, settings schema, or contact/tariff public payload code
changes.
