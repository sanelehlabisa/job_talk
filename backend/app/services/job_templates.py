"""Fixed starter suggestions, stored separately from a job's scoring criteria."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .criteria import normalize_target_profile


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
    state: Literal[
        "unanswered", "needs_clarification", "confirmed", "not_required"
    ] = "unanswered"


class JobDraft(BaseModel):
    template_id: str
    label: str
    description: str
    fields: list[DraftField]


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


def sync_job_draft(draft: dict, title: str, description: str, profile: dict) -> dict:
    """Reflect saved requirements; never promote a template suggestion."""
    result = JobDraft.model_validate(draft)
    requirements = normalize_target_profile(profile)
    existing_keys = {field.key for field in result.fields}
    for key, requirement in requirements.items():
        if key not in existing_keys:
            result.fields.append(DraftField(
                key=key,
                label=requirement["label"],
                type=requirement["type"],
                weight=requirement["weight"],
                description=requirement["description"],
            ))
    for field in result.fields:
        if field.scope == "metadata":
            field.target = (
                title if title and title != "Untitled role" else None
            ) if field.key == "job_title" else (description or None)
            field.state = "confirmed" if field.target else "unanswered"
            continue
        requirement = requirements.get(field.key)
        if requirement is None:
            # Explicit exclusions are retained. An absent value alone is not an exclusion.
            if field.state != "not_required":
                field.target = None
                field.state = "unanswered"
            continue
        field.target = requirement.get("target")
        field.type = requirement["type"]
        field.unit = requirement.get("unit")
        field.weight = requirement["weight"]
        field.description = requirement["description"]
        field.state = (
            "needs_clarification"
            if requirement.get("confirmed") is False or field.target is None
            else "confirmed"
        )
    return result.model_dump()
