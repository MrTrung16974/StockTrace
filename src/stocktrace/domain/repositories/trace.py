"""Trace engine repository ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceDocument,
    TraceEventType,
    TraceSource,
)


class TraceSourceRepository(Protocol):
    """Persistence port for trace source metadata."""

    async def upsert_source(self, source: TraceSource) -> None:
        """Insert or update a trace source."""
        ...

    async def get_source(self, code: str) -> TraceSource | None:
        """Return source metadata by code."""
        ...


class TraceDocumentRepository(Protocol):
    """Persistence port for source documents."""

    async def save_document(self, document: TraceDocument) -> None:
        """Persist a fetched source document."""
        ...

    async def get_document_by_checksum(self, checksum: str) -> TraceDocument | None:
        """Return a document by checksum."""
        ...


class TraceEventRepository(Protocol):
    """Persistence port for normalized trace events."""

    async def save_event(self, event: StockTraceEvent) -> None:
        """Persist a normalized trace event."""
        ...

    async def list_events(
        self,
        *,
        symbol: str | None = None,
        event_types: tuple[TraceEventType, ...] = (),
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[StockTraceEvent]:
        """Return trace events matching the filter."""
        ...
