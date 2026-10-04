import json

import pytest
from fastapi.testclient import TestClient

from app.services.ai import GeneratedTurn, MAX_PROVIDER_INPUT_CHARS, _provider_input
from app.services.context import build_chat_context
from app.services.job_templates import apply_draft_updates, draft_profile, draft_question, new_job_draft
from app.tests.test_job_drafts import proposal
from app.tests.test_flow import app, authenticate, models, setup_function


PARAGRAPH = (
    "I wanna create a post for a job position based in south africa durban, the job is for a "
    "graduate elecronic enginer with bsc or beng defree, with pass mark 60%+ overall on their "
    "quelification, the work is full on site, no experince require, but the candiat must have "
    "understing of circuit, and will work pcb designs. be a hight motivated"
)


def electronic_updates():
    return [
        proposal("job_title", "the job is for a graduate elecronic enginer", "Graduate Electronic Engineer"),
        proposal("role_description", "will work pcb designs", "Work on PCB designs"),
        proposal("location", "based in south africa durban", "Durban, South Africa"),
        proposal("working_arrangement", "the work is full on site", "on-site"),
        proposal("experience", "no experince require", state="not_required"),
        proposal("education", "with bsc or beng defree, with pass mark 60%+ overall on their quelification",
                 "BSc or BEng degree with an overall mark of at least 60%"),
        proposal("skills", "must have understing of circuit", "Understanding of circuits"),
    ]


def test_natural_language_fields_accept_spelling_repairs_and_still_require_actual_gaps():
    saved = apply_draft_updates(new_job_draft("generic-role"), electronic_updates(), PARAGRAPH)
    fields = {f["key"]: f for f in saved["fields"]}
    assert fields["job_title"]["target"] == "Graduate Electronic Engineer"
    assert fields["working_arrangement"]["target"] == "on-site"
    assert fields["experience"]["state"] == "not_required"
    assert "experience" not in draft_profile(saved)
    assert "60%" in fields["education"]["target"]
    assert fields["skills"]["state"] == "confirmed"
    assert "company" in draft_question(saved)
    assert fields["working_hours"]["state"] == fields["availability"]["state"] == "unanswered"


def test_old_user_evidence_fills_only_unanswered_fields_and_keeps_latest_corrections():
    draft = new_job_draft("generic-role")
    correction = "Job title: Junior Circuit Designer. Experience: two years. Work arrangement: hybrid."
    updates = [proposal("job_title", "Junior Circuit Designer", "Junior Circuit Designer"),
               proposal("experience", "Experience: two years", 2, kind="number", unit="years"),
               proposal("working_arrangement", "Work arrangement: hybrid", "hybrid")]
    draft = apply_draft_updates(draft, updates, correction)
    saved = apply_draft_updates(draft, electronic_updates(), "Use what I already told you", [PARAGRAPH, correction])
    fields = {f["key"]: f for f in saved["fields"]}
    assert fields["job_title"]["target"] == "Junior Circuit Designer"
    assert fields["experience"]["target"] == 2
    assert fields["working_arrangement"]["target"] == "hybrid"
    assert fields["education"]["state"] == fields["skills"]["state"] == "confirmed"


def test_history_cannot_supply_unquoted_facts_or_replace_ambiguous_requirements():
    draft = new_job_draft("generic-role")
    assert apply_draft_updates(draft, electronic_updates(), "Use earlier details", []) == draft
    for answer in ("That's fine", "Yes", "No"):
        assert apply_draft_updates(draft, electronic_updates(), answer, [PARAGRAPH]) == draft
    invented = proposal("job_title", "graduate elecronic enginer", "Senior Aerospace Engineer")
    saved = apply_draft_updates(draft, [invented], PARAGRAPH)
    assert saved == draft
    vague = proposal("experience", "not sure if experience is required", state="not_required")
    assert apply_draft_updates(draft, [vague], vague.source_quote) == draft
    wrong = proposal("experience", "No degree needed", state="not_required")
    assert apply_draft_updates(draft, [wrong], wrong.source_quote) == draft
    invented_mark = electronic_updates()[5]
    invented_mark.target = "BSc or BEng with 80% overall"
    assert apply_draft_updates(draft, [invented_mark], PARAGRAPH) == draft
    stitched = proposal("skills", "understing of circuit, be a hight motivated", "Circuit knowledge and motivation")
    assert apply_draft_updates(draft, [stitched], "Use earlier details", [PARAGRAPH]) == draft


def test_provider_keeps_early_and_long_messages_and_never_silently_drops_context():
    chat = models.Chat(id=10, intent="employer", profile={})
    long_answer = "Relevant job details. " * 70 + "no experince require"
    chat.messages = [models.Message(sender="user", content=long_answer)] + [
        models.Message(sender="assistant" if i % 2 else "user", content=f"message {i}") for i in range(20)]
    context = build_chat_context(chat)
    payload = json.loads(_provider_input(context, "employer", "Use earlier answers", "Next question"))
    assert len(payload["earlier_messages"]) == 21
    assert payload["earlier_messages"][0]["content"] == long_answer
    assert payload["earlier_messages"][-1]["content"] == "message 19"
    context["messages"] = [{"role": "user", "content": "x" * MAX_PROVIDER_INPUT_CHARS}]
    with pytest.raises(ValueError, match="safety bound"):
        _provider_input(context, "employer", "Continue", "Next question")


def test_api_recovers_rejected_earlier_details_from_its_own_chat(monkeypatch):
    captured = []

    def interpreted(context, *args):
        captured.append(context)
        # First simulate the old missed extraction, then recover it on a later turn.
        return GeneratedTurn(reply="unused", template_updates=[] if len(captured) == 1 else electronic_updates())

    monkeypatch.setattr("app.main.generate_turn", interpreted)
    _, headers = authenticate("history-check@example.com", "recruiter")
    with TestClient(app) as client:
        chat = client.post("/api/chats", json={"template_id": "generic-role"}, headers=headers).json()
        path = f"/api/chats/{chat['id']}/messages"
        client.post(path, json={"content": PARAGRAPH}, headers=headers)
        response = client.post(path, json={"content": "Use what I already told you"}, headers=headers)
        assert response.status_code == 200
        saved = response.json()
        assert PARAGRAPH in [m["content"] for m in captured[-1]["messages"] if m["role"] == "user"]
        assert saved["chat"]["job_post"]["title"] == "Graduate Electronic Engineer"
        assert "experience" not in saved["chat"]["profile"]
        assert "company" in saved["assistant_message"]["content"]
        assert client.get(f"/api/chats/{chat['id']}", headers=headers).json() == saved["chat"]
