# Shared VPS deployment and renewal

Target: `https://jobtalk.roventics.com` alongside the existing `roventics.com`.
Only the **independent shared edge** owns ports 80/443. Job Talk production now
contains backend, frontend and PostgreSQL; Roventics' new production file contains
its frontend/backend. Job Talk's backend remains Unix-socket-only.

The shared package is tracked at `deploy/edge-proxy/` and installed separately at
`~/apps/edge-proxy/`. Its certificates are in global Docker volumes, not app
folders. **No existing `.env` is edited by these scripts.** The edge reads the
existing `~/apps/job_talk/.env` for `APP_DOMAIN` and the admin's ACME email.

These are **operator commands for the VPS**, not a record of a live deployment.
Check out the reviewed Job Talk and Roventics feature commits first. Preserve
local VM changes, especially `.env`, `backend/.env`, `frontend/config.js` and data.
Docker Compose must support `!override` (used for the loopback preview).

## 1. DNS: perform this at the DNS provider

Create this record where `roventics.com` DNS is managed:

| Type | Name | Value |
| --- | --- | --- |
| A | jobtalk | 209.74.85.79 |

Confirm that IP belongs to this VPS first. Keep existing apex/`www` records intact.
Check conflicting AAAA records and any DNS-provider proxy settings. This is not
an application command or a Linux subdomain-creation command.

```sh
getent ahostsv4 jobtalk.roventics.com
```

The VM's existing Job Talk environment must have
`APP_DOMAIN=jobtalk.roventics.com`, its real admin/sender/SMTP/Gemini settings and
strong database/session secrets. Inspect/edit it yourself if necessary; no script
copies a template over it. Keep your computer's environment unchanged.

## 2. Inventory, backups and prepare the shared edge

Record the current container names, image IDs, volumes, website/API responses and
certificate dates. The commands below use the reported `roventics-nginx-1`,
`roventics-frontend-1` and `roventics-backend-1`; adjust them if inspection differs.
Review `docker exec roventics-nginx-1 nginx -T` before replacing any config. Back up
application data using [database operations](database-operations.md). Do not use
`down -v`, `--remove-orphans`, or stop the full Roventics stack during migration.

```sh
mkdir -p ~/apps/edge-proxy
cp -R ~/apps/job_talk/deploy/edge-proxy/. ~/apps/edge-proxy/
cd ~/apps/edge-proxy
sh edge.sh init
mkdir -p secrets backups
chmod 700 secrets backups
# Install apache2-utils if htpasswd is not available; it prompts for the password.
test -f secrets/jobtalk.htpasswd || htpasswd -cB secrets/jobtalk.htpasswd staging
chmod 644 secrets/jobtalk.htpasswd
```

Connect the **running** Roventics containers without recreating its apps. Skip an
individual connect command if that container is already on `roventics_edge`.

```sh
docker network connect --alias roventics-frontend roventics_edge roventics-frontend-1
docker network connect --alias roventics-backend roventics_edge roventics-backend-1
docker network connect roventics_edge roventics-nginx-1
sh edge.sh preview up -d --build --wait proxy
```

The preview binds only loopback 18080/18443. Missing Job Talk services do not block
Roventics configuration/reload. Create a backup of the existing active config:

```sh
docker cp roventics-nginx-1:/etc/nginx/conf.d/default.conf backups/roventics-original.conf
diff -u backups/roventics-original.conf migration/roventics-acme.conf
```

**Review the diff first.** The supplied migration config matches the locally
inspected Roventics routes/rate limit, adds ACME forwarding, and uses unique app
aliases. If the VPS has other routes or settings, preserve them in the temporary
config before continuing. Do not blindly replace an unfamiliar live config.

```sh
docker cp migration/roventics-acme.conf roventics-nginx-1:/etc/nginx/conf.d/default.conf
if docker exec roventics-nginx-1 nginx -t; then
  docker exec roventics-nginx-1 nginx -s reload
else
  docker cp backups/roventics-original.conf roventics-nginx-1:/etc/nginx/conf.d/default.conf
  echo 'Validation failed; original config restored. Stop here.' >&2
  exit 1
fi
```

