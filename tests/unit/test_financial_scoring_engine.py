"""Unit tests for financial scoring engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from stocktrace.application.services.financial.scoring_engine import FinancialScoringEngine
from stocktrace.domain.entities.financial import FinancialRatio, Recommendation, Valuation, ValuationStatus


@pytest.fixture
def engine() -> FinancialScoringEngine:
    return FinancialScoringEngine()


@pytest.fixture
def strong_ratios() -> list[FinancialRatio]:
    return [
        FinancialRatio(
            symbol="FPT",
            period="Q4",
            period_end=date(2025, 12, 31),
            roe=Decimal("22"),
            roa=Decimal("12"),
            net_margin=Decimal("16"),
            gross_margin=Decimal("45"),
            revenue_growth=Decimal("18"),
            profit_growth=Decimal("21"),
            eps_growth=Decimal("15"),
            debt_to_equity=Decimal("0.4"),
            current_ratio=Decimal("1.8"),
            quick_ratio=Decimal("1.2"),
            operating_cash_flow=Decimal("1800000000000"),
            free_cash_flow=Decimal("1200000000000"),
            fcf_growth=Decimal("10"),
            cash_conversion=Decimal("1.1"),
            pe=Decimal("19"),
            pb=Decimal("3"),
        ),
    ]


@pytest.fixture
def undervalued() -> Valuation:
    return Valuation(
        symbol="FPT",
        period_end=date(2025, 12, 31),
        current_pe=Decimal("19"),
        average_pe=Decimal("22"),
        current_pb=Decimal("3"),
        average_pb=Decimal("3.5"),
        status=ValuationStatus.UNDERVALUED,
    )


def test_high_score_recommends_buy(
    engine: FinancialScoringEngine,
    strong_ratios: list[FinancialRatio],
    undervalued: Valuation,
) -> None:
    score = engine.calculate("FPT", "1Y", strong_ratios, undervalued)
    assert score.overall_score >= Decimal("7")
    assert score.recommendation in (Recommendation.BUY, Recommendation.STRONG_BUY)


def test_score_categories_present(
    engine: FinancialScoringEngine,
    strong_ratios: list[FinancialRatio],
    undervalued: Valuation,
) -> None:
    score = engine.calculate("FPT", "1Y", strong_ratios, undervalued)
    assert len(score.categories) == 5
    assert score.growth_score > Decimal("0")
    assert score.profitability_score > Decimal("0")


def test_empty_ratios_returns_hold(engine: FinancialScoringEngine) -> None:
    score = engine.calculate("FPT", "1Y", [], None)
    assert score.recommendation == Recommendation.HOLD
