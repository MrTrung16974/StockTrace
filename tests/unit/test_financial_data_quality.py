"""Tests for financial statement quality gates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from stocktrace.application.services.financial.data_quality import FinancialDataQualityEngine
from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    FinancialStatement,
    IncomeStatement,
)

_EXPECTED_QUALITY_ISSUES = 2


def _statement(index: int, *, balanced: bool = True) -> FinancialStatement:
    period_end = date(2025, index * 3, 28)
    assets = Decimal("100")
    liabilities = Decimal("60")
    equity = Decimal("40") if balanced else Decimal("35")
    income = IncomeStatement(
        symbol="ABC",
        period=f"Q{index}",
        period_end=period_end,
        revenue=Decimal("100"),
        cost_of_goods=Decimal("50"),
        gross_profit=Decimal("50"),
        operating_expenses=Decimal("20"),
        operating_income=Decimal("30"),
        ebitda=Decimal("30"),
        net_income=Decimal("20"),
        eps=Decimal("1000"),
    )
    balance = BalanceSheet(
        symbol="ABC",
        period=f"Q{index}",
        period_end=period_end,
        total_assets=assets,
        total_liabilities=liabilities,
        total_equity=equity,
        short_term_debt=Decimal("10"),
        long_term_debt=Decimal("10"),
        cash_and_equivalents=Decimal("10"),
        inventory=Decimal("10"),
        current_assets=Decimal("40"),
        current_liabilities=Decimal("30"),
    )
    cash_flow = CashFlow(
        symbol="ABC",
        period=f"Q{index}",
        period_end=period_end,
        operating_cash_flow=Decimal("25"),
        investing_cash_flow=Decimal("-10"),
        financing_cash_flow=Decimal("0"),
        free_cash_flow=Decimal("15"),
        capex=Decimal("10"),
    )
    return FinancialStatement("ABC", f"Q{index}", period_end, income, balance, cash_flow)


def test_quality_gate_accepts_four_recent_balanced_quarters() -> None:
    quality = FinancialDataQualityEngine().assess(
        [_statement(index) for index in range(1, 5)],
        is_mock_data=False,
        today=date(2025, 12, 31),
    )

    assert quality.score == Decimal("100")
    assert quality.is_ready_for_investment_signal is True


def test_quality_gate_blocks_unbalanced_or_insufficient_data() -> None:
    quality = FinancialDataQualityEngine().assess(
        [_statement(1), _statement(2), _statement(3, balanced=False)],
        is_mock_data=False,
        today=date(2025, 12, 31),
    )

    assert quality.is_ready_for_investment_signal is False
    assert len(quality.issues) == _EXPECTED_QUALITY_ISSUES
