param([switch]$SkipBuild)

# Disposable production check: no real .env, host ports, mail or model calls.
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$fixture = Join-Path ([IO.Path]::GetTempPath()) ("jobtalk-policy-" + [guid]::NewGuid().ToString('N'))
$project = 'jt_policy_' + [guid]::NewGuid().ToString('N').Substring(0, 12)
$imageTag = 'jt078-policy-check'
$compose = @('--env-file', "$fixture/test.env", '-p', $project,
    '-f', "$repo/prod.docker-compose.yaml", '-f', "$fixture/override.yaml")

function Invoke-Compose([string[]]$Arguments) {
    & docker compose @compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Isolated Compose check failed: $($Arguments[0])" }
}

New-Item -ItemType Directory -Path "$fixture/certificates/live/jobtalk.roventics.com", "$fixture/challenges/.well-known/acme-challenge" -Force | Out-Null
try {
    # These deliberately fictional credentials are only for disposable containers.
    @"
POSTGRES_DB=jt077_policy_test
POSTGRES_USER=job_talk
POSTGRES_PASSWORD=isolated-policy-database-password
DATABASE_URL=postgresql+psycopg://job_talk:isolated-policy-database-password@postgres:5432/jt077_policy_test
APP_DOMAIN=jobtalk.roventics.com
SESSION_TOKEN_PEPPER=isolated-policy-session-pepper-more-than-32-characters
SMTP_HOST=smtp.policy.invalid
SMTP_USER=policy-check
SMTP_SECURE=false
SMTP_PASSWORD=isolated-policy-mail-password
EMAIL_FROM=policy-check@roventics.com
TLS_EMAIL=policy-check@roventics.com
SUPPORT_EMAIL=policy-check@roventics.com
AI_PROVIDER=mock
GEMINI_API_KEY=
OPENAI_API_KEY=
ADMIN_EMAIL=
STAGING_HTPASSWD_PATH=$($fixture.Replace('\', '/'))/htpasswd
"@ | Set-Content -Encoding ASCII "$fixture/test.env"
    @"
services:
  postgres:
    environment:
      POSTGRES_DB: jt077_policy_test
      POSTGRES_USER: job_talk
      POSTGRES_PASSWORD: isolated-policy-database-password
  backend:
    image: job-talk-backend:$imageTag
    # Test client needs to reach the proxy; production has no shared TCP network.
    networks:
      - edge
    environment:
      JOBTALK_POLICY_CHECK: '1'
      DATABASE_URL: postgresql+psycopg://job_talk:isolated-policy-database-password@postgres:5432/jt077_policy_test
      POSTGRES_PASSWORD: isolated-policy-database-password
      AI_PROVIDER: mock
      GEMINI_API_KEY: ''
      OPENAI_API_KEY: ''
      SMTP_HOST: smtp.policy.invalid
    volumes:
      - '$($PSScriptRoot.Replace('\', '/')):/checks:ro'
  frontend:
    image: job-talk-frontend:$imageTag
  proxy:
    image: job-talk-proxy:$imageTag
    ports: !override []
    volumes: !override
      - 'backend_socket:/run/jobtalk:ro'
      - '$($fixture.Replace('\', '/'))/certificates:/etc/letsencrypt:ro'
      - '$($fixture.Replace('\', '/'))/challenges:/var/www/certbot:ro'
      - '$($fixture.Replace('\', '/'))/htpasswd:/etc/nginx/auth/.htpasswd:ro'
"@ | Set-Content -Encoding ASCII "$fixture/override.yaml"
    'policy-challenge' | Set-Content -Encoding ASCII "$fixture/challenges/.well-known/acme-challenge/check"
    if (-not $SkipBuild) { Invoke-Compose @('build', 'backend', 'frontend', 'proxy') }
    $hash = docker run --rm --entrypoint openssl "job-talk-backend:$imageTag" passwd -apr1 policy-staging-password
    if ($LASTEXITCODE -ne 0) { throw 'Could not create disposable staging credential' }
    "staging:$hash" | Set-Content -Encoding ASCII "$fixture/htpasswd"
    Invoke-Compose @('config', '--quiet')
    # Explicit services exclude certificate issuance/renewal; nothing contacts ACME.
    Invoke-Compose @('up', '-d', '--wait', 'postgres', 'backend', 'frontend', 'proxy')
    Invoke-Compose @('exec', '-T', '-e', 'PYTHONPATH=/app', 'backend', 'python', '/checks/nginx-policy-probe.py', '--bootstrap')
    & docker run --rm --user 0 --entrypoint sh -v "${fixture}:/fixtures" "job-talk-backend:$imageTag" -c 'openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=jobtalk.roventics.com -keyout /fixtures/certificates/live/jobtalk.roventics.com/privkey.pem -out /fixtures/certificates/live/jobtalk.roventics.com/fullchain.pem 2>/dev/null'
    if ($LASTEXITCODE -ne 0) { throw 'Could not create disposable TLS certificate' }
    Invoke-Compose @('restart', 'proxy')
    Invoke-Compose @('up', '-d', '--wait', 'proxy')
    Invoke-Compose @('exec', '-T', 'proxy', 'nginx', '-t')
    Invoke-Compose @('exec', '-T', '-e', 'PYTHONPATH=/app', 'backend', 'python', '/checks/nginx-policy-probe.py')
    $proxyLog = & docker compose @compose logs --no-color proxy 2>&1 | Out-String
    if ($proxyLog -notmatch 'by zone "jobtalk_auth"' -or $proxyLog -notmatch 'by zone "jobtalk_api"') {
        throw 'Expected authentication and API rate-limit zones did not activate'
    }
    Write-Output 'PASS: both expected Nginx rate-limit zones activated'
} catch {
    # This project contains only fictional credentials; show proxy startup errors.
    & docker compose @compose logs --tail=30 proxy
    throw
} finally {
    # Only this unique test project and this exact temporary directory are removed.
    & docker compose @compose down --volumes --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw "Isolated cleanup failed; inspect project $project and $fixture" }
    $resolved = [IO.Path]::GetFullPath($fixture)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path $resolved -Leaf) -notmatch '^jobtalk-policy-[a-f0-9]{32}$') {
        throw 'Refusing cleanup outside the isolated fixture directory'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
