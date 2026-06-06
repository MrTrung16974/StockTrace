"""Historical market data port."""

from __future__ import annotations

from typing import Protocol

from stocktrace.ai.models import HistoricalPoint


class HistoricalProvider(Protocol):
    """Outbound port for recent historical price data."""

    async def get_recent(self, symbol: str, days: int = 30) -> list[HistoricalPoint]:
        """Return recent daily price observations."""
        ...
