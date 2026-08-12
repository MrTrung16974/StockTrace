"""Tests for retry behavior of the resilient market-data provider."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from stocktrace.application.services.market_data import StockQuote
from stocktrace.infrastructure.providers.resilient_provider import ResilientQuoteProvider

_EXPECTED_RETRY_CALLS = 2


class _FlakyQuoteProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def get_quote(self, symbol: str) -> StockQuote:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary provider failure")
        return StockQuote(
            ticker=symbol,
            company_name="Test",
            current_price=Decimal("10"),
            change=Decimal("0"),
            change_percent=Decimal("0"),
            open_price=Decimal("10"),
            high_price=Decimal("10"),
            low_price=Decimal("10"),
            volume=1,
            timestamp=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_resilient_provider_retries_with_a_fresh_coroutine() -> None:
    inner = _FlakyQuoteProvider()
    provider = ResilientQuoteProvider(inner, max_retries=2)

    quote = await provider.get_quote("HPG")

    assert quote.ticker == "HPG"
    assert inner.calls == _EXPECTED_RETRY_CALLS
