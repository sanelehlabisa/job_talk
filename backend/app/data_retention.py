import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models
from .database import SessionLocal
from .settings import get_settings


def delete_candidate_data(db: Session, user_ids: list[int]) -> int:
    if not user_ids:
        return 0
    chat_ids = list(
        db.scalars(select(models.Chat.id).where(models.Chat.user_id.in_(user_ids)))
    )
    db.execute(
        delete(models.Application).where(
            models.Application.candidate_user_id.in_(user_ids)
        )
    )
    db.execute(delete(models.AuthSession).where(models.AuthSession.user_id.in_(user_ids)))
    if chat_ids:
        db.execute(delete(models.Message).where(models.Message.chat_id.in_(chat_ids)))
        db.execute(delete(models.Chat).where(models.Chat.id.in_(chat_ids)))
    db.execute(delete(models.User).where(models.User.id.in_(user_ids)))
    return len(user_ids)


def purge_expired_guest_data(db: Session, before: datetime) -> int:
    user_ids = list(
        db.scalars(
            select(models.User.id).where(
                models.User.role == "candidate",
                models.User.created_at < before,
            )
        )
    )
    deleted = delete_candidate_data(db, user_ids)
    db.execute(
        delete(models.ExperimentEvent).where(
            models.ExperimentEvent.created_at < before
        )
    )
    db.commit()
    return deleted


def delete_application_data(db: Session, application_id: int) -> bool:
    application = db.get(models.Application, application_id)
    if not application:
        return False
    delete_candidate_data(db, [application.candidate_user_id])
    db.commit()
    return True


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Remove Job Talk candidate demo data")
    subparsers = parser.add_subparsers(dest="command", required=True)
    purge = subparsers.add_parser("purge-guests")
    purge.add_argument("--older-than-days", type=int, default=settings.demo_data_retention_days)
    purge.add_argument("--confirm", action="store_true")
    application = subparsers.add_parser("delete-application")
    application.add_argument("application_id", type=int)
    application.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("No data changed. Re-run with --confirm after checking the command.")

    with SessionLocal() as db:
        if args.command == "purge-guests":
            if not 1 <= args.older_than_days <= settings.demo_data_retention_days:
                raise SystemExit(
                    "--older-than-days must be between 1 and "
                    f"{settings.demo_data_retention_days}"
                )
            cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)
            deleted = purge_expired_guest_data(db, cutoff)
            print(f"Deleted {deleted} guest candidate record(s) created before {cutoff.isoformat()}")
        else:
            deleted = delete_application_data(db, args.application_id)
            if not deleted:
                raise SystemExit(f"Application {args.application_id} was not found")
            print(f"Deleted candidate data for application {args.application_id}")


if __name__ == "__main__":
    main()
