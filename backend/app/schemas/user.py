"""
User and Authentication Schemas
"""

import uuid
from datetime import datetime
from typing import Optional
from app.schemas.common import BaseSchema

try:
    import email_validator  # noqa: F401
    from pydantic import EmailStr
except ImportError:
    EmailStr = str  # type: ignore[misc,assignment]


class UserBase(BaseSchema):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: uuid.UUID
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class Token(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class TokenPayload(BaseSchema):
    sub: Optional[str] = None
    exp: Optional[int] = None
