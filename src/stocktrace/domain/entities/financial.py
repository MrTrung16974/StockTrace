"""Financial analysis domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Recommendation(StrEnum):
    """Investment recommendation levels."""

    STRONG_SELL = "STRONG SELL"
    SELL = "SELL"
    HOLD = "HOLD"
    BUY = "BUY"
    STRONG_BUY = "STRONG BUY"


class ValuationStatus(StrEnum):
    """Relative valuation status."""

    UNDERVALUED = "UNDERVALUED"
    FAIR = "FAIR"
    OVERVALUED = "OVERVALUED"


class TraceType(StrEnum):
    """Financial trace signal types."""

    TRACE_FINANCIAL = "TRACE_FINANCIAL"
    TRACE_VALUATION = "TRACE_VALUATION"
    TRACE_CASHFLOW = "TRACE_CASHFLOW"
    TRACE_DEBT = "TRACE_DEBT"
    TRACE_GROWTH = "TRACE_GROWTH"
    TRACE_RISK = "TRACE_RISK"


class SignalLevel(StrEnum):
    """Alert signal severity."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class FinancialProfile(StrEnum):
    """Industry-specific framework used for financial interpretation."""

    GENERAL = "general"
    BANK = "bank"


@dataclass(frozen=True, slots=True)
class IncomeStatement:
    """Quarterly or annual income statement."""

    symbol: str
    period: str
    period_end: date
    revenue: Decimal
    cost_of_goods: Decimal
    gross_profit: Decimal
    operating_expenses: Decimal
    operating_income: Decimal
    ebitda: Decimal
    net_income: Decimal
    eps: Decimal
    currency: str = "VND"
    profile: FinancialProfile = FinancialProfile.GENERAL


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    """Quarterly or annual balance sheet."""

    symbol: str
    period: str
    period_end: date
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    short_term_debt: Decimal
    long_term_debt: Decimal
    cash_and_equivalents: Decimal
    inventory: Decimal
    current_assets: Decimal
    current_liabilities: Decimal
    currency: str = "VND"


@dataclass(frozen=True, slots=True)
class CashFlow:
    """Quarterly or annual cash flow statement."""

    symbol: str
    period: str
    period_end: date
    operating_cash_flow: Decimal
    investing_cash_flow: Decimal
    financing_cash_flow: Decimal
    free_cash_flow: Decimal
    capex: Decimal
    currency: str = "VND"


@dataclass(frozen=True, slots=True)
class FinancialStatement:
    """Combined financial statement for a period."""

    symbol: str
    period: str
    period_end: date
    income: IncomeStatement
    balance: BalanceSheet
    cash_flow: CashFlow


@dataclass(frozen=True, slots=True)
class FinancialRatio:
    """Calculated financial ratios for a period."""

    symbol: str
    period: str
    period_end: date
    # Profitability
    roe: Decimal | None = None
    roa: Decimal | None = None
    ros: Decimal | None = None
    gross_margin: Decimal | None = None
    ebitda_margin: Decimal | None = None
    net_margin: Decimal | None = None
    # Growth
    revenue_growth: Decimal | None = None
    profit_growth: Decimal | None = None
    eps_growth: Decimal | None = None
    revenue_cagr: Decimal | None = None
    # Debt
    debt_to_equity: Decimal | None = None
    debt_to_asset: Decimal | None = None
    interest_coverage: Decimal | None = None
    current_ratio: Decimal | None = None
    quick_ratio: Decimal | None = None
    # Cash Flow
    operating_cash_flow: Decimal | None = None
    free_cash_flow: Decimal | None = None
    fcf_growth: Decimal | None = None
    cash_conversion: Decimal | None = None
    # Valuation
    pe: Decimal | None = None
    pb: Decimal | None = None
    peg: Decimal | None = None
    ev_ebitda: Decimal | None = None
    dcf_value: Decimal | None = None
    graham_value: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CategoryScore:
    """Score for a single financial category."""

    category: str
    score: Decimal
    weight: Decimal
    weighted_score: Decimal


@dataclass(frozen=True, slots=True)
class FinancialScore:
    """Weighted composite financial score (0-10)."""

    symbol: str
    period: str
    overall_score: Decimal
    recommendation: Recommendation
    growth_score: Decimal
    profitability_score: Decimal
    debt_score: Decimal
    cash_flow_score: Decimal
    valuation_score: Decimal
    categories: tuple[CategoryScore, ...] = ()


@dataclass(frozen=True, slots=True)
class Valuation:
    """Valuation metrics for a symbol."""

    symbol: str
    period_end: date
    current_pe: Decimal | None
    average_pe: Decimal | None
    current_pb: Decimal | None
    average_pb: Decimal | None
    status: ValuationStatus
    target_price: Decimal | None = None
    current_price: Decimal | None = None
    historical_pe: tuple[tuple[int, Decimal], ...] = ()
    historical_pb: tuple[tuple[int, Decimal], ...] = ()


@dataclass(frozen=True, slots=True)
class RevenueSegment:
    """Revenue composition segment."""

    name: str
    percentage: Decimal


@dataclass(frozen=True, slots=True)
class CompanyFundamental:
    """Company fundamental profile."""

    symbol: str
    company_name: str
    sector: str
    industry: str
    market_cap: Decimal | None = None
    shares_outstanding: Decimal | None = None
    revenue_segments: tuple[RevenueSegment, ...] = ()
    data_source: str = "unknown"
    is_mock_data: bool = False


@dataclass(frozen=True, slots=True)
class FinancialDataQuality:
    """Evidence and validation status for a financial analysis."""

    score: Decimal
    is_ready_for_analysis: bool
    is_ready_for_investment_signal: bool
    issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FinancialSignal:
    """Triggered financial alert signal."""

    trace_type: TraceType
    level: SignalLevel
    label: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIFinancialAnalysis:
    """LLM-generated financial analysis."""

    symbol: str
    executive_summary: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    opportunities: tuple[str, ...]
    risks: tuple[str, ...]
    recommendation: Recommendation
    confidence: Decimal
    target_price: Decimal | None = None
    raw_response: str = ""


@dataclass(frozen=True, slots=True)
class ChartDataPoint:
    """Single data point for chart rendering."""

    label: str
    value: Decimal


@dataclass(frozen=True, slots=True)
class ChartSeries:
    """A named series of chart data points."""

    name: str
    points: tuple[ChartDataPoint, ...]
    unit: str = ""


@dataclass(frozen=True, slots=True)
class ChartMetadata:
    """Metadata for a single chart widget."""

    chart_id: str
    chart_type: str
    title: str
    series: tuple[ChartSeries, ...]
    ascii_render: str = ""


@dataclass(frozen=True, slots=True)
class FinancialAnalysis:
    """Complete financial analysis aggregate."""

    symbol: str
    company_name: str
    period_label: str
    period_start: date
    period_end: date
    statements: tuple[FinancialStatement, ...]
    ratios: tuple[FinancialRatio, ...]
    score: FinancialScore
    valuation: Valuation
    fundamentals: CompanyFundamental
    quality: FinancialDataQuality
    ai_analysis: AIFinancialAnalysis | None = None
    signals: tuple[FinancialSignal, ...] = ()
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, slots=True)
class FinancialDashboard:
    """Visual dashboard response for Telegram/API."""

    analysis: FinancialAnalysis
    charts: tuple[ChartMetadata, ...]
    telegram_html: str
    json_payload: dict[str, Any]
