"""Unit tests for StockQueryService application service."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import pytest

from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.stock_query_service import StockQueryService
from stocktrace.domain.entities.news_article import NewsArticle
from stocktrace.domain.entities.stock_quote import StockQuote
from stocktrace.domain.ports.providers import NewsProvider, StockProvider


# ── test doubles ─────────────────────────────────────────────────────────────

class FakeStockProvider(StockProvider):
    def __init__(self, quote: Optional[StockQuote] = None) -> None:
        self._quote = quote
        self.last_symbol: Optional[str] = None

    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        self.last_symbol = symbol
        return self._quote

    async def is_healthy(self) -> bool:
        return True


class BrokenStockProvider(StockProvider):
    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        raise RuntimeError("provider exploded")

    async def is_healthy(self) -> bool:
        return False


class FakeNewsProvider(NewsProvider):
    def __init__(self, articles: Optional[List[NewsArticle]] = None) -> None:
        self._articles = articles or []
        self.last_symbol: Optional[str] = None
        self.last_limit: Optional[int] = None

    async def get_news(self, symbol: str, limit: int = 5) -> List[NewsArticle]:
        self.last_symbol = symbol
        self.last_limit = limit
        return self._articles[:limit]

    async def is_healthy(self) -> bool:
        return True


class BrokenNewsProvider(NewsProvider):
    async def get_news(self, symbol: str, limit: int = 5) -> List[NewsArticle]:
        raise RuntimeError("news provider exploded")

    async def is_healthy(self) -> bool:
        return False


def _make_quote(symbol: str = "AAPL") -> StockQuote:
    return StockQuote(
        symbol=symbol,
        price=189.50,
        open=188.00,
        high=191.00,
        low=187.50,
        volume=55_000_000,
        previous_close=187.00,
        currency="USD",
        exchange="NASDAQ",
        company_name="Apple Inc.",
        fetched_at=datetime.utcnow(),
    )


def _make_article(symbol: str = "AAPL") -> NewsArticle:
    return NewsArticle(
        title=f"{symbol} news headline",
        url="https://example.com",
        source="Reuters",
        symbol=symbol,
        published_at=datetime.utcnow(),
    )


# ── get_price tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_price_returns_quote_for_valid_symbol():
    expected = _make_quote("AAPL")
    service = StockQueryService(
        stock_provider=FakeStockProvider(expected),
        news_provider=FakeNewsProvider(),
    )
    result = await service.get_price(GetPriceQuery(symbol="AAPL"))
    assert result is expected


@pytest.mark.asyncio
async def test_get_price_normalizes_symbol_to_uppercase():
    provider = FakeStockProvider(_make_quote("AAPL"))
    service = StockQueryService(stock_provider=provider, news_provider=FakeNewsProvider())

    await service.get_price(GetPriceQuery(symbol="aapl"))
    assert provider.last_symbol == "AAPL"


@pytest.mark.asyncio
async def test_get_price_strips_whitespace_from_symbol():
    provider = FakeStockProvider(_make_quote("HPG.VN"))
    service = StockQueryService(stock_provider=provider, news_provider=FakeNewsProvider())

    await service.get_price(GetPriceQuery(symbol="  HPG.VN  "))
    assert provider.last_symbol == "HPG.VN"


@pytest.mark.asyncio
async def test_get_price_returns_none_when_provider_finds_nothing():
    service = StockQueryService(
        stock_provider=FakeStockProvider(None),
        news_provider=FakeNewsProvider(),
    )
    result = await service.get_price(GetPriceQuery(symbol="UNKNOWN"))
    assert result is None


@pytest.mark.asyncio
async def test_get_price_returns_none_on_provider_exception():
    service = StockQueryService(
        stock_provider=BrokenStockProvider(),
        news_provider=FakeNewsProvider(),
    )
    # Must NOT raise — errors are swallowed and None returned
    result = await service.get_price(GetPriceQuery(symbol="AAPL"))
    assert result is None


# ── get_news tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_news_returns_articles_for_valid_symbol():
    articles = [_make_article("TSLA") for _ in range(3)]
    service = StockQueryService(
        stock_provider=FakeStockProvider(),
        news_provider=FakeNewsProvider(articles),
    )
    result = await service.get_news(GetNewsQuery(symbol="TSLA", limit=5))
    assert result == articles


@pytest.mark.asyncio
async def test_get_news_normalizes_symbol():
    provider = FakeNewsProvider([_make_article("TSLA")])
    service = StockQueryService(stock_provider=FakeStockProvider(), news_provider=provider)

    await service.get_news(GetNewsQuery(symbol="tsla"))
    assert provider.last_symbol == "TSLA"


@pytest.mark.asyncio
async def test_get_news_respects_limit():
    articles = [_make_article() for _ in range(10)]
    provider = FakeNewsProvider(articles)
    service = StockQueryService(stock_provider=FakeStockProvider(), news_provider=provider)

    result = await service.get_news(GetNewsQuery(symbol="AAPL", limit=3))
    assert len(result) <= 3
    assert provider.last_limit == 3


@pytest.mark.asyncio
async def test_get_news_returns_empty_list_when_provider_finds_nothing():
    service = StockQueryService(
        stock_provider=FakeStockProvider(),
        news_provider=FakeNewsProvider([]),
    )
    result = await service.get_news(GetNewsQuery(symbol="AAPL"))
    assert result == []


@pytest.mark.asyncio
async def test_get_news_returns_empty_list_on_provider_exception():
    service = StockQueryService(
        stock_provider=FakeStockProvider(),
        news_provider=BrokenNewsProvider(),
    )
    # Must NOT raise
    result = await service.get_news(GetNewsQuery(symbol="AAPL"))
    assert result == []
