"""Draft edits are tested only through the isolated SQLite test database."""
from fastapi.testclient import TestClient

from app.services.ai import GeneratedTurn
from app.services.job_templates import (
    apply_draft_updates, draft_can_publish, draft_profile, finish_draft,
    new_job_draft, remove_draft_field,
)
from app.tests.test_flow import app, app_settings, authenticate, setup_function
from app.tests.test_job_drafts import developer_updates, proposal


def ready_draft():
    updates = [u for u in developer_updates() if u.key not in {"education", "working_hours", "availability", "git"}]
    return apply_draft_updates(new_job_draft("junior-software-developer"), updates,
                               "; ".join(u.source_quote for u in updates))


def edit_payload(**changes):
    return {"label": "Circuit simulation", "value": "Use circuit simluation tools", **changes}


def test_done_drops_only_blank_optional_fields_and_never_restores_from_history():
    draft = ready_draft()
    unclear = proposal("git", "Git may be useful", None, kind="skill", state="needs_clarification", label="Git")
    draft = apply_draft_updates(draft, [unclear], unclear.source_quote)
    finished = finish_draft(draft)
    fields = {f["key"]: f for f in finished["fields"]}
    assert "working_hours" not in fields and "education" not in fields
    assert fields["git"]["state"] == "needs_clarification"
    assert not draft_can_publish(finished)
    finished = remove_draft_field(finished, "git")
    assert draft_can_publish(finished)
    old = proposal("working_hours", "Working hours: 40 hours weekly", "40 hours weekly")
    assert apply_draft_updates(finished, [old], "Use my previous answers", [old.source_quote]) == finished
    restored = apply_draft_updates(finished, [old], old.source_quote)
    assert "working_hours" in draft_profile(restored)
    assert "working_hours" not in restored["removed_keys"]
    empty = finish_draft(new_job_draft("generic-role"))
    assert {f["key"] for f in empty["fields"]} == {"company_name", "company_location", "job_title", "role_description", "working_arrangement", "location"}
    assert not draft_can_publish(empty)


def test_natural_new_label_and_age_note_do_not_create_age_scores():
    source = "they must know circuit simluation"
    update = proposal("circuit_simulation", source, "Circuit simulation knowledge", label="Circuit simulation")
    draft = apply_draft_updates(ready_draft(), [update], source)
    assert "circuit_simulation" in draft_profile(draft)
    for key, label, source in (
        ("age_restriction", "Age restriction", "i would like to add age resticition that a person needs to be younger than 25"),
        ("eligibility", "Eligibility", "Eligibility: person must be under 25 years old"),
    ):
        update = proposal(key, source, "Must be younger than 25", label=label)
        draft = apply_draft_updates(draft, [update], source)
        field = next(f for f in draft["fields"] if f["key"] == key)
        assert field["scope"] == "metadata" and field["weight"] == 0
        assert key not in draft_profile(draft)
    hours = proposal("working_hours", "Working hours: over 25 hours weekly", "Over 25 hours weekly")
    saved = apply_draft_updates(draft, [hours], hours.source_quote)
    assert "working_hours" in draft_profile(saved)


def test_explicit_chat_removal_keeps_essentials_and_does_not_accept_negation():
    draft = ready_draft()
    remove = proposal("javascript", "Please remove JavaScript", state="not_required", label="JavaScript")
    saved = apply_draft_updates(draft, [remove], remove.source_quote)
    assert "javascript" not in draft_profile(saved)
    assert "javascript" in saved["removed_keys"]
    negated = proposal("javascript", "Do not remove JavaScript", state="not_required", label="JavaScript")
    assert apply_draft_updates(draft, [negated], negated.source_quote) == draft
    arrangement = proposal("working_arrangement", "Remove work arrangement", state="not_required")
    assert apply_draft_updates(draft, [arrangement], arrangement.source_quote) == draft


def test_form_save_polishes_one_field_and_syncs_profile_and_history(monkeypatch):
    captured = []
    def polish(context, intent, text, fallback):
        captured.append(context)
        update = proposal("circuit_simulation", text, "Use circuit simulation tools", label="Circuit simulation")
        update.description = "Demonstrate familiarity with circuit simulation tools."
        extra = proposal("experience", text, 99, kind="number", unit="years")
        return GeneratedTurn(reply=fallback, template_updates=[extra, update])
    monkeypatch.setattr("app.main.generate_turn", polish)
    _, headers = authenticate("editor@example.com", "recruiter")
    with TestClient(app) as client:
        chat = client.post("/api/chats", json={"template_id": "generic-role"}, headers=headers).json()
        path = f"/api/chats/{chat['id']}/draft"
        response = client.put(path + "/field", headers=headers, json=edit_payload())
        assert response.status_code == 200, response.text
        result = response.json()
        assert "polished" in result["notice"]
        saved = result["chat"]
        field = next(f for f in saved["job_draft"]["fields"] if f["key"] == "circuit_simulation")
        assert field["target"] == "Use circuit simulation tools"
        assert field["description"] == "Demonstrate familiarity with circuit simulation tools."
        assert saved["profile"] == saved["job_post"]["target_profile"]
        assert "experience" not in saved["profile"]
        assert "Form edit" in saved["messages"][-2]["content"]
        assert captured[0]["form_edit"]["key"] == "circuit_simulation"
        loaded = client.get(f"/api/chats/{chat['id']}", headers=headers).json()
        assert loaded["job_draft"] == saved["job_draft"]
        # Editing the same target again remains possible; its stable key is unchanged.
        response = client.put(path + "/field", headers=headers, json=edit_payload(key="circuit_simulation", value="Use circuit simulation tools"))
        assert response.status_code == 200, response.text
        assert client.put(path + "/field", headers=headers, json=edit_payload()).status_code == 409
        assert client.delete(path + "/fields/circuit_simulation", headers=headers).status_code == 200
        assert client.delete(path + "/fields/job_title", headers=headers).status_code == 422


