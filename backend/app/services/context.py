from copy import deepcopy
from typing import NotRequired, TypedDict

from .. import models


class ContextMessage(TypedDict):
    role: str
    content: str


class ContextJob(TypedDict):
    id: int
    title: str
    criteria: dict
    company_name: NotRequired[str]
    company_location: NotRequired[str]


class ChatContext(TypedDict):
    chat_id: int
    job: ContextJob | None
    draft: dict
    messages: list[ContextMessage]
    user_message_count: NotRequired[int]
    job_draft: NotRequired[dict | None]
    form_edit: NotRequired[dict]


def build_chat_context(
    chat: models.Chat, message_limit: int | None = None
) -> ChatContext:
    """Include the entire conversation for one already-authorized chat by default."""
    if message_limit is not None and message_limit < 1:
        raise ValueError("message_limit must be positive")
    job = chat.target_job if chat.intent == "candidate" else chat.job_post
    return {
        "chat_id": chat.id,
        "job": (
            {
                "id": job.id,
                "title": job.title,
                **({"company_name": job.company_name} if job.company_name else {}),
                **({"company_location": job.company_location} if job.company_location else {}),
                "criteria": deepcopy(job.target_profile or {}),
            }
            if job
            else None
        ),
        "draft": deepcopy(chat.profile or {}),
        **({"job_draft": deepcopy({key: value for key, value in job.draft.items() if key != "source" or value is None})}
           if job and job.draft and chat.intent == "employer" else {}),
        "messages": [
            {"role": message.sender, "content": message.content}
            for message in (chat.messages if message_limit is None else chat.messages[-message_limit:])
        ],
        "user_message_count": sum(
            message.sender == "user" for message in chat.messages
        ),
    }
