"""Composite financial provider error classification tests."""

from __future__ import annotations

import pytest

from stocktrace.domain.ports.financial_provider import (
    FinancialDataNotFoundError,
    FinancialProviderError,
    FinancialProviderUnavailableError,
)
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.providers.financial.composite import CompositeFinancialProvider


class MissingFinancialProvider:
    """Provider double that confirms no statements exist."""

    provider_name = "missing"

    async def get_income_statement(self, symbol: str, period: FinancialPeriod) -> list[object]:
        raise FinancialDataNotFoundError(f"No statements for {symbol}")


class UnavailableFinancialProvider:
    """Provider double that cannot contact its upstream service."""

    provider_name = "unavailable"

    async def get_income_statement(self, symbol: str, period: FinancialPeriod) -> list[object]:
        raise FinancialProviderError(f"Provider unavailable for {symbol}")


@pytest.mark.asyncio
async def test_composite_reports_not_found_when_all_providers_confirm_absence() -> None:
    provider = CompositeFinancialProvider(providers=[MissingFinancialProvider()])

    with pytest.raises(FinancialDataNotFoundError):
        await provider.get_income_statement("HPG", FinancialPeriod.parse("1Y"))


@pytest.mark.asyncio
async def test_composite_reports_unavailable_when_any_provider_cannot_confirm_data() -> None:
    provider = CompositeFinancialProvider(
        providers=[MissingFinancialProvider(), UnavailableFinancialProvider()],
    )

    with pytest.raises(FinancialProviderUnavailableError):
        await provider.get_income_statement("HPG", FinancialPeriod.parse("1Y"))
