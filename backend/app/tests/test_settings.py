import pytest
from pydantic import ValidationError

from app.settings import Settings


PRODUCTION_PASSWORD = "database-secret-2026-long-value"


def production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "app_domain": "jobs.jobtalk.co.za",
        "public_origin": "https://jobs.jobtalk.co.za",
        "allowed_hosts": "jobs.jobtalk.co.za",
        "cors_origins": "https://jobs.jobtalk.co.za",
        "forwarded_allow_ips": "127.0.0.1",
        "tls_email": "ops@jobtalk.co.za",
        "smtp_host": "smtp.provider.co.za",
        "smtp_port": 587,
        "smtp_username": "jobtalk-sender",
        "smtp_password": "smtp-secret-2026-long-value",
        "email_from": "login@jobtalk.co.za",
        "database_url": (
            "postgresql+psycopg://job_talk:"
            f"{PRODUCTION_PASSWORD}@postgres:5432/job_talk"
        ),
        "postgres_password": PRODUCTION_PASSWORD,
        "session_token_pepper": "session-token-pepper-2026-long-random-value",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_production_settings_are_parsed():
    settings = production_settings(
        allowed_hosts="jobs.jobtalk.co.za,localhost",
        cors_origins="https://jobs.jobtalk.co.za,https://admin.jobtalk.co.za/",
    )

    assert settings.allowed_host_list == ["jobs.jobtalk.co.za", "localhost"]
    assert settings.cors_origin_list == [
        "https://jobs.jobtalk.co.za",
        "https://admin.jobtalk.co.za",
    ]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("public_origin", "http://jobs.jobtalk.co.za"),
        ("session_token_pepper", "too-short"),
        ("session_token_pepper", "replace-with-at-least-32-random-characters"),
        ("database_url", "postgresql+psycopg://job_talk:postgres@postgres:5432/job_talk"),
        ("app_domain", "jobs.example.com"),
        ("tls_email", "ops@example.com"),
        ("smtp_password", "replace-with-a-strong-smtp-password"),
        ("email_from", "login@example.com"),
    ],
)
def test_unsafe_production_settings_are_rejected(name, value):
    with pytest.raises(ValidationError):
        production_settings(**{name: value})


def test_database_password_values_must_match():
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD must match"):
        production_settings(postgres_password="different-database-secret-value")
