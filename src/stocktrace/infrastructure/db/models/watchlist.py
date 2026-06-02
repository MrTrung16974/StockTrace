"""Watchlist ORM model."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from stocktrace.infrastructure.db.base import Base


class WatchlistItemModel(Base):
    """Database representation of a watchlist item."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("owner_id", "symbol", name="uq_watchlist_items_owner_symbol"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
