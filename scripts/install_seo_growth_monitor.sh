#!/usr/bin/env bash
set -euo pipefail

# Installs only the unit definitions and root-owned credential copies. It never
# enables or starts the timer; inspect the service first as described in docs/SEO_MONITORING.md.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
credential_source_dir="${1:?pass a root-owned directory containing seo-monitor.env and google-gsc.json}"
credential_target_dir="/root/.config/tenderlex"

[[ $EUID -eq 0 ]] || { printf '%s\n' 'Run this installer as root.' >&2; exit 1; }
[[ -f "$credential_source_dir/seo-monitor.env" && -f "$credential_source_dir/google-gsc.json" ]] || {
  printf '%s\n' 'Both required credential files are missing.' >&2
  exit 1
}

install -d -m 0700 "$credential_target_dir"
install -m 0600 "$credential_source_dir/seo-monitor.env" "$credential_target_dir/seo-monitor.env"
install -m 0600 "$credential_source_dir/google-gsc.json" "$credential_target_dir/google-gsc.json"
install -m 0644 "$project_root/deploy/systemd/tenderlex-seo-monitor.service" /etc/systemd/system/tenderlex-seo-monitor.service
install -m 0644 "$project_root/deploy/systemd/tenderlex-seo-monitor.timer" /etc/systemd/system/tenderlex-seo-monitor.timer
systemctl daemon-reload
systemctl disable --now tenderlex-seo-monitor.timer 2>/dev/null || true
systemctl reset-failed tenderlex-seo-monitor.service 2>/dev/null || true
systemd-analyze verify /etc/systemd/system/tenderlex-seo-monitor.service /etc/systemd/system/tenderlex-seo-monitor.timer
printf '%s\n' 'Installed and left disabled. Follow docs/SEO_MONITORING.md before any manual oneshot or enable action.'
