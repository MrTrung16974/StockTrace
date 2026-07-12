"""Trace engine API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TraceSourceResponse(BaseModel):
    """Trace source metadata response."""

    code: str
    name: str
    source_type: str
    base_url: str
    rank: int
    official: bool
    description: str = ""


class TraceReasonResponse(BaseModel):
    """Trace reason response."""

    label: str
    detail: str
    weight: float


class TraceEventResponse(BaseModel):
    """Normalized trace event response."""

    symbol: str | None
    event_type: str
    severity: str
    title: str
    summary: str
    source_code: str
    source_name: str
    source_url: str
    confidence: float = Field(ge=0, le=1)
    reasons: list[TraceReasonResponse]
    metadata: dict[str, str]
    occurred_at: datetime | None = None
    created_at: datetime


class TraceScoreResponse(BaseModel):
    """Trace score response."""

    signal_score: float
    risk_score: float
    conviction_score: float
    change_score: float
    event_count: int
    high_severity_count: int


class TraceTimelineResponse(BaseModel):
    """Trace timeline response."""

    symbol: str
    score: TraceScoreResponse
    events: list[TraceEventResponse]
    generated_at: datetime


class TraceExplanationResponse(BaseModel):
    """Trace explanation response."""

    symbol: str
    summary: str
    reasons: list[str]
    risks: list[str]
    next_watch: list[str]
    confidence: float
    generated_at: datetime


class TraceEventsResponse(BaseModel):
    """Recent trace events response."""

    events: list[TraceEventResponse]
