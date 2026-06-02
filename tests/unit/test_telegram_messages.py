"""Telegram message builder tests."""

from __future__ import annotations

from datetime import UTC, datetime

from stocktrace.domain.entities.watchlist_item import WatchlistItem
from stocktrace.infrastructure.config.test import load_test_settings
from stocktrace.infrastructure.telegram.messages import (
    build_added_message,
    build_help_message,
    build_removed_message,
    build_start_message,
    build_status_message,
    build_watchlist_message,
)


def test_build_start_message_mentions_connection() -> None:
    message = build_start_message()

    assert "StockTrace is connected." in message
    assert "/status" in message


def test_build_help_message_mentions_future_commands() -> None:
    message = build_help_message()

    assert "/add SYMBOL" in message
    assert "/news SYMBOL" in message


def test_build_status_message_uses_settings() -> None:
    message = build_status_message(load_test_settings())

    assert "Environment: test" in message
    assert "Database: SQLite" in message


def test_build_watchlist_message_handles_empty_list() -> None:
    assert build_watchlist_message([]) == "Watchlist is empty. Use /add SYMBOL to add one."


def test_build_watchlist_message_lists_symbols() -> None:
    item = WatchlistItem(
        id="item-1",
        owner_id="user-1",
        symbol="FPT",
        created_at=datetime.now(tz=UTC),
    )

    assert "1. FPT" in build_watchlist_message([item])


def test_build_added_and_removed_messages() -> None:
    assert build_added_message("FPT") == "Added FPT to watchlist."
    assert build_removed_message("FPT", removed=True) == "Removed FPT from watchlist."
    assert build_removed_message("FPT", removed=False) == "FPT was not in watchlist."
