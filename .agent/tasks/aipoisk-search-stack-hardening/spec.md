# AI Poisk Search Stack Hardening

Date: 2026-06-02

## Goal

Remove the single-source Tavily dependency from supplier discovery and make the
search stack suitable for paid-client supplier lead discovery.

## Acceptance Criteria

- Tavily plan-limit errors do not stop supplier discovery.
- Yandex Search API can be used as the primary Russian B2B search source.
- Google Custom Search can be used as a secondary source when configured.
- DDGS remains only an emergency fallback.
- Search evidence records provider counts and candidate source metadata.
- Existing supplier verification still requires opened supplier pages and
  contacts before XLSX rows are accepted.
- Fresh tests and live smoke checks are recorded in evidence.
