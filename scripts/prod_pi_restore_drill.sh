#!/usr/bin/env bash
# Isolierter Restore-Drill: lädt ein vollständiges NAS-Archiv, stellt es in
# temporäre Docker-Ressourcen wieder her und liest es mit einem isolierten
# Backend. Die produktive DB und der produktive Dokumentenspeicher bleiben
# dabei unverändert.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/prod_pi_restore_drill.sh --confirm-production

Der Drill liest das neueste vollständige NAS-Archiv, stellt Datenbank und
Dokumentenspeicher in temporären Docker-Ressourcen wieder her und prüft einen
Dokumentabruf über ein isoliertes Backend. Er benötigt vorübergehend ungefähr
die dreifache Archivgröße an freiem Speicher unter /tmp.
EOF
}

if [[ "${1:-}" != "--confirm-production" || $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"
[[ -f .env.prod ]] || { echo "Error: .env.prod is required." >&2; exit 2; }

compose=(docker compose --env-file .env.prod -f docker-compose.prod.yml)
run_id="$(date +%Y%m%d%H%M%S)-$$"
drill_dir="$(mktemp -d /tmp/papermind-restore-drill.XXXXXX)"
source_dir="/tmp/papermind-restore-source-${run_id}"
db_container="papermind-restore-db-${run_id}"
app_container="papermind-restore-app-${run_id}"
storage_volume="papermind_restore_storage_${run_id}"
db_password="$(openssl rand -hex 24)"
backend_id=""

cleanup() {
  [[ -n "${app_container}" ]] && docker rm -f "${app_container}" >/dev/null 2>&1 || true
  [[ -n "${db_container}" ]] && docker rm -f "${db_container}" >/dev/null 2>&1 || true
  [[ -n "${storage_volume}" ]] && docker volume rm -f "${storage_volume}" >/dev/null 2>&1 || true
  [[ -n "${backend_id}" ]] && docker exec "${backend_id}" rm -rf "${source_dir}" >/dev/null 2>&1 || true
  rm -rf "${drill_dir}"
}
trap cleanup EXIT

report_error() {
  local exit_code=$?
  echo "FAIL: restore drill stopped at line ${BASH_LINENO[0]} (exit ${exit_code})." >&2
  exit "${exit_code}"
}
trap report_error ERR

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

wait_for() {
  local description="$1"
  shift
  local deadline=$((SECONDS + 120))
  until "$@" >/dev/null 2>&1; do
    (( SECONDS < deadline )) || fail "Timed out waiting for ${description}."
    sleep 2
  done
}

echo "[1/7] Selecting the newest complete archive from the NAS ..."
backend_id="$("${compose[@]}" ps -q backend)"
[[ -n "${backend_id}" ]] || fail "Production backend container is not running."
archive_data="$("${compose[@]}" exec -T backend python -c '
from app.db.session import SessionLocal
from app.services.backup import BackupService
db = SessionLocal()
try:
    archive = next((item for item in BackupService(db).list_archives() if item.get("complete")), None)
    assert archive is not None, "No complete archive found"
    print("{}|{}".format(archive["name"], int(archive["size_bytes"])))
finally:
    db.close()
')"
archive_name="${archive_data%%|*}"
archive_size="${archive_data##*|}"
[[ "${archive_name}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{6}$ ]] || fail "Invalid archive name returned."
[[ "${archive_size}" =~ ^[0-9]+$ ]] || fail "Invalid archive size returned."

available_bytes="$(df -Pk /tmp | awk 'NR == 2 { print $4 * 1024 }')"
required_bytes=$((archive_size * 3 + 1073741824))
(( available_bytes >= required_bytes )) || fail "Insufficient free /tmp space for isolated restore drill."

echo "[2/7] Downloading ${archive_name} into an isolated temporary directory ..."
"${compose[@]}" exec -T \
  -e PM_RESTORE_SOURCE_DIR="${source_dir}" \
  -e PM_RESTORE_ARCHIVE="${archive_name}" \
  backend python -c '
import os
from pathlib import Path
from app.db.session import SessionLocal
from app.services.backup import BackupService, _SmbTarget

destination = Path(os.environ["PM_RESTORE_SOURCE_DIR"])
destination.mkdir(parents=True, exist_ok=True)
db = SessionLocal()
try:
    service = BackupService(db)
    target = _SmbTarget.from_config(service.get_config())
    target.validate()
    BackupService._download(target, os.environ["PM_RESTORE_ARCHIVE"], "database.dump", destination / "database.dump")
    BackupService._download(target, os.environ["PM_RESTORE_ARCHIVE"], "storage.tar.gz", destination / "storage.tar.gz")
finally:
    db.close()
'
mkdir -p "${drill_dir}/input"
docker cp "${backend_id}:${source_dir}/." "${drill_dir}/input"
[[ -s "${drill_dir}/input/database.dump" && -s "${drill_dir}/input/storage.tar.gz" ]] || fail "Downloaded archive is incomplete."

echo "[3/7] Restoring the database into a disposable PostgreSQL container ..."
network_name="$(docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}' "${backend_id}")"
[[ -n "${network_name}" ]] || fail "Could not determine PaperMind Docker network."
docker run -d --rm --name "${db_container}" --network "${network_name}" \
  --network-alias papermind-restore-db \
  -e POSTGRES_DB=papermind_restore \
  -e POSTGRES_USER=restore_user \
  -e POSTGRES_PASSWORD="${db_password}" \
  pgvector/pgvector:pg17 >/dev/null
wait_for "temporary PostgreSQL" docker exec "${db_container}" pg_isready -U restore_user -d papermind_restore
docker cp "${drill_dir}/input/database.dump" "${db_container}:/tmp/database.dump"
docker exec -e PGPASSWORD="${db_password}" "${db_container}" \
  pg_restore --exit-on-error --no-owner --no-acl \
  --username=restore_user --dbname=papermind_restore /tmp/database.dump

document_count="$(docker exec -e PGPASSWORD="${db_password}" "${db_container}" \
  psql -At -U restore_user -d papermind_restore -c 'SELECT count(*) FROM documents')"
[[ "${document_count}" =~ ^[0-9]+$ ]] || fail "Restored documents table is not readable."
revision="$(docker exec -e PGPASSWORD="${db_password}" "${db_container}" \
  psql -At -U restore_user -d papermind_restore -c 'SELECT version_num FROM alembic_version LIMIT 1')"
[[ -n "${revision}" ]] || fail "Restored Alembic revision is missing."

echo "[4/7] Restoring the document storage into a disposable Docker volume ..."
docker volume create "${storage_volume}" >/dev/null
backend_image="$("${compose[@]}" images -q backend | head -n 1)"
[[ -n "${backend_image}" ]] || fail "Backend image is unavailable."
docker run --rm \
  -v "${drill_dir}/input:/input:ro" \
  -v "${storage_volume}:/restore" \
  --entrypoint python "${backend_image}" -c '
import shutil
import tarfile
from pathlib import Path

with tarfile.open("/input/storage.tar.gz", "r:gz") as archive:
    archive.extractall("/restore/unpacked", filter="data")
source = Path("/restore/unpacked/storage")
if not source.is_dir():
    source = Path("/restore/unpacked")
destination = Path("/restore/storage")
destination.mkdir(parents=True, exist_ok=True)
for child in source.iterdir():
    target = destination / child.name
    if child.is_dir():
        shutil.copytree(child, target, dirs_exist_ok=True)
    else:
        shutil.copy2(child, target)
'

echo "[5/7] Verifying restored document files against database storage keys ..."
docker exec -e PGPASSWORD="${db_password}" "${db_container}" \
  psql -At -U restore_user -d papermind_restore -c \
  'SELECT storage_key FROM documents WHERE storage_key IS NOT NULL AND NOT is_deleted ORDER BY storage_key' \
  | docker run --rm -i -v "${storage_volume}:/restore:ro" --entrypoint python "${backend_image}" -c '
import sys
from pathlib import Path

root = Path("/restore/storage")
keys = [line.strip() for line in sys.stdin if line.strip()]
missing = [key for key in keys if not (root / key).is_file()]
assert not missing, f"Missing restored document files: {missing[:5]}"
print(f"verified storage keys: {len(keys)}")
'

echo "[6/7] Starting an isolated backend against the restored data ..."
database_url="postgresql://restore_user:${db_password}@papermind-restore-db:5432/papermind_restore"
docker run -d --rm --name "${app_container}" --network "${network_name}" \
  -e DATABASE_URL="${database_url}" \
  -e APP_DATABASE_URL="${database_url}" \
  -e WORKER_DATABASE_URL="${database_url}" \
  -e AI_BASE_URL=http://ai:11439 \
  -e AUTH_ENABLED=false \
  -e AUTO_OCR_ON_UPLOAD=false \
  -e STORAGE_PATH=/restore/storage \
  -v "${storage_volume}:/restore:ro" \
  --entrypoint sh "${backend_image}" -c \
  'alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8040 --no-access-log' >/dev/null
wait_for "isolated backend readiness" docker exec "${app_container}" python -c \
  'import urllib.request; assert urllib.request.urlopen("http://127.0.0.1:8040/health/ready", timeout=3).status == 200'

echo "[7/7] Reading restored application data and a restored document file ..."
docker exec "${app_container}" python -c \
  'import urllib.request; assert urllib.request.urlopen("http://127.0.0.1:8040/api/documents?limit=1", timeout=5).status == 200'
document_id="$(docker exec -e PGPASSWORD="${db_password}" "${db_container}" \
  psql -At -U restore_user -d papermind_restore -c \
  'SELECT id FROM documents WHERE storage_key IS NOT NULL AND NOT is_deleted ORDER BY created_at DESC LIMIT 1')"
if [[ -n "${document_id}" ]]; then
  docker exec "${app_container}" python -c \
    "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8040/api/documents/${document_id}/file', timeout=10).status == 200"
fi

echo "PASS: restore drill succeeded for ${archive_name} (revision ${revision}, documents ${document_count})."
