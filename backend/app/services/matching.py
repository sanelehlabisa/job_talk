import re
from decimal import Decimal, ROUND_HALF_UP

from ..models import JobPost
from .criteria import normalize_target_profile


MIN_RECOMMENDATION_SCORE = 0.5


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]+", value.lower()))


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

GENERIC_REQUIREMENT_TOKENS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "the", "their", "to",
    "was", "will", "with", "work", "working", "this", "that",
    "applicant",
    "applicants",
    "candidate",
    "experience",
    "important",
    "minimum",
    "preferred",
    "relevant",
    "required",
    "requirement",
    "role",
    "should",
    "year",
    "years",
    *NUMBER_WORDS.keys(),
}


def _years(value: str) -> int | None:
    match = re.search(r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)[+-]? years?", value, re.I)
    if not match:
        return None
    raw = match.group(1).lower()
    return int(raw) if raw.isdigit() else NUMBER_WORDS[raw]


def _place(value: str) -> str | None:
    patterns = (
        r"\b(?:based|located)\s+in\s+([A-Za-z][A-Za-z '-]{1,60})",
        r"\b(?:role|position|job)\s+(?:is\s+)?in\s+([A-Za-z][A-Za-z '-]{1,60})",
        r"\b(?:from|near)\s+([A-Za-z][A-Za-z '-]{1,60})",
        r"\bin\s+([A-Za-z][A-Za-z '-]{1,60})",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.I)
        if match:
            return re.split(
                r"\b(?:while|and|but|with|whereas)\b",
                match.group(1),
            )[0].strip(" .,").lower()
    return None


def _candidate_value(key: str, requirement: dict, candidate_item: dict):
    if candidate_item.get("assessment") == "gap" or candidate_item.get("state") == "needs_clarification":
        return None
    if "value" in candidate_item:
        return candidate_item["value"]
    evidence = candidate_item.get("evidence", "")
    if not evidence:
        return None
    if requirement.get("type") == "number":
        return _years(evidence)
    if requirement.get("type") == "skill":
        return True
    if key == "location":
        place = _place(evidence)
        return place.title() if place else evidence
    if key == "working_arrangement":
        return next(
            (item for item in ("remote", "hybrid", "on-site") if item in evidence.lower()),
            evidence,
        )
    return evidence


def criterion_score(key: str, requirement: dict, candidate_profile: dict) -> tuple[float, str]:
    candidate_item = candidate_profile.get(key, {})
    evidence = candidate_item.get("evidence", "")
    requirement_text = requirement.get("description", "")

    if candidate_item.get("state") == "needs_clarification":
        return 0.0, "This answer needs clarification before it can be compared."

    if candidate_item.get("assessment") == "gap":
        return 0.0, "The candidate explicitly reported a gap for this criterion."

    if requirement.get("type") == "number" and evidence:
        target = requirement.get("target")
        candidate_value = _candidate_value(key, requirement, candidate_item)
        if isinstance(target, (int, float)) and isinstance(
            candidate_value, (int, float)
        ):
            if target <= 0:
                return 1.0, "The criterion has no positive minimum target."
            score = min(1.0, max(0.0, candidate_value / target))
            unit = str(requirement.get("unit") or "units")
            return score, (
                f"The candidate reports {candidate_value} {unit} against a "
                f"target of {target} {unit}."
            )
        return 0.0, (
            "The candidate provided related evidence, but it does not contain "
            "the measurable value requested by this criterion."
        )

    if key == "location" and evidence:
        required_place = _place(requirement_text) or str(requirement.get("target") or "").strip().lower()
        candidate_place = _place(evidence) or str(_candidate_value(key, requirement, candidate_item) or "").strip().lower()
        if required_place and candidate_place:
            if required_place == candidate_place:
                return 0.95, f"The candidate's location matches the role: {candidate_place.title()}."
            return 0.3, f"The candidate is based in {candidate_place.title()}, while the role refers to {required_place.title()}."
    if key == "experience" and evidence:
        required_years, candidate_years = _years(requirement_text), _years(evidence)
        if required_years is not None and candidate_years is not None:
            if candidate_years >= required_years:
                return 1.0, f"The candidate reports {candidate_years} years against a {required_years}-year requirement."
            score = max(0.2, candidate_years / required_years)
            return score, f"The candidate reports {candidate_years} years against a {required_years}-year requirement."
    if key == "working_arrangement" and evidence:
        arrangements = ("remote", "hybrid", "on-site")
        required = next((item for item in arrangements if item in requirement_text.lower()), None)
        candidate = next((item for item in arrangements if item in evidence.lower()), None)
        if required and candidate:
            return (0.95, f"The candidate is open to the role's {required} arrangement.") if required == candidate else (0.4, f"The candidate prefers {candidate}, while this role is {required}.")
    if evidence:
        concrete = bool(
            _years(evidence)
            or re.search(
                r"\b(?:built|completed|coordinated|created|fixed|installed|launched|maintained|managed|operated|repaired|used|worked|welded)\b",
                evidence,
                re.I,
            )
        )
        score = 0.9 if concrete else 0.55
        quality = (
            "a concrete example"
            if concrete
            else "a general claim without a concrete example"
        )
        return score, f"The candidate provided {quality} for this criterion."

    candidate_text = " ".join(
        item.get("evidence", "")
        for item in candidate_profile.values()
        if item.get("assessment") != "gap"
    )
    required_tokens = _tokens(f"{key} {requirement_text}") - GENERIC_REQUIREMENT_TOKENS
    candidate_tokens = _tokens(candidate_text)
    overlap = len(required_tokens & candidate_tokens) / max(len(required_tokens), 1)
    score = min(0.75, overlap * 1.5)
    if score >= 0.5:
        return score, "The candidate described related experience, although the criterion was not explicit."
    if requirement.get("optional"):
        return 0.5, "No direct evidence was provided, but this criterion is optional."
    return score, "The conversation does not yet contain direct evidence for this criterion."


