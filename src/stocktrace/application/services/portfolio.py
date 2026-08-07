"""Portfolio application service."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from decimal import Decimal

from stocktrace.application.services.watchlist import normalize_symbol
from stocktrace.domain.entities.portfolio_item import PortfolioItem
from stocktrace.domain.repositories.portfolio import PortfolioRepository


class PortfolioService:
    """Coordinate portfolio use cases."""

    def __init__(
        self,
        repository_context_factory: Callable[[], AbstractAsyncContextManager[PortfolioRepository]],
    ) -> None:
        self._repository_context_factory = repository_context_factory

    async def add_position(
        self,
        owner_id: str,
        raw_symbol: str | None,
        quantity: int,
        average_price: Decimal,
    ) -> PortfolioItem:
        """Validate and add a position to a user's portfolio."""
        symbol = normalize_symbol(raw_symbol)
        async with self._repository_context_factory() as repository:
            return await repository.add_or_update(
                owner_id=owner_id,
                symbol=symbol,
                quantity=quantity,
                average_price=average_price,
            )

    async def remove_position(self, owner_id: str, raw_symbol: str | None) -> bool:
        """Validate and remove a position from a user's portfolio."""
        symbol = normalize_symbol(raw_symbol)
        async with self._repository_context_factory() as repository:
            return await repository.remove(owner_id=owner_id, symbol=symbol)

    async def list_positions(self, owner_id: str) -> list[PortfolioItem]:
        """List positions for a user."""
        async with self._repository_context_factory() as repository:
            return await repository.list_by_owner(owner_id=owner_id)
