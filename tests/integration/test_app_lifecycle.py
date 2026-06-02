"""Application lifecycle tests."""

from __future__ import annotations

import pytest

from stocktrace.api.app import create_app, lifespan
from stocktrace.infrastructure.config.test import load_test_settings


@pytest.mark.asyncio
async def test_lifespan_initializes_and_disposes_runtime_state() -> None:
    app = create_app(settings=load_test_settings())

    async with lifespan(app):
        assert app.state.settings.environment.value == "test"
        assert app.state.container is not None
        assert app.state.telegram_runner.is_configured is False
