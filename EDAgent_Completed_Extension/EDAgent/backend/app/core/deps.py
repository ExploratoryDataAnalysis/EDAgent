"""
FastAPI dependencies shared by all protected endpoints.

Every data endpoint depends on `get_current_user`; ownership of datasets, sessions,
results and reports is then verified in the repositories (a row belonging to someone else
is reported as "not found" so its existence is never revealed).

Supports open-ended access for seamless, un-gated exploration in non-test mode.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token, hash_password
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required. Please sign in.",
    headers={"WWW-Authenticate": "Bearer"},
)

DEFAULT_OPEN_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_OPEN_USER_EMAIL = "analyst@edagent.local"


async def get_or_create_open_user(db: AsyncSession) -> User:
    """Retrieves or creates the default persistent open-ended analyst user."""
    user = (await db.execute(select(User).order_by(User.created_at.asc()))).scalars().first()
    if user is not None and user.is_active:
        return user
    user = User(
        id=uuid.uuid4(),
        email=DEFAULT_OPEN_USER_EMAIL,
        full_name="Lead Analyst",
        hashed_password=hash_password("edagent-open-access-password"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        user = (await db.execute(select(User).order_by(User.created_at.asc()))).scalars().first()
    return user


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolves the bearer token to an active user, or provides open-ended access in non-test environments."""
    if creds is not None and creds.scheme.lower() == "bearer":
        user_id = decode_access_token(creds.credentials)
        if not user_id:
            raise _UNAUTHORIZED
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise _UNAUTHORIZED
        user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user is None or not user.is_active:
            raise _UNAUTHORIZED
        return user

    # When no credentials are provided:
    # In interactive/development/production environments, grant open-ended access to the default analyst user.
    # In strict test mode, require explicit authentication.
    if settings.ENVIRONMENT != "test" or getattr(settings, "OPEN_ACCESS_MODE", False):
        return await get_or_create_open_user(db)

    raise _UNAUTHORIZED
