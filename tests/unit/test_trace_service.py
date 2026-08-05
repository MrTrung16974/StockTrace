"""Trace service fallback behavior tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from stocktrace.application.services.trace.trace_service import TraceService
from stocktrace.domain.entities.financial_snapshot import FinancialDashboardSnapshot
from stocktrace.domain.ports.financial_provider import FinancialProviderUnavailableError

SNAPSHOT_EVENT_COUNT = 2


class EmptyTraceRepository:
    """Trace repository double with no ingested official events."""

    async def list_events(self, **_: Any) -> list[Any]:
        return []


@pytest.mark.asyncio
async def test_trace_uses_saved_financial_snapshot_when_provider_is_unavailable() -> None:
    financial_service = AsyncMock()
    financial_service.analyze.side_effect = FinancialProviderUnavailableError("provider down")
    snapshot_service = AsyncMock()
    snapshot_service.get_latest.return_value = FinancialDashboardSnapshot(
        symbol="HPG",
        period="1Y",
        telegram_html="<b>HPG</b>",
        json_payload={
            "financial_score": 7.5,
            "recommendation": "BUY",
            "valuation": {"status": "FAIR"},
        },
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
    )

    @asynccontextmanager
    async def repository_context():
        yield EmptyTraceRepository()

    service = TraceService(
        repository_context_factory=repository_context,
        financial_analysis_service=cast(Any, financial_service),
        financial_snapshot_service=cast(Any, snapshot_service),
    )

    explanation = await service.explain("HPG")

    assert len(explanation.reasons) == SNAPSHOT_EVENT_COUNT
    assert all("đã lưu HPG" in reason for reason in explanation.reasons)
    snapshot_service.get_latest.assert_awaited_once_with("HPG", "1Y")


@pytest.mark.asyncio
async def test_trace_reports_no_official_record_without_financial_fallback() -> None:
    @asynccontextmanager
    async def repository_context():
        yield EmptyTraceRepository()

    service = TraceService(repository_context_factory=repository_context)

    explanation = await service.explain("HPG")

    assert "Chưa có sự kiện trace chính thức" in explanation.summary
