import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from . import models
from .settings import get_settings


EVENT_TYPES = {
    "visit",
    "application_started",
    "application_submitted",
    "comparison_opened",
    "candidate_feedback",
    "recruiter_feedback",
}


def visitor_digest(visitor_id: str) -> str:
    return hmac.new(
        get_settings().session_token_pepper.encode("utf-8"),
        f"experiment:{visitor_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def record_event(
    db: Session,
    event_type: str,
    visitor_id: str | None,
    subject_type: str = "none",
    subject_id: int = 0,
    useful: bool | None = None,
) -> bool:
    if not visitor_id or event_type not in EVENT_TYPES:
        return False
    now = datetime.now(timezone.utc)
    visitor_hash = visitor_digest(visitor_id)
    event_date = now.date().isoformat()
    existing = db.scalar(
        select(models.ExperimentEvent.id).where(
            models.ExperimentEvent.event_type == event_type,
            models.ExperimentEvent.visitor_hash == visitor_hash,
            models.ExperimentEvent.event_date == event_date,
            models.ExperimentEvent.subject_type == subject_type,
            models.ExperimentEvent.subject_id == subject_id,
        )
    )
    if existing:
        return False
    db.add(
        models.ExperimentEvent(
            event_type=event_type,
            visitor_hash=visitor_hash,
            event_date=event_date,
            subject_type=subject_type,
            subject_id=subject_id,
            useful=useful,
            created_at=now,
        )
    )
    return True


def build_report(db: Session) -> dict:
    counts = {
        event_type: db.scalar(
            select(func.count(models.ExperimentEvent.id)).where(
                models.ExperimentEvent.event_type == event_type
            )
        )
        or 0
        for event_type in EVENT_TYPES
    }
    unique_visitors = db.scalar(
        select(func.count(distinct(models.ExperimentEvent.visitor_hash))).where(
            models.ExperimentEvent.event_type == "visit"
        )
    ) or 0
    visitor_ranges = db.execute(
        select(
            models.ExperimentEvent.visitor_hash,
            func.min(models.ExperimentEvent.created_at),
            func.max(models.ExperimentEvent.created_at),
        )
        .where(models.ExperimentEvent.event_type == "visit")
        .group_by(models.ExperimentEvent.visitor_hash)
    ).all()
    seven_day_returns = sum(
        1
        for _, first_seen, last_seen in visitor_ranges
        if first_seen
        and last_seen
        and timedelta(0) < last_seen - first_seen <= timedelta(days=7)
    )
    recruiters_who_compared = db.scalar(
        select(func.count(distinct(models.ExperimentEvent.visitor_hash))).where(
            models.ExperimentEvent.event_type == "comparison_opened"
        )
    ) or 0
    feedback = {}
    for kind in ("candidate", "recruiter"):
        event_type = f"{kind}_feedback"
        total = counts[event_type]
        positive = db.scalar(
            select(func.count(models.ExperimentEvent.id)).where(
                models.ExperimentEvent.event_type == event_type,
                models.ExperimentEvent.useful.is_(True),
            )
        ) or 0
        feedback[kind] = {
            "responses": total,
            "useful": positive,
            "useful_rate": round(positive / total, 2) if total else None,
        }
    return {
        "unique_visitors": unique_visitors,
        "application_starts": counts["application_started"],
        "application_submissions": counts["application_submitted"],
        "comparison_opens": counts["comparison_opened"],
        "recruiters_who_compared": recruiters_who_compared,
        "seven_day_returns": seven_day_returns,
        "feedback": feedback,
    }
