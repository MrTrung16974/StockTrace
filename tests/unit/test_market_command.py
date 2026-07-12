from unittest.mock import AsyncMock

import pytest

from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
)
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.config.settings import Settings, TelegramSettings
from stocktrace.infrastructure.providers.financial.mock_provider import MockFinancialProvider
from stocktrace.infrastructure.telegram.aiogram_router import (
    _build_financial_command_response,
    _financial_usage,
    create_router,
)


@pytest.mark.asyncio
async def test_market_command_no_service() -> None:
    settings = Settings(telegram=TelegramSettings(allowed_user_ids=[123]))
    router = create_router(
        settings=settings,
        watchlist_service=AsyncMock(),
        market_data_service=AsyncMock(),
        market_analysis_service=None,
    )

    assert router is not None
    assert any(
        handler.callback.__name__ == "market_analysis" for handler in router.message.handlers
    )


def test_financial_commands_are_registered() -> None:
    settings = Settings(telegram=TelegramSettings(allowed_user_ids=[123]))
    router = create_router(
        settings=settings,
        watchlist_service=AsyncMock(),
        market_data_service=AsyncMock(),
        financial_analysis_service=AsyncMock(),
    )

    callback_names = {handler.callback.__name__ for handler in router.message.handlers}

    assert {
        "financial",
        "report",
        "valuation",
        "score",
        "financial_metric",
        "compare",
    }.issubset(callback_names)


def test_trace_commands_are_registered() -> None:
    settings = Settings(telegram=TelegramSettings(allowed_user_ids=[123]))
    router = create_router(
        settings=settings,
        watchlist_service=AsyncMock(),
        market_data_service=AsyncMock(),
        trace_service=AsyncMock(),
    )

    callback_names = {handler.callback.__name__ for handler in router.message.handlers}

    assert "trace" in callback_names


def test_financial_usage_is_command_specific() -> None:
    assert _financial_usage("report") == "Cách dùng: /report MÃ (vd: /report HPG)"
    assert _financial_usage("score") == "Cách dùng: /score MÃ (vd: /score HPG)"


@pytest.mark.asyncio
async def test_financial_command_response_is_command_specific() -> None:
    service = FinancialAnalysisService(financial_provider=MockFinancialProvider())
    dashboard = await service.analyze("HPG", FinancialPeriod.parse("1Y"))

    score_text = _build_financial_command_response(dashboard, "score")
    valuation_text = _build_financial_command_response(dashboard, "valuation")
    report_text = _build_financial_command_response(dashboard, "report")

    assert "<b>Điểm tài chính HPG</b>" in score_text
    assert "Nhóm điểm:" in score_text
    assert "<b>Định giá HPG</b>" in valuation_text
    assert "Trạng thái:" in valuation_text
    assert "Báo cáo phân tích tài chính" in report_text
