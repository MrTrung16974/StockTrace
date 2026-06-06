"""Application composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from stocktrace.ai.analysis_service import AnalysisService
from stocktrace.ai.prompt_builder import PromptBuilder
from stocktrace.ai.translation_service import TranslationService
from stocktrace.application.queries.stock_handlers import (
    GetStockNewsQueryHandler,
    GetStockQuoteQueryHandler,
)
from stocktrace.application.services.health import HealthCheckService
from stocktrace.application.services.market_data import MarketDataService
from stocktrace.application.services.stock_analysis_service import StockAnalysisService
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.domain.ports.ai_cache import AICache
from stocktrace.domain.ports.market_data_cache import MarketDataCache
from stocktrace.domain.repositories.watchlist import WatchlistRepository
from stocktrace.infrastructure.ai.provider_factory import create_llm_provider
from stocktrace.infrastructure.cache.memory import InMemoryMarketDataCache
from stocktrace.infrastructure.cache.memory_ai_cache import InMemoryAICache
from stocktrace.infrastructure.cache.redis import RedisMarketDataCache
from stocktrace.infrastructure.cache.redis_ai_cache import RedisAICache
from stocktrace.infrastructure.config import Settings, get_settings
from stocktrace.infrastructure.db.repositories import SqlAlchemyWatchlistRepository
from stocktrace.infrastructure.db.session import SessionManager
from stocktrace.infrastructure.news.yahoo import YahooFinanceNewsProvider
from stocktrace.infrastructure.providers.yahoo import YahooFinanceQuoteProvider
from stocktrace.infrastructure.providers.yahoo_historical import YahooHistoricalProvider
from stocktrace.infrastructure.scheduler.protocols import TelegramMessageBot
from stocktrace.infrastructure.scheduler.service import SchedulerService
from stocktrace.infrastructure.scheduler.stock_analysis_job import StockAnalysisJob


class Container:
    """Composition root for application services and adapters."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session_manager = SessionManager(settings.database)
        self._market_data_cache: MarketDataCache | None = None
        self._ai_cache: AICache | None = None
        self._market_data_service: MarketDataService | None = None
        self._quote_query_handler: GetStockQuoteQueryHandler | None = None
        self._news_query_handler: GetStockNewsQueryHandler | None = None
        self._analysis_service: AnalysisService | None = None
        self._translation_service: TranslationService | None = None
        self._stock_analysis_service: StockAnalysisService | None = None
        self._historical_provider: YahooHistoricalProvider | None = None

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

    def ai_cache(self) -> AICache:
        """Build the cache adapter for AI responses."""
        if self._ai_cache is None:
            redis_settings = self._settings.redis
            if redis_settings.enabled:
                try:
                    self._ai_cache = RedisAICache(url=redis_settings.url)
                except Exception:
                    self._ai_cache = InMemoryAICache()
            else:
                self._ai_cache = InMemoryAICache()
        return self._ai_cache

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

    def historical_provider(self) -> YahooHistoricalProvider:
        """Build the historical price provider."""
        if self._historical_provider is None:
            timeout_seconds = float(self._settings.providers.request_timeout_seconds)
            self._historical_provider = YahooHistoricalProvider(timeout_seconds=timeout_seconds)
        return self._historical_provider

    def analysis_service(self) -> AnalysisService:
        """Build the core AI analysis service."""
        if self._analysis_service is None:
            ai_settings = self._settings.ai
            self._analysis_service = AnalysisService(
                llm=create_llm_provider(ai_settings),
                prompt_builder=PromptBuilder(
                    max_tokens=ai_settings.max_tokens,
                    temperature=ai_settings.temperature,
                ),
                settings=ai_settings,
                cache=self.ai_cache(),
            )
        return self._analysis_service

    def translation_service(self) -> TranslationService:
        """Build the AI translation service."""
        if self._translation_service is None:
            ai_settings = self._settings.ai
            self._translation_service = TranslationService(
                llm=create_llm_provider(ai_settings),
                settings=ai_settings,
                cache=self.ai_cache(),
            )
        return self._translation_service

    def stock_analysis_service(self) -> StockAnalysisService:
        """Build the stock analysis application service."""
        if self._stock_analysis_service is None:
            self._stock_analysis_service = StockAnalysisService(
                quote_handler=self.quote_query_handler(),
                news_handler=self.news_query_handler(),
                analysis_service=self.analysis_service(),
                translation_service=self.translation_service(),
                historical_provider=self.historical_provider(),
                market_data_service=self.market_data_service(),
            )
        return self._stock_analysis_service

    def stock_analysis_job(self, bot: TelegramMessageBot) -> StockAnalysisJob:
        """Build scheduled AI analysis jobs."""
        return StockAnalysisJob(
            stock_analysis_service=self.stock_analysis_service(),
            watchlist_service=self.watchlist_service(),
            bot=bot,
            settings=self._settings,
        )

    def scheduler_service(self, bot: TelegramMessageBot) -> SchedulerService:
        """Build the scheduled Telegram job service."""
        return SchedulerService(
            quote_handler=self.quote_query_handler(),
            news_handler=self.news_query_handler(),
            watchlist_service=self.watchlist_service(),
            bot=bot,
            settings=self._settings,
            analysis_job=self.stock_analysis_job(bot),
        )

    async def dispose(self) -> None:
        """Dispose infrastructure resources."""
        if self._market_data_cache is not None and hasattr(self._market_data_cache, "close"):
            await self._market_data_cache.close()  # type: ignore[func-returns-value]
        if self._ai_cache is not None:
            await self._ai_cache.close()
        await self._session_manager.dispose()

    @asynccontextmanager
    async def _watchlist_repository(self) -> AsyncIterator[WatchlistRepository]:
        async with self._session_manager.session() as session:
            yield SqlAlchemyWatchlistRepository(session=session)


@lru_cache(maxsize=1)
def get_container() -> Container:
    """Return the process-level dependency container."""
    return Container(settings=get_settings())
