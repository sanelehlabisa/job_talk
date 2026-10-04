import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .services.criteria import normalize_target_profile
from .services.job_templates import JobDraft
from .services.job_sources import VacancySource, VacancySourcePublic


def clean_user_text(value: str, allowed_controls: str = "") -> str:
    cleaned = value.strip()
    if any(
        unicodedata.category(character).startswith("C")
        and character not in allowed_controls
        for character in cleaned
    ):
        raise ValueError("Control characters are not allowed")
    return cleaned


def clean_message_text(value: str) -> str:
    return clean_user_text(value, "\n\r\t")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RecruiterEmailRequest(BaseModel):
    email: EmailStr


class RecruiterCodeVerifyRequest(RecruiterEmailRequest):
    code: str = Field(pattern=r"^\d{6}$")


class MessageResponseStatus(BaseModel):
    message: str


class GuestSessionRequest(BaseModel):
    job_id: int | None = Field(default=None, gt=0)


class ChatCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str | None = Field(default=None, min_length=1, max_length=60)
    source: VacancySource | None = None


class SelectJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: int = Field(gt=0)


class UserOut(ORMModel):
    id: int
    email: str
    role: Literal["candidate", "recruiter"]
    is_admin: bool = False


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserOut


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

    _clean_content = field_validator("content")(clean_message_text)


class DraftFieldEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,59}$")
    label: str = Field(min_length=2, max_length=80)
    value: str = Field(min_length=2, max_length=500)

    _clean_fields = field_validator("label", "value")(clean_user_text)


class ApplicationFieldEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,59}$")
    value: str = Field(max_length=500)
    criteria_version: str = Field(pattern=r"^[a-f0-9]{64}$")

    _clean_value = field_validator("value")(clean_user_text)


class MessageOut(ORMModel):
    id: int
    sender: Literal["user", "assistant"]
    content: str
    created_at: datetime


class JobOut(ORMModel):
    id: int
    title: str
    description: str
    target_profile: dict
    published: bool
    company_name: str | None = None
    company_location: str | None = None
    source: VacancySourcePublic | None = None
    closing_date: str | None = None
    criteria_version: str

    _normalize_target_profile = field_validator("target_profile", mode="before")(
        normalize_target_profile
    )


class CriterionScoreOut(BaseModel):
    label: str
    type: Literal["number", "skill", "text"]
    unit: str | None = None
    candidate_value: str | int | float | bool | None = None
    target_value: str | int | float | bool | None = None
    score: float
    comparison_score: float = 0
    weight: float
    evidence: str
    reason: str
    gap: Literal["reported", "missing"] | None = None
    rating_source: Literal["gemini", "rules"] = "rules"


class RecommendationOut(BaseModel):
    job: JobOut
    match_score: float
    rating_source: Literal["gemini", "rules"] = "rules"
    recommended: bool
    explanation: str
    criteria: dict[str, CriterionScoreOut]
    available_example: bool = False


class ChatSummary(ORMModel):
    id: int
    intent: str | None
    status: str
    workspace_title: str
    target_job_id: int | None = None
    created_at: datetime
    recruiter_email: str | None = None


class ChatOut(ChatSummary):
    profile: dict
    messages: list[MessageOut]
    job_post: JobOut | None = None
    target_job: JobOut | None = None
    can_publish: bool = False
    has_unpublished_changes: bool = False
    job_draft: JobDraft | None = None
    application_fields: list[dict] = Field(default_factory=list)


class MessageResponse(BaseModel):
    chat: ChatOut
    assistant_message: MessageOut
    recommendations: list[RecommendationOut] = []


class DraftEditResponse(BaseModel):
    chat: ChatOut
    notice: str


class ApplyRequest(BaseModel):
    candidate_chat_id: int
    candidate_name: str = Field(min_length=2, max_length=100)
    candidate_location: str = Field(min_length=2, max_length=100)
    preferred_contact: str = Field(min_length=3, max_length=320)
    consent_to_share: Literal[True]
    criteria_version: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    _clean_candidate_fields = field_validator(
        "candidate_name", "candidate_location", "preferred_contact"
    )(clean_user_text)


class ApplicationOut(ORMModel):
    id: int
    candidate_chat_id: int
    job_post_id: int
    candidate_profile: dict
    match_result: dict
    submitted: bool
    created_at: datetime
    earlier_requirements: bool = False

    @model_validator(mode="after")
    def include_comparison(self):
        from .services.matching import with_comparison_scores
        self.match_result = with_comparison_scores(self.match_result)
        return self


class FeedbackCreate(BaseModel):
    kind: Literal["candidate", "recruiter"]
    context_id: int = Field(gt=0)
    useful: bool
