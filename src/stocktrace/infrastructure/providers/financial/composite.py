"""Composite financial provider with fallback chain."""

from __future__ import annotations

from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    CompanyFundamental,
    FinancialRatio,
    IncomeStatement,
)
from stocktrace.domain.ports.financial_provider import FinancialDataNotFoundError, FinancialProviderError
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class CompositeFinancialProvider:
    """Try multiple financial providers in order until one succeeds."""

    def __init__(self, providers: list) -> None:
        self._providers = providers

    @property
    def provider_name(self) -> str:
        names = [p.provider_name for p in self._providers]
        return f"composite({','.join(names)})"

    async def get_income_statement(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[IncomeStatement]:
        return await self._call("get_income_statement", symbol, period)

    async def get_balance_sheet(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[BalanceSheet]:
        return await self._call("get_balance_sheet", symbol, period)

    async def get_cash_flow(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[CashFlow]:
        return await self._call("get_cash_flow", symbol, period)

    async def get_ratios(
        self,
        symbol: str,
        period: FinancialPeriod,
    ) -> list[FinancialRatio]:
        for provider in self._providers:
            try:
                return await provider.get_ratios(symbol, period)
            except (FinancialProviderError, FinancialDataNotFoundError):
                continue
        return []

    async def get_company_fundamentals(self, symbol: str) -> CompanyFundamental:
        return await self._call("get_company_fundamentals", symbol)

    async def _call(self, method: str, symbol: str, period: FinancialPeriod | None = None):
        """Call method on providers with fallback."""
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                fn = getattr(provider, method)
                if period is not None:
                    return await fn(symbol, period)
                return await fn(symbol)
            except (FinancialProviderError, FinancialDataNotFoundError) as exc:
                logger.warning(
                    "financial_provider_failed",
                    provider=provider.provider_name,
                    method=method,
                    symbol=symbol,
                    error=str(exc),
                )
                last_error = exc
                continue
        msg = f"All financial providers failed for {symbol}"
        raise FinancialDataNotFoundError(msg) from last_error
