import argparse

from sqlalchemy import select

from . import models
from .database import SessionLocal


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage recruiter access")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    for command in ("approve", "reject"):
        child = subparsers.add_parser(command)
        child.add_argument("email")
        child.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.command == "list":
        list_recruiters()
    else:
        set_recruiter_status(
            args.email,
            "approved" if args.command == "approve" else "rejected",
            args.quiet,
        )


if __name__ == "__main__":
    main()
