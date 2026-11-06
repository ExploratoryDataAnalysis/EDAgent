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
    iqr: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    zeros_count: Optional[int] = None
    zeros_percentage: Optional[float] = None
    infinite_count: Optional[int] = None
    nan_count: Optional[int] = None


class CategoricalSummary(BaseSchema):
    unique_count: int
    most_frequent_value: Optional[str] = None
    most_frequent_count: Optional[int] = None
    most_frequent_percentage: Optional[float] = None
    top_values: List[Dict[str, Any]] = []  # e.g. [{"value": "Active", "count": 10, "percentage": 83.3}]
    is_high_cardinality: bool = False


class DateSummary(BaseSchema):
    parse_success_rate: float = 0.0
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    invalid_date_count: int = 0
    date_range_days: Optional[int] = None
    timezone_warnings: List[str] = []


class ColumnProfile(BaseSchema):
    name: str
    storage_dtype: str
    inferred_type: str
    semantic_role: SemanticRoleEnum
    role_confidence: float = 1.0
    role_uncertainty_reason: Optional[str] = None
    non_null_count: int
    missing_count: int
    missing_percentage: float
    distinct_count: int
    is_unique: bool
    numeric_summary: Optional[NumericSummary] = None
    categorical_summary: Optional[CategoricalSummary] = None
    date_summary: Optional[DateSummary] = None
    sample_values: List[Any] = []


class QualityWarning(BaseSchema):
    column: Optional[str] = None
    check_type: str  # constant, near_constant, mixed_types, invalid_dates, possible_id, high_missingness, infinite_values, suspicious_values, unusual_distribution, possible_out_of_range
    severity: SeverityEnum
    message: str
    affected_count: Optional[int] = None


class MissingnessReport(BaseSchema):
    total_cells: int
    missing_cells: int
    overall_missing_percentage: float
    per_column: Dict[str, float] = {}  # column_name -> percentage
    columns_with_missing: List[str] = []
    missingness_chart_data: List[Dict[str, Any]] = []
    missingness_patterns: List[Dict[str, Any]] = []


class DuplicatesReport(BaseSchema):
    exact_duplicate_rows_count: int
    exact_duplicate_percentage: float
    candidate_duplicate_keys: List[str] = []
    duplicate_rows_sample: List[Dict[str, Any]] = []


class DatasetOverview(BaseSchema):
    dataset_name: str
    total_rows: int
    total_columns: int
    file_size_bytes: int
    memory_estimate_bytes: int
    selected_sheet: Optional[str] = None
    load_time_seconds: float = 0.0
    profiling_duration_seconds: float = 0.0
    parsing_warnings: List[str] = []


# --- Distribution Analysis Schemas ---

class HistogramBin(BaseSchema):
    bin_start: float
    bin_end: float
    count: int
    percentage: float


class NumericHistogram(BaseSchema):
    column: str
    bins: List[HistogramBin] = []


class NumericBoxplot(BaseSchema):
    column: str
    min: float
    q25: float
    median: float
    q75: float
    max: float
    iqr: float
    lower_fence: float
    upper_fence: float
    outlier_count: int
    outliers_sample: List[float] = []


class CategoricalFrequencyItem(BaseSchema):
    value: str
    count: int
    percentage: float


class CategoricalFrequencyChart(BaseSchema):
    column: str
    categories: List[CategoricalFrequencyItem] = []
    other_count: int = 0
    other_percentage: float = 0.0


class DateDistributionItem(BaseSchema):
    period: str
    count: int


class DateDistributionChart(BaseSchema):
    column: str
    unit: str  # "year", "month", "day"
    buckets: List[DateDistributionItem] = []


class TimeDistributionChart(BaseSchema):
    column: str
    day_of_week: Dict[str, int] = {}
    hour_of_day: Dict[str, int] = {}


class DistributionAnalysis(BaseSchema):
    histograms: List[NumericHistogram] = []
    boxplots: List[NumericBoxplot] = []
    categorical_frequencies: List[CategoricalFrequencyChart] = []
    date_distributions: List[DateDistributionChart] = []
    time_distributions: List[TimeDistributionChart] = []


# --- Relationship Analysis Schemas ---

class CorrelationMatrix(BaseSchema):
    columns: List[str] = []
    matrix: Dict[str, Dict[str, Optional[float]]] = {}


class CategoricalAssociation(BaseSchema):
    column_x: str
    column_y: str
    cramers_v: float
    chi2: float
    p_value: float


class RelationshipAnalysis(BaseSchema):
    pearson: Optional[CorrelationMatrix] = None
    spearman: Optional[CorrelationMatrix] = None
    categorical_associations: List[CategoricalAssociation] = []
    warnings: List[str] = []
    excluded_columns: List[str] = []


# --- Recommendation Schemas ---

class SuggestedAnalysis(BaseSchema):
    title: str
    description: str
    operation: str  # "group_by", "trend", "histogram", "boxplot", "correlation", "outlier", "missingness"
    columns: List[str] = []
    rationale: str


class ProfilerResultResponse(BaseSchema):
    dataset_id: Optional[uuid.UUID] = None
    overview: DatasetOverview
    columns: List[ColumnProfile]
    missingness: MissingnessReport
    duplicates: DuplicatesReport
    distributions: Optional[DistributionAnalysis] = None
    quality_warnings: List[QualityWarning] = []
    relationships: Optional[RelationshipAnalysis] = None
    suggested_analyses: List[SuggestedAnalysis] = []
    suggested_questions: List[str] = []
    correlation_matrix: Optional[Dict[str, Dict[str, Optional[float]]]] = None
    computed_at: str
