"""Tests for the Phase-14 fail-closed limited auto-trading pilot gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from stocktrace.domain.entities.auto_trade import (
    AutoTradeApprovalRecord,
    AutoTradeBlockCode,
    AutoTradeGateDecision,
    AutoTradePilotPolicy,
    PaperTradingReadinessEvidence,
)
from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState
from stocktrace.domain.entities.investment_suggestion import (
    SuggestionAction,
    TradeIntentDraft,
    TradeSide,
)
from stocktrace.domain.entities.paper_trading import PaperAccountSnapshot
from stocktrace.domain.entities.pre_trade_risk import PreTradeRiskDecision, RiskPolicy
from stocktrace.domain.services.auto_trade_gate import AutoTradeGate
from stocktrace.domain.services.pre_trade_risk import PreTradeRiskEngine

NOW = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)


def _active_control(*, rollout_owner_ids: tuple[str, ...] = ("owner-1",)) -> AutoTradeControlState:
    return AutoTradeControlState(
        state_id="control-1",
        kill_switch_active=False,
        rollout_percentage=0,
        rollout_owner_ids=rollout_owner_ids,
        updated_by="risk-operator-1",
        updated_at=NOW,
    )


def _intent(*, symbol: str = "HPG", quantity: int = 20) -> TradeIntentDraft:
    return TradeIntentDraft(
        owner_id="owner-1",
        account_reference="paper-1",
        suggestion_id="suggestion-1",
        symbol=symbol,
        suggestion_action=SuggestionAction.ACCUMULATE_CONDITIONALLY,
        side=TradeSide.BUY,
        quantity=quantity,
        limit_price=Decimal("25000"),
        created_at=NOW,
        intent_id="intent-1",
    )


def _risk_decision(intent: TradeIntentDraft) -> PreTradeRiskDecision:
    return PreTradeRiskEngine().assess(
        intent,
        PaperAccountSnapshot("paper-1", "owner-1", Decimal("3000000")),
        orders_submitted_today=0,
        policy=RiskPolicy(100, Decimal("3000000"), 2, "risk-v1"),
        checked_at=NOW,
    )


def _policy(*, enabled: bool = True) -> AutoTradePilotPolicy:
    return AutoTradePilotPolicy(
        enabled=enabled,
        allowed_symbols=("HPG",),
        max_notional_per_order=Decimal("500000"),
        max_notional_per_day=Decimal("1000000"),
        max_orders_per_day=1,
        minimum_paper_observation=timedelta(days=30),
        minimum_paper_completed_orders=20,
        policy_version="pilot-v1",
    )


def _approval(*, expires_at: datetime = NOW + timedelta(days=1)) -> AutoTradeApprovalRecord:
    return AutoTradeApprovalRecord(
        approval_id="approval-1",
        owner_id="owner-1",
        account_reference="paper-1",
        approved_by="risk-officer-1",
        approved_at=NOW,
        expires_at=expires_at,
        paper_trading_evidence=PaperTradingReadinessEvidence(
            evidence_id="evidence-1",
            owner_id="owner-1",
            account_reference="paper-1",
            observation_started_at=NOW - timedelta(days=30),
            observation_ended_at=NOW,
            completed_order_count=20,
            is_stable=True,
        ),
    )


def _assess(
    *,
    intent: TradeIntentDraft | None = None,
    approval: AutoTradeApprovalRecord | None = None,
    policy: AutoTradePilotPolicy | None = None,
    orders_submitted_today: int = 0,
    notional_submitted_today: Decimal = Decimal("0"),
    checked_at: datetime = NOW,
    control_state: AutoTradeControlState | None = None,
) -> AutoTradeGateDecision:
    draft = intent or _intent()
    return AutoTradeGate().assess(
        draft,
        _risk_decision(draft),
        approval,
        policy or _policy(),
        control_state=control_state or _active_control(),
        orders_submitted_today=orders_submitted_today,
        notional_submitted_today=notional_submitted_today,
        checked_at=checked_at,
    )


def test_auto_trade_requires_both_config_and_a_separate_manual_approval() -> None:
    config_disabled = _assess(approval=_approval(), policy=_policy(enabled=False))
    approval_missing = _assess(approval=None)

    assert config_disabled.is_authorized is False
    assert AutoTradeBlockCode.AUTOMATION_DISABLED in config_disabled.blocks
    assert approval_missing.is_authorized is False
    assert AutoTradeBlockCode.APPROVAL_MISSING in approval_missing.blocks


def test_auto_trade_authorizes_only_a_stable_paper_pilot_inside_every_limit() -> None:
    decision = _assess(approval=_approval())

    assert decision.is_authorized is True
    assert decision.blocks == ()
    assert decision.approval_id == "approval-1"
    assert decision.has_valid_checksum() is True


@pytest.mark.parametrize(
    ("intent", "orders", "daily_notional", "expected"),
    [
        (_intent(symbol="FPT"), 0, Decimal("0"), AutoTradeBlockCode.SYMBOL_NOT_ALLOWED),
        (_intent(quantity=21), 0, Decimal("0"), AutoTradeBlockCode.MAX_ORDER_NOTIONAL_EXCEEDED),
        (_intent(), 1, Decimal("0"), AutoTradeBlockCode.DAILY_ORDER_LIMIT_EXCEEDED),
        (_intent(), 0, Decimal("600000"), AutoTradeBlockCode.DAILY_NOTIONAL_LIMIT_EXCEEDED),
    ],
)
def test_auto_trade_blocks_each_pilot_limit(
    intent: TradeIntentDraft,
    orders: int,
    daily_notional: Decimal,
    expected: AutoTradeBlockCode,
) -> None:
    decision = _assess(
        intent=intent,
        approval=_approval(),
        orders_submitted_today=orders,
        notional_submitted_today=daily_notional,
    )

    assert decision.is_authorized is False
    assert expected in decision.blocks


def test_auto_trade_blocks_expired_or_insufficient_paper_evidence() -> None:
    expired = _assess(
        approval=_approval(expires_at=NOW + timedelta(minutes=1)),
        checked_at=NOW + timedelta(minutes=1),
    )
    insufficient = AutoTradeApprovalRecord(
        approval_id="approval-2",
        owner_id="owner-1",
        account_reference="paper-1",
        approved_by="risk-officer-1",
        approved_at=NOW,
        expires_at=NOW + timedelta(days=1),
        paper_trading_evidence=PaperTradingReadinessEvidence(
            evidence_id="evidence-2",
            owner_id="owner-1",
            account_reference="paper-1",
            observation_started_at=NOW - timedelta(days=2),
            observation_ended_at=NOW,
            completed_order_count=1,
            is_stable=False,
        ),
    )
    insufficient_decision = _assess(approval=insufficient)

    assert AutoTradeBlockCode.APPROVAL_EXPIRED in expired.blocks
    assert AutoTradeBlockCode.PAPER_TRADING_UNSTABLE in insufficient_decision.blocks
    assert AutoTradeBlockCode.PAPER_TRADING_OBSERVATION_TOO_SHORT in insufficient_decision.blocks
    assert AutoTradeBlockCode.PAPER_TRADING_ORDER_COUNT_TOO_LOW in insufficient_decision.blocks


def test_auto_trade_kill_switch_or_rollout_miss_overrides_all_other_authorization() -> None:
    killed = _active_control()
    killed = killed.activate_kill_switch(
        reason="operator emergency stop",
        updated_by="risk-operator-1",
        updated_at=NOW,
    )
    rollout_miss = _active_control(rollout_owner_ids=())

    killed_decision = _assess(approval=_approval(), control_state=killed)
    rollout_decision = _assess(approval=_approval(), control_state=rollout_miss)

    assert AutoTradeBlockCode.KILL_SWITCH_ACTIVE in killed_decision.blocks
    assert AutoTradeBlockCode.OWNER_NOT_IN_ROLLOUT in rollout_decision.blocks
