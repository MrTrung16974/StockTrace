"""Configuration tests."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from stocktrace.infrastructure.config import Environment, Settings, TelegramSettings
from stocktrace.infrastructure.config.settings import SecuritySettings
from stocktrace.infrastructure.config.test import load_test_settings


def test_test_settings_use_memory_database() -> None:
    settings = load_test_settings()

    assert settings.environment is Environment.TEST
    assert settings.database.url == "sqlite+aiosqlite:///:memory:"
    assert settings.redis.enabled is False


def test_production_requires_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment=Environment.PRODUCTION)


def test_nested_settings_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_port = 9000
    monkeypatch.setenv("STOCKTRACE_API__PORT", "9000")
    settings = Settings(_env_file=None)

    assert settings.api.port == expected_port


def test_prod_settings_load_with_required_secrets() -> None:
    settings = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        debug=False,
        telegram=TelegramSettings(
            bot_token=SecretStr("123456:test"),
            chat_id="123456",
            allowed_user_ids=[123456],
        ),
        security=SecuritySettings(api_key=SecretStr("test-api-key")),
    )

    assert settings.environment is Environment.PRODUCTION
    assert settings.debug is False
