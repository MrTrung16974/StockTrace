"""Financial analysis CQRS query handlers."""

from __future__ import annotations

from stocktrace.application.queries.financial_queries import (
    CompareFinancialQuery,
    GetFinancialAnalysisQuery,
    GetFinancialReportQuery,
    GetFinancialScoreQuery,
    GetValuationQuery,
)
from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
    FinancialCompareResult,
)
from stocktrace.domain.entities.financial import FinancialDashboard
from stocktrace.domain.value_objects.financial_period import FinancialPeriod


class GetFinancialAnalysisQueryHandler:
    """Handle financial analysis dashboard queries."""

    def __init__(self, service: FinancialAnalysisService) -> None:
        self._service = service

    async def handle(self, query: GetFinancialAnalysisQuery) -> FinancialDashboard:
        period = FinancialPeriod.parse(query.period)
        return await self._service.analyze(query.symbol, period)


class GetFinancialReportQueryHandler:
    """Handle financial report queries (defaults to 1Y)."""

    def __init__(self, service: FinancialAnalysisService) -> None:
        self._service = service

    async def handle(self, query: GetFinancialReportQuery) -> FinancialDashboard:
        period = FinancialPeriod.parse("1Y")
        return await self._service.analyze(query.symbol, period)


class GetValuationQueryHandler:
    """Handle valuation queries."""

    def __init__(self, service: FinancialAnalysisService) -> None:
        self._service = service

    async def handle(self, query: GetValuationQuery) -> FinancialDashboard:
        period = FinancialPeriod.parse("1Y")
        return await self._service.analyze(query.symbol, period)


class GetFinancialScoreQueryHandler:
    """Handle financial score queries."""

    def __init__(self, service: FinancialAnalysisService) -> None:
        self._service = service

    async def handle(self, query: GetFinancialScoreQuery) -> FinancialDashboard:
        period = FinancialPeriod.parse(query.period)
        return await self._service.analyze(query.symbol, period)


class CompareFinancialQueryHandler:
    """Handle financial comparison queries."""

    def __init__(self, service: FinancialAnalysisService) -> None:
        self._service = service

    async def handle(self, query: CompareFinancialQuery) -> FinancialCompareResult:
        period = FinancialPeriod.parse(query.period)
        return await self._service.compare(query.symbol_a, query.symbol_b, period)
