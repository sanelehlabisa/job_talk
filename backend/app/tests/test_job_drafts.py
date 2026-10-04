import json

from fastapi.testclient import TestClient

from app.tests.test_flow import app, authenticate, setup_function, SessionLocal, models
from app.services.ai import GeneratedTurn, generate_turn
from app.services.context import build_chat_context
from app.services.job_templates import (
    DraftUpdate, apply_draft_updates, draft_can_publish, draft_profile,
    draft_question, fallback_draft_updates, new_job_draft,
)
from app.settings import Settings


def proposal(key, source, target=None, *, state="confirmed", kind="text", importance="required", unit=None, label=None):
    return DraftUpdate(key=key, label=label or key.replace("_", " ").title(),
                       type=kind, target=target, unit=unit, state=state,
                       importance=importance, description=source, source_quote=source)


def developer_updates():
    return [
        proposal("job_title", "Junior Software Developer", "Junior Software Developer"),
        proposal("role_description", "Build and test small web apps", "Build and test small web apps"),
        proposal("working_arrangement", "Hybrid in Cape Town", "hybrid"),
        proposal("location", "Hybrid in Cape Town", "Cape Town"),
        proposal("experience", "One year of experience", 1, kind="number", unit="year"),
        proposal("education", "No degree needed", state="not_required"),
        proposal("working_hours", "Working hours: weekdays 9 to 5", "Weekdays 9 to 5"),
        proposal("availability", "Start next month", "Next month"),
        proposal("javascript", "JavaScript required to build simple interfaces", True, kind="skill", label="JavaScript"),
        proposal("git", "Git preferred for saving changes", True, kind="skill", importance="preferred", label="Git"),
    ]


def test_descriptive_arrangement_is_saved_without_repeating_the_question():
    source = "Hybrid work is required, with two days per week at the office."
    update = proposal("working_arrangement", source, "Hybrid with two days per week at the office")
    draft = apply_draft_updates(new_job_draft("generic-role"), [update], source)
    field = next(f for f in draft["fields"] if f["key"] == "working_arrangement")
    assert field["state"] == "confirmed"
    assert field["target"] == "hybrid"
    assert field["description"] == source
    assert draft_profile(draft)["working_arrangement"]["source_quote"] == source
    # Keep existing AI interpretation of equivalent wording without literal modes.
    indirect = "Work at the employer's office every day."
    inferred = apply_draft_updates(new_job_draft("generic-role"),
        [proposal("working_arrangement", indirect, "on-site")], indirect)
    assert next(f for f in inferred["fields"] if f["key"] == "working_arrangement")["target"] == "on-site"
    # Neither a choice between two modes nor an unsupported mode is confirmation.
    for text, target in (("Remote or hybrid, undecided", "Remote or hybrid"),
                         ("On-site work is required", "Hybrid with two office days")):
        result = apply_draft_updates(new_job_draft("generic-role"),
            [proposal("working_arrangement", text, target)], text)
        assert next(f for f in result["fields"] if f["key"] == "working_arrangement")["state"] == "unanswered"


