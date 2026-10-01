#!/bin/sh
set -eu

certificate="/etc/letsencrypt/live/${APP_DOMAIN}/fullchain.pem"
configuration="/etc/nginx/conf.d/default.conf"
reload_seconds="${CERTIFICATE_RELOAD_SECONDS:-3600}"

render_configuration() {
    if [ -f "$certificate" ]; then
        template="/etc/nginx/jobtalk/production.conf.template"
    else
        template="/etc/nginx/jobtalk/bootstrap.conf.template"
    fi
    envsubst '${APP_DOMAIN}' < "$template" > "$configuration"
}

certificate_stamp() {
    if [ -f "$certificate" ]; then
        sha256sum "$certificate" | cut -d ' ' -f 1
    else
        printf 'missing\n'
    fi
}

watch_certificate() {
    previous_stamp=$(certificate_stamp)
    while sleep "$reload_seconds"; do
        current_stamp=$(certificate_stamp)
        if [ "$current_stamp" != "$previous_stamp" ]; then
            render_configuration
            if nginx -t; then
                nginx -s reload
                previous_stamp="$current_stamp"
            fi
        fi
    done
}

case "$reload_seconds" in
    ''|*[!0-9]*)
        echo "CERTIFICATE_RELOAD_SECONDS must be a positive integer" >&2
        exit 1
        ;;
    0)
        echo "CERTIFICATE_RELOAD_SECONDS must be greater than zero" >&2
        exit 1
        ;;
esac

render_configuration
watch_certificate &
exec "$@"
