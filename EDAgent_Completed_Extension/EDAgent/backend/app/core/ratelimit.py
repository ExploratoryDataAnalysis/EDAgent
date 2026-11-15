"""
Small in-process sliding-window rate limiter (no extra infrastructure).

Limits are per client key (authenticated user id when a valid token is present, else the
client IP) and per route class. It is per worker process, which is adequate for the
single-node deployment this project targets; behind several workers each applies its own
window. Swap the `_hits` store for Redis if you need a cluster-wide limit.
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.security import decode_access_token


def _route_class(path: str) -> Tuple[str, int]:
    base = settings.API_V1_STR
    if path.startswith(f"{base}/auth"):
        return "auth", settings.AUTH_RATE_LIMIT_PER_MINUTE
    if path.startswith((f"{base}/analysis", f"{base}/chat")):
        return "analysis", settings.ANALYSIS_RATE_LIMIT_PER_MINUTE
    return "general", settings.RATE_LIMIT_PER_MINUTE


class RateLimitMiddleware(BaseHTTPMiddleware):
    WINDOW_SECONDS = 60

    def __init__(self, app):
        super().__init__(app)
        self._hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or not request.url.path.startswith(settings.API_V1_STR):
            return await call_next(request)

        guest_endpoint = request.url.path.rstrip("/") == f"{settings.API_V1_STR}/auth/guest-session"
        creating_guest = guest_endpoint and request.method == "POST"
        if guest_endpoint and not creating_guest:
            klass, limit = "general", settings.RATE_LIMIT_PER_MINUTE
        else:
            klass, limit = _route_class(request.url.path)
        if limit <= 0:  # 0 disables limiting (used by the test-suite)
            return await call_next(request)

        # Identify the caller: a valid JWT subject beats the socket address.
        key = request.client.host if request.client else "unknown"
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            sub = decode_access_token(auth[7:])
            if sub and not creating_guest:
                key = f"user:{sub}"

        now = time.monotonic()
        window = self._hits[(klass, key)]
        while window and now - window[0] > self.WINDOW_SECONDS:
            window.popleft()
        if len(window) >= limit:
            retry = max(1, int(self.WINDOW_SECONDS - (now - window[0])))
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry)},
                content={
                    "success": False,
                    "message": f"Too many requests. Please retry in {retry}s.",
                    "error_code": "RATE_LIMITED",
                    "errors": ["rate limit exceeded"],
                },
            )
        window.append(now)
        return await call_next(request)
