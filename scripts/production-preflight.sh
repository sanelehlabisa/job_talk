#!/bin/sh
set -eu

env_file=${ENV_FILE:-.env}
compose_file=${COMPOSE_FILE:-prod.docker-compose.yaml}
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
    APP_DOMAIN TLS_EMAIL SMTP_HOST SMTP_USER SMTP_PASSWORD \
    EMAIL_FROM SUPPORT_EMAIL POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD \
    SESSION_TOKEN_PEPPER
do
    require_value "$key"
done

domain=$(read_env_value APP_DOMAIN)
htpasswd_path=$(read_env_value STAGING_HTPASSWD_PATH)
htpasswd_path=${htpasswd_path:-./secrets/nginx/.htpasswd}
session_pepper=$(read_env_value SESSION_TOKEN_PEPPER)
ai_provider=$(read_env_value AI_PROVIDER)
openai_key=$(read_env_value OPENAI_API_KEY)
gemini_key=$(read_env_value GEMINI_API_KEY)

command -v git >/dev/null 2>&1 || fail "Git is not installed"
current_commit=$(git rev-parse HEAD 2>/dev/null) || fail "release directory is not a Git checkout"

case "$domain" in
    *.*) ;;
    *) fail "APP_DOMAIN must be a fully qualified subdomain" ;;
esac
test -f "$htpasswd_path" || fail "staging password file $htpasswd_path does not exist"
test "${#session_pepper}" -ge 32 || fail "SESSION_TOKEN_PEPPER must contain at least 32 characters"

case "$ai_provider" in
    ""|mock) ;;
    openai)
        test -n "$openai_key" || fail "OPENAI_API_KEY is required when AI_PROVIDER=openai"
        ;;
    gemini)
        test -n "$gemini_key" || fail "GEMINI_API_KEY is required when AI_PROVIDER=gemini"
        ;;
    *) fail "AI_PROVIDER must be mock, openai or gemini" ;;
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
echo "Release commit: $current_commit"
echo "DNS IPv4: $(echo "$resolved_ips" | paste -sd, -)"
echo "Next: configure the VM firewall, then run ./scripts/issue-certificate.sh"
