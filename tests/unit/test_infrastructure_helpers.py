"""Infrastructure helper tests."""

from __future__ import annotations

import pytest

from stocktrace.infrastructure.config import DatabaseSettings, LoggingSettings
from stocktrace.infrastructure.config.dev import load_dev_settings
from stocktrace.infrastructure.db.session import (
    SessionManager,
    create_engine,
    create_session_factory,
)
from stocktrace.infrastructure.logging.config import configure_logging, get_logger
from stocktrace.infrastructure.metrics.timing import timed_operation
from stocktrace.infrastructure.tracing.hooks import trace_span


def test_dev_settings_enable_debug() -> None:
    settings = load_dev_settings()

    assert settings.debug is True
    assert settings.environment.value == "development"


def test_sqlite_engine_and_session_factory_can_be_created() -> None:
    settings = DatabaseSettings(url="sqlite+aiosqlite:///:memory:")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    assert engine is not None
    assert session_factory is not None


@pytest.mark.asyncio
async def test_session_manager_disposes_sqlite_engine() -> None:
    manager = SessionManager(DatabaseSettings(url="sqlite+aiosqlite:///:memory:"))

    async with manager.session() as session:
        assert session.is_active

    await manager.dispose()


def test_logging_configuration_and_helpers() -> None:
    configure_logging(LoggingSettings(json_enabled=False))
    logger = get_logger(__name__)

    assert logger is not None


def test_timing_and_tracing_helpers() -> None:
    with timed_operation("unit-test"):
        pass

    with trace_span("unit-test"):
        pass
