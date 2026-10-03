# Production Compose operations

The production package keeps PostgreSQL, FastAPI, and the built frontend on
private Compose networks. Only the Nginx proxy publishes host ports 80 and 443.
Run every command from the release directory on the VM.

The file is **`prod.docker-compose.yaml`**. Port **80** is the HTTP entry point;
it redirects to **HTTPS on 443** after certificate setup. Before a certificate
exists, port 80 serves only ACME challenges and `/proxy-health`; app requests
return 503 so sign-in never runs over plain HTTP.

The default project name is `job_talk_prod`, keeping production containers and
volumes separate from development. If upgrading an older production installation
named `job_talk`, set `COMPOSE_PROJECT_NAME=job_talk` in its `.env.production` to
retain its existing volumes. Do not run that older project beside development.

## Prepare a release

1. Check out the exact Git commit to deploy and confirm the working tree is clean.
2. Copy `.env.production.example` to `.env.production` and replace every
   placeholder. Set `JOB_TALK_IMAGE_TAG` to the full Git commit SHA. The
   preflight rejects a tag that differs from the checked-out commit so all three
   application images share the reviewed release identity.
3. Create the private staging password file. `htpasswd` prompts for the password
   so it does not appear in shell history:

```sh
mkdir -p secrets/nginx
chmod 700 secrets/nginx
htpasswd -cB secrets/nginx/.htpasswd staging
# Nginx workers must read the mounted hash file; its host directory stays private.
chmod 644 secrets/nginx/.htpasswd
```

This password gates the staging webpage. `/api/` uses Job Talk's existing
Bearer-token checks; public API endpoints remain public through Nginx and private
ones still require an authorized session. Requiring HTTP Basic there would
conflict with the app's `Authorization: Bearer ...` header. This uses Nginx's
[per-location authentication override](https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html#auth_basic).
Keep the webpage gate enabled until the public-pilot safety checks pass.
The ignored `STAGING_HTPASSWD_PATH` setting may point to a different file.
Set `ADMIN_EMAIL` to the operator's approved recruiter address, if needed. Choose
`AI_PROVIDER=gemini` with `GEMINI_API_KEY` and `GEMINI_MODEL` (or explicitly choose
`mock` for a local configuration check). Never copy development database
credentials or publish ports for the backend, frontend or PostgreSQL.

4. After DNS points to the VM, run the preflight without printing resolved
configuration or secrets. Pass the VM's public IPv4 address so the DNS check
also rejects a record that points to another host:

```sh
EXPECTED_PUBLIC_IP=203.0.113.10 ./scripts/production-preflight.sh
```

The check rejects example values, inconsistent origin settings, a missing
staging password file, unresolved or mismatched DNS, and an invalid production
Compose configuration.

5. You can also validate only the resolved Compose configuration without
printing it, because resolved output contains secrets:

```sh
docker compose --env-file .env.production -f prod.docker-compose.yaml config --quiet
```

Build the three application images. All receive the same immutable release tag;
only `/api` is compiled into the browser bundle.

```sh
docker compose --env-file .env.production -f prod.docker-compose.yaml build backend frontend proxy
```

## Issue and renew TLS certificates

After the subdomain points to the VM and inbound port 80 is open, issue the first
Let's Encrypt certificate:

```sh
./scripts/issue-certificate.sh
```

The proxy starts in a limited HTTP bootstrap mode that serves only ACME
challenges and a health check. The script obtains the certificate, switches the
proxy to HTTPS, and validates the resulting Nginx configuration.

The pinned `certbot-renew` service checks for renewal every 12 hours. Nginx
hashes the mounted certificate each hour by default and reloads gracefully when
the contents change. Change `CERTIFICATE_RELOAD_SECONDS` only when testing.
Run a Let's Encrypt staging renewal test after the real certificate exists:

```sh
./scripts/renew-certificate.sh --dry-run
```

A successful dry run must leave repeated HTTPS readiness requests available.
The certificate data lives in the `letsencrypt` named volume and remains after a
normal Compose shutdown.

## Start and verify

```sh
docker compose --env-file .env.production -f prod.docker-compose.yaml up -d
docker compose --env-file .env.production -f prod.docker-compose.yaml ps
APP_DOMAIN=$(sed -n 's/^APP_DOMAIN=//p' .env.production | tr -d '\r')
curl --fail --silent --show-error "https://$APP_DOMAIN/api/ready"
```

`postgres`, `backend`, and `frontend` must show healthy. The proxy becomes
healthy only after both application services are healthy. In `docker compose
ps`, only the proxy may show published host ports, specifically `80->80` and
`443->443`.

The lightweight `/api/health` endpoint confirms the process is alive.
`/api/ready` also executes a database query and is used by the backend
container health check. The internal probe sends `Host: APP_DOMAIN` so it passes
the same allowed-host checks as public traffic without adding a public backend port.

**Local verification (2026-10-03):** The production images and isolated Compose
stack passed startup, HTTP bootstrap, certificate-watcher activation, 80-to-443
redirect, ACME, Nginx syntax, gated frontend, API readiness and scoped guest-token
access. Only Nginx had published ports. The check used loopback test ports and a
disposable self-signed certificate; it does not establish public DNS, a trusted
certificate, real SMTP delivery, or Let's Encrypt renewal. Run the documented
issuance and `renew --dry-run` on the VM after configuring the real domain.

## Logs and routine commands

```sh
docker compose --env-file .env.production -f prod.docker-compose.yaml logs --tail=200 backend proxy certbot-renew
docker compose --env-file .env.production -f prod.docker-compose.yaml restart proxy
docker compose --env-file .env.production -f prod.docker-compose.yaml stop
docker compose --env-file .env.production -f prod.docker-compose.yaml start
```

Do not run `docker compose config` without `--quiet` in shared terminals or CI
logs because it expands environment secrets.

## Upgrade

1. Record the current Git commit and `JOB_TALK_IMAGE_TAG`.
2. Create and verify a database backup using
   [`database-operations.md`](database-operations.md).
3. Check out the new commit and set `JOB_TALK_IMAGE_TAG` to that full SHA.
4. Validate and build the new images.
5. Recreate the services and wait for readiness:

```sh
docker compose --env-file .env.production -f prod.docker-compose.yaml config --quiet
docker compose --env-file .env.production -f prod.docker-compose.yaml build backend frontend proxy
docker compose --env-file .env.production -f prod.docker-compose.yaml up -d
docker compose --env-file .env.production -f prod.docker-compose.yaml ps
```

The backend entrypoint applies Alembic migrations before starting Uvicorn. A
failed migration leaves the backend unhealthy and prevents the proxy from
starting.

## Roll back

Set `JOB_TALK_IMAGE_TAG` back to the previously recorded tag and recreate the
application services:

```sh
docker compose --env-file .env.production -f prod.docker-compose.yaml up -d --no-build backend frontend proxy
```

This assumes the previous tagged images remain on the VM and the database
schema is backward compatible. Follow the database rollback rules in
[`database-operations.md`](database-operations.md) when a migration is not
backward compatible.

## Shut down

```sh
docker compose --env-file .env.production -f prod.docker-compose.yaml down
```

This keeps the named PostgreSQL and certificate volumes. Using `down -v`
permanently deletes the database and certificate volumes and is reserved for an
intentional, verified teardown.
