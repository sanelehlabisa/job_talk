#!/bin/sh
set -eu

env_file=${ENV_FILE:-.env.production}
compose_file=${COMPOSE_FILE:-production.docker-compose.yaml}
expected_ip=${EXPECTED_PUBLIC_IP:-}

fail() {
    echo "Preflight failed: $1" >&2
    exit 1
}

read_env_value() {
    sed -n "s/^$1=//p" "$env_file" | tail -n 1 | tr -d '\r'
}

require_value() {
    key=$1
    value=$(read_env_value "$key")
    test -n "$value" || fail "$key is missing from $env_file"
    case "$value" in
        *replace-with*|*.example.com|*@example.com)
            fail "$key still contains an example value"
            ;;
    esac
}

test -f "$env_file" || fail "$env_file does not exist"
test -f "$compose_file" || fail "$compose_file does not exist"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
docker compose version >/dev/null 2>&1 || fail "Docker Compose is not available"

for key in \
    JOB_TALK_IMAGE_TAG APP_DOMAIN PUBLIC_ORIGIN ALLOWED_HOSTS CORS_ORIGINS \
    TLS_EMAIL STAGING_HTPASSWD_PATH SMTP_HOST SMTP_USERNAME SMTP_PASSWORD \
    EMAIL_FROM SUPPORT_EMAIL POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD \
    DATABASE_URL SESSION_TOKEN_PEPPER
do
    require_value "$key"
done

domain=$(read_env_value APP_DOMAIN)
public_origin=$(read_env_value PUBLIC_ORIGIN)
allowed_hosts=$(read_env_value ALLOWED_HOSTS)
cors_origins=$(read_env_value CORS_ORIGINS)
htpasswd_path=$(read_env_value STAGING_HTPASSWD_PATH)
session_pepper=$(read_env_value SESSION_TOKEN_PEPPER)
ai_provider=$(read_env_value AI_PROVIDER)
openai_key=$(read_env_value OPENAI_API_KEY)

case "$domain" in
    *.*) ;;
    *) fail "APP_DOMAIN must be a fully qualified subdomain" ;;
esac
test "$public_origin" = "https://$domain" || fail "PUBLIC_ORIGIN must equal https://$domain"
test "$allowed_hosts" = "$domain" || fail "ALLOWED_HOSTS must contain only $domain for the first deployment"
test "$cors_origins" = "$public_origin" || fail "CORS_ORIGINS must equal PUBLIC_ORIGIN"
test -f "$htpasswd_path" || fail "staging password file $htpasswd_path does not exist"
test "${#session_pepper}" -ge 32 || fail "SESSION_TOKEN_PEPPER must contain at least 32 characters"

case "$ai_provider" in
    ""|mock) ;;
    openai)
        test -n "$openai_key" || fail "OPENAI_API_KEY is required when AI_PROVIDER=openai"
        ;;
    *) fail "AI_PROVIDER must be mock or openai" ;;
esac

resolved_ips=$(getent ahostsv4 "$domain" 2>/dev/null | awk '{ print $1 }' | sort -u || true)
test -n "$resolved_ips" || fail "$domain does not resolve to an IPv4 address"
if test -n "$expected_ip"; then
    echo "$resolved_ips" | grep -Fx "$expected_ip" >/dev/null || \
        fail "$domain does not resolve to EXPECTED_PUBLIC_IP"
fi

docker compose --env-file "$env_file" -f "$compose_file" config --quiet || \
    fail "production Compose configuration is invalid"

echo "Production preflight passed for $domain."
echo "DNS IPv4: $(echo "$resolved_ips" | paste -sd, -)"
echo "Next: configure the VM firewall, then run ./scripts/issue-certificate.sh"
