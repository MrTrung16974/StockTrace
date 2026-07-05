"""Financial analysis API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from stocktrace.api.dependencies import get_request_container
from stocktrace.api.schemas.financial import (
    AISummarySchema,
    ChartPointSchema,
    ChartSchema,
    ChartSeriesSchema,
    FinancialCompareResponse,
    FinancialDashboardResponse,
    FinancialScoresSchema,
    SignalSchema,
    ValuationSchema,
)
from stocktrace.application.queries.financial_queries import (
    CompareFinancialQuery,
    GetFinancialAnalysisQuery,
    GetFinancialReportQuery,
    GetFinancialScoreQuery,
    GetValuationQuery,
)
from stocktrace.bootstrap.container import Container
from stocktrace.domain.entities.financial import FinancialDashboard
from stocktrace.domain.ports.financial_provider import FinancialDataNotFoundError

router = APIRouter(prefix="/api/v1/financial", tags=["financial"])


def _dashboard_to_response(dashboard: FinancialDashboard) -> FinancialDashboardResponse:
    """Map domain dashboard to API response."""
    analysis = dashboard.analysis
    score = analysis.score
    payload = dashboard.json_payload

    ai_summary = None
    if analysis.ai_analysis:
        ai = analysis.ai_analysis
        ai_summary = AISummarySchema(
            executive_summary=ai.executive_summary,
            strengths=list(ai.strengths),
            weaknesses=list(ai.weaknesses),
            risks=list(ai.risks),
            recommendation=ai.recommendation.value,
            confidence=float(ai.confidence),
            target_price=float(ai.target_price) if ai.target_price else None,
        )

    charts = [
        ChartSchema(
            id=c["id"],
            type=c["type"],
            title=c["title"],
            series=[
                ChartSeriesSchema(
                    name=s["name"],
                    unit=s.get("unit", ""),
                    points=[ChartPointSchema(label=p["label"], value=p["value"]) for p in s["points"]],
                )
                for s in c["series"]
            ],
        )
        for c in payload.get("charts", [])
    ]

    scores_data = payload.get("scores", {})
    val_data = payload.get("valuation", {})

    return FinancialDashboardResponse(
        symbol=analysis.symbol,
        company_name=analysis.company_name,
        period_start=analysis.period_start,
        period_end=analysis.period_end,
        period_label=analysis.period_label,
        recommendation=score.recommendation.value,
        confidence=payload.get("confidence", 75),
        financial_score=float(score.overall_score),
        scores=FinancialScoresSchema(
            growth=scores_data.get("growth", 0),
            profitability=scores_data.get("profitability", 0),
            debt=scores_data.get("debt", 0),
            cash_flow=scores_data.get("cash_flow", 0),
            valuation=scores_data.get("valuation", 0),
        ),
        valuation=ValuationSchema(
            current_pe=val_data.get("current_pe"),
            average_pe=val_data.get("average_pe"),
            status=val_data.get("status", "FAIR"),
            target_price=val_data.get("target_price"),
        ),
        charts=charts,
        signals=[
            SignalSchema(
                type=s["type"],
                level=s["level"],
                label=s["label"],
                reasons=s["reasons"],
            )
            for s in payload.get("signals", [])
        ],
        ai_summary=ai_summary,
        generated_at=analysis.generated_at,
    )


@router.get("/{ticker}/analysis", response_model=FinancialDashboardResponse)
async def get_financial_analysis(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
    period: Annotated[str, Query(description="Analysis period e.g. 6M, 1Y, 3Y")] = "1Y",
) -> FinancialDashboardResponse:
    """Return visual financial analysis dashboard for a ticker."""
    try:
        dashboard = await container.financial_analysis_handler().handle(
            GetFinancialAnalysisQuery(symbol=ticker, period=period),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FinancialDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _dashboard_to_response(dashboard)


@router.get("/{ticker}/report", response_model=FinancialDashboardResponse)
async def get_financial_report(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
) -> FinancialDashboardResponse:
    """Return financial report (1Y default)."""
    try:
        dashboard = await container.financial_report_handler().handle(
            GetFinancialReportQuery(symbol=ticker),
        )
    except FinancialDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _dashboard_to_response(dashboard)


@router.get("/{ticker}/valuation", response_model=FinancialDashboardResponse)
async def get_valuation(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
) -> FinancialDashboardResponse:
    """Return valuation analysis."""
    try:
        dashboard = await container.financial_valuation_handler().handle(
            GetValuationQuery(symbol=ticker),
        )
    except FinancialDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _dashboard_to_response(dashboard)


@router.get("/{ticker}/score", response_model=FinancialDashboardResponse)
async def get_financial_score(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
    period: Annotated[str, Query()] = "1Y",
) -> FinancialDashboardResponse:
    """Return financial health score."""
    try:
        dashboard = await container.financial_score_handler().handle(
            GetFinancialScoreQuery(symbol=ticker, period=period),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FinancialDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _dashboard_to_response(dashboard)


@router.get("/compare/{ticker_a}/{ticker_b}", response_model=FinancialCompareResponse)
async def compare_financial(
    ticker_a: str,
    ticker_b: str,
    container: Annotated[Container, Depends(get_request_container)],
    period: Annotated[str, Query()] = "1Y",
) -> FinancialCompareResponse:
    """Compare financial health of two tickers."""
    try:
        result = await container.financial_compare_handler().handle(
            CompareFinancialQuery(symbol_a=ticker_a, symbol_b=ticker_b, period=period),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FinancialDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FinancialCompareResponse(
        symbol_a=_dashboard_to_response(result.symbol_a),
        symbol_b=_dashboard_to_response(result.symbol_b),
        winner=result.winner,
        comparison_summary=result.comparison_summary,
    )
