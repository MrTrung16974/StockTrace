"""Market data application services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from stocktrace.application.services.watchlist import normalize_symbol


class MarketDataError(RuntimeError):
    """Raised when external market data cannot be retrieved."""


class QuoteNotFoundError(MarketDataError):
    """Raised when a provider cannot find a quote for the symbol."""


@dataclass(frozen=True, slots=True)
class StockQuote:
    """Latest quote data for a stock symbol."""

    ticker: str
    company_name: str
    current_price: Decimal
    change: Decimal
    change_percent: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: int
    timestamp: datetime
    currency: str = "USD"
    source: str = "Yahoo Finance"


@dataclass(frozen=True, slots=True)
class NewsArticle:
    """News article related to a stock symbol."""

    ticker: str
    title: str
    summary: str | None
    url: str
    source: str
    published_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class HistoricalPrice:
    """Historical price point."""
    date: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

@dataclass(frozen=True, slots=True)
class FundamentalData:
    """Fundamental financial data for a stock."""
    eps: Decimal | None = None
    pe: Decimal | None = None
    pb: Decimal | None = None
    roe: Decimal | None = None
    roa: Decimal | None = None
    foreign_buy_vol: int | None = None
    foreign_sell_vol: int | None = None

class QuoteProvider(Protocol):
    """Port for retrieving quote data."""

    async def get_quote(self, symbol: str) -> StockQuote:
        """Return the latest quote for a symbol."""
        ...

    async def get_historical_prices(self, symbol: str, days: int = 365) -> list[HistoricalPrice]:
        """Return historical prices for a symbol."""
        ...

    async def get_fundamental_data(self, symbol: str) -> FundamentalData:
        """Return fundamental data for a symbol."""
        ...

class NewsProvider(Protocol):
    """Port for retrieving stock news."""

    async def get_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        """Return latest news for a symbol."""
        ...


class MarketDataService:
    """Coordinate stock quote and news use cases."""

    def __init__(self, quote_provider: QuoteProvider, news_provider: NewsProvider) -> None:
        self._quote_provider = quote_provider
        self._news_provider = news_provider

    async def get_quote(self, raw_symbol: str | None) -> StockQuote:
        """Validate a symbol and return the latest quote."""
        symbol = normalize_symbol(raw_symbol)
        return await self._quote_provider.get_quote(symbol)

    async def get_news(self, raw_symbol: str | None, limit: int = 5) -> list[NewsArticle]:
        """Validate a symbol and return latest related news."""
        symbol = normalize_symbol(raw_symbol)
        return await self._news_provider.get_news(symbol=symbol, limit=limit)

    async def get_historical_prices(self, raw_symbol: str | None, days: int = 365) -> list[HistoricalPrice]:
        """Validate a symbol and return historical prices."""
        symbol = normalize_symbol(raw_symbol)
        return await self._quote_provider.get_historical_prices(symbol, days)

    async def get_fundamental_data(self, raw_symbol: str | None) -> FundamentalData:
        """Validate a symbol and return fundamental data."""
        symbol = normalize_symbol(raw_symbol)
        return await self._quote_provider.get_fundamental_data(symbol)
