"""
Analysis Session Schemas
"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.schemas.common import BaseSchema
from app.schemas.chat import ChatTurn


class SessionCreate(BaseSchema):
    dataset_id: uuid.UUID
    title: Optional[str] = Field(default=None, max_length=255)


class SessionRename(BaseSchema):
    title: str = Field(min_length=1, max_length=255)


class SessionSummary(BaseSchema):
    id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_name: Optional[str] = None
    title: str
    turn_count: int = 0
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionSummary):
    turns: List[ChatTurn] = Field(default_factory=list)
