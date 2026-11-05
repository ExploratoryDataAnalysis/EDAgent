"""
Conversational Analysis Schemas
Supports conversational follow-ups, clarifying questions, and "cannot answer" boundaries.
"""

import uuid
from enum import Enum
from typing import List, Optional, Dict, Any
from app.schemas.common import BaseSchema
from app.schemas.analysis import StructuredAnalysisPlan, AnalysisResultResponse


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseSchema):
    role: MessageRole
    content: str
    result_id: Optional[uuid.UUID] = None
    created_at: Optional[str] = None


class ChatRequest(BaseSchema):
    session_id: uuid.UUID
    message: str
    conversation_history: List[ChatMessage] = []


class ChatResponse(BaseSchema):
    session_id: uuid.UUID
    reply_text: str
    is_clarification_needed: bool = False
    clarifying_question: Optional[str] = None
    cannot_answer_reason: Optional[str] = None
    analysis_plan: Optional[StructuredAnalysisPlan] = None
    analysis_result: Optional[AnalysisResultResponse] = None
