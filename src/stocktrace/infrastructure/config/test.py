"""Test configuration helpers."""

from __future__ import annotations

from stocktrace.infrastructure.config.settings import (
    DatabaseSettings,
    Environment,
    ObservabilitySettings,
    RedisSettings,
    Settings,
    TelegramSettings,
)


def load_test_settings() -> Settings:
    """Load deterministic settings for tests."""
    return Settings(
        _env_file=None,
        environment=Environment.TEST,
        debug=True,
        database=DatabaseSettings(url="sqlite+aiosqlite:///:memory:"),
        redis=RedisSettings(enabled=False),
        telegram=TelegramSettings(polling_enabled=False),
        observability=ObservabilitySettings(prometheus_enabled=False),
    )
