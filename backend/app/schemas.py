from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr


class UserOut(ORMModel):
    id: int
    email: EmailStr


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


class RecommendationOut(BaseModel):
    job: JobOut
    match_score: float
    explanation: str


class ChatSummary(ORMModel):
    id: int
    intent: str | None
    status: str
    created_at: datetime


class ChatOut(ChatSummary):
    profile: dict
    messages: list[MessageOut]
    job_post: JobOut | None = None
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

