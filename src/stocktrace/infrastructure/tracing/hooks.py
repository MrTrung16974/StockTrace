"""No-op tracing boundary."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def trace_span(_name: str) -> Iterator[None]:
    """Provide a stable tracing API before OpenTelemetry is introduced."""
    yield
