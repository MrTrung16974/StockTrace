"""Cache port for market data use cases."""

from __future__ import annotations

from typing import Protocol

from stocktrace.application.services.market_data import NewsArticle, StockQuote


class MarketDataCache(Protocol):
    """Port for caching stock quotes and news articles."""

    async def get_quote(self, ticker: str) -> StockQuote | None:
        """Return a cached quote if present."""

    async def set_quote(self, quote: StockQuote, ttl_seconds: int) -> None:
        """Cache a quote for a limited time."""

    async def get_news(self, ticker: str, limit: int) -> list[NewsArticle] | None:
        """Return cached news if present."""

    async def set_news(
        self,
        ticker: str,
        limit: int,
        articles: list[NewsArticle],
        ttl_seconds: int,
    ) -> None:
        """Cache a news list for a limited time."""
