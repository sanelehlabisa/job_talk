# Database operations

Job Talk applies versioned Alembic migrations before FastAPI starts. A failed
migration stops the backend container, so it cannot serve against a partly
upgraded schema.

## Create a backup

Run this on the VM from the release directory before every deployment and from
a daily scheduler:

```sh
BACKUP_RETENTION_DAYS=7 ./scripts/backup-postgres.sh
```

The script uses `prod.docker-compose.yaml` and `.env` by
default. Override `COMPOSE_FILE`, `ENV_FILE`, or `BACKUP_DIR` when needed. It
creates a PostgreSQL custom-format dump, verifies that `pg_restore` can read its
catalog, writes a SHA-256 checksum, grants owner-only file access, and deletes
backup files older than the configured retention period.

Copy backups to storage outside the VM. A backup on the same disk does not
protect against VM or disk loss. Never commit backup files.

## Prove a backup can be restored

Restore into a separate database on the running PostgreSQL service:

```sh
./scripts/restore-postgres.sh backups/postgres/job-talk-YYYYMMDDTHHMMSSZ.dump job_talk_restore_check
```

The command refuses invalid database names and refuses to overwrite the primary
database. After checking the restored data, remove only the temporary database:

```sh
docker compose --env-file .env -f prod.docker-compose.yaml \
  exec -T postgres sh -c 'dropdb --username="$POSTGRES_USER" job_talk_restore_check'
```

For a full clean-stack drill, start only PostgreSQL with a new Compose project
and empty volume, then restore into its empty configured database:

```sh
COMPOSE_PROJECT_NAME=job_talk_restore \
  docker compose --env-file .env -f prod.docker-compose.yaml up -d postgres
COMPOSE_PROJECT_NAME=job_talk_restore \
  ./scripts/restore-postgres.sh BACKUP_FILE job_talk --allow-primary-empty
```

Start the backend only after restore succeeds. Verify the health endpoint,
recruiter login, job count, candidate count, and one known record before deleting
the temporary Compose project and volume.

## Update an existing database password

`POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` come from your `.env`.
The PostgreSQL image only initializes them when its data directory is empty.
An existing database retains its stored password across container rebuilds.

If you changed `.env` and see `password authentication failed`, connect through
the database container's local socket, using its configured role:

```sh
docker compose --env-file .env -f prod.docker-compose.yaml exec postgres \
  sh -c 'exec psql -U "$POSTGRES_USER" -d postgres'
```

At the psql prompt run `\password`, enter the same password now saved in `.env`
twice (input is hidden), then `\q`. Do not include `.env` quoting characters.
This updates the current role without deleting data. If the local login fails,
stop and inspect that error; do not reset the database or remove its volume.
Then run the normal production startup command and check `/api/ready`.

For a planned rotation, take a backup first and update both the stored role
password and `.env` together. Keep the existing working values during deployment.

## Upgrade and rollback

1. Record the deployed Git commit and current database revision with
   `alembic current`.
2. Create and copy a verified backup off the VM.
3. Check out the new commit, rebuild the images and start the backend. Its entrypoint runs
   `alembic upgrade head` before Uvicorn.
4. Check backend logs, `/api/health`, and the recruiter and candidate smoke flow.

To roll back an application-only release, rebuild and deploy the previous Git commit.
If its schema is compatible, leave the database at the newer revision. For a
reversible schema change, stop the backend and run the exact documented Alembic
downgrade before starting the previous image. For a destructive or irreversible
change, restore the pre-deployment backup into a clean database and point the
previous image at it. Never guess a downgrade target on the production database.
