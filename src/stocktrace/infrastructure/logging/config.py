"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog

from stocktrace.infrastructure.config import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    """Configure stdlib and structlog logging."""
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any
    if settings.json_enabled:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.level,
    )
    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.level),
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
