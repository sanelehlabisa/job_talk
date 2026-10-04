from fastapi.testclient import TestClient

from app.services.ai import GeneratedTurn
from app.services.matching import MIN_DISCOVERY_SCORE, MIN_RECOMMENDATION_SCORE
from app.tests.test_candidate_application import guest, proposal
from app.tests.test_flow import app, create_published_job, setup_function, SessionLocal, models


def requirement(label, target=True, kind="skill", weight=1):
    return {"label": label, "type": kind, "target": target, "weight": weight, "description": label}


def test_partial_matches_use_low_cutoff_and_reply_names_the_same_jobs():
    create_published_job(email="discovery-plumber@example.test", title="Plumber")
    first = create_published_job(email="discovery-python@example.test", title="Python Developer", target_profile={
        "python": requirement("Python"), "docker": requirement("Docker"), "git": requirement("Git"),
    })
    second = create_published_job(email="discovery-api@example.test", title="Python API Developer", target_profile={
        "python": requirement("Python"), "docker": requirement("Docker"),
        "git": requirement("Git"), "java": requirement("Java"),
    })
    with TestClient(app) as client:
        chat, headers = guest(client)
        path = f"/api/chats/{chat['id']}"
        response = client.post(path + "/messages", headers=headers, json={"content": "I built Python APIs."}).json()
        suggestions = response["recommendations"]
        assert [item["job"]["id"] for item in suggestions] == [first, second]
        assert all(MIN_DISCOVERY_SCORE <= item["match_score"] < MIN_RECOMMENDATION_SCORE for item in suggestions)
        assert all(not item["recommended"] and not item["available_example"] for item in suggestions)
        reply = response["assistant_message"]["content"]
        for index, item in enumerate(suggestions, 1):
            assert f"{index}. {item['job']['title']}" in reply
        assert "Plumber" not in reply
        assert "show matching published jobs here as they become available" not in reply
        old_scores = {item["job"]["id"]: item["match_score"] for item in suggestions}
        corrected = client.post(path + "/messages", headers=headers, json={"content": "I built Docker containers and used Git to save changes."}).json()
        assert all(item["match_score"] > old_scores[item["job"]["id"]] for item in corrected["recommendations"])
        assert client.get(path + "/recommendations", headers=headers).json() == corrected["recommendations"]


def test_checks_all_jobs_before_limiting_and_ignores_location_only_similarity():
    for index in range(6):
        create_published_job(email=f"irrelevant-{index}@example.test", title=f"Welder {index}", target_profile={
            "experience": {**requirement("Experience", 2, "number"), "unit": "years"},
            "location": requirement("Location", "Cape Town", "text"),
            "welding": requirement("Welding", weight=.1),
        })
    relevant = create_published_job(email="relevant@example.test", title="Python Developer", target_profile={
        "python": requirement("Python"), "docker": requirement("Docker"), "git": requirement("Git"),
    })
    with TestClient(app) as client:
        chat, headers = guest(client)
        path = f"/api/chats/{chat['id']}"
        response = client.post(path + "/messages", headers=headers, json={
            "content": "I have three years of Python experience. I built Python APIs. I am in Cape Town."
        }).json()
        assert [item["job"]["id"] for item in response["recommendations"]] == [relevant]
        assert "Welder" not in response["assistant_message"]["content"]


def test_existing_background_is_retained_and_negative_correction_removes_suggestion(monkeypatch):
    job_id = create_published_job(title="Python Developer", target_profile={
        "python": requirement("Python"), "docker": requirement("Docker"), "git": requirement("Git"),
    })
    with TestClient(app) as client:
        chat, headers = guest(client)
        path = f"/api/chats/{chat['id']}"
        client.post(path + "/messages", headers=headers, json={"content": "I built Python APIs for three years in Cape Town."})
        def no_new_evidence(context, intent, text, fallback):
            assert any("three years in Cape Town" in item["content"] for item in context["messages"] if item["role"] == "user")
            assert text == "Are any jobs available for those skills?"
            assert context["draft"]["location"]["evidence"]
            return GeneratedTurn(reply="Invented vacancy at Fake Company", candidate_updates=[])
        monkeypatch.setattr("app.main.generate_turn", no_new_evidence)
        response = client.post(path + "/messages", headers=headers, json={"content": "Are any jobs available for those skills?"}).json()
        assert response["recommendations"][0]["job"]["id"] == job_id
        assert "1. Python Developer" in response["assistant_message"]["content"]
        assert "Fake Company" not in response["assistant_message"]["content"]
        assert "Where are you based" not in response["assistant_message"]["content"]
        text = "Correction: I have no Python experience"
        updates = [proposal("python", text, state="gap")]
        monkeypatch.setattr("app.main.generate_turn", lambda *args: GeneratedTurn(reply="", candidate_updates=updates))
        response = client.post(path + "/messages", headers=headers, json={"content": text}).json()
        assert all(item["available_example"] for item in response["recommendations"])
        assert "available-job examples" in response["assistant_message"]["content"].lower()


def test_honest_no_match_and_no_open_jobs_replies():
    job_id = create_published_job(title="Welder", target_profile={"welding": requirement("Welding")})
    with TestClient(app) as client:
        chat, headers = guest(client)
        path = f"/api/chats/{chat['id']}"
        response = client.post(path + "/messages", headers=headers, json={"content": "I built Python APIs for three years in Cape Town."}).json()
        assert response["recommendations"][0]["available_example"]
        reply = response["assistant_message"]["content"]
        assert "none is closely related" in reply and "1. Welder" in reply
        assert "Where are you based" not in reply
        with SessionLocal() as db:
            db.get(models.JobPost, job_id).published = False
            db.commit()
        response = client.post(path + "/messages", headers=headers, json={"content": "Any available jobs?"}).json()
        assert response["recommendations"] == []
        assert "no open jobs available" in response["assistant_message"]["content"]
        assert "Welder" not in response["assistant_message"]["content"]
