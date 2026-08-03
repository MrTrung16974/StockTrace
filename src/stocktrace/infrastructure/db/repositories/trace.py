"""SQLAlchemy trace engine repositories."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceDocument,
    TraceEventType,
    TraceReason,
    TraceSeverity,
    TraceSource,
    TraceSourceType,
)
from stocktrace.infrastructure.db.models.trace import (
    TraceDocumentModel,
    TraceEventModel,
    TraceSourceModel,
)


class SqlAlchemyTraceRepository:
    """Persist and query normalized trace engine data."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_source(self, source: TraceSource) -> None:
        """Insert or update a trace source."""
        existing = await self._session.get(TraceSourceModel, source.code)
        if existing is None:
            self._session.add(
                TraceSourceModel(
                    code=source.code,
                    name=source.name,
                    source_type=source.source_type.value,
                    base_url=source.base_url,
                    rank=source.rank,
                    official=source.official,
                    description=source.description,
                ),
            )
            return

        existing.name = source.name
        existing.source_type = source.source_type.value
        existing.base_url = source.base_url
        existing.rank = source.rank
        existing.official = source.official
        existing.description = source.description

    async def get_source(self, code: str) -> TraceSource | None:
        """Return source metadata by code."""
        model = await self._session.get(TraceSourceModel, code)
        if model is None:
            return None
        return self._source_to_domain(model)

    async def save_document(self, document: TraceDocument) -> None:
        """Persist a fetched source document."""
        if document.checksum and await self.get_document_by_checksum(document.checksum):
            return
        self._session.add(
            TraceDocumentModel(
                id=str(uuid4()),
                source_code=document.source_code,
                title=document.title,
                url=document.url,
                published_at=document.published_at,
                fetched_at=document.fetched_at,
                checksum=document.checksum,
                content_type=document.content_type,
                raw_text=document.raw_text,
            ),
        )

    async def get_document_by_checksum(self, checksum: str) -> TraceDocument | None:
        """Return a document by checksum."""
        result = await self._session.execute(
            select(TraceDocumentModel).where(TraceDocumentModel.checksum == checksum),
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._document_to_domain(model)

    async def save_event(self, event: StockTraceEvent) -> None:
        """Persist a normalized trace event."""
        duplicate = await self._session.execute(
            select(TraceEventModel.id).where(
                TraceEventModel.symbol == event.symbol,
                TraceEventModel.event_type == event.event_type.value,
                TraceEventModel.source_code == event.source.code,
                TraceEventModel.source_url == event.source_url,
                TraceEventModel.title == event.title,
                TraceEventModel.occurred_at == event.occurred_at,
            ).limit(1),
        )
        if duplicate.scalar_one_or_none() is not None:
            return

        document_id = None
        if event.document is not None:
            existing_document_id = None
            if event.document.checksum:
                result = await self._session.execute(
                    select(TraceDocumentModel.id).where(
                        TraceDocumentModel.checksum == event.document.checksum,
                    ).limit(1),
                )
                existing_document_id = result.scalar_one_or_none()
            document_id = existing_document_id or str(uuid4())
            if existing_document_id is None:
                self._session.add(self._document_to_model(event.document, document_id))

        await self.upsert_source(event.source)
        self._session.add(
            TraceEventModel(
                id=str(uuid4()),
                symbol=event.symbol,
                event_type=event.event_type.value,
                severity=event.severity.value,
                title=event.title,
                summary=event.summary,
                source_code=event.source.code,
                source_url=event.source_url,
                document_id=document_id,
                reasons_json=self._reasons_to_json(event.reasons),
                metadata_json=json.dumps(event.metadata, sort_keys=True),
                confidence=float(event.confidence),
                occurred_at=event.occurred_at,
                created_at=event.created_at,
            ),
        )

    async def list_events(
        self,
        *,
        symbol: str | None = None,
        event_types: tuple[TraceEventType, ...] = (),
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[StockTraceEvent]:
        """Return trace events matching the filter."""
        stmt = (
            select(TraceEventModel, TraceSourceModel, TraceDocumentModel)
            .join(TraceSourceModel, TraceEventModel.source_code == TraceSourceModel.code)
            .outerjoin(TraceDocumentModel, TraceEventModel.document_id == TraceDocumentModel.id)
            .order_by(TraceEventModel.created_at.desc())
            .limit(limit)
        )

        if symbol is not None:
            stmt = stmt.where(TraceEventModel.symbol == symbol)
        if event_types:
            stmt = stmt.where(TraceEventModel.event_type.in_([item.value for item in event_types]))
        if since is not None:
            stmt = stmt.where(
                func.coalesce(TraceEventModel.occurred_at, TraceEventModel.created_at) >= since,
            )

        result = await self._session.execute(stmt)
        return [
            self._event_to_domain(event_model, source_model, document_model)
            for event_model, source_model, document_model in result.all()
        ]

    def _document_to_model(self, document: TraceDocument, document_id: str) -> TraceDocumentModel:
        return TraceDocumentModel(
            id=document_id,
            source_code=document.source_code,
            title=document.title,
            url=document.url,
            published_at=document.published_at,
            fetched_at=document.fetched_at,
            checksum=document.checksum,
            content_type=document.content_type,
            raw_text=document.raw_text,
        )

    def _event_to_domain(
        self,
        event: TraceEventModel,
        source: TraceSourceModel,
        document: TraceDocumentModel | None,
    ) -> StockTraceEvent:
        return StockTraceEvent(
            symbol=event.symbol,
            event_type=TraceEventType(event.event_type),
            severity=TraceSeverity(event.severity),
            title=event.title,
            summary=event.summary,
            source=self._source_to_domain(source),
            document=self._document_to_domain(document) if document is not None else None,
            reasons=self._reasons_from_json(event.reasons_json),
            confidence=Decimal(str(event.confidence)),
            occurred_at=event.occurred_at,
            created_at=event.created_at,
            metadata=json.loads(event.metadata_json),
        )

    def _source_to_domain(self, source: TraceSourceModel) -> TraceSource:
        return TraceSource(
            code=source.code,
            name=source.name,
            source_type=TraceSourceType(source.source_type),
            base_url=source.base_url,
            rank=source.rank,
            official=source.official,
            description=source.description,
        )

    def _document_to_domain(self, document: TraceDocumentModel) -> TraceDocument:
        return TraceDocument(
            source_code=document.source_code,
            title=document.title,
            url=document.url,
            published_at=document.published_at,
            fetched_at=document.fetched_at,
            checksum=document.checksum,
            content_type=document.content_type,
            raw_text=document.raw_text,
        )

    def _reasons_to_json(self, reasons: tuple[TraceReason, ...]) -> str:
        return json.dumps(
            [
                {
                    "label": reason.label,
                    "detail": reason.detail,
                    "weight": str(reason.weight),
                }
                for reason in reasons
            ],
            sort_keys=True,
        )

    def _reasons_from_json(self, raw: str) -> tuple[TraceReason, ...]:
        payload = json.loads(raw)
        return tuple(
            TraceReason(
                label=item["label"],
                detail=item["detail"],
                weight=Decimal(str(item.get("weight", "1"))),
            )
            for item in payload
        )
