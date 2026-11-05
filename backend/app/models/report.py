"""
GeneratedReport ORM Model
"""

import uuid
from app.models.base import TimestampedUUIDModel

try:
    from sqlalchemy import Column, String, ForeignKey, JSON
    from sqlalchemy.dialects.postgresql import UUID
    from sqlalchemy.orm import relationship

    class GeneratedReport(TimestampedUUIDModel):
        __tablename__ = "generated_reports"

        session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
        title = Column(String(255), nullable=False)
        format = Column(String(16), default="PDF", nullable=False)  # PDF, HTML
        storage_uri = Column(String(512), nullable=False)
        included_sections = Column(JSON, nullable=False)  # list of section keys
        dataset_fingerprint = Column(String(64), nullable=False)

        session = relationship("AnalysisSession", back_populates="reports")

except Exception:
    class GeneratedReport(TimestampedUUIDModel):  # type: ignore[no-redef]
        title: str
