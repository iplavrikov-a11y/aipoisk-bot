#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
SITE_DIR="$ROOT_DIR/site"
DB_PATH="$ROOT_DIR/data/aipoisk.db"
BACKUP_DIR="$ROOT_DIR/data/backups"
STAMP="$(date -u +%Y%m%d%H%M%S)"
job_gate_pid=""
job_gate_in=""
job_gate_out=""
job_gate_open=0
services_touched=0

log() {
  printf '[deploy] %s\n' "$*"
}

curl_get() {
  curl -fsS --connect-timeout 3 --max-time 20 "$@"
}

curl_head() {
  curl -fsSI --connect-timeout 3 --max-time 20 "$@"
}

acquire_job_restart_gate() {
  local line

  coproc JOB_GATE { sqlite3 -batch "$DB_PATH"; }
  job_gate_pid="$JOB_GATE_PID"
  exec {job_gate_in}>&"${JOB_GATE[1]}"
  exec {job_gate_out}<&"${JOB_GATE[0]}"
  job_gate_open=1
  printf '%s\n' \
    '.bail on' \
    '.timeout 15000' \
    'BEGIN IMMEDIATE;' \
    "SELECT 'ACTIVE=' || count(*) FROM jobs WHERE status IN ('pending','running');" \
    >&"$job_gate_in"
  IFS= read -r line <&"$job_gate_out" || return 1
  [[ "$line" == ACTIVE=* ]] || return 1
  active_jobs="${line#ACTIVE=}"
  [[ "$active_jobs" =~ ^[0-9]+$ ]]
}

release_job_restart_gate() {
  local action="${1:-ROLLBACK}"
  if [[ "$job_gate_open" != "1" ]]; then
    return 0
  fi

  printf '%s;\n.quit\n' "$action" >&"$job_gate_in" 2>/dev/null || true
  exec {job_gate_in}>&- || true
  wait "$job_gate_pid" 2>/dev/null || true
  exec {job_gate_out}<&- || true
  job_gate_open=0
}

on_exit() {
  local exit_code=$?
  trap - EXIT
  set +e
  release_job_restart_gate ROLLBACK
  if [[ "$exit_code" != "0" && "$services_touched" == "1" ]]; then
    log "restoring TenderLex services after deploy interruption"
    systemctl start \
      tender-source-service.service \
      aipoisk-api.service \
      aipoisk-worker.service \
      aipoisk-bot.service \
      tenderlex-site.service
  fi
  exit "$exit_code"
}

trap on_exit EXIT

wait_for_url() {
  local url="$1"
  local attempts="${2:-30}"
  local delay="${3:-1}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl_get "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  curl_get "$url" >/dev/null
}

active_job_count() {
  if [[ ! -f "$DB_PATH" ]]; then
    log "job database is missing: $DB_PATH" >&2
    return 1
  fi
  sqlite3 -readonly "$DB_PATH" \
    "select count(*) from jobs where status in ('pending', 'running');"
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
  log "creating WAL-safe sqlite backup at $backup_path"
  sqlite3 "$DB_PATH" ".timeout 10000" ".backup '$backup_path'"
  backup_check="$(sqlite3 -readonly "$backup_path" "PRAGMA quick_check;")"
  if [[ "$backup_check" != "ok" ]]; then
    log "sqlite backup integrity check failed: $backup_check"
    exit 1
  fi
  log "sqlite backup verified"
fi

log "restarting production services"
active_jobs="$(active_job_count)"
if [[ "${AIPOISK_FORCE_JOB_SERVICE_RESTART:-0}" != "0" ]]; then
  log "forced job-service restart is disabled for safe deploys"
  exit 1
fi
if [[ "$active_jobs" != "0" ]]; then
  log "deploy blocked because active jobs are present: $active_jobs"
  exit 1
fi

services_touched=1
systemctl restart tender-source-service.service
wait_for_url http://127.0.0.1:8096/ready 30 1
curl_get http://127.0.0.1:8096/ready \
  | jq -e '.ok == true and .tenderplan.ok == true' >/dev/null
curl_get http://127.0.0.1:8096/health/eis \
  | jq -e '.ok == true and .via_proxy == true' >/dev/null

log "acquiring the final durable job restart fence"
acquire_job_restart_gate
if [[ "$active_jobs" != "0" ]]; then
  log "deploy blocked because active jobs are present at the restart fence: $active_jobs"
  exit 1
fi

log "stopping job services before updating the shared browser runtime"
systemctl stop \
  aipoisk-api.service \
  aipoisk-worker.service \
  aipoisk-bot.service

log "ensuring compatible Playwright headless Chromium"
"$BACKEND_DIR/.venv/bin/python" -m playwright install --only-shell chromium

systemctl start \
  aipoisk-api.service \
  aipoisk-worker.service \
  aipoisk-bot.service
release_job_restart_gate COMMIT
systemctl restart tenderlex-site.service

log "checking service state"
systemctl is-active --quiet tender-source-service.service
systemctl is-active --quiet aipoisk-api.service
systemctl is-active --quiet aipoisk-worker.service
systemctl is-active --quiet aipoisk-bot.service
systemctl is-active --quiet tenderlex-site.service

log "checking live API payload"
wait_for_url http://127.0.0.1:8088/api/health/ready 30 1
curl_get http://127.0.0.1:8088/api/health/ready \
  | jq -e '.ok == true and .database.ok == true and .queue.ok == true and .queue.stale_running == 0 and .tender_source.ok == true' >/dev/null
wait_for_url http://127.0.0.1:8088/api/public/site 30 1
curl_get http://127.0.0.1:8088/api/public/site | rg -q '"contacts"'
curl_get http://127.0.0.1:8088/api/public/site | rg -q '"max"'

log "checking live site routes"
wait_for_url http://127.0.0.1:3093/ 30 1
wait_for_url http://127.0.0.1:3093/cabinet 30 1
curl_head http://127.0.0.1:3093/ >/dev/null
curl_head http://127.0.0.1:3093/cabinet >/dev/null

log "checking metrika placement"
[[ "$(curl_get http://127.0.0.1:3093/cabinet | tr '<' '\n' | rg -o 'mc\.yandex\.ru|yandex-metrika|metrika' | wc -l)" == "0" ]]
[[ "$(curl_get http://127.0.0.1:3093/ | tr '<' '\n' | rg -o 'mc\.yandex\.ru|yandex-metrika|metrika' | wc -l)" != "0" ]]

log "checking procurement resource slice placement"
for service in \
  tender-source-service.service \
  aipoisk-api.service \
  aipoisk-worker.service \
  aipoisk-bot.service \
  tenderlex-site.service; do
  control_group="$(systemctl show "$service" --property=ControlGroup --value)"
  [[ "$control_group" == /procurement.slice/procurement-tenderlex.slice/* ]]
done

services_touched=0
log "live deploy verified"
