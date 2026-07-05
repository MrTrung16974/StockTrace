"""Financial analysis orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from stocktrace.application.services.financial.ai_financial_analysis_service import (
    AIFinancialAnalysisService,
)
from stocktrace.application.services.financial.ratio_engine import FinancialRatioEngine
from stocktrace.application.services.financial.scoring_engine import FinancialScoringEngine
from stocktrace.application.services.financial.signal_engine import FinancialSignalEngine
from stocktrace.application.services.financial.valuation_engine import ValuationEngine
from stocktrace.application.services.financial.visualization_engine import (
    FinancialVisualizationEngine,
)
from stocktrace.application.services.market_data import MarketDataService
from stocktrace.application.services.watchlist import normalize_symbol
from stocktrace.domain.entities.financial import (
    BalanceSheet,
    CashFlow,
    FinancialAnalysis,
    FinancialDashboard,
    FinancialStatement,
    IncomeStatement,
)
from stocktrace.domain.ports.financial_provider import FinancialDataNotFoundError, FinancialProvider
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class FinancialAnalysisError(RuntimeError):
    """Raised when financial analysis cannot be completed."""


@dataclass(frozen=True, slots=True)
class FinancialCompareResult:
    """Comparison result between two symbols."""

    symbol_a: FinancialDashboard
    symbol_b: FinancialDashboard
    winner: str
    comparison_summary: str


class FinancialAnalysisService:
    """Orchestrate financial statement analysis workflow."""

    def __init__(
        self,
        financial_provider: FinancialProvider,
        market_data_service: MarketDataService | None = None,
        ai_service: AIFinancialAnalysisService | None = None,
        ratio_engine: FinancialRatioEngine | None = None,
        scoring_engine: FinancialScoringEngine | None = None,
        valuation_engine: ValuationEngine | None = None,
        signal_engine: FinancialSignalEngine | None = None,
        visualization_engine: FinancialVisualizationEngine | None = None,
    ) -> None:
        self._provider = financial_provider
        self._market_data = market_data_service
        self._ai = ai_service
        self._ratio_engine = ratio_engine or FinancialRatioEngine()
        self._scoring_engine = scoring_engine or FinancialScoringEngine()
        self._valuation_engine = valuation_engine or ValuationEngine()
        self._signal_engine = signal_engine or FinancialSignalEngine()
        self._visualization = visualization_engine or FinancialVisualizationEngine()

    async def analyze(
        self,
        raw_symbol: str,
        period: FinancialPeriod,
    ) -> FinancialDashboard:
        """Run full financial analysis and return visual dashboard."""
        symbol = normalize_symbol(raw_symbol)
        period_start, period_end = period.date_range()

        fundamentals = await self._provider.get_company_fundamentals(symbol)
        income_stmts = await self._provider.get_income_statement(symbol, period)
        balance_sheets = await self._provider.get_balance_sheet(symbol, period)
        cash_flows = await self._provider.get_cash_flow(symbol, period)

        if not income_stmts:
            msg = f"No financial data found for {symbol}."
            raise FinancialDataNotFoundError(msg)

        statements = self._merge_statements(symbol, income_stmts, balance_sheets, cash_flows)

        current_price: Decimal | None = None
        shares = fundamentals.shares_outstanding
        if self._market_data is not None:
            try:
                quote = await self._market_data.get_quote(symbol)
                current_price = quote.current_price
            except Exception as exc:
                logger.warning("financial_quote_fetch_failed", symbol=symbol, error=str(exc))

        ratios = self._ratio_engine.calculate(statements, current_price, shares)
        valuation = self._valuation_engine.calculate(symbol, ratios, current_price)
        score = self._scoring_engine.calculate(symbol, period.label, ratios, valuation)
        signals = self._signal_engine.detect(ratios, score, valuation)

        analysis = FinancialAnalysis(
            symbol=symbol,
            company_name=fundamentals.company_name,
            period_label=period.label,
            period_start=period_start,
            period_end=period_end,
            statements=tuple(statements),
            ratios=tuple(ratios),
            score=score,
            valuation=valuation,
            fundamentals=fundamentals,
            signals=signals,
        )

        if self._ai is not None:
            ai_result = await self._ai.analyze(analysis)
            analysis = FinancialAnalysis(
                symbol=analysis.symbol,
                company_name=analysis.company_name,
                period_label=analysis.period_label,
                period_start=analysis.period_start,
                period_end=analysis.period_end,
                statements=analysis.statements,
                ratios=analysis.ratios,
                score=analysis.score,
                valuation=analysis.valuation,
                fundamentals=analysis.fundamentals,
                ai_analysis=ai_result,
                signals=analysis.signals,
                generated_at=analysis.generated_at,
            )

        return self._visualization.build_dashboard(analysis)

    async def compare(
        self,
        raw_symbol_a: str,
        raw_symbol_b: str,
        period: FinancialPeriod,
    ) -> FinancialCompareResult:
        """Compare financial health of two symbols."""
        dash_a = await self.analyze(raw_symbol_a, period)
        dash_b = await self.analyze(raw_symbol_b, period)

        score_a = dash_a.analysis.score.overall_score
        score_b = dash_b.analysis.score.overall_score

        if score_a >= score_b:
            winner = dash_a.analysis.symbol
            diff = score_a - score_b
        else:
            winner = dash_b.analysis.symbol
            diff = score_b - score_a

        summary = (
            f"{winner} scores higher ({diff:.1f} points). "
            f"{dash_a.analysis.symbol}: {score_a}/10 vs "
            f"{dash_b.analysis.symbol}: {score_b}/10."
        )

        return FinancialCompareResult(
            symbol_a=dash_a,
            symbol_b=dash_b,
            winner=winner,
            comparison_summary=summary,
        )

    def _merge_statements(
        self,
        symbol: str,
        income: list[IncomeStatement],
        balance: list[BalanceSheet],
        cash_flow: list[CashFlow],
    ) -> list[FinancialStatement]:
        """Merge individual statements into combined records."""
        balance_map = {b.period: b for b in balance}
        cf_map = {c.period: c for c in cash_flow}

        statements: list[FinancialStatement] = []
        for inc in sorted(income, key=lambda x: x.period_end):
            bal = balance_map.get(inc.period)
            cf = cf_map.get(inc.period)
            if bal is None or cf is None:
                continue
            statements.append(
                FinancialStatement(
                    symbol=symbol,
                    period=inc.period,
                    period_end=inc.period_end,
                    income=inc,
                    balance=bal,
                    cash_flow=cf,
                ),
            )
        return statements
