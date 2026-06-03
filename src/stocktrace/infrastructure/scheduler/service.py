"""Scheduled Telegram jobs for StockTrace."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Protocol
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from stocktrace.application.queries.stock_handlers import (
    GetStockNewsQueryHandler,
    GetStockQuoteQueryHandler,
)
from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger


class TelegramMessageBot(Protocol):
    """Minimal Telegram bot contract used by scheduled jobs."""

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        disable_web_page_preview: bool | None = None,
    ) -> object:
        """Send a Telegram message."""
        ...


class SchedulerService:
    """Register and execute scheduled market-data Telegram jobs."""

    def __init__(
        self,
        quote_handler: GetStockQuoteQueryHandler,
        news_handler: GetStockNewsQueryHandler,
        bot: TelegramMessageBot,
        settings: Settings,
        scheduler: AsyncIOScheduler | None = None,
    ) -> None:
        self._quote_handler = quote_handler
        self._news_handler = news_handler
        self._bot = bot
        self._settings = settings
        self._timezone = ZoneInfo(settings.scheduler.timezone)
        self._scheduler = scheduler or AsyncIOScheduler(timezone=self._timezone)
        self._logger = get_logger(__name__)

    @property
    def is_running(self) -> bool:
        """Return whether the scheduler is currently running."""
        return self._scheduler.running

    def start(self) -> None:
        """Start scheduled jobs if they are configured."""
        if self._scheduler.running:
            return
        if not self._settings.scheduler.enabled:
            self._logger.info("scheduler_skipped", reason="disabled")
            return
        if self._chat_id is None:
            self._logger.warning("scheduler_skipped", reason="missing_telegram_chat_id")
            return

        self._scheduler.add_job(
            self.send_news_digest,
            CronTrigger(
                hour=",".join(str(hour) for hour in self._settings.scheduler.news_digest_hours),
                minute=0,
                timezone=self._timezone,
            ),
            id="stocktrace-news-digest",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.add_job(
            self.send_price_alert,
            IntervalTrigger(
                minutes=self._settings.scheduler.price_alert_interval_minutes,
                timezone=self._timezone,
            ),
            id="stocktrace-price-alert",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        self._logger.info("scheduler_started")

    async def shutdown(self) -> None:
        """Stop scheduled jobs."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._logger.info("scheduler_stopped")

    async def send_news_digest(self) -> None:
        """Send one news digest message per watchlist symbol."""
        chat_id = self._chat_id
        if chat_id is None:
            self._logger.warning("news_digest_skipped", reason="missing_telegram_chat_id")
            return

        for symbol in self._watchlist_symbols:
            try:
                articles = await self._news_handler.handle(
                    GetNewsQuery(
                        symbol=symbol,
                        limit=self._settings.scheduler.news_digest_limit,
                    ),
                )
                message = self._build_news_digest_message(symbol, articles)
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception as exc:
                self._logger.error("news_digest_symbol_failed", symbol=symbol, error=str(exc))
            await asyncio.sleep(self._settings.scheduler.news_symbol_delay_seconds)

    async def send_price_alert(self) -> None:
        """Send a single price board message for all watchlist symbols."""
        chat_id = self._chat_id
        if chat_id is None:
            self._logger.warning("price_alert_skipped", reason="missing_telegram_chat_id")
            return

        quotes: list[StockQuote] = []
        for symbol in self._watchlist_symbols:
            try:
                quote = await self._quote_handler.handle(GetPriceQuery(symbol=symbol))
                if quote is not None:
                    quotes.append(quote)
            except Exception as exc:
                self._logger.error("price_alert_symbol_failed", symbol=symbol, error=str(exc))

        if not quotes:
            self._logger.warning("price_alert_skipped", reason="empty_quote_result")
            return

        await self._bot.send_message(
            chat_id=chat_id,
            text=self._build_price_alert_message(quotes),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    @property
    def _chat_id(self) -> str | None:
        return self._settings.telegram.chat_id

    @property
    def _watchlist_symbols(self) -> list[str]:
        return [symbol.upper() for symbol in self._settings.scheduler.watchlist_symbols]

    def _build_news_digest_message(self, symbol: str, articles: list[NewsArticle]) -> str:
        now = datetime.now(tz=self._timezone)
        lines = [f"📰 Tin tức {now:%H:%M} — {escape(symbol.upper())}", ""]
        if not articles:
            lines.append("Không có tin mới.")
            return "\n".join(lines)

        for index, article in enumerate(articles, start=1):
            title = escape(article.title)
            url = escape(article.url)
            source = escape(article.source)
            lines.append(f'{index}. <a href="{url}">{title}</a>')
            lines.append(f"   {source} • {_age_label(article.published_at, now)}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _build_price_alert_message(self, quotes: list[StockQuote]) -> str:
        now = datetime.now(tz=self._timezone)
        lines = [f"📊 Bảng giá — {now:%H:%M}", ""]
        for quote in quotes:
            lines.append(
                f"{escape(quote.ticker):<5} "
                f"{_format_price(quote.current_price):>10}  "
                f"{_trend_icon(quote.change_percent)} {_format_percent(quote.change_percent)}"
            )
        return "\n".join(lines)


def _age_label(published_at: datetime | None, now: datetime) -> str:
    if published_at is None:
        return "vừa cập nhật"
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=ZoneInfo("UTC"))
    published_at = published_at.astimezone(now.tzinfo)
    minutes = max(0, int((now - published_at).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} phút trước"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} giờ trước"
    days = hours // 24
    return f"{days} ngày trước"


def _format_price(value: Decimal) -> str:
    if value == value.to_integral():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _format_percent(value: Decimal) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}%"


def _trend_icon(value: Decimal) -> str:
    if value > 0:
        return "📈"
    if value < 0:
        return "📉"
    return "➡️"
