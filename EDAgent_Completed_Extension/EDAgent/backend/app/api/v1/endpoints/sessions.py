"""
Analysis sessions: one workspace conversation per dataset. Create, list, restore (with the full
history of questions, plans and results), rename and delete.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.analysis import AnalysisRequest
from app.models.session import AnalysisSession
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatKind, ChatTurn
from app.schemas.analysis import StructuredAnalysisPlan
from app.schemas.common import APIResponse
from app.schemas.session import SessionCreate, SessionDetail, SessionRename, SessionSummary
from app.services import analysis_service
from app.services.export_storage import remove_export_file
from app.services import guest_sessions

router = APIRouter()


def _turn(req: AnalysisRequest) -> ChatTurn:
    return ChatTurn(
        request_id=req.id,
        user_query=req.user_query,
        kind=ChatKind(req.kind),
        assistant_message=req.assistant_message,
        explanation_source=req.explanation_source,
        plan=StructuredAnalysisPlan.model_validate(req.structured_plan) if req.structured_plan else None,
        result=analysis_service.result_from_row(req.result) if req.result else None,
        status=req.status,
        created_at=req.created_at,
    )


async def _get_owned(db: AsyncSession, session_id: uuid.UUID, user: User) -> AnalysisSession:
    session = await SessionRepository(db).get(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.post("", response_model=APIResponse[SessionSummary], status_code=201, summary="Create Session")
async def create_session(payload: SessionCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dataset = await DatasetRepository(db).get_by_id(payload.dataset_id, user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    session = await SessionRepository(db).create(user.id, dataset.id, payload.title or f"Analysis of {dataset.name}")
    return APIResponse(
        success=True, message="Session created.",
        data=SessionSummary(id=session.id, dataset_id=dataset.id, dataset_name=dataset.name, title=session.title, turn_count=0, created_at=session.created_at, updated_at=session.updated_at),
    )


@router.get("", response_model=APIResponse[List[SessionSummary]], summary="List Sessions")
async def list_sessions(dataset_id: Optional[uuid.UUID] = Query(None), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await SessionRepository(db).list_for_user(user.id, dataset_id)
    data = [
        SessionSummary(id=s.id, dataset_id=s.dataset_id, dataset_name=name, title=s.title, turn_count=int(n), created_at=s.created_at, updated_at=s.updated_at)
        for s, name, n in rows
    ]
    return APIResponse(success=True, message=f"{len(data)} session(s).", data=data)


@router.get("/{session_id}", response_model=APIResponse[SessionDetail], summary="Restore Session")
async def get_session(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Returns the session with every turn (question, plan, answer, full result) so the UI can restore it."""
    repo = SessionRepository(db)
    session = await _get_owned(db, session_id, user)
    dataset = await DatasetRepository(db).get_by_id(session.dataset_id, user.id)
    turns = await repo.turns(session.id)
    return APIResponse(
        success=True, message="Session restored.",
        data=SessionDetail(
            id=session.id, dataset_id=session.dataset_id, dataset_name=dataset.name if dataset else None, title=session.title,
            turn_count=len(turns), created_at=session.created_at, updated_at=session.updated_at, turns=[_turn(t) for t in turns],
        ),
    )


@router.patch("/{session_id}", response_model=APIResponse[SessionSummary], summary="Rename Session")
async def rename_session(session_id: uuid.UUID, payload: SessionRename, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await _get_owned(db, session_id, user)
    session.title = payload.title.strip()
    await db.flush()
    n = len(await SessionRepository(db).turns(session.id))
    return APIResponse(
        success=True, message="Session renamed.",
        data=SessionSummary(id=session.id, dataset_id=session.dataset_id, title=session.title, turn_count=n, created_at=session.created_at, updated_at=session.updated_at),
    )


@router.delete("/{session_id}", response_model=APIResponse[bool], summary="Delete Session")
async def delete_session(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.is_guest:
        await guest_sessions.lock_active(db, user.id)
    session = await _get_owned(db, session_id, user)
    uris = await SessionRepository(db).delete(session)
    await db.commit()
    for uri in uris:
        remove_export_file(uri)
    return APIResponse(success=True, message="Session deleted with its history, results and reports.", data=True)
