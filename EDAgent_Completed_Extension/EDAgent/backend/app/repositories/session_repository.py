"""
Session Repository
Analysis sessions, their conversation turns and stored results, always scoped by owner.
"""

import uuid
from typing import List, Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import AnalysisRequest, AnalysisResult
from app.models.dataset import Dataset
from app.models.report import GeneratedReport
from app.models.session import AnalysisSession


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, dataset_id: uuid.UUID, title: str) -> AnalysisSession:
        session = AnalysisSession(user_id=user_id, dataset_id=dataset_id, title=title)
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Optional[AnalysisSession]:
        q = select(AnalysisSession).where(and_(AnalysisSession.id == session_id, AnalysisSession.user_id == user_id))
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID, dataset_id: Optional[uuid.UUID] = None) -> List[tuple]:
        """Returns (session, dataset_name, turn_count) tuples, newest activity first."""
        turn_count = (
            select(AnalysisRequest.session_id, func.count(AnalysisRequest.id).label("n"))
            .group_by(AnalysisRequest.session_id)
            .subquery()
        )
        q = (
            select(AnalysisSession, Dataset.name, func.coalesce(turn_count.c.n, 0))
            .join(Dataset, Dataset.id == AnalysisSession.dataset_id)
            .outerjoin(turn_count, turn_count.c.session_id == AnalysisSession.id)
            .where(AnalysisSession.user_id == user_id)
            .order_by(AnalysisSession.updated_at.desc())
        )
        if dataset_id:
            q = q.where(AnalysisSession.dataset_id == dataset_id)
        return [tuple(r) for r in (await self.db.execute(q)).all()]

    async def latest_for_dataset(self, user_id: uuid.UUID, dataset_id: uuid.UUID) -> Optional[AnalysisSession]:
        q = (
            select(AnalysisSession)
            .where(and_(AnalysisSession.user_id == user_id, AnalysisSession.dataset_id == dataset_id))
            .order_by(AnalysisSession.updated_at.desc())
            .limit(1)
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def turns(self, session_id: uuid.UUID) -> List[AnalysisRequest]:
        """All conversation turns oldest-first, with their results eagerly loaded."""
        q = (
            select(AnalysisRequest)
            .options(selectinload(AnalysisRequest.result))
            .where(AnalysisRequest.session_id == session_id)
            .order_by(AnalysisRequest.created_at.asc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_turn(self, request_id: uuid.UUID, user_id: uuid.UUID) -> Optional[AnalysisRequest]:
        q = (
            select(AnalysisRequest)
            .options(selectinload(AnalysisRequest.result))
            .join(AnalysisSession, AnalysisSession.id == AnalysisRequest.session_id)
            .where(and_(AnalysisRequest.id == request_id, AnalysisSession.user_id == user_id))
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_result(self, result_id: uuid.UUID, user_id: uuid.UUID) -> Optional[AnalysisResult]:
        q = (
            select(AnalysisResult)
            .join(AnalysisRequest, AnalysisRequest.id == AnalysisResult.request_id)
            .join(AnalysisSession, AnalysisSession.id == AnalysisRequest.session_id)
            .where(and_(AnalysisResult.id == result_id, AnalysisSession.user_id == user_id))
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def delete(self, session: AnalysisSession) -> List[str]:
        """Deletes a session with its turns, results and reports; returns report file URIs."""
        uris = [
            r[0]
            for r in (await self.db.execute(select(GeneratedReport.storage_uri).where(GeneratedReport.session_id == session.id)))
            if r[0]
        ]
        request_ids = select(AnalysisRequest.id).where(AnalysisRequest.session_id == session.id)
        await self.db.execute(delete(AnalysisResult).where(AnalysisResult.request_id.in_(request_ids)))
        await self.db.execute(delete(AnalysisRequest).where(AnalysisRequest.session_id == session.id))
        await self.db.execute(delete(GeneratedReport).where(GeneratedReport.session_id == session.id))
        await self.db.execute(delete(AnalysisSession).where(AnalysisSession.id == session.id))
        await self.db.flush()
        return uris
