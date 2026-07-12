"""Unit tests for trace source catalog."""

from __future__ import annotations

from decimal import Decimal

from stocktrace.application.services.trace import official_trace_sources
from stocktrace.domain.entities.trace import (
    StockTraceEvent,
    TraceEventType,
    TraceSeverity,
)


def test_official_trace_sources_are_ranked_source_of_truth() -> None:
    sources = official_trace_sources()

    assert {source.code for source in sources} >= {
        "VNX",
        "HOSE",
        "HNX",
        "SSC",
        "VSDC",
        "SBV",
        "GSO",
        "MOF",
    }
    assert all(source.rank == 1 for source in sources)
    assert all(source.official for source in sources)


def test_trace_event_prefers_document_url() -> None:
    source = official_trace_sources()[0]
    event = StockTraceEvent(
        symbol="FPT",
        event_type=TraceEventType.TRACE_DISCLOSURE,
        severity=TraceSeverity.INFO,
        title="FPT disclosure",
        summary="Issuer disclosure published.",
        source=source,
        confidence=Decimal("1"),
    )

    assert event.source_url == source.base_url
