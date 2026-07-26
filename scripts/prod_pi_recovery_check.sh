#!/usr/bin/env bash
# Kontrollierter Recovery-Test für eine laufende PaperMind-Produktivinstanz.
#
# Der Lauf verursacht kurze, absichtliche Ausfälle von KI, Datenbank und Worker.
# Deshalb ist er nur mit --confirm-production möglich. Er verändert weder
# Dokumente noch Backups und führt keinen Restore aus; geprüft werden
# Backup-Verbindung und die Vollständigkeit vorhandener Archive.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/prod_pi_recovery_check.sh --confirm-production

Prüft kontrolliert:
  - Docker-Memory-Limits (isolierter OOM-Test)
  - KI- und DB-Ausfall mit Wiederanlauf der Bereitschaftsprüfung
  - Worker-Neustart und Healthcheck
  - NAS-Schreibzugriff sowie vollständige vorhandene Backup-Archive

Der Test stoppt KI, DB und Worker jeweils kurz. Nicht während eines geplanten
Backups oder eines zeitkritischen Imports ausführen.
EOF
}

if [[ "${1:-}" != "--confirm-production" || $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

if [[ ! -f .env.prod ]]; then
  echo "Error: .env.prod is required; run this on the Pi production checkout." >&2
  exit 2
fi

compose=(docker compose --env-file .env.prod -f docker-compose.prod.yml)
recovery_needed=0

recover_services() {
  if [[ "${recovery_needed}" -eq 1 ]]; then
    echo "Recovery guard: starting all PaperMind services ..." >&2
    "${compose[@]}" up -d --wait db ai backend worker frontend >/dev/null || true
  fi
}
trap recover_services EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

backend_ready() {
  "${compose[@]}" exec -T backend python -c \
    'import urllib.request; response = urllib.request.urlopen("http://127.0.0.1:8040/health/ready", timeout=3); raise SystemExit(0 if response.status == 200 else 1)'
}

wait_for_backend_ready() {
  local deadline=$((SECONDS + 90))
  until backend_ready >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      fail "Backend did not become ready within 90 seconds."
    fi
    sleep 2
  done
}

assert_backend_unready() {
  if backend_ready >/dev/null 2>&1; then
    fail "Backend stayed ready although its dependency was deliberately stopped."
  fi
}

assert_healthy() {
  local service="$1"
  "${compose[@]}" up -d --wait "${service}" >/dev/null
}

echo "[1/6] Checking current service health ..."
for service in db ai backend worker frontend; do
  assert_healthy "${service}"
done
wait_for_backend_ready

echo "[2/6] Checking enforced Docker memory limits ..."
backend_image="$("${compose[@]}" images -q backend | head -n 1)"
[[ -n "${backend_image}" ]] || fail "Backend image is not available."
set +e
docker run --rm --memory=64m --memory-swap=64m --entrypoint python "${backend_image}" \
  -c 'bytearray(128 * 1024 * 1024)' >/dev/null 2>&1
oom_exit=$?
set -e
[[ "${oom_exit}" -eq 137 ]] || fail "Expected isolated OOM exit 137, got ${oom_exit}."

echo "[3/6] Simulating AI outage and recovery ..."
recovery_needed=1
"${compose[@]}" stop ai >/dev/null
assert_backend_unready
assert_healthy ai
wait_for_backend_ready

echo "[4/6] Simulating database outage and recovery ..."
"${compose[@]}" stop db >/dev/null
assert_backend_unready
assert_healthy db
wait_for_backend_ready

echo "[5/6] Restarting worker and verifying its heartbeat ..."
"${compose[@]}" restart worker >/dev/null
assert_healthy worker

echo "[6/6] Verifying backup target and restore inputs (non-destructive) ..."
"${compose[@]}" exec -T backend python -c '
from app.db.session import SessionLocal
from app.services.backup import BackupService

db = SessionLocal()
try:
    service = BackupService(db)
    result = service.test_connection()
    assert result.get("ok"), result
    archives = service.list_archives()
    assert any(item.get("complete") for item in archives), "No complete backup archive found"
    print("backup target ok; complete archives: {}".format(sum(bool(item.get("complete")) for item in archives)))
finally:
    db.close()
'

recovery_needed=0
echo "PASS: controlled recovery suite completed successfully."
