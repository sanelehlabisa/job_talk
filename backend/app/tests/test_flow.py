import os
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

os.environ["DATABASE_URL"] = "sqlite:///./test_job_talk.db"

from fastapi.testclient import TestClient

from app import models
from app.auth import issue_session
from app.database import Base, SessionLocal, engine
from app.main import app
from app.services.ai import _preview, generate_reply
from app.services.conversation import detect_intent
from app.services.matching import match_profiles


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def authenticate(email, role):
    with SessionLocal() as db:
        user = models.User(
            email=email,
            role=role,
            approval_status="approved" if role == "recruiter" else "not_required",
        )
        db.add(user)
        db.flush()
        payload = issue_session(db, user).model_dump(mode="json")
    return payload["user"], {"Authorization": f"Bearer {payload['access_token']}"}


def create_published_job(email="seed-owner@example.com", title="Test Welder"):
    with SessionLocal() as db:
        user = models.User(email=email, role="recruiter", approval_status="approved")
        db.add(user)
        db.flush()
        chat = models.Chat(user_id=user.id, intent="employer", status="published")
        db.add(chat)
        db.flush()
        job = models.JobPost(
            chat_id=chat.id,
            user_id=user.id,
            title=title,
            description="A published test role.",
            target_profile={
                "welding": {"weight": 0.9, "description": "Welding experience is required."}
            },
            published=True,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id


def test_end_to_end_employer_to_application():
    with TestClient(app) as client:
        employer, employer_headers = authenticate("employer@example.com", "recruiter")
        employer_chat = client.post("/api/chats", headers=employer_headers).json()
        response = client.post(
            f"/api/chats/{employer_chat['id']}/messages",
            json={"content": "I am looking to hire a junior Python developer with FastAPI and two years experience in Cape Town."},
            headers=employer_headers,
        ).json()
        assert response["chat"]["intent"] == "employer"
        assert response["chat"]["can_publish"] is True
        job = response["chat"]["job_post"]
        assert client.post(f"/api/jobs/{job['id']}/publish", headers=employer_headers).status_code == 200

        guest = client.post("/api/auth/guest", json={"job_id": job["id"]}).json()
        candidate_headers = {"Authorization": f"Bearer {guest['access_token']}"}
        candidate_chat = client.get("/api/chats", headers=candidate_headers).json()[0]
        response = client.post(
            f"/api/chats/{candidate_chat['id']}/messages",
            json={"content": "I am looking for a job. I have three years of Python experience and built two FastAPI APIs."},
            headers=candidate_headers,
        ).json()
        assert response["chat"]["intent"] == "candidate"
        assert len(response["recommendations"]) == 1
        application = client.post(
            f"/api/jobs/{job['id']}/apply",
            json={"candidate_chat_id": candidate_chat["id"]},
            headers=candidate_headers,
        )
        assert application.status_code == 201
        assert application.json()["match_result"]["overall_score"] > 0.5


def test_guest_session_needs_no_email_or_password_and_is_candidate_only():
    job_id = create_published_job()
    with TestClient(app) as client:
        assert client.get("/api/chats").status_code == 401
        assert client.get("/api/jobs").status_code == 401
        assert client.get("/api/applications").status_code == 401

        public_jobs = client.get("/api/public/jobs")
        assert public_jobs.status_code == 200
        assert public_jobs.json()[0]["id"] == job_id
        assert client.get(f"/api/public/jobs/{job_id}").status_code == 200

        guest = client.post("/api/auth/guest", json={"job_id": job_id})
        assert guest.status_code == 201
        payload = guest.json()
        assert payload["user"]["role"] == "candidate"
        headers = {"Authorization": f"Bearer {payload['access_token']}"}
        with SessionLocal() as db:
            session = db.scalar(select(models.AuthSession))
            assert session.token_hash != payload["access_token"]
            assert len(session.token_hash) == 64
        chats = client.get("/api/chats", headers=headers).json()
        assert len(chats) == 1
        assert chats[0]["intent"] == "candidate"
        assert chats[0]["target_job_id"] == job_id
        assert client.post("/api/chats", headers=headers).status_code == 409
        other_job_id = create_published_job(
            email="other-owner@example.com", title="Other published role"
        )
        assert client.post(
            f"/api/jobs/{other_job_id}/apply",
            json={"candidate_chat_id": chats[0]["id"]},
            headers=headers,
        ).status_code == 403
        assert client.post("/api/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/auth/me", headers=headers).status_code == 401
        assert client.post("/api/auth/register", json={}).status_code == 404
        assert client.post("/api/auth/login", json={}).status_code == 404


def test_approved_recruiter_signs_in_with_single_use_email_code(monkeypatch):
    sent = {}
    monkeypatch.setattr(
        "app.main.send_recruiter_login_code",
        lambda recipient, code: sent.update(recipient=recipient, code=code),
    )
    with SessionLocal() as db:
        db.add(
            models.User(
                email="recruiter@example.com",
                role="recruiter",
                approval_status="approved",
            )
        )
        db.commit()

    with TestClient(app) as client:
        requested = client.post(
            "/api/auth/recruiter/request-code",
            json={"email": "recruiter@example.com"},
        )
        assert requested.status_code == 202
        assert sent["recipient"] == "recruiter@example.com"
        verified = client.post(
            "/api/auth/recruiter/verify-code",
            json={"email": "recruiter@example.com", "code": sent["code"]},
        )
        assert verified.status_code == 200
        assert verified.json()["user"]["role"] == "recruiter"
        assert client.post(
            "/api/auth/recruiter/verify-code",
            json={"email": "recruiter@example.com", "code": sent["code"]},
        ).status_code == 401


def test_unknown_recruiter_request_stays_pending_without_revealing_status(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.main.send_recruiter_login_code",
        lambda recipient, code: sent.append((recipient, code)),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/recruiter/request-code",
            json={"email": "pending@example.com"},
        )
        assert response.status_code == 202
        assert sent == []
    with SessionLocal() as db:
        user = db.scalar(select(models.User).where(models.User.email == "pending@example.com"))
        assert user.approval_status == "pending"


def test_chat_job_and_application_access_is_scoped_to_authenticated_owner():
    with TestClient(app) as client:
        employer, employer_headers = authenticate("owner@example.com", "recruiter")
        employer_chat = client.post("/api/chats", headers=employer_headers).json()
        employer_response = client.post(
            f"/api/chats/{employer_chat['id']}/messages",
            json={"content": "I need a welder with welding and forklift experience in Cape Town."},
            headers=employer_headers,
        ).json()
        job_id = employer_response["chat"]["job_post"]["id"]

        candidate, candidate_headers = authenticate("worker@example.com", "candidate")
        assert client.get(
            f"/api/chats?user_id={employer['id']}", headers=candidate_headers
        ).json() == []
        assert client.get(
            f"/api/chats/{employer_chat['id']}", headers=candidate_headers
        ).status_code == 404
        assert client.post(
            f"/api/chats/{employer_chat['id']}/messages",
            json={"content": "change another user's chat"},
            headers=candidate_headers,
        ).status_code == 404
        assert client.get(
            f"/api/chats/{employer_chat['id']}/recommendations", headers=candidate_headers
        ).status_code == 404
        assert client.post(
            f"/api/jobs/{job_id}/publish", headers=candidate_headers
        ).status_code == 403

        assert client.post(
            f"/api/jobs/{job_id}/publish", headers=employer_headers
        ).status_code == 200
        candidate_chat = client.post("/api/chats", headers=candidate_headers).json()
        client.post(
            f"/api/chats/{candidate_chat['id']}/messages",
            json={"content": "I am a welder with forklift experience in Cape Town."},
            headers=candidate_headers,
        )

        stranger, stranger_headers = authenticate("stranger@example.com", "candidate")
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json={"candidate_chat_id": candidate_chat["id"]},
            headers=stranger_headers,
        ).status_code == 404
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json={"candidate_chat_id": candidate_chat["id"]},
            headers=candidate_headers,
        ).status_code == 201

        assert len(client.get("/api/applications", headers=candidate_headers).json()) == 1
        assert len(client.get(
            f"/api/applications?job_id={job_id}", headers=employer_headers
        ).json()) == 1
        assert client.get(
            f"/api/applications?job_id={job_id}", headers=stranger_headers
        ).status_code == 403
        assert client.get("/api/applications", headers=stranger_headers).json() == []


