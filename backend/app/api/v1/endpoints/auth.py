"""
Authentication & User Endpoints
"""

from fastapi import APIRouter, HTTPException, status
from app.schemas.user import UserCreate, UserResponse, Token
from app.schemas.common import APIResponse

router = APIRouter()


@router.post("/register", response_model=APIResponse[UserResponse], summary="Register User")
async def register_user(payload: UserCreate):
    """User registration stub for Phase 0 API contract."""
    return APIResponse(
        success=True,
        message="User registration initialized",
        data=None
    )


@router.post("/login", response_model=APIResponse[Token], summary="User Login")
async def login_user():
    """User login endpoint stub."""
    return APIResponse(
        success=True,
        message="Login endpoint contract",
        data=None
    )
