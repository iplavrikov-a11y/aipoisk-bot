#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
SITE_DIR="$ROOT_DIR/site"
DB_PATH="$ROOT_DIR/data/aipoisk.db"
BACKUP_DIR="$ROOT_DIR/data/backups"
STAMP="$(date -u +%Y%m%d%H%M%S)"

log() {
  printf '[deploy] %s\n' "$*"
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-30}"
  local delay="${3:-1}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  curl -fsS "$url" >/dev/null
}

active_job_count() {
  if [[ ! -f "$DB_PATH" ]]; then
    printf '0'
    return 0
  fi
  sqlite3 "$DB_PATH" "select count(*) from jobs where status='pending' or (status='running' and (updated_at is null or updated_at >= datetime('now', '-30 minutes')));"
}

site_systemd_env() {
  local key="$1"
  local env_line
  env_line="$(systemctl show tenderlex-site.service --property=Environment --value 2>/dev/null || true)"
  for item in $env_line; do
    case "$item" in
      "$key="*) printf '%s' "${item#*=}"; return 0 ;;
    esac
  done
  return 0
}

export AIPOISK_SITE_API_BASE_URL="${AIPOISK_SITE_API_BASE_URL:-http://127.0.0.1:8088}"
export NEXT_PUBLIC_SITE_URL="${NEXT_PUBLIC_SITE_URL:-https://tenderlex.ru}"
export TENDERLEX_YANDEX_METRIKA_ID="${TENDERLEX_YANDEX_METRIKA_ID:-$(site_systemd_env TENDERLEX_YANDEX_METRIKA_ID)}"
export TENDERLEX_YANDEX_VERIFICATION="${TENDERLEX_YANDEX_VERIFICATION:-$(site_systemd_env TENDERLEX_YANDEX_VERIFICATION)}"
export TENDERLEX_GOOGLE_SITE_VERIFICATION="${TENDERLEX_GOOGLE_SITE_VERIFICATION:-$(site_systemd_env TENDERLEX_GOOGLE_SITE_VERIFICATION)}"

cd "$ROOT_DIR"

log "running backend tests"
PYTHONPATH="$BACKEND_DIR" pytest backend/tests -q

log "building admin frontend"
(cd "$FRONTEND_DIR" && npm run build)

log "typechecking and building public site"
(cd "$SITE_DIR" && npm run typecheck && npm run build)

if [[ -f "$DB_PATH" ]]; then
  mkdir -p "$BACKUP_DIR"
  backup_path="$BACKUP_DIR/aipoisk-before-live-deploy-$STAMP.db"
  log "backing up sqlite database to $backup_path"
  cp "$DB_PATH" "$backup_path"
fi

log "restarting production services"
active_jobs="$(active_job_count)"
if [[ "${AIPOISK_FORCE_JOB_SERVICE_RESTART:-0}" == "1" || "$active_jobs" == "0" ]]; then
  systemctl restart aipoisk-api.service
  systemctl restart aipoisk-worker.service
  systemctl restart aipoisk-bot.service
else
  log "skipping api/worker/bot restart because active jobs are present: $active_jobs"
fi
systemctl restart tenderlex-site.service

log "checking service state"
systemctl is-active --quiet aipoisk-api.service
systemctl is-active --quiet aipoisk-worker.service
systemctl is-active --quiet aipoisk-bot.service
systemctl is-active --quiet tenderlex-site.service

log "checking live API payload"
wait_for_url http://127.0.0.1:8088/api/public/site 30 1
curl -fsS http://127.0.0.1:8088/api/public/site | rg -q '"contacts"'
curl -fsS http://127.0.0.1:8088/api/public/site | rg -q '"max"'

log "checking live site routes"
wait_for_url http://127.0.0.1:3093/ 30 1
wait_for_url http://127.0.0.1:3093/cabinet 30 1
curl -fsSI http://127.0.0.1:3093/ >/dev/null
curl -fsSI http://127.0.0.1:3093/cabinet >/dev/null

log "checking metrika placement"
[[ "$(curl -fsS http://127.0.0.1:3093/cabinet | tr '<' '\n' | rg -o 'mc\.yandex\.ru|yandex-metrika|metrika' | wc -l)" == "0" ]]
[[ "$(curl -fsS http://127.0.0.1:3093/ | tr '<' '\n' | rg -o 'mc\.yandex\.ru|yandex-metrika|metrika' | wc -l)" != "0" ]]

log "live deploy verified"
