"""Scheduler service tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.domain.entities.watchlist_item import WatchlistItem
from stocktrace.infrastructure.config import (
    ProvidersSettings,
    RedisSettings,
    SchedulerSettings,
    Settings,
    TelegramSettings,
)
from stocktrace.infrastructure.scheduler.financial_job import FinancialAnalysisJob
from stocktrace.infrastructure.scheduler.service import SchedulerService

PRICE_INTERVAL_MINUTES = 1
PRICE_CHANGE_THRESHOLD_PERCENT = Decimal("0.1")
PRICE_ALERT_COOLDOWN_MINUTES = 5
NEWS_DIGEST_HOURS = [8, 12, 16, 20]
FINANCIAL_DAILY_REPORT_HOUR = 9
TWO_ITEMS = 2
MARKET_OPEN_TIME = datetime(2026, 6, 8, 10, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))


class FakeBot:
    """Telegram bot test double."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        disable_web_page_preview: bool | None = None,
    ) -> None:
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            },
        )


class FakeNewsHandler:
    """News query handler test double."""

    def __init__(self) -> None:
        self.queries: list[GetNewsQuery] = []

    async def handle(self, query: GetNewsQuery) -> list[NewsArticle]:
        self.queries.append(query)
        if query.symbol == "VCB":
            raise RuntimeError("news failed")
        return [
            NewsArticle(
                ticker=query.symbol,
                title="FPT earnings beat expectations",
                summary="summary",
                url="https://example.com/fpt",
                source="Reuters",
                published_at=datetime.now(tz=UTC) - timedelta(hours=3),
            ),
        ]


class FakeQuoteHandler:
    """Quote query handler test double."""

    def __init__(self) -> None:
        self.queries: list[GetPriceQuery] = []

    async def handle(self, query: GetPriceQuery) -> StockQuote | None:
        self.queries.append(query)
        if query.symbol == "VCB":
            raise RuntimeError("quote failed")
        return StockQuote(
            ticker=query.symbol,
            company_name=f"{query.symbol} Corp",
            current_price=Decimal("125000"),
            change=Decimal("1500"),
            change_percent=Decimal("1.21"),
            open_price=Decimal("123500"),
            high_price=Decimal("126000"),
            low_price=Decimal("122000"),
            volume=2350000,
            timestamp=datetime.now(tz=UTC),
            currency="VND",
            source="test",
        )


class SequentialQuoteHandler:
    """Quote handler double that returns one configured price per poll."""

    def __init__(self, prices: list[Decimal]) -> None:
        self._prices = iter(prices)

    async def handle(self, query: GetPriceQuery) -> StockQuote:
        price = next(self._prices)
        return StockQuote(
            ticker=query.symbol,
            company_name=f"{query.symbol} Corp",
            current_price=price,
            change=Decimal("0"),
            change_percent=Decimal("0"),
            open_price=price,
            high_price=price,
            low_price=price,
            volume=1,
            timestamp=datetime.now(tz=UTC),
            currency="VND",
            source="test",
        )


class FakeWatchlistService:
    """Watchlist service test double."""

    def __init__(self, symbols: list[str] | None = None) -> None:
        self.symbols = symbols if symbols is not None else ["FPT", "VCB"]
        self.owner_ids: list[str] = []

    async def list_symbols(self, owner_id: str) -> list[WatchlistItem]:
        self.owner_ids.append(owner_id)
        return [
            WatchlistItem(
                id=f"{owner_id}:{symbol}",
                owner_id=owner_id,
                symbol=symbol,
                created_at=datetime.now(tz=UTC),
            )
            for symbol in self.symbols
        ]


class FakeFinancialAnalysisJob:
    """Financial job double used to verify registration only."""

    async def send_daily_financial_reports(self) -> None:
        return None

    async def sync_financial_statements(self) -> None:
        return None

    async def recalculate_valuations(self) -> None:
        return None

    async def refresh_quarterly_reports(self) -> None:
        return None


class FakeTraceIngestionJob:
    """Trace ingestion double used to verify scheduler registration."""

    async def run(self) -> None:
        return None


class FakeStockAnalysisJob:
    """Stock analysis job double used to verify feature-flagged registration."""

    async def run_morning_report(self) -> None:
        return None

    async def run_evening_report(self) -> None:
        return None


