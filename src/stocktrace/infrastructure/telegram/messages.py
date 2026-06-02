"""Telegram message builders."""

from __future__ import annotations

from collections.abc import Sequence

from stocktrace.domain.entities.watchlist_item import WatchlistItem
from stocktrace.infrastructure.config import Settings


def build_start_message() -> str:
    """Build the /start response."""
    return "\n".join(
        [
            "StockTrace is connected.",
            "",
            "Commands:",
            "/status - system status",
            "/help - show commands",
        ],
    )


def build_help_message() -> str:
    """Build the /help response."""
    return "\n".join(
        [
            "StockTrace commands:",
            "/status - system status",
            "/help - show commands",
            "",
            "/add SYMBOL",
            "/remove SYMBOL",
            "/list",
            "",
            "Coming next:",
            "/price SYMBOL",
            "/news SYMBOL",
        ],
    )


def build_status_message(settings: Settings) -> str:
    """Build the /status response."""
    database_backend = "SQLite" if settings.database.is_sqlite else "PostgreSQL"
    return "\n".join(
        [
            "StockTrace status",
            f"Service: {settings.app.name}",
            f"Version: {settings.app.version}",
            f"Environment: {settings.environment.value}",
            f"Database: {database_backend}",
            f"Redis enabled: {settings.redis.enabled}",
            "Telegram: connected",
        ],
    )


def build_watchlist_message(items: Sequence[WatchlistItem]) -> str:
    """Build the /list response."""
    if not items:
        return "Watchlist is empty. Use /add SYMBOL to add one."

    symbols = "\n".join(f"{index}. {item.symbol}" for index, item in enumerate(items, start=1))
    return "\n".join(["Watchlist:", symbols])


def build_added_message(symbol: str) -> str:
    """Build the /add response."""
    return f"Added {symbol} to watchlist."


def build_removed_message(symbol: str, removed: bool) -> str:
    """Build the /remove response."""
    if removed:
        return f"Removed {symbol} from watchlist."
    return f"{symbol} was not in watchlist."
