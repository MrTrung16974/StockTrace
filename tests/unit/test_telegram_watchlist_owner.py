"""Tests for the watchlist ownership boundary used by Telegram commands."""

from __future__ import annotations

from types import SimpleNamespace

from stocktrace.infrastructure.telegram.aiogram_router import _watchlist_owner_id


def test_watchlist_owner_is_the_telegram_chat_id() -> None:
    message = SimpleNamespace(chat=SimpleNamespace(id=-100987654321))

    assert _watchlist_owner_id(message) == "-100987654321"


def test_watchlist_owner_is_missing_without_a_chat() -> None:
    message = SimpleNamespace(chat=None)

    assert _watchlist_owner_id(message) is None
