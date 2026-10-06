# Deploy Job Talk behind VM Nginx

Each application owns its Docker Compose stack. The VM owns public routing and
HTTPS. Job Talk needs only this route:

```text
Browser -> VM Nginx (80/443) -> 127.0.0.1:8081 -> Job Talk gateway
                                                   |-- frontend
                                                   `-- private API socket -> database
```

No shared Docker stack, external network or certificate volumes. Existing `.env`
files are preserved. The examples below assume an Ubuntu/Debian VM with Docker
and host Nginx. They are instructions, not a record of a live deployment.

**Existing server:** earlier notes showed `roventics-nginx-1` owning 80/443.
Host Nginx must become the public listener before using this setup. Preserve the
existing website's routes and certificates during that separate server change;
do not blindly stop its container or start a second listener on the same ports.
This repository supplies only Job Talk's site configuration.

## 1. DNS

At the DNS provider for `roventics.com`, add an A record named `jobtalk` pointing
to `209.74.85.79`, after confirming that this is your VPS address. Preserve other
records. Check any conflicting AAAA record. There is no Linux command required
to create the subdomain.

```sh
getent ahostsv4 jobtalk.roventics.com
```

## 2. Start this app

Keep the VM's existing `.env` with `APP_DOMAIN=jobtalk.roventics.com` and its real
SMTP, Gemini, database and session settings. Do not replace it with the local
computer's file. Back up an existing database before upgrading; see
[database operations](database-operations.md). The project/database volume names
are unchanged. The application has no dependency on the other website's Compose.

```sh
cd ~/apps/job_talk
# Install apache2-utils if htpasswd is unavailable. It prompts for a password.
mkdir -p secrets/nginx
chmod 700 secrets/nginx
test -f secrets/nginx/.htpasswd || htpasswd -cB secrets/nginx/.htpasswd staging
chmod 644 secrets/nginx/.htpasswd
sh scripts/production-preflight.sh
docker compose --env-file .env -f prod.docker-compose.yaml up -d --build
curl --fail -H 'Host: jobtalk.roventics.com' http://127.0.0.1:8081/api/ready
# First installation only: creates the configured admin, retaining normal email login.
docker compose --env-file .env -f prod.docker-compose.yaml exec backend python -m app.recruiters seed
```

Only the app gateway publishes a port, on localhost:8081. Database and backend
have no host TCP listeners. Keep Docker Engine current for localhost binding
isolation. VM Nginx overwrites client forwarding headers; the app gateway trusts
private Docker source addresses for the client IP used by its request limits.
Tokens, approval and record ownership remain backend requirements.

If an older Job Talk proxy is still running, remove its obsolete listener only
as part of your reviewed server migration. Do not use `down -v` or touch another
application. The removed shared-edge implementation was never deployed by us.

## 3. Add one VM Nginx site

On a VM where host Nginx already handles the existing website:

```sh
cd ~/apps/job_talk
# Back up an existing Job Talk site before replacing it, especially after Certbot.
sudo cp nginx/vm-jobtalk.conf /etc/nginx/sites-available/jobtalk
sudo ln -sfn /etc/nginx/sites-available/jobtalk /etc/nginx/sites-enabled/jobtalk
sudo nginx -t && sudo systemctl reload nginx
```

The site forwards the whole hostname to localhost:8081, preserving `/api/`.
It does not change the other website's site files. This initial HTTP config is
for certificate setup; use the app only over HTTPS after the next step.

## 4. HTTPS and automatic renewal

Install Certbot's Nginx package if it is not already present. Use the same admin
email already configured for Job Talk when Certbot asks for the registration email.
No new environment variable is needed.

```sh
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d jobtalk.roventics.com --redirect
sudo systemctl enable --now certbot.timer
sudo certbot renew --dry-run
systemctl list-timers --all | grep certbot
```

Certbot installs the certificate and redirect in the host site and stores TLS
state under `/etc/letsencrypt`. Its timer renews automatically; there is no
application renewal container or custom watcher. Use the installed scheduler
instead if this VM already uses another Certbot installation. Never run duplicate
renewal schedulers. The manual renewal check is simply `sudo certbot renew`.

Do not overwrite Certbot's modified site with the original HTTP file during
ordinary app updates. Back up VM Nginx configuration and certificates separately
from application data.

## 5. Verify, then update normally

```sh
curl --fail https://jobtalk.roventics.com/api/ready
curl --fail https://roventics.com/
```

Test emailed recruiter login, job publication, candidate application, comparison
and logout in the browser. Keep private staging until the user accepts the flow.
For public launch, remove only the server-level `auth_basic` and
`auth_basic_user_file` lines in `nginx/app.conf.template`, rebuild the gateway,
and verify an anonymous browser can open the app. API token controls stay intact.

Ordinary app updates need only:

```sh
cd ~/apps/job_talk
docker compose --env-file .env -f prod.docker-compose.yaml up -d --build
```

Keep the previous app images/commit for rollback and never remove database volumes.
Changing Job Talk should not require restarting VM Nginx or the other application.
If a site change fails, restore that site's backup, run `nginx -t`, then reload.

## Local verification

Run `powershell -ExecutionPolicy Bypass -File scripts/check-nginx-policies.ps1`.
It checks the real Compose definition for localhost-only ports and no external
network, then exercises an isolated app behind simulated VM Nginx with self-signed
TLS. It checks frontend assets, API policies, tokens, email-code redemption and
logout using a disposable database and no SMTP/AI calls. Live DNS, trusted
issuance, renewal and the actual hiring flow still need server/user verification.

References: [Certbot Nginx and renewal](https://eff-certbot.readthedocs.io/en/stable/using.html),
[Docker localhost port publishing](https://docs.docker.com/engine/network/port-publishing/).
