from copy import deepcopy
from typing import TypedDict

from .. import models


MAX_CONTEXT_MESSAGES = 12


class ContextMessage(TypedDict):
    role: str
    content: str


class ContextJob(TypedDict):
    id: int
    title: str
    criteria: dict


class ChatContext(TypedDict):
    chat_id: int
    job: ContextJob | None
    draft: dict
    messages: list[ContextMessage]


def build_chat_context(
    chat: models.Chat, message_limit: int = MAX_CONTEXT_MESSAGES
) -> ChatContext:
    """Build the complete bounded context for one already-authorized chat."""
    if message_limit < 1:
        raise ValueError("message_limit must be positive")
    job = chat.target_job if chat.intent == "candidate" else chat.job_post
    return {
        "chat_id": chat.id,
        "job": (
            {
                "id": job.id,
                "title": job.title,
                "criteria": deepcopy(job.target_profile or {}),
            }
            if job
            else None
        ),
        "draft": deepcopy(chat.profile or {}),
        "messages": [
            {"role": message.sender, "content": message.content}
            for message in chat.messages[-message_limit:]
        ],
    }
