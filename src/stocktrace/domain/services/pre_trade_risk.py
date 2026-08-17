"""Deterministic, fail-closed pre-trade risk checks."""

from __future__ import annotations

from datetime import datetime

from stocktrace.domain.entities.investment_suggestion import TradeIntentDraft, TradeSide
from stocktrace.domain.entities.paper_trading import PaperAccountSnapshot
from stocktrace.domain.entities.pre_trade_risk import (
    PreTradeRiskDecision,
    RiskControlCode,
    RiskPolicy,
    RiskViolation,
)


class PreTradeRiskEngine:
    """Evaluate deterministic size, exposure, count, cash, and position controls."""

    def assess(
        self,
        intent: TradeIntentDraft,
        account: PaperAccountSnapshot | None,
        *,
        orders_submitted_today: int,
        policy: RiskPolicy,
        checked_at: datetime,
    ) -> PreTradeRiskDecision:
        """Return one explicit approval/rejection without changing account state."""
        _require_aware_time(checked_at)
        if orders_submitted_today < 0:
            raise ValueError("orders_submitted_today must not be negative.")

        violations: list[RiskViolation] = []
        notional = intent.limit_price * intent.quantity
        if intent.quantity > policy.max_quantity_per_order:
            violations.append(
                _violation(
                    RiskControlCode.MAX_QUANTITY_EXCEEDED,
                    "Draft quantity exceeds the maximum quantity per order.",
                ),
            )
        if notional > policy.max_notional_per_order:
            violations.append(
                _violation(
                    RiskControlCode.MAX_NOTIONAL_EXCEEDED,
                    "Draft notional exceeds the maximum notional per order.",
                ),
            )
        if orders_submitted_today >= policy.max_orders_per_day:
            violations.append(
                _violation(
                    RiskControlCode.DAILY_ORDER_LIMIT_EXCEEDED,
                    "Daily order limit has already been reached.",
                ),
            )
        if account is None:
            violations.append(
                _violation(
                    RiskControlCode.ACCOUNT_UNAVAILABLE,
                    "Account state is unavailable; risk checks fail closed.",
                ),
            )
        elif account.owner_id != intent.owner_id:
            violations.append(
                _violation(
                    RiskControlCode.ACCOUNT_OWNER_MISMATCH,
                    "Draft owner does not match account owner.",
                ),
            )
        elif intent.side is TradeSide.BUY and account.cash_balance < notional:
            violations.append(
                _violation(
                    RiskControlCode.INSUFFICIENT_CASH,
                    "Account cash balance is insufficient for the draft notional.",
                ),
            )
        elif (
            intent.side is TradeSide.SELL
            and _position_quantity(account, intent.symbol) < intent.quantity
        ):
            violations.append(
                _violation(
                    RiskControlCode.INSUFFICIENT_POSITION,
                    "Account position is insufficient for the draft quantity.",
                ),
            )
        return PreTradeRiskDecision(
            intent_id=intent.intent_id,
            account_reference=intent.account_reference,
            is_approved=not violations,
            violations=tuple(violations),
            policy_version=policy.policy_version,
            checked_at=checked_at,
        )


def _violation(code: RiskControlCode, message: str) -> RiskViolation:
    return RiskViolation(code=code, message=message)


def _position_quantity(account: PaperAccountSnapshot, symbol: str) -> int:
    return next((item.quantity for item in account.positions if item.symbol == symbol), 0)


def _require_aware_time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("checked_at must be timezone-aware.")
