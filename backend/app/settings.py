from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


WEAK_SECRET_VALUES = {
    "postgres",
    "password",
    "change-me",
    "changeme",
    "replace-me",
    "replace-with-a-strong-secret",
}


def is_weak_secret(value: str, minimum_length: int) -> bool:
    normalized = value.strip().lower()
    return (
        len(value) < minimum_length
        or normalized in WEAK_SECRET_VALUES
        or normalized.startswith(("change-", "replace-"))
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "test", "production"] = "development"
    app_domain: str = "localhost"
    public_origin: str = "http://localhost:5173"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    forwarded_allow_ips: str = "127.0.0.1"

    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_secure: bool = False
    email_from: EmailStr | None = None
    recruiter_code_ttl_minutes: int = Field(default=10, ge=5, le=30)
    recruiter_code_max_attempts: int = Field(default=5, ge=3, le=10)
    recruiter_code_request_cooldown_seconds: int = Field(default=60, ge=30, le=600)
    recruiter_code_request_max_per_hour: int = Field(default=5, ge=1, le=20)
    demo_data_retention_days: int = Field(default=30, ge=7, le=30)
    admin_email: EmailStr | None = None

    database_url: str = "sqlite:///./job_talk.db"
    postgres_password: str | None = None
    auth_session_hours: int = Field(default=24, ge=1, le=168)
    session_token_pepper: str = "dev-only-session-token-pepper"
    ai_provider: Literal["mock", "openai", "gemini"] = "mock"
    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default="gpt-4o-mini", min_length=1, max_length=100)
    gemini_api_key: SecretStr | None = None
    gemini_model: str = Field(default="gemini-3.5-flash-lite", pattern=r"^[a-z0-9][a-z0-9.-]{0,99}$")
    ai_timeout_seconds: float = Field(default=20, ge=1, le=60)
    ai_max_output_tokens: int = Field(default=3000, ge=64, le=6000)
    ai_max_calls_per_chat: int = Field(default=12, ge=1, le=50)

    @field_validator("admin_email", mode="before")
    @classmethod
    def normalize_admin_email(cls, value):
        if isinstance(value, str):
            return value.strip().lower() or None
        return value

    @property
    def allowed_host_list(self) -> list[str]:
        return [value.strip() for value in self.allowed_hosts.split(",") if value.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip().rstrip("/") for value in self.cors_origins.split(",") if value.strip()]

    @property
    def api_docs_enabled(self) -> bool:
        return self.app_env != "production"

    @model_validator(mode="after")
    def validate_production_contract(self):
        if self.app_env != "production":
            return self

        origin = urlparse(self.public_origin)
        if origin.scheme != "https" or origin.hostname != self.app_domain or origin.path not in ("", "/"):
            raise ValueError("PUBLIC_ORIGIN must be the HTTPS root of APP_DOMAIN in production")
        if self.app_domain == "example.com" or self.app_domain.endswith(".example.com"):
            raise ValueError("APP_DOMAIN must be replaced with the real production subdomain")
        if self.app_domain not in self.allowed_host_list:
            raise ValueError("ALLOWED_HOSTS must include APP_DOMAIN in production")
        if self.public_origin.rstrip("/") not in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must include PUBLIC_ORIGIN in production")
        if not self.forwarded_allow_ips.strip():
            raise ValueError("FORWARDED_ALLOW_IPS is required in production")

        if not self.smtp_host or not self.smtp_user or not self.smtp_password:
            raise ValueError("SMTP host and credentials are required in production")
        # SMTP credentials are issued by the mail provider, not by this app.
        # Reject empty/example values without imposing our own password length.
        if is_weak_secret(self.smtp_password.strip(), 1):
            raise ValueError("SMTP_PASSWORD must be a non-empty, non-placeholder provider credential")
        if self.email_from is None or str(self.email_from).lower().endswith("@example.com"):
            raise ValueError("EMAIL_FROM must be a real sender address in production")

        if is_weak_secret(self.session_token_pepper, 32):
            raise ValueError("SESSION_TOKEN_PEPPER must be a strong value of at least 32 characters")

        database = make_url(self.database_url)
        if not database.drivername.startswith("postgresql"):
            raise ValueError("Production DATABASE_URL must use PostgreSQL")
        database_password = database.password or ""
        if is_weak_secret(database_password, 16):
            raise ValueError("Production database password must be a strong value of at least 16 characters")
        if self.postgres_password and self.postgres_password != database_password:
            raise ValueError("POSTGRES_PASSWORD must match the password in DATABASE_URL")
        if self.ai_provider == "openai" and (
            self.openai_api_key is None
            or not self.openai_api_key.get_secret_value().strip()
        ):
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        if self.ai_provider == "gemini" and (
            self.gemini_api_key is None or not self.gemini_api_key.get_secret_value().strip()
        ):
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
