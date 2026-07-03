"""Two-level cache: L1 (in-memory) → L2 (Redis) with automatic backfill."""

from __future__ import annotations

from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.domain.ports.market_data_cache import MarketDataCache
from stocktrace.infrastructure.cache.memory import InMemoryMarketDataCache
from stocktrace.infrastructure.cache.redis import RedisMarketDataCache
from stocktrace.infrastructure.logging.config import get_logger

# L1 TTL is intentionally short so it does not serve stale data for too long
_L1_QUOTE_TTL = 10   # seconds
_L1_NEWS_TTL = 60    # seconds


class LayeredMarketDataCache(MarketDataCache):
    """Cache-aside with L1 (process memory) → L2 (Redis) chain.

    Read path:  L1 hit → return immediately
                L1 miss, L2 hit → backfill L1, return
                L2 miss → caller fetches from provider
    Write path: write to L1 (short TTL) and L2 (full TTL) simultaneously
    """

    def __init__(self, l1: InMemoryMarketDataCache, l2: RedisMarketDataCache) -> None:
        self._l1 = l1
        self._l2 = l2
        self._logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # Quotes
    # ------------------------------------------------------------------

    async def get_quote(self, ticker: str) -> StockQuote | None:
        # L1
        result = await self._l1.get_quote(ticker)
        if result is not None:
            self._track_hit("L1", "quote")
            return result

        # L2
        result = await self._l2.get_quote(ticker)
        if result is not None:
            self._track_hit("L2", "quote")
            await self._l1.set_quote(result, ttl_seconds=_L1_QUOTE_TTL)
            return result

        self._track_miss("quote")
        return None

    async def set_quote(self, quote: StockQuote, ttl_seconds: int) -> None:
        await self._l1.set_quote(quote, ttl_seconds=min(ttl_seconds, _L1_QUOTE_TTL))
        await self._l2.set_quote(quote, ttl_seconds=ttl_seconds)

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    async def get_news(self, ticker: str, limit: int) -> list[NewsArticle] | None:
        result = await self._l1.get_news(ticker, limit)
        if result is not None:
            self._track_hit("L1", "news")
            return result

        result = await self._l2.get_news(ticker, limit)
        if result is not None:
            self._track_hit("L2", "news")
            await self._l1.set_news(ticker, limit, result, ttl_seconds=_L1_NEWS_TTL)
            return result

        self._track_miss("news")
        return None

    async def set_news(
        self,
        ticker: str,
        limit: int,
        articles: list[NewsArticle],
        ttl_seconds: int,
    ) -> None:
        await self._l1.set_news(ticker, limit, articles, ttl_seconds=min(ttl_seconds, _L1_NEWS_TTL))
        await self._l2.set_news(ticker, limit, articles, ttl_seconds=ttl_seconds)

    async def close(self) -> None:
        await self._l2.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _track_hit(self, layer: str, data_type: str) -> None:
        self._logger.debug("cache_hit", layer=layer, data_type=data_type)
        try:
            from stocktrace.infrastructure.metrics.prometheus import cache_hits_total  # noqa: PLC0415

            cache_hits_total.labels(layer=layer).inc()
        except Exception:  # noqa: BLE001
            pass

    def _track_miss(self, data_type: str) -> None:
        self._logger.debug("cache_miss", data_type=data_type)
        try:
            from stocktrace.infrastructure.metrics.prometheus import cache_misses_total  # noqa: PLC0415

            cache_misses_total.inc()
        except Exception:  # noqa: BLE001
            pass
