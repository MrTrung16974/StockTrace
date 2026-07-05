"""Unit tests for financial ratio engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from stocktrace.application.services.financial.ratio_engine import FinancialRatioEngine
from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    FinancialStatement,
    IncomeStatement,
)
from stocktrace.infrastructure.providers.financial.sample_data import (
    build_balance_sheet,
    build_cash_flow,
    build_income_statement,
)


def _make_statement(
    symbol: str,
    period: str,
    period_end: date,
    revenue_b: Decimal,
    profit_b: Decimal,
    ocf_b: Decimal,
) -> FinancialStatement:
    inc = build_income_statement(symbol, period, period_end, revenue_b, profit_b, ocf_b)
    bal = build_balance_sheet(symbol, period, period_end, revenue_b)
    cf = build_cash_flow(symbol, period, period_end, ocf_b, profit_b)
    return FinancialStatement(
        symbol=symbol,
        period=period,
        period_end=period_end,
        income=inc,
        balance=bal,
        cash_flow=cf,
    )


@pytest.fixture
def engine() -> FinancialRatioEngine:
    return FinancialRatioEngine()


@pytest.fixture
def fpt_statements() -> list[FinancialStatement]:
    return [
        _make_statement("FPT", "Q1", date(2025, 3, 31), Decimal("14000"), Decimal("2200"), Decimal("1000")),
        _make_statement("FPT", "Q2", date(2025, 6, 30), Decimal("15200"), Decimal("2400"), Decimal("1200")),
        _make_statement("FPT", "Q3", date(2025, 9, 30), Decimal("16500"), Decimal("2600"), Decimal("1500")),
        _make_statement("FPT", "Q4", date(2025, 12, 31), Decimal("17800"), Decimal("2900"), Decimal("1800")),
    ]


def test_calculate_ratios_returns_one_per_period(
    engine: FinancialRatioEngine,
    fpt_statements: list[FinancialStatement],
) -> None:
    ratios = engine.calculate(fpt_statements)
    assert len(ratios) == 4


def test_roe_calculated(engine: FinancialRatioEngine, fpt_statements: list[FinancialStatement]) -> None:
    ratios = engine.calculate(fpt_statements)
    latest = ratios[-1]
    assert latest.roe is not None
    assert latest.roe > Decimal("0")


def test_revenue_growth_calculated(
    engine: FinancialRatioEngine,
    fpt_statements: list[FinancialStatement],
) -> None:
    ratios = engine.calculate(fpt_statements)
    assert ratios[0].revenue_growth is None
    assert ratios[1].revenue_growth is not None
    assert ratios[1].revenue_growth > Decimal("0")


def test_debt_ratios(engine: FinancialRatioEngine, fpt_statements: list[FinancialStatement]) -> None:
    ratios = engine.calculate(fpt_statements)
    latest = ratios[-1]
    assert latest.debt_to_equity is not None
    assert latest.current_ratio is not None


def test_empty_statements(engine: FinancialRatioEngine) -> None:
    assert engine.calculate([]) == []
