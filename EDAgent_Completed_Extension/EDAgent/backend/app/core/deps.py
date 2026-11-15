"""Authentication dependency for protected workspace routes."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import token_claims
from app.models.user import User
from app.services import guest_sessions

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required. Please sign in.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise _UNAUTHORIZED

    claims = token_claims(creds.credentials)
    subject = claims.get("sub")
    if not subject:
        raise _UNAUTHORIZED
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise _UNAUTHORIZED
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active or user.is_guest != (claims.get("guest") is True):
        raise _UNAUTHORIZED
    if user.is_guest:
        request.state.guest_id = user.id
        lease = await guest_sessions.active(db, user.id)
        if lease is None:
            raise _UNAUTHORIZED
        request.state.guest_deadline = lease.expires_at
    return user


async def account_only(user: User = Depends(get_current_user)) -> User:
    if user.is_guest:
        raise HTTPException(403, detail="This action requires a signed-in account.")
    return user


async def charge_guest(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    if user.is_guest:
        # Persist the attempt even if parsing or computation fails.
        await guest_sessions.lock_active(db, user.id, charge=True)
        await db.commit()
    return user
