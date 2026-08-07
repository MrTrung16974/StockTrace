"""Portfolio application service tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from stocktrace.application.services.portfolio import PortfolioService
from stocktrace.domain.entities.portfolio_item import PortfolioItem


class FakePortfolioRepository:
    """In-memory portfolio repository for service tests."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], PortfolioItem] = {}

    async def add_or_update(
        self,
        owner_id: str,
        symbol: str,
        quantity: int,
        average_price: Decimal,
    ) -> PortfolioItem:
        item = PortfolioItem(
            id=f"{owner_id}:{symbol}",
            owner_id=owner_id,
            symbol=symbol,
            quantity=quantity,
            average_price=average_price,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        self.items[(owner_id, symbol)] = item
        return item

    async def remove(self, owner_id: str, symbol: str) -> bool:
        return self.items.pop((owner_id, symbol), None) is not None

    async def get_item(self, owner_id: str, symbol: str) -> PortfolioItem | None:
        return self.items.get((owner_id, symbol))

    async def list_by_owner(self, owner_id: str) -> list[PortfolioItem]:
        return sorted(
            [item for item in self.items.values() if item.owner_id == owner_id],
            key=lambda item: item.symbol,
        )


@pytest.mark.asyncio
async def test_portfolio_service_add_list_remove() -> None:
    repository = FakePortfolioRepository()

    @asynccontextmanager
    async def repository_context() -> AsyncIterator[FakePortfolioRepository]:
        yield repository

    service = PortfolioService(repository_context_factory=repository_context)

    # Test Add
    added = await service.add_position(owner_id="user-1", raw_symbol="fpt", quantity=100, average_price=Decimal("95.5"))
    assert added.symbol == "FPT"
    assert added.quantity == 100
    assert added.average_price == Decimal("95.5")

    # Test Update
    updated = await service.add_position(owner_id="user-1", raw_symbol="fpt", quantity=200, average_price=Decimal("100.0"))
    assert updated.quantity == 200
    assert updated.average_price == Decimal("100.0")

    # Test List
    listed = await service.list_positions(owner_id="user-1")
    assert len(listed) == 1
    assert listed[0].symbol == "FPT"

    # Test Remove
    removed = await service.remove_position(owner_id="user-1", raw_symbol="FPT")
    assert removed is True

    # Test List After Remove
    listed_after_remove = await service.list_positions(owner_id="user-1")
    assert listed_after_remove == []
