#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/prod_pi_fast_scans.sh [options]

Reduce scanner import latency on the production Pi by tuning worker polling.

Options:
  --poll-seconds <n>    Worker scan-folder poll interval (default: 1)
  --stable-seconds <n>  Required PDF quiet time before import (default: 1)
  --no-restart          Update .env.prod only; do not restart the worker
  -h, --help            Show this help
EOF
}

POLL_SECONDS=1
STABLE_SECONDS=1
RESTART_WORKER=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --poll-seconds)
      shift
      POLL_SECONDS="${1:-}"
      ;;
    --stable-seconds)
      shift
      STABLE_SECONDS="${1:-}"
      ;;
    --no-restart)
      RESTART_WORKER=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

log() { printf '[prod-fast-scans] %s\n' "$*"; }
die() { printf '[prod-fast-scans] ERROR: %s\n' "$*" >&2; exit 1; }

validate_positive_int() {
  local name="$1"
  local value="$2"
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || die "${name} must be a positive integer"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local file=".env.prod"
  if grep -qE "^${key}=" "${file}"; then
    sed -i "s/^${key}=.*/${key}=${value}/" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

[[ -f .env.prod ]] || die "Missing .env.prod"
command -v docker >/dev/null 2>&1 || die "Missing required command: docker"
validate_positive_int "poll seconds" "${POLL_SECONDS}"
validate_positive_int "stable seconds" "${STABLE_SECONDS}"

backup=".env.prod.fast-scans.$(date +%Y%m%d%H%M%S).bak"
cp .env.prod "${backup}"
log "Backed up .env.prod to ${backup}"

set_env_value "WORKER_POLL_INTERVAL_SECONDS" "${POLL_SECONDS}"
set_env_value "IMPORT_INBOX_FILE_STABLE_SECONDS" "${STABLE_SECONDS}"
log "Set WORKER_POLL_INTERVAL_SECONDS=${POLL_SECONDS}"
log "Set IMPORT_INBOX_FILE_STABLE_SECONDS=${STABLE_SECONDS}"

if [[ "${RESTART_WORKER}" -eq 1 ]]; then
  log "Restarting production worker"
  docker compose --env-file .env.prod -f docker-compose.prod.yml up -d worker
  docker compose --env-file .env.prod -f docker-compose.prod.yml ps worker
fi

log "Done"
