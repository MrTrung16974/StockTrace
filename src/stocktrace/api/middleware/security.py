"""HTTP security middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from hmac import compare_digest
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from stocktrace.infrastructure.config import SecuritySettings


@dataclass(slots=True)
class FixedWindowRateLimiter:
    """In-memory fixed-window rate limiter.

    This is intentionally process-local for Phase 0. A Redis-backed implementation can replace it
    later without changing the middleware contract.
    """

    limit: int
    window_seconds: int = 60
    _buckets: dict[str, tuple[int, float]] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        """Return whether a request is allowed for the current window."""
        now = monotonic()
        count, window_started_at = self._buckets.get(key, (0, now))
        if now - window_started_at >= self.window_seconds:
            self._buckets[key] = (1, now)
            return True

        if count >= self.limit:
            return False

        self._buckets[key] = (count + 1, window_started_at)
        return True


class ApiSecurityMiddleware(BaseHTTPMiddleware):
    """Protect non-public API paths with API key and rate limiting."""

    def __init__(self, app: ASGIApp, settings: SecuritySettings) -> None:
        super().__init__(app)
        self._settings = settings
        self._rate_limiter = FixedWindowRateLimiter(limit=settings.rate_limit_per_minute)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Validate request before it reaches routers."""
        if self._is_public_path(request.url.path):
            return await call_next(request)

        client_key = self._client_key(request)
        if not self._rate_limiter.allow(client_key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )

        if not self._has_valid_api_key(request):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        return any(
            path == public_path or path.startswith(f"{public_path}/")
            for public_path in self._settings.public_paths
        )

    def _has_valid_api_key(self, request: Request) -> bool:
        expected = self._settings.api_key
        if expected is None:
            return True

        provided = request.headers.get(self._settings.api_key_header)
        if provided is None:
            return False

        return compare_digest(provided, expected.get_secret_value())

    @staticmethod
    def _client_key(request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",", maxsplit=1)[0].strip()
        if request.client is None:
            return "unknown"
        return request.client.host
