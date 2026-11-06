"""
Report Generation & Export Centre Schemas
Directly maps to Section 6.2 and 6.3 of the project specification.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import Field

from app.schemas.common import BaseSchema


class ReportSectionEnum(str, Enum):
    """The 16 sections of the EDA report (numbering matches the specification)."""
    COVER = "cover"                                    # 1  cover page and dataset information
    EXECUTIVE_SUMMARY = "executive_summary"            # 2
    DIMENSIONS_INVENTORY = "dimensions_inventory"      # 3  dimensions and column inventory
    TYPES_ROLES = "types_roles"                        # 4  data types and semantic roles
    DESCRIPTIVE_STATS = "descriptive_stats"            # 5
    MISSING_VALUES = "missing_values"                  # 6
    DUPLICATES = "duplicates"                          # 7
    QUALITY_FINDINGS = "quality_findings"              # 8
    UNIVARIATE = "univariate"                          # 9  univariate distributions
    BIVARIATE_MULTIVARIATE = "bivariate_multivariate"  # 10
    CORRELATIONS = "correlations"                      # 11
    TIME_ANALYSIS = "time_analysis"                    # 12 where applicable
    USER_ANALYSES = "user_analyses"                    # 13
    CHARTS_TABLES = "charts_tables"                    # 14
    INTERPRETATION_LIMITATIONS = "interpretation_limitations"  # 15
    REPRODUCIBILITY = "reproducibility"                # 16 reproducibility information and appendix


class ReportFormatEnum(str, Enum):
    PDF = "pdf"
    HTML = "html"


DEFAULT_SECTIONS = list(ReportSectionEnum)


class ReportGenerateRequest(BaseSchema):
    session_id: uuid.UUID
    title: str = Field(default="Exploratory Data Analysis Report", max_length=200)
    format: ReportFormatEnum = ReportFormatEnum.PDF
    concise_mode: bool = False
    included_sections: List[ReportSectionEnum] = Field(default_factory=lambda: list(DEFAULT_SECTIONS))
    # Which of the session's analyses to include; None = all of them.
    included_result_ids: Optional[List[uuid.UUID]] = None


class ReportResponse(BaseSchema):
    report_id: uuid.UUID
    session_id: uuid.UUID
    title: str
    format: ReportFormatEnum
    status: str
    download_url: Optional[str] = None
    dataset_fingerprint: str
    created_at: datetime
    job_id: Optional[str] = None
    error_message: Optional[str] = None
    config: Optional[ReportGenerateRequest] = None
