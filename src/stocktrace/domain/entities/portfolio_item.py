"""Portfolio item domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioItem:
    """A stock position tracked by a Telegram user."""

    id: str
    owner_id: str
    symbol: str
    quantity: int
    average_price: Decimal
    created_at: datetime
    updated_at: datetime
