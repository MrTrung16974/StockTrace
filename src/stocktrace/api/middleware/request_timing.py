"""Request timing middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from stocktrace.infrastructure.logging.config import get_logger


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Attach execution time to responses and structured logs."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._logger = get_logger(__name__)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started_at = perf_counter()
        response = await call_next(request)
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
        self._logger.info(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        return response
