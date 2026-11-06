"""
Dataset & DatasetMetadata ORM Models
"""

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import TimestampedUUIDModel


class Dataset(TimestampedUUIDModel):
    __tablename__ = "datasets"

    # Every dataset belongs to exactly one user; all reads filter on this column.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_format = Column(String(32), nullable=False)  # csv, tsv, xlsx
    storage_uri = Column(String(512), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    checksum_sha256 = Column(String(64), nullable=False, index=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="datasets")
    metadata_entry = relationship("DatasetMetadata", back_populates="dataset", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("AnalysisSession", back_populates="dataset", cascade="all, delete-orphan")
    jobs = relationship("BackgroundJob", back_populates="dataset")


class DatasetMetadata(TimestampedUUIDModel):
    __tablename__ = "dataset_metadata"

    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    inferred_schema = Column(JSON, nullable=False)  # column name -> inferred type
    summary_statistics = Column(JSON, nullable=False)  # full profiler payload
    missingness_report = Column(JSON, nullable=False)
    duplicates_report = Column(JSON, nullable=False)
    quality_warnings = Column(JSON, nullable=False)
    parsed_sheets = Column(JSON, nullable=True)  # sheet names list for Excel
    sample_preview = Column(JSON, nullable=True)  # head, tail, sample records
    # How the file was parsed (delimiter / encoding / sheet). Analyses reload the file with
    # exactly these options so every result matches what the profiler saw.
    parse_options = Column(JSON, nullable=True)

    dataset = relationship("Dataset", back_populates="metadata_entry")
