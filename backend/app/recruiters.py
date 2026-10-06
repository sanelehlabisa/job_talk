import argparse

from sqlalchemy import select

from . import models
from .database import SessionLocal
from .settings import get_settings


DEMO_RECRUITER_EMAIL = "recruiter@example.com"


def seed_recruiter(quiet: bool = False) -> bool:
    """Create local test access or the configured production admin, without jobs."""
    settings = get_settings()
    email = settings.admin_email if settings.app_env == "production" else DEMO_RECRUITER_EMAIL
    if not email:
        raise SystemExit("ADMIN_EMAIL is required to seed production access")
    normalized = str(email).strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(models.User).where(models.User.email == normalized))
        if user:
            if user.role != "recruiter":
                raise SystemExit("That email belongs to a candidate guest session")
            if not quiet:
                print(f"{normalized}: already exists ({user.approval_status}); unchanged")
            return False
        db.add(models.User(email=normalized, role="recruiter", approval_status="approved"))
        db.commit()
    if not quiet:
        print(f"{normalized}: seeded; sign in with an emailed code")
    return True


def set_recruiter_status(email: str, status: str, quiet: bool = False) -> None:
    normalized = email.strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(models.User).where(models.User.email == normalized))
        if user and user.role != "recruiter":
            raise SystemExit("That email belongs to a candidate guest session")
        if not user:
            user = models.User(email=normalized, role="recruiter", approval_status=status)
            db.add(user)
        else:
            user.approval_status = status
        db.commit()
    if not quiet:
        print(f"{normalized}: {status}")


def list_recruiters() -> None:
    with SessionLocal() as db:
        users = db.scalars(
            select(models.User)
            .where(models.User.role == "recruiter")
            .order_by(models.User.created_at)
        ).all()
        for user in users:
            print(f"{user.email}\t{user.approval_status}")


def delete_unused_recruiter(email: str, quiet: bool = False) -> None:
    normalized = email.strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(models.User).where(models.User.email == normalized))
        if not user or user.role != "recruiter":
            raise SystemExit("Recruiter access request not found")
        if user.chats:
            raise SystemExit(
                "Recruiter has hiring records; use the documented support review before deletion"
            )
        db.delete(user)
        db.commit()
    if not quiet:
        print(f"{normalized}: deleted")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage recruiter access")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    subparsers.add_parser("seed").add_argument("--quiet", action="store_true")
    for command in ("approve", "reject", "delete"):
        child = subparsers.add_parser(command)
        child.add_argument("email")
        child.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.command == "list":
        list_recruiters()
    elif args.command == "seed":
        seed_recruiter(args.quiet)
    elif args.command in {"approve", "reject"}:
        set_recruiter_status(
            args.email,
            "approved" if args.command == "approve" else "rejected",
            args.quiet,
        )
    else:
        delete_unused_recruiter(args.email, args.quiet)


if __name__ == "__main__":
    main()
