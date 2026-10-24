#!/bin/sh
set -eu

# Development entrypoint. Production uses a dedicated migration service.
python - <<'PY'
import time
import psycopg
from app.core.config import settings
dsn = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
for attempt in range(30):
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            break
    except psycopg.OperationalError:
        if attempt == 29:
            raise SystemExit('PostgreSQL is not ready; check its health and database settings')
        time.sleep(1)
PY
alembic upgrade head
if [ "${UVICORN_RELOAD:-false}" = true ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