This keeps the old listener serving the site, while ACME requests reach the new
edge. Recheck the existing website and its API before requesting certificates.

## 3. Issue certificates while the old listener stays running

```sh
cd ~/apps/edge-proxy
sh edge.sh preview issue roventics.com
# If www is currently served and resolves here, use this instead of the line above:
# sh edge.sh preview issue roventics.com www.roventics.com
```

Use separate certificates so Job Talk DNS cannot block Roventics renewal. Once
Job Talk DNS resolves here:

```sh
sh edge.sh preview issue jobtalk.roventics.com
```

Certificates and keys are stored in `roventics_edge_certificates`, shared read-only
with Nginx. The central account email comes from `ADMIN_EMAIL`. No wildcard or
extra TLS email variable is needed. ACME uses the running webroot, never stops
Nginx, and the proxy reloads after validation.

## 4. Start Job Talk privately and test the preview

```sh
cd ~/apps/job_talk
EXPECTED_PUBLIC_IP=209.74.85.79 sh scripts/production-preflight.sh
docker compose --env-file .env -f prod.docker-compose.yaml up -d --build --wait
# Only on first setup; this preserves an existing admin's approval state:
docker compose --env-file .env -f prod.docker-compose.yaml exec backend python -m app.recruiters seed
cd ~/apps/edge-proxy
curl --fail --connect-to roventics.com:443:127.0.0.1:18443 https://roventics.com/
curl --fail --connect-to jobtalk.roventics.com:443:127.0.0.1:18443 https://jobtalk.roventics.com/api/ready
```

Use `-u staging` with curl for the Job Talk webpage; it prompts for the staging
password. Do not put passwords in commands. Test the login/create/apply/compare
flow through an SSH tunnel or the final domain during the controlled handoff.
The existing Roventics POST `/api/inquiry` sends email: test it only with an
intentional test message, not an automatic probe. Compare its status/headers and
frontend behavior to the baseline. Never run this test against real applicant data.

If old Job Talk proxy/renewal containers exist from a previous deployment, inspect
and stop those **specific containers** before handoff. The new app file cannot
start them. Do not delete their volumes or any application database volume.

## 5. Handoff ports 80/443 (brief planned listener restart)

A container port-owner change can briefly interrupt connections. Do this only
when preview, certificate and Roventics checks pass, in your chosen cutover window.
Keep the old container and backup config for rollback. Do not publish the new
Roventics product card before the Job Talk URL and public launch are approved.

Before stopping the old listener, prepare its fallback certificate from the
**new central certificate**, avoiding rollback to the reported expired one:

```sh
cd ~/apps/edge-proxy
umask 077
proxy_id=$(sh edge.sh preview ps -q proxy)
docker cp -L "$proxy_id":/etc/letsencrypt/live/roventics.com/fullchain.pem backups/roventics-current.crt
docker cp -L "$proxy_id":/etc/letsencrypt/live/roventics.com/privkey.pem backups/roventics-current.key
docker cp backups/roventics-current.crt roventics-nginx-1:/tmp/edge-roventics.crt
docker cp backups/roventics-current.key roventics-nginx-1:/tmp/edge-roventics.key
docker exec roventics-nginx-1 chmod 600 /tmp/edge-roventics.key
docker exec roventics-nginx-1 sed -i 's|/etc/nginx/certs/server.crt|/tmp/edge-roventics.crt|;s|/etc/nginx/certs/server.key|/tmp/edge-roventics.key|' /etc/nginx/conf.d/default.conf
docker exec roventics-nginx-1 nginx -t
docker exec roventics-nginx-1 nginx -s reload
```

Verify the old public site now presents the valid certificate. Then hand off:

