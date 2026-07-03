"""Request correlation and timing middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from stocktrace.api.middleware.correlation import CorrelationContext, set_correlation
from stocktrace.infrastructure.logging.config import get_logger


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Attach correlation IDs, execution time and structured logs to every HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._logger = get_logger(__name__)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Build correlation context — honour upstream traceparent if present
        traceparent = request.headers.get("traceparent")
        correlation = CorrelationContext.generate(traceparent=traceparent)
        set_correlation(correlation)

        # Bind to structlog so every log line in this request carries these fields
        structlog.contextvars.bind_contextvars(
            request_id=correlation.request_id,
            trace_id=correlation.trace_id,
            span_id=correlation.span_id,
        )

        started_at = perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
            structlog.contextvars.clear_contextvars()

        response.headers["X-Request-ID"] = correlation.request_id
        response.headers["X-Trace-ID"] = correlation.trace_id
        response.headers["X-Process-Time-Ms"] = str(elapsed_ms)

        self._logger.info(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            request_id=correlation.request_id,
            trace_id=correlation.trace_id,
        )
        return response
