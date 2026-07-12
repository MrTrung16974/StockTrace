"""Unit tests for trace scoring engine."""

from __future__ import annotations

from decimal import Decimal

from stocktrace.application.services.trace import TraceScoringEngine, official_trace_sources
from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceEventType,
    TraceSeverity,
)


def test_empty_trace_score_is_neutral() -> None:
    score = TraceScoringEngine().calculate("FPT", ())

    assert score.signal_score == Decimal("0")
    assert score.risk_score == Decimal("0")
    assert score.conviction_score == Decimal("0")
    assert score.event_count == 0


def test_official_high_severity_events_raise_signal_and_risk() -> None:
    source = official_trace_sources()[0]
    events = (
        StockTraceEvent(
            symbol="FPT",
            event_type=TraceEventType.TRACE_DISCLOSURE,
            severity=TraceSeverity.HIGH,
            title="Disclosure",
            summary="Important issuer disclosure.",
            source=source,
            confidence=Decimal("1"),
        ),
    )

    score = TraceScoringEngine().calculate("FPT", events)

    assert score.signal_score == Decimal("80.00")
    assert score.risk_score == Decimal("80.00")
    assert score.conviction_score == Decimal("100.00")
    assert score.high_severity_count == 1
