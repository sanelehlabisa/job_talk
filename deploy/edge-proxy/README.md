# Shared Roventics edge

This is an independent Compose project for the VPS, versioned here so its release
is reviewable. Install this directory at `~/apps/edge-proxy`; certificate/account
data lives in external Docker volumes, outside both app repositories.

Follow [the migration runbook](../../docs/production-operations.md) from the
Job Talk checkout. Do not run the public listener while the old one owns 80/443.
This package reads `../job_talk/.env` without modifying it. If that installation
uses another path, supply `JOBTALK_ENV_FILE=/absolute/path/.env` for the command.

```sh
sh edge.sh init                         # create shared network/volumes once
sh edge.sh preview up -d --build proxy  # loopback 18080/18443 rehearsal
sh edge.sh preview issue roventics.com  # add www.roventics.com only if used
sh edge.sh preview issue jobtalk.roventics.com
# After the runbook's old-listener handoff:
sh edge.sh up -d --wait proxy certbot-renew
sh edge.sh renew --dry-run
sh edge.sh logs --tail=80 proxy certbot-renew
```

The renewal service checks every 12 hours; the proxy checks certificate changes
every minute and validates configuration before a graceful reload. Manual issue
and renew commands also request that reload. Failed validation leaves the running
workers serving their previous configuration. Real issuance/dry-run need DNS and
public ACME access; local integration tests use disposable self-signed certificates.

`secrets/jobtalk.htpasswd` gates the Job Talk webpage during private testing.
The API retains scoped Bearer tokens. Keep this gate until public launch approval;
then remove its two `auth_basic` directives in the Job Talk HTTPS template and
rebuild only the edge. Roventics has no such gate.

External resources are `roventics_edge` (network), `roventics_edge_certificates`,
`roventics_edge_acme`, and `jobtalk_backend_socket` (volumes). Both apps' own
database/private-data volumes keep their existing identities. Never delete the
external volumes during ordinary upgrades or rollback. Only backend and edge
mount the Job Talk socket; there is no Docker daemon socket mount.
