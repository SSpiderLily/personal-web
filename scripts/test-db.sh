#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir/backend"
uv run --locked --python "${UV_PYTHON:-3.13}" python ../scripts/test_database.py "$@"
