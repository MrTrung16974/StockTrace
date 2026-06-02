"""Watchlist application service."""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from stocktrace.domain.entities.watchlist_item import WatchlistItem
from stocktrace.domain.repositories.watchlist import WatchlistRepository

SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,15}$")


class InvalidSymbolError(ValueError):
    """Raised when a stock symbol is invalid."""


class WatchlistService:
    """Coordinate watchlist use cases."""

    def __init__(
        self,
        repository_context_factory: Callable[[], AbstractAsyncContextManager[WatchlistRepository]],
    ) -> None:
        self._repository_context_factory = repository_context_factory

    async def add_symbol(self, owner_id: str, raw_symbol: str | None) -> WatchlistItem:
        """Validate and add a symbol to a user's watchlist."""
        symbol = normalize_symbol(raw_symbol)
        async with self._repository_context_factory() as repository:
            return await repository.add(owner_id=owner_id, symbol=symbol)

    async def remove_symbol(self, owner_id: str, raw_symbol: str | None) -> bool:
        """Validate and remove a symbol from a user's watchlist."""
        symbol = normalize_symbol(raw_symbol)
        async with self._repository_context_factory() as repository:
            return await repository.remove(owner_id=owner_id, symbol=symbol)

    async def list_symbols(self, owner_id: str) -> list[WatchlistItem]:
        """List symbols for a user."""
        async with self._repository_context_factory() as repository:
            return await repository.list_by_owner(owner_id=owner_id)


def normalize_symbol(raw_symbol: str | None) -> str:
    """Normalize and validate user-provided symbols."""
    symbol = (raw_symbol or "").strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise InvalidSymbolError(
            "Symbol must be 1-16 characters and contain only letters, numbers, dot, dash, "
            "or underscore.",
        )
    return symbol
