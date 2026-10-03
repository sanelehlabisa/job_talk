from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.services.ai import GeneratedTurn
from app.services.candidate_application import edit_application_answer, application_fields
from app.services.matching import match_profiles
from app.tests.test_candidate_application import CRITERIA, guest as start_guest, proposal
from app.tests.test_flow import (
    app, authenticate, create_published_job, application_payload, setup_function,
    SessionLocal, models,
)


def guest(client, job_id=None):
    chat, headers = start_guest(client, job_id)
    return client.get(f"/api/chats/{chat['id']}", headers=headers).json(), headers


def save(client, chat, headers, key, value, **extra):
    return client.put(f"/api/chats/{chat['id']}/application/field", headers=headers, json={
        "key": key, "value": value, "criteria_version": chat["target_job"]["criteria_version"], **extra,
    })


def test_form_and_chat_share_evidence_and_submit_the_same_scores(monkeypatch):
    job_id = create_published_job(target_profile=CRITERIA)
    with TestClient(app) as client:
        chat, headers = guest(client, job_id)
        path = f"/api/chats/{chat['id']}"
        original_job = deepcopy(chat["target_job"])
        def no_model(*args):
            raise AssertionError("Direct form edits must not need an AI call")
        monkeypatch.setattr("app.main.generate_turn", no_model)
        for key, value in [("python", "2.5 years building Python APIs"), ("git", "I don't have that skill"),
                           ("working_hours", "40 hours a week"), ("location", "Cape Town")]:
            response = save(client, chat, headers, key, value)
            assert response.status_code == 200, response.text
            chat = response.json()
        assert len(chat["messages"]) == 1  # Form edits do not clutter the conversation.
        assert chat["target_job"] == original_job
        assert chat["profile"]["python"]["value"] == 2.5
        assert chat["profile"]["git"]["assessment"] == "gap"
        assert {f["key"]: f["state"] for f in chat["application_fields"]}["git"] == "gap"

        # Guided fallback must preserve typed form values on an unrelated turn.
        monkeypatch.setattr("app.main.generate_turn", lambda *args: GeneratedTurn(reply=""))
        response = client.post(path + "/messages", headers=headers, json={"content": "hello"})
        assert response.json()["chat"]["profile"] == chat["profile"]
        def correction(context, intent, text, fallback):
            assert context["draft"]["python"]["value"] == 2.5
            assert context["draft"]["working_hours"]["evidence"] == "40 hours a week"
            return GeneratedTurn(reply="", candidate_updates=[proposal("python", text, 2)])
        monkeypatch.setattr("app.main.generate_turn", correction)
        response = client.post(path + "/messages", headers=headers, json={"content": "Correction: two years of Python experience"})
        chat = response.json()["chat"]
        assert chat["profile"]["python"]["value"] == 2
        assert chat["profile"]["working_hours"]["value"] == "40 hours a week"
        assert client.get(path, headers=headers).json()["application_fields"] == chat["application_fields"]

        response = client.post(f"/api/jobs/{job_id}/apply", headers=headers, json={
            **application_payload(chat["id"]), "criteria_version": chat["target_job"]["criteria_version"],
        })
        assert response.status_code == 201, response.text
        submitted = response.json()
        expected = match_profiles(chat["profile"], CRITERIA)
        assert submitted["match_result"]["criteria"] == expected["criteria"]
        assert submitted["candidate_profile"]["python"] == chat["profile"]["python"]
        assert submitted["match_result"]["criteria"]["git"]["score"] == 0
        assert save(client, chat, headers, "python", "10 years").status_code == 409


def test_clearing_answer_keeps_requirement_and_prevents_history_recovery(monkeypatch):
    job_id = create_published_job(target_profile=CRITERIA)
    with TestClient(app) as client:
        chat, headers = guest(client, job_id)
        path = f"/api/chats/{chat['id']}"
        old = proposal("python", "I have three years of Python experience", 3)
        monkeypatch.setattr("app.main.generate_turn", lambda *args: GeneratedTurn(reply="", candidate_updates=[old]))
        assert client.post(path + "/messages", headers=headers, json={"content": old.source_quote}).status_code == 200
        cleared = save(client, chat, headers, "python", "").json()
        assert next(f for f in cleared["application_fields"] if f["key"] == "python")["state"] == "unanswered"
        assert cleared["target_job"]["target_profile"]["python"]["target"] == 3
        response = client.post(path + "/messages", headers=headers, json={"content": "What else?"})
        assert response.json()["chat"]["profile"]["python"]["evidence"] == ""
        response = client.post(path + "/messages", headers=headers, json={"content": old.source_quote})
        assert response.json()["chat"]["profile"]["python"]["value"] == 3


def test_form_edit_requires_scoped_session_current_job_and_open_application():
    job_id = create_published_job(target_profile=CRITERIA)
    _, recruiter = authenticate("editor-other@example.test", "recruiter")
    with TestClient(app) as client:
        chat, headers = guest(client, job_id)
        _, other = guest(client, job_id)
        discovery, discovery_headers = guest(client)
        assert save(client, chat, {}, "python", "3 years").status_code == 401
        assert save(client, chat, other, "python", "3 years").status_code == 404
        assert save(client, chat, recruiter, "python", "3 years").status_code == 404
        assert client.put(f"/api/chats/{discovery['id']}/application/field", headers=discovery_headers,
                          json={"key": "python", "value": "3", "criteria_version": "0" * 64}).status_code == 403
        assert save(client, chat, headers, "invented", "yes").status_code == 404
        assert save(client, chat, headers, "python", "3", weight=1).status_code == 422
        assert save(client, chat, headers, "python", "x" * 501).status_code == 422
        assert save(client, chat, headers, "python", "3", criteria_version="0" * 64).status_code == 409
        with SessionLocal() as db:
            job = db.get(models.JobPost, job_id)
            assert job.target_profile == CRITERIA
            job.chat.status = "closed"
            job.published = False
            db.commit()
        assert save(client, chat, headers, "python", "3 years").status_code == 409


@pytest.mark.parametrize("answer,expected", [("2.5", 2.5), ("two years", 2), ("0", 0),
    ("-2 years", None), ("1-3 years", None), ("18 months", None),
    ("some experience", None), ("2 years Python and 3 years Java", None)])
def test_numeric_form_answers_never_invent_or_mix_quantities(answer, expected):
    profile = edit_application_answer({}, CRITERIA, "python", answer)
    assert profile["python"]["value"] == expected
    field = application_fields(profile, CRITERIA)[0]
    assert field["state"] == ("captured" if expected is not None else "needs_clarification")
