"""
BackgroundJob ORM Model
"""

from datetime import datetime
from app.models.base import TimestampedUUIDModel

try:
    from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Text
    from sqlalchemy.dialects.postgresql import UUID
    from sqlalchemy.orm import relationship

    class BackgroundJob(TimestampedUUIDModel):
        __tablename__ = "background_jobs"

        dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True)
        session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
        job_type = Column(String(64), nullable=False)  # PROFILING, ANALYSIS, REPORT_GENERATION, CONVERSION
        status = Column(String(32), default="PENDING", nullable=False, index=True)  # PENDING, PROCESSING, SUCCESS, FAILURE, REVOKED
        progress_percentage = Column(Float, default=0.0, nullable=False)
        status_message = Column(String(255), default="Job enqueued", nullable=False)
        error_details = Column(Text, nullable=True)
        completed_at = Column(DateTime(timezone=True), nullable=True)

        dataset = relationship("Dataset", back_populates="jobs")

except Exception:
    class BackgroundJob(TimestampedUUIDModel):  # type: ignore[no-redef]
        job_type: str
        status: str
