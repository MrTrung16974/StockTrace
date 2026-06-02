"""Watchlist domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WatchlistItem:
    """A stock symbol tracked by a Telegram user."""

    id: str
    owner_id: str
    symbol: str
    created_at: datetime
