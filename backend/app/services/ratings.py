"""Saved model ratings; weights and totals remain in matching.py."""
import hashlib
import json
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field

from .criteria import normalize_target_profile


RATINGS_KEY = "_match_ratings"


class CriterionRating(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    score: int = Field(ge=0, le=100, strict=True)
    reason: str = Field(min_length=4, max_length=240)
    evidence_keys: list[str] = Field(max_length=24)


class JobRating(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: int
    criteria: list[CriterionRating] = Field(max_length=24)


class RatingReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jobs: list[JobRating]

    @classmethod
    def provider_schema(cls) -> dict:
        # Gemini rejected the bounded nested schema in a live check. Keep these
        # collection/text bounds in Pydantic and send the simpler shape.
        def simplify(value):
            if isinstance(value, dict):
                return {key: simplify(item) for key, item in value.items()
                        if key not in {"maxItems", "minLength", "maxLength"}}
            if isinstance(value, list):
                return [simplify(item) for item in value]
            return value
        return simplify(cls.model_json_schema())


def evidence_profile(profile: dict) -> dict:
    return {key: value for key, value in profile.items()
            if key not in {RATINGS_KEY, "candidate_details", "consent"}}


def rating_signature(profile: dict, criteria: dict) -> str:
    data = [evidence_profile(profile), normalize_target_profile(criteria)]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def usable_evidence(item: dict) -> bool:
    return bool(item.get("evidence")) and item.get("assessment") != "gap" and item.get("state") not in {
        "gap", "unanswered", "needs_clarification",
    }


def saved_rating(profile: dict, criteria: dict, job_id: int | None = None, title: str | None = None) -> dict | None:
    results = profile.get(RATINGS_KEY, {}).get("results", {})
    choices = [results.get(str(job_id), {})] if job_id is not None else results.values()
    signature = rating_signature(profile, criteria)
    matches = [rating for rating in choices if rating.get("signature") == signature
               and (title is None or rating.get("title") == title)]
    return matches[0] if len(matches) == 1 else None


def save_ratings(profile: dict, jobs: list[dict], reply: RatingReply, *, selected: bool, model: str) -> dict:
    """Reject unknown/duplicate fields and unsupported positive ratings as a batch."""
    expected = {job["id"]: normalize_target_profile(job["criteria"]) for job in jobs}
    if len(reply.jobs) != len(expected) or {job.job_id for job in reply.jobs} != set(expected):
        raise ValueError("Ratings must cover exactly the supplied jobs")
    results = {}
    for job in reply.jobs:
        criteria = expected[job.job_id]
        if len(job.criteria) != len(criteria) or {rating.key for rating in job.criteria} != set(criteria):
            raise ValueError("Ratings must cover exactly the published criteria")
        scores = {}
        for rating in job.criteria:
            item = profile.get(rating.key, {})
            blocked = item.get("assessment") == "gap" or item.get("state") in {
                "gap", "unanswered", "needs_clarification",
            } or (selected and (not usable_evidence(item) or (
                criteria[rating.key]["type"] == "number" and
                (isinstance(item.get("value"), bool) or not isinstance(item.get("value"), (int, float)))
            )))
            if blocked:
                scores[rating.key] = {"score": 0, "reason": "No confirmed answer, or the candidate reported a gap.", "evidence_keys": []}
                continue
            keys = list(dict.fromkeys(rating.evidence_keys))
            if any(key not in evidence_profile(profile) or not usable_evidence(profile[key]) for key in keys):
                raise ValueError("Rating refers to missing or unresolved evidence")
            if rating.score and (not keys or (selected and rating.key not in keys)):
                raise ValueError("A positive rating needs supporting saved evidence")
            scores[rating.key] = rating.model_dump(exclude={"key"})
        results[str(job.job_id)] = {"signature": rating_signature(profile, criteria),
                                   "title": next(item["title"] for item in jobs if item["id"] == job.job_id),
                                   "criteria": scores, "source": "gemini", "model": model}
    updated = deepcopy(profile)
    updated[RATINGS_KEY] = {**profile.get(RATINGS_KEY, {}), "results": results}
    return updated