```sh
docker update --restart=no roventics-nginx-1
docker stop roventics-nginx-1
sh edge.sh up -d --wait proxy certbot-renew
curl --fail https://roventics.com/
curl --fail https://jobtalk.roventics.com/api/ready
sh edge.sh renew --dry-run
```

Recheck both app flows. Only the shared edge should publish 80/443. Keep the old
proxy stopped with restart disabled until the migration is accepted. After
acceptance, manage Roventics app services with its new `prod.docker-compose.yaml`
and the same `roventics` project identity; this preserves backend private-data
mounts. Rebuild/deploy its frontend to publish the Job Talk card **after** the app
is approved for public use and the Job Talk staging gate is removed.

Once approved, remove the server-level `auth_basic` and `auth_basic_user_file`
lines in the shared edge's Job Talk HTTPS template, rebuild its proxy, then
publish the card:

```sh
cd ~/apps/edge-proxy
sh edge.sh up -d --build --wait proxy
cd ~/apps/roventics
docker compose -f prod.docker-compose.yaml up -d --build frontend
```

Keep the API's token checks and `auth_basic off` locations unchanged. Check the
public link in a fresh browser session. Disable any older certificate renewal
cron jobs/services identified during inventory once shared renewal is verified.

## Renewal and ordinary updates

`certbot-renew` checks every 12 hours. The proxy detects changed certificate/key
files every minute, runs `nginx -t`, and gracefully reloads only valid changes.
A failed validation keeps the currently running workers/configuration. No Docker
socket is mounted into public containers and no app owns certificate storage.

```sh
cd ~/apps/edge-proxy
sh edge.sh renew --dry-run              # verify Let's Encrypt renewal
sh edge.sh renew                        # manual check; automatic service also runs
sh edge.sh logs --tail=80 proxy certbot-renew
```

Back up the central certificate/ACME account volume securely as well as app data.
For app updates, build/recreate only that app's services; the edge resolves their
unique Docker aliases again without needing a proxy restart. For edge updates,
keep the previous built image/config before rebuilding. Never delete external
certificate/socket volumes or alter app database volume names during upgrades.

## Rollback

Before handoff: restore the reviewed original proxy config if needed and stop the
preview edge; application containers/data remain unchanged. Keep a valid current
certificate in the old listener once issued; do not restore the expired pair.

If the new public listener fails after handoff, restore preview mode to free the
public ports, then restart the retained old listener with its refreshed certificate:

```sh
cd ~/apps/edge-proxy
sh edge.sh preview up -d --wait proxy
docker start roventics-nginx-1
docker update --restart=unless-stopped roventics-nginx-1
```

This is a temporary Roventics fallback while investigating; it does not serve Job
Talk's UI. Keep the central certificates/renewal data, preserve the old listener's
ACME-forwarding config and restore the shared listener after fixing it. For later
edge updates, restore the last tested shared image/config against the same volumes.
For Job Talk failures alone, revert only its app image/config; do not restore its
old public proxy stack or disturb Roventics. Database rollback rules remain in
[database operations](database-operations.md).

## Local verification and sources

Run `powershell -ExecutionPolicy Bypass -File scripts/check-nginx-policies.ps1`
from Job Talk. It builds the real Job Talk/Roventics frontends, uses a disposable
Job Talk database and a simulated Roventics API in three isolated Compose projects,
and publishes no host ports. It does not send email or call AI/ACME. Live DNS,
trusted certificate issuance, renewal dry-run and real SMTP remain VM checks.

Verified locally on 2026-10-06: both frontends, API forwarding/authentication and
limits, old-proxy ACME forwarding for both domains, continued Roventics service
during a Job Talk outage/recreation, rejection of an invalid certificate and
automatic reload of a valid replacement. Existing app environment hashes were
unchanged. Real hiring/LLM usability checks remain recorded separately.

Protocol references: [Nginx variable upstreams](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass),
[Let's Encrypt HTTP-01](https://letsencrypt.org/docs/challenge-types/#http-01-challenge),
[Certbot webroot and renewal](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).
