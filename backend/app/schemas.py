from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class ApplicationOut(ORMModel):
    id: int
    candidate_chat_id: int
    job_post_id: int
    candidate_profile: dict
    match_result: dict
    submitted: bool
    created_at: datetime
