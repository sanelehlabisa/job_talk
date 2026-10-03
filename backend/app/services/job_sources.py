"""Manually checked vacancy metadata; no fetching or importing services."""

import unicodedata
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator


class VacancySourcePublic(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    employer: str = Field(min_length=2, max_length=160)
    checked_on: str

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value):
        parsed = urlsplit(str(TypeAdapter(HttpUrl).validate_python(value.strip())))
        if parsed.username or parsed.password:
            raise ValueError("Source links must not contain credentials")
        query = [(key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
                 if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(sorted(query)), ""))

    @field_validator("employer")
    @classmethod
    def clean_employer(cls, value):
        value = value.strip()
        if len(value) < 2 or any(unicodedata.category(c).startswith("C") for c in value):
            raise ValueError("Enter a readable employer name")
        return value

    @field_validator("checked_on")
    @classmethod
    def valid_date(cls, value):
        checked = date.fromisoformat(value)
        if checked > datetime.now(timezone.utc).date():
            raise ValueError("Date checked cannot be in the future")
        return checked.isoformat()


class VacancySource(VacancySourcePublic):
    model_config = ConfigDict(extra="forbid")
    original_text: str = Field(min_length=20, max_length=5000)

    @field_validator("original_text")
    @classmethod
    def clean_source_text(cls, value):
        value = value.strip()
        if len(value) < 20 or any(unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in value):
            raise ValueError("Paste the vacancy text (20 to 5000 characters)")
        return value
