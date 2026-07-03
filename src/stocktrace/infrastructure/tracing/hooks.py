"""Distributed tracing boundary — wraps OpenTelemetry when enabled."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any


@contextmanager
def trace_span(name: str, *, attributes: dict[str, Any] | None = None) -> Iterator[None]:
    """Open a tracing span for a sync operation.

    Delegates to OpenTelemetry when available; falls back to a no-op so callers
    never need to guard against the SDK being absent.
    """
    try:
        from opentelemetry import trace  # noqa: PLC0415

        tracer = trace.get_tracer("stocktrace")
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            yield
    except ImportError:
        yield  # OTEL not installed — silently no-op


@asynccontextmanager
async def async_trace_span(name: str, *, attributes: dict[str, Any] | None = None) -> AsyncIterator[None]:
    """Open a tracing span for an async operation."""
    try:
        from opentelemetry import trace  # noqa: PLC0415

        tracer = trace.get_tracer("stocktrace")
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            yield
    except ImportError:
        yield  # OTEL not installed — silently no-op
