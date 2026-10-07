param([switch]$SkipBuild)
# Disposable app and public-proxy fixtures. Never reads a real .env or calls ACME/SMTP/AI.
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$roventics = [IO.Path]::GetFullPath((Join-Path $repo '../roventics'))
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('jobtalk-policy-' + [guid]::NewGuid().ToString('N'))
$project = 'jt_proxy_' + [guid]::NewGuid().ToString('N').Substring(0, 10)
$proxyNetwork = "${project}_network"
$compose = @('--env-file', "$fixture/test.env", '-p', $project, '-f', "$repo/prod.docker-compose.yaml", '-f', "$fixture/test.yaml")

function Compose([string[]]$Arguments) {
    & docker compose @compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Isolated Compose failed: $($Arguments -join ' ')" }
}

New-Item -ItemType Directory -Path "$fixture/certificates/live/roventics.com", "$fixture/challenges/.well-known/acme-challenge" -Force | Out-Null
try {
    docker network create $proxyNetwork | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the disposable proxy network' }
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
    $fixtureMount = $fixture.Replace('\', '/')
    @"
services:
  backend:
    image: job-talk-backend:proxy-check
    networks: [database, outbound, web, public_proxy]
    environment:
      JOBTALK_POLICY_CHECK: '1'
      AI_PROVIDER: mock
      GEMINI_API_KEY: ''
    volumes:
      - '$($PSScriptRoot.Replace('\', '/')):/checks:ro'
  frontend:
    image: job-talk-frontend:proxy-check
  gateway:
    image: job-talk-gateway:proxy-check
    ports: !override []
    volumes: !override
      - backend_socket:/run/jobtalk:ro
      - '${fixtureMount}/htpasswd:/etc/nginx/auth/.htpasswd:ro'
  roventics_frontend:
    image: roventics-frontend:proxy-check
    build: '$((Join-Path $roventics 'frontend').Replace('\', '/'))'
    networks:
      roventics:
        aliases: [roventics-frontend-1]
  roventics_backend:
    image: nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
    volumes:
      - '${fixtureMount}/roventics-api.conf:/etc/nginx/conf.d/default.conf:ro'
    networks:
      roventics:
        aliases: [roventics-backend-1]
  proxy:
    image: nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
    volumes:
      - '$((Join-Path $roventics 'nginx/nginx.conf').Replace('\', '/')):/etc/nginx/conf.d/default.conf:ro'
      - '${fixtureMount}/certificates:/etc/letsencrypt:ro'
      - '${fixtureMount}/challenges:/var/www/certbot:ro'
    networks: [roventics, public_proxy]
    depends_on: [roventics_frontend, roventics_backend, gateway]
networks:
  public_proxy:
    name: ${proxyNetwork}
  roventics:
"@ | Set-Content -Encoding ASCII "$fixture/test.yaml"
    'server { listen 8080; location /api/ { return 200 "$request_uri|$host"; } }' | Set-Content -Encoding ASCII "$fixture/roventics-api.conf"
    'policy-challenge' | Set-Content -Encoding ASCII "$fixture/challenges/.well-known/acme-challenge/check"
    Compose @('config', '--quiet')
    $definition = docker compose --env-file "$fixture/test.env" -f "$repo/prod.docker-compose.yaml" -f "$fixture/test.yaml" config --format json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Could not validate production ports' }
    foreach ($service in @('backend', 'frontend', 'postgres')) {
        if ($definition.services.$service.ports) { throw "$service publishes an unexpected host port" }
    }
    if ($definition.services.gateway.ports) { throw 'The isolated fixture must publish no host ports' }
    if ($definition.networks.public_proxy.name -ne $proxyNetwork) { throw 'Proxy network override failed' }
    if (-not $SkipBuild) {
        Compose @('build', 'backend', 'frontend', 'gateway', 'roventics_frontend')
    }
    $hash = docker run --rm --entrypoint openssl job-talk-backend:proxy-check passwd -apr1 policy-staging-password
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated staging password' }
    "staging:$hash" | Set-Content -Encoding ASCII "$fixture/htpasswd"
    docker run --rm --user 0 --entrypoint sh -v "${fixture}:/fixtures" job-talk-backend:proxy-check -c 'openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=roventics.com -addext subjectAltName=DNS:roventics.com,DNS:jobtalk.roventics.com -keyout /fixtures/certificates/live/roventics.com/privkey.pem -out /fixtures/certificates/live/roventics.com/fullchain.pem 2>/dev/null'
    if ($LASTEXITCODE -ne 0) { throw 'Could not create disposable certificate' }
    Compose @('up', '-d', '--wait')
    Compose @('exec', '-T', '-e', 'PYTHONPATH=/app', 'backend', 'python', '/checks/nginx-policy-probe.py')
    $log = docker compose @compose logs --no-color gateway 2>&1 | Out-String
    if ($log -notmatch 'by zone "jobtalk_auth"' -or $log -notmatch 'by zone "jobtalk_api"') { throw 'Gateway rate limits did not activate' }
    Write-Output 'PASS: public proxy configuration, private routing, both websites and Job Talk API/token protections (Roventics API simulated).'
} catch {
    & docker compose @compose logs --tail=20 gateway proxy
    throw
} finally {
    & docker compose @compose down --volumes --remove-orphans
    $cleanupFailed = $LASTEXITCODE -ne 0
    docker network rm $proxyNetwork 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { $cleanupFailed = $true }
    if ($cleanupFailed) { throw "Inspect isolated project $project and fixture $fixture; cleanup failed" }
    $resolved = [IO.Path]::GetFullPath($fixture)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolved -Leaf) -notmatch '^jobtalk-policy-[a-f0-9]{32}$') { throw 'Refusing unsafe fixture cleanup' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
