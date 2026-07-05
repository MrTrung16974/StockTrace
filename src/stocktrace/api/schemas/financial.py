"""Financial analysis API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ChartPointSchema(BaseModel):
    """Chart data point."""

    label: str
    value: float


class ChartSeriesSchema(BaseModel):
    """Chart series."""

    name: str
    unit: str = ""
    points: list[ChartPointSchema]


class ChartSchema(BaseModel):
    """Chart metadata."""

    id: str
    type: str
    title: str
    series: list[ChartSeriesSchema]


class FinancialScoresSchema(BaseModel):
    """Category scores."""

    growth: float
    profitability: float
    debt: float
    cash_flow: float
    valuation: float


class ValuationSchema(BaseModel):
    """Valuation snapshot."""

    current_pe: float | None = None
    average_pe: float | None = None
    status: str
    target_price: float | None = None


class SignalSchema(BaseModel):
    """Financial signal."""

    type: str
    level: str
    label: str
    reasons: list[str]


class AISummarySchema(BaseModel):
    """AI analysis summary."""

    executive_summary: str
    strengths: list[str]
    weaknesses: list[str]
    risks: list[str]
    recommendation: str
    confidence: float
    target_price: float | None = None


class FinancialDashboardResponse(BaseModel):
    """Full financial dashboard response."""

    symbol: str
    company_name: str
    period_start: date
    period_end: date
    period_label: str
    recommendation: str
    confidence: int
    financial_score: float
    scores: FinancialScoresSchema
    valuation: ValuationSchema
    charts: list[ChartSchema]
    signals: list[SignalSchema]
    ai_summary: AISummarySchema | None = None
    generated_at: datetime | None = None


class FinancialCompareResponse(BaseModel):
    """Financial comparison response."""

    symbol_a: FinancialDashboardResponse
    symbol_b: FinancialDashboardResponse
    winner: str
    comparison_summary: str
