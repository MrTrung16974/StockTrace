from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class StockQuote:
    """Immutable domain entity representing a stock price snapshot."""

    symbol: str
    price: float
    open: float
    high: float
    low: float
    volume: int
    previous_close: float
    currency: str
    exchange: str
    company_name: str
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None

    @property
    def change(self) -> float:
        return self.price - self.previous_close

    @property
    def change_percent(self) -> float:
        if self.previous_close == 0:
            return 0.0
        return (self.change / self.previous_close) * 100

    @property
    def change_emoji(self) -> str:
        if self.change > 0:
            return "📈"
        elif self.change < 0:
            return "📉"
        return "➡️"
