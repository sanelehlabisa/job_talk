"""Fixed starter suggestions, stored separately from a job's scoring criteria."""

import json
import math
import re
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .job_sources import VacancySource
from .criteria import NUMBER_WORDS

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
    removed_keys: list[str] = Field(default_factory=list)
    published_closing_date: str | None = None


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
    "working_arrangement": ("remote", "hybrid", "on-site", "onsite", "on site", "work arrangement"),
    "location": ("location", "based", "in", "anywhere", "worldwide", "restrictions"),
    "education": ("education", "degree", "qualifications", "qualification", "certificate", "certification", "diploma"),
    "experience": ("experience", "years", "project", "entry level", "entry-level"),
    "working_hours": ("hours", "shift", "weekdays", "weekends", "monday", "schedule"),
    "availability": ("start", "available", "availability", "immediately", "notice"),
    "skills": ("skills", "skill"),
    "tools": ("tools", "tool", "equipment"),
    "closing_date": ("closing date", "application deadline", "applications close", "deadline"),
}

ESSENTIAL_FIELDS = {"job_title", "role_description", "working_arrangement", "location"}


def parse_closing_date(value: str) -> str | None:
    """Explicit calendar dates only; never guess a year or an ambiguous slash date."""
    value = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", value, flags=re.I)
    patterns = ((r"\b\d{4}-\d{2}-\d{2}\b", ("%Y-%m-%d",)),
                (r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b", ("%d %B %Y", "%d %b %Y")),
                (r"\b[A-Za-z]+\s+\d{1,2},?\s+\d{4}\b", ("%B %d %Y", "%b %d %Y")))
    for pattern, formats in patterns:
        match = re.search(pattern, value)
        if match:
            for fmt in formats:
                try:
                    return datetime.strptime(match.group().replace(",", ""), fmt).date().isoformat()
                except ValueError:
                    continue
    return None


def form_field_update(draft: dict, key: str, label: str, value: str) -> DraftUpdate:
    """Keep types/weights behind a label/value form; preserve existing semantics."""
    from .conversation import _importance
    value = " ".join(value.split())
    field = next((f for f in JobDraft.model_validate(draft).fields if f.key == key), None)
    kind, target, unit = "text", value, None
    importance = _importance(value) or (field.importance if field and field.importance != "unspecified" else "required")
    state = "confirmed"
    if re.fullmatch(r"(?:not required|not needed|none)[.! ]*", value, re.I):
        state, target = "not_required", None
        source = f"{label} is not required."
    else:
        year_match = re.search(r"(?<![\w.\-])(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\+?\s+years?\b", value, re.I)
        years = (NUMBER_WORDS.get(year_match[1].lower()) if not year_match[1][0].isdigit()
                 else float(year_match[1])) if year_match else None
        if key == "closing_date":
            target = parse_closing_date(value)
            if not target:
                raise ValueError("Enter a closing date with a year, such as 2026-11-30.")
        elif (not field or field.scope != "metadata") and not informational_only(key, label, value, value) and (
                (field and field.type == "number") or (years is not None and key not in ESSENTIAL_FIELDS | {"education", "availability", "working_hours"})):
            kind = "number"
            if years is not None:
                target, unit = years, "years"
            else:
                match = re.fullmatch(r"(?:at least\s+)?(\d+(?:\.\d+)?)\s*(.*)", value, re.I)
                if not match or (match[2] and match[2].casefold() != (field.unit or "").casefold()):
                    raise ValueError("Enter an amount and its unit, such as 2 years, or clarify it in chat.")
                target, unit = float(match[1]), field.unit
                if unit and not match[2]:
                    value += f" {unit}"
        elif field and field.type == "skill":
            kind, target = "skill", True
        source = f"Form edit — {label}: {value}."
    if key in {"job_title", "role_description", "closing_date"} or (field and field.scope == "metadata"):
        importance = "unspecified"
    return DraftUpdate(key=key, label=label, type=kind, target=target, unit=unit,
                       importance=importance, state=state, description=value if len(value) >= 4 else f"{label}: {value}",
                       source_quote=source)


def informational_only(key: str, label: str, target, description: str) -> bool:
    """Personal characteristics are never inputs to automated hiring scores."""
    wording = f"{key.replace('_', ' ')} {label} {target} {description}"
    return bool(re.search(
        r"\b(age|aged|birth|gender|sex|race|racial|ethnicity|ethnic|religion|religious|"
        r"disability|disabled|marital|pregnant|pregnancy)\b|"
        r"\b(?:younger|older) than\b|\byears? old\b|"
        r"\b(?:under|over) \d+\b(?![.\d]|\s*(?:years?|months?|weeks?|days?|hours?|minutes?|percent|%|kg|cm)\b)",
        wording, re.I,
    ))


def remove_draft_field(draft: dict, key: str) -> dict:
    result = JobDraft.model_validate(draft)
    if key in ESSENTIAL_FIELDS:
        raise ValueError("Keep the role, description, work arrangement and location rules.")
    if key != "closing_date" and not any(field.key == key for field in result.fields):
        raise ValueError("Field not found.")
    result.fields = [field for field in result.fields if field.key != key]
    result.removed_keys = list(dict.fromkeys([*result.removed_keys, key]))
    return result.model_dump()


def finish_draft(draft: dict) -> dict:
    """Drop only blank optional suggestions, never partially answered requirements."""
    for field in JobDraft.model_validate(draft).fields:
        if field.key not in ESSENTIAL_FIELDS and field.state == "unanswered" and field.target is None:
            draft = remove_draft_field(draft, field.key)
    if not any(f["key"] == "closing_date" for f in draft["fields"]):
        draft = remove_draft_field(draft, "closing_date")
    return draft


def _mentions(field: DraftField, text: str) -> bool:
    terms = (*ALIASES.get(field.key, ()), field.label, field.key.replace("_", " "))
    return any(re.search(r"\b" + re.escape(term) + r"\b", text, re.I) for term in terms)


def _explicit_exclusion(field: DraftField, source: str, expected: str | None) -> bool:
    if field.key == expected and re.fullmatch(r"(?:not required|not needed|none)[.! ]*", source, re.I):
        return True
    if field.key == "location" and re.search(r"\b(anywhere|worldwide|no location restrictions|unrestricted)\b", source, re.I):
        return True
    terms = (*ALIASES.get(field.key, ()), field.label, field.key.replace("_", " "))
    # Accept a small spelling error in an explicit exclusion, e.g. "no experince".
    vocabulary = {word.casefold() for term in terms for word in term.split() if len(word) >= 5}
    def correct_word(match):
        word = match.group().casefold()
        close = get_close_matches(word, vocabulary, n=1, cutoff=.8) if len(word) >= 5 else []
        return close[0] if close else word
    source = re.sub(r"[a-zA-Z]+", correct_word, source)
    names = "(?:" + "|".join(re.escape(term) for term in terms) + ")"
    if re.search(rf"\b(?:remove|delete|drop) (?:the )?{names}\b", source, re.I):
        return not re.search(r"\b(?:not|don't|do not|never)\b", source, re.I)
    return bool(re.search(
        rf"\b(?:no (?:specific |prior |formal )?{names}\b|{names} (?:is |are )?not (?:required|needed)|"
        rf"(?:don't|do not) (?:need|require) (?:a |any )?{names}\b|without (?:a |any )?{names}\b)", source, re.I))


def draft_gaps(draft: dict) -> list[DraftField]:
    fields = JobDraft.model_validate(draft).fields
    gaps = [f for f in fields if f.state not in {"confirmed", "not_required"}
            and not (f.key == "closing_date" and f.state == "unanswered")]
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
        and not informational_only(f.key, f.label, f.target, f.description)
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
        "closing_date": "What is the closing date, including the year, or should we leave it out?",
    }
    return questions.get(field.key, f"For {field.label}, what should applicants demonstrate, and is it required, preferred, or not needed?")


