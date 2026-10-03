from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app import models  # noqa: F401
from app.database import Base
from app.settings import get_settings


BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPECTED_TABLES = {
    "alembic_version",
    "applications",
    "auth_sessions",
    "chats",
    "experiment_events",
    "job_posts",
    "messages",
    "recruiter_login_codes",
    "users",
}


def migration_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def upgrade_database(monkeypatch, database_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = migration_config()
    command.upgrade(config, "head")
    get_settings.cache_clear()


def test_migrations_create_fresh_schema(monkeypatch, tmp_path):
    database_path = tmp_path / "fresh.db"
    upgrade_database(monkeypatch, database_path)

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261003_05"
    assert "draft" in {column["name"] for column in inspect(engine).get_columns("job_posts")}
    engine.dispose()


def test_initial_migration_adopts_existing_schema(monkeypatch, tmp_path):
    database_path = tmp_path / "existing.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = migration_config()
    command.upgrade(config, "20260929_01")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM alembic_version"))
    engine.dispose()
    command.upgrade(config, "head")
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261003_05"
    engine.dispose()


def test_template_draft_migration_preserves_existing_job(monkeypatch, tmp_path):
    database_path = tmp_path / "legacy-job.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = migration_config()
    command.upgrade(config, "20261001_04")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, email, role, created_at) VALUES (1, 'legacy@example.com', 'recruiter', CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO chats (id, user_id, intent, status, profile, created_at) VALUES (1, 1, 'employer', 'published', '{}', CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO job_posts (id, chat_id, user_id, title, description, target_profile, published, created_at) VALUES (1, 1, 1, 'Existing job', 'Saved description', '{}', 1, CURRENT_TIMESTAMP)"))
    command.upgrade(config, "head")
    get_settings.cache_clear()
    with engine.connect() as connection:
        job = connection.execute(text("SELECT title, description, published, draft FROM job_posts WHERE id = 1")).one()
        assert tuple(job) == ("Existing job", "Saved description", 1, None)
    engine.dispose()