def test_matching_explains_location_and_experience_differences():
    result = match_profiles(
        {
            "location": {"evidence": "The candidate is based in Durban."},
            "experience": {"evidence": "The candidate reported one year of experience."},
        },
        {
            "location": {"weight": 0.5, "description": "The role is based in Cape Town."},
            "experience": {"weight": 0.8, "description": "The role asks for two years of relevant experience."},
        },
    )
    assert result["criteria"]["location"]["score"] == 0.3
    assert result["criteria"]["experience"]["score"] == 0.5
    assert "Durban" in result["criteria"]["location"]["reason"]


def test_trade_worker_can_find_and_apply_to_trade_role():
    with TestClient(app) as client:
        employer, employer_headers = authenticate("trade-employer@example.com", "recruiter")
        employer_chat = client.post("/api/chats", headers=employer_headers).json()
        response = client.post(
            f"/api/chats/{employer_chat['id']}/messages",
            json={"content": "I am looking to hire a welder with welding and forklift experience in Cape Town, with two years of experience."},
            headers=employer_headers,
        ).json()
        assert response["chat"]["intent"] == "employer"
        assert response["chat"]["job_post"]["title"] == "Welder"
        assert response["chat"]["can_publish"] is True
        job_id = response["chat"]["job_post"]["id"]
        assert client.post(f"/api/jobs/{job_id}/publish", headers=employer_headers).status_code == 200

        candidate, candidate_headers = authenticate("trade-candidate@example.com", "candidate")
        candidate_chat = client.post("/api/chats", headers=candidate_headers).json()
        response = client.post(
            f"/api/chats/{candidate_chat['id']}/messages",
            json={"content": "I am looking for a job. I have three years of welding and forklift experience in Cape Town."},
            headers=candidate_headers,
        ).json()
        assert response["chat"]["intent"] == "candidate"
        assert {"welding", "forklift_operation"} <= response["chat"]["profile"].keys()
        assert response["recommendations"][0]["job"]["id"] == job_id
        recommendation = response["recommendations"][0]
        assert recommendation["match_score"] > 0.8
        criteria = recommendation["criteria"]
        assert {"welding", "forklift_operation", "experience"} <= criteria.keys()
        weighted = sum(
            (Decimal(str(item["score"])) * Decimal(str(item["weight"])) for item in criteria.values()),
            Decimal("0"),
        )
        total_weight = sum((Decimal(str(item["weight"])) for item in criteria.values()), Decimal("0"))
        expected = (weighted / total_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert Decimal(str(recommendation["match_score"])) == expected
        refreshed = client.get(
            f"/api/chats/{candidate_chat['id']}/recommendations", headers=candidate_headers
        ).json()
        assert refreshed[0]["criteria"] == criteria
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json={"candidate_chat_id": candidate_chat["id"]},
            headers=candidate_headers,
        ).status_code == 201


