"""Select the disposable database before any test imports application modules."""

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_job_talk.db"
os.environ["AI_PROVIDER"] = "mock"
