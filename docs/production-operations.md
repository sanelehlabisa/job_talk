# Production Compose operations

The production package keeps PostgreSQL, FastAPI, and the built frontend on
private Compose networks. Only the Nginx proxy publishes host ports 80 and 443.
Run every command from the release directory on the VM.

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
chmod 600 secrets/nginx/.htpasswd
```

Keep this authentication enabled until the public-pilot safety checks pass.
The ignored `STAGING_HTPASSWD_PATH` setting may point to a different file.
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
docker compose --env-file .env.production -f production.docker-compose.yaml config --quiet
```

Build the three application images. All receive the same immutable release tag;
only `/api` is compiled into the browser bundle.

```sh
docker compose --env-file .env.production -f production.docker-compose.yaml build backend frontend proxy
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
docker compose --env-file .env.production -f production.docker-compose.yaml up -d
docker compose --env-file .env.production -f production.docker-compose.yaml ps
curl --fail --silent --show-error "https://$APP_DOMAIN/api/ready"
```

`postgres`, `backend`, and `frontend` must show healthy. The proxy becomes
healthy only after both application services are healthy. In `docker compose
ps`, only the proxy may show published host ports, specifically `80->80` and
`443->443`.

The lightweight `/api/health` endpoint confirms the process is alive.
`/api/ready` also executes a database query and is used by the backend
container health check.

## Logs and routine commands

```sh
docker compose --env-file .env.production -f production.docker-compose.yaml logs --tail=200 backend proxy certbot-renew
docker compose --env-file .env.production -f production.docker-compose.yaml restart proxy
docker compose --env-file .env.production -f production.docker-compose.yaml stop
docker compose --env-file .env.production -f production.docker-compose.yaml start
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
docker compose --env-file .env.production -f production.docker-compose.yaml config --quiet
docker compose --env-file .env.production -f production.docker-compose.yaml build backend frontend proxy
docker compose --env-file .env.production -f production.docker-compose.yaml up -d
docker compose --env-file .env.production -f production.docker-compose.yaml ps
```

The backend entrypoint applies Alembic migrations before starting Uvicorn. A
failed migration leaves the backend unhealthy and prevents the proxy from
starting.

## Roll back

Set `JOB_TALK_IMAGE_TAG` back to the previously recorded tag and recreate the
application services:

```sh
docker compose --env-file .env.production -f production.docker-compose.yaml up -d --no-build backend frontend proxy
```

This assumes the previous tagged images remain on the VM and the database
schema is backward compatible. Follow the database rollback rules in
[`database-operations.md`](database-operations.md) when a migration is not
backward compatible.

## Shut down

```sh
docker compose --env-file .env.production -f production.docker-compose.yaml down
```

This keeps the named PostgreSQL and certificate volumes. Using `down -v`
permanently deletes the database and certificate volumes and is reserved for an
intentional, verified teardown.
