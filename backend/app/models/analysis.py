"""
AnalysisRequest & AnalysisResult ORM Models
"""

import uuid
from app.models.base import TimestampedUUIDModel

try:
    from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON, Boolean, Text
    from sqlalchemy.dialects.postgresql import UUID
    from sqlalchemy.orm import relationship

    class AnalysisRequest(TimestampedUUIDModel):
        __tablename__ = "analysis_requests"

        session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
        user_query = Column(Text, nullable=False)
        structured_plan = Column(JSON, nullable=True)  # machine-validated JSON plan
        status = Column(String(32), default="PENDING", nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED
        error_message = Column(Text, nullable=True)

        session = relationship("AnalysisSession", back_populates="requests")
        result = relationship("AnalysisResult", back_populates="request", uselist=False, cascade="all, delete-orphan")

    class AnalysisResult(TimestampedUUIDModel):
        __tablename__ = "analysis_results"

        request_id = Column(UUID(as_uuid=True), ForeignKey("analysis_requests.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
        operation_type = Column(String(64), nullable=False)  # histogram, boxplot, correlation, group_by, etc.
        summary_text = Column(Text, nullable=False)  # AI plain-language explanation
        execution_code = Column(Text, nullable=False)  # reproducible Python/SQL code executed
        records_examined = Column(Integer, nullable=False)
        records_used = Column(Integer, nullable=False)
        is_sampled = Column(Boolean, default=False, nullable=False)
        sample_size = Column(Integer, nullable=True)
        plot_spec = Column(JSON, nullable=True)  # Plotly JSON specification
        data_table = Column(JSON, nullable=True)  # summary/tabular result rows
        warnings = Column(JSON, nullable=False, default=list)  # statistical / data assumptions warnings
        execution_time_ms = Column(Float, nullable=False)

        request = relationship("AnalysisRequest", back_populates="result")

except Exception:
    class AnalysisRequest(TimestampedUUIDModel):  # type: ignore[no-redef]
        user_query: str

    class AnalysisResult(TimestampedUUIDModel):  # type: ignore[no-redef]
        operation_type: str
