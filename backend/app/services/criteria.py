import re
from collections.abc import Mapping


GENERAL_CRITERIA = {
    "availability",
    "education",
    "experience",
    "location",
    "working_arrangement",
}
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _years(value: object) -> int | None:
    match = re.search(
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)[+-]? years?",
        str(value or ""),
        re.I,
    )
    if not match:
        return None
    raw = match.group(1).lower()
    return int(raw) if raw.isdigit() else NUMBER_WORDS[raw]


def _text_target(key: str, value: str) -> str:
    if key == "location":
        match = re.search(
            r"\b(?:based|located|work)\s+in\s+([A-Za-z][A-Za-z .'-]{1,60})",
            value,
            re.I,
        )
        if match:
            return re.split(r"[.;]|\b(?:and|but|with)\b", match.group(1))[0].strip()
    if key == "working_arrangement":
        arrangement = next(
            (item for item in ("remote", "hybrid", "on-site") if item in value.lower()),
            None,
        )
        if arrangement:
            return arrangement
    if key == "availability":
        match = re.search(
            r"(?:available(?: to start)?|start requirement:?|start)\s+(.+)",
            value,
            re.I,
        )
        if match:
            return match.group(1).strip(" .")[:100]
    return value.strip(" .")[:160]


def normalize_criterion(key: str, requirement: Mapping[str, object] | None) -> dict:
    """Add the canonical typed fields while retaining compatible source fields."""
    item = dict(requirement or {})
    description = str(item.get("description") or "Details not confirmed.").strip()
    label = str(item.get("label") or key.replace("_", " ").title()).strip()
    years = _years(item.get("years_required")) or _years(description)

    criterion_type = item.get("type")
    target = item.get("target")
    unit = item.get("unit")
    if criterion_type not in {"number", "skill", "text"}:
        if years is not None:
            criterion_type, target, unit = "number", years, "years"
        elif item.get("kind") == "skill" or key not in GENERAL_CRITERIA:
            criterion_type, target = "skill", True
        else:
            criterion_type, target = "text", _text_target(key, description)

    item.update(
        {
            "key": key,
            "label": label,
            "type": criterion_type,
            "target": target,
            "weight": float(item.get("weight", 0.5)),
            "description": description,
        }
    )
    if unit:
        item["unit"] = str(unit)
    else:
        item.pop("unit", None)
    return item


def normalize_target_profile(profile: Mapping[str, object] | None) -> dict:
    return {
        str(key): normalize_criterion(
            str(key), requirement if isinstance(requirement, Mapping) else None
        )
        for key, requirement in (profile or {}).items()
    }
