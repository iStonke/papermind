#!/usr/bin/env bash
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}" || exit 1

COMPOSE=(docker compose --env-file .env.prod -f docker-compose.prod.yml)

section() {
  printf '\n===== %s =====\n' "$*"
}

run() {
  printf '+ %s\n' "$*"
  "$@" 2>&1 || printf 'WARN: command failed: %s\n' "$*" >&2
}

run_sh() {
  printf '+ %s\n' "$*"
  sh -c "$*" 2>&1 || printf 'WARN: command failed: %s\n' "$*" >&2
}

section "Time / Host"
run date -Is
run hostnamectl
run uptime
run uname -a

section "Git"
run git branch --show-current
run git rev-parse --short HEAD
run git status --short
run ls -l backend/alembic/versions/053_scanner_import_inbox.py

section "Network"
run hostname -I
run ip -br address
run ip route
run_sh "ss -ltnp | sed -n '1,80p'"
run_sh "getent hosts papermind.local || true"
run_sh "getent hosts papermind || true"

section "Disk / Memory / Temperature"
run free -h
run df -h /
run df -h "${REPO_DIR}"
run_sh "command -v vcgencmd >/dev/null 2>&1 && vcgencmd measure_temp || true"
run_sh "command -v vcgencmd >/dev/null 2>&1 && vcgencmd get_throttled || true"

section "Docker Runtime"
run docker version
run docker info
run_sh "cat /proc/cgroups 2>/dev/null || true"
run_sh "mount | grep -E 'cgroup|docker' || true"

section "Compose Status"
run "${COMPOSE[@]}" ps
run docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
run docker stats --no-stream

section "Container Restart Counts"
run_sh "docker inspect papermind-ai-1 papermind-backend-1 papermind-caddy-1 papermind-db-1 papermind-frontend-1 papermind-worker-1 --format '{{.Name}} restart={{.RestartCount}} oom={{.State.OOMKilled}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' 2>/dev/null || true"

section "HTTP Health"
run_sh "curl -kfsS https://127.0.0.1/healthz && printf '\\n' || true"
run_sh "curl -fsS http://127.0.0.1/healthz && printf '\\n' || true"
run_sh "${COMPOSE[*]} exec -T backend python -c 'import urllib.request; print(urllib.request.urlopen(\"http://127.0.0.1:8040/health/ready\", timeout=3).read().decode())' || true"
run_sh "${COMPOSE[*]} exec -T ai python -c 'import urllib.request; print(urllib.request.urlopen(\"http://127.0.0.1:11439/health\", timeout=3).read().decode())' || true"

section "Recent Compose Logs"
run "${COMPOSE[@]}" logs --tail=80 backend
run "${COMPOSE[@]}" logs --tail=80 frontend
run "${COMPOSE[@]}" logs --tail=80 caddy
run "${COMPOSE[@]}" logs --tail=80 worker

section "Systemd Services"
run_sh "systemctl --no-pager --full status docker papermind-host-control papermind-scan-watch papermind-scan-idle.timer 2>/dev/null || true"

section "Kernel / Journal Warnings"
run_sh "journalctl -k -p warning..alert --since '2 hours ago' --no-pager 2>/dev/null | tail -200 || true"
run_sh "journalctl -u docker --since '2 hours ago' --no-pager 2>/dev/null | tail -160 || true"
run_sh "dmesg -T 2>/dev/null | grep -Ei 'oom|out of memory|under-voltage|voltage|thrott|thermal|usb|eth0|wlan|docker|cgroup' | tail -200 || true"

section "Done"
