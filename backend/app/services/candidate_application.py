"""Candidate statements mapped to the selected job's immutable criteria."""

import math
import re
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .criteria import NUMBER_WORDS, normalize_target_profile
from .conversation import (
    _criterion_denied, _experience_scope_conflicts, _supports_expected_criterion,
    update_candidate_profile,
)


class CandidateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    value: str | float | bool | None
    state: Literal["captured", "needs_clarification", "gap"]
    evidence: str
    source_quote: str


def _supported_wording(proposed: str, source: str) -> str:
    """Keep readable extraction, falling back to the quote if new facts appear."""
    words = lambda value: {word.rstrip("s") for word in re.findall(r"[a-z0-9+#]+", value.casefold())}
    connectors = {"candidate", "report", "reported", "ha", "have", "the", "a", "an", "with", "of", "in", "on", "and", "to", "for", "their"}
    if words(proposed) - words(source) - connectors:
        return source.strip()[:500]
    return proposed.strip()


def answer_state(answer: dict, requirement: dict) -> str:
    if answer.get("assessment") == "gap":
        return "gap"
    if not answer.get("evidence"):
        return "unanswered"
    if answer.get("state") == "needs_clarification":
        return "needs_clarification"
    if requirement.get("type") == "number" and not isinstance(answer.get("value"), (int, float)):
        return "needs_clarification"
    return "captured"


def application_fields(profile: dict, criteria: dict) -> list[dict]:
    return [
        {**requirement, "state": answer_state(profile.get(key, {}), requirement),
         "value": profile.get(key, {}).get("value"),
         "evidence": profile.get(key, {}).get("evidence", "")}
        for key, requirement in normalize_target_profile(criteria).items()
    ]


def apply_candidate_updates(profile: dict, criteria: dict | None, updates: list[CandidateUpdate],
                            current_text: str, earlier_user_texts: list[str], expected: str | None = None) -> dict:
    """Accept source-backed values; never let the model change job criteria or scores."""
    result = deepcopy(profile)
    requirements = normalize_target_profile(criteria) if criteria is not None else None
    normalize = lambda value: " ".join(value.casefold().split())
    current = normalize(current_text)
    if re.fullmatch(r"(?:yes|ok(?:ay)?|that['’]?s fine|fine|sure|sounds good)[.! ]*", current):
        return result
    history = [normalize(text) for text in earlier_user_texts]
    for update in updates[:24]:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", update.key) or update.key in {"candidate_details", "consent"}:
            continue
        if requirements is not None and update.key not in requirements:
            continue
        source = normalize(update.source_quote)
        if not source or len(source) > 1600:
            continue
        if source not in current:
            # Reuse an unanswered field from this chat, never overwrite a later correction.
            if result.get(update.key, {}).get("evidence") or not any(source in text for text in history):
                continue
        requirement = (requirements or {}).get(update.key, {})
        if update.key == "experience" and _experience_scope_conflicts(update.source_quote, requirement):
            continue
        related = _supports_expected_criterion(update.source_quote, update.key, requirement)
        label = requirement.get("label") or update.label
        named = bool(label.strip()) and (label.casefold() in source or update.key.replace("_", " ") in source)
        if not related and not named and update.key != expected:
            continue
        if not 4 <= len(update.evidence.strip()) <= 500:
            continue
        source_numbers = set(re.findall(r"\d+", source))
        source_numbers.update(str(value) for word, value in NUMBER_WORDS.items() if re.search(r"\b" + word + r"\b", source))
        if not set(re.findall(r"\d+", update.evidence)).issubset(source_numbers):
            continue
        value = update.value
        if update.state == "gap":
            explicit_gap = _criterion_denied(update.source_quote, update.key, requirement)
            if not explicit_gap and not (update.key == expected and re.search(r"\b(?:no|none|don't|cannot|can't|haven't|never)\b", source)):
                continue
            value = None
        elif update.state == "captured":
            if _criterion_denied(update.source_quote, update.key, requirement):
                continue
            kind = requirement.get("type")
            if kind == "number" or (kind is None and isinstance(value, (int, float)) and not isinstance(value, bool)):
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100000:
                    continue
                numbers = {float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", source)}
                numbers.update(v for k, v in NUMBER_WORDS.items() if re.search(r"\b" + k + r"\b", source))
                if value not in numbers:
                    continue
            elif kind == "skill":
                if value is not True or _criterion_denied(update.source_quote, update.key, requirement):
                    continue
            elif kind == "text" and not isinstance(value, str):
                continue
            elif not isinstance(value, (str, bool)) or (isinstance(value, str) and not 1 <= len(value.strip()) <= 500):
                continue
            if isinstance(value, str) and not set(re.findall(r"\d+", value)).issubset(source_numbers):
                continue
        else:
            value = None
        if isinstance(value, str):
            value = _supported_wording(value, update.source_quote)
        result[update.key] = {
            "criterion_key": update.key, "value": value,
            "evidence": ("Reported gap: " + update.source_quote.strip()[:470]) if update.state == "gap"
            else _supported_wording(update.evidence, update.source_quote),
            "source_quote": update.source_quote.strip(), "state": update.state,
            "assessment": "gap" if update.state == "gap" else "claimed",
        }
    return result


def reuse_discovery_answers(messages: list, criteria: dict) -> dict:
    """Replay only this guest's statements against their explicitly selected role."""
    profile = {}
    for message in messages:
        if message.sender == "user":
            profile = update_candidate_profile(profile, message.content, criteria)
    return {key: value for key, value in profile.items() if key in criteria}
