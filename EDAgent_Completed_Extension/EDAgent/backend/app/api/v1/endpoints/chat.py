"""
Conversational analysis endpoint: natural-language question in, computed + explained result out.
The conversation history is looked up server-side from the session, never taken from the client.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import APIResponse
from app.services.ai import orchestrator
from app.services.ai.llm import ai_status

router = APIRouter()


@router.get("/status", summary="AI Configuration Status")
async def chat_status(user: User = Depends(get_current_user)):
    """Whether AI chat is configured. Never includes keys or other secrets."""
    return APIResponse(success=True, message="AI status.", data=ai_status())


@router.post("/message", response_model=APIResponse[ChatResponse], summary="Process Natural Language Analysis Query")
async def process_chat_message(payload: ChatRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await SessionRepository(db).get(payload.session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    dataset = await DatasetRepository(db).get_by_id(session.dataset_id, user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    response = await orchestrator.handle_chat(db, session, dataset, payload.message.strip())
    return APIResponse(success=True, message="Chat response generated.", data=response)
