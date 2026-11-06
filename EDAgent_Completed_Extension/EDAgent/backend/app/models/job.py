"""
BackgroundJob ORM Model
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import TimestampedUUIDModel


class BackgroundJob(TimestampedUUIDModel):
    __tablename__ = "background_jobs"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    job_type = Column(String(64), nullable=False)  # profiling, analysis, report_generation, conversion
    status = Column(String(32), default="PENDING", nullable=False, index=True)  # PENDING, PROCESSING, SUCCESS, FAILURE, REVOKED
    progress_percentage = Column(Float, default=0.0, nullable=False)
    status_message = Column(String(255), default="Job enqueued", nullable=False)
    error_details = Column(Text, nullable=True)
    result_ref = Column(JSON, nullable=True)  # e.g. {"report_id": "..."}
    completed_at = Column(DateTime(timezone=True), nullable=True)

    dataset = relationship("Dataset", back_populates="jobs")
