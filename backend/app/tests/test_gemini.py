import json

import httpx
import pytest

from app.services.ai import generate_turn
from app.services.candidate_application import CandidateUpdate, apply_candidate_updates
from app.services.conversation import candidate_reply, update_candidate_profile
from app.services.job_templates import DraftUpdate, apply_draft_updates, new_job_draft
from app.settings import Settings


def context():
    return {"chat_id": 9, "job": None, "draft": {}, "messages": [
        {"role": "user", "content": "I have three years of Python experience"}], "user_message_count": 1}


@pytest.mark.parametrize("kind", ["candidate", "template", "legacy"])
def test_gemini_uses_existing_schemas_and_bounded_context(monkeypatch, kind):
    captured = {}
    ctx = context()
    if kind == "template":
        ctx["job_draft"] = new_job_draft("plumber")
    data = {"reply": "Where is the role based?", "role_updates": []} if kind == "legacy" else {"updates": []}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, request=httpx.Request("POST", url), json={"candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(data)}]}}]})

    monkeypatch.setattr("app.services.ai.httpx.post", post)
    settings = Settings(_env_file=None, ai_provider="gemini", gemini_api_key="test-secret-only", ai_max_output_tokens=2400)
    turn = generate_turn(ctx, "candidate" if kind == "candidate" else "employer", "I am in cape town", "Next question", settings)
    assert captured["url"].endswith("/gemini-3.5-flash-lite:generateContent")
    assert captured["headers"] == {"x-goog-api-key": "test-secret-only"}
    assert "test-secret-only" not in captured["url"] + json.dumps(captured["json"])
    body = captured["json"]
    config = body["generationConfig"]
    assert config["maxOutputTokens"] == 2400 and config["temperature"] == 0
    assert config["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    assert config["responseMimeType"] == "application/json"
    sent = json.loads(body["contents"][0]["parts"][0]["text"])
    assert sent["earlier_messages"] == ctx["messages"]
    assert sent["current_message"] == "I am in cape town"
    assert "tools" not in body
    if kind == "candidate":
        assert turn.candidate_updates == []
        assert "weight" not in config["responseJsonSchema"]["$defs"]["CandidateUpdate"]["properties"]
    elif kind == "template":
        assert turn.template_updates == []
        assert all("suggestion" not in field for field in sent["job_draft"]["fields"])
    else:
        assert turn.role_updates == []


@pytest.mark.parametrize("response_body", [
    {"candidates": []},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": '{"updates": []}'}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"updates": [{"key": "invented"}]}'}]}}]},
])
def test_gemini_incomplete_or_invalid_output_falls_back(monkeypatch, response_body):
    monkeypatch.setattr("app.services.ai.httpx.post", lambda url, **kwargs:
        httpx.Response(200, request=httpx.Request("POST", url), json=response_body))
    turn = generate_turn(context(), "candidate", "Hello", "Next question",
                         Settings(_env_file=None, ai_provider="gemini", gemini_api_key="test"))
    assert turn.candidate_updates is None and turn.reply == "Next question"


def test_gemini_quota_failure_is_not_retried_or_logged_with_secrets(monkeypatch, caplog):
    calls = []

    def limited(url, **kwargs):
        calls.append(url)
        return httpx.Response(429, request=httpx.Request("POST", url),
                              json={"error": {"code": 429, "message": "secret-and-private-text"}})

    monkeypatch.setattr("app.services.ai.httpx.post", limited)
    settings = Settings(_env_file=None, ai_provider="gemini", gemini_api_key="secret-and-private-text", ai_max_calls_per_chat=2)
    assert generate_turn(context(), "candidate", "Private", "Next question", settings).candidate_updates is None
    assert len(calls) == 1 and "secret-and-private-text" not in caplog.text
    ctx = {**context(), "user_message_count": 2}
    assert generate_turn(ctx, "candidate", "Private", "Next question", settings).candidate_updates is None
    assert len(calls) == 1


def test_lowercase_location_and_willingness_survive_guided_and_ai_validation():
    text = "I am currently based in cape town, but don't mind relocating within south africa, and also I prefer hybrid work."
    profile = update_candidate_profile({"python": {"evidence": "Python"}, "experience": {"evidence": "Three years"}}, text)
    assert "Cape Town" in profile["location"]["evidence"]
    assert profile["working_arrangement"]["assessment"] != "gap"
    assert "Where are you based" not in candidate_reply(profile)
    assert "Cape Town" in update_candidate_profile({}, "I am in cape town mowbray at the moment")["location"]["evidence"]
    updates = [CandidateUpdate(key=key, label=key.replace("_", " "), value=value, state="captured",
                               evidence=text, source_quote=text)
               for key, value in (("location", "cape town"), ("working_arrangement", "hybrid"))]
    saved = apply_candidate_updates({}, None, updates, text, [])
    assert set(saved) == {"location", "working_arrangement"}
    assert saved["working_arrangement"]["value"] == "hybrid"
    denied = update_candidate_profile({}, "I cannot do hybrid work")
    assert denied["working_arrangement"]["assessment"] == "gap"


def test_reset_fixture_refuses_non_test_database(monkeypatch):
    from types import SimpleNamespace
    from sqlalchemy.engine import make_url
    from app.tests import test_flow

    def unexpected_reset(*args, **kwargs):
        pytest.fail("Database reset must never run for a non-test connection")

    monkeypatch.setattr(test_flow.Base.metadata, "drop_all", unexpected_reset)
    for url in ("postgresql://localhost/job_talk", "sqlite:///./job_talk.db"):
        monkeypatch.setattr(test_flow, "engine", SimpleNamespace(url=make_url(url)))
        with pytest.raises(RuntimeError, match="Refusing to reset"):
            test_flow.setup_function()


def test_recruiter_arrangement_normalizes_model_casing_without_accepting_unknown_values():
    draft = new_job_draft("junior-software-developer")
    update = DraftUpdate(key="working_arrangement", label="Work arrangement", type="text",
                         target="Hybrid", unit=None, state="confirmed", importance="unspecified",
                         description="Hybrid work in Cape Town.", source_quote="Hybrid in cape town")
    saved = apply_draft_updates(draft, [update], "Hybrid in cape town")
    field = next(f for f in saved["fields"] if f["key"] == "working_arrangement")
    assert field["target"] == "hybrid" and field["state"] == "confirmed"
    update.target = "Anything"
    assert apply_draft_updates(draft, [update], "Hybrid in cape town") == draft


def test_recruiter_description_accepts_equivalent_written_numbers_only():
    draft = new_job_draft("junior-software-developer")
    update = DraftUpdate(key="experience", label="Experience", type="number", target=1, unit="years",
                         state="confirmed", importance="required", description="1 year of coding experience.",
                         source_quote="one year of coding experience")
    saved = apply_draft_updates(draft, [update], "one year of coding experience")
    field = next(f for f in saved["fields"] if f["key"] == "experience")
    assert field["target"] == 1 and field["state"] == "confirmed"
    update.description = "3 years of coding experience."
    assert apply_draft_updates(draft, [update], "one year of coding experience") == draft
