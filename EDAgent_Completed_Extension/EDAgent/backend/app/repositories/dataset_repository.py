"""
Dataset Repository
Asynchronous persistence for datasets and their metadata. Every query is scoped to the
owning user, so a dataset id from another account behaves exactly like a missing one.
"""

import uuid
from typing import List, Optional, Tuple

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import AnalysisRequest, AnalysisResult
from app.models.dataset import Dataset, DatasetMetadata
from app.models.job import BackgroundJob
from app.models.report import GeneratedReport
from app.models.session import AnalysisSession


class DatasetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, dataset: Dataset, metadata: Optional[DatasetMetadata] = None) -> Dataset:
        self.db.add(dataset)
        # Flush the parent first so the metadata FK is satisfied on every backend.
        await self.db.flush()
        if metadata:
            metadata.dataset_id = dataset.id
            self.db.add(metadata)
        await self.db.flush()
        await self.db.refresh(dataset)
        return dataset

    async def get_by_id(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dataset]:
        """Returns the dataset only if it exists, is not deleted and belongs to `user_id`."""
        query = (
            select(Dataset)
            .options(selectinload(Dataset.metadata_entry))
            .where(and_(Dataset.id == dataset_id, Dataset.user_id == user_id, Dataset.is_deleted == False))  # noqa: E712
        )
        return (await self.db.execute(query)).scalar_one_or_none()

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        q = select(func.count(Dataset.id)).where(and_(Dataset.user_id == user_id, Dataset.is_deleted == False))  # noqa: E712
        return (await self.db.execute(q)).scalar_one() or 0

    async def list_datasets(self, user_id: uuid.UUID, skip: int = 0, limit: int = 50) -> Tuple[List[Dataset], int]:
        conditions = [Dataset.is_deleted == False, Dataset.user_id == user_id]  # noqa: E712
        total = (await self.db.execute(select(func.count(Dataset.id)).where(and_(*conditions)))).scalar_one() or 0
        query = (
            select(Dataset)
            .options(selectinload(Dataset.metadata_entry))
            .where(and_(*conditions))
            .order_by(Dataset.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list((await self.db.execute(query)).scalars().all()), total

    async def update(self, dataset: Dataset) -> Dataset:
        await self.db.flush()
        await self.db.refresh(dataset)
        return dataset

    async def purge(self, dataset: Dataset) -> List[str]:
        """
        Permanently removes a dataset and everything derived from it, children first (explicit
        deletes avoid relying on database-level cascades, which SQLite does not enforce by
        default). Returns the storage URIs of generated report files so the caller can delete
        them from disk.
        """
        session_ids = [
            row[0] for row in (await self.db.execute(select(AnalysisSession.id).where(AnalysisSession.dataset_id == dataset.id)))
        ]
        report_uris: List[str] = []
        if session_ids:
            report_uris = [
                row[0]
                for row in (await self.db.execute(
                    select(GeneratedReport.storage_uri).where(GeneratedReport.session_id.in_(session_ids))
                ))
                if row[0]
            ]
            request_ids = select(AnalysisRequest.id).where(AnalysisRequest.session_id.in_(session_ids))
            await self.db.execute(delete(AnalysisResult).where(AnalysisResult.request_id.in_(request_ids)))
            await self.db.execute(delete(AnalysisRequest).where(AnalysisRequest.session_id.in_(session_ids)))
            await self.db.execute(delete(GeneratedReport).where(GeneratedReport.session_id.in_(session_ids)))
            await self.db.execute(delete(BackgroundJob).where(BackgroundJob.session_id.in_(session_ids)))
            await self.db.execute(delete(AnalysisSession).where(AnalysisSession.id.in_(session_ids)))
        await self.db.execute(delete(BackgroundJob).where(BackgroundJob.dataset_id == dataset.id))
        await self.db.execute(delete(DatasetMetadata).where(DatasetMetadata.dataset_id == dataset.id))
        await self.db.execute(delete(Dataset).where(Dataset.id == dataset.id))
        await self.db.flush()
        return report_uris
