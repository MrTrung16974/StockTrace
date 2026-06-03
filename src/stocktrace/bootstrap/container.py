"""Application composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from stocktrace.application.queries.stock_handlers import (
    GetStockNewsQueryHandler,
    GetStockQuoteQueryHandler,
)
from stocktrace.application.services.health import HealthCheckService
from stocktrace.application.services.market_data import MarketDataService
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.domain.ports.market_data_cache import MarketDataCache
from stocktrace.domain.repositories.watchlist import WatchlistRepository
from stocktrace.infrastructure.cache.memory import InMemoryMarketDataCache
from stocktrace.infrastructure.cache.redis import RedisMarketDataCache
from stocktrace.infrastructure.config import Settings, get_settings
from stocktrace.infrastructure.db.repositories import SqlAlchemyWatchlistRepository
from stocktrace.infrastructure.db.session import SessionManager
from stocktrace.infrastructure.news.yahoo import YahooFinanceNewsProvider
from stocktrace.infrastructure.providers.yahoo import YahooFinanceQuoteProvider
from stocktrace.infrastructure.scheduler.service import SchedulerService, TelegramMessageBot


class Container:
    """Composition root for application services and adapters."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session_manager = SessionManager(settings.database)
        self._market_data_cache: MarketDataCache | None = None
        self._market_data_service: MarketDataService | None = None
        self._quote_query_handler: GetStockQuoteQueryHandler | None = None
        self._news_query_handler: GetStockNewsQueryHandler | None = None

    def health_service(self) -> HealthCheckService:
        """Build the health service."""
        return HealthCheckService(
            service_name=self._settings.app.name,
            version=self._settings.app.version,
            environment=self._settings.environment.value,
        )

    def watchlist_service(self) -> WatchlistService:
        """Build the watchlist service."""
        return WatchlistService(repository_context_factory=self._watchlist_repository)

    def market_data_service(self) -> MarketDataService:
        """Build the market data service."""
        if self._market_data_service is None:
            timeout_seconds = float(self._settings.providers.request_timeout_seconds)
            self._market_data_service = MarketDataService(
                quote_provider=YahooFinanceQuoteProvider(timeout_seconds=timeout_seconds),
                news_provider=YahooFinanceNewsProvider(timeout_seconds=timeout_seconds),
            )
        return self._market_data_service

    def market_data_cache(self) -> MarketDataCache:
        """Build the cache adapter for market data queries."""
        if self._market_data_cache is None:
            redis_settings = self._settings.redis
            if redis_settings.enabled:
                try:
                    self._market_data_cache = RedisMarketDataCache(url=redis_settings.url)
                except Exception:
                    self._market_data_cache = InMemoryMarketDataCache()
            else:
                self._market_data_cache = InMemoryMarketDataCache()
        return self._market_data_cache

    def quote_query_handler(self) -> GetStockQuoteQueryHandler:
        """Build the stock quote query handler."""
        if self._quote_query_handler is None:
            self._quote_query_handler = GetStockQuoteQueryHandler(
                market_data_service=self.market_data_service(),
                cache=self.market_data_cache(),
                ttl_seconds=self._settings.cache.quote_ttl_seconds,
            )
        return self._quote_query_handler

    def news_query_handler(self) -> GetStockNewsQueryHandler:
        """Build the stock news query handler."""
        if self._news_query_handler is None:
            self._news_query_handler = GetStockNewsQueryHandler(
                market_data_service=self.market_data_service(),
                cache=self.market_data_cache(),
                ttl_seconds=self._settings.cache.news_ttl_seconds,
            )
        return self._news_query_handler

    def scheduler_service(self, bot: TelegramMessageBot) -> SchedulerService:
        """Build the scheduled Telegram job service."""
        return SchedulerService(
            quote_handler=self.quote_query_handler(),
            news_handler=self.news_query_handler(),
            bot=bot,
            settings=self._settings,
        )

    async def dispose(self) -> None:
        """Dispose infrastructure resources."""
        if self._market_data_cache is not None and hasattr(self._market_data_cache, "close"):
            await self._market_data_cache.close()  # type: ignore[func-returns-value]
        await self._session_manager.dispose()

    @asynccontextmanager
    async def _watchlist_repository(self) -> AsyncIterator[WatchlistRepository]:
        async with self._session_manager.session() as session:
            yield SqlAlchemyWatchlistRepository(session=session)


@lru_cache(maxsize=1)
def get_container() -> Container:
    """Return the process-level dependency container."""
    return Container(settings=get_settings())
