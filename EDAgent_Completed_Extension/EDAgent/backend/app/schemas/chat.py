"""
Conversational Analysis Schemas
Supports conversational follow-ups, clarifying questions, and "cannot answer" boundaries.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import Field

from app.schemas.common import BaseSchema
from app.schemas.analysis import StructuredAnalysisPlan, AnalysisResultResponse


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatKind(str, Enum):
    ANALYSIS = "analysis"
    CLARIFICATION = "clarification"
    CANNOT_ANSWER = "cannot_answer"
    AI_UNAVAILABLE = "ai_unavailable"
    ERROR = "error"


class ChatRequest(BaseSchema):
    """The server owns conversation history (looked up by session), so a client can never
    forge earlier turns or inject fake context."""
    session_id: uuid.UUID
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseSchema):
    session_id: uuid.UUID
    request_id: Optional[uuid.UUID] = None
    kind: ChatKind = ChatKind.ANALYSIS
    reply_text: str
    is_clarification_needed: bool = False
    clarifying_question: Optional[str] = None
    cannot_answer_reason: Optional[str] = None
    analysis_plan: Optional[StructuredAnalysisPlan] = None
    analysis_result: Optional[AnalysisResultResponse] = None
    suggested_questions: List[str] = Field(default_factory=list)
    # "llm" = prose written by the model from computed results; "template" = deterministic
    # fallback text built by the backend (used when the model call failed or is unavailable).
    explanation_source: Optional[str] = None
    ai_configured: bool = True
    created_at: Optional[datetime] = None


class ChatTurn(BaseSchema):
    """One persisted question/answer pair, used for history and session restoration."""
    request_id: uuid.UUID
    user_query: str
    kind: ChatKind
    assistant_message: Optional[str] = None
    explanation_source: Optional[str] = None
    plan: Optional[StructuredAnalysisPlan] = None
    result: Optional[AnalysisResultResponse] = None
    status: str
    created_at: datetime


class ChatMessage(BaseSchema):
    role: MessageRole
    content: str
    result_id: Optional[uuid.UUID] = None
    created_at: Optional[str] = None
