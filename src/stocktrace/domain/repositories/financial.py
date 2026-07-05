"""Financial data repository ports."""

from __future__ import annotations

from typing import Protocol

from stocktrace.domain.entities.financial import (
    FinancialAnalysis,
    FinancialRatio,
    FinancialScore,
    FinancialStatement,
    Valuation,
)


class FinancialStatementRepository(Protocol):
    """Persistence port for financial statements."""

    async def save_statements(self, statements: list[FinancialStatement]) -> None:
        """Persist financial statements."""
        ...

    async def get_statements(
        self,
        symbol: str,
        limit: int = 20,
    ) -> list[FinancialStatement]:
        """Retrieve stored financial statements for a symbol."""
        ...


class FinancialRatioRepository(Protocol):
    """Persistence port for financial ratios."""

    async def save_ratios(self, ratios: list[FinancialRatio]) -> None:
        """Persist calculated ratios."""
        ...

    async def get_ratios(
        self,
        symbol: str,
        limit: int = 20,
    ) -> list[FinancialRatio]:
        """Retrieve stored ratios for a symbol."""
        ...


class FinancialScoreRepository(Protocol):
    """Persistence port for financial scores."""

    async def save_score(self, score: FinancialScore) -> None:
        """Persist a financial score."""
        ...

    async def get_latest_score(self, symbol: str) -> FinancialScore | None:
        """Retrieve the most recent score for a symbol."""
        ...


class FinancialAnalysisRepository(Protocol):
    """Persistence port for full financial analyses."""

    async def save_analysis(self, analysis: FinancialAnalysis) -> None:
        """Persist a complete financial analysis."""
        ...

    async def get_latest_analysis(self, symbol: str) -> FinancialAnalysis | None:
        """Retrieve the most recent analysis for a symbol."""
        ...


class ValuationRepository(Protocol):
    """Persistence port for valuation history."""

    async def save_valuation(self, valuation: Valuation) -> None:
        """Persist valuation data."""
        ...

    async def get_valuation_history(
        self,
        symbol: str,
        limit: int = 20,
    ) -> list[Valuation]:
        """Retrieve valuation history for a symbol."""
        ...
