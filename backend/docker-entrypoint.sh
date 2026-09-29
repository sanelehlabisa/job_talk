#!/bin/sh
set -eu

alembic upgrade head
if [ "${APP_ENV:-development}" != "production" ] && [ -n "${DEMO_RECRUITER_EMAIL:-}" ]; then
    python -m app.recruiters approve "$DEMO_RECRUITER_EMAIL" --quiet
    if [ "${SEED_DEMO_JOBS:-false}" = "true" ]; then
        python -m app.seed_jobs
    fi
fi
exec "$@"
