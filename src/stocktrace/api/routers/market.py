"""Market-wide AI analysis API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from stocktrace.api.dependencies import get_request_container
from stocktrace.api.schemas.market import (
    AIMarketAnalysisSchema,
    MarketAnalysisResponse,
    MarketIndexSchema,
    MarketNewsArticleSchema,
    MarketQuoteSchema,
)
from stocktrace.application.services.market_analysis_service import (
    DOMESTIC_INDICES,
    MarketAnalysisService,
)
from stocktrace.bootstrap.container import Container

router = APIRouter(prefix="/api/v1/market", tags=["market"])


def _market_service(container: Container) -> MarketAnalysisService:
    return container.market_analysis_service()


@router.get("/analysis", response_model=MarketAnalysisResponse)
async def get_market_analysis(
    container: Annotated[Container, Depends(get_request_container)],
    news_limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> MarketAnalysisResponse:
    """Return Gemini-powered macro market analysis for Vietnam stock market.

    Aggregates:
    - VNINDEX, VN30, HNXINDEX, UPCOMINDEX real-time quotes
    - Key sector proxies (Banking, Securities, Real Estate, Steel, Tech, Retail, Energy)
    - International benchmarks (S&P500, Nasdaq, DXY, Oil, Gold, Bitcoin)
    - Recent market news (Vietnamese and international)

    Then runs a Gemini analysis pass to produce:
    - Market sentiment classification
    - Sector rotation insights
    - Cash flow commentary
    - International risk factors
    - Short-term and medium-term outlook
    """
    svc = _market_service(container)
    try:
        bundle = await svc.analyze_market(news_limit=news_limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Market analysis failed: {exc}") from exc

    # ── Map indices ──────────────────────────────────────────────────────────
    indices_list: list[MarketIndexSchema] = []
    for name in DOMESTIC_INDICES:
        quote = bundle.indices.get(name)
        indices_list.append(
            MarketIndexSchema(
                name=name,
                ticker=name,
                current_price=float(quote.current_price) if quote else None,
                change_percent=float(quote.change_percent) if quote else None,
            )
        )

    # ── Map sectors ──────────────────────────────────────────────────────────
    sectors_map: dict[str, MarketQuoteSchema | None] = {}
    for name, quote in bundle.sectors.items():
        if quote:
            sectors_map[name] = MarketQuoteSchema(
                ticker=quote.ticker,
                current_price=float(quote.current_price),
                change_percent=float(quote.change_percent),
            )
        else:
            sectors_map[name] = None

    # ── Map international ────────────────────────────────────────────────────
    international_map: dict[str, MarketQuoteSchema | None] = {}
    for name, quote in bundle.international.items():
        if quote:
            international_map[name] = MarketQuoteSchema(
                ticker=quote.ticker,
                current_price=float(quote.current_price),
                change_percent=float(quote.change_percent),
            )
        else:
            international_map[name] = None

    # ── Map news ─────────────────────────────────────────────────────────────
    news_list = [
        MarketNewsArticleSchema(
            title=article.title,
            source=article.source,
            url=article.url,
            published_at=article.published_at,
        )
        for article in bundle.news
    ]

    # ── Map AI analysis ──────────────────────────────────────────────────────
    ai_analysis: AIMarketAnalysisSchema | None = None
    if bundle.analysis is not None:
        a = bundle.analysis
        ai_analysis = AIMarketAnalysisSchema(
            overview=a.overview,
            sentiment=a.sentiment.value,
            positive_sectors=a.positive_sectors,
            negative_sectors=a.negative_sectors,
            cash_flow=a.cash_flow,
            international_impact=a.international_impact,
            short_term=a.short_term,
            medium_term=a.medium_term,
            risks=a.risks,
            conclusion=a.conclusion,
        )

    return MarketAnalysisResponse(
        timestamp=bundle.timestamp,
        indices=indices_list,
        sectors=sectors_map,
        international=international_map,
        news=news_list,
        ai_analysis=ai_analysis,
        ai_enabled=svc.is_enabled,
    )
