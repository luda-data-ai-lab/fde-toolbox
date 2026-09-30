#!/usr/bin/env bash
# Runs FDE Toolbox without Docker: uvicorn serving the API and the built frontend on one port.
# Prerequisites: Python 3.12 and a built frontend (frontend/dist). For offline machines, install
# backend wheels beforehand (pip download ... on a connected machine, then PIP_FIND_LINKS=<dir>).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3.12}"
cd "$ROOT/backend"

if [ ! -f "$ROOT/frontend/dist/index.html" ]; then
  echo "frontend/dist not found. Build it first: (cd frontend && npm ci && npm run build)" >&2
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  "$PYTHON" -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -e .
fi
if [ ! -f .env ]; then
  cp .env.example .env
  secret="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))')"
  fernet="$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  sed -i.bak -e "s|^SECRET_KEY=.*|SECRET_KEY=$secret|" -e "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$fernet|" .env && rm -f .env.bak
  chmod 600 .env
  echo "created backend/.env with generated keys"
fi
mkdir -p data
export STATIC_DIR="$ROOT/frontend/dist"
.venv/bin/python -m app.cli migrate
.venv/bin/python -m app.cli seed-assets || echo "seed-assets skipped: run 'python -m app.cli init-admin' first"
echo "FDE Toolbox on http://$HOST:$PORT"
exec .venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
