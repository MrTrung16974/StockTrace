"""Watchlist application service tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from stocktrace.application.services.watchlist import (
    InvalidSymbolError,
    WatchlistService,
    normalize_symbol,
)
from stocktrace.domain.entities.watchlist_item import WatchlistItem


class FakeWatchlistRepository:
    """In-memory watchlist repository for service tests."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], WatchlistItem] = {}

    async def add(self, owner_id: str, symbol: str) -> WatchlistItem:
        item = self.items.get((owner_id, symbol))
        if item is not None:
            return item

        item = WatchlistItem(
            id=f"{owner_id}:{symbol}",
            owner_id=owner_id,
            symbol=symbol,
            created_at=datetime.now(tz=UTC),
        )
        self.items[(owner_id, symbol)] = item
        return item

    async def remove(self, owner_id: str, symbol: str) -> bool:
        return self.items.pop((owner_id, symbol), None) is not None

    async def list_by_owner(self, owner_id: str) -> list[WatchlistItem]:
        return sorted(
            [item for item in self.items.values() if item.owner_id == owner_id],
            key=lambda item: item.symbol,
        )


def test_normalize_symbol_accepts_supported_characters() -> None:
    assert normalize_symbol(" fpt ") == "FPT"
    assert normalize_symbol("msft.us") == "MSFT.US"


def test_normalize_symbol_rejects_invalid_input() -> None:
    with pytest.raises(InvalidSymbolError):
        normalize_symbol("bad symbol")


@pytest.mark.asyncio
async def test_watchlist_service_add_list_remove() -> None:
    repository = FakeWatchlistRepository()

    @asynccontextmanager
    async def repository_context() -> AsyncIterator[FakeWatchlistRepository]:
        yield repository

    service = WatchlistService(repository_context_factory=repository_context)

    added = await service.add_symbol(owner_id="user-1", raw_symbol="fpt")
    listed = await service.list_symbols(owner_id="user-1")
    removed = await service.remove_symbol(owner_id="user-1", raw_symbol="FPT")
    listed_after_remove = await service.list_symbols(owner_id="user-1")

    assert added.symbol == "FPT"
    assert [item.symbol for item in listed] == ["FPT"]
    assert removed is True
    assert listed_after_remove == []
