#!/bin/sh
set -eu

compose_file=${COMPOSE_FILE:-production.docker-compose.yaml}
env_file=${ENV_FILE:-.env.production}

read_env_value() {
    sed -n "s/^$1=//p" "$env_file" | tail -n 1 | tr -d '\r'
}

domain=$(read_env_value APP_DOMAIN)
email=$(read_env_value TLS_EMAIL)
htpasswd_path=$(read_env_value STAGING_HTPASSWD_PATH)
htpasswd_path=${htpasswd_path:-./secrets/nginx/.htpasswd}

test -n "$domain"
test -n "$email"
test -f "$htpasswd_path"

compose() {
    docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

compose up -d postgres backend frontend proxy certbot-renew
compose --profile certificate-tools run --rm certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --domain "$domain" \
    --email "$email" \
    --agree-tos \
    --no-eff-email \
    --non-interactive
compose up -d --force-recreate proxy
compose exec -T proxy nginx -t
