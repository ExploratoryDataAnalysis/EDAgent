"""
AnalysisSession ORM Model
"""

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import TimestampedUUIDModel


class AnalysisSession(TimestampedUUIDModel):
    __tablename__ = "analysis_sessions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New Analysis Session")

    user = relationship("User", back_populates="sessions")
    dataset = relationship("Dataset", back_populates="sessions")
    requests = relationship("AnalysisRequest", back_populates="session", cascade="all, delete-orphan", order_by="AnalysisRequest.created_at")
    reports = relationship("GeneratedReport", back_populates="session", cascade="all, delete-orphan")
