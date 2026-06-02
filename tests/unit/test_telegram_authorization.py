"""Telegram authorization tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from aiogram.types import User

from stocktrace.infrastructure.config import TelegramSettings
from stocktrace.infrastructure.telegram.authorization import is_authorized_user


def test_telegram_user_is_allowed_when_whitelist_is_empty() -> None:
    user = cast(User, SimpleNamespace(id=123))

    assert is_authorized_user(user, TelegramSettings()) is True


def test_telegram_user_must_be_in_whitelist_when_configured() -> None:
    user = cast(User, SimpleNamespace(id=123))
    settings = TelegramSettings(allowed_user_ids=[456])

    assert is_authorized_user(user, settings) is False


def test_missing_telegram_user_is_rejected() -> None:
    assert is_authorized_user(None, TelegramSettings()) is False
