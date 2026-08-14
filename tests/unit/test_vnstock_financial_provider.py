"""Regression tests for Vnstock 4.x financial statement identifiers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pandas as pd
import pytest

from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.providers.financial.vnstock_provider import (
    VNStockFinancialProvider,
)

_REVENUE = 55_000
_LIABILITIES = 60_000
_SHORT_TERM_DEBT = 12_000
_LONG_TERM_DEBT = 8_000
_OPERATING_CASH_FLOW = 9_000
_FREE_CASH_FLOW = 6_000


def _frame(values: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "item_id": list(values),
            "2026-Q2": list(values.values()),
        },
    )


@pytest.mark.asyncio
async def test_provider_accepts_current_vnstock_vci_item_ids() -> None:
    provider = VNStockFinancialProvider()
    provider._fetch_statement = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            _frame(
                {
                    "net_sales": 55_000,
                    "cost_of_sales": 40_000,
                    "gross_profit": 15_000,
                    "operating_profit_loss": 8_000,
                    "net_profit_loss_after_tax": 5_000,
                    "eps_basic_vnd": 1_200,
                },
            ),
            _frame(
                {
                    "total_assets": 100_000,
                    "liabilities": 60_000,
                    "owners_equity": 40_000,
                    "cash_and_cash_equivalents": 10_000,
                    "current_assets": 50_000,
                    "current_liabilities": 30_000,
                    "short_term_borrowings": 12_000,
                    "long_term_borrowings": 8_000,
                },
            ),
            _frame(
                {
                    "net_cash_inflows_outflows_from_operating_activities": 9_000,
                    "net_cash_inflows_outflows_from_investing_activities": -4_000,
                    "net_cash_inflows_outflows_from_financing_activities": -2_000,
                    "purchases_of_fixed_assets_and_other_long_term_assets": -3_000,
                },
            ),
        ],
    )
    period = FinancialPeriod.parse("1Y")

    income = await provider.get_income_statement("HPG", period)
    balance = await provider.get_balance_sheet("HPG", period)
    cash_flow = await provider.get_cash_flow("HPG", period)

    assert income[0].revenue == _REVENUE
    assert balance[0].total_liabilities == _LIABILITIES
    assert balance[0].short_term_debt == _SHORT_TERM_DEBT
    assert balance[0].long_term_debt == _LONG_TERM_DEBT
    assert cash_flow[0].operating_cash_flow == _OPERATING_CASH_FLOW
    assert cash_flow[0].free_cash_flow == _FREE_CASH_FLOW
