"""Stock market response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StockQuoteResponse(BaseModel):
    """Quote response payload."""

    ticker: str = Field(examples=["FPT"])
    company_name: str = Field(examples=["FPT Corporation"])
    current_price: float = Field(examples=[125000])
    change: float = Field(examples=[1500])
    change_percent: float = Field(examples=[1.21])
    open_price: float = Field(examples=[123000])
    high_price: float = Field(examples=[126000])
    low_price: float = Field(examples=[122000])
    volume: int = Field(examples=[2350000])
    timestamp: datetime
    currency: str = Field(default="USD", examples=["VND", "USD"])
    source: str = Field(default="Yahoo Finance", examples=["Yahoo Finance"])


class StockNewsArticleResponse(BaseModel):
    """News article response payload."""

    title: str
    summary: str | None = None
    source: str
    url: str
    published_at: datetime | None = None


class StockNewsResponse(BaseModel):
    """News list response payload."""

    ticker: str
    articles: list[StockNewsArticleResponse]
    # AI-powered insights added when AI is enabled
    ai_sentiment: str | None = Field(
        default=None,
        description="Overall sentiment: positive / negative / neutral / mixed",
    )
    ai_overview: str | None = Field(
        default=None,
        description="Gemini-generated news overview in Vietnamese",
    )
    ai_short_term: str | None = Field(
        default=None,
        description="Short-term price implication derived from news",
    )
    ai_risks: str | None = Field(
        default=None,
        description="Key risk factors identified from news",
    )


class AIScenarioSchema(BaseModel):
    """Gemini-generated scenario analysis."""

    positive: str | None = None
    neutral: str | None = None
    negative: str | None = None


class AIRecommendationSchema(BaseModel):
    """Gemini-generated recommendation block."""

    action: str | None = Field(default=None, examples=["MUA", "BÁN", "QUAN SÁT"])
    confidence: str | None = Field(default=None, examples=["Cao", "Trung bình", "Thấp"])
    reasons: str | None = None


class StockAnalysisResponse(BaseModel):
    """Full Gemini-powered stock analysis response."""

    ticker: str
    company_name: str | None = None
    current_price: float | None = None
    change_percent: float | None = None
    sentiment: str = Field(description="positive / negative / neutral / mixed")

    # Core analysis sections
    overview: str
    positives: str
    risks: str
    short_term: str
    medium_term: str | None = None
    conclusion: str | None = None

    # Scenario and recommendation
    scenarios: AIScenarioSchema | None = None
    recommendation: AIRecommendationSchema | None = None

    # Quantitative context
    technical_score: float | None = None
    news_count: int = 0
    has_historical_data: bool = False

    generated_at: datetime
