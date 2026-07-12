"""Trace engine API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from stocktrace.api.dependencies import get_request_container
from stocktrace.api.schemas.trace import (
    TraceEventResponse,
    TraceEventsResponse,
    TraceExplanationResponse,
    TraceReasonResponse,
    TraceScoreResponse,
    TraceSourceResponse,
    TraceTimelineResponse,
)
from stocktrace.application.services.trace import official_trace_sources
from stocktrace.bootstrap.container import Container
from stocktrace.domain.entities.trace import StockTraceEvent

router = APIRouter(prefix="/api/v1/trace", tags=["trace"])


def _event_to_response(event: StockTraceEvent) -> TraceEventResponse:
    return TraceEventResponse(
        symbol=event.symbol,
        event_type=event.event_type.value,
        severity=event.severity.value,
        title=event.title,
        summary=event.summary,
        source_code=event.source.code,
        source_name=event.source.name,
        source_url=event.source_url,
        confidence=float(event.confidence),
        reasons=[
            TraceReasonResponse(
                label=reason.label,
                detail=reason.detail,
                weight=float(reason.weight),
            )
            for reason in event.reasons
        ],
        metadata=event.metadata,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
    )


@router.get("/sources", response_model=list[TraceSourceResponse])
async def list_trace_sources() -> list[TraceSourceResponse]:
    """Return official trace source catalog."""
    return [
        TraceSourceResponse(
            code=source.code,
            name=source.name,
            source_type=source.source_type.value,
            base_url=source.base_url,
            rank=source.rank,
            official=source.official,
            description=source.description,
        )
        for source in official_trace_sources()
    ]


@router.get("/events", response_model=TraceEventsResponse)
async def list_trace_events(
    container: Annotated[Container, Depends(get_request_container)],
    since: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> TraceEventsResponse:
    """Return recent trace events across the market."""
    events = await container.trace_service().list_recent_events(since=since, limit=limit)
    return TraceEventsResponse(events=[_event_to_response(event) for event in events])


@router.get("/{ticker}", response_model=TraceTimelineResponse)
async def get_trace_timeline(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
    since: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> TraceTimelineResponse:
    """Return scored trace timeline for a ticker."""
    timeline = await container.trace_service().build_timeline(
        ticker,
        since=since,
        limit=limit,
    )
    score = timeline.score
    return TraceTimelineResponse(
        symbol=timeline.symbol,
        score=TraceScoreResponse(
            signal_score=float(score.signal_score),
            risk_score=float(score.risk_score),
            conviction_score=float(score.conviction_score),
            change_score=float(score.change_score),
            event_count=score.event_count,
            high_severity_count=score.high_severity_count,
        ),
        events=[_event_to_response(event) for event in timeline.events],
        generated_at=timeline.generated_at,
    )


@router.get("/{ticker}/explain", response_model=TraceExplanationResponse)
async def explain_trace(
    ticker: str,
    container: Annotated[Container, Depends(get_request_container)],
    since: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> TraceExplanationResponse:
    """Explain why a ticker has its current trace profile."""
    explanation = await container.trace_service().explain(ticker, since=since, limit=limit)
    return TraceExplanationResponse(
        symbol=explanation.symbol,
        summary=explanation.summary,
        reasons=list(explanation.reasons),
        risks=list(explanation.risks),
        next_watch=list(explanation.next_watch),
        confidence=float(explanation.confidence),
        generated_at=explanation.generated_at,
    )
