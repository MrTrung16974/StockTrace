"""Mock financial provider with sample Vietnamese stock data."""

from __future__ import annotations

from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    CompanyFundamental,
    FinancialRatio,
    IncomeStatement,
)
from stocktrace.domain.ports.financial_provider import FinancialDataNotFoundError
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.providers.financial.sample_data import (
    build_balance_sheet,
    build_cash_flow,
    build_fundamentals,
    build_income_statement,
    get_company_data,
)


class MockFinancialProvider:
    """Financial provider using sample data for development."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def get_income_statement(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[IncomeStatement]:
        data = get_company_data(symbol)
        if data is None:
            msg = f"No financial data for {symbol}"
            raise FinancialDataNotFoundError(msg)

        return [
            build_income_statement(symbol, q[0], q[1], q[2], q[3], q[4])
            for q in data["quarters"]
        ]

    async def get_balance_sheet(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[BalanceSheet]:
        data = get_company_data(symbol)
        if data is None:
            msg = f"No financial data for {symbol}"
            raise FinancialDataNotFoundError(msg)

        return [
            build_balance_sheet(symbol, q[0], q[1], q[2])
            for q in data["quarters"]
        ]

    async def get_cash_flow(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[CashFlow]:
        data = get_company_data(symbol)
        if data is None:
            msg = f"No financial data for {symbol}"
            raise FinancialDataNotFoundError(msg)

        return [
            build_cash_flow(symbol, q[0], q[1], q[4], q[3])
            for q in data["quarters"]
        ]

    async def get_ratios(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[FinancialRatio]:
        return []

    async def get_company_fundamentals(self, symbol: str) -> CompanyFundamental:
        result = build_fundamentals(symbol)
        if result is None:
            msg = f"No company data for {symbol}"
            raise FinancialDataNotFoundError(msg)
        return result