def test_form_auth_admin_done_published_edits_and_numeric_validation(monkeypatch):
    monkeypatch.setattr(app_settings, "admin_email", "admin@example.com")
    _, owner = authenticate("owner@example.com", "recruiter")
    _, other = authenticate("other@example.com", "recruiter")
    _, admin = authenticate("admin@example.com", "recruiter")
    with TestClient(app) as client:
        chat = client.post("/api/chats", json={"template_id": "junior-software-developer"}, headers=owner).json()
        path = f"/api/chats/{chat['id']}/draft"
        assert client.put(path + "/field", json=edit_payload()).status_code == 401
        for method, suffix, kwargs in (("put", "/field", {"json": edit_payload()}), ("delete", "/fields/git", {}), ("post", "/done", {})):
            assert getattr(client, method)(path + suffix, headers=other, **kwargs).status_code == 404
        numeric = edit_payload(key="experience", label="Experience", value="At least two years of relevant experience")
        response = client.put(path + "/field", headers=admin, json=numeric)
        assert response.status_code == 200, response.text
        assert "Saved as entered" in response.json()["notice"]
        for bad in (dict(numeric, value="-1 years"), dict(numeric, value="several"), dict(numeric, weight=1)):
            assert client.put(path + "/field", headers=owner, json=bad).status_code == 422
        updates = [u for u in developer_updates() if u.key not in {"education", "working_hours", "availability", "git"}]
        monkeypatch.setattr("app.main.generate_turn", lambda *args: GeneratedTurn(reply="", template_updates=updates))
        client.post(f"/api/chats/{chat['id']}/messages", headers=owner, json={"content": "; ".join(u.source_quote for u in updates)})
        done = client.post(path + "/done", headers=admin).json()["chat"]
        assert done["can_publish"] and not done["job_post"]["published"]
        assert "git" not in {f["key"] for f in done["job_draft"]["fields"]}
        assert client.post(f"/api/jobs/{chat['job_post']['id']}/publish", headers=owner).status_code == 200
        public_before = client.get(f"/api/public/jobs/{chat['job_post']['id']}").json()
        for method, suffix, kwargs in (("put", "/field", {"json": edit_payload()}), ("delete", "/fields/experience", {}), ("post", "/done", {})):
            assert getattr(client, method)(path + suffix, headers=admin, **kwargs).status_code == 200
        assert client.get(f"/api/public/jobs/{chat['job_post']['id']}").json() == public_before


def test_ready_in_chat_matches_done_without_calling_ai_or_publishing(monkeypatch):
    updates = [u for u in developer_updates() if u.key not in {"education", "working_hours", "availability", "git"}]
    monkeypatch.setattr("app.main.generate_turn", lambda *args: GeneratedTurn(reply="", template_updates=updates))
    _, headers = authenticate("ready@example.com", "recruiter")
    with TestClient(app) as client:
        chat = client.post("/api/chats", json={"template_id": "junior-software-developer"}, headers=headers).json()
        path = f"/api/chats/{chat['id']}/messages"
        client.post(path, headers=headers, json={"content": "; ".join(u.source_quote for u in updates)})
        def no_ai(*args):
            raise AssertionError("Done does not need a provider call")
        monkeypatch.setattr("app.main.generate_turn", no_ai)
        for message in ("ready for publication", "I'm done"):
            result = client.post(path, headers=headers, json={"content": message}).json()
            assert result["chat"]["can_publish"]
            assert not result["chat"]["job_post"]["published"]
            assert "optional fields removed" in result["assistant_message"]["content"]


def test_form_polishing_cannot_change_an_explicit_numeric_target(monkeypatch):
    def changed_number(context, intent, text, fallback):
        update = proposal("experience", text, 5, kind="number", unit="years")
        return GeneratedTurn(reply=fallback, template_updates=[update])
    monkeypatch.setattr("app.main.generate_turn", changed_number)
    _, headers = authenticate("numeric-editor@example.com", "recruiter")
    with TestClient(app) as client:
        chat = client.post("/api/chats", json={"template_id": "generic-role"}, headers=headers).json()
        response = client.put(f"/api/chats/{chat['id']}/draft/field", headers=headers,
                              json=edit_payload(key="experience", label="Experience", value="At least two years of circuit design"))
        assert response.status_code == 200
        assert response.json()["chat"]["profile"]["experience"]["target"] == 2
        assert "Saved as entered" in response.json()["notice"]
