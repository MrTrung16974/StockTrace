"""Audit application service — fire-and-forget event emission + trace replay."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from stocktrace.domain.events import DomainEvent
from stocktrace.domain.ports.audit_repository import AuditRepository
from stocktrace.infrastructure.logging.config import get_logger


class AuditService:
    """Coordinate audit event persistence and trace retrieval."""

    def __init__(
        self,
        repository_context_factory: object,  # async context manager factory → AuditRepository
    ) -> None:
        self._repo_factory = repository_context_factory
        self._logger = get_logger(__name__)

    def emit(self, event: DomainEvent) -> None:
        """Fire-and-forget: schedule event persistence without blocking the caller."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._save(event), name=f"audit-{event.event_type}")
        except RuntimeError:
            # No running event loop — skip (e.g. during tests that don't run async)
            pass

    async def emit_async(self, event: DomainEvent) -> None:
        """Await event persistence — use in scheduled jobs where latency is acceptable."""
        await self._save(event)

    async def get_trace(self, trace_id: str) -> list[DomainEvent]:
        """Return all events belonging to a single trace in order."""
        async with self._repo_factory() as repo:  # type: ignore[attr-defined]
            return await repo.get_trace(trace_id)

    async def get_symbol_timeline(self, symbol: str, limit: int = 50) -> list[DomainEvent]:
        """Return the most recent events for a symbol."""
        async with self._repo_factory() as repo:  # type: ignore[attr-defined]
            return await repo.get_symbol_timeline(symbol, limit)

    async def replay(self, trace_id: str) -> str:
        """Return a human-readable trace replay string."""
        events = await self.get_trace(trace_id)
        if not events:
            return f"No events found for trace {trace_id}"

        lines = [f"=== Trace Replay: {trace_id} ===", ""]
        for event in events:
            ts = event.created_at.strftime("%H:%M:%S.%f")[:-3]
            lines.append(f"{ts}  {event.event_type:<30}  {event.aggregate_id}")
        return "\n".join(lines)

    async def _save(self, event: DomainEvent) -> None:
        """Persist a single event, swallowing errors to protect the hot path."""
        try:
            async with self._repo_factory() as repo:  # type: ignore[attr-defined]
                await repo.save_event(event)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "audit_event_save_failed",
                event_type=event.event_type,
                error=str(exc),
            )

        # Emit Prometheus counter
        try:
            from stocktrace.infrastructure.metrics.prometheus import audit_events_total  # noqa: PLC0415

            audit_events_total.labels(event_type=event.event_type).inc()
        except Exception:  # noqa: BLE001
            pass
