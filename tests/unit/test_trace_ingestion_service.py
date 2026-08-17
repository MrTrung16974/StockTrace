"""Tests for persisting official trace events."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from stocktrace.application.services.trace.ingestion_service import (
    OfficialTraceIngestionService,
    OfficialTraceIngestionUnavailableError,
)
from stocktrace.application.services.trace.source_catalog import official_trace_sources
from stocktrace.domain.entities.trace import StockTraceEvent, TraceEventType, TraceSeverity


@pytest.mark.asyncio
async def test_ingestion_service_persists_events_from_each_available_provider() -> None:
    event = StockTraceEvent(
        symbol="HPG",
        event_type=TraceEventType.TRACE_DISCLOSURE,
        severity=TraceSeverity.INFO,
        title="HPG disclosure",
        summary="Official disclosure",
        source=official_trace_sources()[1],
        confidence=Decimal("1"),
    )
    trace_service = AsyncMock()
    provider = AsyncMock()
    provider.provider_name = "official-provider"
    provider.list_events.return_value = [event]
    service = OfficialTraceIngestionService(trace_service=trace_service, providers=[provider])

    saved = await service.ingest_symbol("HPG", limit=20)

    assert saved == 1
    provider.list_events.assert_awaited_once_with(symbol="HPG", limit=20)
    trace_service.save_event.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_ingestion_service_raises_when_all_official_providers_are_unavailable() -> None:
    trace_service = AsyncMock()
    provider = AsyncMock()
    provider.provider_name = "official-provider"
    provider.list_events.side_effect = RuntimeError("network unavailable")
    service = OfficialTraceIngestionService(trace_service=trace_service, providers=[provider])

    with pytest.raises(OfficialTraceIngestionUnavailableError, match="official-provider"):
        await service.ingest_symbol("HPG", limit=20)

    trace_service.save_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingestion_service_does_not_hide_database_write_failures() -> None:
    event = StockTraceEvent(
        symbol="HPG",
        event_type=TraceEventType.TRACE_DISCLOSURE,
        severity=TraceSeverity.INFO,
        title="HPG disclosure",
        summary="Official disclosure",
        source=official_trace_sources()[1],
        confidence=Decimal("1"),
    )
    trace_service = AsyncMock()
    trace_service.save_event.side_effect = RuntimeError("trace_events table missing")
    provider = AsyncMock()
    provider.provider_name = "official-provider"
    provider.list_events.return_value = [event]
    service = OfficialTraceIngestionService(trace_service=trace_service, providers=[provider])

    with pytest.raises(RuntimeError, match="trace_events table missing"):
        await service.ingest_symbol("HPG", limit=20)

    provider.list_events.assert_awaited_once_with(symbol="HPG", limit=20)
    trace_service.save_event.assert_awaited_once_with(event)
