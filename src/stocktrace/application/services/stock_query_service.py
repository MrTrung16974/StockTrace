from __future__ import annotations

import logging
from typing import List, Optional

from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.domain.entities.news_article import NewsArticle
from stocktrace.domain.entities.stock_quote import StockQuote
from stocktrace.domain.ports.providers import NewsProvider, StockProvider

logger = logging.getLogger(__name__)


class StockQueryService:
    """
    Application service that handles price and news queries.

    Orchestrates provider calls, handles errors, and returns domain entities.
    Does not own any infrastructure details — those live in the adapters.
    """

    def __init__(self, stock_provider: StockProvider, news_provider: NewsProvider) -> None:
        self._stock_provider = stock_provider
        self._news_provider = news_provider

    async def get_price(self, query: GetPriceQuery) -> Optional[StockQuote]:
        """
        Resolve the latest quote for a symbol.

        Returns None if the symbol is unknown or the provider is unavailable.
        """
        symbol = query.symbol.upper().strip()
        logger.info("get_price: symbol=%s", symbol)
        try:
            quote = await self._stock_provider.get_quote(symbol)
            if quote is None:
                logger.warning("get_price: no data returned for symbol=%s", symbol)
            return quote
        except Exception as exc:
            logger.error("get_price: provider error for symbol=%s: %s", symbol, exc)
            return None

    async def get_news(self, query: GetNewsQuery) -> List[NewsArticle]:
        """
        Resolve recent news articles for a symbol.

        Returns an empty list on provider failure so callers never crash.
        """
        symbol = query.symbol.upper().strip()
        logger.info("get_news: symbol=%s limit=%d", symbol, query.limit)
        try:
            articles = await self._news_provider.get_news(symbol, limit=query.limit)
            logger.info("get_news: found %d articles for symbol=%s", len(articles), symbol)
            return articles
        except Exception as exc:
            logger.error("get_news: provider error for symbol=%s: %s", symbol, exc)
            return []
