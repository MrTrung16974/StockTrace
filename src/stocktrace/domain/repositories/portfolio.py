"""Portfolio repository contract."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from stocktrace.domain.entities.portfolio_item import PortfolioItem


class PortfolioRepository(Protocol):
    """Persistence contract for portfolio items."""

    async def add_or_update(
        self,
        owner_id: str,
        symbol: str,
        quantity: int,
        average_price: Decimal,
    ) -> PortfolioItem:
        """Add a new position or update an existing one."""

    async def remove(self, owner_id: str, symbol: str) -> bool:
        """Remove a symbol from an owner's portfolio."""

    async def get_item(self, owner_id: str, symbol: str) -> PortfolioItem | None:
        """Get a specific position by symbol."""

    async def list_by_owner(self, owner_id: str) -> list[PortfolioItem]:
        """List positions held by an owner."""
