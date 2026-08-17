"""Orchestration for ingesting official trace events."""

from __future__ import annotations

from stocktrace.application.services.trace.trace_service import TraceService
from stocktrace.domain.ports.official_source_provider import OfficialSourceProvider
from stocktrace.infrastructure.logging.config import get_logger


class OfficialTraceIngestionUnavailableError(RuntimeError):
    """Raised when every configured official provider is unavailable."""


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
        failed_providers: list[str] = []
        for provider in self._providers:
            try:
                events = await provider.list_events(symbol=symbol, limit=limit)
            except Exception as exc:
                failed_providers.append(provider.provider_name)
                self._logger.warning(
                    "official_trace_ingest_failed",
                    provider=provider.provider_name,
                    symbol=symbol,
                    error=str(exc),
                )
                continue

            for event in events:
                await self._trace_service.save_event(event)
                saved += 1

        if self._providers and len(failed_providers) == len(self._providers):
            providers = ", ".join(failed_providers)
            raise OfficialTraceIngestionUnavailableError(
                f"No official trace provider is available for {symbol}: {providers}",
            )
        return saved
