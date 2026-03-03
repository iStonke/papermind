#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy_pi.sh [options]

Options:
  --branch <name>  Git branch to update (default: main)
  --compose        Run docker compose up -d after git update
  --build          Use --build with docker compose (implies --compose)
  --worker         Start/update worker with compose profile "worker"
  -h, --help       Show this help
EOF
}

BRANCH="main"
RUN_COMPOSE=0
RUN_BUILD=0
RUN_WORKER=0

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

if [[ "${RUN_COMPOSE}" -eq 1 ]]; then
  compose_args=(up -d)
  if [[ "${RUN_BUILD}" -eq 1 ]]; then
    compose_args+=(--build)
  fi
  echo "Running: docker compose ${compose_args[*]}"
  docker compose "${compose_args[@]}"
fi

if [[ "${RUN_WORKER}" -eq 1 ]]; then
  worker_args=(--profile worker up -d worker)
  if [[ "${RUN_BUILD}" -eq 1 ]]; then
    worker_args=(--profile worker up -d --build worker)
  fi
  echo "Running: docker compose ${worker_args[*]}"
  docker compose "${worker_args[@]}"
fi

echo "Done."
