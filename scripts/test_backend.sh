#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"
compose=(docker compose -p "papermind-tests-$$" -f docker-compose.test.yml)
cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
"${compose[@]}" up --build --abort-on-container-exit --exit-code-from tests
