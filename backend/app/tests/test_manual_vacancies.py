from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient

from app.tests.test_flow import (
    app, app_settings, authenticate, application_payload, setup_function, SessionLocal, models,
)
from app.services.context import build_chat_context


ROLE = (
    "Job title: Workshop Welder; Role description: Repair workshop gates and frames; "
    "Skills: Welding is required; Tools: Welding equipment is required; "
    "Experience: two years of welding experience; Work arrangement: on-site; "
    "Location: Cape Town; Working hours: weekdays; Start availability: immediately; No degree needed"
)


def vacancy(**changes):
    return {"url": "https://example.com/jobs/welder", "employer": "Example Workshop",
            "checked_on": datetime.now(timezone.utc).date().isoformat(), "original_text": ROLE, **changes}


def owner(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "owner@example.com")
    return authenticate("owner@example.com", "recruiter")[1]


def create_reviewed_job(client, headers):
    response = client.post("/api/chats", headers=headers, json={"template_id": "generic-role", "source": vacancy()})
    assert response.status_code == 201
    chat = response.json()
    assert chat["job_draft"]["source"] == vacancy()
    assert not chat["can_publish"]
    assert client.post(f"/api/jobs/{chat['job_post']['id']}/publish", headers=headers).status_code == 400
    interpreted = client.post(f"/api/chats/{chat['id']}/messages", headers=headers, json={"content": ROLE})
    assert interpreted.status_code == 200
    chat = interpreted.json()["chat"]
    assert chat["can_publish"]
    assert chat["job_draft"]["source"] == vacancy()
    assert not {"source", "url", "employer", "checked_on", "original_text"} & set(chat["job_post"]["target_profile"])
    assert "education" not in chat["job_post"]["target_profile"]
    return chat


def test_curated_draft_review_source_visibility_duplicate_and_publication(monkeypatch):
    headers = owner(monkeypatch)
    with TestClient(app) as client:
        chat = create_reviewed_job(client, headers)
        job_id = chat["job_post"]["id"]
        # Metadata never becomes model context or a score criterion.
        with SessionLocal() as db:
            job = db.get(models.JobPost, job_id)
            assert "source" not in build_chat_context(job.chat)["job_draft"]
            assert job.source == vacancy()
        corrected = client.post(f"/api/chats/{chat['id']}/messages", headers=headers,
                                json={"content": "Experience: three years of welding experience"}).json()["chat"]
        assert corrected["job_draft"]["source"] == vacancy()
        assert corrected["job_post"]["target_profile"]["experience"]["target"] == 3
        assert client.get(f"/api/chats/{chat['id']}", headers=headers).json()["job_draft"] == corrected["job_draft"]
        assert client.post(f"/api/jobs/{job_id}/publish", headers=headers).status_code == 200
        public = client.get(f"/api/public/jobs/{job_id}").json()
        assert public["source"] == {k: v for k, v in vacancy().items() if k != "original_text"}
        assert "original_text" not in json.dumps(public)
        assert public["target_profile"] == corrected["job_post"]["target_profile"]
        duplicate = client.post("/api/chats", headers=headers, json={
            "template_id": "plumber", "source": vacancy(url="https://EXAMPLE.com/jobs/welder?utm_source=test#top")})
        assert duplicate.status_code == 409
        assert len(client.get("/api/chats", headers=headers).json()) == 1
        assert client.post(f"/api/chats/{chat['id']}/messages", headers=headers, json={"content": "Change the source"}).status_code == 200