def _title_supported(title: str, source: str) -> bool:
    """Permit spelling repairs, but not extra qualifications or seniority in titles."""
    words = re.findall(r"[a-z0-9]+", source.casefold())
    for word in re.findall(r"[a-z0-9]+", title.casefold()):
        if word not in words and not (len(word) >= 5 and get_close_matches(word, words, n=1, cutoff=.8)):
            return False
    return True


def _new_label_supported(label: str, source: str) -> bool:
    # Allow paraphrasing/spelling repairs without inventing a wholly unrelated skill.
    generic = {"required", "preferred", "requirement", "requirements", "ability", "knowledge",
               "skill", "skills", "experience", "familiarity", "proficiency", "restriction",
               "restrictions", "minimum", "maximum", "level", "limit"}
    words = re.findall(r"[a-z0-9+#]+", source.casefold())
    label_words = re.findall(r"[a-z0-9+#]+", label.casefold())
    meaningful_words = [word for word in label_words if word not in generic] or label_words
    return any(word in words or (len(word) >= 5 and get_close_matches(word, words, n=1, cutoff=.75))
               for word in meaningful_words)


def apply_draft_updates(draft: dict, updates: list[DraftUpdate], text: str,
                        earlier_user_texts: list[str] | None = None) -> dict:
    """Validate grounding, types and explicit exclusions before changing a draft."""
    result = JobDraft.model_validate(draft)
    fields = {f.key: f for f in result.fields}
    gaps = draft_gaps(draft)
    expected = gaps[0].key if gaps else None
    normalized = " ".join(text.casefold().split())
    history = [" ".join(message.casefold().split()) for message in (earlier_user_texts or [])]
    vague = r"(?:that'?s fine|that is fine|fine|ok(?:ay)?|yes|no|sure|whatever|sounds good)[.! ]*"
    if re.fullmatch(vague, normalized):
        return result.model_dump()
    for update in updates[:24]:
        source = " ".join(update.source_quote.split())
        if not source or len(source) > 1600:
            continue
        from_history = source.casefold() not in normalized
        if from_history and not any(source.casefold() in message for message in history):
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", update.key):
            continue
        field = fields.get(update.key)
        if from_history and update.key in result.removed_keys:
            continue
        if field is None:
            # Prefer existing labels/keys; never manufacture a duplicate criterion.
            field = next((f for f in result.fields if f.label.casefold() == update.label.casefold()), None)
        if from_history and field is None and result.removed_keys:
            continue  # A removed criterion must not return under a new synonym/key.
        if from_history and field is not None and (field.state != "unanswered" or field.source_quote):
            continue  # Earlier wording may fill a gap, never restore superseded answers.
        if field is None:
            if (len(result.fields) >= 24 or not 2 <= len(update.label.strip()) <= 80
                    or (not _new_label_supported(update.label, source)
                        and not (update.key == "closing_date" and re.search(r"\b(closing date|applications close|application deadline|deadline)\b", source, re.I)))):
                continue
            field = DraftField(key=update.key, label=update.label, type=update.type,
                               weight=.85, description="Details not confirmed.")
        if field.key == "closing_date":
            field.scope, field.weight = "metadata", 0
        # The model maps language to known fields; literal field labels are not
        # required. Exact user quotes, explicit exclusions, types and quantities
        # remain validated here. The guided parser still uses _mentions.
        if update.state == "not_required":
            if field.key in {"job_title", "role_description", "working_arrangement"}:
                continue
            if not _explicit_exclusion(field, source, expected):
                continue
            if field.key not in ESSENTIAL_FIELDS and re.search(r"\b(remove|delete|drop)\b", source, re.I):
                result.fields = [f for f in result.fields if f.key != field.key]
                result.removed_keys = list(dict.fromkeys([*result.removed_keys, field.key]))
                fields.pop(field.key, None)
                continue
            field.target, field.unit, field.state = None, None, "not_required"
            field.importance = "unspecified"
            field.description = "Not required by the recruiter."
        else:
            target = update.target
            if field.key == "working_arrangement" and isinstance(target, str):
                # Models may include useful details (e.g. two office days).
                # Keep those in description, but store the canonical arrangement.
                pattern = r"\b(remote|hybrid|on[ -]?site)\b"
                canonical = lambda value: "on-site" if value.startswith("on") else value
                proposed_modes = {canonical(m) for m in re.findall(pattern, target.casefold())}
                quoted_modes = {canonical(m) for m in re.findall(pattern, source.casefold())}
                if len(proposed_modes) != 1 or (quoted_modes and not proposed_modes.issubset(quoted_modes)):
                    continue  # Ambiguous choices or invented arrangements need clarification.
                target = proposed_modes.pop()
            supporting_source = source
            if field.target == target and field.type == update.type and field.source_quote:
                supporting_source = field.source_quote + " " + source
            if update.state == "confirmed" or target is not None:
                if update.type == "number":
                    if (isinstance(target, bool) or not isinstance(target, (int, float))
                            or not math.isfinite(target) or not 0 <= target <= 100000):
                        continue
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
                if field.key == "job_title" and not _title_supported(target, source):
                    continue
            if field.key == "closing_date" and update.state == "confirmed":
                parsed_date = parse_closing_date(str(target))
                if not parsed_date or parsed_date != parse_closing_date(source):
                    continue
                target = parsed_date
            # Reject invented quantities in polished descriptions/targets.
            proposed = f"{update.description} {target if isinstance(target, str) else ''}"
            source_numbers = set(re.findall(r"\d+", supporting_source))
            source_numbers.update(str(value) for word, value in NUMBER_WORDS.items()
                                  if re.search(r"\b" + word + r"\b", supporting_source, re.I))
            if field.key != "closing_date" and not set(re.findall(r"\d+", proposed)).issubset(source_numbers):
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
        if 2 <= len(update.label.strip()) <= 80 and update.label.casefold() != field.label.casefold():
            field.label = update.label.strip()
        if informational_only(field.key, field.label, field.target, field.description):
            field.scope, field.weight = "metadata", 0
        field.source_quote = source if update.state == "not_required" else supporting_source[-2000:]
        result.removed_keys = [key for key in result.removed_keys if key != field.key]
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


