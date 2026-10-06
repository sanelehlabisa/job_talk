from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app import recruiters, seed_jobs
from app.tests.test_flow import models, SessionLocal, setup_function


def test_local_seed_is_repeatable_and_creates_no_jobs_or_tokens(monkeypatch):
    monkeypatch.setattr(recruiters, "get_settings", lambda: SimpleNamespace(app_env="development"))
    assert recruiters.seed_recruiter(quiet=True) is True
    assert recruiters.seed_recruiter(quiet=True) is False
    with SessionLocal() as db:
        user = db.scalar(select(models.User))
        assert (user.email, user.role, user.approval_status) == (
            "recruiter@example.com", "recruiter", "approved")
        assert db.scalar(select(func.count()).select_from(models.User)) == 1
        for model in (models.JobPost, models.Chat, models.AuthSession, models.RecruiterLoginCode):
            assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_seed_preserves_existing_approval_and_records(monkeypatch, status):
    monkeypatch.setattr(recruiters, "get_settings", lambda: SimpleNamespace(app_env="development"))
    with SessionLocal() as db:
        user = models.User(email="recruiter@example.com", role="recruiter", approval_status=status)
        db.add(user)
        db.flush()
        chat = models.Chat(user_id=user.id, intent="employer")
        db.add(chat)
        db.flush()
        db.add(models.JobPost(user_id=user.id, chat_id=chat.id, title="Keep my real draft"))
        db.commit()
    assert recruiters.seed_recruiter(quiet=True) is False
    with SessionLocal() as db:
        assert db.scalar(select(models.User)).approval_status == status
        assert db.scalar(select(models.JobPost)).title == "Keep my real draft"


def test_explicit_production_seed_uses_admin_and_still_requires_login(monkeypatch):
    monkeypatch.setattr(recruiters, "get_settings", lambda: SimpleNamespace(
        app_env="production", admin_email="owner@example.com"))
    assert recruiters.seed_recruiter(quiet=True) is True
    with SessionLocal() as db:
        assert db.scalar(select(models.User)).email == "owner@example.com"
        for model in (models.AuthSession, models.RecruiterLoginCode, models.JobPost):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_production_seed_needs_admin_and_cannot_create_demo_jobs(monkeypatch):
    settings = SimpleNamespace(app_env="production", admin_email=None)
    monkeypatch.setattr(recruiters, "get_settings", lambda: settings)
    monkeypatch.setattr(seed_jobs, "get_settings", lambda: settings)
    with pytest.raises(SystemExit, match="ADMIN_EMAIL"):
        recruiters.seed_recruiter(quiet=True)
    with pytest.raises(SystemExit, match="development-only"):
        seed_jobs.seed_jobs()


def test_seed_cannot_turn_a_candidate_into_a_recruiter(monkeypatch):
    monkeypatch.setattr(recruiters, "get_settings", lambda: SimpleNamespace(
        app_env="production", admin_email="candidate@example.com"))
    with SessionLocal() as db:
        db.add(models.User(email="candidate@example.com", role="candidate", approval_status="not_required"))
        db.commit()
    with pytest.raises(SystemExit, match="candidate guest"):
        recruiters.seed_recruiter(quiet=True)
