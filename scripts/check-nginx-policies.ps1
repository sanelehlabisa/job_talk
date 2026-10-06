param([switch]$SkipBuild)
# Disposable app and a stand-in for VM Nginx. No real .env/AI/SMTP.
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('jobtalk-policy-' + [guid]::NewGuid().ToString('N'))
$project = 'jt_host_' + [guid]::NewGuid().ToString('N').Substring(0, 10)
$compose = @('--env-file', "$fixture/test.env", '-p', $project, '-f', "$repo/prod.docker-compose.yaml", '-f', "$fixture/test.yaml")
function Compose([string[]]$Arguments) {
    & docker compose @compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Isolated Compose failed: $($Arguments -join ' ')" }
}
New-Item -ItemType Directory -Path $fixture | Out-Null
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
    $fixtureMount = $fixture.Replace('\', '/')
    @"
services:
  backend:
    image: job-talk-backend:host-check
    networks: [database, outbound, web]
    environment:
      JOBTALK_POLICY_CHECK: '1'
      AI_PROVIDER: mock
      GEMINI_API_KEY: ''
    volumes:
      - '$($PSScriptRoot.Replace('\', '/')):/checks:ro'
  frontend:
    image: job-talk-frontend:host-check
  gateway:
    image: job-talk-gateway:host-check
    ports: !override []
    volumes: !override
      - backend_socket:/run/jobtalk:ro
      - '${fixtureMount}/htpasswd:/etc/nginx/auth/.htpasswd:ro'
  proxy:
    image: nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
    volumes:
      - '${fixtureMount}/vm.conf:/etc/nginx/conf.d/default.conf:ro'
      - '${fixtureMount}/cert.pem:/fixtures/cert.pem:ro'
      - '${fixtureMount}/key.pem:/fixtures/key.pem:ro'
    networks: [web]
    depends_on:
      gateway:
        condition: service_healthy
"@ | Set-Content -Encoding ASCII "$fixture/test.yaml"
    $hostConfig = [IO.File]::ReadAllText("$repo/nginx/vm-jobtalk.conf")
    $hostConfig = $hostConfig.Replace('listen 80;', "listen 443 ssl;`n    ssl_certificate /fixtures/cert.pem;`n    ssl_certificate_key /fixtures/key.pem;")
    $hostConfig = $hostConfig.Replace('http://127.0.0.1:8081', 'http://gateway:80')
    $hostConfig += 'server { listen 80; server_name jobtalk.roventics.com; if ($host != "jobtalk.roventics.com") { return 444; } return 308 https://jobtalk.roventics.com$request_uri; }'
    [IO.File]::WriteAllText("$fixture/vm.conf", $hostConfig)
    Compose @('config', '--quiet')
    $definition = docker compose --env-file "$fixture/test.env" -f "$repo/prod.docker-compose.yaml" config --format json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Could not validate production ports' }
    $binding = $definition.services.gateway.ports
    if ($binding.Count -ne 1 -or $binding[0].host_ip -ne '127.0.0.1' -or $binding[0].published -ne '8081') { throw 'Gateway must bind only localhost:8081' }
    foreach ($service in @('backend', 'frontend', 'postgres')) {
        if ($definition.services.$service.ports) { throw "$service publishes an unexpected host port" }
    }
    foreach ($network in $definition.networks.PSObject.Properties.Value) {
        if ($network.external) { throw 'Production must not require an external network' }
    }
    if (-not $SkipBuild) { Compose @('build', 'backend', 'frontend', 'gateway') }
    $hash = docker run --rm --entrypoint openssl job-talk-backend:host-check passwd -apr1 policy-staging-password
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated staging password' }
    "staging:$hash" | Set-Content -Encoding ASCII "$fixture/htpasswd"
    docker run --rm --user 0 --entrypoint sh -v "${fixture}:/fixtures" job-talk-backend:host-check -c 'openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=jobtalk.roventics.com -keyout /fixtures/key.pem -out /fixtures/cert.pem 2>/dev/null'
    if ($LASTEXITCODE -ne 0) { throw 'Could not create disposable certificate' }
    Compose @('up', '-d', '--wait')
    Compose @('exec', '-T', '-e', 'PYTHONPATH=/app', 'backend', 'python', '/checks/nginx-policy-probe.py')
    $log = docker compose @compose logs --no-color gateway 2>&1 | Out-String
    if ($log -notmatch 'by zone "jobtalk_auth"' -or $log -notmatch 'by zone "jobtalk_api"') { throw 'Gateway rate limits did not activate' }
    Write-Output 'PASS: independent Compose, localhost-only gateway, host HTTPS routing and API/token protections.'
} catch {
    & docker compose @compose logs --tail=20 gateway proxy
    throw
} finally {
    & docker compose @compose down --volumes --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw "Inspect isolated project $project and fixture $fixture; cleanup failed" }
    $resolved = [IO.Path]::GetFullPath($fixture)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolved -Leaf) -notmatch '^jobtalk-policy-[a-f0-9]{32}$') { throw 'Refusing unsafe fixture cleanup' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