def draft_from_published_job(job) -> dict:
    """Make existing seeded/legacy jobs editable without changing the live post."""
    from .criteria import normalize_target_profile
    draft = new_job_draft("generic-role")
    fields = {field["key"]: field for field in draft["fields"]}
    for field in fields.values():
        field["state"] = "unanswered" if field["key"] in ESSENTIAL_FIELDS else "not_required"
    for key, value in (("job_title", job.title), ("role_description", job.description)):
        fields[key].update(target=value, state="confirmed", description=value, source_quote=value)
    for key, requirement in normalize_target_profile(job.target_profile).items():
        fields[key] = DraftField(**{**{k: v for k, v in requirement.items() if k in DraftField.model_fields},
                                    "state": "confirmed", "importance": "preferred" if requirement.get("optional") else "required"}).model_dump()
    draft["fields"] = list(fields.values())
    draft["published_closing_date"] = job.closing_date
    return draft


def draft_changes_live_job(job) -> bool:
    if not job.draft:
        return False
    from .criteria import normalize_target_profile
    fields = {field["key"]: field for field in job.draft["fields"]}
    closing = fields.get("closing_date", {})
    return (fields["job_title"]["target"] != job.title
            or fields["role_description"]["target"] != job.description
            or normalize_target_profile(draft_profile(job.draft)) != normalize_target_profile(job.target_profile)
            or (closing.get("target") if closing.get("state") == "confirmed" else None) != job.closing_date)
