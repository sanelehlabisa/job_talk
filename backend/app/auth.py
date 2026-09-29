import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .settings import get_settings


password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)
settings = get_settings()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def token_digest(token: str) -> str:
    return hmac.new(
        settings.session_token_pepper.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


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
    return schemas.AuthResponse(access_token=token, expires_at=expires_at, user=user)


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
    return session.user
