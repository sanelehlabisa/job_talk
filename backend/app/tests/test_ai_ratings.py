import json
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from app.services.ai import rate_candidate
from app.services.matching import match_profiles
from app.services.ratings import RATINGS_KEY, RatingReply, save_ratings
from app.settings import Settings
from app.tests.test_candidate_application import CRITERIA
from app.tests.test_application_editor import guest, save
from app.tests.test_flow import app, create_published_job, application_payload, setup_function, SessionLocal, models


def settings(**kwargs):
    return Settings(_env_file=None, ai_provider="gemini", gemini_api_key="test-secret", **kwargs)


def answer(text, value=None, **kwargs):
    return {"evidence": text, "source_quote": text, "value": value if value is not None else text,
            "state": "captured", "assessment": "claimed", **kwargs}


def context(profile):
    return {"chat_id": 1, "job": {"id": 9, "title": "Developer", "criteria": CRITERIA},
            "draft": profile, "messages": [{"role": "user", "content": "Entire original conversation"}]}


def reply(scores=None, job_id=9):
    scores = scores or {"python": 50, "git": 0, "location": 100, "working_hours": 0}
    return {"jobs": [{"job_id": job_id, "criteria": [
        {"key": key, "score": score, "reason": "Candidate partly meets the stated requirement.",
         "evidence_keys": [key] if score else []} for key, score in scores.items()]}]}


