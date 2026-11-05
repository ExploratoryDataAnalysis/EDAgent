"""
Conversational Analysis (AI Chat) Endpoints
"""

from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import APIResponse

router = APIRouter()


@router.post("/message", response_model=APIResponse[ChatResponse], summary="Process Natural Language Analysis Query")
async def process_chat_message(payload: ChatRequest):
    """
    Translates user natural language questions into structured plans,
    triggers backend computation, and delivers plain-language explanations with guardrails.
    """
    return APIResponse(
        success=True,
        message="Chat response generated.",
        data=None
    )
