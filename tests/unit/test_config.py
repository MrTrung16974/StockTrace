"""Configuration tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from stocktrace.infrastructure.config import Environment, Settings
from stocktrace.infrastructure.config.prod import load_prod_settings
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
    settings = Settings()

    assert settings.api.port == expected_port


def test_prod_settings_load_with_required_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCKTRACE_TELEGRAM__BOT_TOKEN", "123456:test")
    monkeypatch.setenv("STOCKTRACE_TELEGRAM__CHAT_ID", "123456")
    monkeypatch.setenv("STOCKTRACE_TELEGRAM__ALLOWED_USER_IDS", "[123456]")
    monkeypatch.setenv("STOCKTRACE_SECURITY__API_KEY", "test-api-key")

    settings = load_prod_settings()

    assert settings.environment is Environment.PRODUCTION
    assert settings.debug is False