def mock_http(monkeypatch, data, calls):
    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={"candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(data)}]}}]})
    monkeypatch.setattr("app.services.ai.httpx.post", post)


def test_batch_ratings_use_saved_answers_full_chat_backend_weights_and_cache(monkeypatch):
    profile = {"python": answer("1.5 years of Python", 1.5), "location": answer("I can relocate to Cape Town")}
    ctx = context(profile)
    calls = []
    mock_http(monkeypatch, reply(), calls)
    scored = rate_candidate(ctx, [ctx["job"]], settings())
    result = match_profiles(scored, CRITERIA)
    assert result["rating_source"] == "gemini" and result["overall_score"] == .38
    assert result["criteria"]["python"]["score"] == .5
    assert result["criteria"]["location"]["score"] == 1
    assert result["criteria"]["git"]["score"] == 0
    assert result["criteria"]["python"]["weight"] == CRITERIA["python"]["weight"]
    payload = json.loads(calls[0]["contents"][0]["parts"][0]["text"])
    assert payload["conversation"] == ctx["messages"] and payload["candidate_answers"] == profile
    assert "test-secret" not in json.dumps(calls)
    rate_candidate({**ctx, "draft": scored}, [ctx["job"]], settings())
    assert len(calls) == 1
    changed = deepcopy(scored)
    changed["python"] = answer("Three years of Python", 3)
    assert match_profiles(changed, CRITERIA)["rating_source"] == "rules"
    changed_criteria = deepcopy(CRITERIA)
    changed_criteria["python"]["target"] = 4
    assert match_profiles(scored, changed_criteria)["rating_source"] == "rules"


@pytest.mark.parametrize("state", ["gap", "unanswered", "needs_clarification"])
def test_model_cannot_give_points_to_gap_clear_or_unclear_answer(state):
    profile = {"python": answer("Earlier Python claim", 3, state=state)}
    data = reply({key: 100 for key in CRITERIA})
    saved = save_ratings(profile, [context(profile)["job"]], RatingReply.model_validate(data), selected=True, model="test")
    assert all(c["score"] == 0 for c in match_profiles(saved, CRITERIA)["criteria"].values())


@pytest.mark.parametrize("change", ["high", "negative", "nan", "string", "boolean", "unknown", "duplicate", "omitted", "fabricated", "weight"])
def test_invalid_model_ratings_fall_back_without_changing_evidence(monkeypatch, change):
    profile = {"python": answer("1.5 years of Python", 1.5), "location": answer("Cape Town")}
    data = reply()
    first = data["jobs"][0]["criteria"][0]
    if change in {"high", "negative", "nan", "string", "boolean"}:
        first["score"] = {"high": 101, "negative": -1, "nan": float("nan"), "string": "100", "boolean": True}[change]
    elif change == "unknown": first["key"] = "invented"
    elif change == "duplicate": data["jobs"][0]["criteria"][1] = first
    elif change == "omitted": data["jobs"][0]["criteria"].pop()
    elif change == "fabricated": first["evidence_keys"] = ["imaginary"]
    else: first["weight"] = 99
    mock_http(monkeypatch, data, [])
    ctx = context(profile)
    saved = rate_candidate(ctx, [ctx["job"]], settings())
    assert match_profiles(saved, CRITERIA)["rating_source"] == "rules"
    assert saved["python"] == profile["python"] and saved[RATINGS_KEY]["calls"] == 1


def test_quota_budget_oversize_and_mock_do_not_block_edits_or_log_private_data(monkeypatch, caplog):
    calls = []
    def unavailable(url, **kwargs):
        calls.append(url)
        return httpx.Response(429, request=httpx.Request("POST", url), json={"error": {"message": "private-secret"}})
    monkeypatch.setattr("app.services.ai.httpx.post", unavailable)
    ctx = context({"python": answer("Python", 1)})
    saved = rate_candidate(ctx, [ctx["job"]], settings(ai_max_calls_per_chat=1))
    assert len(calls) == 1 and "private-secret" not in caplog.text
    rate_candidate({**ctx, "draft": saved}, [ctx["job"]], settings(ai_max_calls_per_chat=1))
    rate_candidate(ctx, [ctx["job"]], Settings(_env_file=None, ai_provider="mock"))
    rate_candidate({**ctx, "messages": [{"role": "user", "content": "x" * 128_001}]}, [ctx["job"]], settings())
    assert len(calls) == 1


def test_equal_criteria_on_different_jobs_keep_separate_ratings():
    criteria = {"experience": {"type": "number", "target": 3, "unit": "years", "weight": 1, "description": "Three years of relevant experience"}}
    jobs = [{"id": 1, "title": "Developer", "criteria": criteria}, {"id": 2, "title": "Welder", "criteria": criteria}]
    profile = {"experience": answer("Three years of software development", 3)}
    data = {"jobs": [reply({"experience": score}, job_id)["jobs"][0] for job_id, score in [(1, 100), (2, 0)]]}
    saved = save_ratings(profile, jobs, RatingReply.model_validate(data), selected=False, model="test")
    assert match_profiles(saved, criteria, 1)["overall_score"] == 1
    assert match_profiles(saved, criteria, 2)["overall_score"] == 0
    assert match_profiles(saved, criteria, 3)["rating_source"] == "rules"
    assert match_profiles(saved, criteria, 1, "Electrician")["rating_source"] == "rules"


def test_generic_experience_alone_does_not_recommend_an_unrelated_trade():
    from app.main import discovery_connection
    job = models.JobPost(title="Welder", target_profile=CRITERIA)
    result = {"rating_source": "gemini", "criteria": {"experience": {
        "label": "Experience", "score": 1, "evidence": "Three years of software"}}}
    assert discovery_connection({}, job, result) == []


def test_form_chat_refresh_submission_and_recruiter_share_frozen_ratings(monkeypatch):
    job_id = create_published_job(target_profile=CRITERIA)
    import app.services.ai as ai
    monkeypatch.setattr(ai, "get_settings", settings)
    calls = []
    mock_http(monkeypatch, reply(job_id=job_id), calls)
    with TestClient(app) as client:
        chat, headers = guest(client, job_id)
        # Missing fields are forced to zero even if the provider awards points.
        response = save(client, chat, headers, "python", "1.5 years of Python")
        assert response.status_code == 200, response.text
        assert RATINGS_KEY not in response.json()["profile"]
        path = f"/api/chats/{chat['id']}"
        shown = client.get(path + "/recommendations", headers=headers).json()[0]
        assert shown["rating_source"] == "gemini"
        assert shown["criteria"]["python"]["score"] == .5
        assert shown["criteria"]["location"]["score"] == 0
        client.get(path + "/recommendations", headers=headers)
        assert len(calls) == 1
        response = client.post(f"/api/jobs/{job_id}/apply", headers=headers, json=application_payload(chat["id"]))
        assert response.status_code == 201, response.text
        frozen = response.json()["match_result"]
        assert "location" not in response.json()["candidate_profile"]
        assert frozen["overall_score"] == shown["match_score"]
        assert frozen["criteria"] == shown["criteria"] and frozen["rating_source"] == "gemini"
        assert len(calls) == 1
        with SessionLocal() as db:
            job = db.get(models.JobPost, job_id)
            job.target_profile = {**job.target_profile, "location": {**CRITERIA["location"], "target": "Durban"}}
            db.commit()
        application = client.get("/api/applications", headers=headers).json()[0]
        assert application["match_result"] == frozen


def test_semantic_discovery_can_match_different_words_across_all_jobs(monkeypatch):
    from app.services.ai import GeneratedTurn
    from app.services.candidate_application import CandidateUpdate
    import app.services.ai as ai
    monkeypatch.setattr(ai, "get_settings", settings)
    create_published_job(email="one@example.test", title="Welder")
    create_published_job(email="two@example.test", title="Driver", target_profile={"driving": {"type": "skill", "target": True, "weight": 1, "description": "Driving"}})
    relevant = create_published_job(email="three@example.test", title="Customer Care", target_profile={"customer_support": {
        "type": "text", "label": "Customer care", "target": "Resolve customer complaints", "description": "Resolve customer complaints", "weight": 1}})
    text = "I helped angry shoppers get refunds."
    monkeypatch.setattr("app.main.generate_turn", lambda *args: GeneratedTurn(reply="", candidate_updates=[
        CandidateUpdate(key="refunds", label="Refunds", value=text, evidence=text, source_quote=text, state="captured")]))
    data = {"jobs": [{"job_id": job_id, "criteria": [{"key": key, "score": score, "reason": "Resolved complaints through refunds." if score else "No relevant evidence.", "evidence_keys": ["refunds"] if score else []}]}
        for job_id, key, score in [(1, "welding", 0), (2, "driving", 0), (relevant, "customer_support", 90)]]}
    calls = []
    mock_http(monkeypatch, data, calls)
    with TestClient(app) as client:
        chat, headers = guest(client)
        response = client.post(f"/api/chats/{chat['id']}/messages", headers=headers, json={"content": text})
        assert response.status_code == 200, response.text
        recs = response.json()["recommendations"]
        assert [r["job"]["id"] for r in recs] == [relevant]
        assert recs[0]["rating_source"] == "gemini" and recs[0]["match_score"] == .9
        payload = json.loads(calls[0]["contents"][0]["parts"][0]["text"])
        assert len(payload["jobs"]) == 3 and payload["conversation"][-1]["content"] == text
