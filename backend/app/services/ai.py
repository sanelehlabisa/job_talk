from collections.abc import Iterator

from .context import ChatContext


def _preview(text: str) -> str:
    """Show at most ten source characters: the first five and last five."""
    normalized = " ".join(text.split())
    if len(normalized) <= 10:
        return normalized
    return f"{normalized[:5]}{normalized[-5:]}"


def _mock_reply_parts(
    context: ChatContext,
    intent: str | None,
    user_text: str,
    fallback: str,
) -> Iterator[str]:
    """Yield deterministic reply sections while the real AI is disabled."""
    history = context["messages"]
    yield f'"{_preview(user_text)}"'
    yield "Mock AI received your message."

    previous_user = next(
        (message["content"] for message in reversed(history) if message["role"] == "user"),
        None,
    )
    context_summary = f"Chat #{context['chat_id']} context: {len(history)} earlier message(s)"
    if previous_user:
        context_summary += f'; previous user message "{_preview(previous_user)}".'
    else:
        context_summary += "; no previous user message."
    if context["job"]:
        context_summary += (
            f" Selected job #{context['job']['id']}: {context['job']['title']}."
        )
    draft_fields = ", ".join(sorted(context["draft"])) or "none"
    context_summary += f" Draft fields: {draft_fields}."
    yield context_summary

    if intent == "candidate":
        yield "Mode: job seeker."
    elif intent == "employer":
        yield "Mode: hiring."
    else:
        yield "Mode: choosing a chat path."
    yield fallback


def generate_reply(
    context: ChatContext,
    intent: str | None,
    user_text: str,
    fallback: str,
) -> str:
    """Return a deterministic stand-in for an eventual AI provider."""
    return " ".join(_mock_reply_parts(context, intent, user_text, fallback))
