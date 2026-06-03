"""Stock quote and news API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from stocktrace.api.dependencies import get_request_container
from stocktrace.api.schemas.stocks import (
    StockNewsArticleResponse,
    StockNewsResponse,
    StockQuoteResponse,
)
from stocktrace.application.queries.stock_handlers import (
    GetStockNewsQueryHandler,
    GetStockQuoteQueryHandler,
)
from stocktrace.application.queries.stock_queries import GetNewsQuery, GetPriceQuery
from stocktrace.bootstrap.container import Container

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


def _quote_handler(container: Container) -> GetStockQuoteQueryHandler:
    return container.quote_query_handler()


def _news_handler(container: Container) -> GetStockNewsQueryHandler:
    return container.news_query_handler()


@router.get("/{ticker}/quote", response_model=StockQuoteResponse)
async def get_quote(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
) -> StockQuoteResponse:
    """Return the latest quote for a ticker."""
    try:
        quote = await _quote_handler(container).handle(GetPriceQuery(symbol=ticker))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@router.get("/{ticker}/news", response_model=StockNewsResponse)
async def get_news(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> StockNewsResponse:
    """Return the latest news articles for a ticker."""
    try:
        articles = await _news_handler(container).handle(GetNewsQuery(symbol=ticker, limit=limit))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StockNewsResponse(
        ticker=ticker.strip().upper(),
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
    )
