"""
Authentication & User Endpoints
Registration, login and "who am I". Passwords are bcrypt-hashed; tokens are short-lived JWTs.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import _bearer, _UNAUTHORIZED, get_current_user
from app.core.security import create_access_token, hash_password, token_claims, verify_password
from app.models.user import GUEST_EMAIL_SUFFIX, GUEST_PASSWORD_MARKER, GuestLease, User
from app.schemas.common import APIResponse
from app.schemas.user import GuestPolicy, Token, UserCreate, UserLogin, UserResponse
from app.services import guest_sessions

router = APIRouter()

# A real bcrypt hash of a throwaway string. Verifying against it when the e-mail is
# unknown keeps login timing the same whether or not the account exists.
_DUMMY_HASH = hash_password("timing-equaliser")
# The removed open-access path provisioned this account with a fixed password.
_LEGACY_OPEN_EMAIL = "analyst@edagent.local"


def _user_response(user: User, deadline: int | None = None) -> UserResponse:
    result = UserResponse.model_validate(user)
    if deadline is not None:
        result.guest = GuestPolicy(
            expires_at=deadline, max_upload_bytes=settings.GUEST_MAX_UPLOAD_BYTES,
            max_datasets=settings.GUEST_MAX_DATASETS, max_actions=settings.GUEST_MAX_ACTIONS,
        )
    return result


def _token_for(user: User, deadline: int | None = None) -> Token:
    token, expires_in = create_access_token(
        str(user.id), settings.GUEST_SESSION_MINUTES if deadline is not None else None, guest=user.is_guest,
    )
    return Token(access_token=token, expires_in_seconds=expires_in, user=_user_response(user, deadline))


@router.post("/register", response_model=APIResponse[Token], summary="Register User", status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(status_code=403, detail="Registration is disabled on this server.")
    email = payload.email.lower().strip()
    if email == _LEGACY_OPEN_EMAIL or email.endswith(GUEST_EMAIL_SUFFIX):
        raise HTTPException(status_code=422, detail="This e-mail address is reserved.")
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this e-mail already exists.")
    user = User(email=email, full_name=payload.full_name, hashed_password=hash_password(payload.password))
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return APIResponse(success=True, message="Account created.", data=_token_for(user))


@router.post("/login", response_model=APIResponse[Token], summary="User Login")
async def login_user(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    ok = verify_password(payload.password, user.hashed_password if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active or user.is_guest or email == _LEGACY_OPEN_EMAIL:
        # One generic message for every failure mode: never reveal which part was wrong.
        raise HTTPException(status_code=401, detail="Incorrect e-mail or password.")
    return APIResponse(success=True, message="Signed in.", data=_token_for(user))


@router.get("/me", response_model=APIResponse[UserResponse], summary="Current User")
async def read_current_user(request: Request, user: User = Depends(get_current_user)):
    return APIResponse(success=True, message="Current user.", data=_user_response(user, getattr(request.state, "guest_deadline", None)))


@router.get("/guest-session")
async def guest_availability(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return APIResponse(data={"available": settings.ALLOW_GUEST_SESSIONS})


@router.post("/guest-session", response_model=APIResponse[Token], status_code=201)
async def start_guest_session(response: Response, db: AsyncSession = Depends(get_db)):
    if not settings.ALLOW_GUEST_SESSIONS:
        raise HTTPException(403, detail="New private guest sessions are unavailable.")
    user_id = uuid.uuid4()
    user = User(
        id=user_id, email=f"{user_id.hex}{GUEST_EMAIL_SUFFIX}",
        full_name="Private guest", hashed_password=GUEST_PASSWORD_MARKER,
    )
    deadline = guest_sessions.timestamp() + settings.GUEST_SESSION_MINUTES * 60
    db.add(user)
    await db.flush()
    db.add(GuestLease(user_id=user_id, expires_at=deadline))
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return APIResponse(data=_token_for(user, deadline))


@router.delete("/guest-session", status_code=204)
async def clear_guest_session(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    # An expired guest token can only clear its own lease. Repeated clear succeeds
    # after the owned rows have gone. Account tokens never reach the delete.
    claims = token_claims(creds.credentials, allow_expired=True) if creds else {}
    if claims.get("guest") is not True:
        raise _UNAUTHORIZED
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        raise _UNAUTHORIZED
    await guest_sessions.clear(user_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
