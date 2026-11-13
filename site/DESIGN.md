# TenderLex visual system

Approved direction, applied to the production website and customer cabinet on 2026-10-18; homepage v3 shipped on 2026-10-20: warm paper, forest green, restrained lime accents and clear procurement workflows.

## Tokens and typography

- Shared tokens: `src/app/brand-theme.css`; public layouts: `src/app/public-redesign.css`; cabinet: `src/app/cabinet/cabinet-redesign.css`.
- Local variable Manrope font in WOFF2 (53,736 bytes), weights 200–800, loaded through `next/font/local`. Font and OFL license: `src/app/fonts/`. No font request to Google is required.
- Background `#f7f8f3`, paper `#ffffff`, text `#202f29`, muted text `#617068`, primary `#174b3f`, focus outline `#668a4c`. Use lime for highlights, not small light text.
- Use 12px card corners, subtle borders, restrained shadows, readable tables and tabular numbers. Preserve reduced-motion behavior and visible keyboard focus.

## Components and behavior

Public pages use the shared header/footer, retained URLs and metadata. The header stays visible during page scrolling. The native mobile menu scrolls internally on short phones and closes with Escape. Modules retain their documented order: suppliers, products/analogs, documentation analysis.

The cabinet uses existing React handlers and API contracts. On desktop, account tools occupy a left sidebar; on phones, a balance/menu control reveals the same tools. Task tabs, forms, files, history, results and modals remain actual product components. Cabinet task order remains analysis, suppliers, analysis + search, products/analogs; optional monitoring follows feature flags.

Tariffs, payment availability, contacts, free access and balances come from existing settings and session endpoints. Do not hardcode them for visual consistency. Product/analog reports remain Word only. The homepage uses Home v3: server-rendered markup (`home-v3-content.ts`) with scoped styles (`home-v3.css`) and a progressive-enhancement client (`home-v3-interactions.tsx`). The five-step walkthrough shows a specification, extracted fields with source tracing, supplier candidates, an analog comparison and an RFQ draft with a self-check. It never launches tasks, sends requests or invents supplier/source links. `?step=1..5` is shareable; without JS the first step and all content remain visible.

Public motion is progressive enhancement. Home v3 owns its motion (reveal, step transitions, autoplay) and is explicitly skipped by `PublicMotion`; the legacy public motion remains for other pages. Motion never hides normal content, excludes cabinet routes and H1 containers, cleans up on navigation and responds to reduced-motion changes. No animation package is required.

Expanded cabinet tariffs belong to the main working column. Keep full amounts visible at375/768/1024/1440; checking page overflow alone misses truncation. Delivery-city/radius fields must remain labelled, with the opt-in40% fee and required nonempty city.

Background task refresh must keep pagination usable. Only explicit navigation/filter loads own `jobsLoading`; background requests are single-flight, and request generations prevent previous pages, filters or sessions from replacing current results or firing stale completion notifications. Preserve `no-store` requests and existing notification preferences. `test_cabinet_polling_browser.py` holds an old response while changing pages to verify this contract.

## SEO and indexing

- Homepage metadata, canonical URLs, Open Graph and JSON-LD are owned by `src/app/page.tsx`; sitewide Organization/SoftwareApplication live in `src/app/layout.tsx`.
- Home v3 ships FAQ, WebSite and Service JSON-LD; article pages use TechArticle with `datePublished` and `dateModified`.
- Sitemap is generated from `src/app/sitemap.ts`; article `lastmod` comes from each article's `updatedDate`. Keep changed commercial pages' dates current.
- `/v2` is intentionally `noindex, nofollow` with canonical `/` while it remains a design alternative outside the main navigation.
- `robots.ts` keeps `/api/`, `/cabinet`, `/v2`, `/test-buttons` and `/demo-*` out of crawling. 404 pages are `noindex`.
- Open Graph image: `public/tenderlex-og-1200x630.png` (1200×630). `llms.txt` must cover every sitemap URL.
- Yandex Metrika is consent-gated: `YandexMetrika` renders only after the visitor allows analytics; `YANDEX_METRIKA_COUNTER_ID` is the production fallback.
- Google Search Console is the live reporting source (read-only service account). Yandex Webmaster API is currently unreachable from the VPS (IPv4 timeout, no IPv6); Wordstat API is unavailable. Treat cached Webmaster/Wordstat values as stale in admin.
- After content changes, run the site-scope deploy, then `scripts/test_public_refinement_browser.py`, `scripts/test_public_redesign_browser.py` and `scripts/test_public_navigation_browser.py`; submit changed URLs through IndexNow when appropriate.

## Verification and releases

Do not run a production build inside the active live `site/` directory: Next.js replaces its `.next` tree. Use the existing isolated release pipeline from the repository root:

```sh
AIPOISK_DEPLOY_SCOPE=site ./scripts/deploy_tenderlex_live.sh
```

The pipeline builds separately, retains a previous build and restarts only the site. For local QA, use a separate source copy and independent port; do not modify the live build tree.

Relevant checks in `scripts/`: `check_cabinet_contracts.mjs`, `test_cabinet_workflows_browser.py`, `test_public_redesign_browser.py`, `test_public_navigation_browser.py`, `test_public_refinement_browser.py`, `audit_public_copy.py`, `test_site_analytics_browser.py`, `check_tenderlex_seo.sh`, and existing SSR/schema/content checks. Browser cabinet scenarios must intercept customer APIs and paid/external mutations. Reports distinguish simulated UI verification from real OAuth, payment settlement and AI execution.
