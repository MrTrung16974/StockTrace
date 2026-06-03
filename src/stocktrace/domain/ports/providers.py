from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from stocktrace.domain.entities.news_article import NewsArticle
from stocktrace.domain.entities.stock_quote import StockQuote


class StockProvider(ABC):
    """Port: contract for fetching stock price data from any external source."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """Fetch the latest quote for a symbol. Returns None if not found."""
        ...

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Return True if the provider is reachable and functioning."""
        ...


class NewsProvider(ABC):
    """Port: contract for fetching news articles related to a stock symbol."""

    @abstractmethod
    async def get_news(self, symbol: str, limit: int = 5) -> List[NewsArticle]:
        """Fetch recent news articles for a symbol."""
        ...

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Return True if the provider is reachable and functioning."""
        ...
