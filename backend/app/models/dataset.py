"""
Dataset & DatasetMetadata ORM Models
"""

import uuid
from app.models.base import TimestampedUUIDModel

try:
    from sqlalchemy import Column, String, Integer, BigInteger, ForeignKey, JSON, Boolean
    from sqlalchemy.dialects.postgresql import UUID
    from sqlalchemy.orm import relationship

    class Dataset(TimestampedUUIDModel):
        __tablename__ = "datasets"

        user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
        name = Column(String(255), nullable=False)
        original_filename = Column(String(255), nullable=False)
        file_format = Column(String(32), nullable=False)  # csv, tsv, xlsx, parquet
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
        inferred_schema = Column(JSON, nullable=False)  # column names, types, semantic roles
        summary_statistics = Column(JSON, nullable=False)
        missingness_report = Column(JSON, nullable=False)
        duplicates_report = Column(JSON, nullable=False)
        quality_warnings = Column(JSON, nullable=False)
        parsed_sheets = Column(JSON, nullable=True)  # sheet names list for Excel
        sample_preview = Column(JSON, nullable=True)  # head, tail, sample records

        dataset = relationship("Dataset", back_populates="metadata_entry")

except Exception:
    class Dataset(TimestampedUUIDModel):  # type: ignore[no-redef]
        name: str
        storage_uri: str

    class DatasetMetadata(TimestampedUUIDModel):  # type: ignore[no-redef]
        dataset_id: uuid.UUID
