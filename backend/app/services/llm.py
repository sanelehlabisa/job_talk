import json
import logging
import os
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _output_text(result: dict) -> str:
    """Extract text safely from a raw Responses API result."""
    if result.get("output_text"):
        return str(result["output_text"]).strip()
    for item in result.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"]).strip()
    return ""


def generate_reply(intent: str | None, profile: dict, user_text: str, fallback: str) -> str:
    """Generate a concise reply with OpenAI, falling back when unavailable."""
    if not OPENAI_API_KEY:
        return fallback

    system_prompt = (
        "You are Job Talk, a concise and friendly recruitment assistant. "
        "The user is either finding a job or hiring. Respond naturally to their latest message. "
        "Acknowledge useful information and ask at most one relevant follow-up question. "
        "Never invent facts, scores, jobs, or application outcomes. Never reject a candidate. "
        "Do not mention JSON, extraction, models, or internal systems. Keep the response under 70 words."
    )
    context = (
        f"Chat intent: {intent or 'not established'}\n"
        f"Current structured profile: {json.dumps(profile, ensure_ascii=False)}\n"
        f"Suggested safe fallback response: {fallback}"
    )
    payload = json.dumps(
        {
            "model": OPENAI_MODEL,
            "instructions": system_prompt,
            "input": f"{context}\n\nLatest user message: {user_text}",
            "max_output_tokens": 120,
            "temperature": 0.25,
            "store": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{OPENAI_BASE_URL}/responses",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
        return _output_text(result) or fallback
    except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
        logger.warning("OpenAI unavailable; using deterministic reply: %s", exc)
        return fallback
