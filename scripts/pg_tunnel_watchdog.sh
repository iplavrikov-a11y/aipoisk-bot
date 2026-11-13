#!/usr/bin/env bash
set -u
exec /root/projects/tenderlex/backend/.venv/bin/python /root/projects/tenderlex/scripts/pg_tunnel_watchdog.py
