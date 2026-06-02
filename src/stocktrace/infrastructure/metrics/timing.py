"""Execution timing helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

from stocktrace.infrastructure.logging.config import get_logger


@contextmanager
def timed_operation(operation: str) -> Iterator[None]:
    """Log elapsed time for a named operation."""
    logger = get_logger(__name__)
    started_at = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info("operation_completed", operation=operation, elapsed_ms=elapsed_ms)
