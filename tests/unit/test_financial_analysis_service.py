"""Unit tests for financial analysis service."""

from __future__ import annotations

import pytest

from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
)
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.providers.financial.mock_provider import MockFinancialProvider


@pytest.fixture
def service() -> FinancialAnalysisService:
    return FinancialAnalysisService(financial_provider=MockFinancialProvider())


@pytest.mark.asyncio
async def test_analyze_fpt_returns_dashboard(service: FinancialAnalysisService) -> None:
    period = FinancialPeriod.parse("1Y")
    dashboard = await service.analyze("FPT", period)

    assert dashboard.analysis.symbol == "FPT"
    assert dashboard.analysis.company_name == "FPT CORPORATION"
    assert dashboard.analysis.score.overall_score > 0
    assert len(dashboard.charts) == 5
    assert "Financial Analysis Dashboard" in dashboard.telegram_html
    assert dashboard.json_payload["symbol"] == "FPT"


@pytest.mark.asyncio
async def test_analyze_includes_recommendation(service: FinancialAnalysisService) -> None:
    period = FinancialPeriod.parse("6M")
    dashboard = await service.analyze("FPT", period)

    assert dashboard.analysis.score.recommendation is not None
    assert dashboard.json_payload["recommendation"] in (
        "BUY", "SELL", "HOLD", "STRONG BUY", "STRONG SELL",
    )


@pytest.mark.asyncio
async def test_compare_fpt_cmg(service: FinancialAnalysisService) -> None:
    period = FinancialPeriod.parse("1Y")
    result = await service.compare("FPT", "CMG", period)

    assert result.winner in ("FPT", "CMG")
    assert result.symbol_a.analysis.symbol == "FPT"
    assert result.symbol_b.analysis.symbol == "CMG"


@pytest.mark.asyncio
async def test_unknown_symbol_raises(service: FinancialAnalysisService) -> None:
    from stocktrace.domain.ports.financial_provider import FinancialDataNotFoundError

    period = FinancialPeriod.parse("1Y")
    with pytest.raises(FinancialDataNotFoundError):
        await service.analyze("UNKNOWN", period)
