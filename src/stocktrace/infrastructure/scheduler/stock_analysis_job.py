"""Compatibility shell for disabled scheduled AI reports."""

from __future__ import annotations

from stocktrace.application.services.stock_analysis_service import StockAnalysisService
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.scheduler.protocols import TelegramMessageBot


class StockAnalysisJob:
    """Reject automatic AI execution; analysis is user-command-only."""

    def __init__(
        self,
        stock_analysis_service: StockAnalysisService,
        watchlist_service: WatchlistService,
        bot: TelegramMessageBot,
        settings: Settings,
    ) -> None:
        # Retain constructor compatibility without exposing an automatic AI path.
        self._stock_analysis_service = stock_analysis_service
        self._watchlist_service = watchlist_service
        self._bot = bot
        self._settings = settings
        self._logger = get_logger(__name__)

    async def run_morning_report(self) -> None:
        """Skip the legacy automatic morning AI report."""
        self._log_disabled("ai_morning_report")

    async def run_evening_report(self) -> None:
        """Skip the legacy automatic evening AI report."""
        self._log_disabled("ai_evening_report")

    def _log_disabled(self, job_name: str) -> None:
        self._logger.info(
            "scheduler_ai_report_skipped",
            job=job_name,
            reason="automatic_ai_forbidden",
        )
