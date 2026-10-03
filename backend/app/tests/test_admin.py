from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.tests.test_flow import (
    app, app_settings, authenticate, application_payload, create_published_job,
    models, SessionLocal, setup_function,
)
from app.auth import issue_session, token_digest
from app.settings import Settings


def test_admin_email_is_optional_normalized_and_validated():
    assert Settings(_env_file=None, admin_email=" ").admin_email is None
    assert Settings(_env_file=None, admin_email=" Owner@Example.com ").admin_email == "owner@example.com"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, admin_email="not an email")


def test_admin_reads_all_jobs_and_submitted_snapshots_without_other_chat_or_edit_access(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "owner@example.com")
    _, admin_headers = authenticate("owner@example.com", "recruiter")
    job_ids = [create_published_job(email=f"recruiter-{i}@example.com") for i in range(2)]
    recruiter_headers = []
    with SessionLocal() as db:
        for job_id in job_ids:
            user = db.get(models.User, db.get(models.JobPost, job_id).user_id)
            recruiter_headers.append({"Authorization": f"Bearer {issue_session(db, user).access_token}"})
    with TestClient(app) as client:
        draft = client.post("/api/chats", json={"template_id": "plumber"}, headers=recruiter_headers[0]).json()
        guests, applications = [], []
        for job_id in job_ids:
            guest = client.post("/api/auth/guest", json={"job_id": job_id}).json()
            headers = {"Authorization": f"Bearer {guest['access_token']}"}
            chat = client.get("/api/chats", headers=headers).json()[0]
            response = client.post(f"/api/jobs/{job_id}/apply", headers=headers, json=application_payload(chat["id"]))
            assert response.status_code == 201
            assert response.json()["candidate_profile"]["consent"]["operator_access_disclosed"] is True
            guests.append((headers, chat))
            applications.append(response.json())

        # Even a persisted but unsubmitted record is never exposed or counted.
        with SessionLocal() as db:
            hidden_chat = models.Chat(user_id=guest["user"]["id"], intent="candidate")
            db.add(hidden_chat)
            db.flush()
            db.add(models.Application(candidate_chat_id=hidden_chat.id, candidate_user_id=guest["user"]["id"],
                                      job_post_id=job_ids[0], submitted=False))
            db.commit()
        assert client.post(f"/api/jobs/{job_ids[1]}/close", headers=recruiter_headers[1]).status_code == 200
        jobs = client.get("/api/admin/jobs", headers=admin_headers).json()
        assert {job["status"] for job in jobs} == {"draft", "published", "closed"}
        assert {job["id"] for job in jobs} == {*job_ids, draft["job_post"]["id"]}
        assert sum(job["submitted_count"] for job in jobs) == 2
        assert all("messages" not in job and "draft" not in job and "chat_id" not in job for job in jobs)
        assert client.get("/api/chats", headers=admin_headers).json() == []
        assert client.get("/api/applications?job_id=99999", headers=admin_headers).status_code == 404
        for i, job_id in enumerate(job_ids):
            assert client.get(f"/api/applications?job_id={job_id}", headers=admin_headers).json() == [applications[i]]
            assert client.get(f"/api/applications?job_id={job_id}", headers=recruiter_headers[i]).json() == [applications[i]]
            assert client.get(f"/api/applications?job_id={job_id}", headers=recruiter_headers[1-i]).status_code == 404
            for headers in (admin_headers, recruiter_headers[i], guests[1-i][0]):
                assert client.get(f"/api/chats/{guests[i][1]['id']}", headers=headers).status_code == 404
            for action in ("publish", "close"):
                assert client.post(f"/api/jobs/{job_id}/{action}", headers=admin_headers).status_code == 404
            assert client.get("/api/applications", headers=guests[i][0]).json() == [applications[i]]
            assert client.get(f"/api/applications?job_id={job_id}", headers=guests[i][0]).status_code == 403
        assert client.get(f"/api/chats/{draft['id']}", headers=admin_headers).status_code == 404
        assert client.post(f"/api/chats/{draft['id']}/messages", json={"content": "Change the title"}, headers=admin_headers).status_code == 404
        assert len(client.get("/api/public/jobs").json()) == 1
        assert "recruiter_email" not in client.get("/api/public/jobs").json()[0]


