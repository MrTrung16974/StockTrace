"""Scheduled market analysis job."""

from __future__ import annotations

from stocktrace.application.services.market_analysis_service import MarketAnalysisService
from stocktrace.infrastructure.config.settings import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.scheduler.protocols import TelegramMessageBot
from stocktrace.infrastructure.telegram.formatters import build_market_analysis_report


class MarketAnalysisJob:
    """Execute scheduled market analysis reports."""

    def __init__(
        self,
        service: MarketAnalysisService,
        bot: TelegramMessageBot,
        settings: Settings,
    ) -> None:
        self._service = service
        self._bot = bot
        self._settings = settings
        self._logger = get_logger(__name__)

    async def run_morning_report(self) -> None:
        """Run the morning market report."""
        if not self._settings.scheduler.market_analysis_enabled:
            return
        await self._run_report(title="BÁO CÁO THỊ TRƯỜNG SÁNG", job_name="market_morning_report")

    async def run_evening_report(self) -> None:
        """Run the evening market report."""
        if not self._settings.scheduler.market_analysis_enabled:
            return
        await self._run_report(title="BÁO CÁO THỊ TRƯỜNG TỐI", job_name="market_evening_report")

    async def _run_report(self, title: str, job_name: str) -> None:
        chat_id = self._settings.telegram.chat_id
        if not chat_id:
            self._logger.info("market_analysis_job_skipped", reason="no_chat_id")
            return

        self._logger.info("market_analysis_job_started", job_name=job_name)

        try:
            bundle = await self._service.analyze_market()
            try:
                report = build_market_analysis_report(bundle)
            except Exception as exc:
                self._logger.warning(
                    "market_analysis_format_failed",
                    job_name=job_name,
                    error=str(exc),
                )
                report = "Khong the dinh dang bao cao thi truong chi tiet."
            report = f"<b>{title}</b>\n\n{report}"
            await self._bot.send_message(
                chat_id=chat_id,
                text=report,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as exc:
            self._logger.error("market_analysis_job_failed", job_name=job_name, error=str(exc))
