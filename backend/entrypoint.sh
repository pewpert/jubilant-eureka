#!/usr/bin/env bash
# Container entrypoint: bring the DB schema to head via Alembic, then exec the
# given command (uvicorn for the API, celery for the worker).
#
# Migration is idempotent and handled in three cases:
#   1. Fresh DB (no tables)            → `alembic upgrade head` creates everything.
#   2. Existing DB created by the old  → tables already exist but alembic_version
#      create_all boot path              is absent; we `stamp` the baseline so the
#                                         upgrade doesn't try to re-create them,
#                                         then upgrade applies any newer migrations.
#   3. Already-migrated DB             → `alembic upgrade head` is a no-op.
#
# Only the API container runs migrations (RUN_MIGRATIONS=1); the worker waits via
# depends_on and skips them to avoid two services racing on the same upgrade.
set -euo pipefail

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "[entrypoint] Ensuring DB schema is at head…"
  # If the legacy tables exist but alembic has never run, adopt them at baseline.
  if python -c "
import sys
from sqlalchemy import create_engine, inspect
from app.config import get_settings
url = get_settings().database_url.replace('+asyncpg','+psycopg2').replace('postgresql+asyncpg','postgresql+psycopg2')
insp = inspect(create_engine(url))
tables = set(insp.get_table_names())
# Legacy schema present but no alembic bookkeeping yet?
sys.exit(0 if ('listings' in tables and 'alembic_version' not in tables) else 1)
"; then
    echo "[entrypoint] Legacy tables found without alembic_version — stamping baseline."
    alembic stamp 0001_baseline
  fi
  alembic upgrade head
  echo "[entrypoint] Migrations complete."
fi

exec "$@"
