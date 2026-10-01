import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

os.environ["DATABASE_URL"] = "sqlite:///./test_job_talk.db"

from fastapi.testclient import TestClient

from app import models
from app.auth import issue_session, token_digest
from app.database import Base, SessionLocal, engine
from app.main import app
from app.services.ai import _preview, generate_reply
from app.services.context import build_chat_context
from app.services.conversation import detect_intent, wants_to_publish
from app.services.matching import match_profiles
from app.settings import Settings


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


def create_published_job(
    email="seed-owner@example.com", title="Test Welder", target_profile=None
):
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
            target_profile=target_profile
            or {"welding": {"weight": 0.9, "description": "Welding experience is required."}},
            published=True,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id


def application_payload(chat_id, name="Nomsa Dlamini", contact="nomsa@example.com"):
    return {
        "candidate_chat_id": chat_id,
        "candidate_name": name,
        "preferred_contact": contact,
        "consent_to_share": True,
    }


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
            json=application_payload(candidate_chat["id"]),
            headers=candidate_headers,
        )
        assert application.status_code == 201
        submitted = application.json()
        assert submitted["match_result"]["overall_score"] > 0.5
        assert submitted["candidate_profile"]["candidate_details"] == {
            "name": "Nomsa Dlamini",
            "preferred_contact": "nomsa@example.com",
        }
        assert submitted["candidate_profile"]["consent"]["share_with_recruiter"] is True
        assert client.post(
            f"/api/chats/{candidate_chat['id']}/messages",
            json={"content": "Change my frozen application"},
            headers=candidate_headers,
        ).status_code == 409


def test_recruiter_refines_and_publishes_a_job_by_saying_done():
    with TestClient(app) as client:
        _, recruiter_headers = authenticate("conversation-recruiter@example.com", "recruiter")
        chat = client.post("/api/chats", headers=recruiter_headers).json()

        too_early = client.post(
            f"/api/chats/{chat['id']}/messages",
            json={"content": "I am done"},
            headers=recruiter_headers,
        ).json()
        assert too_early["chat"]["job_post"] is None
        assert "at least two important criteria" in too_early["assistant_message"]["content"]
        assert client.get("/api/public/jobs").json() == []

        first_answer = client.post(
            f"/api/chats/{chat['id']}/messages",
            json={"content": "I need a welder."},
            headers=recruiter_headers,
        ).json()
        assert first_answer["chat"]["job_post"]["title"] == "Welder"
        assert first_answer["chat"]["can_publish"] is False

        second_answer = client.post(
            f"/api/chats/{chat['id']}/messages",
            json={"content": "Forklift operation is also required, with two years of experience."},
            headers=recruiter_headers,
        ).json()
        assert second_answer["chat"]["can_publish"] is True
        job_id = second_answer["chat"]["job_post"]["id"]
        assert client.get("/api/public/jobs").json() == []

        published = client.post(
            f"/api/chats/{chat['id']}/messages",
            json={"content": "I am done"},
            headers=recruiter_headers,
        ).json()
        assert published["chat"]["status"] == "published"
        assert published["chat"]["job_post"]["published"] is True
        assert "visible to candidates" in published["assistant_message"]["content"]
        assert [job["id"] for job in client.get("/api/public/jobs").json()] == [job_id]

        guest = client.post("/api/auth/guest", json={"job_id": job_id})
        assert guest.status_code == 201


