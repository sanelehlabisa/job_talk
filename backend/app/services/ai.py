from collections.abc import Iterator


def _preview(text: str) -> str:
    """Show at most ten source characters: the first five and last five."""
    normalized = " ".join(text.split())
    if len(normalized) <= 10:
        return normalized
    return f"{normalized[:5]}{normalized[-5:]}"


def _mock_reply_parts(
    chat_id: int,
    intent: str | None,
    user_text: str,
    fallback: str,
    history: list[dict[str, str]],
) -> Iterator[str]:
    """Yield deterministic reply sections while the real AI is disabled."""
    yield f'"{_preview(user_text)}"'
    yield "Mock AI received your message."

    previous_user = next(
        (message["content"] for message in reversed(history) if message["role"] == "user"),
        None,
    )
    context_summary = f"Chat #{chat_id} context: {len(history)} earlier message(s)"
    if previous_user:
        context_summary += f'; previous user message "{_preview(previous_user)}".'
    else:
        context_summary += "; no previous user message."
    yield context_summary

    if intent == "candidate":
        yield "Mode: job seeker."
    elif intent == "employer":
        yield "Mode: hiring."
    else:
        yield "Mode: choosing a chat path."
    yield fallback


def generate_reply(
    chat_id: int,
    intent: str | None,
    profile: dict,
    user_text: str,
    fallback: str,
    history: list[dict[str, str]],
) -> str:
    """Return a deterministic stand-in for an eventual AI provider."""
    del profile  # Kept in the interface for a future API or local model adapter.
    return " ".join(_mock_reply_parts(chat_id, intent, user_text, fallback, history))
