#!/bin/sh
set -eu

compose_file=${COMPOSE_FILE:-prod.docker-compose.yaml}
env_file=${ENV_FILE:-.env.production}

compose() {
    docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

compose --profile certificate-tools run --rm certbot renew \
    --webroot \
    --webroot-path /var/www/certbot \
    "$@"
compose exec -T proxy nginx -t
compose exec -T proxy nginx -s reload
