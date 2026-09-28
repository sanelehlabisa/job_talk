import os
from decimal import Decimal, ROUND_HALF_UP

os.environ["DATABASE_URL"] = "sqlite:///./test_job_talk.db"

from fastapi.testclient import TestClient

from app import models
from app.database import Base, SessionLocal, engine
from app.main import app
from app.services.ai import _preview, generate_reply
from app.services.conversation import detect_intent
from app.services.matching import match_profiles


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


TEST_PASSWORD = "correct-horse-battery-staple"


def register(client, email):
    response = client.post(
        "/api/auth/register", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["user"], {"Authorization": f"Bearer {payload['access_token']}"}


def test_end_to_end_employer_to_application():
    with TestClient(app) as client:
        employer, employer_headers = register(client, "employer@example.com")
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

        candidate, candidate_headers = register(client, "candidate@example.com")
        candidate_chat = client.post("/api/chats", headers=candidate_headers).json()
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


def test_registration_login_logout_and_protected_routes():
    with TestClient(app) as client:
        assert client.get("/api/chats").status_code == 401
        assert client.get("/api/jobs").status_code == 401
        assert client.get("/api/applications").status_code == 401

        registration = client.post(
            "/api/auth/register",
            json={"email": "secure@example.com", "password": TEST_PASSWORD},
        )
        assert registration.status_code == 201
        registered = registration.json()
        assert registered["token_type"] == "bearer"
        assert "password" not in registered["user"]
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        assert client.get("/api/auth/me", headers=headers).json()["email"] == "secure@example.com"

        duplicate = client.post(
            "/api/auth/register",
            json={"email": "secure@example.com", "password": TEST_PASSWORD},
        )
        assert duplicate.status_code == 409
        assert client.post(
            "/api/auth/login",
            json={"email": "secure@example.com", "password": "wrong-password-value"},
        ).status_code == 401

        login = client.post(
            "/api/auth/login",
            json={"email": "secure@example.com", "password": TEST_PASSWORD},
        )
        assert login.status_code == 200
        login_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.post("/api/auth/logout", headers=login_headers).status_code == 204
        assert client.get("/api/auth/me", headers=login_headers).status_code == 401


def test_existing_account_with_chat_cannot_be_claimed_by_email():
    with SessionLocal() as db:
        user = models.User(email="legacy@example.com")
        db.add(user)
        db.flush()
        db.add(models.Chat(user_id=user.id))
        db.commit()

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={"email": "legacy@example.com", "password": TEST_PASSWORD},
        )
        assert response.status_code == 409


def test_chat_job_and_application_access_is_scoped_to_authenticated_owner():
    with TestClient(app) as client:
        employer, employer_headers = register(client, "owner@example.com")
        employer_chat = client.post("/api/chats", headers=employer_headers).json()
        employer_response = client.post(
            f"/api/chats/{employer_chat['id']}/messages",
            json={"content": "I need a welder with welding and forklift experience in Cape Town."},
            headers=employer_headers,
        ).json()
        job_id = employer_response["chat"]["job_post"]["id"]

        candidate, candidate_headers = register(client, "worker@example.com")
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
        ).status_code == 404

        assert client.post(
            f"/api/jobs/{job_id}/publish", headers=employer_headers
        ).status_code == 200
        candidate_chat = client.post("/api/chats", headers=candidate_headers).json()
        client.post(
            f"/api/chats/{candidate_chat['id']}/messages",
            json={"content": "I am a welder with forklift experience in Cape Town."},
            headers=candidate_headers,
        )

        stranger, stranger_headers = register(client, "stranger@example.com")
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
        ).status_code == 404
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
        employer, employer_headers = register(client, "trade-employer@example.com")
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

        candidate, candidate_headers = register(client, "trade-candidate@example.com")
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
        user, headers = register(client, "history@example.com")
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
        user, headers = register(client, "blank@example.com")
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