class FakeFinancialService:
    """Financial service double that records scheduled analyses."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def analyze(self, symbol: str, period: Any) -> Any:
        self.calls.append((symbol, str(period)))
        return type("Dashboard", (), {"telegram_html": f"<b>{symbol}</b>"})()


class FakeFinancialSnapshotRepository:
    """Snapshot repository double that records completed dashboards."""

    def __init__(self) -> None:
        self.dashboards: list[Any] = []

    async def save_dashboard(self, dashboard: Any) -> None:
        self.dashboards.append(dashboard)


@asynccontextmanager
async def _snapshot_repository_context(repository: FakeFinancialSnapshotRepository):
    yield repository


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        providers=ProvidersSettings(max_retries=0),
        redis=RedisSettings(enabled=False),
        telegram=TelegramSettings(chat_id="chat-1"),
        scheduler=SchedulerSettings(
            news_symbol_delay_seconds=0,
        ),
    )


def test_scheduler_settings_defaults_match_expected_schedule() -> None:
    settings = SchedulerSettings()

    assert settings.price_enabled is True
    assert settings.news_enabled is True
    assert settings.price_alert_interval_minutes == PRICE_INTERVAL_MINUTES
    assert settings.price_change_threshold_percent == PRICE_CHANGE_THRESHOLD_PERCENT
    assert settings.price_alert_cooldown_minutes == PRICE_ALERT_COOLDOWN_MINUTES
    assert settings.news_digest_hours == NEWS_DIGEST_HOURS
    assert settings.financial_daily_report_enabled is True
    assert settings.financial_daily_report_hour == FINANCIAL_DAILY_REPORT_HOUR


@pytest.mark.asyncio
async def test_scheduler_registers_daily_financial_report_at_9am() -> None:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))
    service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, FakeBot()),
        settings=_settings(),
        scheduler=scheduler,
        financial_analysis_job=cast(Any, FakeFinancialAnalysisJob()),
    )

    service.start()

    job = scheduler.get_job("stocktrace-financial-daily-report")
    assert job is not None
    assert str(job.trigger).startswith("cron[hour='9', minute='0']")

    await service.shutdown()


@pytest.mark.asyncio
async def test_scheduler_registers_ai_reports_only_when_enabled() -> None:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))
    settings = _settings()
    service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, FakeBot()),
        settings=settings,
        scheduler=scheduler,
        stock_analysis_job=cast(Any, FakeStockAnalysisJob()),
    )

    service.start()
    assert scheduler.get_job("stocktrace-ai-morning-report") is None
    await service.shutdown()

    enabled_scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))
    settings.scheduler.analysis_enabled = True
    enabled_service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, FakeBot()),
        settings=settings,
        scheduler=enabled_scheduler,
        stock_analysis_job=cast(Any, FakeStockAnalysisJob()),
    )

    enabled_service.start()
    assert enabled_scheduler.get_job("stocktrace-ai-morning-report") is not None
    assert enabled_scheduler.get_job("stocktrace-ai-evening-report") is not None
    await enabled_service.shutdown()


@pytest.mark.asyncio
async def test_scheduler_registers_official_trace_ingestion_job() -> None:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))
    service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, FakeBot()),
        settings=_settings(),
        scheduler=scheduler,
        trace_ingestion_job=cast(Any, FakeTraceIngestionJob()),
    )

    service.start()

    job = scheduler.get_job("stocktrace-trace-official-ingest")
    assert job is not None
    assert str(job.trigger).startswith("cron[hour='7', minute='15']")

    await service.shutdown()


@pytest.mark.asyncio
async def test_scheduler_registers_price_alert_without_optional_adapter() -> None:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))
    service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, FakeBot()),
        settings=_settings(),
        scheduler=scheduler,
    )

    service.start()

    job = scheduler.get_job("stocktrace-price-alert")
    assert job is not None
    assert str(job.trigger).startswith("interval[0:01:00]")

    await service.shutdown()


@pytest.mark.asyncio
async def test_scheduler_does_not_register_price_alert_when_disabled() -> None:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))
    settings = _settings()
    settings.scheduler.price_enabled = False
    service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, FakeBot()),
        settings=settings,
        scheduler=scheduler,
    )

    service.start()

    assert scheduler.get_job("stocktrace-price-alert") is None

    await service.shutdown()


@pytest.mark.asyncio
async def test_daily_financial_job_sends_a_dashboard_for_each_watchlist_symbol() -> None:
    bot = FakeBot()
    financial_service = FakeFinancialService()
    job = FinancialAnalysisJob(
        financial_service=cast(Any, financial_service),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    with patch(
        "stocktrace.infrastructure.scheduler.financial_job.deliver_html_messages",
        new_callable=AsyncMock,
    ) as deliver:
        await job.send_daily_financial_reports()

    assert [symbol for symbol, _ in financial_service.calls] == ["FPT", "VCB"]
    assert len(bot.messages) == TWO_ITEMS
    assert all("Phân tích tài chính 09:00" in message["text"] for message in bot.messages)
    assert deliver.await_count == TWO_ITEMS


@pytest.mark.asyncio
async def test_financial_sync_persists_each_successful_dashboard() -> None:
    financial_service = FakeFinancialService()
    repository = FakeFinancialSnapshotRepository()
    job = FinancialAnalysisJob(
        financial_service=cast(Any, financial_service),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, FakeBot()),
        settings=_settings(),
        snapshot_repository_context_factory=lambda: _snapshot_repository_context(repository),
    )

    await job.sync_financial_statements()

    assert [dashboard.telegram_html for dashboard in repository.dashboards] == [
        "<b>FPT</b>",
        "<b>VCB</b>",
    ]


@pytest.mark.asyncio
async def test_news_digest_sends_one_message_per_successful_symbol() -> None:
    bot = FakeBot()
    news_handler = FakeNewsHandler()
    service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, news_handler),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    await service.send_news_digest()

    assert [query.symbol for query in news_handler.queries] == ["FPT", "VCB"]
    assert len(bot.messages) == 1
    message = bot.messages[0]
    assert message["chat_id"] == "chat-1"
    assert message["parse_mode"] == "HTML"
    assert message["disable_web_page_preview"] is True
    assert "Tin tức" in message["text"]
    assert '<a href="https://example.com/fpt">FPT earnings beat expectations</a>' in message["text"]


@pytest.mark.asyncio
async def test_news_digest_does_not_resend_same_article_url() -> None:
    bot = FakeBot()
    service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    await service.send_news_digest()
    await service.send_news_digest()

    assert len(bot.messages) == 1


@pytest.mark.asyncio
async def test_price_alert_creates_baseline_and_continues_on_errors() -> None:
    bot = FakeBot()
    quote_handler = FakeQuoteHandler()
    service = SchedulerService(
        quote_handler=cast(Any, quote_handler),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    with patch(
        "stocktrace.infrastructure.scheduler.service.datetime",
    ) as mock_datetime:
        mock_datetime.now.return_value = MARKET_OPEN_TIME
        await service.send_price_alert()

    assert [query.symbol for query in quote_handler.queries] == ["FPT", "VCB"]
    assert bot.messages == []


@pytest.mark.asyncio
async def test_price_alert_does_not_send_when_price_is_unchanged() -> None:
    bot = FakeBot()
    service = SchedulerService(
        quote_handler=cast(Any, FakeQuoteHandler()),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    with patch(
        "stocktrace.infrastructure.scheduler.service.datetime",
    ) as mock_datetime:
        mock_datetime.now.return_value = MARKET_OPEN_TIME
        await service.send_price_alert()
        await service.send_price_alert()

    assert bot.messages == []


@pytest.mark.asyncio
async def test_price_alert_sends_when_change_reaches_threshold() -> None:
    bot = FakeBot()
    service = SchedulerService(
        quote_handler=cast(Any, SequentialQuoteHandler([Decimal("100"), Decimal("100.1")])),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService(symbols=["FPT"])),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    with patch("stocktrace.infrastructure.scheduler.service.datetime") as mock_datetime:
        mock_datetime.now.return_value = MARKET_OPEN_TIME
        await service.send_price_alert()
        mock_datetime.now.return_value = MARKET_OPEN_TIME + timedelta(minutes=1)
        await service.send_price_alert()

    assert len(bot.messages) == 1
    message = bot.messages[0]
    assert message["chat_id"] == "chat-1"
    assert message["parse_mode"] == "HTML"
    assert "BIẾN ĐỘNG GIÁ" in message["text"]
    assert "100 → 100.10" in message["text"]
    assert "+0.10%" in message["text"]


@pytest.mark.asyncio
async def test_price_alert_uses_cooldown_but_keeps_latest_snapshot() -> None:
    bot = FakeBot()
    service = SchedulerService(
        quote_handler=cast(
            Any,
            SequentialQuoteHandler(
                [Decimal("100"), Decimal("100.2"), Decimal("100.5"), Decimal("100.7")],
            ),
        ),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService(symbols=["FPT"])),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    with patch("stocktrace.infrastructure.scheduler.service.datetime") as mock_datetime:
        mock_datetime.now.return_value = MARKET_OPEN_TIME
        await service.send_price_alert()
        mock_datetime.now.return_value = MARKET_OPEN_TIME + timedelta(minutes=1)
        await service.send_price_alert()
        mock_datetime.now.return_value = MARKET_OPEN_TIME + timedelta(minutes=2)
        await service.send_price_alert()
        mock_datetime.now.return_value = MARKET_OPEN_TIME + timedelta(minutes=6)
        await service.send_price_alert()

    assert len(bot.messages) == TWO_ITEMS
    assert "100 → 100.20" in bot.messages[0]["text"]
    assert "100.50 → 100.70" in bot.messages[1]["text"]


@pytest.mark.asyncio
async def test_price_alert_skipped_when_market_closed() -> None:
    bot = FakeBot()
    quote_handler = FakeQuoteHandler()
    service = SchedulerService(
        quote_handler=cast(Any, quote_handler),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    closed_time = datetime(2026, 6, 8, 12, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    with patch(
        "stocktrace.infrastructure.scheduler.service.datetime",
    ) as mock_datetime:
        mock_datetime.now.return_value = closed_time
        await service.send_price_alert()

    assert len(bot.messages) == 0
    assert quote_handler.queries == []


@pytest.mark.asyncio
async def test_disabled_symbols_are_skipped() -> None:
    bot = FakeBot()
    quote_handler = FakeQuoteHandler()
    settings = _settings()
    settings.scheduler.disabled_symbols = ["VCB"]
    service = SchedulerService(
        quote_handler=cast(Any, quote_handler),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService()),
        bot=cast(Any, bot),
        settings=settings,
    )

    with patch(
        "stocktrace.infrastructure.scheduler.service.datetime",
    ) as mock_datetime:
        mock_datetime.now.return_value = MARKET_OPEN_TIME
        await service.send_price_alert()

    assert [query.symbol for query in quote_handler.queries] == ["FPT"]


@pytest.mark.asyncio
async def test_scheduler_uses_chat_watchlist_from_database() -> None:
    bot = FakeBot()
    quote_handler = FakeQuoteHandler()
    watchlist_service = FakeWatchlistService(symbols=["MBB"])
    service = SchedulerService(
        quote_handler=cast(Any, quote_handler),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, watchlist_service),
        bot=cast(Any, bot),
        settings=_settings(),
    )

    with patch(
        "stocktrace.infrastructure.scheduler.service.datetime",
    ) as mock_datetime:
        mock_datetime.now.return_value = MARKET_OPEN_TIME
        await service.send_price_alert()

    assert watchlist_service.owner_ids == ["chat-1"]
    assert [query.symbol for query in quote_handler.queries] == ["MBB"]


@pytest.mark.asyncio
async def test_scheduler_uses_configured_watchlist_when_database_list_is_empty() -> None:
    bot = FakeBot()
    quote_handler = FakeQuoteHandler()
    settings = _settings()
    settings.scheduler.watchlist_symbols = ["HPG", "FPT"]
    service = SchedulerService(
        quote_handler=cast(Any, quote_handler),
        news_handler=cast(Any, FakeNewsHandler()),
        watchlist_service=cast(Any, FakeWatchlistService(symbols=[])),
        bot=cast(Any, bot),
        settings=settings,
    )

    with patch(
        "stocktrace.infrastructure.scheduler.service.datetime",
    ) as mock_datetime:
        mock_datetime.now.return_value = MARKET_OPEN_TIME
        await service.send_price_alert()

    assert [query.symbol for query in quote_handler.queries] == ["HPG", "FPT"]
