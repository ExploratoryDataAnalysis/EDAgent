"""
EDAgent FastAPI application entrypoint.
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.ratelimit import RateLimitMiddleware
from app.core.security import assert_production_secret, token_claims
from app.services import guest_sessions
from app.services.export_storage import purge_old_exports
from app.services.ingestion.validator import IngestionValidationError

logger = logging.getLogger("edagent")

# Status codes for ingestion error codes that are not a plain 400.
_INGESTION_STATUS = {
    "FILE_TOO_LARGE": 413,
    "FILE_NOT_FOUND": 404,
    "UNAUTHORIZED": 403,
    "QUOTA_EXCEEDED": 409,
    "SHEET_REQUIRED": 409,
    "STORAGE_UNSUPPORTED": 501,
}


def _error_body(message: str, errors=None, code: str | None = None, detail=None) -> dict:
    """One error shape for every failure so the frontend only has to handle one."""
    body = {"success": False, "message": message, "errors": errors or [message]}
    if code:
        body["error_code"] = code
    if detail is not None:
        body["detail"] = detail
    return body


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_production_secret()
    # Tables are created automatically for the SQLite dev setup; production uses Alembic migrations.
    if engine.dialect.name == "sqlite":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    try:
        removed = purge_old_exports()
        if removed:
            logger.info("Removed %d expired generated files", removed)
    except OSError:
        logger.warning("Could not clean old exports", exc_info=True)
    await guest_sessions.recover_after_restart()
    expiry_task = asyncio.create_task(guest_sessions.sweep_periodically())
    try:
        yield
    finally:
        expiry_task.cancel()
        with suppress(asyncio.CancelledError):
            await expiry_task


def create_application() -> FastAPI:
    application = FastAPI(
        title="EDAgent API",
        description="AI-assisted exploratory data analysis. The AI plans and explains; the backend computes.",
        version="1.0.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    @application.exception_handler(IngestionValidationError)
    async def ingestion_error(request: Request, exc: IngestionValidationError):
        return JSONResponse(status_code=_INGESTION_STATUS.get(exc.error_code, 400), content=_error_body(exc.message, code=exc.error_code))

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else (exc.detail or {}).get("message", "Request failed.")
        extra = exc.detail.get("problems") if isinstance(exc.detail, dict) else None
        return JSONResponse(
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
            content=_error_body(message, errors=extra or [message], detail=exc.detail),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        problems = [f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors()]
        return JSONResponse(status_code=422, content=_error_body("The request was not valid.", errors=problems, detail=jsonable_errors(exc)))

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        # Log the details server-side; never leak internals (paths, SQL, stack traces) to the client.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_error_body("Something went wrong on the server. Please try again.", code="INTERNAL_ERROR"))

    @application.middleware("http")
    async def guest_delivery(request: Request, call_next):
        path = request.url.path.rstrip("/")
        if request.method == "POST" and path == f"{settings.API_V1_STR}/datasets/upload":
            scheme, _, credential = request.headers.get("authorization", "").partition(" ")
            if scheme.lower() == "bearer" and token_claims(credential, allow_expired=True).get("guest") is True:
                # Reject oversized multipart bodies before the parser spools them.
                length = request.headers.get("content-length", "")
                if not length.isdecimal() or int(length) > settings.GUEST_MAX_UPLOAD_BYTES + 64 * 1024:
                    return JSONResponse(
                        status_code=413, content=_error_body("Guest upload exceeds the request limit."),
                        headers={"Cache-Control": "no-store"},
                    )
        try:
            response = await call_next(request)
        except Exception:
            if not getattr(request.state, "guest_id", None):
                raise
            logger.error("Unhandled guest request error")
            response = JSONResponse(status_code=500, content=_error_body("The guest request failed. Please try again."))
        guest_id = getattr(request.state, "guest_id", None)
        if guest_id:
            response.headers["Cache-Control"] = "no-store"
            if response.status_code < 400:
                # A request can finish computing after clear or the lease deadline.
                async with AsyncSessionLocal() as db:
                    if await guest_sessions.active(db, guest_id) is None:
                        return JSONResponse(
                            status_code=401, content=_error_body(guest_sessions.EXPIRED),
                            headers={"Cache-Control": "no-store", "WWW-Authenticate": "Bearer"},
                        )
        return response

    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Retry-After", "X-Bundle-Version", "X-Manifest-SHA256", "X-Artifact-SHA256"],
    )

    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/", tags=["Root"])
    async def root():
        return {"name": settings.APP_NAME, "version": "1.0.0", "docs": f"{settings.API_V1_STR}/docs", "health": f"{settings.API_V1_STR}/health"}

    return application


def jsonable_errors(exc: RequestValidationError):
    """Pydantic error dicts can hold non-serialisable objects (e.g. the original exception)."""
    return [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]


app = create_application()
