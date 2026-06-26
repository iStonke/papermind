#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/prod_pi_stabilize.sh [options]

Idempotent production hardening for a Raspberry Pi PaperMind host.

Options:
  --no-build       Start containers without rebuilding images
  --no-compose     Configure host services only; do not run docker compose up
  --no-scanner     Skip Canon LiDE scan-button host services
  --no-docker-conf Skip Docker daemon log-rotation configuration
  -h, --help       Show this help
EOF
}

RUN_BUILD=1
RUN_COMPOSE=1
RUN_SCANNER=1
RUN_DOCKER_CONF=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build) RUN_BUILD=0 ;;
    --no-compose) RUN_COMPOSE=0 ;;
    --no-scanner) RUN_SCANNER=0 ;;
    --no-docker-conf) RUN_DOCKER_CONF=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"
SERVICE_USER="${SUDO_USER:-${USER}}"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"

log() { printf '[prod-stabilize] %s\n' "$*"; }
warn() { printf '[prod-stabilize] WARNING: %s\n' "$*" >&2; }
die() { printf '[prod-stabilize] ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

require_file() {
  [[ -f "$1" ]] || die "Missing required file: $1"
}

validate_env_prod() {
  require_file ".env.prod"
  if grep -nE '<[^>]+>' .env.prod; then
    die ".env.prod still contains placeholders. Fill them before production start."
  fi
  if ! grep -q '^AUTH_SECRET_KEY=.\{32,\}' .env.prod; then
    die ".env.prod must contain a strong AUTH_SECRET_KEY."
  fi
}

ensure_runtime_dirs() {
  log "Ensuring runtime directories"
  sudo install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0770 scan-inbox host-control backups
  sudo install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0775 .runtime .runtime/frontend-assets
  sudo chown -R "${SERVICE_USER}:${SERVICE_GROUP}" scan-inbox host-control backups .runtime
  chmod 0770 scan-inbox host-control backups
  chmod 0775 .runtime .runtime/frontend-assets
}

configure_docker_daemon() {
  [[ "${RUN_DOCKER_CONF}" -eq 1 ]] || return 0
  require_cmd python3
  log "Configuring Docker daemon log rotation"
  sudo install -d -m 0755 /etc/docker
  if sudo test -f /etc/docker/daemon.json; then
    sudo cp /etc/docker/daemon.json "/etc/docker/daemon.json.papermind.$(date +%Y%m%d%H%M%S).bak"
  fi
  sudo python3 - <<'PY'
import json
from pathlib import Path

path = Path("/etc/docker/daemon.json")
try:
    data = json.loads(path.read_text()) if path.exists() else {}
except Exception:
    data = {}

data.setdefault("log-driver", "json-file")
opts = data.setdefault("log-opts", {})
opts.setdefault("max-size", "10m")
opts.setdefault("max-file", "5")

path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY
  sudo systemctl enable docker >/dev/null
  sudo systemctl restart docker
}

install_host_control() {
  local watcher="${REPO_DIR}/deploy/host-control/papermind-host-control.sh"
  require_file "${watcher}"
  log "Installing host-control service"
  chmod +x "${watcher}"
  sudo tee /etc/systemd/system/papermind-host-control.service >/dev/null <<UNIT
[Unit]
Description=PaperMind Host-Control
After=multi-user.target

[Service]
Type=simple
Environment=CONTROL_DIR=${REPO_DIR}/host-control
Environment=POLL_INTERVAL=3
ExecStart=${watcher}
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  sudo systemctl enable --now papermind-host-control.service >/dev/null
}

install_scan_button_services() {
  [[ "${RUN_SCANNER}" -eq 1 ]] || return 0
  local scan_script="${REPO_DIR}/deploy/scan-button/papermind-scan.sh"
  local watch_script="${REPO_DIR}/deploy/scan-button/papermind-scan-watch.sh"
  require_file "${scan_script}"
  require_file "${watch_script}"

  log "Installing scanner packages and services"
  sudo apt-get update -qq
  sudo apt-get install -y -qq sane-utils img2pdf >/dev/null
  sudo usermod -aG scanner,lp "${SERVICE_USER}" || true

  sudo systemctl mask --now ipp-usb >/dev/null 2>&1 || true
  sudo systemctl disable --now scanbd >/dev/null 2>&1 || sudo systemctl mask scanbd >/dev/null 2>&1 || true

  chmod +x "${scan_script}" "${watch_script}"
  sudo tee /etc/systemd/system/papermind-scan-watch.service >/dev/null <<UNIT
[Unit]
Description=PaperMind Scan-Tasten-Poller (Canon LiDE 400)
After=multi-user.target docker.service

[Service]
Type=simple
ExecStart=${watch_script}
Restart=always
RestartSec=5
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
SupplementaryGroups=scanner lp

[Install]
WantedBy=multi-user.target
UNIT

  sudo tee /etc/systemd/system/papermind-scan-idle.service >/dev/null <<UNIT
[Unit]
Description=PaperMind Scan - Batch automatisch abschliessen

[Service]
Type=oneshot
Environment=IDLE_SECONDS=180
ExecStart=${scan_script} finalize-idle
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
SupplementaryGroups=scanner lp
UNIT

  sudo tee /etc/systemd/system/papermind-scan-idle.timer >/dev/null <<'UNIT'
[Unit]
Description=PaperMind Scan - Idle-Batch-Abschluss regelmaessig pruefen

[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
AccuracySec=15s

[Install]
WantedBy=timers.target
UNIT

  sudo systemctl daemon-reload
  sudo systemctl enable --now papermind-scan-watch.service >/dev/null
  sudo systemctl enable --now papermind-scan-idle.timer >/dev/null
}

run_compose() {
  [[ "${RUN_COMPOSE}" -eq 1 ]] || return 0
  local compose=(docker compose --env-file .env.prod -f docker-compose.prod.yml)
  local args=(up -d)
  if [[ "${RUN_BUILD}" -eq 1 ]]; then
    args+=(--build)
  fi
  log "Starting production stack: ${compose[*]} ${args[*]}"
  "${compose[@]}" "${args[@]}"
}

healthcheck() {
  local compose=(docker compose --env-file .env.prod -f docker-compose.prod.yml)
  log "Container status"
  "${compose[@]}" ps

  log "HTTP health checks"
  curl -fsS http://127.0.0.1/healthz >/dev/null || warn "Frontend healthz is not reachable yet"
  "${compose[@]}" exec -T backend python - <<'PY' || warn "Backend ready check failed"
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8040/health/ready", timeout=3)
PY
  "${compose[@]}" exec -T ai python - <<'PY' || warn "AI health check failed"
import urllib.request
urllib.request.urlopen("http://127.0.0.1:11439/health", timeout=3)
PY
}

require_cmd docker
require_cmd curl
validate_env_prod
ensure_runtime_dirs
configure_docker_daemon
install_host_control
install_scan_button_services
run_compose
healthcheck

log "Production stabilization complete"
