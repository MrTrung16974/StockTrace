"""Official trace source provider ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceDocument,
    TraceEventType,
    TraceSource,
)


class OfficialSourceProviderError(RuntimeError):
    """Raised when an official source cannot be reached or parsed."""


class OfficialSourceProvider(Protocol):
    """Port for retrieving normalized events from official market sources."""

    @property
    def provider_name(self) -> str:
        """Return provider identifier, for example HOSE, HNX, VSDC, SSC."""
        ...

    @property
    def source(self) -> TraceSource:
        """Return source metadata for auditability."""
        ...

    async def list_events(
        self,
        *,
        symbol: str | None = None,
        event_types: tuple[TraceEventType, ...] = (),
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[StockTraceEvent]:
        """Return normalized trace events from the source."""
        ...

    async def fetch_document(self, url: str) -> TraceDocument:
        """Fetch a source document for checksum and provenance storage."""
        ...