def test_recruiter_compares_candidates_and_closes_recruitment():
    with TestClient(app) as client:
        _, recruiter_headers = authenticate("comparison-owner@example.com", "recruiter")
        recruiter_chat = client.post("/api/chats", headers=recruiter_headers).json()
        role = client.post(
            f"/api/chats/{recruiter_chat['id']}/messages",
            json={
                "content": (
                    "I need a welder with welding and forklift experience, three years of "
                    "experience, based in Cape Town."
                )
            },
            headers=recruiter_headers,
        ).json()
        job_id = role["chat"]["job_post"]["id"]
        assert role["chat"]["status"] == "draft"
        assert client.post(f"/api/jobs/{job_id}/publish", headers=recruiter_headers).status_code == 200
        assert client.get(
            f"/api/applications?job_id={job_id}", headers=recruiter_headers
        ).json() == []

        def start_candidate(message):
            guest = client.post("/api/auth/guest", json={"job_id": job_id}).json()
            headers = {"Authorization": f"Bearer {guest['access_token']}"}
            chat = client.get("/api/chats", headers=headers).json()[0]
            client.post(
                f"/api/chats/{chat['id']}/messages",
                json={"content": message},
                headers=headers,
            )
            return chat["id"], headers

        weaker_chat_id, weaker_headers = start_candidate(
            "I have one year of cleaning experience and I am based in Durban."
        )
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=application_payload(weaker_chat_id, "Busi Molefe", "071 555 0101"),
            headers=weaker_headers,
        ).status_code == 201
        one_candidate = client.get(
            f"/api/applications?job_id={job_id}", headers=recruiter_headers
        ).json()
        assert [item["candidate_profile"]["candidate_details"]["name"] for item in one_candidate] == [
            "Busi Molefe"
        ]

        stronger_chat_id, stronger_headers = start_candidate(
            "I have five years of welding and forklift experience and I am based in Cape Town."
        )
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=application_payload(
                stronger_chat_id, "Nomsa Dlamini", "nomsa@example.com"
            ),
            headers=stronger_headers,
        ).status_code == 201
        pending_chat_id, pending_headers = start_candidate(
            "I have four years of welding experience and I am based in Cape Town."
        )

        compared = client.get(
            f"/api/applications?job_id={job_id}", headers=recruiter_headers
        ).json()
        assert len(compared) == 2
        assert [item["candidate_profile"]["candidate_details"]["name"] for item in compared] == [
            "Nomsa Dlamini",
            "Busi Molefe",
        ]
        assert compared[0]["match_result"]["overall_score"] > compared[1]["match_result"]["overall_score"]
        saved_snapshots = [item["candidate_profile"] for item in compared]

        _, other_recruiter_headers = authenticate("comparison-stranger@example.com", "recruiter")
        assert client.get(
            f"/api/applications?job_id={job_id}", headers=other_recruiter_headers
        ).status_code == 404
        assert client.post(
            f"/api/jobs/{job_id}/close", headers=other_recruiter_headers
        ).status_code == 404
        assert client.get(
            f"/api/applications?job_id={job_id}", headers=pending_headers
        ).status_code == 403
        assert client.post(
            f"/api/jobs/{job_id}/close", headers=pending_headers
        ).status_code == 403

        closed = client.post(f"/api/jobs/{job_id}/close", headers=recruiter_headers)
        assert closed.status_code == 200
        assert closed.json()["published"] is False
        assert client.get(
            f"/api/chats/{recruiter_chat['id']}", headers=recruiter_headers
        ).json()["status"] == "closed"
        assert client.get(f"/api/public/jobs/{job_id}").status_code == 404
        assert client.post("/api/auth/guest", json={"job_id": job_id}).status_code == 404
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=application_payload(pending_chat_id, "Late Candidate", "late@example.com"),
            headers=pending_headers,
        ).status_code == 404
        assert client.post(
            f"/api/chats/{recruiter_chat['id']}/messages",
            json={"content": "Change the closed role"},
            headers=recruiter_headers,
        ).status_code == 409
        assert client.post(f"/api/jobs/{job_id}/publish", headers=recruiter_headers).status_code == 409

        preserved = client.get(
            f"/api/applications?job_id={job_id}", headers=recruiter_headers
        ).json()
        assert [item["candidate_profile"] for item in preserved] == saved_snapshots


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
            json=application_payload(chats[0]["id"]),
            headers=headers,
        ).status_code == 403
        assert client.post("/api/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/auth/me", headers=headers).status_code == 401
        assert client.post("/api/auth/register", json={}).status_code == 404
        assert client.post("/api/auth/login", json={}).status_code == 404


