"""Watchlist repository integration tests."""

from __future__ import annotations

import pytest

from stocktrace.infrastructure.config import DatabaseSettings
from stocktrace.infrastructure.db.base import Base
from stocktrace.infrastructure.db.models import WatchlistItemModel
from stocktrace.infrastructure.db.repositories import SqlAlchemyWatchlistRepository
from stocktrace.infrastructure.db.session import SessionManager


@pytest.mark.asyncio
async def test_sqlalchemy_watchlist_repository_add_list_remove() -> None:
    manager = SessionManager(DatabaseSettings(url="sqlite+aiosqlite:///:memory:"))
    async with manager.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with manager.session() as session:
        repository = SqlAlchemyWatchlistRepository(session=session)
        added = await repository.add(owner_id="user-1", symbol="FPT")
        duplicate = await repository.add(owner_id="user-1", symbol="FPT")
        listed = await repository.list_by_owner(owner_id="user-1")
        removed = await repository.remove(owner_id="user-1", symbol="FPT")
        removed_again = await repository.remove(owner_id="user-1", symbol="FPT")

    await manager.dispose()

    assert WatchlistItemModel.__tablename__ == "watchlist_items"
    assert added.symbol == "FPT"
    assert duplicate.id == added.id
    assert [item.symbol for item in listed] == ["FPT"]
    assert removed is True
    assert removed_again is False
