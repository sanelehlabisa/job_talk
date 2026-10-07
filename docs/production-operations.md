# Deploy Job Talk through the existing Roventics proxy

The VPS keeps its current public edge:

```text
Internet -> roventics-nginx-1 (80/443)
              |-- roventics.com -> existing Roventics services
              `-- jobtalk.roventics.com -> jobtalk-gateway:80
```

Each repository owns its own Compose project, environment, services and data.
The only shared resource is the private `roventics_proxy` Docker network between
the existing public proxy and Job Talk's gateway. Job Talk also publishes
`127.0.0.1:8081` for checks made directly on the VPS. It never publishes 80/443.
The network is needed because Docker's host-gateway address cannot reach a
service published only on the host's loopback address.

These are operator commands, not a record of a live deployment. Do not use
`docker system prune`, `docker compose down -v`, or stop unrelated containers.
Never replace an existing `.env` with `.env.example`.

## 1. Add and verify DNS

At the DNS provider for `roventics.com`, add:

```text
Type: A
Name: jobtalk
Value: 209.74.85.79
TTL: default
```

Confirm the address belongs to this VPS and check for a conflicting AAAA record:

```sh
dig NS roventics.com +short
getent ahostsv4 jobtalk.roventics.com
```

## 2. Inspect the running VPS before changing it

The commands below assume the reported container name is still correct. Stop if
the names, certificate path, Compose directory or renewal mechanism differ.

```sh
docker ps --format 'table {{.Names}}\t{{.Ports}}'
docker inspect roventics-nginx-1 --format '{{json .Mounts}}'
docker inspect roventics-nginx-1 --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }} {{ index .Config.Labels "com.docker.compose.project.config_files" }}'
docker exec roventics-nginx-1 nginx -T > /tmp/roventics-nginx-before.txt
sudo certbot certificates
systemctl list-timers --all | grep -i certbot || true
sudo crontab -l
sudo test -r /etc/letsencrypt/live/roventics.com/fullchain.pem
sudo test -r /etc/letsencrypt/live/roventics.com/privkey.pem
```

Back up the live Nginx configuration, Compose file, certificate state and both
applications' data before proceeding. The repository expects the certificate
name to be `roventics.com`. If Certbot reports another name, update the two paths
in `roventics/nginx/nginx.conf` before deploying it.

```sh
umask 077
deployment_backup="$HOME/backups/jobtalk-edge-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$deployment_backup"
docker cp roventics-nginx-1:/etc/nginx/conf.d/default.conf "$deployment_backup/roventics-nginx.conf"
docker inspect roventics-nginx-1 --format '{{.Image}}' > "$deployment_backup/nginx-image-id"
sudo tar -C /etc -czf "$deployment_backup/letsencrypt.tar.gz" letsencrypt
```

Copy the live Compose file reported by Docker inspection into the same directory.
Keep it until both domains and renewal have passed. Use the separate
[database backup procedure](database-operations.md) for Job Talk data.

## 3. Clone or update each repository independently

These changes are on feature branches awaiting merge approval. Use the branch
names below until merged; then use `master`. For the existing VPS, set
`roventics_repo` to the Compose working directory reported in step 2. Reuse that
checkout so its `backend/.env` and `backend/private` mounts remain unchanged.
Likewise reuse an existing Job Talk checkout if present.

Only clone a repository if it is not already installed:

```sh
mkdir -p "$HOME/apps"
roventics_repo="$HOME/apps/roventics" # Existing VPS: use inspected directory instead.
jobtalk_repo="$HOME/apps/job_talk"
git clone --branch fix/jobtalk-vhost https://github.com/sanelehlabisa/roventics.git "$roventics_repo"
git clone --branch fix/existing-roventics-edge https://github.com/sanelehlabisa/job_talk.git "$jobtalk_repo"
```

For existing checkouts, preserve local files and inspect changes before pulling:

```sh
git -C "$roventics_repo" status --short
git -C "$jobtalk_repo" status --short
git -C "$roventics_repo" fetch origin
git -C "$jobtalk_repo" fetch origin
git -C "$roventics_repo" switch fix/jobtalk-vhost
git -C "$jobtalk_repo" switch fix/existing-roventics-edge
git -C "$roventics_repo" pull --ff-only
git -C "$jobtalk_repo" pull --ff-only
```

Keep each repository's ignored environment files. Job Talk's VM `.env` must use
`APP_DOMAIN=jobtalk.roventics.com` plus its real database, SMTP, session and
Gemini values.
For a fresh Job Talk clone only, copy `.env.example` to `.env` and fill its blank
values before continuing. For a fresh Roventics installation, supply its own
`backend/.env` and `backend/private` files. Never overwrite the live copies.
The commands require Docker Compose v2, Certbot and `htpasswd` (Ubuntu package
`apache2-utils`). The existing Roventics project must be named `roventics`, with
`roventics-frontend-1` and `roventics-backend-1`; the proxy uses these existing
names so neither app container needs a restart for the proxy change.

## 4. Prepare Job Talk and the private proxy network

```sh
docker network inspect roventics_proxy >/dev/null 2>&1 || docker network create roventics_proxy

