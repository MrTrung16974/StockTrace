"""Stock analysis scheduler job tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import SecretStr

from stocktrace.ai.analysis_service import parse_analysis_response
from stocktrace.ai.models import AnalysisMode
from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.application.services.stock_analysis_service import AnalysisBundle, StockAnalysisService
from stocktrace.infrastructure.config.settings import AISettings, SchedulerSettings, TelegramSettings
from stocktrace.infrastructure.config.test import load_test_settings
from stocktrace.infrastructure.scheduler.stock_analysis_job import StockAnalysisJob


class FakeBot:
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
            },
        )


class FakeStockAnalysisService:
    @property
    def is_enabled(self) -> bool:
        return True

    async def analyze_symbol(self, symbol: str, *, mode: AnalysisMode, news_limit: int) -> AnalysisBundle:
      analysis = parse_analysis_response(
          symbol,
          "\n".join(
              [
                  "[TỔNG QUAN]",
                  "Ổn định",
                  "[ĐIỂM TÍCH CỰC]",
                  "Tốt",
                  "[RỦI RO]",
                  "Thấp",
                  "[ĐÁNH GIÁ NGẮN HẠN]",
                  "Tăng",
              ],
          ),
          AnalysisMode.FULL,
      )
      return AnalysisBundle(
          symbol=symbol,
          quote=StockQuote(
              ticker=symbol,
              company_name=symbol,
              current_price=Decimal("100"),
              change=Decimal("1"),
              change_percent=Decimal("1"),
              open_price=Decimal("99"),
              high_price=Decimal("101"),
              low_price=Decimal("98"),
              volume=1000,
              timestamp=datetime.now(tz=UTC),
          ),
          news=(
              NewsArticle(
                  ticker=symbol,
                  title="News",
                  summary=None,
                  url=f"https://example.com/{symbol}",
                  source="Test",
              ),
          ),
          analysis=analysis,
      )


class FakeWatchlistService:
    async def list_symbols(self, owner_id: str) -> list:
        return []


@pytest.mark.asyncio
async def test_morning_report_uses_configured_symbols() -> None:
    settings = load_test_settings()
    settings.telegram = TelegramSettings(chat_id="chat-1")
    settings.ai = AISettings(enabled=True, api_key=SecretStr("key"))
    settings.scheduler = SchedulerSettings(
        analysis_enabled=True,
        analysis_symbols=["VCB", "HPG"],
        news_symbol_delay_seconds=0,
    )

    bot = FakeBot()
    job = StockAnalysisJob(
        stock_analysis_service=FakeStockAnalysisService(),  # type: ignore[arg-type]
        watchlist_service=FakeWatchlistService(),  # type: ignore[arg-type]
        bot=bot,
        settings=settings,
    )

    await job.run_morning_report()

    assert len(bot.messages) == 1
    assert "📈 BÁO CÁO AI BUỔI SÁNG" in bot.messages[0]["text"]
    assert "VCB" in bot.messages[0]["text"]
    assert "HPG" in bot.messages[0]["text"]
