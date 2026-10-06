#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
env_file=${JOBTALK_ENV_FILE:-$here/../job_talk/.env}
test -f "$env_file" || { echo "Existing Job Talk environment not found: $env_file" >&2; exit 1; }
preview=false
if [ "${1:-}" = preview ]; then preview=true; shift; fi
compose() {
    if $preview; then
        docker compose --env-file "$env_file" -f "$here/compose.yaml" -f "$here/preview.yaml" "$@"
    else
        docker compose --env-file "$env_file" -f "$here/compose.yaml" "$@"
    fi
}
read_value() { sed -n "s/^$1=//p" "$env_file" | tail -n 1 | tr -d '\r'; }
case "${1:-}" in
    init)
        docker network inspect roventics_edge >/dev/null 2>&1 || docker network create roventics_edge
        for volume in roventics_edge_certificates roventics_edge_acme jobtalk_backend_socket; do
            docker volume inspect "$volume" >/dev/null 2>&1 || docker volume create "$volume"
        done
        echo 'Shared network/volumes ready. Existing app environments were not modified.'
        ;;
    issue)
        shift
        test "$#" -gt 0 || { echo 'Usage: edge.sh [preview] issue roventics.com [www.roventics.com] OR issue jobtalk.roventics.com' >&2; exit 1; }
        primary=$1
        case "$primary" in roventics.com|"$(read_value APP_DOMAIN)") ;; *) echo 'Unknown certificate hostname' >&2; exit 1 ;; esac
        domains=$primary
        shift
        if [ "$#" -gt 0 ]; then
            [ "$primary" = roventics.com ] && [ "$#" = 1 ] && [ "$1" = www.roventics.com ] || exit 1
            domains="$domains,www.roventics.com"
        fi
        email=$(read_value ADMIN_EMAIL)
        test -n "$email" || { echo 'Set ADMIN_EMAIL in the existing Job Talk environment first' >&2; exit 1; }
        compose --profile certificate-tools run --rm certbot certonly --webroot -w /var/www/certbot \
            --cert-name "$primary" -d "$domains" --email "$email" --agree-tos --non-interactive --keep-until-expiring
        compose exec -T proxy edge-reload
        ;;
    renew)
        shift
        compose --profile certificate-tools run --rm certbot renew --webroot -w /var/www/certbot "$@"
        compose exec -T proxy edge-reload
        ;;
    '') echo 'Usage: edge.sh [preview] init|issue|renew|<docker compose arguments>' >&2; exit 1 ;;
    *) compose "$@" ;;
esac
