#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
install -m 0644 "$repo_dir/deploy/systemd/tenderlex-seo-admin.service" /etc/systemd/system/tenderlex-seo-admin.service
install -m 0644 "$repo_dir/deploy/systemd/tenderlex-seo-admin.timer" /etc/systemd/system/tenderlex-seo-admin.timer
systemd-analyze verify /etc/systemd/system/tenderlex-seo-admin.service /etc/systemd/system/tenderlex-seo-admin.timer
systemctl daemon-reload
systemctl enable --now tenderlex-seo-admin.timer
systemctl start tenderlex-seo-admin.service
systemctl show tenderlex-seo-admin.service --property=Result --property=ExecMainStatus
systemctl show tenderlex-seo-admin.timer --property=ActiveState --property=NextElapseUSecMonotonic
