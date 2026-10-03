import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .settings import get_settings


bearer_scheme = HTTPBearer(auto_error=False)
settings = get_settings()


def is_admin(user: models.User) -> bool:
    return bool(
        settings.admin_email
        and user.role == "recruiter"
        and user.approval_status == "approved"
        and user.email.strip().lower() == str(settings.admin_email).strip().lower()
    )


def serialize_user(user: models.User) -> schemas.UserOut:
    return schemas.UserOut.model_validate(user).model_copy(update={"is_admin": is_admin(user)})


def token_digest(token: str) -> str:
    return hmac.new(
        settings.session_token_pepper.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def recruiter_code_digest(user_id: int, code: str) -> str:
    return token_digest(f"recruiter-code:{user_id}:{code}")


def generate_recruiter_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_session(db: Session, user: models.User) -> schemas.AuthResponse:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.auth_session_hours)
    token = secrets.token_urlsafe(32)
    db.execute(
        delete(models.AuthSession).where(
            models.AuthSession.user_id == user.id,
            models.AuthSession.expires_at <= now,
        )
    )
    db.add(
        models.AuthSession(
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=expires_at,
        )
    )
    db.commit()
    return schemas.AuthResponse(access_token=token, expires_at=expires_at, user=serialize_user(user))


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.AuthSession:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    session = db.scalar(
        select(models.AuthSession).where(
            models.AuthSession.token_hash == token_digest(credentials.credentials)
        )
    )
    if not session:
        raise _unauthorized()
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise _unauthorized()
    return session


def get_current_user(session: models.AuthSession = Depends(get_current_session)) -> models.User:
    if session.user.role == "recruiter" and session.user.approval_status != "approved":
        raise _unauthorized()
    return session.user


def get_admin_user(user: models.User = Depends(get_current_user)) -> models.User:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
