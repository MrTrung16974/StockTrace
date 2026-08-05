"""Tests for last-known-good financial dashboard lookup."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from stocktrace.application.services.financial.snapshot_service import FinancialSnapshotService
from stocktrace.domain.entities.financial_snapshot import FinancialDashboardSnapshot


class FakeFinancialSnapshotRepository:
    """Repository double returning a preconfigured snapshot."""

    def __init__(self, snapshot: FinancialDashboardSnapshot | None) -> None:
        self.snapshot = snapshot
        self.queries: list[tuple[str, str]] = []

    async def get_latest_dashboard(
        self,
        symbol: str,
        period: str,
    ) -> FinancialDashboardSnapshot | None:
        self.queries.append((symbol, period))
        return self.snapshot


@pytest.mark.asyncio
async def test_snapshot_service_returns_matching_last_known_good_dashboard() -> None:
    snapshot = FinancialDashboardSnapshot(
        symbol="HPG",
        period="1Y",
        telegram_html="<b>HPG</b>",
        json_payload={"symbol": "HPG"},
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
    )
    repository = FakeFinancialSnapshotRepository(snapshot)

    @asynccontextmanager
    async def repository_context():
        yield repository

    service = FinancialSnapshotService(repository_context_factory=repository_context)

    result = await service.get_latest(symbol="HPG", period="1Y")

    assert result == snapshot
    assert repository.queries == [("HPG", "1Y")]
