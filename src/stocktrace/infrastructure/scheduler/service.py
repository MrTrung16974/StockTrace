"""Scheduled Telegram jobs for StockTrace."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
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
from stocktrace.application.services.policy_news_analysis import PolicyNewsAnalyzer
from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.scheduler.financial_job import FinancialAnalysisJob
from stocktrace.infrastructure.scheduler.market_analysis_job import MarketAnalysisJob
from stocktrace.infrastructure.scheduler.market_hours import is_vn_market_open
from stocktrace.infrastructure.scheduler.paper_confirmation_expiry_job import (
    PaperConfirmationExpiryJob,
)
from stocktrace.infrastructure.scheduler.price_alert_job import PriceAlertJob
from stocktrace.infrastructure.scheduler.protocols import TelegramMessageBot
from stocktrace.infrastructure.scheduler.stock_analysis_job import StockAnalysisJob
from stocktrace.infrastructure.scheduler.suggestion_alert_job import SuggestionAlertJob
from stocktrace.infrastructure.scheduler.trace_ingestion_job import TraceIngestionJob

T = TypeVar("T")
ONE_HOUR_MINUTES = 60
ONE_DAY_HOURS = 24


@dataclass(frozen=True, slots=True)
class PriceChangeEvent:
    """A meaningful movement between two scheduler price snapshots."""

    quote: StockQuote
    previous_price: Decimal
    change_percent: Decimal


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
        stock_analysis_job: StockAnalysisJob | None = None,
        market_analysis_job: MarketAnalysisJob | None = None,
        financial_analysis_job: FinancialAnalysisJob | None = None,
        price_alert_job: PriceAlertJob | None = None,
        policy_news_analyzer: PolicyNewsAnalyzer | None = None,
        suggestion_alert_job: SuggestionAlertJob | None = None,
        trace_ingestion_job: TraceIngestionJob | None = None,
        paper_confirmation_expiry_job: PaperConfirmationExpiryJob | None = None,
    ) -> None:
        self._quote_handler = quote_handler
        self._news_handler = news_handler
        self._watchlist_service = watchlist_service
        self._bot = bot
        self._settings = settings
        self._stock_analysis_job = stock_analysis_job
        self._market_analysis_job = market_analysis_job
        self._financial_analysis_job = financial_analysis_job
        self._price_alert_job = price_alert_job
        self._policy_news_analyzer = policy_news_analyzer or PolicyNewsAnalyzer()
        self._suggestion_alert_job = suggestion_alert_job
        self._trace_ingestion_job = trace_ingestion_job
        self._paper_confirmation_expiry_job = paper_confirmation_expiry_job
        self._timezone = ZoneInfo(settings.scheduler.timezone)
        self._scheduler = scheduler or AsyncIOScheduler(timezone=self._timezone)
        self._logger = get_logger(__name__)
        self._sent_news_urls: set[str] = set()
        self._last_price_by_symbol: dict[str, Decimal] = {}
        self._last_price_alert_at: dict[str, datetime] = {}

    @property
    def is_running(self) -> bool:
        """Return whether the scheduler is currently running."""
        return bool(self._scheduler.running)

    def start(self) -> None:  # noqa: PLR0912
        """Start scheduled jobs if they are configured."""
        if self._scheduler.running:
            return
        if not self._settings.scheduler.enabled:
            self._logger.info("scheduler_skipped", reason="disabled")
            return
        if self._chat_id is None and not self._paper_confirmation_expiry_is_enabled:
            self._logger.warning("scheduler_skipped", reason="missing_telegram_chat_id")
            return
        if self._chat_id is None:
            self._logger.info("scheduler_telegram_jobs_skipped", reason="missing_telegram_chat_id")

        confirmation_expiry_job = self._paper_confirmation_expiry_job
        if confirmation_expiry_job is not None and self._paper_confirmation_expiry_is_enabled:
            self._scheduler.add_job(
                confirmation_expiry_job.run,
                IntervalTrigger(
                    minutes=self._settings.scheduler.paper_confirmation_expiry_interval_minutes,
                    timezone=self._timezone,
                ),
                id="stocktrace-paper-confirmation-expiry",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            if self._chat_id is None:
                self._scheduler.start()
                self._logger.info("scheduler_started")
                return

        has_job = self._paper_confirmation_expiry_is_enabled
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
            price_alert_runner = (
                self._price_alert_job.run
                if self._price_alert_job is not None
                else self.send_price_alert
            )
            self._scheduler.add_job(
                # PriceAlertJob is kept as an optional compatibility adapter, but
                # the scheduler must also work when the container does not inject it.
                # Registering the service method directly prevents the price board
                # from silently disappearing from the schedule.
                price_alert_runner,
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
        if (
            self._suggestion_alert_job is not None
            and self._settings.scheduler.suggestion_alert_enabled
        ):
            self._scheduler.add_job(
                self._suggestion_alert_job.run,
                IntervalTrigger(
                    minutes=self._settings.scheduler.suggestion_alert_interval_minutes,
                    timezone=self._timezone,
                ),
                id="stocktrace-suggestion-alert",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            has_job = True
        # LLM-backed stock reports are deliberately never registered. The daily
        # market snapshot remains data-only because MarketAnalysisService defaults
        # to use_ai=False. AI may only run from an explicit analysis request.
        if self._market_analysis_job is not None:
            self._scheduler.add_job(
                self._market_analysis_job.run_daily_report,
                CronTrigger(
                    hour=self._settings.scheduler.market_daily_report_hour,
                    minute=0,
                    day_of_week="mon-fri",
                    timezone=self._timezone,
                ),
                id="stocktrace-market-daily-overview",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            has_job = True

        if self._financial_analysis_job is not None:
            if self._settings.scheduler.financial_daily_report_enabled:
                self._scheduler.add_job(
                    self._financial_analysis_job.send_daily_financial_reports,
                    CronTrigger(
                        hour=self._settings.scheduler.financial_daily_report_hour,
                        minute=0,
                        timezone=self._timezone,
                    ),
                    id="stocktrace-financial-daily-report",
                    replace_existing=True,
                    max_instances=1,
                    coalesce=True,
                )
            self._scheduler.add_job(
                self._financial_analysis_job.sync_financial_statements,
                CronTrigger(day_of_week="sun", hour=2, minute=0, timezone=self._timezone),
                id="stocktrace-financial-weekly-sync",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            self._scheduler.add_job(
                self._financial_analysis_job.recalculate_valuations,
                CronTrigger(day=1, hour=3, minute=0, timezone=self._timezone),
                id="stocktrace-valuation-monthly",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            self._scheduler.add_job(
                self._financial_analysis_job.refresh_quarterly_reports,
                CronTrigger(month="1,4,7,10", day=15, hour=4, minute=0, timezone=self._timezone),
                id="stocktrace-financial-quarterly",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            has_job = True

        if self._trace_ingestion_job is not None and self._settings.scheduler.trace_ingest_enabled:
            self._scheduler.add_job(
                self._trace_ingestion_job.run,
                CronTrigger(
                    hour=self._settings.scheduler.trace_ingest_hour,
                    minute=15,
                    timezone=self._timezone,
                ),
                id="stocktrace-trace-official-ingest",
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

    @property
    def _paper_confirmation_expiry_is_enabled(self) -> bool:
        """Return whether the non-Telegram confirmation-expiry job is runnable."""
        return (
            self._paper_confirmation_expiry_job is not None
            and self._settings.scheduler.paper_confirmation_expiry_enabled
        )

    async def shutdown(self) -> None:
        """Stop scheduled jobs."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._logger.info("scheduler_stopped")

    async def send_news_digest(self) -> None:
        """Send one news digest message per watchlist symbol (async fanout)."""
        chat_id = self._chat_id
        if chat_id is None:
            self._logger.warning("news_digest_skipped", reason="missing_telegram_chat_id")
            return

        symbols = await self._watchlist_symbols()
        if not symbols:
            self._logger.info("news_digest_skipped", reason="empty_watchlist")
            return

        # Limit concurrency so we don't hammer the provider
        semaphore = asyncio.Semaphore(5)

        async def _fetch_news(symbol: str) -> tuple[str, list[NewsArticle]]:
            async def _operation() -> list[NewsArticle]:
                return await self._news_handler.handle(
                    GetNewsQuery(
                        symbol=symbol,
                        limit=self._settings.scheduler.news_digest_limit,
                        force_refresh=True,
                    ),
                )

            async with semaphore:
                articles = await self._run_with_retry(
                    _operation,
                    symbol=symbol,
                    job_name="news_digest",
                )
                return symbol, articles

        results = await asyncio.gather(
            *[_fetch_news(sym) for sym in symbols],
            return_exceptions=True,
        )

        delay = self._settings.scheduler.news_symbol_delay_seconds
        for item in results:
            if isinstance(item, BaseException):
                self._logger.error("news_digest_symbol_failed", error=str(item))
                continue
            symbol, articles = item
            try:
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
                if delay > 0:
                    await asyncio.sleep(delay)
            except Exception as exc:
                self._logger.error("news_digest_send_failed", symbol=symbol, error=str(exc))

    async def send_price_alert(self) -> None:
        """Notify only when a watchlist price changes materially since the prior poll."""
        now = datetime.now(tz=self._timezone)
        if not is_vn_market_open(now, timezone=self._timezone):
            self._logger.info("price_alert_skipped", reason="market_closed")
            return

        chat_id = self._chat_id
        if chat_id is None:
            self._logger.warning("price_alert_skipped", reason="missing_telegram_chat_id")
            return

        symbols = await self._watchlist_symbols()
        if not symbols:
            self._logger.info("price_alert_skipped", reason="empty_watchlist")
            return

        # Fetch all symbols concurrently — latency = max(individual latencies)
        async def _fetch_quote(symbol: str) -> StockQuote | None:
            async def _operation() -> StockQuote | None:
                return await self._quote_handler.handle(GetPriceQuery(symbol=symbol))

            return await self._run_with_retry(
                _operation,
                symbol=symbol,
                job_name="price_alert",
            )

        results = await asyncio.gather(
            *[
                _fetch_quote(symbol)
                for symbol in symbols
            ],
            return_exceptions=True,
        )

        quotes: list[StockQuote] = []
        for symbol, result in zip(symbols, results, strict=False):
            if isinstance(result, BaseException):
                self._logger.error("price_alert_symbol_failed", symbol=symbol, error=str(result))
            elif result is not None:
                quotes.append(result)

        if not quotes:
            self._logger.info("price_alert_skipped", reason="no_quotes")
            return

        events = self._detect_price_change_events(quotes, now=now)
        if not events:
            self._logger.info("price_alert_skipped", reason="no_material_price_change")
            return

        await self._bot.send_message(
            chat_id=chat_id,
            text=self._build_price_alert_message(events, now=now),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    @property
    def _chat_id(self) -> str | None:
        return self._settings.telegram.chat_id

    async def _watchlist_symbols(self) -> list[str]:
        chat_id = self._chat_id
        if chat_id is None:
            return []
        items = await self._watchlist_service.list_symbols(owner_id=chat_id)
        symbols = [item.symbol.upper() for item in items]
        if not symbols:
            symbols = [symbol.upper() for symbol in self._settings.scheduler.watchlist_symbols]
        disabled = {symbol.upper() for symbol in self._settings.scheduler.disabled_symbols}
        return [
            symbol
            for symbol in symbols
            if symbol not in disabled
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
            policy_impact = self._policy_news_analyzer.analyze(article)
            if policy_impact is not None:
                source = (
                    f"{source}<br/>🏛 {escape(policy_impact.label)} — "
                    f"{escape(policy_impact.reason)}"
                )
            lines.append(f'{index}. <a href="{url}">{title}</a>')
            lines.append(f"   {source} • {_age_label(article.published_at, now)}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _detect_price_change_events(
        self,
        quotes: list[StockQuote],
        *,
        now: datetime,
    ) -> list[PriceChangeEvent]:
        """Save each snapshot and return changes that pass threshold and cooldown checks."""
        threshold = self._settings.scheduler.price_change_threshold_percent
        cooldown = timedelta(minutes=self._settings.scheduler.price_alert_cooldown_minutes)
        events: list[PriceChangeEvent] = []

        for quote in quotes:
            symbol = quote.ticker.upper()
            previous_price = self._last_price_by_symbol.get(symbol)
            self._last_price_by_symbol[symbol] = quote.current_price
            if previous_price is None or previous_price <= 0:
                continue

            change_percent = (
                (quote.current_price - previous_price) / previous_price * Decimal("100")
            )
            if abs(change_percent) < threshold:
                continue

            last_alert_at = self._last_price_alert_at.get(symbol)
            if cooldown and last_alert_at is not None and now - last_alert_at < cooldown:
                self._logger.info("price_alert_skipped", symbol=symbol, reason="cooldown")
                continue

            events.append(
                PriceChangeEvent(
                    quote=quote,
                    previous_price=previous_price,
                    change_percent=change_percent,
                ),
            )
            self._last_price_alert_at[symbol] = now

        return events

    def _build_price_alert_message(self, events: list[PriceChangeEvent], *, now: datetime) -> str:
        """Build an alert whose first line is useful in a mobile notification preview."""
        lines: list[str] = []
        for index, event in enumerate(events):
            quote = event.quote
            lines.extend(
                [
                    f"🔔 <b>BIẾN ĐỘNG GIÁ {escape(quote.ticker)}</b> — "
                    f"{_format_price(event.previous_price)} → {_format_price(quote.current_price)} "
                    f"{_trend_icon(event.change_percent)} {_format_percent(event.change_percent)} "
                    f"• {now:%H:%M}",
                    f"Giá hiện tại: {_format_price(quote.current_price)} {escape(quote.currency)} "
                    f"| Phiên: {_format_signed_price(quote.change)} "
                    f"({_format_percent(quote.change_percent)})",
                    f"Mở/Cao/Thấp: {_format_price(quote.open_price)} / "
                    f"{_format_price(quote.high_price)} / {_format_price(quote.low_price)}",
                    f"Khối lượng: {quote.volume:,} | {escape(quote.company_name)}",
                    f"Nguồn: {escape(quote.source)}",
                ],
            )
            if index < len(events) - 1:
                lines.append("")
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


def _format_signed_price(value: Decimal) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_format_price(value)}"


def _format_percent(value: Decimal) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}%"


def _trend_icon(value: Decimal) -> str:
    if value > 0:
        return "📈"
    if value < 0:
        return "📉"
    return "➡️"
