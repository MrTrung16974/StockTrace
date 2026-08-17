"""Tests for Phase-16 kill-switch and rollout control-plane safeguards."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from stocktrace.application.services.auto_trade_control import AutoTradeControlService
from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState
from stocktrace.infrastructure.paper_trading.in_memory_auto_trade_control_repository import (
    InMemoryAutoTradeControlRepository,
)

NOW = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_missing_control_state_fails_closed_and_kill_switch_is_immediate() -> None:
    repository = InMemoryAutoTradeControlRepository()
    service = AutoTradeControlService(repository)

    initial = await service.get_state(now=NOW)
    stopped = await service.activate_kill_switch(
        reason="reconciliation discrepancy",
        authorized_operator_id="risk-operator-1",
        activated_at=NOW,
    )

    assert initial.kill_switch_active is True
    assert stopped.kill_switch_active is True
    assert stopped.kill_switch_reason == "reconciliation discrepancy"
    assert await repository.get() == stopped


def test_rollout_is_stable_for_each_owner_and_explicit_pilot_owner_is_always_included() -> None:
    state = AutoTradeControlState(
        state_id="control-1",
        kill_switch_active=False,
        rollout_percentage=0,
        rollout_owner_ids=("pilot-owner",),
        updated_by="risk-operator-1",
        updated_at=NOW,
    )

    assert state.is_owner_in_rollout("pilot-owner") is True
    assert state.is_owner_in_rollout("other-owner") is False
    assert state.is_owner_in_rollout("other-owner") is state.is_owner_in_rollout("other-owner")
