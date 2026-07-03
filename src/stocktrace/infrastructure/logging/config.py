"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog

from stocktrace.infrastructure.config import LoggingSettings

# Module-level cache so we can read these in processors without circular imports
_SERVICE_NAME: str = "stocktrace-api"
_SERVICE_VERSION: str = "unknown"
_ENVIRONMENT: str = "development"


def configure_logging(settings: LoggingSettings, *, service_name: str = "stocktrace-api",
                      service_version: str = "unknown", environment: str = "development") -> None:
    """Configure stdlib and structlog logging with full observability context."""
    global _SERVICE_NAME, _SERVICE_VERSION, _ENVIRONMENT  # noqa: PLW0603
    _SERVICE_NAME = service_name
    _SERVICE_VERSION = service_version
    _ENVIRONMENT = environment

    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_service_context,
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


def _add_service_context(
    logger: Any,  # noqa: ANN401
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject service metadata into every log event."""
    event_dict.setdefault("service", _SERVICE_NAME)
    event_dict.setdefault("version", _SERVICE_VERSION)
    event_dict.setdefault("environment", _ENVIRONMENT)
    return event_dict


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
