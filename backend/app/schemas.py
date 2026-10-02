import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .services.criteria import normalize_target_profile


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
    job_id: int = Field(gt=0)


class UserOut(ORMModel):
    id: int
    email: str
    role: Literal["candidate", "recruiter"]


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserOut


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

    _clean_content = field_validator("content")(clean_message_text)


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

    _normalize_target_profile = field_validator("target_profile", mode="before")(
        normalize_target_profile
    )


class CriterionScoreOut(BaseModel):
    score: float
    weight: float
    reason: str


class RecommendationOut(BaseModel):
    job: JobOut
    match_score: float
    explanation: str
    criteria: dict[str, CriterionScoreOut]


class ChatSummary(ORMModel):
    id: int
    intent: str | None
    status: str
    workspace_title: str
    target_job_id: int | None = None
    created_at: datetime


class ChatOut(ChatSummary):
    profile: dict
    messages: list[MessageOut]
    job_post: JobOut | None = None
    target_job: JobOut | None = None
    can_publish: bool = False


class MessageResponse(BaseModel):
    chat: ChatOut
    assistant_message: MessageOut
    recommendations: list[RecommendationOut] = []


class ApplyRequest(BaseModel):
    candidate_chat_id: int
    candidate_name: str = Field(min_length=2, max_length=100)
    candidate_location: str = Field(min_length=2, max_length=100)
    preferred_contact: str = Field(min_length=3, max_length=320)
    consent_to_share: Literal[True]

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


class FeedbackCreate(BaseModel):
    kind: Literal["candidate", "recruiter"]
    context_id: int = Field(gt=0)
    useful: bool
