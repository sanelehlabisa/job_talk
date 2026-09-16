import re
from decimal import Decimal, ROUND_HALF_UP

from ..models import JobPost


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


def _years(value: str) -> int | None:
    match = re.search(r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)[+-]? years?", value, re.I)
    if not match:
        return None
    raw = match.group(1).lower()
    return int(raw) if raw.isdigit() else NUMBER_WORDS[raw]


def _place(value: str) -> str | None:
    match = re.search(r"(?:based|located|role|position|job|from|near) in? ?([A-Za-z .'-]+)", value, re.I)
    if not match:
        match = re.search(r"\bin ([A-Za-z .'-]+)", value, re.I)
    if not match:
        return None
    return re.split(r"\b(?:while|and|but|with|whereas)\b", match.group(1))[0].strip(" .,").lower()


def criterion_score(key: str, requirement: dict, candidate_profile: dict) -> tuple[float, str]:
    evidence = candidate_profile.get(key, {}).get("evidence", "")
    requirement_text = requirement.get("description", "")

    if key == "location" and evidence:
        required_place, candidate_place = _place(requirement_text), _place(evidence)
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
        return 0.95, f"The candidate provided direct evidence: {evidence}"

    candidate_text = " ".join(item.get("evidence", "") for item in candidate_profile.values())
    required_tokens = _tokens(f"{key} {requirement_text}")
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
    for key, requirement in target_profile.items():
        weight = Decimal(str(requirement.get("weight", 0.5)))
        score, reason = criterion_score(key, requirement, candidate_profile)
        rounded_score = Decimal(str(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        criteria[key] = {"score": float(rounded_score), "reason": reason, "weight": float(weight)}
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
