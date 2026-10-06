param([switch]$SkipBuild)
# Three disposable Compose projects. Never reads a real .env or calls ACME/SMTP/AI.
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('jobtalk-policy-' + [guid]::NewGuid().ToString('N'))
$project = 'jt_edge_' + [guid]::NewGuid().ToString('N').Substring(0, 10)
$bundle = Join-Path $repo 'deploy/edge-proxy'
$app = @('--env-file', "$fixture/test.env", '-p', "${project}_app", '-f', "$repo/prod.docker-compose.yaml", '-f', "$fixture/app.yaml")
$edge = @('--env-file', "$fixture/test.env", '-p', "${project}_edge", '-f', "$bundle/compose.yaml", '-f', "$fixture/edge.yaml")
$rov = @('--env-file', "$fixture/test.env", '-p', "${project}_rov", '-f', "$fixture/roventics.yaml")
function Compose([string[]]$Files, [string[]]$Arguments) {
    & docker compose @Files @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Isolated Compose failed: $($Arguments -join ' ')" }
}
function Probe([string]$Mode) {
    $arguments = @('exec', '-T', '-e', 'PYTHONPATH=/app', 'backend', 'python', '/checks/nginx-policy-probe.py')
    if ($Mode) { $arguments += $Mode }
    Compose $app $arguments
}
function Certificate([string]$Domain) {
    & docker run --rm --user 0 --entrypoint sh -v "${fixture}:/fixtures" job-talk-backend:edge-check -c "openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=$Domain -keyout /fixtures/certificates/live/$Domain/privkey.pem -out /fixtures/certificates/live/$Domain/fullchain.pem 2>/dev/null"
    if ($LASTEXITCODE -ne 0) { throw 'Could not create disposable certificate' }
}
New-Item -ItemType Directory -Path "$fixture/certificates/live/jobtalk.roventics.com", "$fixture/certificates/live/roventics.com", "$fixture/challenges/.well-known/acme-challenge" -Force | Out-Null
try {
    @"
POSTGRES_DB=jt077_policy_test
POSTGRES_USER=job_talk
POSTGRES_PASSWORD=isolated-policy-database-password
APP_DOMAIN=jobtalk.roventics.com
SESSION_TOKEN_PEPPER=isolated-policy-session-pepper-more-than-32-characters
SMTP_HOST=smtp.policy.invalid
SMTP_USER=policy-check
SMTP_PASSWORD=isolated-policy-mail-password
EMAIL_FROM=policy-check@roventics.com
ADMIN_EMAIL=policy-check@roventics.com
GEMINI_API_KEY=
"@ | Set-Content -Encoding ASCII "$fixture/test.env"
    @"
services:
  backend:
    image: job-talk-backend:edge-check
    networks: [database, outbound, edge]
    environment:
      JOBTALK_POLICY_CHECK: '1'
      AI_PROVIDER: mock
      GEMINI_API_KEY: ''
    volumes:
      - '$($PSScriptRoot.Replace('\', '/')):/checks:ro'
      - '$($fixture.Replace('\', '/'))/certificates/live/jobtalk.roventics.com:/expected-certificate:ro'
  frontend:
    image: job-talk-frontend:edge-check
networks:
  edge:
    external: false
    name: ${project}_network
volumes:
  backend_socket:
    external: false
    name: ${project}_socket
"@ | Set-Content -Encoding ASCII "$fixture/app.yaml"
    @"
services:
  proxy:
    image: roventics-edge:check
    ports: !override []
    volumes: !override
      - 'jobtalk_socket:/run/jobtalk:ro'
      - '$($fixture.Replace('\', '/'))/certificates:/etc/letsencrypt:ro'
      - '$($fixture.Replace('\', '/'))/challenges:/var/www/certbot:ro'
      - '$($fixture.Replace('\', '/'))/htpasswd:/etc/nginx/auth/.htpasswd:ro'
networks:
  edge:
    name: ${project}_network
volumes:
  jobtalk_socket:
    name: ${project}_socket
"@ | Set-Content -Encoding ASCII "$fixture/edge.yaml"
    @"
services:
  legacy:
    image: nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
    volumes:
      - '$($bundle.Replace('\', '/'))/migration/roventics-acme.conf:/etc/nginx/conf.d/default.conf:ro'
      - '$($fixture.Replace('\', '/'))/certificates/live/roventics.com/fullchain.pem:/etc/nginx/certs/server.crt:ro'
      - '$($fixture.Replace('\', '/'))/certificates/live/roventics.com/privkey.pem:/etc/nginx/certs/server.key:ro'
    networks: [edge]
  frontend:
    image: roventics-frontend:edge-check
    build: '$(([IO.Path]::GetFullPath((Join-Path $repo '../roventics/frontend'))).Replace('\', '/'))'
    networks:
      edge:
        aliases: [roventics-frontend]
  backend:
    image: nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
    volumes:
      - '$($fixture.Replace('\', '/'))/roventics-api.conf:/etc/nginx/conf.d/default.conf:ro'
    networks:
      edge:
        aliases: [roventics-backend]
networks:
  edge:
    external: true
    name: ${project}_network
"@ | Set-Content -Encoding ASCII "$fixture/roventics.yaml"
    'server { listen 8080; location /api/ { return 200 "$request_uri|$host"; } }' | Set-Content -Encoding ASCII "$fixture/roventics-api.conf"
    'policy-challenge' | Set-Content -Encoding ASCII "$fixture/challenges/.well-known/acme-challenge/check"
    Compose $app @('config', '--quiet')
    Compose $edge @('config', '--quiet')
    if (-not $SkipBuild) {
        Compose $app @('build', 'backend', 'frontend')
        Compose $edge @('build', 'proxy')
        Compose $rov @('build', 'frontend')
    }
    $hash = docker run --rm --entrypoint openssl job-talk-backend:edge-check passwd -apr1 policy-staging-password
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated staging password' }
    "staging:$hash" | Set-Content -Encoding ASCII "$fixture/htpasswd"
    Certificate 'roventics.com'
    Compose $app @('up', '-d', '--wait', 'postgres', 'backend', 'frontend')
    # Edge must start even before the Roventics upstream containers exist.
    Compose $edge @('up', '-d', '--wait', 'proxy')
    Compose $rov @('up', '-d', '--wait')
    Probe '--bootstrap'
    Probe '--roventics'
    Probe '--legacy-acme'
    Certificate 'jobtalk.roventics.com'
    Compose $edge @('exec', '-T', 'proxy', 'edge-reload')
    Probe ''
    # A stopped Job Talk frontend must not break edge startup or Roventics.
    Compose $app @('stop', 'frontend')
    Compose $edge @('restart', 'proxy')
    Compose $edge @('up', '-d', '--wait', 'proxy')
    Probe '--roventics'
    Compose $app @('up', '-d', '--wait', '--force-recreate', 'frontend')
    Start-Sleep -Seconds 6
    Probe '--availability'
    # Malformed renewed certificates must not take the currently serving apps down.
    $certPath = "$fixture/certificates/live/jobtalk.roventics.com/fullchain.pem"
    $goodCert = [IO.File]::ReadAllText($certPath)
    [IO.File]::WriteAllText($certPath, 'invalid-certificate-for-isolated-test')
    & docker compose @edge exec -T proxy sh -c 'edge-reload >/dev/null 2>&1'
    if ($LASTEXITCODE -eq 0) { throw 'An invalid certificate was accepted' }
    Probe '--availability'
    [IO.File]::WriteAllText($certPath, $goodCert)
    Certificate 'jobtalk.roventics.com'
    Probe '--watch-certificate'
    Probe '--availability'
    $log = & docker compose @edge logs --no-color proxy 2>&1 | Out-String
    if ($log -notmatch 'by zone "jobtalk_auth"' -or $log -notmatch 'by zone "jobtalk_api"') { throw 'Proxy rate-limit checks did not activate' }
    Write-Output 'PASS: three independent stacks, both domains, private API/auth/policies, app outages/recreation, certificate activation and failed/valid reloads.'
} catch {
    & docker compose @edge logs --tail=30 proxy
    throw
} finally {
    # Only unique disposable projects; external shared production resources are not used.
    & docker compose @rov down --volumes --remove-orphans
    $cleanupFailed = $LASTEXITCODE -ne 0
    & docker compose @edge down --remove-orphans
    $cleanupFailed = $cleanupFailed -or $LASTEXITCODE -ne 0
    & docker compose @app down --volumes --remove-orphans
    if ($cleanupFailed -or $LASTEXITCODE -ne 0) { throw "Inspect isolated project $project and fixture $fixture; cleanup failed" }
    $resolved = [IO.Path]::GetFullPath($fixture)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolved -Leaf) -notmatch '^jobtalk-policy-[a-f0-9]{32}$') { throw 'Refusing unsafe fixture cleanup' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
