"""
User ORM Model
"""

import uuid
from app.models.base import TimestampedUUIDModel

try:
    from sqlalchemy import Column, String, Boolean
    from sqlalchemy.orm import relationship

    class User(TimestampedUUIDModel):
        __tablename__ = "users"

        email = Column(String(255), unique=True, index=True, nullable=False)
        hashed_password = Column(String(255), nullable=False)
        full_name = Column(String(255), nullable=True)
        is_active = Column(Boolean, default=True, nullable=False)
        is_superuser = Column(Boolean, default=False, nullable=False)

        datasets = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
        sessions = relationship("AnalysisSession", back_populates="user", cascade="all, delete-orphan")

except Exception:
    class User(TimestampedUUIDModel):  # type: ignore[no-redef]
        email: str
        full_name: str
