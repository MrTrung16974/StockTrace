"""Scheduled financial analysis jobs."""

from __future__ import annotations

from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
)
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.scheduler.protocols import TelegramMessageBot
from stocktrace.infrastructure.telegram.delivery import deliver_html_messages

logger = get_logger(__name__)


class FinancialAnalysisJob:
    """Background jobs for financial data sync and analysis."""

    def __init__(
        self,
        financial_service: FinancialAnalysisService,
        watchlist_service: WatchlistService,
        bot: TelegramMessageBot,
        settings: Settings,
    ) -> None:
        self._financial = financial_service
        self._watchlist = watchlist_service
        self._bot = bot
        self._settings = settings
        self._logger = get_logger(__name__)

    async def sync_financial_statements(self) -> None:
        """Weekly: sync financial statements for watchlist symbols."""
        chat_id = self._settings.telegram.chat_id
        if chat_id is None:
            return

        items = await self._watchlist.list_symbols(owner_id=str(chat_id))
        period = FinancialPeriod.parse("1Y")

        for item in items:
            try:
                await self._financial.analyze(item.symbol, period)
                self._logger.info("financial_sync_completed", symbol=item.symbol)
            except Exception as exc:
                self._logger.warning(
                    "financial_sync_failed",
                    symbol=item.symbol,
                    error=str(exc),
                )

    async def recalculate_valuations(self) -> None:
        """Monthly: recalculate valuations for watchlist."""
        await self.sync_financial_statements()

    async def send_daily_financial_reports(self) -> None:
        """Send the latest one-year financial dashboard for every watched symbol."""
        chat_id = self._settings.telegram.chat_id
        if chat_id is None:
            return

        items = await self._watchlist.list_symbols(owner_id=str(chat_id))
        period = FinancialPeriod.parse("1Y")

        for item in items:
            try:
                dashboard = await self._financial.analyze(item.symbol, period)
                message = await self._bot.send_message(
                    chat_id=chat_id,
                    text=f"📊 Phân tích tài chính 09:00: <b>{item.symbol}</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                await deliver_html_messages(message, dashboard.telegram_html)
                self._logger.info("daily_financial_report_sent", symbol=item.symbol)
            except Exception as exc:
                self._logger.warning(
                    "daily_financial_report_failed",
                    symbol=item.symbol,
                    error=str(exc),
                )

    async def refresh_quarterly_reports(self) -> None:
        """Quarterly: refresh full financial reports."""
        chat_id = self._settings.telegram.chat_id
        if chat_id is None:
            return

        items = await self._watchlist.list_symbols(owner_id=str(chat_id))
        period = FinancialPeriod.parse("3Y")

        for item in items:
            try:
                dashboard = await self._financial.analyze(item.symbol, period)
                message = await self._bot.send_message(
                    chat_id=chat_id,
                    text=f"📊 Quarterly Financial Report: <b>{item.symbol}</b>",
                )
                await deliver_html_messages(message, dashboard.telegram_html)
            except Exception as exc:
                self._logger.warning(
                    "quarterly_report_failed",
                    symbol=item.symbol,
                    error=str(exc),
                )
