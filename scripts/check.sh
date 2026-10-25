#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major !== 22 || minor < 12) { console.error("Use Node 22.12+ in the 22.x line; see frontend/.nvmrc"); process.exit(1); }'
command -v uv >/dev/null || { echo 'Install uv before running checks.' >&2; exit 1; }

echo 'Checking backend dependencies and HTTP contracts...'
(
  cd backend
  uv sync --locked
  APP_ENV=test DEBUG=false uv run --locked python -m unittest discover -s tests -v
  APP_ENV=test DEBUG=false uv run --locked gunicorn --check-config app.main:app -w 2 -k uvicorn.workers.UvicornWorker
)
echo 'Checking deployment and real temporary backup/recovery safeguards...'
PW_REQUIRE_RECOVERY_TESTS=1 backend/.venv/bin/python -m unittest discover -s tests -v
echo 'Installing frontend dependencies and building...'
npm --prefix frontend ci --no-audit --no-fund
npm --prefix frontend test
npm --prefix frontend run build
echo 'All checks passed. No deployment was performed.'
