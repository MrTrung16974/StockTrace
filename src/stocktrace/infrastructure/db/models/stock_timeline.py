"""Stock timeline ORM model — per-symbol lifecycle events."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from stocktrace.infrastructure.db.base import Base


class StockTimelineModel(Base):
    """Records the full lifecycle of a stock data fetch cycle."""

    __tablename__ = "stock_timeline"
    __table_args__ = (
        Index("ix_stock_timeline_symbol", "symbol"),
        Index("ix_stock_timeline_trace_id", "trace_id"),
        Index("ix_stock_timeline_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    # e.g. SCHEDULER_TRIGGER | QUOTE_FETCH | NEWS_FETCH | RULE_TRIGGER | ALERT_SEND
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
