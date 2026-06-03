"""Telegram message builders."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from html import escape

from stocktrace.application.services.market_data import NewsArticle, StockQuote
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


def build_price_message(quote: StockQuote) -> str:
    """Build the /price response."""
    return "\n".join(
        [
            escape(quote.ticker),
            f"Giá: {_format_vn_price(quote.current_price)}",
            f"{_format_signed_decimal(quote.change_percent)}%",
        ],
    )


def build_news_message(symbol: str, articles: Sequence[NewsArticle]) -> str:
    """Build the /news response."""
    clean_symbol = escape(symbol)
    if not articles:
        return f"No recent news found for {clean_symbol}."

    lines = [f"News for {clean_symbol}:"]
    for index, article in enumerate(articles, start=1):
        title = escape(article.title)
        url = escape(article.url)
        lines.append(f'{index}. <a href="{url}">{title}</a>')
    return "\n".join(lines)


def _format_decimal(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01")) if value.as_tuple().exponent < -2 else value
    return f"{normalized:,}"


def _format_signed_decimal(value: Decimal) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_format_decimal(value)}"


def _format_vn_price(value: Decimal) -> str:
    if value == value.to_integral():
        return f"{int(value):,}".replace(",", ".")
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
