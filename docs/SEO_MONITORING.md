# SEO monitoring

The collector is read-only: it only calls Yandex and Google read APIs and writes
allowlisted aggregate observations below `/var/lib/tenderlex-seo-monitor`. It
does not send messages, submit URLs, or change site content.

## Credential preparation and installation

Create two root-owned files outside the project:

- `seo-monitor.env` with only `YANDEX_WEBMASTER_TOKEN`, `YANDEX_METRIKA_TOKEN`,
  `YANDEX_METRIKA_COUNTER_ID`, `YANDEX_METRIKA_PRIMARY_GOAL_ID`, and optionally
  `YANDEX_WEBMASTER_HOST_ID`.
- `google-gsc.json`, the existing read-only Search Console service-account key.

Place them in a root-only temporary directory and run:

```bash
sudo ./scripts/install_seo_growth_monitor.sh /root/private-seo-monitor-input
```

The installer copies them with mode `0600`, installs the unit definitions, and
explicitly leaves `tenderlex-seo-monitor.timer` disabled. Never place tokens in
the repository or print the credential files.

## Review before enabling

```bash
sudo systemd-analyze verify /etc/systemd/system/tenderlex-seo-monitor.service /etc/systemd/system/tenderlex-seo-monitor.timer
sudo systemd-analyze security tenderlex-seo-monitor.service
sudo systemctl start tenderlex-seo-monitor.service
sudo systemctl status tenderlex-seo-monitor.service --no-pager
sudo systemctl cat tenderlex-seo-monitor.service
```

The service uses `DynamicUser=yes`, `ProtectHome=yes`, a private state directory,
and read-only bind mounts for only `backend/app`, the virtual environment, and
the collector script. Its only writable location is
`/var/lib/tenderlex-seo-monitor`; it cannot read the rest of `/root` or project
data. `LoadCredential` exposes only the two credential files to the process via
the systemd credential directory.

The one-shot run must return success only when required API sources are available.
Before the first closed instrumented day beginning on 2026-10-01 exists, unavailable
funnel goals are reported as `not_ready`, not as a collection failure. Once that
period exists, an unavailable task or download series makes the service fail.

Only after a clean manual run and review should an operator choose to enable the
daily 08:00 Europe/Moscow timer:

```bash
sudo systemctl enable --now tenderlex-seo-monitor.timer
```

## Current provider status (2026-10-20)

- **Google Search Console:** available via the read-only service account for `sc-domain:tenderlex.ru`; sitemap is accepted without errors. Use GSC as the live source for queries, pages and CTR.
- **Yandex Webmaster:** the OAuth token is valid, but `api.webmaster.yandex.net` is unreachable from the VPS (IPv4 timeout; the VPS has no IPv6 route). Cached SQI/indexed-page values are stale — do not treat them as current. Resolve with IPv6 or an approved egress before re-enabling freshness claims.
- **Yandex Wordstat:** the old API host no longer serves the API (404 / certificate mismatch). Do not present cached demand as measured; use a manual Wordstat export if needed.
- **Yandex Metrika:** available and consent-gated; counter IDs come from `TENDERLEX_YANDEX_METRIKA_ID` or `YANDEX_METRIKA_COUNTER_ID`. The SDK is intentionally absent until the visitor allows analytics.
- The monitor can still fail when Webmaster is unreachable. Treat `collection_complete=false` as a provider/network signal, not as proof that the site is broken.
- IndexNow is configured separately and may be used manually for changed URLs; it does not replace Webmaster query data.
