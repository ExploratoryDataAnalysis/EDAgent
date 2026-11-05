"""
Core Application Configuration
Loads environment variables with robust typing and defaults.
"""

import os
from typing import List
from pydantic import BaseModel, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            case_sensitive=False
        )

        # Environment
        ENVIRONMENT: str = "development"
        DEBUG: bool = True
        APP_NAME: str = "EDAgent"
        API_V1_STR: str = "/api/v1"
        SECRET_KEY: str = "edagent-secret-key-change-in-production-min-32-chars"
        ALLOWED_HOSTS: List[str] = ["*"]
        CORS_ORIGINS: List[str] = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173"
        ]

        # Server
        HOST: str = "127.0.0.1"
        PORT: int = 8000

        # Database
        DATABASE_URL: str = "sqlite+aiosqlite:///./edagent.db"
        DATABASE_URL_SYNC: str = "sqlite:///./edagent.db"

        # Redis & Celery
        REDIS_URL: str = "redis://localhost:6379/0"
        CELERY_BROKER_URL: str = "redis://localhost:6379/1"
        CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
        CELERY_TASK_ALWAYS_EAGER: bool = True

        # Storage
        STORAGE_BACKEND: str = "local"
        LOCAL_STORAGE_PATH: str = "./data/uploads"
        EXPORTS_STORAGE_PATH: str = "./data/exports"
        MAX_UPLOAD_SIZE_MB: int = 100

        # S3 / MinIO
        S3_ENDPOINT_URL: str = "http://localhost:9000"
        S3_ACCESS_KEY_ID: str = "minioadmin"
        S3_SECRET_ACCESS_KEY: str = "minioadmin"
        S3_BUCKET_NAME: str = "edagent-data"
        S3_REGION: str = "us-east-1"

        # AI / LLM
        LLM_PROVIDER: str = "mock"
        LLM_MODEL: str = "gpt-4o"
        LLM_API_KEY: str = ""
        LLM_MAX_TOKENS: int = 2048
        LLM_TEMPERATURE: float = 0.1

        # Quotas and Limits
        MAX_CONCURRENT_JOBS_PER_USER: int = 2
        JOB_TIMEOUT_SECONDS: int = 300
        MEMORY_LIMIT_MB: int = 2048
        ROW_LIMIT_PREVIEW: int = 100
        DEFAULT_SAMPLE_SIZE: int = 10000

        # Security & Guardrails
        ENABLE_SANDBOX: bool = True
        PREVENT_SSRF: bool = True

except ImportError:
    # Fallback to pure Pydantic v2 BaseModel reading from os.environ
    class Settings(BaseModel):  # type: ignore[no-redef]
        ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
        DEBUG: bool = Field(default_factory=lambda: os.getenv("DEBUG", "True").lower() in ("true", "1"))
        APP_NAME: str = Field(default_factory=lambda: os.getenv("APP_NAME", "EDAgent"))
        API_V1_STR: str = Field(default_factory=lambda: os.getenv("API_V1_STR", "/api/v1"))
        SECRET_KEY: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "edagent-secret-key-change-in-production-min-32-chars"))
        ALLOWED_HOSTS: List[str] = ["*"]
        CORS_ORIGINS: List[str] = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173"
        ]
        HOST: str = Field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
        PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
        DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./edagent.db"))
        DATABASE_URL_SYNC: str = Field(default_factory=lambda: os.getenv("DATABASE_URL_SYNC", "sqlite:///./edagent.db"))
        REDIS_URL: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        CELERY_BROKER_URL: str = Field(default_factory=lambda: os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"))
        CELERY_RESULT_BACKEND: str = Field(default_factory=lambda: os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"))
        CELERY_TASK_ALWAYS_EAGER: bool = Field(default_factory=lambda: os.getenv("CELERY_TASK_ALWAYS_EAGER", "True").lower() in ("true", "1"))
        STORAGE_BACKEND: str = Field(default_factory=lambda: os.getenv("STORAGE_BACKEND", "local"))
        LOCAL_STORAGE_PATH: str = Field(default_factory=lambda: os.getenv("LOCAL_STORAGE_PATH", "./data/uploads"))
        EXPORTS_STORAGE_PATH: str = Field(default_factory=lambda: os.getenv("EXPORTS_STORAGE_PATH", "./data/exports"))
        MAX_UPLOAD_SIZE_MB: int = Field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_MB", "100")))
        S3_ENDPOINT_URL: str = Field(default_factory=lambda: os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"))
        S3_ACCESS_KEY_ID: str = Field(default_factory=lambda: os.getenv("S3_ACCESS_KEY_ID", "minioadmin"))
        S3_SECRET_ACCESS_KEY: str = Field(default_factory=lambda: os.getenv("S3_SECRET_ACCESS_KEY", "minioadmin"))
        S3_BUCKET_NAME: str = Field(default_factory=lambda: os.getenv("S3_BUCKET_NAME", "edagent-data"))
        S3_REGION: str = Field(default_factory=lambda: os.getenv("S3_REGION", "us-east-1"))
        LLM_PROVIDER: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
        LLM_MODEL: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))
        LLM_API_KEY: str = Field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
        LLM_MAX_TOKENS: int = Field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "2048")))
        LLM_TEMPERATURE: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1")))
        MAX_CONCURRENT_JOBS_PER_USER: int = Field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_JOBS_PER_USER", "2")))
        JOB_TIMEOUT_SECONDS: int = Field(default_factory=lambda: int(os.getenv("JOB_TIMEOUT_SECONDS", "300")))
        MEMORY_LIMIT_MB: int = Field(default_factory=lambda: int(os.getenv("MEMORY_LIMIT_MB", "2048")))
        ROW_LIMIT_PREVIEW: int = Field(default_factory=lambda: int(os.getenv("ROW_LIMIT_PREVIEW", "100")))
        DEFAULT_SAMPLE_SIZE: int = Field(default_factory=lambda: int(os.getenv("DEFAULT_SAMPLE_SIZE", "10000")))
        ENABLE_SANDBOX: bool = Field(default_factory=lambda: os.getenv("ENABLE_SANDBOX", "True").lower() in ("true", "1"))
        PREVENT_SSRF: bool = Field(default_factory=lambda: os.getenv("PREVENT_SSRF", "True").lower() in ("true", "1"))

settings = Settings()
