"""
FastAPI dependencies shared by all protected endpoints.

Every data endpoint depends on `get_current_user`; ownership of datasets, sessions,
results and reports is then verified in the repositories (a row belonging to someone else
is reported as "not found" so its existence is never revealed).
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required. Please sign in.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolves the bearer token to an active user or raises 401."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise _UNAUTHORIZED
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
