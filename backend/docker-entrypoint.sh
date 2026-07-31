#!/bin/sh
set -e
alembic upgrade head
# Railway (and most PaaS) inject $PORT and expect the container to bind to
# it; default to 8000 for local `docker compose` where PORT isn't set.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