def test_template_chat_applies_multiple_fields_corrects_and_publishes(monkeypatch):
    updates = developer_updates()
    captured = []

    def interpreted(context, *args):
        captured.append(context)
        return GeneratedTurn(reply="Do not use this unvalidated claim", template_updates=updates)

    monkeypatch.setattr("app.main.generate_turn", interpreted)
    _, headers = authenticate("draft-review@example.com", "recruiter")
    with TestClient(app) as client:
        chat = client.post("/api/chats", json={"template_id": "junior-software-developer"}, headers=headers).json()
        job_id = chat["job_post"]["id"]
        path = f"/api/chats/{chat['id']}/messages"
        result = client.post(path, json={"content": "; ".join(u.source_quote for u in updates)}, headers=headers)
        assert result.status_code == 200
        body = result.json()
        assert body["chat"]["can_publish"] is True
        assert "Publish job" in body["assistant_message"]["content"]
        assert "unvalidated" not in body["assistant_message"]["content"]
        profile = body["chat"]["job_post"]["target_profile"]
        assert "education" not in profile and "role_description" not in profile
        assert profile["javascript"]["type"] == "skill"
        assert profile["git"]["optional"] and profile["git"]["weight"] == .35
        assert body["chat"]["profile"] == profile
        assert captured[0]["chat_id"] == chat["id"]
        assert all(f["state"] == "unanswered" for f in captured[0]["job_draft"]["fields"])

        updates = [proposal("experience", "Actually change experience to two years", 2, kind="number", unit="years")]
        changed = client.post(path, json={"content": updates[0].source_quote}, headers=headers).json()["chat"]
        assert changed["job_post"]["target_profile"]["experience"]["target"] == 2
        assert changed["job_post"]["target_profile"]["javascript"] == profile["javascript"]
        assert len([f for f in changed["job_draft"]["fields"] if f["key"] == "experience"]) == 1
        assert changed["job_post"]["description"] == "Build and test small web apps"
        with SessionLocal() as db:
            job = db.get(models.JobPost, job_id)
            assert job.draft == changed["job_draft"]
            assert build_chat_context(job.chat)["job_draft"] == job.draft
        assert client.post(f"/api/jobs/{job_id}/publish", headers=headers).status_code == 200
        assert client.post(path, json={"content": "Change the role"}, headers=headers).status_code == 200
        public = next(j for j in client.get("/api/public/jobs").json() if j["id"] == job_id)
        assert public["target_profile"] == changed["job_post"]["target_profile"]
        assert "draft" not in public


def test_ambiguous_answers_and_unsupported_proposals_do_not_remove_requirements():
    draft = new_job_draft("junior-software-developer")
    updates = developer_updates()
    draft = apply_draft_updates(draft, updates, "; ".join(u.source_quote for u in updates))
    original = draft_profile(draft)
    for answer in ("That's fine", "Yes", "No", "Okay"):
        changed = apply_draft_updates(draft, [proposal("javascript", answer, state="not_required")], answer)
        assert changed == draft
    assert apply_draft_updates(draft, [proposal("education", "No degree needed", state="not_required")], "What is the weather?") == draft
    for update in (
        proposal("experience", "Experience is two years", 25, kind="number", unit="years"),
        proposal("job_title", "Job title: Developer", True, kind="skill"),
        proposal("javascript", "JavaScript required", "True", kind="skill"),
        proposal("docker", "JavaScript required", True, kind="skill", label="Docker"),
    ):
        assert draft_profile(apply_draft_updates(draft, [update], update.source_quote)) == original
    unclear = proposal("javascript", "JavaScript might be useful but I am unsure", None, state="needs_clarification", kind="skill", importance="unspecified")
    draft = apply_draft_updates(draft, [unclear], unclear.source_quote)
    assert "javascript" not in draft_profile(draft)
    assert not draft_can_publish(draft)
    assert "JavaScript" in draft_question(draft)


def test_remote_location_and_remaining_fields_are_required_before_publish():
    draft = new_job_draft("junior-software-developer")
    updates = [u for u in developer_updates() if u.key not in {"working_arrangement", "location", "education"}]
    updates.append(proposal("working_arrangement", "Remote work", "remote"))
    draft = apply_draft_updates(draft, updates, "; ".join(u.source_quote for u in updates))
    assert not draft_can_publish(draft)
    assert "location" in draft_question(draft)
    updates = [proposal("location", "Remote from anywhere, no location restrictions", state="not_required"),
               proposal("education", "No degree needed", state="not_required")]
    draft = apply_draft_updates(draft, updates, "; ".join(u.source_quote for u in updates))
    assert draft_can_publish(draft)
    change = proposal("working_arrangement", "Change to on-site", "on-site")
    draft = apply_draft_updates(draft, [change], change.source_quote)
    assert not draft_can_publish(draft)
    assert "Where" in draft_question(draft)
    anywhere = proposal("location", "Location: anywhere worldwide", "Anywhere worldwide")
    draft = apply_draft_updates(draft, [anywhere], anywhere.source_quote)
    assert not draft_can_publish(draft)


