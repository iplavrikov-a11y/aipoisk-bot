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
deploy_scope="${AIPOISK_DEPLOY_SCOPE:-full}"
site_release_root=""
site_release_dir=""
site_next_backup=""
site_next_promoted=0

log() {
  printf '[deploy] %s\n' "$*"
}

case "$deploy_scope" in
  full|backend|site) ;;
  *)
    log "unknown AIPOISK_DEPLOY_SCOPE: $deploy_scope (expected full, backend or site)" >&2
    exit 2
    ;;
esac

curl_get() {
  curl -fsS --connect-timeout 3 --max-time 20 "$@"
}

curl_head() {
  curl -fsSI --connect-timeout 3 --max-time 20 "$@"
}

verify_minprom_registry_runtime() {
  local worker_pid worker_pythonpath worker_registry_dir

  PYTHONPATH="$BACKEND_DIR" \
    SUPPLIER_MINPROM_REGISTRY_CACHE_DIR="${SUPPLIER_MINPROM_REGISTRY_CACHE_DIR:-$ROOT_DIR/data/minprom_registry}" \
    "$BACKEND_DIR/.venv/bin/python" - <<'PY'
from pathlib import Path

from app.supplier_search import get_minprom_registry_cache_status

status = get_minprom_registry_cache_status()
if not status["sqlite_ready"] or int(status["sqlite_entry_count"]) <= 0:
    raise SystemExit("Minprom registry cache is not ready for supplier searches")
if not Path(status["index_path"]).is_file() or not Path(status["sqlite_path"]).is_file():
    raise SystemExit("Minprom registry cache paths are unavailable")
PY

  worker_pid="$(systemctl show aipoisk-worker.service --property=MainPID --value)"
  [[ "$worker_pid" =~ ^[1-9][0-9]*$ ]] || {
    log "worker process is unavailable for Minprom registry verification" >&2
    return 1
  }
  worker_pythonpath="$(tr '\0' '\n' <"/proc/$worker_pid/environ" | sed -n 's/^PYTHONPATH=//p' | head -n 1)"
  worker_registry_dir="$(tr '\0' '\n' <"/proc/$worker_pid/environ" | sed -n 's/^SUPPLIER_MINPROM_REGISTRY_CACHE_DIR=//p' | head -n 1)"
  [[ -n "$worker_pythonpath" && -d "$worker_pythonpath/app" ]] || {
    log "worker code path is unavailable for Minprom registry verification" >&2
    return 1
  }
  [[ -n "$worker_registry_dir" ]] || {
    log "worker has no shared Minprom registry cache directory configured" >&2
    return 1
  }

  SUPPLIER_MINPROM_REGISTRY_CACHE_DIR="$worker_registry_dir" \
    "$BACKEND_DIR/.venv/bin/python" -P -c "
import sys
sys.path.insert(0, r'''$worker_pythonpath''')
from app.supplier_search import get_minprom_registry_cache_status
status = get_minprom_registry_cache_status()
assert status['sqlite_ready'] and int(status['sqlite_entry_count']) > 0, status
"
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

cleanup_site_release() {
  if [[ -n "$site_release_root" && "$site_release_root" == "$ROOT_DIR"/.tenderlex-site-release-* && -d "$site_release_root" ]]; then
    rm -rf -- "$site_release_root"
  fi
}

restore_previous_site_build() {
  if [[ "$site_next_promoted" != "1" || -z "$site_next_backup" || ! -d "$site_next_backup" ]]; then
    return 0
  fi

  log "restoring the previous TenderLex site build"
  systemctl stop tenderlex-site.service || true
  if [[ -d "$SITE_DIR/.next" ]]; then
    mv "$SITE_DIR/.next" "$site_release_root/.next.failed-after-promotion" || true
  fi
  mv "$site_next_backup" "$SITE_DIR/.next"
  site_next_promoted=0
}

on_exit() {
  local exit_code=$?
  trap - EXIT
  set +e
  release_job_restart_gate ROLLBACK
  if [[ "$exit_code" != "0" ]]; then
    restore_previous_site_build
  fi
  cleanup_site_release
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

validate_site_release() {
  local next_dir="$1"
  local required_path
  local -a required_paths=(
    "$next_dir/BUILD_ID"
    "$next_dir/routes-manifest.json"
    "$next_dir/prerender-manifest.json"
    "$next_dir/standalone/server.js"
    "$next_dir/standalone/.next/server/app/cabinet/page_client-reference-manifest.js"
    "$next_dir/standalone/.next/server/app/_not-found/page_client-reference-manifest.js"
  )

  for required_path in "${required_paths[@]}"; do
    if [[ ! -s "$required_path" ]]; then
      log "site release is incomplete: missing $required_path" >&2
      return 1
    fi
  done
}

build_site_release() {
  site_release_root="$(mktemp -d "$ROOT_DIR/.tenderlex-site-release-$STAMP.XXXXXX")"
  site_release_dir="$site_release_root/site"
  mkdir -p "$site_release_dir"

  # Build away from the live standalone tree so an interrupted Next build cannot break requests in flight.
  tar -C "$SITE_DIR" --exclude='./.next*' --exclude='./node_modules' -cf - . | tar -C "$site_release_dir" -xf -
  cp -al "$SITE_DIR/node_modules" "$site_release_dir/node_modules"

  (cd "$site_release_dir" && npm run typecheck && npm run build)
  validate_site_release "$site_release_dir/.next"
}

promote_site_release() {
  mkdir -p "$BACKUP_DIR/tenderlex-site"
  site_next_backup="$BACKUP_DIR/tenderlex-site/.next-$STAMP"
  if [[ ! -d "$SITE_DIR/.next" ]]; then
    log "live site build is missing: $SITE_DIR/.next" >&2
    return 1
  fi
  if [[ -e "$site_next_backup" ]]; then
    log "site rollback path already exists: $site_next_backup" >&2
    return 1
  fi

  mv "$SITE_DIR/.next" "$site_next_backup"
  site_next_promoted=1
  mv "$site_release_dir/.next" "$SITE_DIR/.next"
  log "site build promoted; previous build retained at $site_next_backup"
}

export AIPOISK_SITE_API_BASE_URL="${AIPOISK_SITE_API_BASE_URL:-http://127.0.0.1:8088}"
export NEXT_PUBLIC_SITE_URL="${NEXT_PUBLIC_SITE_URL:-https://tenderlex.ru}"
export TENDERLEX_YANDEX_METRIKA_ID="${TENDERLEX_YANDEX_METRIKA_ID:-$(site_systemd_env TENDERLEX_YANDEX_METRIKA_ID)}"
export TENDERLEX_YANDEX_VERIFICATION="${TENDERLEX_YANDEX_VERIFICATION:-$(site_systemd_env TENDERLEX_YANDEX_VERIFICATION)}"
export TENDERLEX_GOOGLE_SITE_VERIFICATION="${TENDERLEX_GOOGLE_SITE_VERIFICATION:-$(site_systemd_env TENDERLEX_GOOGLE_SITE_VERIFICATION)}"

cd "$ROOT_DIR"

if [[ "$deploy_scope" != "site" ]]; then
  log "running backend tests"
  PYTHONPATH="$BACKEND_DIR" pytest ${AIPOISK_DEPLOY_TESTS:-backend/tests} -q
fi

if [[ "$deploy_scope" == "full" ]]; then
  log "building admin frontend"
  (cd "$FRONTEND_DIR" && npm run build)

  log "building isolated public site release"
  build_site_release
elif [[ "$deploy_scope" == "site" ]]; then
  log "site scope: building isolated public site release"
  build_site_release
else
  # A backend-only deploy must not publish unrelated, uncommitted web assets.
  log "backend scope: leaving admin and site artifacts unchanged"
fi

if [[ "$deploy_scope" != "site" && -f "$DB_PATH" ]]; then
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

if [[ "$deploy_scope" == "site" ]]; then
  log "site scope: promoting the public site without restarting backend job services"
  services_touched=1
  promote_site_release
  systemctl restart tenderlex-site.service
else
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
  if [[ "$deploy_scope" == "full" ]]; then
    promote_site_release
    systemctl restart tenderlex-site.service
  fi
fi

log "checking service state"
systemctl is-active --quiet tenderlex-site.service
if [[ "$deploy_scope" != "site" ]]; then
  systemctl is-active --quiet tender-source-service.service
  systemctl is-active --quiet aipoisk-api.service
  systemctl is-active --quiet aipoisk-worker.service
  systemctl is-active --quiet aipoisk-bot.service

  log "checking shared Minprom registry cache in API and worker runtimes"
  verify_minprom_registry_runtime

  log "checking live API payload"
  wait_for_url http://127.0.0.1:8088/api/health/ready 30 1
  curl_get http://127.0.0.1:8088/api/health/ready \
    | jq -e '.ok == true and .database.ok == true and .queue.ok == true and .queue.stale_running == 0 and .tender_source.ok == true' >/dev/null
  wait_for_url http://127.0.0.1:8088/api/public/site 30 1
  curl_get http://127.0.0.1:8088/api/public/site | rg -q '"contacts"'
  curl_get http://127.0.0.1:8088/api/public/site | rg -q '"max"'
fi

log "checking live site routes"
wait_for_url http://127.0.0.1:3093/ 30 1
wait_for_url http://127.0.0.1:3093/cabinet 30 1
curl_head http://127.0.0.1:3093/ >/dev/null
curl_head http://127.0.0.1:3093/cabinet >/dev/null

if [[ "$deploy_scope" == "full" || "$deploy_scope" == "site" ]]; then
  log "checking analytics consent gate"
  [[ "$(curl_get http://127.0.0.1:3093/cabinet | tr '<' '\n' | rg -o 'mc\.yandex\.ru|yandex-metrika|metrika' | wc -l)" == "0" ]]
  [[ "$(curl_get http://127.0.0.1:3093/ | tr '<' '\n' | rg -o 'mc\.yandex\.ru|yandex-metrika' | wc -l)" == "0" ]]
  curl_get http://127.0.0.1:3093/ | rg -q 'cookie-consent|Разрешить аналитику'
fi

log "checking procurement resource slice placement"
if [[ "$deploy_scope" == "site" ]]; then
  services=(tenderlex-site.service)
else
  services=(
    tender-source-service.service
    aipoisk-api.service
    aipoisk-worker.service
    aipoisk-bot.service
    tenderlex-site.service
  )
fi
for service in "${services[@]}"; do
  control_group="$(systemctl show "$service" --property=ControlGroup --value)"
  [[ "$control_group" == /procurement.slice/procurement-tenderlex.slice/* ]]
done

services_touched=0
cleanup_site_release
log "live deploy verified"
