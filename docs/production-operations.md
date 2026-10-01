# Production Compose operations

The production package keeps PostgreSQL, FastAPI, and the built frontend on
private Compose networks. Only the Nginx proxy publishes host ports 80 and 443.
Run every command from the release directory on the VM.

## Prepare a release

1. Check out the exact Git commit to deploy.
2. Copy `.env.production.example` to `.env.production` and replace every
   placeholder. Set `JOB_TALK_IMAGE_TAG` to the full Git commit SHA.
3. Place the certificate chain and private key at
   `secrets/tls/fullchain.pem` and `secrets/tls/privkey.pem`. The certificate
   issue and renewal workflow belongs to `JT-010`.
4. Validate the resolved configuration without printing it, because resolved
   output contains secrets:

```sh
docker compose --env-file .env.production -f production.docker-compose.yaml config --quiet
```

Build the two application images. Both receive the same immutable release tag;
only `/api` is compiled into the browser bundle.

```sh
docker compose --env-file .env.production -f production.docker-compose.yaml build backend frontend
```

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
docker compose --env-file .env.production -f production.docker-compose.yaml logs --tail=200 backend proxy
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
docker compose --env-file .env.production -f production.docker-compose.yaml build backend frontend
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

This keeps the named PostgreSQL volume. Using `down -v` permanently deletes the
database volume and is reserved for an intentional, verified teardown.
