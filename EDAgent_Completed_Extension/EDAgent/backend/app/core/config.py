"""
Core Application Configuration

All tunables come from environment variables (or a local `.env` file) so the same
build runs unchanged in development, tests and production. Nothing in this module
is ever returned from an API endpoint: secrets such as SECRET_KEY and LLM_API_KEY
stay server-side (see `public_llm_status` for the only LLM info the API exposes).
"""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder that ships in .env.example; refusing it in production prevents
# deployments that silently sign JWTs with a publicly known key.
INSECURE_DEFAULT_SECRET = "edagent-secret-key-change-in-production-min-32-chars"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Environment -------------------------------------------------------
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    APP_NAME: str = "EDAgent"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Server ------------------------------------------------------------
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # --- Database ----------------------------------------------------------
    DATABASE_URL: str = "sqlite+aiosqlite:///./edagent.db"

    # --- Storage -----------------------------------------------------------
    # Only "local" is implemented; the setting is kept so a future object-store backend is a drop-in.
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./data/uploads"
    EXPORTS_STORAGE_PATH: str = "./data/exports"
    # Ships inside the backend package so samples are found no matter where the server is started.
    SAMPLES_PATH: str = str(Path(__file__).resolve().parents[2] / "data" / "samples")
    MAX_UPLOAD_SIZE_MB: int = 200
    # Generated files (reports, bundles) older than this are purged on startup.
    EXPORT_RETENTION_HOURS: int = 72

    # --- AI / LLM ----------------------------------------------------------
    # LLM_PROVIDER: openai | anthropic | mock. "mock" (or a missing key) means AI is
    # *not configured*: the chat endpoint says so instead of faking an answer.
    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = "gpt-4o"
    LLM_API_KEY: str = ""
    # Optional override for OpenAI-compatible gateways (Azure, local servers, ...).
    LLM_BASE_URL: str = ""
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT_SECONDS: int = 45
    # Hard cap on characters of dataset metadata placed in one prompt.
    LLM_MAX_CONTEXT_CHARS: int = 12000

    # --- Quotas, limits and performance -----------------------------------
    MAX_CONCURRENT_JOBS_PER_USER: int = 2
    JOB_TIMEOUT_SECONDS: int = 300
    MEMORY_LIMIT_MB: int = 2048
    ROW_LIMIT_PREVIEW: int = 100
    DEFAULT_SAMPLE_SIZE: int = 10000
    ANALYSIS_TIMEOUT_SECONDS: int = 60
    MAX_CONCURRENT_ANALYSES: int = 4
    # Rows returned inline in a result table; the full table is available via export.
    MAX_RESULT_ROWS: int = 500
    # Table exports re-run truncated results with this higher cap so CSV/XLSX are complete.
    MAX_EXPORT_ROWS: int = 200000
    # Row-level (O(n*k)) algorithms such as K-Means/classification sample above this.
    MAX_MODELLING_ROWS: int = 50000
    ANALYSIS_CACHE_ENTRIES: int = 256
    DATAFRAME_CACHE_ENTRIES: int = 4
    MAX_DATASETS_PER_USER: int = 50

    # Local guest policy. Creation is opt-in and cleanup remains enabled during rollback.
    ALLOW_GUEST_SESSIONS: bool = False
    GUEST_SESSION_MINUTES: int = 60
    GUEST_MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024
    GUEST_MAX_DATASETS: int = 3
    GUEST_MAX_ACTIONS: int = 30

    # --- Rate limiting (per process, per user or IP) ----------------------
    RATE_LIMIT_PER_MINUTE: int = 240
    AUTH_RATE_LIMIT_PER_MINUTE: int = 20
    ANALYSIS_RATE_LIMIT_PER_MINUTE: int = 60

    # --- Security ----------------------------------------------------------
    ENABLE_SANDBOX: bool = True
    PREVENT_SSRF: bool = True
    URL_IMPORT_MAX_MB: int = 50
    URL_IMPORT_TIMEOUT_SECONDS: int = 30
    URL_IMPORT_MAX_REDIRECTS: int = 3
    ALLOW_REGISTRATION: bool = True

    @property
    def sync_database_url(self) -> str:
        """Blocking-driver twin of DATABASE_URL, used by background job threads."""
        url = self.DATABASE_URL
        return (
            url.replace("sqlite+aiosqlite", "sqlite", 1)
            .replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
        )

    @property
    def ai_configured(self) -> bool:
        """True only when a real provider and key are available."""
        return self.LLM_PROVIDER.lower() in ("openai", "anthropic") and bool(self.LLM_API_KEY.strip())


settings = Settings()
