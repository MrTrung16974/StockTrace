"""Port for storing and querying audit events."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.events import DomainEvent


class AuditRepository(Protocol):
    """Persist and query the audit event log."""

    async def save_event(self, event: DomainEvent) -> None:
        """Persist a single domain event."""
        ...

    async def get_trace(self, trace_id: str) -> list[DomainEvent]:
        """Return all events belonging to a single trace, ordered by created_at."""
        ...

    async def get_symbol_timeline(self, symbol: str, limit: int = 50) -> list[DomainEvent]:
        """Return the most recent events for a given stock symbol."""
        ...
