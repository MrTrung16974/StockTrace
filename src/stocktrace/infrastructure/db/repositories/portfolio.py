"""SQLAlchemy portfolio repository."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stocktrace.domain.entities.portfolio_item import PortfolioItem
from stocktrace.infrastructure.db.models.portfolio import PortfolioItemModel


class SqlAlchemyPortfolioRepository:
    """Persist portfolio items with SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_or_update(
        self,
        owner_id: str,
        symbol: str,
        quantity: int,
        average_price: Decimal,
    ) -> PortfolioItem:
        """Add a new position or update an existing one."""
        existing = await self._get_model(owner_id=owner_id, symbol=symbol)
        
        if existing is not None:
            existing.quantity = quantity
            existing.average_price = average_price
            model = existing
        else:
            model = PortfolioItemModel(
                owner_id=owner_id,
                symbol=symbol,
                quantity=quantity,
                average_price=average_price,
            )
            self._session.add(model)
            try:
                await self._session.flush()
            except IntegrityError:
                await self._session.rollback()
                existing = await self._get_model(owner_id=owner_id, symbol=symbol)
                if existing is not None:
                    existing.quantity = quantity
                    existing.average_price = average_price
                    model = existing
                else:
                    raise

        return self._to_domain(model)

    async def remove(self, owner_id: str, symbol: str) -> bool:
        """Remove a portfolio item."""
        model = await self._get_model(owner_id=owner_id, symbol=symbol)
        if model is None:
            return False

        await self._session.delete(model)
        return True

    async def get_item(self, owner_id: str, symbol: str) -> PortfolioItem | None:
        """Get a specific position by symbol."""
        model = await self._get_model(owner_id=owner_id, symbol=symbol)
        if model is None:
            return None
        return self._to_domain(model)

    async def list_by_owner(self, owner_id: str) -> list[PortfolioItem]:
        """List portfolio items by owner."""
        result = await self._session.execute(
            select(PortfolioItemModel)
            .where(PortfolioItemModel.owner_id == owner_id)
            .order_by(PortfolioItemModel.symbol.asc()),
        )
        return [self._to_domain(model) for model in result.scalars().all()]

    async def _get_model(self, owner_id: str, symbol: str) -> PortfolioItemModel | None:
        result = await self._session.execute(
            select(PortfolioItemModel).where(
                PortfolioItemModel.owner_id == owner_id,
                PortfolioItemModel.symbol == symbol,
            ),
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_domain(model: PortfolioItemModel) -> PortfolioItem:
        return PortfolioItem(
            id=model.id,
            owner_id=model.owner_id,
            symbol=model.symbol,
            quantity=model.quantity,
            average_price=model.average_price,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