def test_guided_fallback_does_not_confirm_vague_answers_or_template_suggestions():
    for template in ("plumber", "generic-role"):
        draft = new_job_draft(template)
        for text in ("That's fine", "I like pizza", "hello"):
            draft = apply_draft_updates(draft, fallback_draft_updates(draft, text), text)
        assert all(f["state"] == "unanswered" for f in draft["fields"])
        text = "Job title: Workshop Assistant; Role description: Assist the team with daily repairs; Work arrangement: on-site; Location: Cape Town; No degree needed; Working hours: weekdays; Start availability: immediately"
        draft = apply_draft_updates(draft, fallback_draft_updates(draft, text), text)
        fields = {f["key"]: f for f in draft["fields"]}
        assert fields["education"]["state"] == "not_required"
        assert fields["job_title"]["target"] == "Workshop Assistant"
        assert fields["location"]["target"] == "Cape Town"
        assert not draft_can_publish(draft)
        assert "education" not in draft_profile(draft)


def test_template_provider_receives_saved_states_and_returns_strict_proposals(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"updates": [developer_updates()[5].model_dump()]})}]}]}

    def post(url, **kwargs):
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setattr("app.services.ai.httpx.post", post)
    context = {"chat_id": 1, "job": None, "draft": {}, "messages": [], "job_draft": new_job_draft("junior-software-developer")}
    turn = generate_turn(context, "employer", "No degree needed", "Next question", Settings(_env_file=None, ai_provider="openai", openai_api_key="test"))
    assert turn.template_updates[0].state == "not_required"
    payload = json.loads(captured["input"])
    assert len(payload["job_draft"]["fields"]) == 11
    assert all("suggestion" not in f for f in payload["job_draft"]["fields"])
    schema = captured["text"]["format"]["schema"]
    assert schema["required"] == ["updates"]
    assert schema["$defs"]["DraftUpdate"]["additionalProperties"] is False
    assert "weight" not in schema["$defs"]["DraftUpdate"]["properties"]
    assert captured["store"] is False


def test_short_clarifications_reuse_values_and_preserve_importance():
    draft = new_job_draft("junior-software-developer")
    updates = developer_updates()
    updates[-2] = proposal("javascript", "JavaScript with two years of experience", 2,
                            kind="number", unit="years", importance="unspecified", label="JavaScript")
    draft = apply_draft_updates(draft, updates, "; ".join(u.source_quote for u in updates))
    assert "JavaScript" in draft_question(draft)
    draft = apply_draft_updates(draft, fallback_draft_updates(draft, "Required"), "Required")
    assert draft_profile(draft)["javascript"]["target"] == 2
    assert draft_can_publish(draft)
    correction = proposal("javascript", "Change JavaScript to three years", 3, kind="number", unit="years", importance="unspecified")
    draft = apply_draft_updates(draft, [correction], correction.source_quote)
    assert draft_profile(draft)["javascript"]["importance"] == "required"
    assert draft_profile(draft)["javascript"]["target"] == 3
    wrong = proposal("javascript", "No degree needed; JavaScript required", state="not_required")
    assert draft_profile(apply_draft_updates(draft, [wrong], wrong.source_quote)) == draft_profile(draft)


def test_plumber_and_generic_can_finish_with_labelled_guided_answers():
    for template, skills in (("plumber", "Plumbing required; Pipe fitting required; Tools: pipe cutters required"),
                             ("generic-role", "Skills: repair workshop gates required; No tools needed")):
        text = ("Job title: Maintenance Worker; Role description: The person will repair pipes; "
                "Work arrangement: on-site; Location: Cape Town; No degree needed; "
                "Working hours: weekdays; Start availability: immediately; Experience: two years; " + skills)
        draft = new_job_draft(template)
        draft = apply_draft_updates(draft, fallback_draft_updates(draft, text), text)
        assert draft_can_publish(draft), draft_question(draft)
        assert "education" not in draft_profile(draft)


def test_numeric_experience_accepts_singular_year_without_accepting_other_units():
    draft = new_job_draft("generic-role")
    text = "Experience: one year of customer service"
    guided = apply_draft_updates(draft, fallback_draft_updates(draft, text), text)
    assert draft_profile(guided)["experience"]["target"] == 1
    for source, target, unit in ((text, 1, "years"), ("Experience: two years", 2, "year")):
        update = proposal("experience", source, target, kind="number", unit=unit)
        assert draft_profile(apply_draft_updates(draft, [update], source))["experience"]["target"] == target
    for source in ("Experience: one month", "Experience: one yearbook project"):
        update = proposal("experience", source, 1, kind="number", unit="years")
        assert "experience" not in draft_profile(apply_draft_updates(draft, [update], source))
