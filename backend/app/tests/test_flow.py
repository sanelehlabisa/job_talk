import json
import os
from decimal import Decimal, ROUND_HALF_UP

os.environ["DATABASE_URL"] = "sqlite:///./test_job_talk.db"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.services.conversation import detect_intent
from app.services.matching import match_profiles
from app.services import llm


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def login(client, email):
    return client.post("/api/auth/login", json={"email": email}).json()


def test_end_to_end_employer_to_application():
    with TestClient(app) as client:
        employer = login(client, "employer@example.com")
        employer_chat = client.post(f"/api/chats?user_id={employer['id']}").json()
        response = client.post(
            f"/api/chats/{employer_chat['id']}/messages",
            json={"content": "I am looking to hire a junior Python developer with FastAPI and two years experience in Cape Town."},
        ).json()
        assert response["chat"]["intent"] == "employer"
        assert response["chat"]["can_publish"] is True
        job = response["chat"]["job_post"]
        assert client.post(f"/api/jobs/{job['id']}/publish").status_code == 200

        candidate = login(client, "candidate@example.com")
        candidate_chat = client.post(f"/api/chats?user_id={candidate['id']}").json()
        response = client.post(
            f"/api/chats/{candidate_chat['id']}/messages",
            json={"content": "I am looking for a job. I have three years of Python experience and built two FastAPI APIs."},
        ).json()
        assert response["chat"]["intent"] == "candidate"
        assert len(response["recommendations"]) == 1
        application = client.post(
            f"/api/jobs/{job['id']}/apply", json={"candidate_chat_id": candidate_chat["id"]}
        )
        assert application.status_code == 201
        assert application.json()["match_result"]["overall_score"] > 0.5


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
        employer = login(client, "trade-employer@example.com")
        employer_chat = client.post(f"/api/chats?user_id={employer['id']}").json()
        response = client.post(
            f"/api/chats/{employer_chat['id']}/messages",
            json={"content": "I am looking to hire a welder with welding and forklift experience in Cape Town, with two years of experience."},
        ).json()
        assert response["chat"]["intent"] == "employer"
        assert response["chat"]["job_post"]["title"] == "Welder"
        assert response["chat"]["can_publish"] is True
        job_id = response["chat"]["job_post"]["id"]
        assert client.post(f"/api/jobs/{job_id}/publish").status_code == 200

        candidate = login(client, "trade-candidate@example.com")
        candidate_chat = client.post(f"/api/chats?user_id={candidate['id']}").json()
        response = client.post(
            f"/api/chats/{candidate_chat['id']}/messages",
            json={"content": "I am looking for a job. I have three years of welding and forklift experience in Cape Town."},
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
        refreshed = client.get(f"/api/chats/{candidate_chat['id']}/recommendations").json()
        assert refreshed[0]["criteria"] == criteria
        assert client.post(
            f"/api/jobs/{job_id}/apply", json={"candidate_chat_id": candidate_chat["id"]}
        ).status_code == 201


def test_send_replays_previous_chat_messages(monkeypatch):
    calls = []

    def fake_reply(intent, profile, user_text, fallback, history):
        calls.append((user_text, history))
        return fallback

    monkeypatch.setattr("app.main.generate_reply", fake_reply)
    with TestClient(app) as client:
        user = login(client, "history@example.com")
        chat = client.post(f"/api/chats?user_id={user['id']}").json()
        first_text = "I am looking for a job."
        first = client.post(
            f"/api/chats/{chat['id']}/messages", json={"content": first_text}
        ).json()
        second_text = "I have welding experience."
        client.post(f"/api/chats/{chat['id']}/messages", json={"content": second_text})

    assert calls[0][1] == [{"role": "assistant", "content": chat["messages"][0]["content"]}]
    assert calls[1] == (
        second_text,
        [
            {"role": "assistant", "content": chat["messages"][0]["content"]},
            {"role": "user", "content": first_text},
            {"role": "assistant", "content": first["assistant_message"]["content"]},
        ],
    )


def test_llm_request_has_role_order_and_current_message_once(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"output": [{"type": "message", "content": [
                {"type": "output_text", "text": "I remember your welding experience."}
            ]}]}).encode()

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr(llm, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    history = [
        {"role": "assistant", "content": "Welcome"},
        {"role": "user", "content": "I know welding"},
        {"role": "assistant", "content": "Tell me more"},
    ]
    reply = llm.generate_reply("candidate", {}, "I also drive forklifts", "fallback", history)
    assert reply == "I remember your welding experience."
    assert captured["store"] is False
    assert [item["role"] for item in captured["input"]] == [
        "developer", "assistant", "user", "assistant", "user"
    ]
    assert captured["input"][-1]["content"] == "I also drive forklifts"


def test_whitespace_message_is_rejected_without_saving():
    with TestClient(app) as client:
        user = login(client, "blank@example.com")
        chat = client.post(f"/api/chats?user_id={user['id']}").json()
        response = client.post(f"/api/chats/{chat['id']}/messages", json={"content": "   "})
        assert response.status_code == 422
        saved = client.get(f"/api/chats/{chat['id']}").json()
        assert len(saved["messages"]) == 1


def test_trade_intent_from_plain_language():
    assert detect_intent("We need a plumber for our site.") == "employer"
    assert detect_intent("I am a welder with three years of experience.") == "candidate"


def test_brief_employer_example_detects_intent():
    assert detect_intent("I need a junior Python developer with FastAPI experience in Cape Town.") == "employer"