def test_expired_guest_token_is_deleted_and_cannot_be_replayed():
    job_id = create_published_job()
    with TestClient(app) as client:
        guest = client.post("/api/auth/guest", json={"job_id": job_id}).json()
        token = guest["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        with SessionLocal() as db:
            session = db.scalar(
                select(models.AuthSession).where(
                    models.AuthSession.token_hash == token_digest(token)
                )
            )
            session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        assert client.get("/api/chats", headers=headers).status_code == 401
        assert client.get("/api/chats", headers=headers).status_code == 401
        with SessionLocal() as db:
            assert db.scalar(
                select(models.AuthSession).where(
                    models.AuthSession.token_hash == token_digest(token)
                )
            ) is None


def test_two_guests_on_one_job_cannot_cross_application_boundaries():
    job_id = create_published_job()
    with TestClient(app) as client:
        first = client.post("/api/auth/guest", json={"job_id": job_id}).json()
        second = client.post("/api/auth/guest", json={"job_id": job_id}).json()
        first_headers = {"Authorization": f"Bearer {first['access_token']}"}
        second_headers = {"Authorization": f"Bearer {second['access_token']}"}
        first_chat = client.get("/api/chats", headers=first_headers).json()[0]
        second_chat = client.get("/api/chats", headers=second_headers).json()[0]

        assert first["access_token"] != second["access_token"]
        assert first_chat["id"] != second_chat["id"]
        assert first_chat["target_job_id"] == second_chat["target_job_id"] == job_id
        assert client.get(
            f"/api/chats/{first_chat['id']}", headers=second_headers
        ).status_code == 404
        assert client.post(
            f"/api/chats/{first_chat['id']}/messages",
            json={"content": "Read or change the other candidate's chat"},
            headers=second_headers,
        ).status_code == 404
        assert client.get(
            f"/api/chats/{first_chat['id']}/recommendations", headers=second_headers
        ).status_code == 404
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=application_payload(first_chat["id"], "Wrong Candidate", "wrong@example.com"),
            headers=second_headers,
        ).status_code == 404

        assert client.post(
            f"/api/chats/{first_chat['id']}/messages",
            json={"content": "I have three years of welding experience."},
            headers=first_headers,
        ).status_code == 200
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=application_payload(first_chat["id"], "First Candidate", "first@example.com"),
            headers=first_headers,
        ).status_code == 201
        assert len(client.get("/api/applications", headers=first_headers).json()) == 1
        assert client.get("/api/applications", headers=second_headers).json() == []

        assert client.post(
            f"/api/chats/{second_chat['id']}/messages",
            json={"content": "I have one year of welding experience."},
            headers=second_headers,
        ).status_code == 200
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=application_payload(
                second_chat["id"], "Second Candidate", "second@example.com"
            ),
            headers=second_headers,
        ).status_code == 201
        assert len(client.get("/api/applications", headers=second_headers).json()) == 1


def test_job_specific_followups_cover_strong_partial_unrelated_empty_and_interrupted_flows():
    job_id = create_published_job(
        target_profile={
            "welding": {"weight": 0.9, "description": "Welding experience is required."},
            "experience": {
                "weight": 0.8,
                "description": "The role asks for two years of relevant experience.",
            },
            "forklift_operation": {
                "weight": 0.75,
                "description": "Forklift experience is required.",
            },
            "location": {"weight": 0.55, "description": "The role is based in Cape Town."},
        }
    )

    with TestClient(app) as client:
        def start_candidate():
            guest = client.post("/api/auth/guest", json={"job_id": job_id}).json()
            headers = {"Authorization": f"Bearer {guest['access_token']}"}
            chat = client.get("/api/chats", headers=headers).json()[0]
            return headers, chat

        strong_headers, strong_chat = start_candidate()
        strong = client.post(
            f"/api/chats/{strong_chat['id']}/messages",
            json={
                "content": "I have three years of welding and forklift experience in Cape Town."
            },
            headers=strong_headers,
        ).json()
        assert "captured evidence for this role’s criteria" in strong["assistant_message"]["content"]
        assert len(strong["recommendations"]) == 1

        partial_headers, partial_chat = start_candidate()
        partial = client.post(
            f"/api/chats/{partial_chat['id']}/messages",
            json={"content": "I have three years of welding experience in Cape Town."},
            headers=partial_headers,
        ).json()
        assert "forklift operation experience" in partial["assistant_message"]["content"]

        unrelated_headers, unrelated_chat = start_candidate()
        unrelated = client.post(
            f"/api/chats/{unrelated_chat['id']}/messages",
            json={"content": "I have worked in a retail shop."},
            headers=unrelated_headers,
        ).json()
        assert "welding experience" in unrelated["assistant_message"]["content"]

        empty_headers, empty_chat = start_candidate()
        assert client.post(
            f"/api/chats/{empty_chat['id']}/messages",
            json={"content": "   "},
            headers=empty_headers,
        ).status_code == 422
        assert len(
            client.get(f"/api/chats/{empty_chat['id']}", headers=empty_headers).json()["messages"]
        ) == 1

        refreshed = client.get(
            f"/api/chats/{partial_chat['id']}", headers=partial_headers
        ).json()
        assert {"welding", "experience", "location"} <= refreshed["profile"].keys()
        completed = client.post(
            f"/api/chats/{partial_chat['id']}/messages",
            json={"content": "I operated a forklift every day and I am available immediately."},
            headers=partial_headers,
        ).json()
        assert "captured evidence for this role’s criteria" in completed["assistant_message"]["content"]
        assert {"welding", "experience", "location", "forklift_operation", "availability"} <= completed["chat"]["profile"].keys()


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
            json=application_payload(candidate_chat["id"]),
            headers=stranger_headers,
        ).status_code == 404
        no_consent = application_payload(candidate_chat["id"])
        no_consent["consent_to_share"] = False
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=no_consent,
            headers=candidate_headers,
        ).status_code == 422
        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=application_payload(candidate_chat["id"]),
            headers=candidate_headers,
        ).status_code == 201

        assert len(client.get("/api/applications", headers=candidate_headers).json()) == 1
        recruiter_applications = client.get(
            f"/api/applications?job_id={job_id}", headers=employer_headers
        ).json()
        assert len(recruiter_applications) == 1
        assert recruiter_applications[0]["candidate_profile"]["candidate_details"] == {
            "name": "Nomsa Dlamini",
            "preferred_contact": "nomsa@example.com",
        }
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
            json=application_payload(candidate_chat["id"]),
            headers=candidate_headers,
        ).status_code == 201


