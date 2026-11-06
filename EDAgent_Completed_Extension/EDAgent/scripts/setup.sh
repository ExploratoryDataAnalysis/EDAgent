#!/usr/bin/env bash
# One-time setup: Python virtual environment, backend dependencies, frontend dependencies, .env.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

if [ ! -f backend/.env ]; then
  cp .env.example backend/.env
  echo "Created backend/.env from .env.example (edit it to set SECRET_KEY and optional AI settings)."
fi

(cd frontend && npm ci)
echo "Setup complete. Start everything with: scripts/dev.sh"
