"""Run only through check-nginx-policies.ps1 against its disposable database."""
import base64
from datetime import datetime, timedelta, timezone
import http.client
import json
import os
import re
import ssl
import sys
import time

from sqlalchemy.engine import make_url

assert os.environ.get("JOBTALK_POLICY_CHECK") == "1", "Isolated fixture required"
assert make_url(os.environ["DATABASE_URL"]).database == "jt077_policy_test"
DOMAIN = "jobtalk.roventics.com"
ORIGIN = f"https://{DOMAIN}"
BASIC = "Basic " + base64.b64encode(b"staging:policy-staging-password").decode()


def request(path, expected, method="GET", headers=None, payload=None, tls=True, paced=True):
    if paced:
        time.sleep(0.25)
    connection = (http.client.HTTPSConnection("proxy", 443, timeout=8,
                  context=ssl._create_unverified_context()) if tls else
                  http.client.HTTPConnection("proxy", 80, timeout=8))
    request_headers = {"Host": DOMAIN, **(headers or {})}
    if isinstance(payload, dict):
        payload = json.dumps(payload)
        request_headers["Content-Type"] = "application/json"
    try:
        connection.request(method, path, body=payload, headers=request_headers)
        response = connection.getresponse()
        body = response.read()
        assert response.status in expected, f"{method} {path}: expected {expected}, got {response.status}"
        return response.status, dict(response.getheaders()), body
    finally:
        connection.close()


def wrong_host(tls=True):
    try:
        request("/proxy-health", [], headers={"Host": "foreign.invalid"}, tls=tls)
    except (http.client.RemoteDisconnected, ConnectionResetError):
        return  # Nginx's intentional 444 closes without sending a response.
    raise AssertionError("Unexpected Host was accepted")


if "--bootstrap" in sys.argv:
    request("/proxy-health", [200], tls=False)
    request("/", [503], tls=False)
    request("/.well-known/acme-challenge/check", [200], tls=False)
    wrong_host(tls=False)
    print("PASS: HTTP bootstrap health, ACME, closed app and Host checks")
    sys.exit(0)

_, headers, _ = request("/", [308], tls=False)
assert headers["Location"] == ORIGIN + "/"
request("/.well-known/acme-challenge/check", [200], tls=False)
wrong_host()
wrong_host(tls=False)
request("/", [401])
_, headers, html = request("/", [200], headers={"Authorization": BASIC})
assert "script-src 'self'" in headers["Content-Security-Policy"]
assert "connect-src 'self'" in headers["Content-Security-Policy"]
assert headers["X-Frame-Options"] == "DENY"
assert "max-age=" in headers["Strict-Transport-Security"]
assets = re.findall(r'(?:src|href)="(/assets/[^" ]+)"', html.decode())
assert assets, "Production frontend assets missing"
for asset in assets:
    request(asset, [200], headers={"Authorization": BASIC})
for path in ("/.env", "/.git/config", "/api/.env", "/docs", "/api/docs", "/openapi.json"):
    request(path, [404])
request("/", [405], method="POST")
print("PASS: HTTPS, staging gate, built assets, security headers and hidden paths")

for origin in ("https://foreign.invalid", "https://other.roventics.com", "null", "http://" + DOMAIN):
    request("/api/auth/guest", [403], method="POST", headers={"Origin": origin})
for site in ("cross-site", "same-site"):
    request("/api/health", [403], headers={"Sec-Fetch-Site": site})
for method in ("TRACE", "PATCH"):
    request("/api/health", [405], method=method)
request("/api/auth/guest", [413], method="POST", payload="x" * (128 * 1024 + 1))
request("/api/health", [200])  # Health/CLI without Origin still works.
same_origin = {"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}
_, headers, _ = request("/api/ready", [200], headers=same_origin)
assert headers["Cache-Control"] == "no-store"
assert "Content-Security-Policy" in headers  # Check add_header inheritance.
request("/api/chats", [401], headers=same_origin)
request("/api/chats", [401], headers={**same_origin, "Authorization": "Bearer forged"})
print("PASS: origin, Fetch Metadata, methods, body size, no-store and token requirement")

_, _, body = request("/api/auth/guest", [201], method="POST", headers=same_origin, payload={})
guest = {**same_origin, "Authorization": "Bearer " + json.loads(body)["access_token"]}
request("/api/chats", [200], headers=guest)
request("/api/chats", [403], headers={**guest, "Origin": "https://foreign.invalid"})
request("/api/chats", [403], method="POST", headers=guest, payload={"template_id": "generic-role"})
request("/api/auth/logout", [204], method="POST", headers=guest)
request("/api/chats", [401], headers=guest)

# Seed a single code in this isolated DB, exercising real code redemption without SMTP.
from app import models
from app.auth import recruiter_code_digest
from app.database import SessionLocal

with SessionLocal() as db:
    recruiter = models.User(email="policy-recruiter@roventics.com", role="recruiter", approval_status="approved")
    db.add(recruiter)
    db.flush()
    db.add(models.RecruiterLoginCode(user_id=recruiter.id,
        code_hash=recruiter_code_digest(recruiter.id, "123456"),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
    db.commit()
_, _, body = request("/api/auth/recruiter/verify-code", [200], method="POST",
    headers=same_origin, payload={"email": "policy-recruiter@roventics.com", "code": "123456"})
recruiter_headers = {**same_origin, "Authorization": "Bearer " + json.loads(body)["access_token"]}
request("/api/chats", [200], headers=recruiter_headers)
request("/api/chats", [201], method="POST", headers=recruiter_headers, payload={"template_id": "generic-role"})
request("/api/auth/logout", [204], method="POST", headers=recruiter_headers)
request("/api/chats", [401], headers=recruiter_headers)
print("PASS: guest/recruiter tokens through proxy, code login and logout revocation")

# Last: deliberately exhaust rate buckets without creating users or sending mail.
auth_statuses = [request("/api/auth/recruiter/verify-code", [401, 429], method="POST",
    payload={"email": "absent@roventics.com", "code": "000000"}, paced=False)[0] for _ in range(8)]
assert 429 in auth_statuses, "Authentication rate limit did not activate"
api_statuses = [request("/api/health", [200, 429], paced=False)[0] for _ in range(35)]
assert 429 in api_statuses, "API rate limit did not activate"
print("PASS: authentication and API bursts return 429")
