from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.services.job_templates import apply_draft_updates, draft_can_publish, draft_profile, form_field_update
from app.tests.test_draft_editor import ready_draft
from app.tests.test_job_drafts import proposal
from app.tests.test_flow import app, authenticate, application_payload, models, SessionLocal, setup_function


def test_closing_date_is_optional_and_never_an_assessment_criterion():
    from app.services.job_templates import finish_draft
    draft = finish_draft(ready_draft())
    assert draft_can_publish(draft)
    source = "Applications close on 30 November 2026"
    update = proposal("closing_date", source, "2026-11-30", label="Closing date")
    saved = apply_draft_updates(draft, [update], source)
    field = next(f for f in saved["fields"] if f["key"] == "closing_date")
    assert field["scope"] == "metadata" and field["weight"] == 0
    assert "closing_date" not in draft_profile(saved)
    assert draft_can_publish(saved)
    update.target = "2026-12-30"
    assert apply_draft_updates(saved, [update], source) == saved


def test_simple_values_keep_numeric_skill_and_preferred_meaning():
    draft = ready_draft()
    for value, target in (("2.5 years", 2.5), ("Preferred: three years", 3), ("4", 4), ("2   years", 2)):
        update = form_field_update(draft, "experience", "Experience", value)
        saved = apply_draft_updates(draft, [update], update.source_quote)
        assert draft_profile(saved)["experience"]["target"] == target
        if value.startswith("Preferred"):
            assert draft_profile(saved)["experience"]["weight"] == .35
    update = form_field_update(draft, "javascript", "JavaScript", "Can write simple JavaScript functions")
    assert update.type == "skill" and update.target is True
    update = form_field_update(draft, "javascript", "JavaScript", "Two years of JavaScript")
    assert update.type == "number" and update.target == 2
    update = form_field_update(draft, "age", "Age", "Under 25 years old")
    assert update.type == "text"


def test_date_form_save_clear_and_expiry_cover_all_candidate_entry_points(monkeypatch):
    from app.services.job_templates import finish_draft
    monkeypatch.setattr("app.models.utcnow", lambda: datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc))
    _, owner = authenticate("date-owner@example.com", "recruiter")
    with TestClient(app) as client:
        chat = client.post("/api/chats", headers=owner, json={"template_id": "generic-role"}).json()
        root = f"/api/chats/{chat['id']}"
        with SessionLocal() as db:
            job = db.get(models.JobPost, chat["job_post"]["id"])
            job.draft = finish_draft(ready_draft())  # old draft without a date field
            job.title = "Closing Date Test"
            job.description = "Build and test small apps"
            job.target_profile = draft_profile(job.draft)
            job.chat.profile = job.target_profile
            db.commit()
        payload = {"key": "closing_date", "label": "Closing date", "value": "2026-11-30"}
        response = client.put(root + "/draft/field", headers=owner, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["chat"]["job_post"]["closing_date"] == "2026-11-30"
        assert "closing_date" not in response.json()["chat"]["profile"]
        for invalid in ("tomorrow", "2026-02-30", "30/11", "2026-13-30"):
            assert client.put(root + "/draft/field", headers=owner, json={**payload, "value": invalid}).status_code == 422
        cleared = client.delete(root + "/draft/fields/closing_date", headers=owner).json()
        assert cleared["chat"]["job_post"]["closing_date"] is None
        assert client.put(root + "/draft/field", headers=owner, json=payload).status_code == 200
        job_id = chat["job_post"]["id"]
        assert client.post(f"/api/jobs/{job_id}/publish", headers=owner).status_code == 200
        assert client.get(f"/api/public/jobs/{job_id}").json()["closing_date"] == "2026-11-30"
        session = client.post("/api/auth/guest", json={"job_id": job_id}).json()
        guest = {"Authorization": f"Bearer {session['access_token']}"}
        guest_chat = client.get("/api/chats", headers=guest).json()[0]["id"]
        discovery = client.post("/api/auth/guest", json={}).json()
        discovery_headers = {"Authorization": f"Bearer {discovery['access_token']}"}
        discovery_id = client.get("/api/chats", headers=discovery_headers).json()[0]["id"]
        monkeypatch.setattr("app.models.utcnow", lambda: datetime(2026, 12, 1, tzinfo=timezone.utc))
        assert client.get("/api/public/jobs").json() == []
        assert client.get("/api/jobs", headers=owner).json() == []
        assert client.get(f"/api/public/jobs/{job_id}").status_code == 404
        assert client.post("/api/auth/guest", json={"job_id": job_id}).status_code == 404
        assert client.post(f"/api/chats/{discovery_id}/select-job", headers=discovery_headers, json={"job_id": job_id}).status_code == 404
        assert client.get(f"/api/chats/{guest_chat}/recommendations", headers=guest).json() == []
        assert client.post(f"/api/chats/{guest_chat}/messages", headers=guest, json={"content": "Apply"}).status_code == 409
        assert client.post(f"/api/jobs/{job_id}/apply", headers=guest, json=application_payload(guest_chat)).status_code == 409
        assert client.get(f"/api/chats/{guest_chat}", headers=guest).json()["status"] == "closed"
        assert client.get(root, headers=owner).status_code == 200  # recruiter can still compare applicants
