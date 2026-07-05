"""Financial analysis CQRS queries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetFinancialAnalysisQuery:
    """Query for full financial analysis dashboard."""

    symbol: str
    period: str


@dataclass(frozen=True, slots=True)
class GetFinancialReportQuery:
    """Query for financial report (default 1Y period)."""

    symbol: str


@dataclass(frozen=True, slots=True)
class GetValuationQuery:
    """Query for valuation analysis."""

    symbol: str


@dataclass(frozen=True, slots=True)
class GetFinancialScoreQuery:
    """Query for financial score only."""

    symbol: str
    period: str = "1Y"


@dataclass(frozen=True, slots=True)
class CompareFinancialQuery:
    """Query to compare two symbols."""

    symbol_a: str
    symbol_b: str
    period: str = "1Y"
