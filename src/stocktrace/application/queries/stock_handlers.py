"""Application query handlers for market data with audit event emission."""

from __future__ import annotations

from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.audit_service import AuditService
from stocktrace.application.services.market_data import MarketDataService, NewsArticle, StockQuote
from stocktrace.domain import events as domain_events
from stocktrace.domain.ports.market_data_cache import MarketDataCache


class GetStockQuoteQueryHandler:
    """Resolve a stock quote through the application service and cache."""

    def __init__(
        self,
        market_data_service: MarketDataService,
        cache: MarketDataCache | None = None,
        ttl_seconds: int = 30,
        audit_service: AuditService | None = None,
    ) -> None:
        self._market_data_service = market_data_service
        self._cache = cache
        self._ttl_seconds = ttl_seconds
        self._audit = audit_service

    async def handle(self, query: GetPriceQuery) -> StockQuote | None:
        """Return a quote, using cache when possible. Emits audit events."""
        symbol = query.symbol.strip().upper()

        if self._audit:
            self._audit.emit(domain_events.stock_requested(symbol, source="query"))

        if self._cache is not None:
            try:
                cached = await self._cache.get_quote(symbol)
            except Exception:
                cached = None
            if cached is not None:
                if self._audit:
                    self._audit.emit(domain_events.cache_hit(symbol, layer="cache", data_type="quote"))
                return cached

        if self._audit:
            self._audit.emit(domain_events.cache_miss(symbol, data_type="quote"))

        import time  # noqa: PLC0415
        t0 = time.perf_counter()
        quote = await self._market_data_service.get_quote(symbol)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        if self._audit:
            self._audit.emit(domain_events.quote_fetched(
                symbol,
                price=float(quote.current_price),
                provider=quote.source,
                elapsed_ms=elapsed_ms,
            ))

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
        audit_service: AuditService | None = None,
    ) -> None:
        self._market_data_service = market_data_service
        self._cache = cache
        self._ttl_seconds = ttl_seconds
        self._audit = audit_service

    async def handle(self, query: GetNewsQuery) -> list[NewsArticle]:
        """Return news articles, using cache when possible. Emits audit events."""
        symbol = query.symbol.strip().upper()

        if self._cache is not None:
            try:
                cached = await self._cache.get_news(symbol, query.limit)
            except Exception:
                cached = None
            if cached is not None:
                if self._audit:
                    self._audit.emit(domain_events.cache_hit(symbol, layer="cache", data_type="news"))
                return cached

        if self._audit:
            self._audit.emit(domain_events.cache_miss(symbol, data_type="news"))

        articles = await self._market_data_service.get_news(symbol, limit=query.limit)

        if self._audit:
            self._audit.emit(domain_events.news_fetched(
                symbol,
                article_count=len(articles),
                provider="yahoo",
            ))

        if self._cache is not None:
            try:
                await self._cache.set_news(symbol, query.limit, articles, ttl_seconds=self._ttl_seconds)
            except Exception:
                pass
        return articles
