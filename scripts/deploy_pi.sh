#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy_pi.sh [options]

Bequemster Aufruf für ein volles Prod-Update (Code + alle Container neu
gebaut, inkl. Frontend):

  ./scripts/deploy_pi.sh --prod

Das entspricht "--prod --compose --build" - bei --prod werden Compose-Update
und -Build automatisch aktiviert, sofern nicht --code-only angegeben wird.

Options:
  --branch <name>  Git branch to update (default: current branch)
  --code-only      Bei --prod nur git pull, KEIN docker compose up
  --compose        Run docker compose up -d after git update
  --prod           Use docker-compose.prod.yml; impliziert --compose --build
                    (außer --code-only ist gesetzt)
  --build          Use --build with docker compose (implies --compose)
  --worker         Worker zusätzlich explizit neu starten (normalerweise
                    überflüssig, da --compose ohnehin alle Services inkl.
                    Worker aktualisiert)
  -h, --help       Show this help
EOF
}

BRANCH=""
RUN_COMPOSE=0
RUN_BUILD=0
RUN_WORKER=0
RUN_PROD=0
CODE_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      shift
      BRANCH="${1:-}"
      if [[ -z "${BRANCH}" ]]; then
        echo "Error: --branch requires a value." >&2
        exit 1
      fi
      ;;
    --compose)
      RUN_COMPOSE=1
      ;;
    --prod)
      RUN_PROD=1
      ;;
    --code-only)
      CODE_ONLY=1
      ;;
    --build)
      RUN_BUILD=1
      RUN_COMPOSE=1
      ;;
    --worker)
      RUN_WORKER=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option '$1'." >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if [[ "${RUN_PROD}" -eq 1 && "${CODE_ONLY}" -eq 0 ]]; then
  RUN_COMPOSE=1
  RUN_BUILD=1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

if [[ -z "${BRANCH}" ]]; then
  BRANCH="$(git branch --show-current)"
  if [[ -z "${BRANCH}" ]]; then
    echo "Error: not on a branch. Pass --branch <name> explicitly." >&2
    exit 1
  fi
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Working tree has tracked changes. Commit/stash changes before deploy." >&2
  exit 1
fi

echo "Updating git branch '${BRANCH}' in ${REPO_DIR} ..."
git fetch origin "${BRANCH}"
git switch "${BRANCH}"
git pull --ff-only origin "${BRANCH}"

validate_db_revision_is_known() {
  local db_id db_revision revision_file
  db_id="$("${compose_cmd[@]}" ps -q db 2>/dev/null || true)"
  if [[ -z "${db_id}" ]]; then
    return 0
  fi

  db_revision="$(docker exec "${db_id}" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select version_num from alembic_version limit 1" 2>/dev/null' || true)"
  db_revision="$(printf '%s' "${db_revision}" | tr -d '[:space:]')"
  if [[ -z "${db_revision}" ]]; then
    return 0
  fi

  if [[ "${db_revision}" == [0-9][0-9][0-9]_* ]]; then
    revision_file="backend/alembic/versions/${db_revision}.py"
    if [[ ! -f "${revision_file}" ]]; then
      echo "Error: database is stamped at Alembic revision '${db_revision}', but ${revision_file} is missing in branch '${BRANCH}'." >&2
      echo "Switch to the branch containing that migration or restore the migration before deploying." >&2
      exit 1
    fi
  fi
}

ensure_backup_encryption_key() {
  local secret_dir secret_file
  secret_dir="${REPO_DIR}/.runtime/secrets"
  secret_file="${secret_dir}/backup.key"
  install -d -m 0700 "${secret_dir}"
  if [[ ! -s "${secret_file}" ]]; then
    umask 077
    openssl rand -base64 32 >"${secret_file}"
    echo "Backup encryption key generated at ${secret_file}. Keep an offline copy for disaster recovery."
  fi
  chmod 0600 "${secret_file}"
}

install_restore_drill_timer() {
  local service_source timer_source
  service_source="${REPO_DIR}/deploy/backup/papermind-restore-drill.service"
  timer_source="${REPO_DIR}/deploy/backup/papermind-restore-drill.timer"
  if ! command -v systemctl >/dev/null 2>&1 || [[ ! -f "${service_source}" || ! -f "${timer_source}" ]]; then
    return 0
  fi
  if [[ "${EUID}" -eq 0 ]]; then
    install -m 0644 "${service_source}" /etc/systemd/system/papermind-restore-drill.service
    install -m 0644 "${timer_source}" /etc/systemd/system/papermind-restore-drill.timer
    systemctl daemon-reload
    systemctl enable --now papermind-restore-drill.timer >/dev/null
  elif sudo -n true >/dev/null 2>&1; then
    sudo install -m 0644 "${service_source}" /etc/systemd/system/papermind-restore-drill.service
    sudo install -m 0644 "${timer_source}" /etc/systemd/system/papermind-restore-drill.timer
    sudo systemctl daemon-reload
    sudo systemctl enable --now papermind-restore-drill.timer >/dev/null
  else
    echo "Warning: restore-drill timer was not installed because passwordless sudo is unavailable." >&2
    echo "Run scripts/setup_pi.sh once or install deploy/backup/papermind-restore-drill.* manually." >&2
  fi
}

if [[ "${RUN_COMPOSE}" -eq 1 ]]; then
  compose_cmd=(docker compose)
  if [[ "${RUN_PROD}" -eq 1 ]]; then
    ensure_backup_encryption_key
    compose_cmd+=(--env-file .env.prod -f docker-compose.prod.yml)
    validate_db_revision_is_known
  fi
  compose_args=(up -d)
  if [[ "${RUN_BUILD}" -eq 1 ]]; then
    compose_args+=(--build)
  fi
  echo "Running: ${compose_cmd[*]} ${compose_args[*]}"
  "${compose_cmd[@]}" "${compose_args[@]}"
  if [[ "${RUN_PROD}" -eq 1 ]]; then
    install_restore_drill_timer
  fi
fi

if [[ "${RUN_WORKER}" -eq 1 ]]; then
  compose_cmd=(docker compose)
  if [[ "${RUN_PROD}" -eq 1 ]]; then
    compose_cmd+=(--env-file .env.prod -f docker-compose.prod.yml)
  fi
  worker_args=(up -d worker)
  if [[ "${RUN_BUILD}" -eq 1 ]]; then
    worker_args=(up -d --build worker)
  fi
  echo "Running: ${compose_cmd[*]} ${worker_args[*]}"
  "${compose_cmd[@]}" "${worker_args[@]}"
fi

echo "Done."
