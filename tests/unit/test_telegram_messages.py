"""Telegram message builder tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.domain.entities.watchlist_item import WatchlistItem
from stocktrace.infrastructure.config.test import load_test_settings
from stocktrace.infrastructure.telegram.messages import (
    build_added_message,
    build_help_message,
    build_news_message,
    build_price_message,
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
    assert "/analysis SYMBOL" in message


def test_build_status_message_uses_settings() -> None:
    message = build_status_message(load_test_settings())

    assert "Environment: test" in message
    assert "Database: SQLite" in message
    assert "AI enabled: False" in message


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


def test_build_price_message_formats_quote() -> None:
    message = build_price_message(
        StockQuote(
            ticker="FPT",
            company_name="FPT Corporation",
            current_price=Decimal("125000"),
            change=Decimal("1.25"),
            change_percent=Decimal("1.02"),
            open_price=Decimal("122.00"),
            high_price=Decimal("124.00"),
            low_price=Decimal("121.50"),
            volume=1000,
            timestamp=datetime(2026, 6, 2, 1, 30, tzinfo=UTC),
            currency="USD",
            source="Yahoo Finance",
        ),
    )

    assert "FPT" in message
    assert "Giá: 125.000" in message
    assert "+1.02%" in message


def test_build_news_message_lists_articles_and_escapes_html() -> None:
    message = build_news_message(
        symbol="FPT",
        articles=[
            NewsArticle(
                ticker="FPT",
                title="FPT & market update",
                summary="summary",
                url="https://example.com/news?a=1&b=2",
                source="Yahoo Finance",
            ),
        ],
    )

    assert "News for FPT:" in message
    assert '<a href="https://example.com/news?a=1&amp;b=2">FPT &amp; market update</a>' in message


def test_build_news_message_handles_empty_articles() -> None:
    assert build_news_message(symbol="FPT", articles=[]) == "No recent news found for FPT."
