#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

echo "[backend] unit tests"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
if "${PYTHON_BIN}" -m pytest --version >/dev/null 2>&1; then
  PYTHONPATH=backend "${PYTHON_BIN}" -m pytest backend/tests
else
  echo "pytest is not installed; falling back to unittest. Install backend/requirements-dev.txt for the CI-equivalent backend test command."
  PYTHONPATH=backend "${PYTHON_BIN}" -m unittest discover backend/tests
fi

echo "[frontend] unit tests"
npm --prefix frontend test

echo "[frontend] production build"
npm --prefix frontend run build

echo "All local checks passed."
