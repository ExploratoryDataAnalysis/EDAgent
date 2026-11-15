"""
AnalysisRequest & AnalysisResult ORM Models

One AnalysisRequest is one conversational turn (a question and the assistant's answer).
Turns that produced a computation also own an AnalysisResult.
"""

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import TimestampedUUIDModel


class AnalysisRequest(TimestampedUUIDModel):
    __tablename__ = "analysis_requests"

    session_id = Column(UUID(as_uuid=True), ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_query = Column(Text, nullable=False)
    structured_plan = Column(JSON, nullable=True)  # machine-validated JSON plan
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, COMPLETED, FAILED
    # analysis | clarification | cannot_answer | ai_unavailable | error
    kind = Column(String(32), default="analysis", nullable=False)
    assistant_message = Column(Text, nullable=True)  # what the user saw as the reply
    explanation_source = Column(String(16), nullable=True)  # "guided", "fallback", "template", or legacy "llm"
    error_message = Column(Text, nullable=True)

    session = relationship("AnalysisSession", back_populates="requests")
    result = relationship("AnalysisResult", back_populates="request", uselist=False, cascade="all, delete-orphan")


class AnalysisResult(TimestampedUUIDModel):
    __tablename__ = "analysis_results"

    request_id = Column(UUID(as_uuid=True), ForeignKey("analysis_requests.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    operation_type = Column(String(64), nullable=False)
    summary_text = Column(Text, nullable=False)
    execution_code = Column(Text, nullable=False)  # reproducible Python snippet
    records_examined = Column(Integer, nullable=False)
    records_used = Column(Integer, nullable=False)
    is_sampled = Column(Boolean, default=False, nullable=False)
    sample_size = Column(Integer, nullable=True)
    plot_spec = Column(JSON, nullable=True)  # first chart, kept for quick access
    data_table = Column(JSON, nullable=True)  # first table rows
    warnings = Column(JSON, nullable=False, default=list)
    execution_time_ms = Column(Float, nullable=False)
    # The complete structured result object (tables, charts, methodology, ...). Everything
    # shown in the UI, reports and exports is rebuilt from this single source of truth.
    result_payload = Column(JSON, nullable=True)

    request = relationship("AnalysisRequest", back_populates="result")