def test_admin_capability_rechecks_configuration_and_approval_on_existing_sessions(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "owner@example.com")
    admin, headers = authenticate("OWNER@example.com", "recruiter")
    assert admin["is_admin"] is True
    _, other_headers = authenticate("other@example.com", "recruiter")
    job_id = create_published_job()
    with TestClient(app) as client:
        for configured in (None, "", "other@example.com"):
            monkeypatch.setattr(app_settings, "admin_email", configured)
            assert client.get("/api/auth/me", headers=headers).json()["is_admin"] is False
            assert client.get("/api/admin/jobs", headers=headers).status_code == 403
            assert client.get(f"/api/applications?job_id={job_id}", headers=headers).status_code == 404
        assert client.get("/api/admin/jobs", headers=other_headers).status_code == 200
        monkeypatch.setattr(app_settings, "admin_email", "owner@example.com")
        assert client.get("/api/auth/me", headers=headers).json()["is_admin"] is True
        with SessionLocal() as db:
            db.get(models.User, admin["id"]).approval_status = "rejected"
            db.commit()
        for path in ("/api/auth/me", "/api/admin/jobs", f"/api/applications?job_id={job_id}"):
            assert client.get(path, headers=headers).status_code == 401


def test_admin_private_endpoints_reject_anonymous_spoofed_guest_and_expired_access(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "owner@example.com")
    # Matching the address is insufficient without an approved recruiter identity.
    guest, guest_headers = authenticate("owner@example.com", "candidate")
    _, recruiter_headers = authenticate("regular@example.com", "recruiter")
    _, expired_headers = authenticate("expired@example.com", "recruiter")
    with SessionLocal() as db:
        token = expired_headers["Authorization"].removeprefix("Bearer ")
        session = db.scalar(select(models.AuthSession).where(models.AuthSession.token_hash == token_digest(token)))
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    job_id = create_published_job()
    with TestClient(app) as client:
        assert guest["is_admin"] is False
        for headers in ({}, {"Authorization": "Bearer made-up-token"}, expired_headers):
            assert client.get("/api/admin/jobs", headers=headers).status_code == 401
            assert client.get(f"/api/applications?job_id={job_id}", headers=headers).status_code == 401
        for headers in (guest_headers, recruiter_headers):
            spoofed = {**headers, "X-Role": "admin", "X-Admin-Email": "owner@example.com"}
            assert client.get("/api/admin/jobs?is_admin=true&email=owner@example.com", headers=spoofed).status_code == 403
            assert client.get("/api/auth/me", headers=spoofed).json()["is_admin"] is False
        forged_guest = client.post("/api/auth/guest", json={"email": "owner@example.com", "role": "recruiter", "is_admin": True}).json()
        assert forged_guest["user"]["role"] == "candidate"
        assert forged_guest["user"]["is_admin"] is False


def test_admin_uses_approved_single_use_email_code_then_bearer_token(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "owner@example.com")
    delivered = []
    monkeypatch.setattr("app.main.send_recruiter_login_code", lambda email, code: delivered.append((email, code)))
    with TestClient(app) as client:
        payload = {"email": "owner@example.com", "is_admin": True}
        assert client.post("/api/auth/recruiter/request-code", json=payload).status_code == 202
        assert delivered == []  # Configuration does not bypass approval.
        with SessionLocal() as db:
            user = db.scalar(select(models.User).where(models.User.email == payload["email"]))
            user.approval_status = "approved"
            db.commit()
        client.post("/api/auth/recruiter/request-code", json=payload)
        assert len(delivered) == 1
        code = delivered[0][1]
        verified = client.post("/api/auth/recruiter/verify-code", json={**payload, "code": code})
        assert verified.status_code == 200
        assert verified.json()["user"]["is_admin"] is True
        headers = {"Authorization": f"Bearer {verified.json()['access_token']}"}
        assert client.get("/api/admin/jobs", headers=headers).status_code == 200
        assert client.get("/api/admin/jobs", headers={"Authorization": f"Bearer {code}"}).status_code == 401
        assert client.post("/api/auth/recruiter/verify-code", json={**payload, "code": code}).status_code == 401
        assert client.post("/api/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/admin/jobs", headers=headers).status_code == 401
