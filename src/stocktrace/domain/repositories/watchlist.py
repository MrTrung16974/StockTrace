"""Watchlist repository contract."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.entities.watchlist_item import WatchlistItem


class WatchlistRepository(Protocol):
    """Persistence contract for watchlist items."""

    async def add(self, owner_id: str, symbol: str) -> WatchlistItem:
        """Add a symbol to an owner's watchlist."""

    async def remove(self, owner_id: str, symbol: str) -> bool:
        """Remove a symbol from an owner's watchlist."""

    async def list_by_owner(self, owner_id: str) -> list[WatchlistItem]:
        """List symbols tracked by an owner."""
