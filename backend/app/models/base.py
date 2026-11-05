"""
Base SQLAlchemy Model Definitions
Provides common UUID primary key, timestamp auditing, and serialization helpers.
"""

import uuid
from datetime import datetime, timezone
from app.core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

try:
    from sqlalchemy import Column, DateTime, String
    from sqlalchemy.dialects.postgresql import UUID

    class TimestampedUUIDModel(Base):  # type: ignore[misc,valid-type]
        __abstract__ = True

        id = Column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            index=True,
            nullable=False
        )
        created_at = Column(
            DateTime(timezone=True),
            default=utc_now,
            nullable=False
        )
        updated_at = Column(
            DateTime(timezone=True),
            default=utc_now,
            onupdate=utc_now,
            nullable=False
        )

except Exception:
    class TimestampedUUIDModel:  # type: ignore[no-redef]
        """Fallback mock for Phase 0 prior to database driver linking."""
        id: str
        created_at: datetime
        updated_at: datetime
