"""
Schemas Package
Pydantic models for validation, serialization and the OpenAPI contract.
Import from the concrete modules (e.g. `app.schemas.analysis`) to keep dependencies explicit.
"""

from app.schemas.common import APIResponse, BaseSchema, ErrorResponse, PaginationMeta

__all__ = ["APIResponse", "BaseSchema", "ErrorResponse", "PaginationMeta"]
