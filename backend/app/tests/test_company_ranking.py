from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.services.matching import match_profiles, with_comparison_scores
from app.services.job_templates import new_job_draft, finish_draft, draft_can_publish, remove_draft_field
from app.tests.test_flow import app, authenticate, setup_function, create_published_job, application_payload, SessionLocal, models
from app.tests.test_application_editor import guest
from app.tests.test_live_job_edits import publish_ready_job


CRITERIA = {
    'experience': {'type': 'number', 'target': 2, 'unit': 'years', 'weight': .8, 'description': 'Two years of coding experience'},
    'python': {'type': 'skill', 'target': True, 'weight': .8, 'description': 'Can build Python APIs'},
}


def profile(years):
    return {'experience': {'value': years, 'evidence': f'{years} years of coding experience', 'state': 'captured'},
            'python': {'value': True, 'evidence': 'Built Python APIs', 'state': 'captured'}}


def test_excess_experience_is_visible_and_ranked_before_display_cap():
    ordinary = match_profiles(profile(2), CRITERIA)
    senior = match_profiles(profile(4), CRITERIA)
    assert senior['criteria']['experience']['comparison_score'] == 2
    assert senior['criteria']['experience']['score'] == 1
    assert senior['ranking_score'] > ordinary['ranking_score']
    assert senior['overall_score'] == 1
    assert ordinary['overall_score'] <= 1
    snapshot = deepcopy(senior)
    assert with_comparison_scores(senior) == snapshot
    legacy = deepcopy(senior)
    legacy['overall_score'] = .77
    assert with_comparison_scores(legacy)['overall_score'] == .77
    assert senior == snapshot


@pytest.mark.parametrize('change', [
    {'score': 0}, {'score': .5}, {'gap': 'reported'}, {'gap': 'missing'},
    {'evidence': ''}, {'target_value': 0}, {'candidate_value': True},
    {'candidate_value': float('nan')}, {'type': 'text'},
])
def test_missing_partial_or_non_numeric_evidence_cannot_earn_excess_credit(change):
    field = {'type': 'number', 'candidate_value': 10, 'target_value': 2,
             'score': 1, 'weight': 1, 'evidence': 'Ten years of coding', 'gap': None}
    field.update(change)
    result = with_comparison_scores({'criteria': {'experience': field}, 'overall_score': .4})
    assert result['criteria']['experience']['comparison_score'] <= 1
    assert result['overall_score'] == .4


def test_company_details_required_non_scoring_and_published_explicitly():
    empty = finish_draft(new_job_draft('generic-role'))
    assert not draft_can_publish(empty)
    with pytest.raises(ValueError):
        remove_draft_field(empty, 'company_name')
    _, headers = authenticate('company-owner@example.com', 'recruiter')
    with TestClient(app) as client:
        initial = client.post('/api/chats', headers=headers, json={'template_id': 'generic-role'}).json()
        assert 'Which company' in initial['messages'][0]['content']
        chat, published = publish_ready_job(client, headers)
        assert published['company_name'] == 'Example Works'
        assert published['company_location'] == 'Durban'
        assert published['target_profile']['location']['target'] == 'Cape Town'
        assert not {'company_name', 'company_location'} & published['target_profile'].keys()
        path = f"/api/chats/{chat['id']}"
        response = client.put(path + '/draft/field', headers=headers,
                              json={'key': 'company_name', 'label': 'Company name', 'value': 'New Example Works'})
        assert response.status_code == 200, response.text
        assert response.json()['chat']['has_unpublished_changes']
        url = f"/api/public/jobs/{published['id']}"
        assert client.get(url).json()['company_name'] == 'Example Works'
        saved = client.post(f"/api/jobs/{published['id']}/publish", headers=headers).json()
        assert saved['company_name'] == 'New Example Works'
        assert saved['criteria_version'] == published['criteria_version']
        assert client.get(url).json()['company_name'] == 'New Example Works'
        candidate, _ = guest(client, published['id'])
        assert candidate['target_job']['company_name'] == 'New Example Works'
        assert not {'company_name', 'company_location'} & {f['key'] for f in candidate['application_fields']}
        from app.services.context import build_chat_context
        from app.services.ai import _provider_input
        import json
        with SessionLocal() as db:
            context = build_chat_context(db.get(models.Chat, candidate['id']))
        model_input = json.loads(_provider_input(context, 'candidate', 'Who is hiring?', 'Review the job.'))
        assert model_input['selected_job']['company_name'] == 'New Example Works'
        assert model_input['selected_job']['company_location'] == 'Durban'


def test_recruiter_order_uses_uncapped_score_and_does_not_rewrite_snapshots():
    job_id = create_published_job(email='ranking-owner@example.com', target_profile=CRITERIA)
    from app.auth import issue_session
    with SessionLocal() as db:
        owner = db.get(models.JobPost, job_id).chat.user
        headers = {'Authorization': 'Bearer ' + issue_session(db, owner).access_token}
    with TestClient(app) as client:
        for years in (2, 4, 6):
            chat, guest_headers = guest(client, job_id)
            with SessionLocal() as db:
                db.get(models.Chat, chat['id']).profile = profile(years)
                db.commit()
            response = client.post(f'/api/jobs/{job_id}/apply', headers=guest_headers,
                                   json=application_payload(chat['id'], name=f'Demo {years}'))
            assert response.status_code == 201
        with SessionLocal() as db:
            original = {a.id: deepcopy(a.match_result) for a in db.query(models.Application).all()}
        items = client.get(f'/api/applications?job_id={job_id}', headers=headers).json()
        assert [a['candidate_profile']['candidate_details']['name'] for a in items] == ['Demo 6', 'Demo 4', 'Demo 2']
        assert all(a['match_result']['overall_score'] <= 1 for a in items)
        assert items[0]['match_result']['criteria']['experience']['comparison_score'] == 3
        with SessionLocal() as db:
            assert {a.id: a.match_result for a in db.query(models.Application).all()} == original
