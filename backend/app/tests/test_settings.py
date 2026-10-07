from urllib.parse import quote

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
        "admin_email": "ops@jobtalk.co.za",
        "smtp_host": "smtp.provider.co.za",
        "smtp_port": 587,
        "smtp_user": "jobtalk-sender",
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
    assert settings.api_docs_enabled is False


def test_development_keeps_api_docs_and_retention_is_bounded():
    settings = Settings(_env_file=None, app_env="development")
    assert settings.api_docs_enabled is True

    with pytest.raises(ValidationError):
        Settings(_env_file=None, demo_data_retention_days=31)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("public_origin", "http://jobs.jobtalk.co.za"),
        ("session_token_pepper", "too-short"),
        ("session_token_pepper", "replace-with-at-least-32-random-characters"),
        ("database_url", "postgresql+psycopg://job_talk:postgres@postgres:5432/job_talk"),
        ("app_domain", "jobs.example.com"),
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


def test_existing_database_password_has_no_app_owned_minimum_length():
    credential = "a7!mP2$q"
    settings = production_settings(
        database_url=f"postgresql+psycopg://job_talk:{quote(credential, safe='')}@postgres:5432/job_talk",
        postgres_password=credential,
    )
    assert settings.postgres_password == credential


@pytest.mark.parametrize("credential", ["", "   ", "postgres", "password", "replace-with-database-password"])
def test_database_still_rejects_missing_or_placeholder_credentials(credential):
    with pytest.raises(ValidationError, match="database password must be a non-empty, non-placeholder"):
        production_settings(
            database_url=f"postgresql+psycopg://job_talk:{quote(credential, safe='')}@postgres:5432/job_talk",
            postgres_password=credential,
        )


def test_smtp_provider_password_has_no_app_owned_minimum_length():
    credential = "a7!mP2$q"
    settings = production_settings(smtp_password=credential)
    assert settings.smtp_password == credential


@pytest.mark.parametrize("credential", ["", "   ", "password", "change-me", "replace-with-smtp-password"])
def test_smtp_still_rejects_missing_or_placeholder_credentials(credential):
    with pytest.raises(ValidationError, match="SMTP"):
        production_settings(smtp_password=credential)


def test_settings_errors_do_not_echo_credentials():
    credential = "provider-private-credential"
    with pytest.raises(ValidationError) as exc:
        production_settings(smtp_password=credential, session_token_pepper="short")
    assert credential not in str(exc.value)
    assert "input_value" not in str(exc.value)


def test_openai_provider_requires_a_server_side_api_key_in_production():
    with pytest.raises(ValidationError, match="OPENAI_API_KEY is required"):
        production_settings(ai_provider="openai", openai_api_key="")

    settings = production_settings(
        ai_provider="openai", openai_api_key="sk-production-secret"
    )
    assert settings.openai_api_key.get_secret_value() == "sk-production-secret"
