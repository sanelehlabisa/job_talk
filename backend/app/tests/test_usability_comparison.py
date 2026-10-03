"""JT-060 guided checks; these deliberately do not claim live LLM accuracy."""

from copy import deepcopy

from fastapi.testclient import TestClient

from app.tests.test_flow import app, authenticate, setup_function, application_payload
from app.services.candidate_application import CandidateUpdate, apply_candidate_updates
from app.services.conversation import update_candidate_profile
from app.services.matching import is_recommended


PLUMBER = (
    "Job title: Plumber; Role description: Repair residential pipes; Work arrangement: on-site; "
    "Location: Cape Town; Experience: two years of plumbing experience; Plumbing required; "
    "Pipe fitting required; Tools: pipe cutters required; No degree needed; "
    "Working hours: weekdays; Start availability: immediately"
)
SHOP_ASSISTANT = (
    "Job title: Shop Assistant; Role description: Help customers choose products; "
    "Work arrangement: on-site; Location: Durban; Experience: one year of customer service; "
    "Skills: customer service is required; No tools needed; No degree needed; "
    "Working hours: weekdays; Start availability: immediately"
)


def test_template_roles_stay_separate_and_three_applicants_use_the_published_contract():
    _, recruiter = authenticate("usability-check@example.com", "recruiter")
    with TestClient(app) as client:
        roles = []
        for template, description in (("plumber", PLUMBER), ("generic-role", SHOP_ASSISTANT)):
            chat = client.post("/api/chats", headers=recruiter, json={"template_id": template}).json()
            role = client.post(f"/api/chats/{chat['id']}/messages", headers=recruiter,
                               json={"content": description}).json()["chat"]
            assert role["can_publish"], role["job_draft"]
            assert client.post(f"/api/jobs/{role['job_post']['id']}/publish", headers=recruiter).status_code == 200
            assert "education" not in role["job_post"]["target_profile"]
            roles.append(role)
        plumber, shop = roles
        assert not {"plumbing", "pipe_fitting", "tools"} & set(shop["job_post"]["target_profile"])
        assert shop["job_post"]["target_profile"]["experience"]["target"] == 1
        assert client.get(f"/api/chats/{plumber['id']}", headers=recruiter).json()["job_draft"] == plumber["job_draft"]
        job_id = plumber["job_post"]["id"]
        requirements = plumber["job_post"]["target_profile"]
        cases = [
            ("Strong", "Cape Town", "I worked on-site in Cape Town. I have four years of plumbing experience. I repaired plumbing and fitted pipes. I used pipe cutters on residential jobs. I can work weekdays and start immediately."),
            ("Partial", "Cape Town", "I have one year of plumbing experience in Cape Town. I cannot do pipe fitting. I have not used pipe cutters. I can work on-site on weekdays and start immediately."),
            ("Unrelated", "Johannesburg", "I have four years of Python experience in Johannesburg. I built Python websites."),
        ]
        submitted = []
        for name, location, message in cases:
            guest = client.post("/api/auth/guest", json={"job_id": job_id}).json()
            headers = {"Authorization": f"Bearer {guest['access_token']}"}
            chat = client.get("/api/chats", headers=headers).json()[0]
            path = f"/api/chats/{chat['id']}"
            captured = client.post(path + "/messages", headers=headers, json={"content": message}).json()["chat"]
            for unrelated in ("I like pizza", "That's fine"):
                unchanged = client.post(path + "/messages", headers=headers, json={"content": unrelated}).json()["chat"]
                assert unchanged["profile"] == captured["profile"]
            fields = {field["key"]: field for field in captured["application_fields"]}
            assert set(fields) == set(requirements)
            if name == "Partial":
                assert fields["pipe_fitting"]["state"] == fields["tools"]["state"] == "gap"
                assert fields["experience"]["value"] == 1
            if name == "Unrelated":
                assert fields["experience"]["state"] == "unanswered"
                assert fields["experience"]["value"] is None
            response = client.post(f"/api/jobs/{job_id}/apply", headers=headers,
                                   json=application_payload(chat["id"], name, name.lower() + "@example.com", location))
            assert response.status_code == 201
            application = response.json()
            scores = application["match_result"]["criteria"]
            assert set(scores) == set(requirements)
            for key, score in scores.items():
                assert score["target_value"] == fields[key]["target"] == requirements[key]["target"]
                assert score["weight"] == fields[key]["weight"] == requirements[key]["weight"]
                assert score["candidate_value"] == fields[key]["value"]
            if name == "Unrelated":
                assert scores["experience"]["score"] == 0
                assert scores["experience"]["gap"] == "missing"
            submitted.append(application)
        strong, partial, unrelated = [item["match_result"] for item in submitted]
        assert strong["overall_score"] > partial["overall_score"] > unrelated["overall_score"]
        assert strong["overall_score"] >= .8 and unrelated["overall_score"] < .2
        assert is_recommended(strong) and not is_recommended(unrelated)
        compared = client.get(f"/api/applications?job_id={job_id}", headers=recruiter).json()
        assert [item["id"] for item in compared] == [item["id"] for item in submitted]
        assert [item["match_result"] for item in compared] == [item["match_result"] for item in submitted]
        assert client.post(f"/api/jobs/{job_id}/close", headers=recruiter).status_code == 200
        assert client.get(f"/api/applications?job_id={job_id}", headers=recruiter).json() == compared
        assert client.get(f"/api/public/jobs/{shop['job_post']['id']}").status_code == 200


def test_experience_scope_is_guarded_for_guided_and_model_updates():
    criteria = {"experience": {"label": "Experience", "type": "number", "target": 2,
                               "unit": "years", "weight": .8, "description": "Two years of plumbing experience"}}
    original_criteria = deepcopy(criteria)
    wrong = "I have four years of Python experience"
    relevant = "I have three years of plumbing experience"
    good = update_candidate_profile({}, relevant, criteria)
    assert good["experience"]["value"] == 3
    assert relevant in good["experience"]["evidence"]
    assert "experience" not in update_candidate_profile({}, wrong, criteria, "experience")
    assert update_candidate_profile(good, wrong, criteria, "experience")["experience"] == good["experience"]
    assert update_candidate_profile({}, "Two years", criteria, "experience")["experience"]["value"] == 2
    gap = update_candidate_profile(good, "I have no plumbing experience", criteria, "experience")
    assert gap["experience"]["assessment"] == "gap" and gap["experience"]["value"] is None
    corrected = update_candidate_profile(good, "Correction: one year of plumbing experience", criteria)
    assert corrected["experience"]["value"] == 1
    assert update_candidate_profile(corrected, wrong, criteria)["experience"] == corrected["experience"]
    for state, value, source in (("captured", 4, wrong), ("gap", None, "I have no Python experience")):
        proposal = CandidateUpdate(key="experience", label="Experience", value=value,
                                   state=state, evidence=source, source_quote=source)
        assert apply_candidate_updates(good, criteria, [proposal], source, [], "experience") == good
        assert apply_candidate_updates({}, criteria, [proposal], "I can start immediately", [source], "experience") == {}
    generic = {"experience": {**criteria["experience"], "description": "Two years of general work experience"}}
    assert update_candidate_profile({}, wrong, generic)["experience"]["value"] == 4
    assert criteria == original_criteria
