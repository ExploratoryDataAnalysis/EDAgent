"""
Report Generation & Export Centre Schemas
Directly maps to Section 6.2 and 6.3 of the project specification.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional
from app.schemas.common import BaseSchema


class ReportSectionEnum(str, Enum):
    COVER = "cover"
    EXECUTIVE_SUMMARY = "executive_summary"
    DATASET_STRUCTURE = "dataset_structure"
    DATA_QUALITY = "data_quality"
    UNIVARIATE_ANALYSIS = "univariate_analysis"
    BIVARIATE_MULTIVARIATE = "bivariate_multivariate"
    TIME_GEOGRAPHY = "time_geography"
    USER_REQUESTED_ANALYSES = "user_requested_analyses"
    LIMITATIONS = "limitations"
    APPENDIX = "appendix"


class ReportFormatEnum(str, Enum):
    PDF = "pdf"
    HTML = "html"


class ReportGenerateRequest(BaseSchema):
    session_id: uuid.UUID
    title: str = "Exploratory Data Analysis Report"
    format: ReportFormatEnum = ReportFormatEnum.PDF
    concise_mode: bool = False
    included_sections: List[ReportSectionEnum] = [
        ReportSectionEnum.COVER,
        ReportSectionEnum.EXECUTIVE_SUMMARY,
        ReportSectionEnum.DATASET_STRUCTURE,
        ReportSectionEnum.DATA_QUALITY,
        ReportSectionEnum.UNIVARIATE_ANALYSIS,
        ReportSectionEnum.BIVARIATE_MULTIVARIATE,
        ReportSectionEnum.USER_REQUESTED_ANALYSES,
        ReportSectionEnum.LIMITATIONS,
        ReportSectionEnum.APPENDIX,
    ]


class ReportResponse(BaseSchema):
    report_id: uuid.UUID
    session_id: uuid.UUID
    title: str
    format: ReportFormatEnum
    download_url: str
    dataset_fingerprint: str
    created_at: datetime
