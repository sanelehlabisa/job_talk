"""Exercise every private route and session/code replay against disposable SQLite."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth import recruiter_code_digest, token_digest
from app.tests.test_flow import app, authenticate, setup_function, SessionLocal, models


PUBLIC = {
    ("GET", "/api/health"), ("GET", "/api/ready"),
    ("GET", "/api/public/jobs"), ("GET", "/api/public/jobs/{job_id}"),
    ("POST", "/api/experiment/visit"), ("POST", "/api/auth/guest"),
    ("POST", "/api/auth/recruiter/request-code"), ("POST", "/api/auth/recruiter/verify-code"),
}


def private_routes():
    return [(method, route.path) for route in app.routes
            if isinstance(route, APIRoute) and route.path.startswith("/api/")
            for method in route.methods if (method, route.path) not in PUBLIC]


@pytest.mark.parametrize("token_state", ["missing", "forged", "expired", "logged_out"])
def test_every_private_route_rejects_unusable_tokens(token_state):
    user, headers = authenticate("boundary@example.test", "recruiter")
    with TestClient(app) as client:
        if token_state == "missing": headers = {}
        elif token_state == "forged": headers = {"Authorization": "Bearer invented-token"}
        elif token_state == "expired":
            with SessionLocal() as db:
                session = db.scalar(select(models.AuthSession).where(models.AuthSession.user_id == user["id"]))
                session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                db.commit()
        else:
            assert client.post("/api/auth/logout", headers=headers).status_code == 204
        for method, path in private_routes():
            path = path.replace("{chat_id}", "999").replace("{job_id}", "999").replace("{key}", "python")
            response = client.request(method, path, headers=headers, json={} if method in {"PUT", "POST"} else None)
            assert response.status_code == 401, (token_state, method, path, response.status_code)
            assert response.headers["www-authenticate"] == "Bearer"


def test_approval_is_checked_on_existing_tokens_and_guests_cannot_create_jobs():
    user, headers = authenticate("approved-owner@example.test", "recruiter")
    with TestClient(app) as client:
        created = client.post("/api/chats", headers=headers, json={"template_id": "generic-role"})
        assert created.status_code == 201
        chat = created.json()
        with SessionLocal() as db:
            db.get(models.User, user["id"]).approval_status = "rejected"
            db.commit()
        for method, path, body in [
            ("POST", "/api/chats", {"template_id": "generic-role"}),
            ("GET", f"/api/chats/{chat['id']}", None),
            ("POST", f"/api/chats/{chat['id']}/messages", {"content": "Publish this job"}),
            ("PUT", f"/api/chats/{chat['id']}/draft/field", {}),
            ("POST", f"/api/jobs/{chat['job_post']['id']}/publish", None),
            ("GET", "/api/applications", None),
        ]:
            assert client.request(method, path, headers=headers, json=body).status_code == 401
        # Revoked approval must not prevent the user from revoking their session.
        assert client.post("/api/auth/logout", headers=headers).status_code == 204
        guest = client.post("/api/auth/guest", json={}).json()
        guest_headers = {"Authorization": "Bearer " + guest["access_token"]}
        assert client.post("/api/chats", headers=guest_headers, json={"template_id": "generic-role"}).status_code == 403
        assert client.post(f"/api/jobs/{chat['job_post']['id']}/publish", headers=guest_headers).status_code == 403
        with SessionLocal() as db:
            assert db.scalar(select(func.count(models.JobPost.id))) == 1
            assert not db.get(models.JobPost, chat["job_post"]["id"]).published


@pytest.mark.parametrize("role", ["candidate", "recruiter"])
def test_logout_revokes_only_the_presented_session_and_preserves_work(role):
    user, first = authenticate(f"{role}@example.test", role)
    from app.auth import issue_session
    with SessionLocal() as db:
        second_token = issue_session(db, db.get(models.User, user["id"])).access_token
    with TestClient(app) as client:
        chat = client.post("/api/chats", headers=first).json()
        assert client.post("/api/auth/logout", headers=first).status_code == 204
        assert client.get(f"/api/chats/{chat['id']}", headers=first).status_code == 401
        assert client.get(f"/api/chats/{chat['id']}", headers={"Authorization": "Bearer " + second_token}).status_code == 200
        with SessionLocal() as db:
            digest = token_digest(first["Authorization"].removeprefix("Bearer "))
            assert db.scalar(select(models.AuthSession).where(models.AuthSession.token_hash == digest)) is None


@pytest.mark.parametrize("correct", [True, False])
def test_concurrent_code_verification_has_one_winner_and_no_lost_guesses(monkeypatch, correct):
    with SessionLocal() as db:
        user = models.User(email="concurrent@example.com", role="recruiter", approval_status="approved")
        db.add(user)
        db.flush()
        db.add(models.RecruiterLoginCode(user_id=user.id, code_hash=recruiter_code_digest(user.id, "123456"),
                                        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
        db.commit()
    # Make both requests read the code before either tries to consume it.
    barrier = Barrier(2, timeout=10)
    import secrets
    original_compare = secrets.compare_digest
    def simultaneous_compare(left, right):
        barrier.wait()
        return original_compare(left, right)
    monkeypatch.setattr("app.main.secrets.compare_digest", simultaneous_compare)
    def verify(_):
        with TestClient(app) as client:
            return client.post("/api/auth/recruiter/verify-code", json={
                "email": "concurrent@example.com", "code": "123456" if correct else "000000",
            }).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(verify, range(2)))
    assert statuses == ([200, 401] if correct else [401, 401])
    with SessionLocal() as db:
        assert db.scalar(select(func.count(models.AuthSession.id))) == (1 if correct else 0)
        if not correct:
            assert db.scalar(select(models.RecruiterLoginCode)).attempt_count == 2
