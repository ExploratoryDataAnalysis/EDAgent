"""
Dataset Repository
Handles asynchronous database operations for Dataset and DatasetMetadata entities.
"""

import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dataset import Dataset, DatasetMetadata


class DatasetRepository:
    """Repository for managing datasets and their ingestion metadata."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, dataset: Dataset, metadata: Optional[DatasetMetadata] = None) -> Dataset:
        """Persists a new dataset and optional metadata."""
        self.db.add(dataset)
        if metadata:
            metadata.dataset_id = dataset.id
            self.db.add(metadata)
        await self.db.flush()
        await self.db.refresh(dataset)
        return dataset

    async def get_by_id(
        self, dataset_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
    ) -> Optional[Dataset]:
        """Retrieves a dataset by ID, optionally verifying user ownership."""
        query = (
            select(Dataset)
            .options(selectinload(Dataset.metadata_entry))
            .where(and_(Dataset.id == dataset_id, Dataset.is_deleted == False))  # noqa: E712
        )
        result = await self.db.execute(query)
        dataset = result.scalar_one_or_none()

        if dataset and user_id is not None:
            # If dataset has a user_id and it doesn't match the requesting user, enforce access control
            if dataset.user_id is not None and dataset.user_id != user_id:
                return None

        return dataset

    async def list_datasets(
        self,
        user_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dataset], int]:
        """Lists active datasets with pagination."""
        conditions = [Dataset.is_deleted == False]  # noqa: E712
        if user_id is not None:
            conditions.append(Dataset.user_id == user_id)

        # Count total
        count_query = select(func.count(Dataset.id)).where(and_(*conditions))
        count_res = await self.db.execute(count_query)
        total = count_res.scalar_one() or 0

        # Fetch records
        query = (
            select(Dataset)
            .options(selectinload(Dataset.metadata_entry))
            .where(and_(*conditions))
            .order_by(Dataset.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        datasets = list(result.scalars().all())

        return datasets, total

    async def update(self, dataset: Dataset) -> Dataset:
        """Updates dataset record and flushes to database."""
        await self.db.flush()
        await self.db.refresh(dataset)
        return dataset

    async def delete(self, dataset_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> bool:
        """Soft-deletes a dataset."""
        dataset = await self.get_by_id(dataset_id, user_id=user_id)
        if not dataset:
            return False
        dataset.is_deleted = True
        await self.db.flush()
        return True
