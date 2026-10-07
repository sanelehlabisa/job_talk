"""Select the disposable database before any test imports application modules."""

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_job_talk.db"
os.environ["AI_PROVIDER"] = "mock"


@pytest.fixture(autouse=True)
def no_live_recruiter_notifications(monkeypatch):
    """Tests explicitly capture alerts; never email the configured real admin."""
    monkeypatch.setattr("app.main.send_recruiter_access_request", lambda *args: None)