def test_only_admin_can_add_sources_and_validation_precedes_storage(monkeypatch):
    headers = owner(monkeypatch)
    _, recruiter = authenticate("employer@example.com", "recruiter")
    _, guest = authenticate("guest@example.com", "candidate")
    with TestClient(app) as client:
        payload = {"template_id": "generic-role", "source": vacancy()}
        for unauthorized, status in (({}, 401), (recruiter, 403), (guest, 403)):
            assert client.post("/api/chats", headers=unauthorized, json=payload).status_code == status
        assert client.post("/api/chats", headers=headers, json={"source": vacancy()}).status_code == 422
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        for changes in ({"url": "javascript:alert(1)"}, {"url": "https://user:password@example.com/job"},
                        {"employer": " "}, {"checked_on": tomorrow}, {"checked_on": "invalid"},
                        {"original_text": "short"}, {"original_text": "x" * 5001}, {"receiver": "employer"}):
            assert client.post("/api/chats", headers=headers, json={**payload, "source": vacancy(**changes)}).status_code == 422
        assert client.get("/api/chats", headers=headers).json() == []
        assert client.post("/api/chats", headers=recruiter, json={"template_id": "plumber"}).status_code == 201


def test_curated_consent_aggregate_summary_access_and_closed_snapshots(monkeypatch):
    headers = owner(monkeypatch)
    _, outside = authenticate("advertised-employer@example.com", "recruiter")
    with TestClient(app) as client:
        chat = create_reviewed_job(client, headers)
        job_id = chat["job_post"]["id"]
        client.post(f"/api/jobs/{job_id}/publish", headers=headers)
        guest = client.post("/api/auth/guest", json={"job_id": job_id}).json()
        guest_headers = {"Authorization": f"Bearer {guest['access_token']}"}
        candidate = client.get("/api/chats", headers=guest_headers).json()[0]
        assert "not the advertised employer" in client.get(f"/api/chats/{candidate['id']}", headers=guest_headers).json()["messages"][0]["content"]
        assert client.get(f"/api/admin/jobs/{job_id}/interest", headers=headers).json()["applications"] == 0
        payload = application_payload(candidate["id"], name="Fictional Private Candidate", contact="private@example.com")
        assert client.post(f"/api/jobs/{job_id}/apply", headers=guest_headers, json={**payload, "consent_to_share": False}).status_code == 422
        # A known ideal profile exercises aggregate scoring; no LLM claims are made.
        with SessionLocal() as db:
            db.get(models.Chat, candidate["id"]).profile = {
                key: {"value": item["target"], "evidence": f"I worked with this requirement: {item['target']}", "assessment": "claimed"}
                for key, item in chat["job_post"]["target_profile"].items()
            }
            db.commit()
        applied = client.post(f"/api/jobs/{job_id}/apply", headers=guest_headers, json=payload)
        assert applied.status_code == 201
        snapshot = applied.json()
        consent = snapshot["candidate_profile"]["consent"]
        assert consent["share_with_operator"] is True
        assert consent["share_with_recruiter"] is False
        assert consent["external_employer_sharing_authorized"] is False
        assert consent["vacancy_source"]["employer"] == "Example Workshop"
        summary = client.get(f"/api/admin/jobs/{job_id}/interest", headers=headers).json()
        assert summary["applications"] == summary["strong_matches"] == 1
        assert all(item["strong_evidence"] == 1 for item in summary["criteria"])
        assert set(summary) == {"title", "applications", "strong_matches", "criteria"}
        assert all(set(item) == {"key", "label", "strong_evidence"} for item in summary["criteria"])
        assert "Private Candidate" not in json.dumps(summary) and "private@example.com" not in json.dumps(summary)
        assert client.get(f"/api/applications?job_id={job_id}", headers=outside).status_code == 404
        for unauthorized, status in (({}, 401), (outside, 403), (guest_headers, 403)):
            assert client.get(f"/api/admin/jobs/{job_id}/interest", headers=unauthorized).status_code == status
        assert client.post(f"/api/jobs/{job_id}/close", headers=headers).status_code == 200
        assert client.get(f"/api/public/jobs/{job_id}").status_code == 404
        assert client.post("/api/auth/guest", json={"job_id": job_id}).status_code == 404
        assert client.get(f"/api/applications?job_id={job_id}", headers=headers).json() == [snapshot]
        assert client.get(f"/api/admin/jobs/{job_id}/interest", headers=headers).json() == summary
        assert client.post("/api/chats", headers=headers, json={"template_id": "plumber", "source": vacancy()}).status_code == 409