def match_profiles(candidate_profile: dict, target_profile: dict) -> dict:
    criteria = {}
    weighted_total = Decimal("0")
    total_weight = Decimal("0")
    for key, requirement in normalize_target_profile(target_profile).items():
        weight = Decimal(str(requirement.get("weight", 0.5)))
        score, reason = criterion_score(key, requirement, candidate_profile)
        rounded_score = Decimal(str(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        candidate_item = candidate_profile.get(key, {})
        evidence = candidate_item.get("evidence", "")
        gap = (
            "reported"
            if candidate_item.get("assessment") == "gap"
            else "missing"
            if not evidence
            else None
        )
        criteria[key] = {
            "label": requirement["label"],
            "type": requirement["type"],
            "unit": requirement.get("unit"),
            "candidate_value": _candidate_value(key, requirement, candidate_item),
            "target_value": requirement.get("target"),
            "score": float(rounded_score),
            "weight": float(weight),
            "evidence": evidence,
            "reason": reason,
            "gap": gap,
        }
        weighted_total += rounded_score * weight
        total_weight += weight
    overall = (
        (weighted_total / total_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total_weight else Decimal("0")
    )
    return {"criteria": criteria, "overall_score": float(overall)}


def rank_jobs(candidate_profile: dict, jobs: list[JobPost]) -> list[tuple[JobPost, dict]]:
    ranked = [(job, match_profiles(candidate_profile, job.target_profile)) for job in jobs]
    return sorted(ranked, key=lambda item: item[1]["overall_score"], reverse=True)[:5]


def is_recommended(result: dict) -> bool:
    return float(result.get("overall_score", 0)) >= MIN_RECOMMENDATION_SCORE


def summarize_match(result: dict) -> str:
    criteria = result.get("criteria", {})
    strengths = [key.replace("_", " ") for key, value in criteria.items() if value["score"] >= 0.8]
    gaps = [key.replace("_", " ") for key, value in criteria.items() if value["score"] < 0.5]
    if strengths and gaps:
        return f"Strong alignment on {', '.join(strengths[:2])}; more evidence is needed for {', '.join(gaps[:2])}."
    if strengths:
        return f"Strong alignment on {', '.join(strengths[:3])}."
    if gaps:
        return f"Potential match, with more evidence needed for {', '.join(gaps[:3])}."
    return "The profile has partial alignment across the role's criteria."
