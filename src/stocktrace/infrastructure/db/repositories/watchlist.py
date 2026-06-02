"""SQLAlchemy watchlist repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stocktrace.domain.entities.watchlist_item import WatchlistItem
from stocktrace.infrastructure.db.models.watchlist import WatchlistItemModel


class SqlAlchemyWatchlistRepository:
    """Persist watchlist items with SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, owner_id: str, symbol: str) -> WatchlistItem:
        """Add a watchlist item or return the existing one."""
        existing = await self._get(owner_id=owner_id, symbol=symbol)
        if existing is not None:
            return existing

        model = WatchlistItemModel(owner_id=owner_id, symbol=symbol)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            existing = await self._get(owner_id=owner_id, symbol=symbol)
            if existing is not None:
                return existing
            raise

        return self._to_domain(model)

    async def remove(self, owner_id: str, symbol: str) -> bool:
        """Remove a watchlist item."""
        result = await self._session.execute(
            select(WatchlistItemModel).where(
                WatchlistItemModel.owner_id == owner_id,
                WatchlistItemModel.symbol == symbol,
            ),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False

        await self._session.delete(model)
        return True

    async def list_by_owner(self, owner_id: str) -> list[WatchlistItem]:
        """List watchlist items by owner."""
        result = await self._session.execute(
            select(WatchlistItemModel)
            .where(WatchlistItemModel.owner_id == owner_id)
            .order_by(WatchlistItemModel.symbol.asc()),
        )
        return [self._to_domain(model) for model in result.scalars().all()]

    async def _get(self, owner_id: str, symbol: str) -> WatchlistItem | None:
        result = await self._session.execute(
            select(WatchlistItemModel).where(
                WatchlistItemModel.owner_id == owner_id,
                WatchlistItemModel.symbol == symbol,
            ),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: WatchlistItemModel) -> WatchlistItem:
        return WatchlistItem(
            id=model.id,
            owner_id=model.owner_id,
            symbol=model.symbol,
            created_at=model.created_at,
        )
