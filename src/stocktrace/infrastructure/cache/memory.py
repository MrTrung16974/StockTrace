"""In-memory market data cache."""

from __future__ import annotations

from dataclasses import replace
from time import monotonic

from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.domain.ports.market_data_cache import MarketDataCache


class InMemoryMarketDataCache(MarketDataCache):
    """Simple process-local cache with TTL support."""

    def __init__(self) -> None:
        self._quote_store: dict[str, tuple[float, StockQuote]] = {}
        self._news_store: dict[str, tuple[float, list[NewsArticle]]] = {}

    async def get_quote(self, ticker: str) -> StockQuote | None:
        entry = self._quote_store.get(_quote_key(ticker))
        if entry is None:
            return None
        expires_at, quote = entry
        if expires_at <= monotonic():
            self._quote_store.pop(_quote_key(ticker), None)
            return None
        return replace(quote)

    async def set_quote(self, quote: StockQuote, ttl_seconds: int) -> None:
        self._quote_store[_quote_key(quote.ticker)] = (monotonic() + ttl_seconds, replace(quote))

    async def get_news(self, ticker: str, limit: int) -> list[NewsArticle] | None:
        entry = self._news_store.get(_news_key(ticker, limit))
        if entry is None:
            return None
        expires_at, articles = entry
        if expires_at <= monotonic():
            self._news_store.pop(_news_key(ticker, limit), None)
            return None
        return [replace(article) for article in articles]

    async def set_news(
        self,
        ticker: str,
        limit: int,
        articles: list[NewsArticle],
        ttl_seconds: int,
    ) -> None:
        self._news_store[_news_key(ticker, limit)] = (
            monotonic() + ttl_seconds,
            [replace(article) for article in articles],
        )


def _quote_key(ticker: str) -> str:
    return f"quote:{ticker.upper()}"


def _news_key(ticker: str, limit: int) -> str:
    return f"news:{ticker.upper()}:{limit}"
