"""Scheduler service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

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
from stocktrace.infrastructure.scheduler.service import SchedulerService

PRICE_INTERVAL_MINUTES = 1
NEWS_DIGEST_HOURS = [8, 12, 16, 20]
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


class FakeWatchlistService:
    """Watchlist service test double."""

    def __init__(self, symbols: list[str] | None = None) -> None:
        self.symbols = symbols or ["FPT", "VCB"]
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
    assert settings.news_digest_hours == NEWS_DIGEST_HOURS


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
async def test_price_alert_sends_single_aggregated_message_and_continues_on_errors() -> None:
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
    assert len(bot.messages) == 1
    message = bot.messages[0]
    assert message["chat_id"] == "chat-1"
    assert message["parse_mode"] == "HTML"
    assert "Bảng giá" in message["text"]
    assert "FPT" in message["text"]
    assert "125,000" in message["text"]
    assert "+1.21%" in message["text"]


@pytest.mark.asyncio
async def test_price_alert_sends_every_run_during_market_hours() -> None:
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

    assert len(bot.messages) == 2


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
