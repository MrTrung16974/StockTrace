"""Tests for Vietnam index quotes supplied by vnstock."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from stocktrace.infrastructure.providers.vnstock_index import VNStockIndexProvider


class FakeFrame:
    """Minimal dataframe stand-in returned by vnstock."""

    def to_dict(self, orient: str):
        assert orient == "records"
        return [
            {
                "time": datetime(2026, 8, 4, tzinfo=UTC),
                "open": 1290,
                "high": 1300,
                "low": 1280,
                "close": 1295,
                "volume": 100,
            },
            {
                "time": datetime(2026, 8, 5, tzinfo=UTC),
                "open": 1298,
                "high": 1310,
                "low": 1290,
                "close": 1305,
                "volume": 120,
            },
        ]


@pytest.mark.asyncio
async def test_vnstock_index_provider_builds_quote_from_latest_two_bars() -> None:
    with patch(
        "stocktrace.infrastructure.providers.vnstock_index.asyncio.to_thread",
        new_callable=AsyncMock,
        return_value=FakeFrame(),
    ):
        quote = await VNStockIndexProvider().get_index_quote("vnindex")

    assert quote.ticker == "VNINDEX"
    assert quote.current_price == Decimal("1305")
    assert quote.change == Decimal("10")
    assert quote.change_percent == Decimal("0.7722007722007722007722007722")
    assert quote.source == "vnstock-kbs"
