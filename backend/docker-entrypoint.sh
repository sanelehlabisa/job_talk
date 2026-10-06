#!/bin/sh
set -eu

alembic upgrade head
if [ "${APP_ENV:-development}" = "development" ]; then
    python -m app.recruiters seed --quiet
fi
exec "$@"
