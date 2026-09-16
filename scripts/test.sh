#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

echo "[backend] isolated PostgreSQL, migrations, unit/integration/OCR tests"
bash scripts/test_backend.sh

echo "[frontend] unit tests"
npm --prefix frontend test

echo "[frontend] production build"
npm --prefix frontend run build

echo "[frontend] browser tests on Vite 127.0.0.1:5179"
npm --prefix frontend run test:browser

echo "All local checks passed."
