"""Telegram runner tests."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from stocktrace.bootstrap.container import Container
from stocktrace.infrastructure.config import TelegramSettings
from stocktrace.infrastructure.config.test import load_test_settings
from stocktrace.infrastructure.telegram import TelegramBotRunner


@pytest.mark.asyncio
async def test_telegram_runner_skips_when_token_is_missing() -> None:
    settings = load_test_settings()
    container = Container(settings=settings)
    runner = TelegramBotRunner(settings=settings, watchlist_service=container.watchlist_service())

    await runner.start()
    await runner.stop()
    await container.dispose()

    assert runner.is_configured is False


@pytest.mark.asyncio
async def test_telegram_runner_does_not_crash_on_invalid_token() -> None:
    settings = load_test_settings()
    settings.telegram = TelegramSettings(
        bot_token=SecretStr("invalid-token"),
        polling_enabled=True,
    )
    container = Container(settings=settings)
    runner = TelegramBotRunner(settings=settings, watchlist_service=container.watchlist_service())

    await runner.start()
    await runner.stop()
    await container.dispose()

    assert runner.is_configured is True
    assert runner.is_running is False
