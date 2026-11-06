"""
User and Authentication Schemas
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class UserBase(BaseSchema):
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = True


class UserCreate(BaseSchema):
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=255)
    # 72 is bcrypt's effective limit; longer passwords would be silently truncated.
    password: str = Field(min_length=8, max_length=72)


class UserLogin(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserResponse(UserBase):
    id: uuid.UUID
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class Token(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: Optional[UserResponse] = None


class TokenPayload(BaseSchema):
    sub: Optional[str] = None
    exp: Optional[int] = None
