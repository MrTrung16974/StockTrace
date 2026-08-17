from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
)
from stocktrace.application.services.trace import TraceScoringEngine, official_trace_sources
from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceEventType,
    TraceSeverity,
    TraceTimeline,
)
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.config.settings import Settings, TelegramSettings
from stocktrace.infrastructure.providers.financial.mock_provider import MockFinancialProvider
from stocktrace.infrastructure.telegram.aiogram_router import (
    _build_financial_command_response,
    _build_financial_compare_response,
    _build_trace_command_response,
    _financial_usage,
    create_router,
)


@pytest.mark.asyncio
async def test_market_command_no_service() -> None:
    settings = Settings(telegram=TelegramSettings(allowed_user_ids=[123]))
    router = create_router(
        settings=settings,
        watchlist_service=AsyncMock(),
        portfolio_service=AsyncMock(),
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
        portfolio_service=AsyncMock(),
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
        portfolio_service=AsyncMock(),
        market_data_service=AsyncMock(),
        trace_service=AsyncMock(),
    )

    callback_names = {handler.callback.__name__ for handler in router.message.handlers}

    assert "trace" in callback_names


def test_financial_usage_is_command_specific() -> None:
    assert _financial_usage("report") == "Cách dùng: /report MÃ (vd: /report HPG)"
    assert _financial_usage("score") == "Cách dùng: /score MÃ (vd: /score HPG)"


def test_trace_commands_render_distinct_signal_and_risk_views() -> None:
    events = (
        StockTraceEvent(
            symbol="HPG",
            event_type=TraceEventType.TRACE_DISCLOSURE,
            severity=TraceSeverity.INFO,
            title="HPG disclosure",
            summary="Disclosure",
            source=official_trace_sources()[1],
            confidence=Decimal("1"),
        ),
        StockTraceEvent(
            symbol="HPG",
            event_type=TraceEventType.TRACE_REGULATORY,
            severity=TraceSeverity.HIGH,
            title="HPG warning",
            summary="Warning",
            source=official_trace_sources()[3],
            confidence=Decimal("1"),
        ),
    )
    timeline = TraceTimeline(
        symbol="HPG",
        events=events,
        score=TraceScoringEngine().calculate("HPG", events),
    )

    signals = _build_trace_command_response(timeline, "signals")
    risks = _build_trace_command_response(timeline, "risks")

    assert "Tín hiệu theo dõi" in signals
    assert "HPG disclosure" in signals
    assert "Rủi ro cần theo dõi" in risks
    assert "HPG warning" in risks
    assert "HPG disclosure" not in risks


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


@pytest.mark.asyncio
async def test_financial_compare_explains_and_verifies_result() -> None:
    service = FinancialAnalysisService(financial_provider=MockFinancialProvider())
    result = await service.compare("HPG", "FPT", FinancialPeriod.parse("1Y"))

    text = _build_financial_compare_response(result)

    assert "Vì sao có kết quả này?" in text
    assert "Tự kiểm chứng dữ liệu" in text
    assert "Độ tin cậy: <b>50/100</b>" in text
    assert "chất lượng" in text
    assert "4 kỳ" in text
    assert "Nguồn dữ liệu mô phỏng" in text
