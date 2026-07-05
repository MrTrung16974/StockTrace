"""Financial data provider port."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    CompanyFundamental,
    FinancialRatio,
    IncomeStatement,
)
from stocktrace.domain.value_objects.financial_period import FinancialPeriod


class FinancialProviderError(RuntimeError):
    """Raised when financial data cannot be retrieved."""


class FinancialDataNotFoundError(FinancialProviderError):
    """Raised when no financial data exists for a symbol."""


class FinancialProvider(Protocol):
    """Port for retrieving financial statement data from external sources."""

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        ...

    async def get_income_statement(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[IncomeStatement]:
        """Return income statements for the given period."""
        ...

    async def get_balance_sheet(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[BalanceSheet]:
        """Return balance sheets for the given period."""
        ...

    async def get_cash_flow(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[CashFlow]:
        """Return cash flow statements for the given period."""
        ...

    async def get_ratios(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[FinancialRatio]:
        """Return pre-calculated ratios if available from provider."""
        ...

    async def get_company_fundamentals(self, symbol: str) -> CompanyFundamental:
        """Return company fundamental profile."""
        ...