def test_send_replays_previous_chat_messages(monkeypatch):
    calls = []

    def fake_reply(chat_id, intent, profile, user_text, fallback, history):
        calls.append((chat_id, user_text, history))
        return fallback

    monkeypatch.setattr("app.main.generate_reply", fake_reply)
    with TestClient(app) as client:
        user, headers = authenticate("history@example.com", "candidate")
        chat = client.post("/api/chats", headers=headers).json()
        first_text = "I am looking for a job."
        first = client.post(
            f"/api/chats/{chat['id']}/messages", json={"content": first_text}, headers=headers
        ).json()
        second_text = "I have welding experience."
        client.post(
            f"/api/chats/{chat['id']}/messages", json={"content": second_text}, headers=headers
        )

    assert calls[0] == (
        chat["id"],
        first_text,
        [{"role": "assistant", "content": chat["messages"][0]["content"]}],
    )
    assert calls[1] == (
        chat["id"],
        second_text,
        [
            {"role": "assistant", "content": chat["messages"][0]["content"]},
            {"role": "user", "content": first_text},
            {"role": "assistant", "content": first["assistant_message"]["content"]},
        ],
    )


def test_mock_ai_previews_current_message_and_chat_context():
    history = [
        {"role": "assistant", "content": "Welcome"},
        {"role": "user", "content": "I know welding"},
        {"role": "assistant", "content": "Tell me more"},
    ]
    reply = generate_reply(42, "candidate", {}, "I also drive forklifts", "fallback", history)
    assert reply.startswith('"I alslifts"')
    assert "Chat #42 context: 3 earlier message(s)" in reply
    assert 'previous user message "I knolding"' in reply
    assert "Mode: job seeker." in reply
    assert reply.endswith("fallback")


def test_mock_ai_preview_has_at_most_ten_source_characters():
    assert _preview("short") == "short"
    assert _preview("1234567890") == "1234567890"
    assert _preview("12345678901") == "1234578901"
    assert _preview("  five   spaces  ") == "five paces"


def test_mock_ai_keeps_short_messages_and_chat_context_separate():
    first_chat = generate_reply(1, None, {}, "hello", "choose a path", [])
    second_chat = generate_reply(
        2,
        "employer",
        {},
        "new role",
        "describe the job",
        [{"role": "user", "content": "old role"}],
    )
    assert first_chat.startswith('"hello"')
    assert "Chat #1 context: 0 earlier message(s); no previous user message." in first_chat
    assert "old role" not in first_chat
    assert "Chat #2 context: 1 earlier message(s)" in second_chat
    assert 'previous user message "old role"' in second_chat
    assert "Mode: hiring." in second_chat


def test_whitespace_message_is_rejected_without_saving():
    with TestClient(app) as client:
        user, headers = authenticate("blank@example.com", "candidate")
        chat = client.post("/api/chats", headers=headers).json()
        response = client.post(
            f"/api/chats/{chat['id']}/messages", json={"content": "   "}, headers=headers
        )
        assert response.status_code == 422
        saved = client.get(f"/api/chats/{chat['id']}", headers=headers).json()
        assert len(saved["messages"]) == 1


def test_trade_intent_from_plain_language():
    assert detect_intent("We need a plumber for our site.") == "employer"
    assert detect_intent("I am a welder with three years of experience.") == "candidate"


def test_brief_employer_example_detects_intent():
    assert detect_intent("I need a junior Python developer with FastAPI experience in Cape Town.") == "employer"
