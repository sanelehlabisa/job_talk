#!/bin/sh
set -eu
edge-reload
# Certificate issuance/renewal is owned by the independent edge stack.
# Reload only when the certificate/key fingerprint changes and nginx -t passes.
(while sleep 60; do edge-reload || true; done) &
exec "$@"
