"""
GeneratedReport ORM Model
"""

from sqlalchemy import Column, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import TimestampedUUIDModel


class GeneratedReport(TimestampedUUIDModel):
    __tablename__ = "generated_reports"

    session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    format = Column(String(16), default="pdf", nullable=False)  # pdf, html
    status = Column(String(16), default="PENDING", nullable=False)  # PENDING, PROCESSING, SUCCESS, FAILURE
    storage_uri = Column(String(512), nullable=True)  # set once the file exists
    included_sections = Column(JSON, nullable=False)  # list of section keys
    config = Column(JSON, nullable=True)  # full request so a report can be regenerated
    dataset_fingerprint = Column(String(64), nullable=False)
    error_message = Column(Text, nullable=True)

    session = relationship("AnalysisSession", back_populates="reports")