cd "$jobtalk_repo"
mkdir -p secrets/nginx
chmod 700 secrets/nginx
test -f secrets/nginx/.htpasswd || htpasswd -cB secrets/nginx/.htpasswd staging
chmod 644 secrets/nginx/.htpasswd
umask 022
sh scripts/production-preflight.sh
docker compose --env-file .env -f prod.docker-compose.yaml up -d --build --wait
curl --fail -H 'Host: jobtalk.roventics.com' http://127.0.0.1:8081/api/ready
```

Seed the configured admin once. This keeps normal emailed-code login:

```sh
docker compose --env-file .env -f prod.docker-compose.yaml exec backend python -m app.recruiters seed
```

## 5. Recreate only the Roventics Nginx container

The updated Compose connects the proxy to `roventics_proxy` and mounts the VPS's
`/etc/letsencrypt` and `/var/www/certbot` read-only. Its Nginx configuration keeps
the current Roventics routes and adds the Job Talk hostname. Recreating this one
container is required for the mounts and network; frontend and backend stay up.
On a fresh Roventics installation only, start those two services first with
`docker compose -f docker-compose.yaml up -d --build backend frontend` from its
checkout. This VPS already has them running. The certificate paths checked in
step 2 must exist before starting the proxy.

```sh
sudo mkdir -p /var/www/certbot
cd "$roventics_repo"
docker compose -f docker-compose.yaml config --quiet
docker compose -f docker-compose.yaml build nginx
docker compose -f docker-compose.yaml run --rm --no-deps nginx nginx -t
docker compose -f docker-compose.yaml up -d --no-deps nginx
docker exec roventics-nginx-1 nginx -t
curl --fail https://roventics.com/
docker exec roventics-nginx-1 wget -q -O- \
  --header='Host: jobtalk.roventics.com' http://jobtalk-gateway/api/ready
```

Do not recreate the proxy if the preflight `nginx -t` fails. There is a brief
public-proxy restart; both application containers keep running. Always run
`docker exec roventics-nginx-1 nginx -t` before a reload. Job Talk's HTTPS
certificate will not validate until step 6 completes; the root site retains
its existing valid certificate.

## 6. Extend the existing certificate safely

Certbot requires every domain already on a certificate to be repeated when it is
replaced. Read the `Domains:` line from `sudo certbot certificates`. If the
current certificate contains only `roventics.com`, run:

```sh
sudo certbot certonly --webroot -w /var/www/certbot \
  --cert-name roventics.com --expand \
  -d roventics.com -d jobtalk.roventics.com
```

If it already contains `www.roventics.com`, preserve it:

```sh
sudo certbot certonly --webroot -w /var/www/certbot \
  --cert-name roventics.com --expand \
  -d roventics.com -d www.roventics.com -d jobtalk.roventics.com
```

Preserve every existing certificate domain, including any not shown in these
examples. If an existing name such as `www` does not resolve here, fix its DNS
before issuance; do not silently drop it. Do not delete the working certificate.
After issuance:

```sh
docker exec roventics-nginx-1 nginx -t
docker exec roventics-nginx-1 nginx -s reload
curl --fail https://roventics.com/
curl --fail https://jobtalk.roventics.com/api/ready
```

## 7. Keep the existing Certbot scheduler

Use the scheduler found in step 2. Do not add a second timer or cron job. Inspect
existing renewal hooks first; replace any old hook that stops Nginx for standalone
renewal now that HTTP validation uses webroot. If a deploy hook already reloads
this container, reuse it. Otherwise add this one so renewed certificates load:

```sh
sudo install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-roventics-nginx.sh >/dev/null <<'EOF'
#!/bin/sh
set -eu
docker exec roventics-nginx-1 nginx -t
docker exec roventics-nginx-1 nginx -s reload
EOF
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-roventics-nginx.sh
sudo certbot renew --dry-run --run-deploy-hooks
```

## 8. Final browser checks

1. Open `https://roventics.com` and its existing inquiry flow.
2. Open `https://jobtalk.roventics.com` with the staging password.
3. Sign in as the approved recruiter through email code.
4. Create and publish a job.
5. Apply without an account and submit consent/contact details.
6. Confirm candidate comparison and logout.

Publish the Roventics card only after this passes. For public Job Talk launch,
remove only the two server-level `auth_basic` lines from
`job_talk/nginx/app.conf.template`, rebuild Job Talk's gateway and verify again.
API token, approval, ownership and guest-scope checks remain required.
Rebuild the gateway with the normal Job Talk startup command. Then publish the
updated website card without restarting its backend:

```sh
cd "$roventics_repo"
docker compose -f docker-compose.yaml up -d --build --no-deps frontend
docker exec roventics-nginx-1 nginx -t
docker exec roventics-nginx-1 nginx -s reload
```

## Updates and rollback

Ordinary Job Talk updates do not rebuild or restart Roventics:

```sh
cd "$jobtalk_repo"
git pull --ff-only
docker compose --env-file .env -f prod.docker-compose.yaml up -d --build --wait
```

If the public proxy change fails, restore the backed-up Roventics Nginx files,
run `nginx -t`, and recreate or reload only `roventics-nginx-1`. Keep the latest
valid `/etc/letsencrypt` data and never remove application database volumes.

## Local verification

`scripts/check-nginx-policies.ps1` uses an isolated Compose fixture, disposable
PostgreSQL and certificates. It runs Job Talk's production services and the
actual Roventics Nginx configuration/frontend, with a simulated Roventics API.
Private routing, both hostname/ACME routes, token scope, logout and rate limits
passed on 2026-10-07. It does not verify live SMTP, Gemini, DNS, the existing VPS
containers or Let's Encrypt. Existing website inquiries and the live hiring flow
remain operator acceptance checks.

References: [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/)
and [Certbot renewal hooks](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).
