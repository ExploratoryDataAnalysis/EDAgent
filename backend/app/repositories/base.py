"""
Generic Base Repository
Provides consistent asynchronous CRUD operations.
"""

from typing import Generic, TypeVar, Type, Optional, List, Any
import uuid

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic repository pattern interface."""

    def __init__(self, model_class: Type[T], session: Optional[Any] = None):  # type: ignore
        self.model_class = model_class
        self.session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[T]:
        raise NotImplementedError

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        raise NotImplementedError

    async def create(self, entity: T) -> T:
        raise NotImplementedError

    async def update(self, entity: T) -> T:
        raise NotImplementedError

    async def delete(self, entity_id: uuid.UUID) -> bool:
        raise NotImplementedError
