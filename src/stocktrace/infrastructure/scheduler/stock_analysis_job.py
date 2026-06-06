"""Scheduled AI analysis reports for Telegram."""

from __future__ import annotations

import asyncio

from stocktrace.ai.models import AnalysisMode
from stocktrace.application.services.stock_analysis_service import AnalysisBundle, StockAnalysisService
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.scheduler.protocols import TelegramMessageBot
from stocktrace.infrastructure.telegram.formatters import build_professional_analysis_report


class StockAnalysisJob:
    """Run morning and evening AI analysis reports."""

    def __init__(
        self,
        stock_analysis_service: StockAnalysisService,
        watchlist_service: WatchlistService,
        bot: TelegramMessageBot,
        settings: Settings,
    ) -> None:
        self._stock_analysis_service = stock_analysis_service
        self._watchlist_service = watchlist_service
        self._bot = bot
        self._settings = settings
        self._logger = get_logger(__name__)

    async def run_morning_report(self) -> None:
        """Send the morning AI summary report."""
        await self._run_report(
            title="📈 BÁO CÁO AI BUỔI SÁNG",
            job_name="ai_morning_report",
        )

    async def run_evening_report(self) -> None:
        """Send the evening AI summary report."""
        await self._run_report(
            title="🌙 BÁO CÁO AI BUỔI TỐI",
            job_name="ai_evening_report",
        )

    async def _run_report(self, title: str, job_name: str) -> None:
        if not self._stock_analysis_service.is_enabled:
            self._logger.info("scheduler_ai_report_skipped", job=job_name, reason="ai_disabled")
            return

        chat_id = self._settings.telegram.chat_id
        if chat_id is None:
            self._logger.warning("scheduler_ai_report_skipped", job=job_name, reason="missing_chat_id")
            return

        symbols = await self._analysis_symbols()
        if not symbols:
            self._logger.info("scheduler_ai_report_skipped", job=job_name, reason="empty_symbol_list")
            return

        self._logger.info(
            "scheduler_ai_report_started",
            job=job_name,
            symbols_count=len(symbols),
        )

        bundles: list[AnalysisBundle] = []
        for symbol in symbols:
            try:
                bundle = await self._stock_analysis_service.analyze_symbol(
                    symbol,
                    mode=AnalysisMode.FULL,
                    news_limit=self._settings.scheduler.news_digest_limit,
                )
                bundles.append(bundle)
            except Exception as exc:
                self._logger.error(
                    "scheduler_ai_symbol_failed",
                    job=job_name,
                    symbol=symbol,
                    error=str(exc),
                )
            await asyncio.sleep(self._settings.scheduler.news_symbol_delay_seconds)

        if not bundles:
            self._logger.warning("scheduler_ai_report_skipped", job=job_name, reason="no_results")
            return

        message = self._build_report_message(title=title, bundles=bundles)
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            self._logger.info(
                "scheduler_ai_report_sent",
                job=job_name,
                symbols_count=len(bundles),
            )
        except Exception as exc:
            self._logger.error(
                "scheduler_ai_report_send_failed",
                job=job_name,
                error=str(exc),
            )

    async def _analysis_symbols(self) -> list[str]:
        configured = [
            symbol.upper()
            for symbol in self._settings.scheduler.analysis_symbols
            if symbol.strip()
        ]
        disabled = {symbol.upper() for symbol in self._settings.scheduler.disabled_symbols}
        if configured:
            return [symbol for symbol in configured if symbol not in disabled]

        chat_id = self._settings.telegram.chat_id
        if chat_id is None:
            return []
        items = await self._watchlist_service.list_symbols(owner_id=chat_id)
        return [
            item.symbol.upper()
            for item in items
            if item.symbol.upper() not in disabled
        ]

    def _build_report_message(self, title: str, bundles: list[AnalysisBundle]) -> str:
        sections: list[str] = [title, ""]
        for index, bundle in enumerate(bundles):
            if index > 0:
                sections.extend(["---", ""])
            sections.append(build_professional_analysis_report(bundle))
        return "\n".join(sections).rstrip()
