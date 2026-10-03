"""Published edits reuse draft JSON and preserve submitted evidence and scores."""
from copy import deepcopy

from fastapi.testclient import TestClient

from app.services.ai import GeneratedTurn
from app.services.job_templates import draft_profile, finish_draft
from app.services.matching import match_profiles, is_recommended
from app.tests.test_draft_editor import ready_draft
from app.tests.test_job_drafts import proposal
from app.tests.test_candidate_application import guest
from app.tests.test_flow import (
    app, authenticate, setup_function, SessionLocal, models, application_payload,
    create_published_job,
)


def publish_ready_job(client, headers):
    chat = client.post('/api/chats', headers=headers, json={'template_id': 'junior-software-developer'}).json()
    draft = finish_draft(ready_draft())
    with SessionLocal() as db:
        job = db.get(models.JobPost, chat['job_post']['id'])
        job.draft = draft
        job.target_profile = job.chat.profile = draft_profile(draft)
        fields = {f['key']: f for f in draft['fields']}
        job.title, job.description = fields['job_title']['target'], fields['role_description']['target']
        db.commit()
    response = client.post(f"/api/jobs/{chat['job_post']['id']}/publish", headers=headers)
    assert response.status_code == 200
    return chat, response.json()


def test_published_chat_and_form_save_until_republished_with_frozen_applications(monkeypatch):
    _, owner = authenticate('live-owner@example.com', 'recruiter')
    _, outsider = authenticate('live-outsider@example.com', 'recruiter')
    with TestClient(app) as client:
        chat, live = publish_ready_job(client, owner)
        path = f"/api/chats/{chat['id']}"
        job_id = live['id']
        candidate, candidate_headers = guest(client, job_id)
        client.post(f"/api/chats/{candidate['id']}/messages", headers=candidate_headers,
                    json={'content': 'I have two years of JavaScript experience in Cape Town.'})
        submitted = client.post(f'/api/jobs/{job_id}/apply', headers=candidate_headers,
                                json={**application_payload(candidate['id']), 'criteria_version': live['criteria_version']})
        assert submitted.status_code == 201
        snapshot = submitted.json()
        summary = client.get(f"/api/chats/{candidate['id']}", headers=candidate_headers).json()['application_fields']
        waiting, waiting_headers = guest(client, job_id)

        update = proposal('experience', 'Change experience to five years', 5, kind='number', unit='years')
        monkeypatch.setattr('app.main.generate_turn', lambda *args: GeneratedTurn(reply='', template_updates=[update]))
        assert client.post(path + '/messages', headers=outsider, json={'content': update.source_quote}).status_code == 404
        assert client.put(path + '/draft/field', headers=outsider, json={'key': 'job_title', 'label': 'Job title', 'value': 'Edited Developer'}).status_code == 404
        assert client.post(f'/api/jobs/{job_id}/publish', headers=outsider).status_code == 404
        response = client.post(path + '/messages', headers=owner, json={'content': update.source_quote})
        assert response.status_code == 200
        edited = response.json()['chat']
        assert edited['profile']['experience']['target'] == 5
        assert edited['job_post']['target_profile']['experience']['target'] == 1
        assert edited['has_unpublished_changes'] and edited['can_publish']
        assert 'Publish changes' in response.json()['assistant_message']['content']
        form = client.put(path + '/draft/field', headers=owner, json={'key': 'job_title', 'label': 'Job title', 'value': 'Edited Developer'})
        assert form.status_code == 200
        assert client.get(f'/api/public/jobs/{job_id}').json() == live
        assert len(client.get('/api/chats', headers=owner).json()) == 1
        assert client.get(path, headers=owner).json()['has_unpublished_changes']

        published = client.post(f'/api/jobs/{job_id}/publish', headers=owner).json()
        assert published['title'] == 'Edited Developer'
        assert published['target_profile']['experience']['target'] == 5
        assert published['criteria_version'] != live['criteria_version']
        reloaded = client.get(path, headers=owner).json()
        assert reloaded['job_draft'] and reloaded['status'] == 'published'
        assert not reloaded['can_publish'] and not reloaded['has_unpublished_changes']
        assert client.get(f'/api/public/jobs/{job_id}').json() == published
        previous = client.get(f'/api/applications?job_id={job_id}', headers=owner).json()[0]
        assert previous['earlier_requirements']
        assert previous['candidate_profile'] == snapshot['candidate_profile']
        assert previous['match_result'] == snapshot['match_result']
        assert client.get(f"/api/chats/{candidate['id']}", headers=candidate_headers).json()['application_fields'] == summary

        # A candidate who reviewed the earlier requirements must review the new ones.
        payload = {**application_payload(waiting['id']), 'criteria_version': live['criteria_version']}
        assert client.post(f'/api/jobs/{job_id}/apply', headers=waiting_headers, json=payload).status_code == 409
        payload['criteria_version'] = published['criteria_version']
        assert client.post(f'/api/jobs/{job_id}/apply', headers=waiting_headers, json=payload).status_code == 201
        applications = client.get(f'/api/applications?job_id={job_id}', headers=owner).json()
        assert [a['earlier_requirements'] for a in applications] == [False, True]


