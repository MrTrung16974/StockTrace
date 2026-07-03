import pytest
from unittest.mock import AsyncMock, MagicMock
from stocktrace.infrastructure.scheduler.market_analysis_job import MarketAnalysisJob
from stocktrace.infrastructure.config.settings import Settings, SchedulerSettings, TelegramSettings


@pytest.fixture
def settings():
    s = Settings()
    s.scheduler = SchedulerSettings(market_analysis_enabled=True)
    s.telegram = TelegramSettings(chat_id="123456")
    return s


@pytest.mark.asyncio
async def test_run_morning_report_enabled(settings):
    bot = AsyncMock()
    service = AsyncMock()
    service.analyze_market.return_value = MagicMock()
    
    job = MarketAnalysisJob(service, bot, settings)
    
    await job.run_morning_report()
    
    bot.send_message.assert_called_once()
    assert "BÁO CÁO THỊ TRƯỜNG SÁNG" in bot.send_message.call_args[1]["text"]


@pytest.mark.asyncio
async def test_run_morning_report_disabled(settings):
    settings.scheduler.market_analysis_enabled = False
    bot = AsyncMock()
    service = AsyncMock()
    
    job = MarketAnalysisJob(service, bot, settings)
    
    await job.run_morning_report()
    
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_run_evening_report_no_chat_id(settings):
    settings.telegram.chat_id = ""
    bot = AsyncMock()
    service = AsyncMock()
    
    job = MarketAnalysisJob(service, bot, settings)
    
    await job.run_evening_report()
    
    bot.send_message.assert_not_called()
