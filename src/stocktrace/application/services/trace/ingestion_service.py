"""Orchestration for ingesting official trace events."""

from __future__ import annotations

from stocktrace.application.services.trace.trace_service import TraceService
from stocktrace.domain.ports.official_source_provider import OfficialSourceProvider
from stocktrace.infrastructure.logging.config import get_logger


class OfficialTraceIngestionService:
    """Fetch, normalize, and persist official events for one symbol."""

    def __init__(
        self,
        trace_service: TraceService,
        providers: list[OfficialSourceProvider],
    ) -> None:
        self._trace_service = trace_service
        self._providers = providers
        self._logger = get_logger(__name__)

    async def ingest_symbol(self, symbol: str, *, limit: int) -> int:
        """Persist all available events, continuing when a provider fails."""
        saved = 0
        for provider in self._providers:
            try:
                events = await provider.list_events(symbol=symbol, limit=limit)
                for event in events:
                    await self._trace_service.save_event(event)
                    saved += 1
            except Exception as exc:
                self._logger.warning(
                    "official_trace_ingest_failed",
                    provider=provider.provider_name,
                    symbol=symbol,
                    error=str(exc),
                )
        return saved
