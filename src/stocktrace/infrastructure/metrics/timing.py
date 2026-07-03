"""Execution timing helpers with Prometheus histogram support."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from time import perf_counter

from stocktrace.infrastructure.logging.config import get_logger


@contextmanager
def timed_operation(operation: str, *, metric_labels: dict[str, str] | None = None) -> Iterator[None]:
    """Log elapsed time for a named sync operation and record Prometheus histogram."""
    logger = get_logger(__name__)
    started_at = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info("operation_completed", operation=operation, elapsed_ms=elapsed_ms)
        _record_histogram(operation, elapsed_ms / 1000.0, metric_labels)


@asynccontextmanager
async def async_timed_operation(
    operation: str, *, metric_labels: dict[str, str] | None = None
) -> AsyncIterator[None]:
    """Log elapsed time for a named async operation and record Prometheus histogram."""
    logger = get_logger(__name__)
    started_at = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info("operation_completed", operation=operation, elapsed_ms=elapsed_ms)
        _record_histogram(operation, elapsed_ms / 1000.0, metric_labels)


def _record_histogram(operation: str, elapsed_seconds: float, labels: dict[str, str] | None) -> None:
    """Emit to Prometheus cache_operation histogram when labels are provided."""
    try:
        from stocktrace.infrastructure.metrics.prometheus import cache_operation_seconds  # noqa: PLC0415

        if labels and "layer" in labels:
            cache_operation_seconds.labels(
                operation=labels.get("operation", operation),
                layer=labels["layer"],
            ).observe(elapsed_seconds)
    except Exception:  # noqa: BLE001
        pass  # Metrics are best-effort — never crash the hot path
