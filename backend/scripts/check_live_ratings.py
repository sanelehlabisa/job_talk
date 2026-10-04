"""Small actual-Gemini check using fictional data only; no database access."""
import json

import httpx

from app.services.ai import _gemini_json, RATING_INSTRUCTIONS
from app.services.ratings import RatingReply, save_ratings
from app.services.matching import match_profiles
from app.settings import get_settings


def main():
    settings = get_settings()
    assert settings.ai_provider == "gemini", "Select Gemini for this live check."
    criteria = {
        "customer_support": {"label": "Customer care", "type": "text", "target": "Resolve customer complaints", "weight": 1, "description": "Help customers resolve complaints and refunds"},
        "location": {"label": "Location", "type": "text", "target": "Durban", "weight": .5, "description": "Work on-site in Durban"},
        "python": {"label": "Python", "type": "skill", "target": True, "weight": .5, "description": "Use Python"},
    }
    job = {"id": 1, "title": "Customer Support Assistant", "criteria": criteria}
    positive = "I helped angry shoppers get refunds and resolved their problems."
    negative = "I built and repaired wooden tables for three years."
    scores = []
    for statement in (positive, negative):
        profile = {
            "customer_support": {"evidence": statement, "value": statement, "state": "captured"},
            "location": {"evidence": "I live in Cape Town and can relocate to Durban for this job.", "value": "Can relocate to Durban", "state": "captured"},
            "python": {"evidence": "I do not know Python.", "value": None, "state": "gap", "assessment": "gap"},
        }
        payload = {"selected_job": True,
                   "conversation": [{"role": "user", "content": positive}, {"role": "user", "content": statement}],
                   "jobs": [job], "candidate_answers": profile}
        try:
            parsed = RatingReply.model_validate(_gemini_json(RATING_INSTRUCTIONS, json.dumps(payload), RatingReply, settings))
        except httpx.HTTPStatusError as exc:
            # This request includes only the fictional text above; redact the configured key.
            message = exc.response.json().get("error", {}).get("message", "Request rejected")
            key = settings.gemini_api_key.get_secret_value()
            raise RuntimeError(f"HTTP {exc.response.status_code}: {message.replace(key, '[redacted]')[:900]}") from None
        result = match_profiles(save_ratings(profile, [job], parsed, selected=True, model=settings.gemini_model), criteria)
        ratings = {key: {"score": field["score"], "reason": field["reason"]} for key, field in result["criteria"].items()}
        print(json.dumps({"case": "relevant" if statement == positive else "unrelated correction", "source": result["rating_source"], "ratings": ratings}))
        assert result["criteria"]["python"]["score"] == 0
        assert result["criteria"]["location"]["score"] >= .75
        scores.append(result["criteria"]["customer_support"]["score"])
    assert scores[0] >= .75 and scores[1] <= .25, "Gemini did not distinguish relevant from unrelated evidence."
    print("Actual Gemini rating check passed; no database was read or modified.")


if __name__ == "__main__":
    main()
