#!/bin/sh
set -eu

case "$APP_DOMAIN" in
    ''|*[!a-zA-Z0-9.-]*|roventics.com|www.roventics.com)
        echo 'APP_DOMAIN must be a distinct Job Talk hostname' >&2; exit 1 ;;
esac
# Both certificates and keys are included; nothing sensitive is logged.
stamp=$({
    for domain in roventics.com "$APP_DOMAIN"; do
        for file in fullchain.pem privkey.pem; do
            path="/etc/letsencrypt/live/$domain/$file"
            if [ -f "$path" ]; then sha256sum "$path"; else echo "$path missing"; fi
        done
    done
} | sha256sum | cut -d ' ' -f 1)
[ "$stamp" != "$(cat /tmp/edge-cert-stamp 2>/dev/null || true)" ] || exit 0
mkdir /tmp/edge-reload-lock 2>/dev/null || exit 0
trap 'rmdir /tmp/edge-reload-lock' EXIT

conf=/etc/nginx/conf.d
backup=$(mktemp -d)
cp "$conf"/*.conf "$backup/" 2>/dev/null || true
cp /etc/nginx/edge/default.conf "$conf/default.conf"
if [ -f /etc/letsencrypt/live/roventics.com/fullchain.pem ]; then
    cp /etc/nginx/edge/roventics.conf.template "$conf/roventics.conf"
else
    cp /etc/nginx/edge/roventics-bootstrap.conf "$conf/roventics.conf"
fi
template=bootstrap.conf.template
if [ -f "/etc/letsencrypt/live/$APP_DOMAIN/fullchain.pem" ]; then
    template=production.conf.template
fi
envsubst '${APP_DOMAIN}' < "/etc/nginx/edge/$template" > "$conf/jobtalk.conf"
if nginx -t && { [ ! -s /var/run/nginx.pid ] || nginx -s reload; }; then
    printf '%s\n' "$stamp" > /tmp/edge-cert-stamp
    rm -rf "$backup"
else
    cp "$backup"/*.conf "$conf/" 2>/dev/null || true
    rm -rf "$backup"
    echo 'Edge validation/reload failed; previous running configuration retained' >&2
    exit 1
fi
