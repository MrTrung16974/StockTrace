"""Request correlation context for distributed tracing."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Immutable correlation identifiers attached to every request."""

    request_id: str
    trace_id: str
    span_id: str

    @classmethod
    def generate(cls, *, traceparent: str | None = None) -> "CorrelationContext":
        """Create a fresh context, optionally extracting trace_id from W3C traceparent header."""
        trace_id = _parse_traceparent_trace_id(traceparent) if traceparent else _new_id()
        return cls(
            request_id=f"req-{_new_id()[:8]}",
            trace_id=trace_id,
            span_id=_new_id()[:16],
        )


_CORRELATION_CTX: ContextVar[CorrelationContext | None] = ContextVar(
    "correlation_ctx", default=None
)


def set_correlation(ctx: CorrelationContext) -> None:
    """Bind a correlation context to the current async task."""
    _CORRELATION_CTX.set(ctx)


def get_correlation() -> CorrelationContext | None:
    """Return the active correlation context, or None if not set."""
    return _CORRELATION_CTX.get()


def get_trace_id() -> str:
    """Return the active trace_id or an empty string."""
    ctx = _CORRELATION_CTX.get()
    return ctx.trace_id if ctx else ""


def get_request_id() -> str:
    """Return the active request_id or an empty string."""
    ctx = _CORRELATION_CTX.get()
    return ctx.request_id if ctx else ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return uuid.uuid4().hex


def _parse_traceparent_trace_id(header: str) -> str:
    """Extract trace-id from W3C traceparent (version-traceid-parentid-flags)."""
    parts = header.split("-")
    if len(parts) == 4:  # noqa: PLR2004
        return parts[1]
    return _new_id()
