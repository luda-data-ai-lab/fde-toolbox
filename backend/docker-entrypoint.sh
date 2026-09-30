#!/bin/sh
# On first start, generates SECRET_KEY / ENCRYPTION_KEY into $FDE_SECRETS_DIR (inside the data
# volume) unless they are provided via environment. The app reads them from there, so
# `docker compose exec backend python -m app.cli ...` works too.
set -eu
DIR="${FDE_SECRETS_DIR:-/data/.secrets}"
umask 077
mkdir -p "$DIR"
[ -n "${SECRET_KEY:-}" ] || [ -s "$DIR/secret_key" ] || python -c "import secrets; print(secrets.token_urlsafe(48), end='')" > "$DIR/secret_key"
[ -n "${ENCRYPTION_KEY:-}" ] || [ -s "$DIR/encryption_key" ] || python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode(), end='')" > "$DIR/encryption_key"
if [ "$#" -gt 0 ] && [ "$1" = "uvicorn" ]; then
  python -m app.cli migrate
  python -m app.cli seed-assets || echo "seed-assets skipped: run init-admin, then seed-assets"
fi
exec "$@"
