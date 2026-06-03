from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetPriceQuery:
    """Query intent: fetch the latest stock price for a symbol."""
    symbol: str


@dataclass(frozen=True)
class GetNewsQuery:
    """Query intent: fetch recent news articles for a symbol."""
    symbol: str
    limit: int = 5
