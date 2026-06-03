"""Market data service tests."""

from __future__ import annotations

from decimal import Decimal
from datetime import UTC, datetime

import pytest

from stocktrace.application.services.market_data import (
    MarketDataService,
    NewsArticle,
    StockQuote,
)


class FakeQuoteProvider:
    """Quote provider test double."""

    async def get_quote(self, symbol: str) -> StockQuote:
        return StockQuote(
            ticker=symbol,
            company_name="FPT Corporation",
            current_price=Decimal("10"),
            change=Decimal("0"),
            change_percent=Decimal("0"),
            open_price=Decimal("10"),
            high_price=Decimal("10"),
            low_price=Decimal("10"),
            volume=100,
            timestamp=datetime.now(tz=UTC),
            currency="USD",
            source="test",
        )


class FakeNewsProvider:
    """News provider test double."""

    async def get_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        return [
            NewsArticle(
                ticker=symbol,
                title=f"{symbol} news",
                summary="summary",
                url="https://example.com",
                source="test",
            ),
        ][:limit]


@pytest.mark.asyncio
async def test_market_data_service_normalizes_symbol() -> None:
    service = MarketDataService(
        quote_provider=FakeQuoteProvider(),
        news_provider=FakeNewsProvider(),
    )

    quote = await service.get_quote(" fpt ")
    articles = await service.get_news(" fpt ", limit=1)

    assert quote.ticker == "FPT"
    assert articles[0].title == "FPT news"
