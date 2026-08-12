"""Market analysis API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MarketQuoteSchema(BaseModel):
    """Minimal quote for market overview display."""

    ticker: str
    current_price: float | None = None
    change_percent: float | None = None


class MarketIndexSchema(BaseModel):
    """Vietnam market index snapshot."""

    name: str
    ticker: str
    current_price: float | None = None
    change_percent: float | None = None


class MarketNewsArticleSchema(BaseModel):
    """News article used in market context."""

    title: str
    source: str
    url: str
    published_at: datetime | None = None


class AIMarketAnalysisSchema(BaseModel):
    """Gemini-generated market-wide analysis."""

    overview: str
    sentiment: str = Field(description="positive / negative / neutral / mixed")
    positive_sectors: str
    negative_sectors: str
    cash_flow: str
    international_impact: str
    short_term: str
    medium_term: str
    risks: str
    conclusion: str


class MarketAnalysisResponse(BaseModel):
    """Full market analysis response combining data + AI narrative."""

    timestamp: datetime

    # Market data snapshots
    indices: list[MarketIndexSchema]
    sectors: dict[str, MarketQuoteSchema | None]
    international: dict[str, MarketQuoteSchema | None]

    # News context used for analysis
    news: list[MarketNewsArticleSchema]

    # Gemini AI analysis (None when AI is disabled or key missing)
    ai_analysis: AIMarketAnalysisSchema | None = None

    # Meta
    ai_enabled: bool = False
    ai_status: str = Field(description="available / disabled / unavailable")
    news_error: str | None = None
