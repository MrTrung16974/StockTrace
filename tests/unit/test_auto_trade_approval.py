"""Tests for explicit manual approval records used by the auto-trade pilot gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from stocktrace.application.services.auto_trade_approval import (
    AutoTradeApprovalAlreadyActiveError,
    AutoTradeApprovalService,
)
from stocktrace.domain.entities.auto_trade import (
    AutoTradeApprovalStatus,
    PaperTradingReadinessEvidence,
)
from stocktrace.infrastructure.paper_trading.in_memory_auto_trade_approval_repository import (
    InMemoryAutoTradeApprovalRepository,
)

NOW = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)


def _evidence() -> PaperTradingReadinessEvidence:
    return PaperTradingReadinessEvidence(
        evidence_id="paper-observation-1",
        owner_id="owner-1",
        account_reference="paper-1",
        observation_started_at=NOW - timedelta(days=30),
        observation_ended_at=NOW,
        completed_order_count=20,
        is_stable=True,
    )


@pytest.mark.asyncio
async def test_manual_approval_is_required_and_can_be_revoked_immediately() -> None:
    repository = InMemoryAutoTradeApprovalRepository()
    service = AutoTradeApprovalService(repository)

    approval = await service.approve(
        owner_id="owner-1",
        account_reference="paper-1",
        authorized_approver_id="risk-officer-1",
        paper_trading_evidence=_evidence(),
        approved_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )
    revoked = await service.revoke(approval.approval_id, revoked_at=NOW)

    assert approval.status is AutoTradeApprovalStatus.ACTIVE
    assert revoked.status is AutoTradeApprovalStatus.REVOKED
    assert revoked.is_active_at(NOW) is False


@pytest.mark.asyncio
async def test_manual_approval_cannot_be_duplicated_for_an_active_pilot() -> None:
    service = AutoTradeApprovalService(InMemoryAutoTradeApprovalRepository())
    await service.approve(
        owner_id="owner-1",
        account_reference="paper-1",
        authorized_approver_id="risk-officer-1",
        paper_trading_evidence=_evidence(),
        approved_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )

    with pytest.raises(AutoTradeApprovalAlreadyActiveError):
        await service.approve(
            owner_id="owner-1",
            account_reference="paper-1",
            authorized_approver_id="risk-officer-1",
            paper_trading_evidence=_evidence(),
            approved_at=NOW,
            expires_at=NOW + timedelta(days=1),
        )
