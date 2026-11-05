"""
Automatic Dataset Profiler Schemas
Directly maps to Section 5.2 and Appendix A of the project specification.
"""

import uuid
from enum import Enum
from typing import List, Dict, Any, Optional
from app.schemas.common import BaseSchema


class SemanticRoleEnum(str, Enum):
    IDENTIFIER = "identifier"
    MEASURE = "measure"
    CATEGORY = "category"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    TEXT = "text"
    UNKNOWN = "unknown"


class SeverityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NumericSummary(BaseSchema):
    count: int
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    q25: Optional[float] = None
    median: Optional[float] = None
    q75: Optional[float] = None
    max: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    zeros_count: Optional[int] = None
    infinite_count: Optional[int] = None


class CategoricalSummary(BaseSchema):
    unique_count: int
    top_values: List[Dict[str, Any]]  # e.g. [{"value": "Active", "count": 10, "percentage": 83.3}]
    is_high_cardinality: bool = False


class ColumnProfile(BaseSchema):
    name: str
    storage_dtype: str
    inferred_type: str
    semantic_role: SemanticRoleEnum
    role_confidence: float = 1.0
    non_null_count: int
    missing_count: int
    missing_percentage: float
    distinct_count: int
    is_unique: bool
    numeric_summary: Optional[NumericSummary] = None
    categorical_summary: Optional[CategoricalSummary] = None
    sample_values: List[Any] = []


class QualityWarning(BaseSchema):
    column: Optional[str] = None
    check_type: str  # constant, near_constant, mixed_types, invalid_dates, possible_id, high_missingness
    severity: SeverityEnum
    message: str
    affected_count: Optional[int] = None


class MissingnessReport(BaseSchema):
    total_cells: int
    missing_cells: int
    overall_missing_percentage: float
    per_column: Dict[str, float]  # column_name -> percentage
    columns_with_missing: List[str]


class DuplicatesReport(BaseSchema):
    exact_duplicate_rows_count: int
    exact_duplicate_percentage: float
    candidate_duplicate_keys: List[str] = []


class DatasetOverview(BaseSchema):
    dataset_name: str
    total_rows: int
    total_columns: int
    file_size_bytes: int
    memory_estimate_bytes: int
    selected_sheet: Optional[str] = None
    load_time_seconds: float
    parsing_warnings: List[str] = []


class ProfilerResultResponse(BaseSchema):
    dataset_id: uuid.UUID
    overview: DatasetOverview
    columns: List[ColumnProfile]
    missingness: MissingnessReport
    duplicates: DuplicatesReport
    quality_warnings: List[QualityWarning]
    suggested_questions: List[str]
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
    computed_at: str
