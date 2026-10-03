from copy import deepcopy

from fastapi.testclient import TestClient

from app.tests.test_flow import (
    app, authenticate, create_published_job, application_payload, setup_function,
    SessionLocal, models,
)
from app.services.ai import GeneratedTurn
from app.services.candidate_application import CandidateUpdate, apply_candidate_updates, application_fields
from app.services.conversation import update_candidate_profile, candidate_reply
from app.services.matching import match_profiles


CRITERIA = {
    "python": {"label": "Python", "type": "number", "target": 3, "unit": "years", "weight": .9, "description": "Three years building Python applications"},
    "git": {"label": "Git", "type": "skill", "target": True, "weight": .7, "description": "Use Git to save changes"},
    "location": {"label": "Location", "type": "text", "target": "Cape Town", "weight": .5, "description": "Work in Cape Town"},
    "working_hours": {"label": "Working hours", "type": "text", "target": "Weekdays", "weight": .4, "description": "Work weekday hours"},
}


def proposal(key, quote, value=None, state="captured", evidence=None):
    return CandidateUpdate(key=key, label=CRITERIA.get(key, {}).get("label", key.title()),
                           value=value, state=state, evidence=evidence or quote, source_quote=quote)


def guest(client, job_id=None):
    session = client.post("/api/auth/guest", json={"job_id": job_id}).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    return client.get("/api/chats", headers=headers).json()[0], headers


def test_discovery_finds_third_job_then_collects_corrects_and_submits(monkeypatch):
    create_published_job(email="first@example.com", title="Welder")
    create_published_job(email="second@example.com", title="Driver", target_profile={"driving": {"type": "skill", "target": True, "weight": 1, "description": "Driving"}})
    job_id = create_published_job(email="third@example.com", title="Python Assistant", target_profile=CRITERIA)
    with TestClient(app) as client:
        assert job_id not in [job["id"] for job in client.get("/api/public/jobs").json()[:2]]
        chat, headers = guest(client)
        path = f"/api/chats/{chat['id']}"
        examples = client.get(path + "/recommendations", headers=headers).json()
        assert len(examples) == 2
        assert all(item["available_example"] and not item["recommended"] for item in examples)
        assert job_id not in [item["job"]["id"] for item in examples]
        discovered = client.post(path + "/messages", headers=headers, json={"content": "I have four years of Python experience in Cape Town. I built Python APIs."}).json()
        assert [item["job"]["id"] for item in discovered["recommendations"]] == [job_id]
        assert not discovered["recommendations"][0]["available_example"]
        selected = client.post(path + "/select-job", json={"job_id": job_id}, headers=headers)
        assert selected.status_code == 200
        body = selected.json()
        assert body["target_job_id"] == job_id
        assert body["profile"]["python"]["value"] == 4
        assert {field["key"] for field in body["application_fields"]} == set(CRITERIA)
        assert body["profile"].get("git") is None

        updates = [proposal("git", "I don't have Git experience", state="gap"),
                   proposal("working_hours", "I can work weekday hours", "Weekdays")]
        monkeypatch.setattr("app.main.generate_turn", lambda *args: GeneratedTurn(reply="Ignore this claim of success", candidate_updates=updates))
        response = client.post(path + "/messages", json={"content": "; ".join(u.source_quote for u in updates)}, headers=headers).json()
        fields = {f["key"]: f for f in response["chat"]["application_fields"]}
        assert fields["git"]["state"] == "gap"
        assert fields["working_hours"]["state"] == "captured"
        assert "Ignore" not in response["assistant_message"]["content"]
        assert "git" not in response["assistant_message"]["content"].lower()

        updates = [proposal("python", "Correction: two years of Python experience", 2)]
        response = client.post(path + "/messages", json={"content": updates[0].source_quote}, headers=headers).json()
        assert response["chat"]["profile"]["python"]["value"] == 2
        assert response["chat"]["profile"]["git"]["assessment"] == "gap"
        saved = client.get(path, headers=headers).json()
        assert saved["application_fields"] == response["chat"]["application_fields"]
        assert saved["target_job"]["target_profile"]["python"]["target"] == 3
        assert client.post(f"/api/jobs/{job_id}/apply", json={**application_payload(chat['id']), "consent_to_share": False}, headers=headers).status_code == 422
        submitted = client.post(f"/api/jobs/{job_id}/apply", json=application_payload(chat['id']), headers=headers)
        assert submitted.status_code == 201
        snapshot = submitted.json()
        assert snapshot["match_result"]["criteria"]["git"]["score"] == 0
        assert snapshot["match_result"]["criteria"]["python"]["candidate_value"] == 2
        assert set(snapshot["match_result"]["criteria"]) == set(CRITERIA)
        assert snapshot["candidate_profile"]["python"] == saved["profile"]["python"]
        assert client.post(path + "/messages", json={"content": "Change it"}, headers=headers).status_code == 409


