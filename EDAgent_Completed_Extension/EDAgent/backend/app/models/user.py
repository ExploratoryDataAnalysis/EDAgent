"""
User ORM Model
"""

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampedUUIDModel

GUEST_EMAIL_SUFFIX = "@guest.edagent.example.com"
GUEST_PASSWORD_MARKER = "!"


class User(TimestampedUUIDModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    datasets = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("AnalysisSession", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_guest(self) -> bool:
        return self.email.endswith(GUEST_EMAIL_SUFFIX) and self.hashed_password == GUEST_PASSWORD_MARKER


class GuestLease(Base):
    """The guest user owns workspace rows; the lease owns expiry and the action budget."""

    __tablename__ = "guest_leases"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    expires_at = Column(BigInteger, nullable=False, index=True)  # UTC Unix seconds
    actions = Column(Integer, default=0, nullable=False)
