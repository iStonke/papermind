#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy_pi.sh [options]

Options:
  --branch <name>  Git branch to update (default: current branch)
  --compose        Run docker compose up -d after git update
  --prod           Use docker-compose.prod.yml for compose commands
  --build          Use --build with docker compose (implies --compose)
  --worker         Start/update worker with compose profile "worker"
  -h, --help       Show this help
EOF
}

BRANCH=""
RUN_COMPOSE=0
RUN_BUILD=0
RUN_WORKER=0
RUN_PROD=0

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

preserve_frontend_assets() {
  local assets_dir="${REPO_DIR}/.runtime/frontend-assets"
  local frontend_id

  mkdir -p "${assets_dir}"
  frontend_id="$("${compose_cmd[@]}" ps -q frontend 2>/dev/null || true)"
  if [[ -z "${frontend_id}" ]]; then
    return
  fi

  echo "Preserving frontend assets from the running container ..."
  docker cp "${frontend_id}:/usr/share/nginx/html/assets/." "${assets_dir}/" \
    || echo "Warning: existing frontend assets could not be preserved." >&2
}

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

if [[ "${RUN_COMPOSE}" -eq 1 ]]; then
  compose_cmd=(docker compose)
  if [[ "${RUN_PROD}" -eq 1 ]]; then
    compose_cmd+=(--env-file .env.prod -f docker-compose.prod.yml)
    validate_db_revision_is_known
    preserve_frontend_assets
  fi
  compose_args=(up -d)
  if [[ "${RUN_BUILD}" -eq 1 ]]; then
    compose_args+=(--build)
  fi
  echo "Running: ${compose_cmd[*]} ${compose_args[*]}"
  "${compose_cmd[@]}" "${compose_args[@]}"
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
