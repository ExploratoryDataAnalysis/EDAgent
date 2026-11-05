"""
EDAgent FastAPI Application Entrypoint
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.router import api_router
from app.services.ingestion.validator import IngestionValidationError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-initialize database tables on startup if engine is available
    if hasattr(Base, "metadata") and engine is not None:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"Could not initialize tables automatically: {e}")
    yield


def create_application() -> FastAPI:
    application = FastAPI(
        title="EDAgent API",
        description="AI-powered Exploratory Data Analysis platform backend API",
        version="0.1.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Custom exception handler for user-friendly validation errors
    @application.exception_handler(IngestionValidationError)
    async def ingestion_validation_exception_handler(request: Request, exc: IngestionValidationError):
        status_code = status.HTTP_400_BAD_REQUEST
        if exc.error_code == "FILE_TOO_LARGE":
            status_code = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)
        elif exc.error_code == "FILE_NOT_FOUND":
            status_code = status.HTTP_404_NOT_FOUND
        elif exc.error_code == "UNAUTHORIZED":
            status_code = status.HTTP_403_FORBIDDEN

        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "message": exc.message,
                "error_code": exc.error_code,
                "errors": [exc.message],
            },
        )

    # CORS configuration
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API v1 router
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "docs": f"{settings.API_V1_STR}/docs",
            "health": f"{settings.API_V1_STR}/health",
        }

    return application


app = create_application()
