"""SQLAlchemy persistence for financial dashboard snapshots."""

from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stocktrace.domain.entities.financial import FinancialDashboard
from stocktrace.domain.entities.financial_snapshot import FinancialDashboardSnapshot
from stocktrace.infrastructure.db.models.financial import FinancialAnalysisModel


class SqlAlchemyFinancialDashboardSnapshotRepository:
    """Store the latest rendered financial analysis payload for later fallback use."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_dashboard(self, dashboard: FinancialDashboard) -> None:
        analysis = dashboard.analysis
        payload = {
            "dashboard": dashboard.json_payload,
            "telegram_html": dashboard.telegram_html,
        }
        self._session.add(
            FinancialAnalysisModel(
                id=str(uuid4()),
                symbol=analysis.symbol,
                period=analysis.period_label,
                analysis_json=json.dumps(payload, ensure_ascii=False),
                recommendation=analysis.score.recommendation.value,
                confidence=float(dashboard.json_payload["confidence"]),
            ),
        )
        await self._session.flush()

    async def get_latest_dashboard(
        self,
        symbol: str,
        period: str,
    ) -> FinancialDashboardSnapshot | None:
        """Retrieve a previously delivered dashboard for provider-outage fallback."""
        statement = (
            select(FinancialAnalysisModel)
            .where(
                FinancialAnalysisModel.symbol == symbol,
                FinancialAnalysisModel.period == period,
            )
            .order_by(FinancialAnalysisModel.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        if row is None:
            return None

        payload = json.loads(row.analysis_json)
        return FinancialDashboardSnapshot(
            symbol=row.symbol,
            period=row.period,
            telegram_html=payload["telegram_html"],
            json_payload=payload["dashboard"],
            created_at=row.created_at,
        )
