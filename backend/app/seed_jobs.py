from sqlalchemy import select

from . import models
from .database import SessionLocal
from .settings import get_settings


DEMO_JOBS = (
    {
        "title": "Welder and Forklift Operator",
        "description": "A Cape Town workshop needs a welder who can also operate a forklift safely.",
        "target_profile": {
            "welding": {"weight": 0.9, "description": "Welding experience is required."},
            "forklift_operation": {"weight": 0.75, "description": "Forklift operation experience is required."},
            "experience": {"weight": 0.8, "description": "The role asks for two years of relevant experience."},
            "location": {"weight": 0.55, "description": "The role is based in Cape Town."},
        },
    },
    {
        "title": "Junior Electrician",
        "description": "A Johannesburg maintenance team needs a junior electrician for on-site wiring work.",
        "target_profile": {
            "electrician": {"weight": 0.85, "description": "Electrician experience is required."},
            "electrical_wiring": {"weight": 0.9, "description": "Electrical wiring experience is required."},
            "experience": {"weight": 0.7, "description": "The role asks for one year of relevant experience."},
            "location": {"weight": 0.5, "description": "The role is based in Johannesburg."},
        },
    },
    {
        "title": "Delivery Driver",
        "description": "A Durban supplier needs a reliable local driver for weekday deliveries.",
        "target_profile": {
            "driver": {"weight": 0.9, "description": "Professional driving experience is required."},
            "driving": {"weight": 0.8, "description": "Safe driving experience is required."},
            "experience": {"weight": 0.65, "description": "The role asks for one year of relevant experience."},
            "location": {"weight": 0.55, "description": "The role is based in Durban."},
        },
    },
)


def seed_jobs() -> int:
    settings = get_settings()
    if not settings.demo_recruiter_email:
        raise SystemExit("DEMO_RECRUITER_EMAIL is required to seed demo jobs")
    email = str(settings.demo_recruiter_email).lower()
    created = 0
    with SessionLocal() as db:
        recruiter = db.scalar(select(models.User).where(models.User.email == email))
        if not recruiter or recruiter.role != "recruiter" or recruiter.approval_status != "approved":
            raise SystemExit("The demo recruiter must be approved before seeding jobs")
        for definition in DEMO_JOBS:
            job = db.scalar(
                select(models.JobPost).where(
                    models.JobPost.user_id == recruiter.id,
                    models.JobPost.title == definition["title"],
                )
            )
            if not job:
                chat = models.Chat(
                    user_id=recruiter.id,
                    intent="employer",
                    status="published",
                    profile=definition["target_profile"],
                )
                db.add(chat)
                db.flush()
                db.add(
                    models.Message(
                        chat_id=chat.id,
                        sender="assistant",
                        content="This demo role is published and ready for candidate applications.",
                    )
                )
                job = models.JobPost(chat_id=chat.id, user_id=recruiter.id)
                db.add(job)
                created += 1
            job.title = definition["title"]
            job.description = definition["description"]
            job.target_profile = definition["target_profile"]
            job.published = True
        db.commit()
    print(f"Seeded {len(DEMO_JOBS)} jobs ({created} created)")
    return created


if __name__ == "__main__":
    seed_jobs()
