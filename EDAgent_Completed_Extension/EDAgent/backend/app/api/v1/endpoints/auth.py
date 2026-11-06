"""
Authentication & User Endpoints
Registration, login and "who am I". Passwords are bcrypt-hashed; tokens are short-lived JWTs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse

router = APIRouter()

# A real bcrypt hash of a throwaway string. Verifying against it when the e-mail is
# unknown keeps login timing the same whether or not the account exists.
_DUMMY_HASH = hash_password("timing-equaliser")


def _token_for(user: User) -> Token:
    token, expires_in = create_access_token(str(user.id))
    return Token(access_token=token, expires_in_seconds=expires_in, user=UserResponse.model_validate(user))


@router.post("/register", response_model=APIResponse[Token], summary="Register User", status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(status_code=403, detail="Registration is disabled on this server.")
    email = payload.email.lower().strip()
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
    if not user or not ok or not user.is_active:
        # One generic message for every failure mode: never reveal which part was wrong.
        raise HTTPException(status_code=401, detail="Incorrect e-mail or password.")
    return APIResponse(success=True, message="Signed in.", data=_token_for(user))


@router.get("/me", response_model=APIResponse[UserResponse], summary="Current User")
async def read_current_user(user: User = Depends(get_current_user)):
    return APIResponse(success=True, message="Current user.", data=UserResponse.model_validate(user))
