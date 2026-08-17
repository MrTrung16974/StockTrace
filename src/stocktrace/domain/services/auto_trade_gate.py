"""Deterministic, fail-closed gate for a tightly limited auto-trading pilot."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from stocktrace.domain.entities.auto_trade import (
    AutoTradeApprovalRecord,
    AutoTradeApprovalStatus,
    AutoTradeBlockCode,
    AutoTradeGateDecision,
    AutoTradePilotPolicy,
    new_auto_trade_decision_id,
)
from stocktrace.domain.entities.auto_trade_control import AutoTradeControlState
from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft
from stocktrace.domain.entities.pre_trade_risk import PreTradeRiskDecision


class AutoTradeGate:
    """Authorize a pilot candidate only; it never submits an order to any broker."""

    def assess(
        self,
        intent: TradeIntentDraft,
        risk_decision: PreTradeRiskDecision,
        approval: AutoTradeApprovalRecord | None,
        policy: AutoTradePilotPolicy,
        *,
        control_state: AutoTradeControlState | None,
        orders_submitted_today: int,
        notional_submitted_today: Decimal,
        checked_at: datetime,
    ) -> AutoTradeGateDecision:
        """Return all violated controls, preserving an audit-ready decision trace."""
        _require_aware_time(checked_at)
        if orders_submitted_today < 0:
            raise ValueError("orders_submitted_today must not be negative.")
        if notional_submitted_today < 0:
            raise ValueError("notional_submitted_today must not be negative.")

        blocks: list[AutoTradeBlockCode] = []
        _assess_operational_controls(intent, control_state, blocks)
        if not policy.enabled:
            blocks.append(AutoTradeBlockCode.AUTOMATION_DISABLED)
        if (
            not risk_decision.is_approved
            or risk_decision.intent_id != intent.intent_id
            or risk_decision.account_reference != intent.account_reference
        ):
            blocks.append(AutoTradeBlockCode.PRE_TRADE_RISK_NOT_APPROVED)
        _assess_manual_approval(intent, approval, policy, checked_at, blocks)
        _assess_pilot_limits(
            intent,
            policy,
            orders_submitted_today,
            notional_submitted_today,
            blocks,
        )
        return AutoTradeGateDecision.create(
            decision_id=new_auto_trade_decision_id(),
            intent_id=intent.intent_id,
            account_reference=intent.account_reference,
            approval_id=approval.approval_id if approval is not None else None,
            policy_version=policy.policy_version,
            is_authorized=not blocks,
            blocks=tuple(blocks),
            checked_at=checked_at,
        )


def _assess_operational_controls(
    intent: TradeIntentDraft,
    control_state: AutoTradeControlState | None,
    blocks: list[AutoTradeBlockCode],
) -> None:
    if control_state is None:
        blocks.append(AutoTradeBlockCode.CONTROL_STATE_UNAVAILABLE)
        return
    if control_state.kill_switch_active:
        blocks.append(AutoTradeBlockCode.KILL_SWITCH_ACTIVE)
    if not control_state.is_owner_in_rollout(intent.owner_id):
        blocks.append(AutoTradeBlockCode.OWNER_NOT_IN_ROLLOUT)


def _assess_manual_approval(
    intent: TradeIntentDraft,
    approval: AutoTradeApprovalRecord | None,
    policy: AutoTradePilotPolicy,
    checked_at: datetime,
    blocks: list[AutoTradeBlockCode],
) -> None:
    if approval is None:
        blocks.append(AutoTradeBlockCode.APPROVAL_MISSING)
        return
    if approval.owner_id != intent.owner_id:
        blocks.append(AutoTradeBlockCode.APPROVAL_OWNER_MISMATCH)
    if approval.account_reference != intent.account_reference:
        blocks.append(AutoTradeBlockCode.APPROVAL_ACCOUNT_MISMATCH)
    if approval.status is AutoTradeApprovalStatus.REVOKED:
        blocks.append(AutoTradeBlockCode.APPROVAL_REVOKED)
    elif not approval.is_active_at(checked_at):
        blocks.append(AutoTradeBlockCode.APPROVAL_EXPIRED)
    evidence = approval.paper_trading_evidence
    if not evidence.is_stable:
        blocks.append(AutoTradeBlockCode.PAPER_TRADING_UNSTABLE)
    if evidence.observation_duration < policy.minimum_paper_observation:
        blocks.append(AutoTradeBlockCode.PAPER_TRADING_OBSERVATION_TOO_SHORT)
    if evidence.completed_order_count < policy.minimum_paper_completed_orders:
        blocks.append(AutoTradeBlockCode.PAPER_TRADING_ORDER_COUNT_TOO_LOW)


def _assess_pilot_limits(
    intent: TradeIntentDraft,
    policy: AutoTradePilotPolicy,
    orders_submitted_today: int,
    notional_submitted_today: Decimal,
    blocks: list[AutoTradeBlockCode],
) -> None:
    notional = intent.quantity * intent.limit_price
    if intent.symbol not in policy.allowed_symbols:
        blocks.append(AutoTradeBlockCode.SYMBOL_NOT_ALLOWED)
    if notional > policy.max_notional_per_order:
        blocks.append(AutoTradeBlockCode.MAX_ORDER_NOTIONAL_EXCEEDED)
    if orders_submitted_today >= policy.max_orders_per_day:
        blocks.append(AutoTradeBlockCode.DAILY_ORDER_LIMIT_EXCEEDED)
    if notional_submitted_today + notional > policy.max_notional_per_day:
        blocks.append(AutoTradeBlockCode.DAILY_NOTIONAL_LIMIT_EXCEEDED)


def _require_aware_time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("checked_at must be timezone-aware.")
