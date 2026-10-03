import pytest
from fastapi.testclient import TestClient

from app.tests.test_flow import app, authenticate, setup_function
from app.services.ai import GeneratedTurn


@pytest.mark.parametrize("role", ["candidate", "recruiter"])
def test_guided_notice_appears_once_per_chat_even_after_context_window(monkeypatch, role):
    monkeypatch.setattr("app.main.generate_turn", lambda *args: GeneratedTurn(reply="Unused fallback"))
    with TestClient(app) as client:
        if role == "candidate":
            session = client.post("/api/auth/guest", json={}).json()
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            chat = client.get("/api/chats", headers=headers).json()[0]
        else:
            _, headers = authenticate("chat-feedback@example.com", "recruiter")
            chat = client.post("/api/chats", headers=headers, json={"template_id": "generic-role"}).json()
        path = f"/api/chats/{chat['id']}/messages"
        for index in range(8):
            response = client.post(path, headers=headers, json={"content": "Hello"})
            assert response.status_code == 200
            reply = response.json()["assistant_message"]["content"]
            assert reply.startswith("I'm using guided questions for now.") == (index == 0)
        saved = client.get(f"/api/chats/{chat['id']}", headers=headers).json()
        assert sum(m["content"].startswith("I'm using guided questions for now.")
                   for m in saved["messages"] if m["sender"] == "assistant") == 1
        if role == "recruiter":
            other = client.post("/api/chats", headers=headers, json={"template_id": "plumber"}).json()
            reply = client.post(f"/api/chats/{other['id']}/messages", headers=headers,
                                json={"content": "Hello"}).json()["assistant_message"]["content"]
            assert reply.startswith("I'm using guided questions for now.")
