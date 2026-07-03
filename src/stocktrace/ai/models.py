"""AI analysis data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from stocktrace.application.services.market_data import NewsArticle, StockQuote


class AnalysisMode(StrEnum):
    """Analysis depth for prompt and output formatting."""

    NEWS_ONLY = "news_only"
    FULL = "full"
    MARKET = "market"


class SentimentLabel(StrEnum):
    """High-level sentiment derived from news and price context."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class HistoricalPoint:
    """Single historical price observation."""

    day: date
    close: Decimal
    change_percent: Decimal


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Inputs gathered before building an LLM prompt."""

    symbol: str
    news: tuple[NewsArticle, ...]
    mode: AnalysisMode
    price: StockQuote | None = None
    historical: tuple[HistoricalPoint, ...] = ()
    technical_indicators: dict | None = None
    fundamental_data: dict | None = None
    score: dict | None = None


@dataclass(frozen=True, slots=True)
class MarketAnalysisContext:
    """Inputs gathered for market-level LLM prompt."""

    indices: dict[str, StockQuote | None]
    sectors: dict[str, StockQuote | None]
    international: dict[str, StockQuote | None]
    news: tuple[NewsArticle, ...]


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """Normalized request sent to an LLM provider."""

    prompt: str
    max_tokens: int = 1500
    temperature: float = 0.3
    system_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Normalized response from an LLM provider."""

    content: str
    model: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class StockAnalysisResult:
    """Structured stock analysis parsed from LLM output."""

    symbol: str
    overview: str
    positives: str
    risks: str
    short_term: str
    sentiment: SentimentLabel
    medium_term: str | None = None
    conclusion: str | None = None
    
    # New AI requested fields
    positive_scenario: str | None = None
    neutral_scenario: str | None = None
    negative_scenario: str | None = None
    recommendation_action: str | None = None
    recommendation_confidence: str | None = None
    recommendation_reasons: str | None = None
    
    raw_response: str = ""


@dataclass(frozen=True, slots=True)
class MarketAnalysisResult:
    """Structured market analysis parsed from LLM output."""

    overview: str
    sentiment: SentimentLabel
    positive_sectors: str
    negative_sectors: str
    cash_flow: str
    international_impact: str
    short_term: str
    medium_term: str
    risks: str
    conclusion: str
    raw_response: str = ""