def test_selection_is_owned_single_job_and_rejects_closed_jobs():
    job_id = create_published_job()
    another = create_published_job(email="second-select@example.com")
    closed = create_published_job(email="closed-select@example.com")
    with SessionLocal() as db:
        db.get(models.JobPost, closed).published = False
        db.commit()
    _, recruiter = authenticate("no-select@example.com", "recruiter")
    with TestClient(app) as client:
        first, headers = guest(client)
        second, other = guest(client)
        path = f"/api/chats/{first['id']}/select-job"
        assert client.post(path, json={"job_id": job_id}).status_code == 401
        assert client.post(path, json={"job_id": job_id}, headers=other).status_code == 404
        assert client.post(path, json={"job_id": job_id}, headers=recruiter).status_code == 403
        assert client.post(path, json={"job_id": closed}, headers=headers).status_code == 404
        assert client.post(path, json={"job_id": job_id}, headers=headers).status_code == 200
        assert client.post(path, json={"job_id": job_id}, headers=headers).status_code == 200
        assert client.post(path, json={"job_id": another}, headers=headers).status_code == 403
        assert client.post(f"/api/jobs/{another}/apply", json=application_payload(first['id']), headers=headers).status_code == 403
        assert client.get(f"/api/chats/{second['id']}", headers=other).json()["target_job_id"] is None


def test_candidate_proposals_reject_invention_and_reuse_only_unanswered_history():
    original = deepcopy(CRITERIA)
    text = "I built Python APIs for two years. I have no Git experience."
    updates = [proposal("python", "I built Python APIs for two years", 2), proposal("git", "I have no Git experience", state="gap")]
    saved = apply_candidate_updates({}, CRITERIA, updates, text, [])
    assert saved["python"]["value"] == 2
    for bad in [proposal("python", "I built Python APIs for two years", 10),
                proposal("location", "I built Python APIs for two years", 2),
                proposal("docker", "I built Python APIs for two years", True),
                proposal("git", "I have no Git experience", True),
                proposal("location", "I am based in London", "London")]:
        assert apply_candidate_updates(saved, CRITERIA, [bad], text, []) == saved
    assert apply_candidate_updates(saved, CRITERIA, [proposal("git", "That's fine", True)], "That's fine", []) == saved
    old = proposal("python", "I built Python for five years", 5)
    assert apply_candidate_updates(saved, CRITERIA, [old], "I can work weekdays", [old.source_quote]) == saved
    location = proposal("location", "I am based in Cape Town", "Cape Town")
    reused = apply_candidate_updates(saved, CRITERIA, [location], "I can work weekdays", [location.source_quote])
    assert reused["location"]["value"] == "Cape Town"
    assert CRITERIA == original
    embellished = proposal("python", "I built Python APIs for two years", 2,
                           evidence="Built certified enterprise Python platforms at Google")
    guarded = apply_candidate_updates({}, CRITERIA, [embellished], text, [])
    assert guarded["python"]["evidence"] == embellished.source_quote
    denial = proposal("python", "I have not used Python for two years", 2)
    assert apply_candidate_updates(saved, CRITERIA, [denial], denial.source_quote, []) == saved


def test_unclear_answers_have_no_score_and_do_not_resolve_follow_up():
    text = "I have some Python experience"
    saved = apply_candidate_updates({}, CRITERIA, [proposal("python", text, state="needs_clarification")], text, [])
    result = match_profiles(saved, CRITERIA)
    assert result["criteria"]["python"]["score"] == 0
    assert result["criteria"]["python"]["candidate_value"] is None
    assert application_fields(saved, CRITERIA)[0]["state"] == "needs_clarification"
    assert "python" in candidate_reply(saved, CRITERIA).lower()


def test_guided_parser_scopes_denials_and_keeps_distinct_durations():
    target = {"python": CRITERIA["python"], "git": {**CRITERIA["git"], "type": "number", "target": 3, "unit": "years"}}
    saved = update_candidate_profile({}, "I used Python for two years; I used Git for five years.", target)
    assert saved["python"]["value"] == 2
    assert saved["git"]["value"] == 5
    saved = update_candidate_profile(saved, "I don't have that skill", target, "git")
    assert saved["git"]["assessment"] == "gap"
    assert saved["python"]["value"] == 2
    assert update_candidate_profile(saved, "That's fine", target, "python") == saved
    target = {"experience": {"type": "number", "target": 2, "unit": "years", "description": "Two years of welding experience"},
              "tools": {"type": "text", "target": "Welding equipment", "description": "Use welding equipment"}}
    saved = update_candidate_profile({}, "I have two years of welding experience", target)
    saved = update_candidate_profile(saved, "I cannot use welding equipment", target, "tools")
    assert saved["tools"]["assessment"] == "gap"
    assert saved["experience"]["value"] == 2
    assert saved["experience"]["assessment"] == "claimed"
