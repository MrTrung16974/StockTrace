"""Configuration tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from stocktrace.infrastructure.config import (
    AutoTradeSettings,
    Environment,
    Settings,
    TelegramSettings,
)
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


def test_provider_ca_bundle_can_be_set_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STOCKTRACE_PROVIDERS__CA_BUNDLE_PATH", "/etc/ssl/company-proxy.pem")

    settings = Settings(_env_file=None)

    assert settings.providers.ca_bundle_path == "/etc/ssl/company-proxy.pem"


def test_scheduler_symbol_lists_accept_comma_separated_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STOCKTRACE_SCHEDULER__WATCHLIST_SYMBOLS", "HPG,FPT,VCB")
    monkeypatch.setenv("STOCKTRACE_SCHEDULER__DISABLED_SYMBOLS", "VCB")
    monkeypatch.setenv("STOCKTRACE_SCHEDULER__ANALYSIS_SYMBOLS", "HPG,FPT")

    settings = Settings(_env_file=None)

    assert settings.scheduler.watchlist_symbols == ["HPG", "FPT", "VCB"]
    assert settings.scheduler.disabled_symbols == ["VCB"]
    assert settings.scheduler.analysis_symbols == ["HPG", "FPT"]


def test_ai_fallback_models_accept_comma_separated_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "STOCKTRACE_AI__FALLBACK_MODELS",
        "gemini-3.5-flash-lite,gemini-2.5-flash",
    )

    settings = Settings(_env_file=None)

    assert settings.ai.fallback_models == ["gemini-3.5-flash-lite", "gemini-2.5-flash"]


def test_auto_trade_is_disabled_by_default_and_parses_pilot_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STOCKTRACE_AUTO_TRADE__ALLOWED_SYMBOLS", "hpg,fpt")

    settings = Settings(_env_file=None)

    assert settings.auto_trade.enabled is False
    assert settings.auto_trade.allowed_symbols == ["HPG", "FPT"]


def test_enabled_auto_trade_requires_a_symbol_allowlist() -> None:
    with pytest.raises(ValidationError, match="ALLOWED_SYMBOLS"):
        AutoTradeSettings(enabled=True)


def test_auto_trade_settings_map_all_pilot_limits_to_domain_policy() -> None:
    settings = AutoTradeSettings(
        enabled=True,
        allowed_symbols=["HPG"],
        max_notional_per_order=Decimal("1000000"),
        max_notional_per_day=Decimal("2000000"),
        max_orders_per_day=1,
        minimum_paper_observation_days=30,
        minimum_paper_completed_orders=20,
        policy_version="pilot-v1",
    )

    policy = settings.to_pilot_policy()

    assert policy.enabled is True
    assert policy.allowed_symbols == ("HPG",)
    assert policy.policy_version == "pilot-v1"


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
