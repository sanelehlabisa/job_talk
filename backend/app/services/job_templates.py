"""Fixed starter suggestions, stored separately from a job's scoring criteria."""

import json
import math
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .job_sources import VacancySource

class DraftField(BaseModel):
    key: str
    label: str
    type: Literal["number", "skill", "text"]
    scope: Literal["metadata", "criterion"] = "criterion"
    target: str | int | float | bool | None = None
    suggestion: str | int | float | bool | None = None
    unit: str | None = None
    weight: float = Field(default=0, ge=0, le=1)
    description: str
    importance: Literal["required", "preferred", "unspecified"] = "unspecified"
    source_quote: str = ""
    state: Literal[
        "unanswered", "needs_clarification", "confirmed", "not_required"
    ] = "unanswered"


class JobDraft(BaseModel):
    template_id: str
    label: str
    description: str
    fields: list[DraftField]
    source: VacancySource | None = None


class DraftUpdate(BaseModel):
    """Model proposals contain no weights or publication permissions."""

    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    type: Literal["number", "skill", "text"]
    target: str | float | bool | None
    unit: str | None
    state: Literal["confirmed", "needs_clarification", "not_required"]
    importance: Literal["required", "preferred", "unspecified"]
    description: str
    source_quote: str


ALIASES = {
    "job_title": ("job title", "title", "role", "hire", "hiring", "need"),
    "role_description": ("description", "responsibilities", "duties", "will", "build", "repair", "maintain"),
    "working_arrangement": ("remote", "hybrid", "on-site", "onsite", "work arrangement"),
    "location": ("location", "based", "in", "anywhere", "worldwide", "restrictions"),
    "education": ("education", "degree", "qualifications", "qualification", "certificate", "certification", "diploma"),
    "experience": ("experience", "years", "project", "entry level", "entry-level"),
    "working_hours": ("hours", "shift", "weekdays", "weekends", "monday", "schedule"),
    "availability": ("start", "available", "availability", "immediately", "notice"),
    "skills": ("skills", "skill"),
    "tools": ("tools", "tool", "equipment"),
}


def _mentions(field: DraftField, text: str) -> bool:
    terms = (*ALIASES.get(field.key, ()), field.label, field.key.replace("_", " "))
    return any(re.search(r"\b" + re.escape(term) + r"\b", text, re.I) for term in terms)


def _explicit_exclusion(field: DraftField, source: str, expected: str | None) -> bool:
    if field.key == expected and re.fullmatch(r"(?:not required|not needed|none)[.! ]*", source, re.I):
        return True
    if field.key == "location" and re.search(r"\b(anywhere|worldwide|no location restrictions|unrestricted)\b", source, re.I):
        return True
    terms = (*ALIASES.get(field.key, ()), field.label, field.key.replace("_", " "))
    names = "(?:" + "|".join(re.escape(term) for term in terms) + ")"
    return bool(re.search(
        rf"\b(?:no (?:specific |prior |formal )?{names}\b|{names} (?:is |are )?not (?:required|needed)|"
        rf"(?:don't|do not) (?:need|require) (?:a |any )?{names}\b|without (?:a |any )?{names}\b)", source, re.I))


def draft_gaps(draft: dict) -> list[DraftField]:
    fields = JobDraft.model_validate(draft).fields
    gaps = [f for f in fields if f.state not in {"confirmed", "not_required"}]
    arrangement = next((f.target for f in fields if f.key == "working_arrangement"), None)
    location = next(f for f in fields if f.key == "location")
    unrestricted_location = location.state == "not_required" or re.search(
        r"\b(anywhere|worldwide|unrestricted|no location restrictions)\b",
        str(location.target or ""), re.I,
    )
    if unrestricted_location and arrangement != "remote" and location not in gaps:
        gaps.append(location)
    return gaps


def draft_profile(draft: dict) -> dict:
    return {
        f.key: {
            "key": f.key, "label": f.label, "type": f.type, "target": f.target,
            **({"unit": f.unit} if f.unit else {}), "weight": f.weight,
            "description": f.description, "source_quote": f.source_quote,
            "importance": f.importance, "confirmed": True,
            **({"optional": True} if f.importance == "preferred" else {}),
        }
        for f in JobDraft.model_validate(draft).fields
        if f.scope == "criterion" and f.state == "confirmed" and f.target is not None
    }


def draft_can_publish(draft: dict) -> bool:
    fields = {f.key: f for f in JobDraft.model_validate(draft).fields}
    return (
        not draft_gaps(draft)
        and all(fields[k].state == "confirmed" and fields[k].target
                for k in ("job_title", "role_description", "working_arrangement"))
        and any(k not in {"working_arrangement", "location", "working_hours", "availability"}
                for k in draft_profile(draft))
    )


