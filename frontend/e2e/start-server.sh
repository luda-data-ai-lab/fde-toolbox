#!/usr/bin/env bash
# Starts a throwaway backend (fresh SQLite DB) serving the built frontend for E2E runs.
set -euo pipefail
PORT="${1:-8100}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${E2E_PYTHON:-$ROOT/backend/.venv/bin/python}"
DATA="$(mktemp -d)"
export DATA_DIR="$DATA" DATABASE_URL="sqlite:///$DATA/fde.db" STATIC_DIR="$ROOT/frontend/dist"
export SECRET_KEY="e2e-secret-key-0123456789abcdefghijklmnop" ENCRYPTION_KEY="e2e-encryption-key-0123"
cd "$ROOT/backend"
"$PY" -m app.cli migrate
"$PY" -m app.cli init-admin --email admin@e2e.local --name "E2E Admin" --password admin-pass-123
"$PY" -m app.cli seed-assets
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
