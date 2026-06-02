# AI Poisk Commercial Hardening

Date: 2026-06-02

## Goal

Push supplier search closer to paid-client quality by improving speed,
report explainability, and task reliability.

## Acceptance Criteria

- Supplier verification stops after enough high-ranked verified suppliers are
  found instead of waiting for the full candidate pool.
- Evidence records review batch/early-stop metadata.
- XLSX report shows match quality, search source, evidence URL, and contact URL.
- Admin manual jobs cannot create empty no-input jobs.
- API startup recovers safe pending/stale jobs instead of leaving them stuck.
- Existing live health and download flow stay working after restart.
