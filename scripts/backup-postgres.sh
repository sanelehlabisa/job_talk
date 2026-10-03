#!/bin/sh
set -eu

compose_file=${COMPOSE_FILE:-prod.docker-compose.yaml}
env_file=${ENV_FILE:-.env.production}
backup_dir=${BACKUP_DIR:-./backups/postgres}
retention_days=${BACKUP_RETENTION_DAYS:-7}

case "$retention_days" in
    ''|*[!0-9]*)
        echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2
        exit 2
        ;;
esac

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_path="$backup_dir/job-talk-$timestamp.dump"
temporary_path="$backup_path.tmp"

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
trap 'rm -f "$temporary_path"' EXIT HUP INT TERM

docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
    sh -c 'exec pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom --no-owner --no-acl' \
    > "$temporary_path"

test -s "$temporary_path"
docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
    pg_restore --list < "$temporary_path" > /dev/null

chmod 600 "$temporary_path"
mv "$temporary_path" "$backup_path"
sha256sum "$backup_path" > "$backup_path.sha256"
chmod 600 "$backup_path.sha256"

find "$backup_dir" -type f -name 'job-talk-*.dump*' -mtime "+$retention_days" -delete
echo "$backup_path"