def draft_question(draft: dict) -> str:
    gaps = draft_gaps(draft)
    if not gaps:
        if draft_can_publish(draft):
            return "Review Who you're looking for. You can correct any field in chat, then use Publish job when it is right."
        return "What is one skill, qualification, or experience requirement applicants should demonstrate?"
    field = gaps[0]
    questions = {
        "job_title": "What is the job title?",
        "role_description": "What work will this person do?",
        "working_arrangement": "Is this role remote, hybrid, or on-site?",
        "location": "Where will they work, or is remote work unrestricted by location?",
        "education": "Is a qualification required, preferred, or not needed?",
        "experience": "What relevant experience or practical example should applicants have, or is no experience required?",
        "working_hours": "What working hours or shifts apply, or are the hours unrestricted?",
        "availability": "When should they start, or is the start date flexible?",
    }
    return questions.get(field.key, f"For {field.label}, what should applicants demonstrate, and is it required, preferred, or not needed?")


def apply_draft_updates(draft: dict, updates: list[DraftUpdate], text: str) -> dict:
    """Validate grounding, types and explicit exclusions before changing a draft."""
    result = JobDraft.model_validate(draft)
    fields = {f.key: f for f in result.fields}
    gaps = draft_gaps(draft)
    expected = gaps[0].key if gaps else None
    normalized = " ".join(text.casefold().split())
    vague = r"(?:that'?s fine|that is fine|fine|ok(?:ay)?|yes|no|sure|whatever|sounds good)[.! ]*"
    if re.fullmatch(vague, normalized):
        return result.model_dump()
    for update in updates[:24]:
        source = " ".join(update.source_quote.split())
        if not source or len(source) > 1600 or source.casefold() not in normalized:
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", update.key):
            continue
        field = fields.get(update.key)
        if field is None:
            # Prefer existing labels/keys; never manufacture a duplicate criterion.
            field = next((f for f in result.fields if f.label.casefold() == update.label.casefold()), None)
        if field is None:
            if (len(result.fields) >= 24 or not 2 <= len(update.label) <= 80
                    or update.label.casefold() not in source.casefold()):
                continue
            field = DraftField(key=update.key, label=update.label, type=update.type,
                               weight=.85, description="Details not confirmed.")
        if not _mentions(field, source) and field.key != expected:
            # A title or description can be polished without repeating its label.
            if field.key not in {"job_title", "role_description"}:
                continue
        if update.state == "not_required":
            if field.key in {"job_title", "role_description", "working_arrangement"}:
                continue
            if not _explicit_exclusion(field, source, expected):
                continue
            field.target, field.unit, field.state = None, None, "not_required"
            field.importance = "unspecified"
            field.description = "Not required by the recruiter."
        else:
            target = update.target
            supporting_source = source
            if field.target == target and field.type == update.type and field.source_quote:
                supporting_source += " " + field.source_quote
            if update.state == "confirmed" or target is not None:
                if update.type == "number":
                    if (isinstance(target, bool) or not isinstance(target, (int, float))
                            or not math.isfinite(target) or not 0 <= target <= 100000):
                        continue
                    from .criteria import NUMBER_WORDS
                    numbers = {float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", supporting_source)}
                    numbers.update(v for k, v in NUMBER_WORDS.items() if re.search(r"\b" + k + r"\b", supporting_source, re.I))
                    unit_pattern = (r"years?" if (update.unit or "").casefold() in {"year", "years"}
                                    else re.escape(update.unit or ""))
                    if target not in numbers or (update.unit and not re.search(
                            rf"\b{unit_pattern}\b", supporting_source, re.I)):
                        continue
                elif update.type == "skill":
                    if target is not True:
                        continue
                elif not isinstance(target, str) or not 2 <= len(target.strip()) <= 500:
                    continue
                if field.key == "working_arrangement" and target not in {"remote", "hybrid", "on-site"}:
                    continue
                if field.scope == "metadata" and update.type != "text":
                    continue
                if field.key == "job_title" and (not isinstance(target, str) or len(target) > 200):
                    continue
                if field.key == "job_title" and target.casefold() not in source.casefold():
                    continue
            # Reject invented quantities in polished descriptions/targets.
            proposed = f"{update.description} {target if isinstance(target, str) else ''}"
            if not set(re.findall(r"\d+", proposed)).issubset(set(re.findall(r"\d+", supporting_source))):
                continue
            if not 4 <= len(update.description.strip()) <= 500:
                continue
            field.type, field.target, field.unit = update.type, target, update.unit
            if update.description.casefold() not in {"required", "preferred", "optional", "essential"}:
                field.description = update.description.strip()
            field.state = update.state
            if update.importance != "unspecified":
                field.importance = update.importance
            if field.scope == "criterion":
                if update.importance == "preferred":
                    field.weight = .35
                elif update.importance == "required":
                    defaults = {f.key: f.weight for f in starter_templates()[0].fields}
                    field.weight = defaults.get(field.key, .85)
                # Skills/tools need stated importance, not an arbitrary years target.
                if field.key not in ALIASES or field.key in {"skills", "tools", "education"}:
                    if field.importance == "unspecified":
                        field.state = "needs_clarification"
        field.source_quote = source if update.state == "not_required" else supporting_source[-2000:]
        if field.key not in fields:
            result.fields.append(field)
            fields[field.key] = field
    return result.model_dump()


def fallback_draft_updates(draft: dict, text: str) -> list[DraftUpdate]:
    """Small guided parser for explicit labelled answers when the LLM is unavailable."""
    from .conversation import _importance, _location, update_employer_profile
    from .criteria import _years

    result = []
    fields = JobDraft.model_validate(draft).fields
    gaps = draft_gaps(draft)
    expected = gaps[0].key if gaps else None
    for clause in re.split(r"[;\n]|(?<=[.!?])\s+", text):
        clause = clause.strip(" .")
        if not clause:
            continue
        for field in fields:
            labelled = re.match(rf"(?:{re.escape(field.label)}|{re.escape(field.key.replace('_', ' '))})\s*:\s*(.+)", clause, re.I)
            mentioned = _mentions(field, clause)
            if not mentioned and not labelled:
                continue
            target, kind, unit = None, "text", None
            state = "confirmed"
            importance = _importance(clause) or field.importance
            exclusion = _explicit_exclusion(field, clause, expected)
            if exclusion and (mentioned or labelled):
                state = "not_required"
            elif field.key == "job_title":
                _, details = update_employer_profile({}, clause)
                target = labelled.group(1) if labelled else details.get("title")
                if not target:
                    continue
            elif field.key == "role_description":
                if not labelled and not re.search(r"\b(will|duties|responsibilities)\b", clause, re.I):
                    continue
                target = labelled.group(1) if labelled else clause
            elif field.key == "working_arrangement":
                target = next((a for a in ("remote", "hybrid", "on-site") if a in clause.lower()), None)
                if not target and "onsite" in clause.lower():
                    target = "on-site"
                if not target:
                    continue
            elif field.key == "location":
                target = labelled.group(1) if labelled else _location(clause)
                if not target and re.search(r"\b(anywhere|worldwide|unrestricted)\b", clause, re.I):
                    target = clause
                if not target:
                    continue
            else:
                years = _years(clause)
                if years is not None and (field.key == "experience" or field.key not in ALIASES):
                    kind, target, unit = "number", years, "years"
                elif field.type == "skill":
                    kind, target = "skill", True
                else:
                    target = labelled.group(1) if labelled else clause
            result.append(DraftUpdate(
                key=field.key, label=field.label, type=kind, target=target, unit=unit,
                state=state, importance=importance, description=clause[:500], source_quote=clause,
            ))
    # Short explicit exclusions resolve only the field currently being asked.
    if re.fullmatch(r"(?:not required|not needed|none)[.! ]*", text, re.I) and expected:
        field = next(f for f in fields if f.key == expected)
        result.append(DraftUpdate(key=field.key, label=field.label, type=field.type,
                                 target=None, unit=None, state="not_required",
                                 importance="unspecified", description="Not required.", source_quote=text))
    if not result and expected:
        field = next(f for f in fields if f.key == expected)
        importance = _importance(text)
        years = _years(text)
        if importance and re.fullmatch(r"(?:required|preferred|optional|essential|nice to have)[.! ]*", text, re.I):
            result.append(DraftUpdate(key=field.key, label=field.label, type=field.type,
                                     target=field.target, unit=field.unit,
                                     state="confirmed" if field.target is not None else "needs_clarification",
                                     importance=importance, description=text, source_quote=text))
        elif years is not None and re.fullmatch(r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) years?[.! ]*", text, re.I):
            result.append(DraftUpdate(key=field.key, label=field.label, type="number", target=years,
                                     unit="years" if "years" in text.lower() else "year", state="confirmed",
                                     importance=field.importance, description=text, source_quote=text))
    return result


def starter_templates() -> list[JobDraft]:
    catalogue = json.loads(
        (Path(__file__).resolve().parents[1] / "job_templates.json").read_text(
            encoding="utf-8"
        )
    )
    templates = []
    for template in catalogue["templates"]:
        fields = {
            key: {**field, **template["fields"].get(key, {})}
            for key, field in catalogue["fields"].items()
        }
        fields.update(
            (key, field) for key, field in template["fields"].items()
            if key not in fields
        )
        templates.append(JobDraft(
            template_id=template["id"],
            label=template["label"],
            description=template["description"],
            fields=[DraftField(key=key, **field) for key, field in fields.items()],
        ))
    return templates


def new_job_draft(template_id: str) -> dict:
    for template in starter_templates():
        if template.template_id == template_id:
            return template.model_dump()
    raise ValueError("Job template not found")
