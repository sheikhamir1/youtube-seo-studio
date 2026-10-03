#!/usr/bin/env bash
# Backend entrypoint: apply migrations, then start exactly ONE Uvicorn process
# (a single process = a single worker loop = one Gemini inference at a time).
set -euo pipefail

echo "[entrypoint] applying database migrations..."
if ! alembic upgrade head; then
  echo "[entrypoint] FATAL: database migration failed. Not starting the API." >&2
  exit 1
fi

echo "[entrypoint] seeding prompt templates (idempotent)..."
python -m app.cli seed || echo "[entrypoint] seeding failed; the API will retry at startup."

echo "[entrypoint] starting API + worker (1 uvicorn worker)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
