"""
Common API Schemas and Response Wrappers
"""

from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Operation successful"
    data: Optional[T] = None
    errors: Optional[List[str]] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    errors: List[str] = []
    error_code: Optional[str] = None


class PaginationMeta(BaseModel):
    total_count: int
    page: int
    page_size: int
    total_pages: int