def test_send_replays_previous_chat_messages(monkeypatch):
    calls = []

    def fake_reply(context, intent, user_text, fallback):
        calls.append((context, user_text))
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
        {
            "chat_id": chat["id"],
            "job": None,
            "draft": {},
            "messages": [{"role": "assistant", "content": chat["messages"][0]["content"]}],
            "user_message_count": 0,
        },
        first_text,
    )
    assert calls[1] == (
        {
            "chat_id": chat["id"],
            "job": None,
            "draft": {"welding": {"evidence": f"The candidate said: {second_text}"}},
            "messages": [
                {"role": "assistant", "content": chat["messages"][0]["content"]},
                {"role": "user", "content": first_text},
                {"role": "assistant", "content": first["assistant_message"]["content"]},
            ],
            "user_message_count": 1,
        },
        second_text,
    )


def test_mock_ai_previews_current_message_and_chat_context():
    context = {
        "chat_id": 42,
        "job": {"id": 7, "title": "Workshop Welder", "criteria": {"welding": {}}},
        "draft": {"welding": {"evidence": "I know welding"}},
        "messages": [
            {"role": "assistant", "content": "Welcome"},
            {"role": "user", "content": "I know welding"},
            {"role": "assistant", "content": "Tell me more"},
        ],
    }
    reply = generate_reply(context, "candidate", "I also drive forklifts", "fallback")
    assert reply.startswith('"I alslifts"')
    assert "Chat #42 context: 3 earlier message(s)" in reply
    assert 'previous user message "I knolding"' in reply
    assert "Selected job #7: Workshop Welder." in reply
    assert "Draft fields: welding." in reply
    assert "Mode: job seeker." in reply
    assert reply.endswith("fallback")


def test_readiness_checks_database_connection():
    with TestClient(app) as client:
        response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_mock_ai_preview_has_at_most_ten_source_characters():
    assert _preview("short") == "short"
    assert _preview("1234567890") == "1234567890"
    assert _preview("12345678901") == "1234578901"
    assert _preview("  five   spaces  ") == "five paces"


def test_mock_ai_keeps_short_messages_and_chat_context_separate():
    first_chat = generate_reply(
        {"chat_id": 1, "job": None, "draft": {}, "messages": []},
        None,
        "hello",
        "choose a path",
    )
    second_chat = generate_reply(
        {
            "chat_id": 2,
            "job": None,
            "draft": {},
            "messages": [{"role": "user", "content": "old role"}],
        },
        "employer",
        "new role",
        "describe the job",
    )
    assert first_chat.startswith('"hello"')
    assert "Chat #1 context: 0 earlier message(s); no previous user message." in first_chat
    assert "old role" not in first_chat
    assert "Chat #2 context: 1 earlier message(s)" in second_chat
    assert 'previous user message "old role"' in second_chat
    assert "Mode: hiring." in second_chat


