#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy_pi.sh [options]

Options:
  --branch <name>  Git branch to update (default: main)
  --compose        Run docker compose up -d after git update
  --prod           Use docker-compose.prod.yml for compose commands
  --build          Use --build with docker compose (implies --compose)
  --worker         Start/update worker with compose profile "worker"
  -h, --help       Show this help
EOF
}

BRANCH="main"
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

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit/stash changes before deploy." >&2
  exit 1
fi

echo "Updating git branch '${BRANCH}' in ${REPO_DIR} ..."
git fetch origin "${BRANCH}"
git checkout "${BRANCH}"
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

if [[ "${RUN_COMPOSE}" -eq 1 ]]; then
  compose_cmd=(docker compose)
  if [[ "${RUN_PROD}" -eq 1 ]]; then
    compose_cmd+=(--env-file .env.prod -f docker-compose.prod.yml)
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
