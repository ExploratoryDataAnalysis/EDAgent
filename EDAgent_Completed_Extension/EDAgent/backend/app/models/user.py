"""
User ORM Model
"""

from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship

from app.models.base import TimestampedUUIDModel


class User(TimestampedUUIDModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    datasets = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("AnalysisSession", back_populates="user", cascade="all, delete-orphan")
