"""VNStock financial provider stub."""

from __future__ import annotations

from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    CompanyFundamental,
    FinancialRatio,
    IncomeStatement,
)
from stocktrace.domain.ports.financial_provider import FinancialProviderError
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class VNStockFinancialProvider:
    """Financial data provider using VNStock API (stub for future integration)."""

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "vnstock"

    async def get_income_statement(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[IncomeStatement]:
        msg = "VNStock provider not yet configured. Use mock provider."
        raise FinancialProviderError(msg)

    async def get_balance_sheet(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[BalanceSheet]:
        msg = "VNStock provider not yet configured."
        raise FinancialProviderError(msg)

    async def get_cash_flow(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[CashFlow]:
        msg = "VNStock provider not yet configured."
        raise FinancialProviderError(msg)

    async def get_ratios(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[FinancialRatio]:
        return []

    async def get_company_fundamentals(self, symbol: str) -> CompanyFundamental:
        msg = "VNStock provider not yet configured."
        raise FinancialProviderError(msg)
