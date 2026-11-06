#!/usr/bin/env bash
# Starts the API (port 8000) and the web client (port 5173). Ctrl+C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

(cd "$ROOT/backend" && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
cd "$ROOT/frontend" && npm run dev
