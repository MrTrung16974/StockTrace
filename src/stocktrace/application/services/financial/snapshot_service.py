"""Lookup service for persisted financial dashboard snapshots."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from stocktrace.domain.entities.financial_snapshot import FinancialDashboardSnapshot
from stocktrace.domain.repositories.financial import FinancialDashboardSnapshotRepository


class FinancialSnapshotService:
    """Retrieve a last-known-good dashboard during a provider outage."""

    def __init__(
        self,
        repository_context_factory: Callable[
            [], AbstractAsyncContextManager[FinancialDashboardSnapshotRepository]
        ],
    ) -> None:
        self._repository_context_factory = repository_context_factory

    async def get_latest(
        self,
        symbol: str,
        period: str,
    ) -> FinancialDashboardSnapshot | None:
        """Return a matching snapshot, if a successful job has stored one."""
        async with self._repository_context_factory() as repository:
            return await repository.get_latest_dashboard(symbol=symbol, period=period)
