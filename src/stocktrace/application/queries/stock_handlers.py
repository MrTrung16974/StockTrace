"""Application query handlers for market data."""

from __future__ import annotations

from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.market_data import MarketDataService, NewsArticle, StockQuote
from stocktrace.domain.ports.market_data_cache import MarketDataCache


class GetStockQuoteQueryHandler:
    """Resolve a stock quote through the application service and cache."""

    def __init__(
        self,
        market_data_service: MarketDataService,
        cache: MarketDataCache | None = None,
        ttl_seconds: int = 30,
    ) -> None:
        self._market_data_service = market_data_service
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    async def handle(self, query: GetPriceQuery) -> StockQuote | None:
        """Return a quote, using cache when possible."""
        symbol = query.symbol.strip().upper()
        if self._cache is not None:
            try:
                cached = await self._cache.get_quote(symbol)
            except Exception:
                cached = None
            if cached is not None:
                return cached

        quote = await self._market_data_service.get_quote(symbol)
        if self._cache is not None:
            try:
                await self._cache.set_quote(quote, ttl_seconds=self._ttl_seconds)
            except Exception:
                pass
        return quote


class GetStockNewsQueryHandler:
    """Resolve market news through the application service and cache."""

    def __init__(
        self,
        market_data_service: MarketDataService,
        cache: MarketDataCache | None = None,
        ttl_seconds: int = 300,
    ) -> None:
        self._market_data_service = market_data_service
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    async def handle(self, query: GetNewsQuery) -> list[NewsArticle]:
        """Return news articles, using cache when possible."""
        symbol = query.symbol.strip().upper()
        if self._cache is not None:
            try:
                cached = await self._cache.get_news(symbol, query.limit)
            except Exception:
                cached = None
            if cached is not None:
                return cached

        articles = await self._market_data_service.get_news(symbol, limit=query.limit)
        if self._cache is not None:
            try:
                await self._cache.set_news(symbol, query.limit, articles, ttl_seconds=self._ttl_seconds)
            except Exception:
                pass
        return articles
