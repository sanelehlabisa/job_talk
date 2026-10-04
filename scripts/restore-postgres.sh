#!/bin/sh
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 BACKUP_FILE TARGET_DATABASE [--allow-primary-empty]" >&2
    exit 2
fi

backup_path=$1
target_database=$2
allow_primary=${3:-}
compose_file=${COMPOSE_FILE:-prod.docker-compose.yaml}
env_file=${ENV_FILE:-.env}

case "$target_database" in
    ''|*[!A-Za-z0-9_]*)
        echo "TARGET_DATABASE may contain only letters, numbers, and underscores" >&2
        exit 2
        ;;
esac

test -r "$backup_path"
docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
    pg_restore --list < "$backup_path" > /dev/null

primary_database=$(docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
    sh -c 'printf %s "$POSTGRES_DB"')
created_database=false

cleanup_failed_restore() {
    if [ "$created_database" = true ]; then
        docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
            sh -c 'dropdb --username="$POSTGRES_USER" --if-exists "$1"' sh "$target_database" > /dev/null
    fi
}
trap cleanup_failed_restore EXIT HUP INT TERM

if [ "$target_database" = "$primary_database" ]; then
    if [ "$allow_primary" != "--allow-primary-empty" ]; then
        echo "Refusing to restore over the configured primary database without --allow-primary-empty" >&2
        exit 2
    fi
    table_count=$(docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
        sh -c 'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --tuples-only --no-align --command="SELECT count(*) FROM information_schema.tables WHERE table_schema = '\''public'\''"')
    if [ "$table_count" != "0" ]; then
        echo "The configured primary database is not empty; restore was refused" >&2
        exit 2
    fi
else
    docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
        sh -c 'createdb --username="$POSTGRES_USER" "$1"' sh "$target_database"
    created_database=true
fi

docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
    sh -c 'exec pg_restore --username="$POSTGRES_USER" --dbname="$1" --no-owner --no-acl --exit-on-error' sh "$target_database" \
    < "$backup_path"

revision=$(docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
    sh -c 'psql --username="$POSTGRES_USER" --dbname="$1" --tuples-only --no-align --command="SELECT version_num FROM alembic_version"' sh "$target_database")

created_database=false
trap - EXIT HUP INT TERM
echo "Restored $target_database at migration $revision"
