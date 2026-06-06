"""Scheduled Telegram jobs for StockTrace."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from html import escape
from typing import TypeVar
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
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.scheduler.protocols import TelegramMessageBot
from stocktrace.infrastructure.scheduler.stock_analysis_job import StockAnalysisJob

T = TypeVar("T")
ONE_HOUR_MINUTES = 60
ONE_DAY_HOURS = 24


class SchedulerService:
    """Register and execute scheduled market-data Telegram jobs."""

    def __init__(
        self,
        quote_handler: GetStockQuoteQueryHandler,
        news_handler: GetStockNewsQueryHandler,
        watchlist_service: WatchlistService,
        bot: TelegramMessageBot,
        settings: Settings,
        scheduler: AsyncIOScheduler | None = None,
        analysis_job: StockAnalysisJob | None = None,
    ) -> None:
        self._quote_handler = quote_handler
        self._news_handler = news_handler
        self._watchlist_service = watchlist_service
        self._bot = bot
        self._settings = settings
        self._analysis_job = analysis_job
        self._timezone = ZoneInfo(settings.scheduler.timezone)
        self._scheduler = scheduler or AsyncIOScheduler(timezone=self._timezone)
        self._logger = get_logger(__name__)
        self._last_price_fingerprints: dict[str, tuple[Decimal, Decimal]] = {}
        self._sent_news_urls: set[str] = set()

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

        has_job = False
        if self._settings.scheduler.news_enabled:
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
            has_job = True
        if self._settings.scheduler.price_enabled:
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
            has_job = True
        if self._settings.scheduler.analysis_enabled and self._analysis_job is not None:
            self._scheduler.add_job(
                self._analysis_job.run_morning_report,
                CronTrigger(
                    hour=self._settings.scheduler.morning_report_hour,
                    minute=0,
                    timezone=self._timezone,
                ),
                id="stocktrace-ai-morning-report",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            self._scheduler.add_job(
                self._analysis_job.run_evening_report,
                CronTrigger(
                    hour=self._settings.scheduler.evening_report_hour,
                    minute=0,
                    timezone=self._timezone,
                ),
                id="stocktrace-ai-evening-report",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            has_job = True
        if not has_job:
            self._logger.info("scheduler_skipped", reason="all_jobs_disabled")
            return
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

        symbols = await self._watchlist_symbols()
        if not symbols:
            self._logger.info("news_digest_skipped", reason="empty_watchlist")
            return

        for symbol in symbols:
            try:
                articles = await self._run_with_retry(
                    lambda symbol=symbol: self._news_handler.handle(
                        GetNewsQuery(
                            symbol=symbol,
                            limit=self._settings.scheduler.news_digest_limit,
                        ),
                    ),
                    symbol=symbol,
                    job_name="news_digest",
                )
                new_articles = self._filter_unsent_articles(articles)
                if not new_articles:
                    self._logger.info(
                        "news_digest_symbol_skipped",
                        symbol=symbol,
                        reason="no_new_articles",
                    )
                    continue

                message = self._build_news_digest_message(symbol, new_articles)
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                self._mark_news_sent(new_articles)
            except Exception as exc:
                self._logger.error("news_digest_symbol_failed", symbol=symbol, error=str(exc))
            await asyncio.sleep(self._settings.scheduler.news_symbol_delay_seconds)

    async def send_price_alert(self) -> None:
        """Send a single price board message for all watchlist symbols."""
        chat_id = self._chat_id
        if chat_id is None:
            self._logger.warning("price_alert_skipped", reason="missing_telegram_chat_id")
            return

        symbols = await self._watchlist_symbols()
        if not symbols:
            self._logger.info("price_alert_skipped", reason="empty_watchlist")
            return

        pending_fingerprints: dict[str, tuple[Decimal, Decimal]] = {}
        quotes: list[StockQuote] = []
        for symbol in symbols:
            try:
                quote = await self._run_with_retry(
                    lambda symbol=symbol: self._quote_handler.handle(
                        GetPriceQuery(symbol=symbol),
                    ),
                    symbol=symbol,
                    job_name="price_alert",
                )
                if quote is not None and self._should_send_price(quote):
                    quotes.append(quote)
                    pending_fingerprints[quote.ticker.upper()] = _price_fingerprint(quote)
            except Exception as exc:
                self._logger.error("price_alert_symbol_failed", symbol=symbol, error=str(exc))

        if not quotes:
            self._logger.info("price_alert_skipped", reason="no_price_change")
            return

        await self._bot.send_message(
            chat_id=chat_id,
            text=self._build_price_alert_message(quotes),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        self._last_price_fingerprints.update(pending_fingerprints)

    @property
    def _chat_id(self) -> str | None:
        return self._settings.telegram.chat_id

    async def _watchlist_symbols(self) -> list[str]:
        chat_id = self._chat_id
        if chat_id is None:
            return []
        items = await self._watchlist_service.list_symbols(owner_id=chat_id)
        disabled = {symbol.upper() for symbol in self._settings.scheduler.disabled_symbols}
        return [
            item.symbol.upper()
            for item in items
            if item.symbol.upper() not in disabled
        ]

    async def _run_with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        symbol: str,
        job_name: str,
    ) -> T:
        attempts = max(1, self._settings.providers.max_retries + 1)
        for attempt in range(1, attempts + 1):
            try:
                return await operation()
            except Exception:
                if attempt >= attempts:
                    raise
                self._logger.warning(
                    "scheduler_job_retrying",
                    job=job_name,
                    symbol=symbol,
                    attempt=attempt,
                    attempts=attempts,
                )
                await asyncio.sleep(min(attempt, 3))
        raise RuntimeError("retry loop exhausted")

    def _filter_unsent_articles(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        return [article for article in articles if article.url not in self._sent_news_urls]

    def _mark_news_sent(self, articles: list[NewsArticle]) -> None:
        self._sent_news_urls.update(article.url for article in articles)

    def _should_send_price(self, quote: StockQuote) -> bool:
        symbol = quote.ticker.upper()
        fingerprint = _price_fingerprint(quote)
        return self._last_price_fingerprints.get(symbol) != fingerprint

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
    if minutes < ONE_HOUR_MINUTES:
        return f"{minutes} phút trước"
    hours = minutes // ONE_HOUR_MINUTES
    if hours < ONE_DAY_HOURS:
        return f"{hours} giờ trước"
    days = hours // ONE_DAY_HOURS
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


def _price_fingerprint(quote: StockQuote) -> tuple[Decimal, Decimal]:
    return (quote.current_price, quote.change_percent)
