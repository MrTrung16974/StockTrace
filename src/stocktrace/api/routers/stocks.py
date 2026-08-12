"""Stock quote, news, and AI analysis API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from stocktrace.api.dependencies import get_request_container
from stocktrace.api.schemas.stocks import (
    AIRecommendationSchema,
    AIScenarioSchema,
    StockAnalysisResponse,
    StockNewsArticleResponse,
    StockNewsResponse,
    StockQuoteResponse,
)
from stocktrace.application.queries.stock_handlers import (
    GetStockNewsQueryHandler,
    GetStockQuoteQueryHandler,
)
from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.application.services.market_data import ProviderUnavailableError
from stocktrace.application.services.stock_analysis_service import StockAnalysisService
from stocktrace.bootstrap.container import Container

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


def _quote_handler(container: Container) -> GetStockQuoteQueryHandler:
    return container.quote_query_handler()


def _news_handler(container: Container) -> GetStockNewsQueryHandler:
    return container.news_query_handler()


def _analysis_service(container: Container) -> StockAnalysisService:
    return container.stock_analysis_service()


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/stocks/{ticker}/quote
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{ticker}/quote", response_model=StockQuoteResponse)
async def get_quote(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
) -> StockQuoteResponse:
    """Return the latest market quote for a ticker."""
    try:
        quote = await _quote_handler(container).handle(GetPriceQuery(symbol=ticker))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Quote provider is temporarily unavailable.",
        ) from exc

    if quote is None:
        raise HTTPException(status_code=404, detail=f"Quote not found for {ticker}.")

    return StockQuoteResponse(
        ticker=quote.ticker,
        company_name=quote.company_name,
        current_price=float(quote.current_price),
        change=float(quote.change),
        change_percent=float(quote.change_percent),
        open_price=float(quote.open_price),
        high_price=float(quote.high_price),
        low_price=float(quote.low_price),
        volume=quote.volume,
        timestamp=quote.timestamp,
        currency=quote.currency,
        source=quote.source,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/stocks/{ticker}/news
# Enriched with Gemini AI insights when AI is enabled
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{ticker}/news", response_model=StockNewsResponse)
async def get_news(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    ai: Annotated[bool, Query(description="Include Gemini AI insights")] = True,
) -> StockNewsResponse:
    """Return the latest news articles for a ticker with optional Gemini analysis."""
    try:
        articles = await _news_handler(container).handle(
            GetNewsQuery(symbol=ticker, limit=limit)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="News provider is temporarily unavailable.",
        ) from exc

    normalized = ticker.strip().upper()

    # AI news analysis — only when enabled and requested
    ai_sentiment: str | None = None
    ai_overview: str | None = None
    ai_short_term: str | None = None
    ai_risks: str | None = None

    if ai and articles:
        svc = _analysis_service(container)
        if svc.is_enabled:
            try:
                analysis = await svc.analyze_news(normalized, list(articles))
                if analysis:
                    ai_sentiment = analysis.sentiment.value
                    ai_overview = analysis.overview
                    ai_short_term = analysis.short_term
                    ai_risks = analysis.risks
            except Exception:
                pass  # AI failure must never break the news endpoint

    return StockNewsResponse(
        ticker=normalized,
        articles=[
            StockNewsArticleResponse(
                title=article.title,
                summary=article.summary,
                source=article.source,
                url=article.url,
                published_at=article.published_at,
            )
            for article in articles
        ],
        ai_sentiment=ai_sentiment,
        ai_overview=ai_overview,
        ai_short_term=ai_short_term,
        ai_risks=ai_risks,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/stocks/{ticker}/analysis
# Full Gemini stock analysis: price + news + technical + fundamental → AI
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{ticker}/analysis", response_model=StockAnalysisResponse)
async def get_stock_analysis(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
    mode: Annotated[str, Query(description="'full' or 'news_only'")] = "full",
    news_limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> StockAnalysisResponse:
    """Full Gemini-powered stock analysis combining price, news, technical, and fundamental data.

    - **full** mode: integrates price, historical, technical indicators, fundamentals, and news
    - **news_only** mode: faster, focuses on recent news sentiment (lower cost)
    """
    from stocktrace.ai.models import AnalysisMode  # noqa: PLC0415

    svc = _analysis_service(container)
    if not svc.is_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "AI analysis is not enabled. "
                "Set STOCKTRACE_AI__ENABLED=true and STOCKTRACE_AI__API_KEY in your environment."
            ),
        )

    analysis_mode = AnalysisMode.NEWS_ONLY if mode == "news_only" else AnalysisMode.FULL
    normalized = ticker.strip().upper()

    try:
        bundle = await svc.analyze_symbol(
            normalized,
            mode=analysis_mode,
            news_limit=news_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    if bundle.analysis is None:
        raise HTTPException(
            status_code=503,
            detail="Gemini analysis returned no result. Check your API key and quota.",
        )

    analysis = bundle.analysis
    quote = bundle.quote

    scenarios: AIScenarioSchema | None = None
    if any([analysis.positive_scenario, analysis.neutral_scenario, analysis.negative_scenario]):
        scenarios = AIScenarioSchema(
            positive=analysis.positive_scenario,
            neutral=analysis.neutral_scenario,
            negative=analysis.negative_scenario,
        )

    recommendation: AIRecommendationSchema | None = None
    if any([analysis.recommendation_action, analysis.recommendation_confidence]):
        recommendation = AIRecommendationSchema(
            action=analysis.recommendation_action,
            confidence=analysis.recommendation_confidence,
            reasons=analysis.recommendation_reasons,
        )

    tech_score: float | None = None
    if bundle.score:
        tech_score = float(bundle.score.overall_score)

    return StockAnalysisResponse(
        ticker=normalized,
        company_name=quote.company_name if quote else None,
        current_price=float(quote.current_price) if quote else None,
        change_percent=float(quote.change_percent) if quote else None,
        sentiment=analysis.sentiment.value,
        overview=analysis.overview,
        positives=analysis.positives,
        risks=analysis.risks,
        short_term=analysis.short_term,
        medium_term=analysis.medium_term,
        conclusion=analysis.conclusion,
        scenarios=scenarios,
        recommendation=recommendation,
        technical_score=tech_score,
        news_count=len(bundle.news),
        has_historical_data=len(bundle.historical) > 0,
        generated_at=datetime.now(UTC),
    )
