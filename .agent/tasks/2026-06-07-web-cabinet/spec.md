# TenderLex web cabinet implementation

## Goal

Implement the approved first production slice of TenderLex website functionality:
keep the public SEO landing page at `/`, add a protected web cabinet for users
who cannot or do not want to work through Telegram, and reuse the existing
backend job pipeline for all customer-facing scenarios.

## Scope

- Keep Telegram and website users/payments separated.
- Add website identity separate from Telegram accounts.
- Add customer-safe backend API separate from admin API.
- Reuse existing job processing, parsing, AI supplier search, procurement report,
  DOCX/XLSX generation, billing reservation/charge/release logic.
- Add a Next.js cabinet under `/cabinet`.
- Keep the public landing page useful for SEO and advertising.
- Extend admin visibility enough to distinguish/manage web users.

## Functional Acceptance Criteria

- Public `/` remains an indexable TenderLex landing page.
- Cabinet pages are not indexed.
- A website user can register, log in, log out, and view their own cabinet.
- Website balances are tied to a separate web-owned `Client`, not a Telegram ID.
- Website user can start:
  - supplier search from one file or text ТЗ;
  - multiple supplier searches, one job per ТЗ/file;
  - procurement analysis from uploaded files, archive, notice number, or link;
  - analysis plus supplier search from the same accepted procurement inputs.
- Website user can see only their own jobs.
- Website user can download only their own result files.
- Partial supplier result accept/decline flow works on the web and preserves
  existing billing behavior.
- Admin can identify clients created from website accounts.

## Security Acceptance Criteria

- Admin API remains admin-only.
- Customer API has separate auth and does not expose admin endpoints.
- Customer session uses secure HttpOnly cookie semantics.
- Mutating customer API calls require CSRF protection.
- Login/register endpoints have basic rate limiting.
- Passwords are not stored in plaintext.
- Uploads are size-limited and use existing parser/file storage paths.
- Direct job/download/evidence access checks ownership by authenticated web user.

## Explicit Deferred Scope

- Full automated YooKassa checkout/webhook is deferred until credentials and
  production webhook URL are available.
- Automatic Telegram-to-web account merge/linking is deferred. If needed later,
  it should be an admin-controlled action.
