"""AI financial analysis models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from stocktrace.domain.entities.financial import (
    FinancialAnalysis,
    FinancialScore,
    Recommendation,
)


@dataclass(frozen=True, slots=True)
class FinancialAnalysisContext:
    """Context for LLM financial analysis."""

    symbol: str
    company_name: str
    period_label: str
    score: FinancialScore
    ratios_summary: dict[str, str]
    valuation_summary: dict[str, str]
    strengths_hints: tuple[str, ...]
    risks_hints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FinancialAnalysisLLMResult:
    """Parsed LLM financial analysis result."""

    executive_summary: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    opportunities: tuple[str, ...]
    risks: tuple[str, ...]
    recommendation: Recommendation
    confidence: Decimal
    target_price: Decimal | None = None
    raw_response: str = ""
