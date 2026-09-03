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
  local failed_line="${BASH_LINENO[0]}"
  trap - ERR
  set +e
  if [[ -n "${backend_id}" ]]; then
    "${compose[@]}" exec -T \
      -e PM_RESTORE_ARCHIVE="${archive_name:-unknown}" \
      -e PM_RESTORE_ERROR="Restore drill failed at line ${failed_line} (exit ${exit_code})." \
      backend python -c '
import os
from datetime import datetime, timezone
from app.services.backup import BackupService, write_restore_drill_status
message = os.environ["PM_RESTORE_ERROR"]
write_restore_drill_status({
    "status": "failed",
    "archive": os.environ.get("PM_RESTORE_ARCHIVE"),
    "error": message,
    "finished_at": datetime.now(timezone.utc).isoformat(),
})
BackupService._send_alert("restore_drill_failed", message)
' >/dev/null 2>&1
  fi
  echo "FAIL: restore drill stopped at line ${failed_line} (exit ${exit_code})." >&2
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
from app.services.backup import BackupService

destination = Path(os.environ["PM_RESTORE_SOURCE_DIR"])
destination.mkdir(parents=True, exist_ok=True)
db = SessionLocal()
try:
    service = BackupService(db)
    errors = []
    for label, target in service._targets(service.get_config()):
        try:
            service._download_and_prepare_archive(target, os.environ["PM_RESTORE_ARCHIVE"], destination)
            break
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    else:
        raise RuntimeError("No backup target could provide the archive: " + " | ".join(errors))
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

echo "[5/7] Verifying all restored document and note-image files against database storage keys ..."
docker run --rm --network "${network_name}" \
  -e DATABASE_URL="postgresql://restore_user:${db_password}@papermind-restore-db:5432/papermind_restore" \
  -v "${storage_volume}:/restore:ro" \
  --entrypoint python "${backend_image}" -c '
import os
import psycopg
from pathlib import Path
from app.services.backup import BackupService

root = Path("/restore/storage")
with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
    keys = BackupService._snapshot_storage_keys(connection)
BackupService._verify_snapshot_storage(root, keys)
print(f"verified storage keys: {len(keys)}")
'

if [[ -s "${drill_dir}/input/manifest.json" ]]; then
  echo "[5b/7] Verifying table counts and document/note metadata fingerprints ..."
  docker run --rm --network "${network_name}" \
    -e DATABASE_URL="postgresql://restore_user:${db_password}@papermind-restore-db:5432/papermind_restore" \
    -v "${drill_dir}/input:/input:ro" \
    --entrypoint python "${backend_image}" -c '
import json
import os
import psycopg
from app.services.backup import BackupService

manifest = json.load(open("/input/manifest.json", encoding="utf-8"))
with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
    actual = BackupService._snapshot_database_metadata(connection)
expected = manifest["database"]
BackupService._verify_database_metadata(actual, expected)
print("document and note metadata fingerprints verified")
'
fi

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

echo "[7/7] Reading restored documents, notes, revisions, templates, and files ..."
docker exec "${app_container}" python -c \
  'import urllib.request; assert urllib.request.urlopen("http://127.0.0.1:8040/api/documents?limit=1", timeout=5).status == 200'
document_id="$(docker exec -e PGPASSWORD="${db_password}" "${db_container}" \
  psql -At -U restore_user -d papermind_restore -c \
  'SELECT id FROM documents WHERE storage_key IS NOT NULL AND NOT is_deleted ORDER BY created_at DESC LIMIT 1')"
if [[ -n "${document_id}" ]]; then
  docker exec "${app_container}" python -c \
    "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8040/api/documents/${document_id}/file', timeout=10).status == 200"
fi

docker exec "${app_container}" python -c '
import json
import os
import urllib.request

import psycopg

base = "http://127.0.0.1:8040"

def read_json(path):
    with urllib.request.urlopen(base + path, timeout=10) as response:
        assert response.status == 200
        return json.load(response)

notes_by_id = {}
for path in ("/api/notes", "/api/notes?in_trash=true", "/api/notes/templates"):
    for item in read_json(path).get("items", []):
        notes_by_id[item["id"]] = item

block_templates = read_json("/api/notes/block-templates")
template_items = block_templates.get("items", [])
assert isinstance(template_items, list)

if notes_by_id:
    note_id = next(iter(notes_by_id))
    detail = read_json(f"/api/notes/{note_id}")
    assert detail["id"] == note_id and isinstance(detail.get("body_json"), dict)
    revisions = read_json(f"/api/notes/{note_id}/revisions")
    assert isinstance(revisions.get("items", []), list)

    note_ids = list(notes_by_id)
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        image = connection.execute(
            "SELECT note_id::text, id::text FROM note_image "
            "WHERE note_id::text = ANY(%s) ORDER BY created_at LIMIT 1",
            (note_ids,),
        ).fetchone()
    if image:
        with urllib.request.urlopen(
            f"{base}/api/notes/{image[0]}/images/{image[1]}/file", timeout=10
        ) as response:
            assert response.status == 200 and response.read(1)

print(
    f"verified notes: {len(notes_by_id)}; "
    f"block templates: {len(template_items)}"
)
'

note_count="$(docker exec -e PGPASSWORD="${db_password}" "${db_container}" \
  psql -At -U restore_user -d papermind_restore -c 'SELECT count(*) FROM note')"
[[ "${note_count}" =~ ^[0-9]+$ ]] || fail "Restored notes table is not readable."

"${compose[@]}" exec -T \
  -e PM_RESTORE_ARCHIVE="${archive_name}" \
  -e PM_RESTORE_DOCUMENTS="${document_count}" \
  -e PM_RESTORE_NOTES="${note_count}" \
  backend python -c '
import os
from datetime import datetime, timezone
from app.services.backup import write_restore_drill_status
write_restore_drill_status({
    "status": "success",
    "archive": os.environ["PM_RESTORE_ARCHIVE"],
    "documents": int(os.environ["PM_RESTORE_DOCUMENTS"]),
    "notes": int(os.environ["PM_RESTORE_NOTES"]),
    "verified_at": datetime.now(timezone.utc).isoformat(),
})
'

echo "PASS: restore drill succeeded for ${archive_name} (revision ${revision}, documents ${document_count}, notes ${note_count})."
