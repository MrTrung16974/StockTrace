"""Integration tests for persisted financial dashboard snapshots."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
)
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.config import DatabaseSettings
from stocktrace.infrastructure.db.base import Base
from stocktrace.infrastructure.db.models.financial import FinancialAnalysisModel
from stocktrace.infrastructure.db.repositories import (
    SqlAlchemyFinancialDashboardSnapshotRepository,
)
from stocktrace.infrastructure.db.session import SessionManager
from stocktrace.infrastructure.providers.financial.mock_provider import MockFinancialProvider


@pytest.mark.asyncio
async def test_snapshot_repository_persists_financial_dashboard() -> None:
    manager = SessionManager(DatabaseSettings(url="sqlite+aiosqlite:///:memory:"))
    async with manager.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    dashboard = await FinancialAnalysisService(
        financial_provider=MockFinancialProvider(),
    ).analyze("HPG", FinancialPeriod.parse("1Y"))

    async with manager.session() as session:
        repository = SqlAlchemyFinancialDashboardSnapshotRepository(session=session)
        await repository.save_dashboard(dashboard)

    async with manager.session() as session:
        repository = SqlAlchemyFinancialDashboardSnapshotRepository(session=session)
        row = (
            await session.execute(
                select(FinancialAnalysisModel).where(FinancialAnalysisModel.symbol == "HPG")
            )
        ).scalar_one()
        snapshot = await repository.get_latest_dashboard(symbol="HPG", period="1Y")

    await manager.dispose()

    payload = json.loads(row.analysis_json)
    assert row.period == "1Y"
    assert row.recommendation == dashboard.analysis.score.recommendation.value
    assert row.confidence == dashboard.json_payload["confidence"]
    assert payload["dashboard"]["symbol"] == "HPG"
    assert payload["telegram_html"] == dashboard.telegram_html
    assert snapshot is not None
    assert snapshot.symbol == "HPG"
    assert snapshot.period == "1Y"
    assert snapshot.telegram_html == dashboard.telegram_html
    assert snapshot.json_payload == dashboard.json_payload
