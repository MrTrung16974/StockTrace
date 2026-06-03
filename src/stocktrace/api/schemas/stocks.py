"""Stock market response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StockQuoteResponse(BaseModel):
    """Quote response payload."""

    ticker: str = Field(examples=["FPT"])
    company_name: str = Field(examples=["FPT Corporation"])
    current_price: float = Field(examples=[125000])
    change: float = Field(examples=[1500])
    change_percent: float = Field(examples=[1.21])
    open_price: float = Field(examples=[123500])
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
