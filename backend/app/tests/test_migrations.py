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
    "job_posts",
    "messages",
    "recruiter_login_codes",
    "users",
}


def upgrade_database(monkeypatch, database_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    get_settings.cache_clear()


def test_migrations_create_fresh_schema(monkeypatch, tmp_path):
    database_path = tmp_path / "fresh.db"
    upgrade_database(monkeypatch, database_path)

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260929_02"
    engine.dispose()


def test_initial_migration_adopts_existing_schema(monkeypatch, tmp_path):
    database_path = tmp_path / "existing.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "20260929_01")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM alembic_version"))
    engine.dispose()
    command.upgrade(config, "head")
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260929_02"
    engine.dispose()