def test_openai_provider_uses_bounded_current_chat_context(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"reply": "What welding work have you completed?"}),
                            }
                        ],
                    }
                ]
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.ai.httpx.post", fake_post)
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="sk-test-only",
        openai_model="gpt-4o-mini",
    )
    context = {
        "chat_id": 9,
        "job": {"id": 3, "title": "Welder", "criteria": {"welding": {"weight": 0.9}}},
        "draft": {"experience": {"evidence": "Three years"}},
        "messages": [{"role": "assistant", "content": "Tell me about your work."}],
        "user_message_count": 1,
    }

    reply = generate_reply(
        context,
        "candidate",
        "I can weld",
        "Tell me about your welding evidence.",
        settings=settings,
    )

    assert reply == "What welding work have you completed?"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["json"]["model"] == "gpt-4o-mini"
    assert captured["json"]["store"] is False
    assert captured["json"]["max_output_tokens"] == 180
    assert captured["json"]["text"]["format"]["strict"] is True
    sent = json.loads(captured["json"]["input"])
    assert sent["selected_job"]["id"] == 3
    assert sent["earlier_messages"] == context["messages"]
    assert sent["current_message"] == "I can weld"
    assert len(captured["json"]["input"]) <= 24_000


def test_openai_provider_falls_back_and_obeys_per_chat_limit(monkeypatch):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append((args, kwargs))
        raise ValueError("provider unavailable")

    monkeypatch.setattr("app.services.ai._openai_reply", unavailable)
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="sk-test-only",
        ai_max_calls_per_chat=2,
    )
    context = {
        "chat_id": 10,
        "job": None,
        "draft": {},
        "messages": [],
        "user_message_count": 1,
    }
    fallback = generate_reply(context, "employer", "Need a welder", "Ask for experience", settings)
    assert "Mock AI received your message" in fallback
    assert len(calls) == 1

    context["user_message_count"] = 2
    limited = generate_reply(context, "employer", "Another detail", "Ask for location", settings)
    assert "Mock AI received your message" in limited
    assert len(calls) == 1


def test_context_builder_is_bounded_and_never_mixes_guest_chats(monkeypatch):
    captured = []

    def capture_context(context, intent, user_text, fallback):
        captured.append((context, user_text))
        return fallback

    monkeypatch.setattr("app.main.generate_reply", capture_context)
    job_id = create_published_job()
    with TestClient(app) as client:
        first = client.post("/api/auth/guest", json={"job_id": job_id}).json()
        second = client.post("/api/auth/guest", json={"job_id": job_id}).json()
        first_headers = {"Authorization": f"Bearer {first['access_token']}"}
        second_headers = {"Authorization": f"Bearer {second['access_token']}"}
        first_chat = client.get("/api/chats", headers=first_headers).json()[0]
        second_chat = client.get("/api/chats", headers=second_headers).json()[0]

        client.post(
            f"/api/chats/{first_chat['id']}/messages",
            json={"content": "First candidate knows welding."},
            headers=first_headers,
        )
        client.post(
            f"/api/chats/{second_chat['id']}/messages",
            json={"content": "Second candidate has retail experience."},
            headers=second_headers,
        )
        client.post(
            f"/api/chats/{first_chat['id']}/messages",
            json={"content": "I have three years of experience."},
            headers=first_headers,
        )

        first_context, _ = captured[0]
        second_context, _ = captured[1]
        resumed_first_context, _ = captured[2]
        assert first_context["chat_id"] == resumed_first_context["chat_id"] == first_chat["id"]
        assert second_context["chat_id"] == second_chat["id"]
        assert first_context["job"]["id"] == second_context["job"]["id"] == job_id
        assert "welding" in first_context["job"]["criteria"]
        assert "First candidate" in repr(resumed_first_context)
        assert "Second candidate" not in repr(resumed_first_context)
        assert "First candidate" not in repr(second_context)

        assert client.post(
            f"/api/jobs/{job_id}/apply",
            json=application_payload(
                first_chat["id"], "Private Person", "private-contact@example.com"
            ),
            headers=first_headers,
        ).status_code == 201
        with SessionLocal() as db:
            submitted_chat = db.get(models.Chat, first_chat["id"])
            submitted_context = build_chat_context(submitted_chat)
        assert "private-contact@example.com" not in repr(submitted_context)
        assert "Private Person" not in repr(submitted_context)

    bounded_chat = models.Chat(id=999, intent="candidate", profile={})
    bounded_chat.messages = [
        models.Message(sender="user", content=f"message {index}") for index in range(20)
    ]
    bounded_context = build_chat_context(bounded_chat)
    assert len(bounded_context["messages"]) == 12
    assert bounded_context["messages"][0]["content"] == "message 8"
    assert bounded_context["messages"][-1]["content"] == "message 19"


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


def test_explicit_publish_commands_do_not_match_ordinary_job_text():
    assert wants_to_publish("I am done") is True
    assert wants_to_publish("Publish the job") is True
    assert wants_to_publish("Make this job public") is True
    assert wants_to_publish("The candidate has experience publishing job adverts") is False