def test_closing_date_edits_need_publish_and_closed_chat_stays_editable():
    _, headers = authenticate('deadline-owner@example.com', 'recruiter')
    with TestClient(app) as client:
        chat, live = publish_ready_job(client, headers)
        path = f"/api/chats/{chat['id']}"
        payload = {'key': 'closing_date', 'label': 'Closing date', 'value': '2000-01-01'}
        assert client.put(path + '/draft/field', headers=headers, json=payload).status_code == 200
        assert client.get(f"/api/public/jobs/{live['id']}").json()['closing_date'] is None
        assert client.post(f"/api/jobs/{live['id']}/publish", headers=headers).json()['closing_date'] == '2000-01-01'
        assert client.get(f"/api/public/jobs/{live['id']}").status_code == 404
        # Removing a deadline is also staged, then makes the existing post available.
        assert client.delete(path + '/draft/fields/closing_date', headers=headers).status_code == 200
        assert client.get(f"/api/public/jobs/{live['id']}").status_code == 404
        assert client.post(f"/api/jobs/{live['id']}/publish", headers=headers).status_code == 200
        assert client.get(f"/api/public/jobs/{live['id']}").status_code == 200
        client.post(f"/api/jobs/{live['id']}/close", headers=headers)
        assert client.post(path + '/messages', headers=headers, json={'content': 'Role description: Build and test mobile apps'}).status_code == 200
        assert client.get(path, headers=headers).json()['status'] == 'closed'
        assert client.get(path, headers=headers).json()['job_post']['description'] == live['description']
        assert client.post(f"/api/jobs/{live['id']}/publish", headers=headers).status_code == 409


def test_legacy_job_and_application_are_preserved_when_editing(monkeypatch):
    _, owner = authenticate('legacy-owner@example.com', 'recruiter')
    with TestClient(app) as client:
        chat, live = publish_ready_job(client, owner)
        candidate, headers = guest(client, live['id'])
        result = client.post(f"/api/jobs/{live['id']}/apply", headers=headers, json=application_payload(candidate['id'])).json()
        old_result = deepcopy(result['match_result'])
        old_result.pop('criteria_version')
        old_result.pop('requirements')
        with SessionLocal() as db:
            db.get(models.Application, result['id']).match_result = old_result
            db.get(models.JobPost, live['id']).draft = None
            db.commit()
        path = f"/api/chats/{chat['id']}"
        original = client.get(path, headers=owner).json()
        assert original['job_draft'] and not original['has_unpublished_changes']
        assert client.put(path + '/draft/field', headers=owner, json={'key': 'experience', 'label': 'Experience', 'value': '3 years of experience'}).status_code == 200
        assert client.post(f"/api/jobs/{live['id']}/publish", headers=owner).status_code == 200
        saved = client.get(f"/api/applications?job_id={live['id']}", headers=owner).json()[0]
        assert saved['earlier_requirements']
        assert saved['match_result']['criteria'] == old_result['criteria']
        assert saved['match_result']['requirements'] == result['match_result']['requirements']
        assert saved['match_result']['criteria_version'] == live['criteria_version']


def test_discovery_examples_exclude_closed_private_expired_jobs_and_never_invent():
    available = create_published_job(email='available@example.com')
    closed = create_published_job(email='closed@example.com')
    expired = create_published_job(email='expired@example.com')
    with SessionLocal() as db:
        db.get(models.JobPost, closed).published = False
        db.get(models.JobPost, expired).draft = {'published_closing_date': '2000-01-01'}
        db.commit()
    with TestClient(app) as client:
        candidate, headers = guest(client)
        path = f"/api/chats/{candidate['id']}"
        examples = client.get(path + '/recommendations', headers=headers).json()
        assert [item['job']['id'] for item in examples] == [available]
        assert examples[0]['available_example'] and not examples[0]['recommended']
        reply = client.post(path + '/messages', headers=headers, json={'content': 'Hello'}).json()
        assert reply['recommendations'][0]['available_example']
        with SessionLocal() as db:
            db.get(models.JobPost, available).published = False
            db.commit()
        assert client.get(path + '/recommendations', headers=headers).json() == []


def test_discovery_matches_confirmed_targets_despite_generic_template_descriptions():
    requirements = {
        'skills': {'type': 'text', 'target': 'circuit design', 'weight': .85,
                   'description': 'The practical skills needed for this role.'},
        'working_arrangement': {'type': 'text', 'target': 'on-site', 'weight': .5,
                                'description': 'Remote, hybrid, or on-site work.'},
    }
    profile = {'experience': {'value': 'three years', 'evidence': 'Three years of circuit design experience'},
               'working_arrangement': {'value': 'on-site', 'evidence': 'I can work on-site'}}
    result = match_profiles(profile, requirements)
    assert is_recommended(result)
    assert result['criteria']['working_arrangement']['score'] == .95
    assert result['criteria']['skills']['score'] == .75
    # Related discovery text supports a suggestion, never a fabricated direct answer.
    assert result['criteria']['skills']['gap'] == 'missing'
    assert result['criteria']['skills']['evidence'] == ''
    profile['experience']['evidence'] = 'Three years of cleaning experience'
    assert match_profiles(profile, requirements)['criteria']['skills']['score'] == 0
