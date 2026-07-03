"""SQLAlchemy implementation of the AuditRepository port."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stocktrace.domain.events import DomainEvent
from stocktrace.infrastructure.db.models.audit import AuditEventModel
from stocktrace.infrastructure.db.models.stock_timeline import StockTimelineModel


class SqlAlchemyAuditRepository:
    """Store and query audit events using the existing SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_event(self, event: DomainEvent) -> None:
        """Persist a domain event and also record it in the stock timeline."""
        model = AuditEventModel(
            event_id=event.event_id,
            trace_id=event.trace_id,
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            payload=json.dumps(event.payload),
            created_at=event.created_at,
        )
        self._session.add(model)

        # Mirror to stock_timeline when aggregate_id looks like a ticker (≤ 10 chars)
        if len(event.aggregate_id) <= 10:  # noqa: PLR2004
            timeline = StockTimelineModel(
                trace_id=event.trace_id,
                symbol=event.aggregate_id.upper(),
                event_type=event.event_type,
                payload=json.dumps(event.payload),
                created_at=event.created_at,
            )
            self._session.add(timeline)

    async def get_trace(self, trace_id: str) -> list[DomainEvent]:
        """Return all events for a trace in chronological order."""
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.trace_id == trace_id)
            .order_by(AuditEventModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars()]

    async def get_symbol_timeline(self, symbol: str, limit: int = 50) -> list[DomainEvent]:
        """Return the most recent timeline events for a symbol."""
        stmt = (
            select(StockTimelineModel)
            .where(StockTimelineModel.symbol == symbol.upper())
            .order_by(StockTimelineModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_timeline_to_domain(row) for row in reversed(rows)]


def _to_domain(model: AuditEventModel) -> DomainEvent:
    return DomainEvent(
        event_id=model.event_id,
        trace_id=model.trace_id,
        event_type=model.event_type,
        aggregate_id=model.aggregate_id,
        payload=json.loads(model.payload),
        created_at=model.created_at.replace(tzinfo=UTC) if model.created_at.tzinfo is None else model.created_at,
    )


def _timeline_to_domain(model: StockTimelineModel) -> DomainEvent:
    import uuid  # noqa: PLC0415

    return DomainEvent(
        event_id=str(uuid.uuid4()),
        trace_id=model.trace_id,
        event_type=model.event_type,
        aggregate_id=model.symbol,
        payload=json.loads(model.payload),
        created_at=model.created_at.replace(tzinfo=UTC) if model.created_at.tzinfo is None else model.created_at,
    )
