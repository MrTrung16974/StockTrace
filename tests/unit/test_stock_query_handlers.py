"""Stock query handler tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from stocktrace.application.queries.stock_handlers import (
    GetStockNewsQueryHandler,
    GetStockQuoteQueryHandler,
)
from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.market_data import NewsArticle, StockQuote


class FakeMarketDataService:
    """Service double returning deterministic market data."""

    def __init__(self) -> None:
        self.quote_calls = 0
        self.news_calls = 0

    async def get_quote(self, raw_symbol: str | None) -> StockQuote:
        self.quote_calls += 1
        assert raw_symbol == "FPT"
        return StockQuote(
            ticker="FPT",
            company_name="FPT Corporation",
            current_price=Decimal("125000"),
            change=Decimal("1500"),
            change_percent=Decimal("1.21"),
            open_price=Decimal("123500"),
            high_price=Decimal("126000"),
            low_price=Decimal("122000"),
            volume=2350000,
            timestamp=datetime.now(tz=UTC),
            currency="VND",
            source="test",
        )

    async def get_news(self, raw_symbol: str | None, limit: int = 5) -> list[NewsArticle]:
        self.news_calls += 1
        assert raw_symbol == "FPT"
        assert limit == 5
        return [
            NewsArticle(
                ticker="FPT",
                title="FPT news",
                summary="summary",
                url="https://example.com",
                source="test",
            ),
        ]


class FakeCache:
    """Cache double storing values in memory."""

    def __init__(self) -> None:
        self.quote: StockQuote | None = None
        self.news: list[NewsArticle] | None = None

    async def get_quote(self, ticker: str) -> StockQuote | None:
        return self.quote

    async def set_quote(self, quote: StockQuote, ttl_seconds: int) -> None:
        self.quote = quote

    async def get_news(self, ticker: str, limit: int) -> list[NewsArticle] | None:
        return self.news

    async def set_news(
        self,
        ticker: str,
        limit: int,
        articles: list[NewsArticle],
        ttl_seconds: int,
    ) -> None:
        self.news = articles


@pytest.mark.asyncio
async def test_quote_handler_uses_cache_after_first_fetch() -> None:
    service = FakeMarketDataService()
    cache = FakeCache()
    handler = GetStockQuoteQueryHandler(service, cache=cache, ttl_seconds=30)

    first = await handler.handle(GetPriceQuery(symbol="fpt"))
    second = await handler.handle(GetPriceQuery(symbol="fpt"))

    assert first is not None
    assert second is not None
    assert service.quote_calls == 1


@pytest.mark.asyncio
async def test_news_handler_uses_cache_after_first_fetch() -> None:
    service = FakeMarketDataService()
    cache = FakeCache()
    handler = GetStockNewsQueryHandler(service, cache=cache, ttl_seconds=300)

    first = await handler.handle(GetNewsQuery(symbol="fpt"))
    second = await handler.handle(GetNewsQuery(symbol="fpt"))

    assert first[0].title == "FPT news"
    assert second[0].title == "FPT news"
    assert service.news_calls == 1
