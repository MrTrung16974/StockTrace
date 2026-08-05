"""Scheduled ingestion of official trace notices."""

from __future__ import annotations

from stocktrace.application.services.trace.ingestion_service import OfficialTraceIngestionService
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger


class TraceIngestionJob:
    """Refresh official disclosure events for the scheduled watchlist."""

    def __init__(
        self,
        ingestion_service: OfficialTraceIngestionService,
        watchlist_service: WatchlistService,
        settings: Settings,
    ) -> None:
        self._ingestion = ingestion_service
        self._watchlist = watchlist_service
        self._settings = settings
        self._logger = get_logger(__name__)

    async def run(self) -> None:
        """Fetch and store official events for all configured symbols."""
        chat_id = self._settings.telegram.chat_id
        if chat_id is None:
            return
        items = await self._watchlist.list_symbols(owner_id=chat_id)
        symbols = [item.symbol.upper() for item in items]
        if not symbols:
            symbols = [symbol.upper() for symbol in self._settings.scheduler.watchlist_symbols]
        disabled = {symbol.upper() for symbol in self._settings.scheduler.disabled_symbols}
        for symbol in symbols:
            if symbol in disabled:
                continue
            saved = await self._ingestion.ingest_symbol(
                symbol,
                limit=self._settings.scheduler.trace_ingest_limit,
            )
            self._logger.info("official_trace_ingest_completed", symbol=symbol, event_count=saved)
