"""Trace engine domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class TraceSourceType(StrEnum):
    """Official and supporting trace data source groups."""

    EXCHANGE = "EXCHANGE"
    DISCLOSURE = "DISCLOSURE"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    REGULATORY = "REGULATORY"
    MACRO = "MACRO"
    COMPANY_IR = "COMPANY_IR"
    THIRD_PARTY = "THIRD_PARTY"


class TraceEventType(StrEnum):
    """Supported stock trace event types."""

    TRACE_PRICE = "TRACE_PRICE"
    TRACE_VOLUME = "TRACE_VOLUME"
    TRACE_DISCLOSURE = "TRACE_DISCLOSURE"
    TRACE_FINANCIAL_STATEMENT = "TRACE_FINANCIAL_STATEMENT"
    TRACE_CORPORATE_ACTION = "TRACE_CORPORATE_ACTION"
    TRACE_FOREIGN_OWNERSHIP = "TRACE_FOREIGN_OWNERSHIP"
    TRACE_REGULATORY = "TRACE_REGULATORY"
    TRACE_ENFORCEMENT = "TRACE_ENFORCEMENT"
    TRACE_MACRO_RATE = "TRACE_MACRO_RATE"
    TRACE_FX = "TRACE_FX"
    TRACE_SECTOR = "TRACE_SECTOR"
    TRACE_MARKET_STRUCTURE = "TRACE_MARKET_STRUCTURE"


class TraceSeverity(StrEnum):
    """Business impact level of a trace event."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class TraceSource:
    """Metadata for a source used by the trace engine."""

    code: str
    name: str
    source_type: TraceSourceType
    base_url: str
    rank: int
    official: bool
    description: str = ""


@dataclass(frozen=True, slots=True)
class TraceDocument:
    """Source document or web page that supports one or more trace events."""

    source_code: str
    title: str
    url: str
    published_at: datetime | None = None
    fetched_at: datetime = field(default_factory=datetime.now)
    checksum: str | None = None
    content_type: str | None = None
    raw_text: str | None = None


@dataclass(frozen=True, slots=True)
class TraceReason:
    """Structured reason explaining why a trace event matters."""

    label: str
    detail: str
    weight: Decimal = Decimal("1")


@dataclass(frozen=True, slots=True)
class StockTraceEvent:
    """A normalized market, disclosure, regulatory, or macro trace event."""

    symbol: str | None
    event_type: TraceEventType
    severity: TraceSeverity
    title: str
    summary: str
    source: TraceSource
    document: TraceDocument | None = None
    reasons: tuple[TraceReason, ...] = ()
    confidence: Decimal = Decimal("1")
    occurred_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def source_url(self) -> str:
        """Return the most specific URL attached to the event."""
        if self.document is not None:
            return self.document.url
        return self.source.base_url


@dataclass(frozen=True, slots=True)
class TraceScore:
    """Deterministic score summary for a symbol's trace events."""

    symbol: str
    signal_score: Decimal
    risk_score: Decimal
    conviction_score: Decimal
    change_score: Decimal
    event_count: int
    high_severity_count: int


@dataclass(frozen=True, slots=True)
class TraceTimeline:
    """Trace timeline and score for a symbol."""

    symbol: str
    events: tuple[StockTraceEvent, ...]
    score: TraceScore
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, slots=True)
class TraceExplanation:
    """Human-readable deterministic explanation of a trace timeline."""

    symbol: str
    summary: str
    reasons: tuple[str, ...]
    risks: tuple[str, ...]
    next_watch: tuple[str, ...]
    confidence: Decimal
    generated_at: datetime = field(default_factory=datetime.now)
